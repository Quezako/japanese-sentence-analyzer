#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import io
import json
import os
import urllib.request
import zipfile

from pathlib import Path

RELEASE_API = "https://api.github.com/repos/scriptin/jmdict-simplified/releases/latest"
BASE_DIR = Path(__file__).resolve().parent.parent
OUT_JSON = BASE_DIR / "data" / "src" / "jmdict-eng-common.json"
OUT_WORDS = BASE_DIR / "data" / "src" / "jmdict_basic_words.csv"


def fetch_latest_jmdict_common_zip_url():
    with urllib.request.urlopen(RELEASE_API) as response:
        payload = json.load(response)

    for asset in payload.get("assets", []):
        name = str(asset.get("name", "")).lower()
        if "jmdict-eng-common" in name and name.endswith(".json.zip"):
            return asset.get("browser_download_url")

    raise RuntimeError("Could not find JMdict ENG common zip asset in latest release")


def download_json_from_zip(zip_url):
    with urllib.request.urlopen(zip_url) as response:
        zip_bytes = response.read()

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        json_names = [name for name in archive.namelist() if name.endswith(".json")]
        if not json_names:
            raise RuntimeError("No JSON file found in archive")
        with archive.open(json_names[0]) as json_file:
            return json.load(json_file)


def collect_forms(entry):
    forms = set()

    for item in entry.get("kanji", []):
        text = str(item.get("text", "")).strip()
        if text:
            forms.add(text)

    for item in entry.get("kana", []):
        text = str(item.get("text", "")).strip()
        if text:
            forms.add(text)

    return sorted(forms)


def main():
    print("Resolving latest JMdict ENG common release...")
    zip_url = fetch_latest_jmdict_common_zip_url()
    print(f"  {zip_url}")

    print("Downloading and parsing JMdict ENG common JSON...")
    payload = download_json_from_zip(zip_url)
    words = payload.get("words", [])
    print(f"  entries: {len(words)}")

    os.makedirs("data", exist_ok=True)

    with open(OUT_JSON, "w", encoding="utf-8") as output_json:
        json.dump(payload, output_json, ensure_ascii=False)
    print(f"Written {OUT_JSON}")

    total_forms = 0
    with open(OUT_WORDS, "w", encoding="utf-8", newline="") as output_csv:
        writer = csv.writer(output_csv, delimiter="|")
        writer.writerow(["word", "entry_id", "source"])

        for entry in words:
            entry_id = str(entry.get("id", "")).strip()
            forms = collect_forms(entry)
            for form in forms:
                writer.writerow([form, entry_id, "jmdict-eng-common"])
            total_forms += len(forms)

    print(f"Written {OUT_WORDS} (forms: {total_forms})")


if __name__ == "__main__":
    main()
