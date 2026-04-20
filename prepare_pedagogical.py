#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generates data/jlpt_vocab_pedagogical.csv by comparing:
  - "strict" dataset: data/jlpt_vocab.csv (source: Bluskyo)
    - "pedagogical" datasets:
            1) Bunpro extraction: data/bunpro-voc-jlpt.csv (priority)
            2) yomitan-jlpt-vocab (source: Waller / tanos.co.uk, fallback)

Only entries where the pedagogical level is LOWER (easier) than the strict level
are written to the output file. This avoids noise and only corrects over-ratings.

If a word is present in both Bunpro and Waller overrides, Bunpro is kept.

Output format (pipe-separated):
  word|jlpt_level|source
"""

import pandas as pd
import os
import sys

BASE_URL = "https://raw.githubusercontent.com/stephenmk/yomitan-jlpt-vocab/main/original_data/{level}.csv"
OUTPUT_FILE = "data/jlpt_vocab_pedagogical.csv"
STRICT_FILE = "data/jlpt_vocab.csv"
BUNPRO_FILE = "data/bunpro-voc-jlpt.csv"
BUNPRO_O_FILE = "data/bunpro-o-vocab-extracted.csv"

LEVEL_NUM = {'N5': 1, 'N4': 2, 'N3': 3, 'N2': 4, 'N1': 5}


def download_waller_vocab():
    """Download N1-N5 vocab from yomitan-jlpt-vocab and return a dict word -> level."""
    mapping = {}
    for level in ['n5', 'n4', 'n3', 'n2', 'n1']:
        url = BASE_URL.format(level=level)
        print(f"  Downloading {url} ...")
        try:
            df = pd.read_csv(url, dtype=str).fillna('')
            jlpt = level.upper()
            for _, row in df.iterrows():
                kana = str(row.get('kana', '')).strip()
                kanji = str(row.get('kanji', '')).strip()
                for word in [kana, kanji]:
                    if not word:
                        continue
                    existing = mapping.get(word)
                    if existing is None or LEVEL_NUM[jlpt] < LEVEL_NUM[existing]:
                        mapping[word] = jlpt
        except Exception as e:
            print(f"  ERROR downloading {url}: {e}")
    return mapping


def load_bunpro_vocab():
    """Load Bunpro extracted vocab map: word -> level."""
    if not os.path.exists(BUNPRO_FILE):
        print(f"  WARNING: {BUNPRO_FILE} not found, Bunpro source skipped.")
        return {}

    df = pd.read_csv(BUNPRO_FILE, sep='|', dtype=str).fillna('')
    if 'word' not in df.columns or 'jlpt_level' not in df.columns:
        print(f"  WARNING: invalid Bunpro format in {BUNPRO_FILE}, source skipped.")
        return {}

    mapping = {}
    for _, row in df.iterrows():
        word = str(row.get('word', '')).strip()
        level = str(row.get('jlpt_level', '')).strip().upper()
        if not word or level not in LEVEL_NUM:
            continue
        existing = mapping.get(word)
        if existing is None or LEVEL_NUM[level] < LEVEL_NUM[existing]:
            mapping[word] = level
    return mapping


def compute_overrides(source_map, strict_map, source_name):
    """Return word -> override entry when source level is easier than strict level."""
    overrides = {}
    for word, src_level in source_map.items():
        strict_level = strict_map.get(word)
        if strict_level is None:
            continue
        if LEVEL_NUM[src_level] < LEVEL_NUM[strict_level]:
            overrides[word] = {
                'word': word,
                'jlpt_level': src_level,
                'source': source_name,
            }
    return overrides


def compute_overrides_all(source_map, strict_map, source_name):
    """Like compute_overrides but also includes entries absent from the strict dataset.
    Used for bunpro-o which contains expressions not present in word-level strict data."""
    overrides = {}
    for word, src_level in source_map.items():
        strict_level = strict_map.get(word)
        if strict_level is None:
            # Word not in strict dataset: include it unconditionally
            overrides[word] = {
                'word': word,
                'jlpt_level': src_level,
                'source': source_name,
            }
        elif LEVEL_NUM[src_level] < LEVEL_NUM[strict_level]:
            overrides[word] = {
                'word': word,
                'jlpt_level': src_level,
                'source': source_name,
            }
    return overrides


def load_bunpro_o_vocab():
    """Load Bunpro-O extracted vocab map: word -> level (includes expressions)."""
    if not os.path.exists(BUNPRO_O_FILE):
        print(f"  WARNING: {BUNPRO_O_FILE} not found, bunpro-o source skipped.")
        return {}

    df = pd.read_csv(BUNPRO_O_FILE, sep='|', dtype=str).fillna('')
    if 'word' not in df.columns or 'jlpt_level' not in df.columns:
        print(f"  WARNING: invalid format in {BUNPRO_O_FILE}, source skipped.")
        return {}

    mapping = {}
    for _, row in df.iterrows():
        word = str(row.get('word', '')).strip()
        level = str(row.get('jlpt_level', '')).strip().upper()
        if not word or level not in LEVEL_NUM:
            continue
        existing = mapping.get(word)
        if existing is None or LEVEL_NUM[level] < LEVEL_NUM[existing]:
            mapping[word] = level
    return mapping


def load_strict_vocab():
    """Load the strict vocab map: word -> lowest level found."""
    if not os.path.exists(STRICT_FILE):
        print(f"ERROR: {STRICT_FILE} not found. Run prepare_datasets.py first.")
        sys.exit(1)
    df = pd.read_csv(STRICT_FILE, sep='|', dtype=str).fillna('')
    mapping = {}
    for _, row in df.iterrows():
        word = str(row.get('word', '')).strip()
        level = str(row.get('jlpt_level', '')).strip().upper()
        if not word or level not in LEVEL_NUM:
            continue
        existing = mapping.get(word)
        if existing is None or LEVEL_NUM[level] < LEVEL_NUM[existing]:
            mapping[word] = level
    return mapping


def main():
    print("Loading strict vocab dataset...")
    strict = load_strict_vocab()
    print(f"  {len(strict)} entries loaded.")

    print("Loading Bunpro-O extracted vocab (highest priority)...")
    bunpro_o = load_bunpro_o_vocab()
    print(f"  {len(bunpro_o)} entries loaded.")

    print("Computing Bunpro-O overrides (includes expressions absent from strict)...")
    bunpro_o_overrides = compute_overrides_all(bunpro_o, strict, 'bunpro-o')
    print(f"  {len(bunpro_o_overrides)} Bunpro-O overrides found.")

    print("Loading Bunpro pedagogical vocab...")
    bunpro = load_bunpro_vocab()
    print(f"  {len(bunpro)} entries loaded.")

    print("Computing Bunpro overrides (pedagogical level < strict level)...")
    bunpro_overrides = compute_overrides(bunpro, strict, 'bunpro')
    print(f"  {len(bunpro_overrides)} Bunpro overrides found.")

    print("Downloading Waller/yomitan pedagogical vocab...")
    pedagogical = download_waller_vocab()
    print(f"  {len(pedagogical)} entries loaded.")

    print("Computing Waller overrides (pedagogical level < strict level)...")
    waller_overrides = compute_overrides(pedagogical, strict, 'waller')
    print(f"  {len(waller_overrides)} Waller overrides found.")

    # Merge with priority: Bunpro-O > Bunpro > Waller
    merged = dict(waller_overrides)
    merged.update(bunpro_overrides)
    merged.update(bunpro_o_overrides)

    overrides = list(merged.values())
    overrides.sort(key=lambda x: (LEVEL_NUM[x['jlpt_level']], x['word']))
    print(f"  {len(overrides)} merged overrides found.")

    os.makedirs('data', exist_ok=True)
    out_df = pd.DataFrame(overrides, columns=['word', 'jlpt_level', 'source'])
    out_df.to_csv(OUTPUT_FILE, sep='|', index=False)
    print(f"Written to {OUTPUT_FILE}")

    # Show sample
    print("\nSample overrides:")
    print(out_df.head(30).to_string(index=False))

    sample_word = '週間'
    row = out_df[out_df['word'] == sample_word]
    if not row.empty:
        print(f"\nCheck {sample_word}: {row.iloc[0]['jlpt_level']} ({row.iloc[0]['source']})")
    else:
        print(f"\nCheck {sample_word}: not present in overrides")


if __name__ == '__main__':
    main()
