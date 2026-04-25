from __future__ import annotations

import csv
import html
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JSON_PATH = ROOT / "input" / "sentences-all_v11.json"
SENTENCES_ONLY_PATH = ROOT / "input" / "sentences-only.csv"
OUTPUT_PATH = ROOT / "output" / "sentences-only-mp3-map.csv"

# Keep only Japanese letters/symbols that are useful for sentence identity.
KEEP_JAPANESE_RE = re.compile(r"[^ぁ-ゟ゠-ヿ㐀-䶿一-鿿豈-﫿々〆〤ーヶヵ]")
HTML_TAG_RE = re.compile(r"<[^>]+>")


def sanitize_japanese_sentence(value: str) -> str:
    text = html.unescape(value or "")
    text = HTML_TAG_RE.sub("", text)
    text = unicodedata.normalize("NFKC", text)
    text = KEEP_JAPANESE_RE.sub("", text)
    return text.strip()


def load_json_audio_index(json_path: Path) -> dict[str, list[str]]:
    text = json_path.read_text(encoding="utf-8", errors="ignore")
    index: dict[str, list[str]] = defaultdict(list)

    try:
        raw = json.loads(text)
        for item in raw:
            jap = str(item.get("jap", ""))
            audio_url = str(item.get("audio_jap", "")).strip()
            if not jap or not audio_url:
                continue

            key = sanitize_japanese_sentence(jap)
            if not key:
                continue

            if audio_url not in index[key]:
                index[key].append(audio_url)

        return index
    except json.JSONDecodeError:
        pass

    audio_re = re.compile(r'"audio_jap"\s*:\s*"((?:\\.|[^"\\])*)"')
    jap_re = re.compile(r'"jap"\s*:\s*"((?:\\.|[^"\\])*)"')

    current_audio: str | None = None
    current_jap: str | None = None

    for line in text.splitlines():
        audio_match = audio_re.search(line)
        if audio_match:
            current_audio = json.loads('"' + audio_match.group(1) + '"').strip()

        jap_match = jap_re.search(line)
        if jap_match:
            current_jap = json.loads('"' + jap_match.group(1) + '"')

        if line.strip().startswith('}') or line.strip().startswith('},'):
            if current_audio and current_jap:
                key = sanitize_japanese_sentence(current_jap)
                if key and current_audio not in index[key]:
                    index[key].append(current_audio)
            current_audio = None
            current_jap = None

    return index


def build_mapping_csv(sentences_only_path: Path, output_path: Path, audio_index: dict[str, list[str]]) -> tuple[int, int]:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    total_rows = 0
    matched_rows = 0

    with sentences_only_path.open("r", encoding="utf-8-sig", newline="") as input_file, output_path.open(
        "w", encoding="utf-8", newline=""
    ) as output_file:
        reader = csv.reader(input_file, delimiter=";")
        writer = csv.writer(output_file, delimiter=";", lineterminator="\n")

        header = next(reader, None)
        if not header or len(header) < 2:
            raise ValueError("Invalid sentences-only.csv format: expected at least 2 columns")

        writer.writerow(["id", "mp3_urls"])

        for row in reader:
            if len(row) < 2:
                continue

            sentence_id = row[0].strip()
            japanese_sentence = row[1]
            key = sanitize_japanese_sentence(japanese_sentence)
            urls = audio_index.get(key, [])

            if urls:
                matched_rows += 1

            writer.writerow([sentence_id, ",".join(urls)])
            total_rows += 1

    return total_rows, matched_rows


def main() -> None:
    audio_index = load_json_audio_index(JSON_PATH)
    total_rows, matched_rows = build_mapping_csv(SENTENCES_ONLY_PATH, OUTPUT_PATH, audio_index)

    print(f"JSON source: {JSON_PATH}")
    print(f"Sentences source: {SENTENCES_ONLY_PATH}")
    print(f"Output CSV: {OUTPUT_PATH}")
    print(f"Rows processed: {total_rows}")
    print(f"Rows matched: {matched_rows}")
    print(f"Rows unmatched: {total_rows - matched_rows}")


if __name__ == "__main__":
    main()
