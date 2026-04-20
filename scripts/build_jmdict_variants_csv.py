#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_JSON = BASE_DIR / "data" / "src" / "jmdict-eng-common.json"
OUTPUT_CSV = BASE_DIR / "data" / "jmdict_word_variants.csv"


def get_forms(entry):
    forms = []
    for item in entry.get("kanji", []):
        text = str(item.get("text", "")).strip()
        if text:
            forms.append(text)
    for item in entry.get("kana", []):
        text = str(item.get("text", "")).strip()
        if text:
            forms.append(text)
    return sorted(set(forms))


def main():
    if not INPUT_JSON.exists():
        raise SystemExit(f"Missing input file: {INPUT_JSON}")

    with INPUT_JSON.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    words = payload.get("words", [])
    rows = []

    for entry in words:
        entry_id = str(entry.get("id", "")).strip()
        if not entry_id:
            continue
        forms = get_forms(entry)
        if len(forms) < 2:
            continue

        for word in forms:
            for variant in forms:
                if variant == word:
                    continue
                rows.append((word, variant, entry_id, "jmdict-eng-common"))

    rows = sorted(set(rows), key=lambda value: (value[0], value[1], value[2]))

    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="|")
        writer.writerow(["word", "variant", "entry_id", "source"])
        writer.writerows(rows)

    print(f"Written: {OUTPUT_CSV}")
    print(f"Rows: {len(rows)}")


if __name__ == "__main__":
    main()
