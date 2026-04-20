#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import io
import json
import re
import urllib.request
import zipfile
from collections import defaultdict

from pathlib import Path

RELEASE_API = "https://api.github.com/repos/scriptin/jmdict-simplified/releases/latest"
BASE_DIR = Path(__file__).resolve().parent.parent
OUT_FILE = BASE_DIR / "data" / "proper_nouns.csv"

# Keep the most useful name categories for sentence-level PN tagging.
ALLOWED_TYPES = {
    "place", "surname", "given", "fem", "masc", "person",
    "station", "organization", "company"
}


def fetch_latest_jmnedict_zip_url():
    with urllib.request.urlopen(RELEASE_API) as response:
        payload = json.load(response)

    for asset in payload.get("assets", []):
        name = str(asset.get("name", "")).lower()
        if "jmnedict-all" in name and name.endswith(".json.zip"):
            return asset.get("browser_download_url")

    raise RuntimeError("Could not find JMnedict zip asset in latest release")


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


def main():
    print("Resolving latest JMnedict release...")
    zip_url = fetch_latest_jmnedict_zip_url()
    print(f"  {zip_url}")

    print("Downloading and parsing JMnedict JSON...")
    payload = download_json_from_zip(zip_url)
    words = payload.get("words", [])
    print(f"  entries: {len(words)}")

    lexicon = defaultdict(set)

    for entry in words:
        entry_types = set()
        for tr in entry.get("translation", []):
            for type_name in tr.get("type", []):
                if type_name in ALLOWED_TYPES:
                    entry_types.add(type_name)

        if not entry_types:
            continue

        forms = []
        for item in entry.get("kanji", []):
            forms.append(str(item.get("text", "")).strip())
        for item in entry.get("kana", []):
            forms.append(str(item.get("text", "")).strip())

        for form in forms:
            if not is_usable_word(form):
                continue
            lexicon[form].update(entry_types)

    print(f"  unique proper nouns: {len(lexicon)}")

    with open(OUT_FILE, "w", encoding="utf-8", newline="") as output:
        writer = csv.writer(output, delimiter="|")
        writer.writerow(["word", "types", "source"])
        for word in sorted(lexicon.keys()):
            writer.writerow([word, ",".join(sorted(lexicon[word])), "jmnedict"])

    print(f"Written {OUT_FILE}")


if __name__ == "__main__":
    main()
