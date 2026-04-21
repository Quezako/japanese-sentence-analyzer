"""
fetch_bunpro_vocab.py
---------------------
Interroge l'API Bunpro pour une liste de mots japonais et enregistre
les résultats (word, jlpt_level, tags, reading, meaning) dans un CSV.

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


def normalize_jlpt_level(value: str) -> str:
    """Garde uniquement les niveaux JLPT standards N1..N5."""
    raw = (value or '').strip().upper()
    if not raw:
        return ''
    if raw in {'N1', 'N2', 'N3', 'N4', 'N5'}:
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
        meaning = attrs.get("meaning", "") or ""
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
            "meaning": meaning,
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
            "meaning": "",
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

    # Charger les mots déjà traités pour pouvoir reprendre
    already_done = set()
    if os.path.exists(output_path):
        with open(output_path, encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="|")
            for row in reader:
                already_done.add(row.get("query", "").strip())
        print(f"{len(already_done)} mots déjà présents dans {output_path}, ils seront ignorés.")

    words_to_fetch = [w for w in words if w not in already_done]
    print(f"{len(words_to_fetch)} mots à interroger sur Bunpro.")

    fieldnames = ["query", "word", "reading", "meaning", "jlpt_level", "jlpt_level_raw", "tags"]
    write_header = not os.path.exists(output_path)

    with open(output_path, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter="|")
        if write_header:
            writer.writeheader()

        for i, word in enumerate(words_to_fetch):
            print(f"[{i+1}/{len(words_to_fetch)}] {word} ...", end=" ", flush=True)
            entries = search_word(word)
            for entry in entries:
                writer.writerow(entry)
            f.flush()
            found = [e for e in entries if e["word"]]
            if found:
                levels = [e["jlpt_level"] for e in found if e["jlpt_level"]]
                print(f"{len(found)} résultat(s), niveaux: {', '.join(levels) if levels else 'inconnu'}")
            else:
                print("aucun résultat")
            if delay > 0 and i < len(words_to_fetch) - 1:
                time.sleep(delay)

    print(f"\nTerminé. Résultats enregistrés dans {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Interroge l'API Bunpro vocab pour une liste de mots japonais.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--from-csv", metavar="CSV", help="CSV de test (colonne jlpt_no_katakana)")
    source.add_argument("--words", nargs="+", metavar="MOT", help="Mots à chercher en argument direct")
    source.add_argument("--words-file", metavar="FICHIER", help="Fichier texte, un mot par ligne")
    parser.add_argument("--output", default="data/bunpro-jlpt-api.csv", help="Fichier CSV de sortie (défaut: data/bunpro-jlpt-api.csv)")
    parser.add_argument("--delay", type=float, default=0.3, help="Délai en secondes entre chaque requête (défaut: 0.3)")
    args = parser.parse_args()

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
