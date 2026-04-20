#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Extracts JLPT vocabulary from saved HTML files and converts to pipe-separated CSV.

Sources supported:
  - Bunpro deck HTML files (data/bunpro-voc-jlpt/n5-1.htm, n4-2.htm, etc.)
    Format: <p class="deck-card-title">私（わたし）</p> + level in <div class="contentable-type vocab">N5</div>
  - Nihoner vocabulary HTML files (data/bunpro-voc-jlpt/Nihoner/Vocabulary - Nihoner n5.htm)
    Format: <div class="jv-jp">花瓶</div> + <div class="jv-kana">かびん</div>
    Level is inferred from the filename (n5, n4, etc.)

Output:
    data/bunpro-voc-jlpt.csv   (word|kana|jlpt_level)
  data/nihoner-voc-jlpt.csv  (word|kana|jlpt_level|source)
"""

import os
import re
import glob
import pandas as pd
from bs4 import BeautifulSoup

BUNPRO_DIR = "data/bunpro-voc-jlpt"
NIHONER_DIR = "data/bunpro-voc-jlpt/Nihoner"
OUTPUT_BUNPRO = "data/bunpro-voc-jlpt.csv"
OUTPUT_NIHONER = "data/nihoner-voc-jlpt.csv"


def infer_level_from_filename(filename):
    """Extract JLPT level (N1-N5) from filename like n5-1.htm or Nihoner n5.htm."""
    m = re.search(r'n([1-5])', os.path.basename(filename).lower())
    if m:
        return f"N{m.group(1)}"
    return None


def parse_bunpro_title(title_text):
    """
    Parse '私（わたし）' or '本' or '会う（あう）' into (kanji_form, kana).
    Returns (word, kana) where kana may be empty.
    """
    title_text = title_text.strip()
    m = re.match(r'^(.+?)（(.+?)）', title_text)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return title_text, ''


def extract_bunpro(html_file):
    """Extract vocab items from a Bunpro deck HTML file."""
    items = []
    with open(html_file, encoding='utf-8', errors='ignore') as f:
        soup = BeautifulSoup(f, 'lxml')

    # Each card: div.js_decks-card_info contains level divs + title
    for card in soup.select('div.js_decks-card_info'):
        # Level: second div with class contentable-type vocab
        level_divs = card.select('div.contentable-type.vocab')
        level = None
        for d in level_divs:
            txt = d.get_text(strip=True).upper()
            if re.fullmatch(r'N[1-5]', txt):
                level = txt
                break

        # Title
        title_p = card.select_one('p.deck-card-title')
        if not title_p or not level:
            continue

        word, kana = parse_bunpro_title(title_p.get_text(strip=True))
        if word:
            items.append({'word': word, 'kana': kana, 'jlpt_level': level})

    return items


def extract_nihoner(html_file):
    """Extract vocab items from a Nihoner vocabulary HTML file."""
    level = infer_level_from_filename(html_file)
    if not level:
        print(f"  Could not infer level from: {html_file}")
        return []

    items = []
    with open(html_file, encoding='utf-8', errors='ignore') as f:
        soup = BeautifulSoup(f, 'lxml')

    # Each vocab card contains .jv-jp (kanji) and optionally .jv-kana
    # They are siblings inside a card container
    for jp_div in soup.select('div.jv-jp'):
        word = jp_div.get_text(strip=True)
        # Strip leading ～ or 〜
        word = word.lstrip('～〜')
        if not word:
            continue

        # kana sibling
        kana_div = jp_div.find_next_sibling('div', class_='jv-kana')
        kana = kana_div.get_text(strip=True) if kana_div else ''

        items.append({'word': word, 'kana': kana, 'jlpt_level': level, 'source': 'nihoner'})

    return items


def dedup(items):
    """Keep lowest level per word (same rule as strict vocab)."""
    LEVEL_NUM = {'N5': 1, 'N4': 2, 'N3': 3, 'N2': 4, 'N1': 5}
    seen = {}
    for item in items:
        word = item['word']
        lv = item['jlpt_level']
        existing = seen.get(word)
        if existing is None or LEVEL_NUM[lv] < LEVEL_NUM[existing['jlpt_level']]:
            seen[word] = item
    return list(seen.values())


def main():
    # --- Bunpro ---
    print("=== Bunpro ===")
    bunpro_files = sorted(glob.glob(os.path.join(BUNPRO_DIR, "*.htm")))
    bunpro_items = []
    for f in bunpro_files:
        items = extract_bunpro(f)
        print(f"  {os.path.basename(f)}: {len(items)} items")
        bunpro_items.extend(items)

    bunpro_items = dedup(bunpro_items)
    df_bp = pd.DataFrame(bunpro_items, columns=['word', 'kana', 'jlpt_level'])
    df_bp.sort_values(['jlpt_level', 'word'], inplace=True)
    df_bp.to_csv(OUTPUT_BUNPRO, sep='|', index=False)
    print(f"  → {len(df_bp)} unique entries written to {OUTPUT_BUNPRO}")

    # --- Nihoner ---
    print("\n=== Nihoner ===")
    nihoner_files = sorted(glob.glob(os.path.join(NIHONER_DIR, "*.htm")))
    nihoner_items = []
    for f in nihoner_files:
        items = extract_nihoner(f)
        print(f"  {os.path.basename(f)}: {len(items)} items")
        nihoner_items.extend(items)

    nihoner_items = dedup(nihoner_items)
    df_nih = pd.DataFrame(nihoner_items, columns=['word', 'kana', 'jlpt_level', 'source'])
    df_nih.sort_values(['jlpt_level', 'word'], inplace=True)
    df_nih.to_csv(OUTPUT_NIHONER, sep='|', index=False)
    print(f"  → {len(df_nih)} unique entries written to {OUTPUT_NIHONER}")

    # Show samples
    print("\nSample Bunpro:")
    print(df_bp.head(10).to_string(index=False))
    print("\nSample Nihoner:")
    print(df_nih.head(10).to_string(index=False))


if __name__ == '__main__':
    main()
