#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pandas as pd
import re
from janome.tokenizer import Tokenizer
import os
import argparse
from collections import OrderedDict

# Initialize tokenizer
tokenizer = Tokenizer()


def load_level_map(file_path, key_column):
    if not os.path.exists(file_path):
        return {}
    df = pd.read_csv(file_path, sep='|', dtype=str).fillna('')
    if key_column not in df.columns or 'jlpt_level' not in df.columns:
        return {}
    mapping = {}
    for _, row in df.iterrows():
        key = str(row[key_column]).strip()
        level = str(row['jlpt_level']).strip().upper()
        if not key:
            continue
        if level not in {'N1', 'N2', 'N3', 'N4', 'N5'}:
            continue
        existing = mapping.get(key)
        if existing is None or get_jlpt_level(level) < get_jlpt_level(existing):
            mapping[key] = level
    return mapping


def load_pedagogical_map(file_path):
    """
    Load pedagogical vocabulary map: words whose 'real-world' JLPT level
    is lower (easier) than what the official dataset says.
    Returns dict: word -> (level, source)
    Only entries where level is valid N1-N5 are kept.
    """
    if not os.path.exists(file_path):
        return {}
    df = pd.read_csv(file_path, sep='|', dtype=str).fillna('')
    if 'word' not in df.columns or 'jlpt_level' not in df.columns:
        return {}
    mapping = {}
    for _, row in df.iterrows():
        key = str(row['word']).strip()
        level = str(row['jlpt_level']).strip().upper()
        source = str(row.get('source', 'pedagogical')).strip() if 'source' in df.columns else 'pedagogical'
        if not key or level not in {'N1', 'N2', 'N3', 'N4', 'N5'}:
            continue
        mapping[key] = (level, source)
    return mapping


def load_grammar_patterns(primary_file, fallback_file='grammar_patterns.csv'):
    frames = []

    if os.path.exists(primary_file):
        frames.append(pd.read_csv(primary_file, sep='|', dtype=str).fillna(''))

    if fallback_file and os.path.exists(fallback_file):
        frames.append(pd.read_csv(fallback_file, sep='|', dtype=str).fillna(''))

    if not frames:
        return pd.DataFrame(columns=['pattern', 'jlpt_level'])

    merged = pd.concat(frames, ignore_index=True)
    if 'pattern' not in merged.columns or 'jlpt_level' not in merged.columns:
        return pd.DataFrame(columns=['pattern', 'jlpt_level'])

    merged['pattern'] = merged['pattern'].astype(str).str.strip()
    merged['jlpt_level'] = merged['jlpt_level'].astype(str).str.strip().str.upper()
    merged = merged[(merged['pattern'] != '') & (merged['jlpt_level'].isin(['N1', 'N2', 'N3', 'N4', 'N5']))]
    merged = merged.drop_duplicates(subset=['pattern', 'jlpt_level'])
    return merged


def grammar_pattern_variants(pattern):
    variants = [pattern]
    if 'くらい' in pattern:
        variants.append(pattern.replace('くらい', 'ぐらい'))
    if 'ぐらい' in pattern:
        variants.append(pattern.replace('ぐらい', 'くらい'))
    return list(dict.fromkeys(variants))

def get_jlpt_level(level_str):
    """
    Convert level string to numeric value for comparison.
    Higher number = harder level (N1 is hardest)
    """
    if not level_str or level_str.strip() == '':
        return 0
    
    level_str = str(level_str).strip().upper()
    
    if 'N1' in level_str:
        return 5
    elif 'N2' in level_str:
        return 4
    elif 'N3' in level_str:
        return 3
    elif 'N4' in level_str:
        return 2
    elif 'N5' in level_str:
        return 1
    else:
        return 0

def numeric_to_jlpt(num):
    """Convert numeric level back to JLPT format"""
    if num >= 5:
        return 'N1'
    elif num >= 4:
        return 'N2'
    elif num >= 3:
        return 'N3'
    elif num >= 2:
        return 'N4'
    elif num >= 1:
        return 'N5'
    else:
        return '-'


def should_count_for_vocab(token):
    pos = token.part_of_speech.split(',')
    major = pos[0] if len(pos) > 0 else ''
    sub1 = pos[1] if len(pos) > 1 else ''
    sub2 = pos[2] if len(pos) > 2 else ''

    if major in {'助詞', '助動詞', '記号'}:
        return False
    if major == '動詞' and sub1 in {'非自立', '接尾'}:
        return False
    if major == '名詞' and sub1 in {'数', '代名詞'}:
        return False
    surface = token.surface if hasattr(token, 'surface') else ''
    if surface and re.fullmatch(r'[0-9０-９]+', surface):
        return False
    if major in {'名詞', '動詞', '形容詞', '副詞'}:
        return True
    return False


def detect_conjugation_details(sentence):
    details = OrderedDict()
    try:
        tokens = list(tokenizer.tokenize(sentence))
        for idx in range(len(tokens) - 1):
            current_token = tokens[idx]
            next_token = tokens[idx + 1]

            current_surface = current_token.surface
            next_base = next_token.base_form if hasattr(next_token, 'base_form') else next_token.surface
            next_pos = next_token.part_of_speech.split(',')
            next_major = next_pos[0] if len(next_pos) > 0 else ''
            next_sub1 = next_pos[1] if len(next_pos) > 1 else ''

            if current_surface in {'て', 'で'} and next_base == 'いる' and next_major == '動詞' and next_sub1 == '非自立':
                details['ている'] = 'N4'
    except Exception:
        return OrderedDict()

    return details

def analyze_vocabulary(sentence, vocab_map):
    """
    Analyze vocabulary in sentence and return highest JLPT level.
    Uses janome tokenizer to handle conjugated verbs and complex words.
    """
    max_level = 0
    details = OrderedDict()
    
    try:
        tokens = tokenizer.tokenize(sentence)
        for token in tokens:
            if not should_count_for_vocab(token):
                continue
            surface = token.surface
            base_form = token.base_form if hasattr(token, 'base_form') else surface
            found_level = None

            if base_form and base_form != '*':
                found_level = vocab_map.get(base_form)

            if not found_level and surface and surface != '*':
                found_level = vocab_map.get(surface)

            detail_key = base_form if base_form and base_form != '*' else surface
            if not detail_key:
                continue

            if found_level:
                level = get_jlpt_level(found_level)
                max_level = max(max_level, level)
                details[detail_key] = found_level
            else:
                details[detail_key] = '?'
    except Exception as e:
        print(f"Error analyzing vocabulary in '{sentence}': {e}")

    details_str = ','.join([f"{k}:{v}" for k, v in details.items()]) if details else '-'
    return numeric_to_jlpt(max_level), details_str

def analyze_vocab_pedagogical(sentence, vocab_map, pedagogical_map):
    """
    Same as analyze_vocabulary but overrides levels from pedagogical_map.
    Returns (level, details_str) only if the result differs from the strict analysis.
    details format: 'word:N5@minna'
    Returns ('-', '-') if identical to strict.
    """
    max_strict = 0
    max_peda = 0
    details = OrderedDict()

    try:
        tokens = tokenizer.tokenize(sentence)
        for token in tokens:
            if not should_count_for_vocab(token):
                continue
            surface = token.surface
            base_form = token.base_form if hasattr(token, 'base_form') else surface

            strict_level = None
            if base_form and base_form != '*':
                strict_level = vocab_map.get(base_form)
            if not strict_level and surface and surface != '*':
                strict_level = vocab_map.get(surface)

            detail_key = base_form if base_form and base_form != '*' else surface
            if not detail_key:
                continue

            # Check pedagogical override (for base_form or surface)
            peda_entry = pedagogical_map.get(base_form) or pedagogical_map.get(surface)

            if strict_level:
                strict_num = get_jlpt_level(strict_level)
                max_strict = max(max_strict, strict_num)

                if peda_entry:
                    peda_level, peda_source = peda_entry
                    peda_num = get_jlpt_level(peda_level)
                    # Only override if pedagogical is easier (lower number)
                    if peda_num < strict_num:
                        max_peda = max(max_peda, peda_num)
                        details[detail_key] = f"{peda_level}@{peda_source}"
                    else:
                        max_peda = max(max_peda, strict_num)
                        details[detail_key] = strict_level
                else:
                    max_peda = max(max_peda, strict_num)
                    details[detail_key] = strict_level
            else:
                # Word not in strict vocab
                if peda_entry:
                    peda_level, peda_source = peda_entry
                    peda_num = get_jlpt_level(peda_level)
                    max_peda = max(max_peda, peda_num)
                    details[detail_key] = f"{peda_level}@{peda_source}"
                else:
                    details[detail_key] = '?'
    except Exception as e:
        print(f"Error in pedagogical vocab analysis for '{sentence}': {e}")

    details_str = ','.join([f"{k}:{v}" for k, v in details.items()]) if details else '-'

    if max_peda == max_strict:
        # No difference: return same level as strict, no details needed
        return numeric_to_jlpt(max_strict), '-'

    return numeric_to_jlpt(max_peda), details_str


def analyze_kanji(sentence, kanji_map):
    """
    Analyze kanji in sentence and return highest JLPT level.
    Uses janome to extract kanji and their JLPT levels.
    """
    max_level = 0
    details = OrderedDict()
    
    try:
        for char in sentence:
            if not ('\u4e00' <= char <= '\u9fff'):
                continue
            level_str = kanji_map.get(char)
            if not level_str:
                continue
            level = get_jlpt_level(level_str)
            max_level = max(max_level, level)
            details[char] = level_str
    except Exception as e:
        print(f"Error analyzing kanji in '{sentence}': {e}")

    details_str = ','.join([f"{k}:{v}" for k, v in details.items()]) if details else '-'
    return numeric_to_jlpt(max_level), details_str

def analyze_grammar(sentence, grammar_patterns):
    """
    Analyze grammar patterns in sentence and return highest JLPT level.
    Matches regex patterns from grammar_patterns dataframe.
    """
    max_level = 0
    details = OrderedDict()
    
    try:
        for _, row in grammar_patterns.iterrows():
            pattern = str(row['pattern']).strip()
            if not pattern:
                continue
            level = get_jlpt_level(row['jlpt_level'])

            for variant in grammar_pattern_variants(pattern):
                try:
                    if re.search(variant, sentence):
                        max_level = max(max_level, level)
                        details[variant] = row['jlpt_level']
                        break
                except re.error:
                    if variant in sentence:
                        max_level = max(max_level, level)
                        details[variant] = row['jlpt_level']
                        break

        conjugation_details = detect_conjugation_details(sentence)
        for pattern, jlpt_level in conjugation_details.items():
            level = get_jlpt_level(jlpt_level)
            max_level = max(max_level, level)
            details[pattern] = jlpt_level
    except Exception as e:
        print(f"Error analyzing grammar in '{sentence}': {e}")

    details_str = ','.join([f"{k}:{v}" for k, v in details.items()]) if details else '-'
    return numeric_to_jlpt(max_level), details_str

def process_sentences(
    input_file,
    output_file,
    grammar_file='data/jlpt_grammar.csv',
    vocab_file='data/jlpt_vocab.csv',
    kanji_file='data/jlpt_kanji.csv',
    pedagogical_file='data/jlpt_vocab_pedagogical.csv',
    max_rows=None
):
    """
    Main function: reads input CSV, analyzes sentences, and writes output CSV
    
    Input CSV format: id;ja
    Output CSV format: id;sentence;vocab_level;kanji_level;grammar_level
    """
    
    vocab_map = load_level_map(vocab_file, 'word')
    kanji_map = load_level_map(kanji_file, 'kanji')
    pedagogical_map = load_pedagogical_map(pedagogical_file)
    print(f"Loaded vocab entries: {len(vocab_map)}")
    print(f"Loaded kanji entries: {len(kanji_map)}")
    print(f"Loaded pedagogical overrides: {len(pedagogical_map)}")

    grammar_patterns = load_grammar_patterns(grammar_file, fallback_file='grammar_patterns.csv')

    print(f"Loaded grammar patterns: {len(grammar_patterns)}")
    
    # Read input CSV
    print(f"Reading {input_file}...")
    try:
        df = pd.read_csv(input_file, sep=';', dtype={'sentence': str})
    except:
        # Try different encoding
        df = pd.read_csv(input_file, sep=';', encoding='utf-8', dtype={'sentence': str})
    
    # Assume columns are: id, sentence (or ja)
    if 'ja' in df.columns:
        df = df.rename(columns={'ja': 'sentence'})

    if max_rows is not None:
        df = df.head(max_rows).copy()
    
    print(f"Processing {len(df)} sentences...")
    
    # Analyze each sentence
    vocab_levels = []
    vocab_details = []
    vocab_peda_levels = []
    vocab_peda_details = []
    kanji_levels = []
    kanji_details = []
    grammar_levels = []
    grammar_details = []
    
    for idx, sentence in enumerate(df['sentence']):
        if idx % 100 == 0:
            print(f"  Progress: {idx}/{len(df)}")
        
        sentence = str(sentence).strip()
        
        vocab_level, vocab_detail = analyze_vocabulary(sentence, vocab_map)
        peda_level, peda_detail = analyze_vocab_pedagogical(sentence, vocab_map, pedagogical_map)
        kanji_level, kanji_detail = analyze_kanji(sentence, kanji_map)
        grammar_level, grammar_detail = analyze_grammar(sentence, grammar_patterns)

        vocab_levels.append(vocab_level)
        vocab_details.append(vocab_detail)
        vocab_peda_levels.append(peda_level)
        vocab_peda_details.append(peda_detail)
        kanji_levels.append(kanji_level)
        kanji_details.append(kanji_detail)
        grammar_levels.append(grammar_level)
        grammar_details.append(grammar_detail)
    
    # Create output dataframe
    output_df = df.copy()
    output_df.columns = ['id', 'sentence']
    output_df['vocab_jlpt_pedagogical'] = vocab_peda_levels
    output_df['vocab_pedagogical_details'] = vocab_peda_details
    output_df['vocab_jlpt'] = vocab_levels
    output_df['vocab_details'] = vocab_details
    output_df['kanji_jlpt'] = kanji_levels
    output_df['kanji_details'] = kanji_details
    output_df['grammar_jlpt'] = grammar_levels
    output_df['grammar_details'] = grammar_details
    
    # Write output CSV
    print(f"Writing results to {output_file}...")
    output_df.to_csv(output_file, sep=';', index=False, encoding='utf-8')
    
    print(f"Done! Processed {len(output_df)} sentences.")
    print(f"Output saved to {output_file}")
    
    return output_df

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='JLPT analyzer for Japanese sentences')
    parser.add_argument('--input', default='input/sentences-only.csv', help='Input CSV path')
    parser.add_argument('--output', default='output/sentences-with-levels.csv', help='Output CSV path')
    parser.add_argument('--grammar', default='data/jlpt_grammar.csv', help='Grammar patterns CSV path')
    parser.add_argument('--vocab', default='data/jlpt_vocab.csv', help='Vocabulary JLPT CSV path')
    parser.add_argument('--kanji', default='data/jlpt_kanji.csv', help='Kanji JLPT CSV path')
    parser.add_argument('--max-rows', type=int, default=None, help='Process only first N rows')
    parser.add_argument('--pedagogical', default='data/jlpt_vocab_pedagogical.csv', help='Pedagogical overrides CSV path')
    args = parser.parse_args()

    result = process_sentences(
        input_file=args.input,
        output_file=args.output,
        grammar_file=args.grammar,
        vocab_file=args.vocab,
        kanji_file=args.kanji,
        pedagogical_file=args.pedagogical,
        max_rows=args.max_rows
    )
    
    # Show sample
    print("\nSample of results:")
    print(result.head(10))
