"""
fetch_bunpro_vocab.py
---------------------
Interroge l'API Bunpro pour une liste de mots japonais et enregistre
les résultats (word, reading, jlpt_level, tags) dans un CSV.

Usage:
  # Depuis le CSV de test (colonne jlpt_no_katakana) :
  python fetch_bunpro_vocab.py --from-csv output/sentences-with-levels-test.csv

  # Depuis une liste de mots en argument :
  python fetch_bunpro_vocab.py --words 始発 出来上がる 退かす

  # Depuis un fichier texte (un mot par ligne) :
  python fetch_bunpro_vocab.py --words-file words.txt

  # Changer le fichier de sortie (défaut : data/bunpro-jlpt-api.csv) :
  python fetch_bunpro_vocab.py --from-csv output/sentences-with-levels-test.csv --output data/bunpro-jlpt-api.csv
"""

import argparse
import csv
import json
import os
import re
import sys
import time
import unicodedata

import requests

API_URL = "https://api.bunpro.jp/api/frontend/search/reviewables_v1_1"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:149.0) Gecko/20100101 Firefox/149.0",
    "Accept": "application/json",
    "Accept-Language": "fr-FR,en-US;q=0.9",
    "content-type": "application/json",
    "authorization": "Token token=null",
    "Origin": "https://bunpro.jp",
    "Referer": "https://bunpro.jp/",
    "DNT": "1",
}
PAYLOAD_TEMPLATE = {
    "options": {
        "include_reviews": True,
        "include_bookmarks": True,
        "include_notes": True,
        "only_bookmarks": False,
    },
    "is_searching_grammar": False,
    "is_searching_vocab": True,
}

JLPT_TAG_RE = re.compile(r'\bJLPT[_-]?(N?\d)\b', re.IGNORECASE)
OUTPUT_FIELDNAMES = ["word", "reading", "jlpt_level", "jlpt_level_raw", "tags"]
VALID_JLPT_LEVELS = {"N1", "N2", "N3", "N4", "N5"}
STATE_SUFFIX = ".state.json"

LETTER_NAME_MAP = {
    "あーる": "r",
    "あい": "i",
    "いー": "e",
    "う゛ぃ": "v",
    "えっくす": "x",
    "えっち": "h",
    "えぬ": "n",
    "えふ": "f",
    "えむ": "m",
    "える": "l",
    "えー": "a",
    "えす": "s",
    "おー": "o",
    "きゅー": "q",
    "けー": "k",
    "しー": "c",
    "じぇい": "j",
    "じぇー": "j",
    "じー": "g",
    "ずぃー": "z",
    "ぜっと": "z",
    "てぃー": "t",
    "てー": "t",
    "でぃー": "d",
    "でー": "d",
    "ぴー": "p",
    "びー": "b",
    "ふい": "v",
    "ぶい": "v",
    "ゆー": "u",
    "わい": "y",
    "だぶりゅー": "w",
    "えいち": "h",
}
LETTER_NAME_KEYS = sorted(LETTER_NAME_MAP.keys(), key=len, reverse=True)


def kata_to_hira(text: str) -> str:
    chars = []
    for char in str(text or ''):
        code = ord(char)
        if 0x30A1 <= code <= 0x30F6:
            chars.append(chr(code - 0x60))
        else:
            chars.append(char)
    return ''.join(chars)


def normalize_match_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold().strip()
    text = re.sub(r"[\s\u3000・･·•.。,，､/／_-]+", "", text)
    return text


def kana_letter_names_to_ascii(value: str) -> str:
    source = normalize_match_text(kata_to_hira(value))
    if not source:
        return ''

    letters = []
    index = 0
    while index < len(source):
        matched = False
        for key in LETTER_NAME_KEYS:
            if source.startswith(key, index):
                letters.append(LETTER_NAME_MAP[key])
                index += len(key)
                matched = True
                break
        if not matched:
            return ''
    return ''.join(letters)


def build_exact_match_keys(value: str) -> set[str]:
    keys = set()
    normalized = normalize_match_text(value)
    if normalized:
        keys.add(normalized)

    letter_name_ascii = kana_letter_names_to_ascii(value)
    if letter_name_ascii:
        keys.add(letter_name_ascii)

    return keys


def is_exact_match(query: str, word: str, reading: str) -> bool:
    query_keys = build_exact_match_keys(query)
    if not query_keys:
        return False
    candidate_keys = build_exact_match_keys(word) | build_exact_match_keys(reading)
    return bool(query_keys & candidate_keys)


def is_classified_entry(row: dict) -> bool:
    jlpt_level = str(row.get("jlpt_level", "")).strip().upper()
    jlpt_level_raw = str(row.get("jlpt_level_raw", "")).strip().upper()
    return jlpt_level in VALID_JLPT_LEVELS or (bool(jlpt_level_raw) and jlpt_level_raw != "NUNCLASSIFIED")


def should_keep_entry(row: dict) -> bool:
    word = str(row.get("word", "")).strip()
    if not word:
        return False

    query = str(row.get("query", "")).strip()
    reading = str(row.get("reading", "")).strip()
    if query and is_exact_match(query, word, reading):
        return True

    return is_classified_entry(row)


def project_output_row(row: dict) -> dict:
    return {field: str(row.get(field, "")).strip() for field in OUTPUT_FIELDNAMES}


def filter_and_deduplicate_rows(rows: list[dict]) -> list[dict]:
    filtered_rows = []
    seen = set()

    for row in rows:
        if 'query' in row:
            keep = should_keep_entry(row)
        else:
            keep = bool(str(row.get("word", "")).strip())

        if not keep:
            continue

        projected = project_output_row(row)
        key = tuple(projected[field] for field in OUTPUT_FIELDNAMES)
        if key in seen:
            continue
        seen.add(key)
        filtered_rows.append(projected)

    return filtered_rows


def state_path_for_output(output_path: str) -> str:
    return output_path + STATE_SUFFIX


def load_existing_output(output_path: str) -> tuple[list[dict], set[str]]:
    if not os.path.exists(output_path):
        return [], set()

    existing_rows = []
    processed_queries = set()
    with open(output_path, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="|")
        for row in reader:
            if not row:
                continue
            query = str(row.get("query", "")).strip()
            if query:
                processed_queries.add(query)
            existing_rows.append(row)
    return existing_rows, processed_queries


def load_processed_queries(output_path: str) -> set[str]:
    state_path = state_path_for_output(output_path)
    if not os.path.exists(state_path):
        return set()

    try:
        with open(state_path, encoding="utf-8") as f:
            payload = json.load(f)
    except Exception:
        return set()

    queries = payload.get("processed_queries", []) if isinstance(payload, dict) else []
    return {str(query).strip() for query in queries if str(query).strip()}


def save_processed_queries(output_path: str, processed_queries: set[str]) -> None:
    state_path = state_path_for_output(output_path)
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump({"processed_queries": sorted(processed_queries)}, f, ensure_ascii=False, indent=2)


def write_output_rows(output_path: str, rows: list[dict]) -> None:
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDNAMES, delimiter="|")
        writer.writeheader()
        for row in rows:
            writer.writerow(project_output_row(row))


def refilter_output_file(output_path: str) -> int:
    existing_rows, legacy_queries = load_existing_output(output_path)
    filtered_rows = filter_and_deduplicate_rows(existing_rows)
    write_output_rows(output_path, filtered_rows)

    processed_queries = load_processed_queries(output_path) | legacy_queries
    if processed_queries:
        save_processed_queries(output_path, processed_queries)

    return len(filtered_rows)


def normalize_jlpt_level(value: str) -> str:
    """Garde uniquement les niveaux JLPT standards N1..N5."""
    raw = (value or '').strip().upper()
    if not raw:
        return ''
    if raw in VALID_JLPT_LEVELS:
        return raw
    return ''


def extract_jlpt_from_tags(tags_str: str) -> str | None:
    """Extrait le niveau JLPT le plus élevé (= le plus facile) depuis une chaîne de tags."""
    if not tags_str:
        return None
    levels = []
    for m in JLPT_TAG_RE.finditer(tags_str):
        raw = m.group(1).upper()
        if not raw.startswith('N'):
            raw = 'N' + raw
        levels.append(raw)
    if not levels:
        return None
    order = {'N5': 0, 'N4': 1, 'N3': 2, 'N2': 3, 'N1': 4}
    levels.sort(key=lambda l: order.get(l, 99))
    return levels[0]  # niveau le plus facile


def search_word(word: str) -> list[dict]:
    """Appelle l'API Bunpro pour un mot et retourne la liste des entrées vocab trouvées."""
    payload = dict(PAYLOAD_TEMPLATE)
    payload["query"] = word
    try:
        resp = requests.post(API_URL, headers=HEADERS, json=payload, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"  [ERREUR] {word}: {e}", file=sys.stderr)
        return []

    results = []
    vocabs = data.get("vocabs", {}).get("data", [])
    for item in vocabs:
        attrs = item.get("attributes", {})
        vocab_word = attrs.get("title", "") or attrs.get("word", "") or ""
        reading = attrs.get("kana", "") or attrs.get("reading", "") or ""
        jlpt_level_raw = (attrs.get("jlpt_level", "") or "").strip().upper()
        if jlpt_level_raw and not jlpt_level_raw.startswith("N"):
            jlpt_level_raw = "N" + jlpt_level_raw
        jlpt_level = normalize_jlpt_level(jlpt_level_raw)
        # Récupérer les tags JMdict (part of speech)
        pos_list = attrs.get("jmdict_pos", []) or []
        tags_str = " ".join(pos_list) if isinstance(pos_list, list) else str(pos_list)
        results.append({
            "query": word,
            "word": vocab_word,
            "reading": reading,
            "jlpt_level": jlpt_level,
            "jlpt_level_raw": jlpt_level_raw,
            "tags": tags_str,
        })

    # Si aucun résultat direct, on enregistre quand même une ligne vide
    if not results:
        results.append({
            "query": word,
            "word": "",
            "reading": "",
            "jlpt_level": "",
            "jlpt_level_raw": "",
            "tags": "",
        })
    return results


def words_from_test_csv(csv_path: str) -> list[str]:
    """Extrait les mots depuis la colonne jlpt_no_katakana du CSV de test."""
    words = []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            val = row.get("jlpt_no_katakana", "").strip()
            if not val or val == "-":
                continue
            # Format attendu : 始発:N1 ou 退かす:?
            word = re.sub(r":.*", "", val).strip()
            if word and word not in words:
                words.append(word)
    return words


def words_from_file(path: str) -> list[str]:
    with open(path, encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def run(words: list[str], output_path: str, delay: float = 0.3):
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)

    existing_rows, legacy_queries = load_existing_output(output_path)
    already_done = load_processed_queries(output_path) | legacy_queries
    if already_done:
        print(f"{len(already_done)} mots déjà traités pour {output_path}, ils seront ignorés.")

    words_to_fetch = [w for w in words if w not in already_done]
    print(f"{len(words_to_fetch)} mots à interroger sur Bunpro.")

    all_rows = list(existing_rows)
    processed_queries = set(already_done)

    for i, word in enumerate(words_to_fetch):
        print(f"[{i+1}/{len(words_to_fetch)}] {word} ...", end=" ", flush=True)
        entries = search_word(word)
        all_rows.extend(entries)
        processed_queries.add(word)

        kept_entries = [entry for entry in entries if should_keep_entry(entry)]
        if kept_entries:
            levels = [e["jlpt_level"] for e in kept_entries if e["jlpt_level"]]
            print(f"{len(kept_entries)} résultat(s) conservé(s), niveaux: {', '.join(levels) if levels else 'inconnu'}")
        else:
            print("aucun résultat conservé")

        if delay > 0 and i < len(words_to_fetch) - 1:
            time.sleep(delay)

    filtered_rows = filter_and_deduplicate_rows(all_rows)
    write_output_rows(output_path, filtered_rows)
    save_processed_queries(output_path, processed_queries)

    print(f"\nTerminé. Résultats enregistrés dans {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Interroge l'API Bunpro vocab pour une liste de mots japonais.")
    source = parser.add_mutually_exclusive_group(required=False)
    source.add_argument("--from-csv", metavar="CSV", help="CSV de test (colonne jlpt_no_katakana)")
    source.add_argument("--words", nargs="+", metavar="MOT", help="Mots à chercher en argument direct")
    source.add_argument("--words-file", metavar="FICHIER", help="Fichier texte, un mot par ligne")
    parser.add_argument("--output", default="data/bunpro-jlpt-api.csv", help="Fichier CSV de sortie (défaut: data/bunpro-jlpt-api.csv)")
    parser.add_argument("--delay", type=float, default=0.3, help="Délai en secondes entre chaque requête (défaut: 0.3)")
    parser.add_argument("--refilter-output", action="store_true", help="Refiltre un CSV Bunpro existant avec les règles de conservation actuelles")
    args = parser.parse_args()

    if args.refilter_output and not any([args.from_csv, args.words, args.words_file]):
        kept_count = refilter_output_file(args.output)
        print(f"{kept_count} ligne(s) conservée(s) dans {args.output}")
        return

    if args.from_csv:
        words = words_from_test_csv(args.from_csv)
    elif args.words_file:
        words = words_from_file(args.words_file)
    else:
        words = args.words

    if not words:
        print("Aucun mot trouvé.", file=sys.stderr)
        sys.exit(1)

    run(words, args.output, delay=args.delay)


if __name__ == "__main__":
    main()
