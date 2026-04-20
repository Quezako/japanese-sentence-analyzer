#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import io
import json
import re
import urllib.request
import zipfile

from pathlib import Path

RELEASE_API = "https://api.github.com/repos/scriptin/jmdict-simplified/releases/latest"
BASE_DIR = Path(__file__).resolve().parent.parent
OUT_FILE = BASE_DIR / "data" / "common_vocab.csv"


def fetch_latest_jmdict_zip_url():
    with urllib.request.urlopen(RELEASE_API) as response:
        payload = json.load(response)

    for asset in payload.get("assets", []):
        name = str(asset.get("name", "")).lower()
        if "jmdict-eng" in name and name.endswith(".json.zip"):
            return asset.get("browser_download_url")

    raise RuntimeError("Could not find JMdict ENG zip asset in latest release")


def download_json_from_zip(zip_url):
    with urllib.request.urlopen(zip_url) as response:
        zip_bytes = response.read()

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        json_names = [name for name in archive.namelist() if name.endswith(".json")]
        if not json_names:
            raise RuntimeError("No JSON file found in archive")
        with archive.open(json_names[0]) as json_file:
            return json.load(json_file)


def is_usable_word(text):
    if not text:
        return False
    text = str(text).strip()
    if len(text) < 2:
        return False
    return bool(re.search(r"[A-Za-z\u3040-\u30ff\u3400-\u9fff々〆ヶ]", text))


def load_existing_manual_words(file_path):
    try:
        with open(file_path, "r", encoding="utf-8", newline="") as file:
            reader = csv.DictReader(file, delimiter="|")
            words = set()
            for row in reader:
                word = str(row.get("word", "")).strip()
                source = str(row.get("source", "")).strip().lower()
                if word and source.startswith("manual"):
                    words.add(word)
            return words
    except Exception:
        return set()


def collect_entry_forms(entry):
    forms = []
    for item in entry.get("kanji", []):
        text = str(item.get("text", "")).strip()
        if is_usable_word(text):
            forms.append((text, bool(item.get("common"))))

    for item in entry.get("kana", []):
        text = str(item.get("text", "")).strip()
        if is_usable_word(text):
            forms.append((text, bool(item.get("common"))))

    return forms


def main():
    print("Resolving latest JMdict release...")
    zip_url = fetch_latest_jmdict_zip_url()
    print(f"  {zip_url}")

    print("Downloading and parsing JMdict JSON...")
    payload = download_json_from_zip(zip_url)
    words = payload.get("words", [])
    print(f"  entries: {len(words)}")

    common_words = {}

    for entry in words:
        entry_forms = collect_entry_forms(entry)
        if not entry_forms:
            continue

        has_common_form = any(is_common for _text, is_common in entry_forms)
        if not has_common_form:
            continue

        for text, is_common in entry_forms:
            source = "jmdict-common" if is_common else "jmdict-variant"
            existing = common_words.get(text)
            if existing == "jmdict-common":
                continue
            common_words[text] = source

    manual_words = load_existing_manual_words(OUT_FILE)
    common_count = sum(1 for source in common_words.values() if source == "jmdict-common")
    variant_count = sum(1 for source in common_words.values() if source == "jmdict-variant")
    print(f"  JMdict common words: {common_count}")
    print(f"  JMdict variants from common entries: {variant_count}")
    print(f"  Existing manual words kept: {len(manual_words)}")

    with open(OUT_FILE, "w", encoding="utf-8", newline="") as output:
        writer = csv.writer(output, delimiter="|")
        writer.writerow(["word", "source"])

        for word in sorted(common_words):
            writer.writerow([word, common_words[word]])

        for word in sorted(manual_words):
            if word not in common_words:
                writer.writerow([word, "manual-common"])

    print(f"Written {OUT_FILE}")


if __name__ == "__main__":
    main()
