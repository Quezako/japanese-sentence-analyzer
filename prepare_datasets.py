#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import json
import re
from pathlib import Path
from urllib.request import urlopen

DATA_DIR = Path(__file__).parent / 'data'

VOCAB_URL = 'https://raw.githubusercontent.com/Bluskyo/JLPT_Vocabulary/main/data/results/JLPTWords.csv'
KANJI_URL = 'https://raw.githubusercontent.com/davidluzgouveia/kanji-data/master/kanji.json'
GRAMMAR_URL = 'https://raw.githubusercontent.com/skies18/jlpt-grammar-dictionary/main/src/data/grammar.json'


def _download_text(url: str) -> str:
    with urlopen(url) as response:
        return response.read().decode('utf-8')


def _num_to_jlpt(level_num: int) -> str:
    return f'N{level_num}'


def build_vocab_dataset() -> Path:
    raw = _download_text(VOCAB_URL)
    rows = list(csv.DictReader(raw.splitlines()))

    output_path = DATA_DIR / 'jlpt_vocab.csv'
    seen = set()
    with output_path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.writer(handle, delimiter='|')
        writer.writerow(['word', 'jlpt_level'])

        for row in rows:
            kanji = (row.get('Kanji') or '').strip()
            reading = (row.get('Reading') or '').strip()
            level_raw = (row.get('Level') or '').strip()
            if not level_raw.isdigit():
                continue

            jlpt = _num_to_jlpt(int(level_raw))

            candidates = [kanji]
            if not kanji and reading:
                candidates.append(reading)

            for candidate in candidates:
                if not candidate:
                    continue
                key = (candidate, jlpt)
                if key in seen:
                    continue
                seen.add(key)
                writer.writerow([candidate, jlpt])

    return output_path


def build_kanji_dataset() -> Path:
    raw = _download_text(KANJI_URL)
    payload = json.loads(raw)

    output_path = DATA_DIR / 'jlpt_kanji.csv'
    with output_path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.writer(handle, delimiter='|')
        writer.writerow(['kanji', 'jlpt_level'])

        for kanji, info in payload.items():
            jlpt_new = info.get('jlpt_new')
            if not isinstance(jlpt_new, int):
                continue
            if jlpt_new < 1 or jlpt_new > 5:
                continue
            writer.writerow([kanji, _num_to_jlpt(jlpt_new)])

    return output_path


def _cleanup_grammar_point(grammar_point: str) -> list[str]:
    text = grammar_point.strip()
    text = text.replace('〜', '').replace('～', '')
    text = text.replace('（', '(').replace('）', ')')
    text = re.sub(r'\s+', '', text)

    candidates = re.split(r'[／/・,，]|\bor\b', text)
    cleaned = []
    for candidate in candidates:
        candidate = candidate.strip()
        candidate = re.sub(r'\([^)]*\)', '', candidate)
        candidate = candidate.strip()
        if not candidate:
            continue
        if len(candidate) < 2:
            continue
        if len(candidate) == 2 and candidate in {'です', 'ます', 'でした', 'ません'}:
            continue
        cleaned.append(candidate)

    return cleaned


def build_grammar_dataset() -> Path:
    raw = _download_text(GRAMMAR_URL)
    rows = json.loads(raw)

    output_path = DATA_DIR / 'jlpt_grammar.csv'
    seen = set()
    with output_path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.writer(handle, delimiter='|')
        writer.writerow(['pattern', 'jlpt_level', 'source'])

        for row in rows:
            level = (row.get('level') or '').strip().upper()
            name = (row.get('name') or '').strip()
            if level not in {'N1', 'N2', 'N3', 'N4', 'N5'}:
                continue
            if not name:
                continue

            for pattern in _cleanup_grammar_point(name):
                key = (pattern, level)
                if key in seen:
                    continue
                seen.add(key)
                writer.writerow([pattern, level, 'skies18/jlpt-grammar-dictionary'])

    return output_path


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    vocab_path = build_vocab_dataset()
    kanji_path = build_kanji_dataset()
    grammar_path = build_grammar_dataset()

    print(f'Created: {vocab_path}')
    print(f'Created: {kanji_path}')
    print(f'Created: {grammar_path}')


if __name__ == '__main__':
    main()
