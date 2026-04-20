#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pandas as pd
import re
import html
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

    def _kata_to_hira(text):
        chars = []
        for char in str(text):
            code = ord(char)
            if 0x30A1 <= code <= 0x30F6:
                chars.append(chr(code - 0x60))
            else:
                chars.append(char)
        return ''.join(chars)

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

        # Spoken-form alias: if entry is kanji, also index its hiragana reading.
        # This makes vocabulary scoring less dependent on orthography.
        if re.search(r'[\u3400-\u9fff々〆ヶ]', key):
            try:
                tokens = list(tokenizer.tokenize(key))
                if len(tokens) == 1:
                    reading = getattr(tokens[0], 'reading', '')
                    if reading and reading != '*':
                        hira = _kata_to_hira(reading)
                        if hira and hira != key:
                            existing_hira = mapping.get(hira)
                            if existing_hira is None or get_jlpt_level(level) < get_jlpt_level(existing_hira):
                                mapping[hira] = level
            except Exception:
                pass
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

    def _kata_to_hira(text):
        chars = []
        for char in str(text):
            code = ord(char)
            if 0x30A1 <= code <= 0x30F6:
                chars.append(chr(code - 0x60))
            else:
                chars.append(char)
        return ''.join(chars)

    mapping = {}
    for _, row in df.iterrows():
        key = str(row['word']).strip()
        level = str(row['jlpt_level']).strip().upper()
        source = str(row.get('source', 'pedagogical')).strip() if 'source' in df.columns else 'pedagogical'
        if not key or level not in {'N1', 'N2', 'N3', 'N4', 'N5'}:
            continue
        mapping[key] = (level, source)

        if re.search(r'[\u3400-\u9fff々〆ヶ]', key):
            try:
                tokens = list(tokenizer.tokenize(key))
                if len(tokens) == 1:
                    reading = getattr(tokens[0], 'reading', '')
                    if reading and reading != '*':
                        hira = _kata_to_hira(reading)
                        if hira and hira != key:
                            existing = mapping.get(hira)
                            if existing is None or get_jlpt_level(level) < get_jlpt_level(existing[0]):
                                mapping[hira] = (level, source)
            except Exception:
                pass
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


def load_proper_nouns(file_path):
    """Load external proper noun lexicon as a set of words."""
    if not file_path or not os.path.exists(file_path):
        return set()
    try:
        df = pd.read_csv(file_path, sep='|', dtype=str).fillna('')
    except Exception:
        return set()

    if 'word' not in df.columns:
        return set()

    words = set()
    for word in df['word']:
        value = str(word).strip()
        if value:
            words.add(value)
    return words


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
    if major == '名詞' and sub1 == '非自立':
        return False
    if major == '名詞' and sub1 in {'数'}:
        return False
    surface = token.surface if hasattr(token, 'surface') else ''
    if surface and re.fullmatch(r'[0-9０-９]+', surface):
        return False
    if major in {'名詞', '動詞', '形容詞', '副詞'}:
        return True
    return False


def is_proper_noun_token(token):
    pos = token.part_of_speech.split(',')
    major = pos[0] if len(pos) > 0 else ''
    sub1 = pos[1] if len(pos) > 1 else ''
    return major == '名詞' and sub1 == '固有名詞'


def unknown_vocab_tag(token, detail_key=None, proper_nouns=None):
    if detail_key and proper_nouns and detail_key in proper_nouns:
        return 'PN'
    return 'PN' if is_proper_noun_token(token) else '?'


def get_counter_override_level(token):
    """Pedagogical fallback for very common counters in beginner contexts."""
    pos = token.part_of_speech.split(',')
    major = pos[0] if len(pos) > 0 else ''
    sub1 = pos[1] if len(pos) > 1 else ''
    sub2 = pos[2] if len(pos) > 2 else ''
    surface = token.surface if hasattr(token, 'surface') else ''

    if major == '名詞' and sub1 == '接尾' and sub2 == '助数詞' and surface in {'時', '分', '日', '歳', '回'}:
        return 'N5'
    return None


def clean_sentence_for_analysis(sentence):
    """Remove HTML tags/entities and normalize whitespace before analysis."""
    text = html.unescape(str(sentence))
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def is_meaningful_token_text(text):
    """Keep only tokens containing Japanese or alphanumeric characters."""
    if not text:
        return False
    return bool(re.search(r'[A-Za-z0-9Ａ-Ｚａ-ｚ０-９\u3040-\u30ff\u3400-\u9fff々〆ヶ]', text))


def is_katakana_word(text):
    """Return True when a token is composed only of katakana characters."""
    if not text:
        return False
    return bool(re.fullmatch(r'[\u30A0-\u30FF\uFF66-\uFF9F]+', text))


def katakana_to_hiragana(text):
    if not text:
        return ''
    chars = []
    for char in text:
        code = ord(char)
        if 0x30A1 <= code <= 0x30F6:
            chars.append(chr(code - 0x60))
        else:
            chars.append(char)
    return ''.join(chars)


def candidate_forms_for_lookup(base_form, surface, reading=None):
    """Build lookup candidates including honorific-prefix and reading variants."""
    candidates = []
    forms = [base_form, surface]

    has_kanji_input = False
    for f in [base_form, surface]:
        if not f or f == '*':
            continue
        if re.search(r'[\u3400-\u9fff々〆ヶ]', str(f)):
            has_kanji_input = True
            break

    if reading and reading != '*' and has_kanji_input:
        forms.append(katakana_to_hiragana(str(reading).strip()))

    for form in forms:
        if not form or form == '*':
            continue
        form = str(form).strip()
        if not form:
            continue
        candidates.append(form)
        if len(form) >= 2 and form[0] in {'お', 'ご'}:
            candidates.append('御' + form[1:])
            candidates.append(form[1:])
    return list(dict.fromkeys(candidates))


def pick_best_vocab_level(vocab_map, candidates):
    """Return easiest level found among candidates in vocab map."""
    best_level = None
    best_candidate = None
    for cand in candidates:
        level = vocab_map.get(cand)
        if not level:
            continue
        if best_level is None or get_jlpt_level(level) < get_jlpt_level(best_level):
            best_level = level
            best_candidate = cand
    return best_level, best_candidate


def pick_best_pedagogical_entry(pedagogical_map, candidates):
    """Return easiest pedagogical entry found among candidates."""
    best_entry = None
    best_candidate = None
    for cand in candidates:
        entry = pedagogical_map.get(cand)
        if not entry:
            continue
        level, _source = entry
        if best_entry is None or get_jlpt_level(level) < get_jlpt_level(best_entry[0]):
            best_entry = entry
            best_candidate = cand
    return best_entry, best_candidate


def is_tokenization_artifact(token):
    """Detect Janome artifacts like いつ -> い(いる)+つ and ignore them."""
    surface = token.surface if hasattr(token, 'surface') else ''
    base_form = token.base_form if hasattr(token, 'base_form') else surface
    pos = token.part_of_speech.split(',')
    major = pos[0] if len(pos) > 0 else ''

    if major != '動詞':
        return False
    if not surface or not base_form:
        return False

    # Single hiragana token analyzed as an independent verb is usually noise.
    if re.fullmatch(r'[ぁ-ゖ]', surface) and len(base_form) >= 2:
        return True

    return False


def is_honorific_prefix(token):
    """Return True if token is an お/ご honorific prefix (接頭詞,名詞接続)."""
    if token.surface not in ('お', 'ご', '御'):
        return False
    pos = token.part_of_speech.split(',')
    return pos[0] == '接頭詞'


def detect_conjugation_details(sentence):
    details = OrderedDict()
    try:
        tokens = list(tokenizer.tokenize(sentence))
        seen_honorific = False  # report お/ご only once per sentence
        for idx in range(len(tokens)):
            token = tokens[idx]

            # Honorific prefix お/ご → N5 grammar pattern
            if is_honorific_prefix(token) and not seen_honorific:
                details['お/ご(honorifique)'] = 'N5'
                seen_honorific = True

            if idx >= len(tokens) - 1:
                continue
            next_token = tokens[idx + 1]
            current_surface = token.surface
            next_base = next_token.base_form if hasattr(next_token, 'base_form') else next_token.surface
            next_pos = next_token.part_of_speech.split(',')
            next_major = next_pos[0] if len(next_pos) > 0 else ''
            next_sub1 = next_pos[1] if len(next_pos) > 1 else ''

            if current_surface in {'て', 'で'} and next_base == 'いる' and next_major == '動詞' and next_sub1 == '非自立':
                details['ている'] = 'N4'
    except Exception:
        return OrderedDict()

    return details


def detect_grammar_matches(sentence, grammar_patterns):
    """Return ordered grammar matches as list of (matched_pattern, jlpt_level)."""
    matches = []
    seen = set()
    try:
        for _, row in grammar_patterns.iterrows():
            pattern = str(row['pattern']).strip()
            if not pattern:
                continue
            jlpt_level = str(row['jlpt_level']).strip().upper()
            for variant in grammar_pattern_variants(pattern):
                matched = False
                if variant == 'ので':
                    # Avoid matching explanatory copula "のです" as conjunction "ので".
                    matched = bool(re.search(r'ので(?!す)', sentence))
                    if matched:
                        key = (variant, jlpt_level)
                        if key not in seen:
                            matches.append(key)
                            seen.add(key)
                    continue
                try:
                    matched = bool(re.search(variant, sentence))
                except re.error:
                    matched = variant in sentence

                if matched:
                    key = (variant, jlpt_level)
                    if key not in seen:
                        matches.append(key)
                        seen.add(key)
                    break
    except Exception:
        return []

    conjugation_details = detect_conjugation_details(sentence)
    for pattern, jlpt_level in conjugation_details.items():
        key = (pattern, jlpt_level)
        if key not in seen:
            matches.append(key)
            seen.add(key)

    return matches


def should_skip_vocab_due_to_grammar(detail_key, vocab_level, grammar_matches):
    """Suppress a vocab token if it is part of an easier matched grammar expression."""
    if not detail_key or not vocab_level or not grammar_matches:
        return False
    if len(detail_key) < 2:
        return False

    vocab_num = get_jlpt_level(vocab_level)
    for pattern, grammar_level in grammar_matches:
        grammar_num = get_jlpt_level(grammar_level)
        if grammar_num <= 0 or grammar_num >= vocab_num:
            continue
        if not pattern or pattern == detail_key:
            continue
        if len(pattern) <= len(detail_key):
            continue
        if detail_key in pattern:
            return True
    return False

def find_compound_matches(tokens, vocab_map, pedagogical_map=None):
    """
    Pre-pass: detect compound words split across consecutive tokens.
    Returns a dict: token_index -> (compound_word, strict_level, peda_entry)
    for the FIRST token of each matched compound. Consumed indices are also returned.
    Tries bigrammes and trigrammes (surface and base_form combinations).
    """
    matches = {}   # first_index -> (word, strict_level, peda_entry)
    consumed = set()
    n = len(tokens)

    for i in range(n):
        if i in consumed:
            continue
        # Try trigram then bigram
        for size in (3, 2):
            if i + size > n:
                continue
            group = tokens[i:i + size]

            # Do not create compounds across particles/auxiliaries/symbols
            blocked = False
            for t in group:
                pos = t.part_of_speech.split(',')
                major = pos[0] if len(pos) > 0 else ''
                if major in {'助詞', '助動詞', '記号'}:
                    blocked = True
                    break
                token_surface = t.surface if hasattr(t, 'surface') else ''
                token_base = t.base_form if hasattr(t, 'base_form') else token_surface
                token_text = token_base if token_base and token_base != '*' else token_surface
                if not is_meaningful_token_text(token_text):
                    blocked = True
                    break

            # Avoid compounding number/pronoun + counter suffix (e.g., 何分, 6時)
            if not blocked and size == 2:
                p0 = group[0].part_of_speech.split(',')
                p1 = group[1].part_of_speech.split(',')
                major0 = p0[0] if len(p0) > 0 else ''
                sub10 = p0[1] if len(p0) > 1 else ''
                major1 = p1[0] if len(p1) > 0 else ''
                sub11 = p1[1] if len(p1) > 1 else ''
                sub21 = p1[2] if len(p1) > 2 else ''
                if major0 == '名詞' and sub10 in {'数', '代名詞'} and major1 == '名詞' and sub11 == '接尾' and sub21 == '助数詞':
                    blocked = True

            if blocked:
                continue

            # Build candidate compound forms: surface concat and base_form concat
            surfaces = ''.join(t.surface for t in group)
            bases = ''.join(
                (t.base_form if hasattr(t, 'base_form') and t.base_form and t.base_form != '*' else t.surface)
                for t in group
            )
            reading_parts = []
            for t in group:
                r = getattr(t, 'reading', '') if hasattr(t, 'reading') else ''
                if not r or r == '*':
                    reading_parts = []
                    break
                reading_parts.append(r)
            reading = ''.join(reading_parts)
            candidates = list(dict.fromkeys([surfaces, bases]))  # deduplicated, order preserved
            if reading:
                candidates.append(katakana_to_hiragana(reading))
            # Also try stripping leading お/ご from compound
            for c in list(candidates):
                if c and c[0] in ('お', 'ご') and len(c) > 1:
                    candidates.append('御' + c[1:])
                    candidates.append(c[1:])

            strict_level, strict_word = pick_best_vocab_level(vocab_map, candidates)
            peda_entry, peda_word = (None, None)
            if pedagogical_map:
                peda_entry, peda_word = pick_best_pedagogical_entry(pedagogical_map, candidates)

            matched_word = strict_word or peda_word

            if matched_word:
                matches[i] = (matched_word, strict_level, peda_entry, set(range(i, i + size)))
                consumed.update(range(i, i + size))
                break  # don't try smaller size for same start index

    return matches, consumed


def analyze_vocabulary(sentence, vocab_map, grammar_matches=None, proper_nouns=None):
    """
    Analyze vocabulary in sentence and return highest JLPT level.
    Uses janome tokenizer to handle conjugated verbs and complex words.
    """
    max_level = 0
    details = OrderedDict()
    
    try:
        tokens = list(tokenizer.tokenize(sentence))
        compound_matches, consumed_by_compound = find_compound_matches(tokens, vocab_map)

        for idx, token in enumerate(tokens):
            # Compound check must happen before any filtering
            if idx in compound_matches:
                word, strict_level, _, _ = compound_matches[idx]
                if strict_level:
                    if should_skip_vocab_due_to_grammar(word, strict_level, grammar_matches):
                        continue
                    level = get_jlpt_level(strict_level)
                    max_level = max(max_level, level)
                    details[word] = strict_level
                else:
                    details[word] = unknown_vocab_tag(token, detail_key=word, proper_nouns=proper_nouns)
                continue

            if idx in consumed_by_compound:
                continue

            if not should_count_for_vocab(token):
                continue
            if is_tokenization_artifact(token):
                continue
            # Honorific prefix handled as grammar, skip in vocab
            if is_honorific_prefix(token):
                continue

            surface = token.surface
            base_form = token.base_form if hasattr(token, 'base_form') else surface
            reading = getattr(token, 'reading', '') if hasattr(token, 'reading') else ''

            counter_level = get_counter_override_level(token)
            if counter_level:
                detail_key = surface if surface else base_form
                if detail_key and is_meaningful_token_text(detail_key):
                    level = get_jlpt_level(counter_level)
                    max_level = max(max_level, level)
                    details[detail_key] = counter_level
                continue

            lookup_candidates = candidate_forms_for_lookup(base_form, surface, reading=reading)
            found_level, _ = pick_best_vocab_level(vocab_map, lookup_candidates)

            detail_key = base_form if base_form and base_form != '*' else surface
            if not detail_key:
                continue
            if not is_meaningful_token_text(detail_key):
                continue

            if found_level:
                if should_skip_vocab_due_to_grammar(detail_key, found_level, grammar_matches):
                    continue
                level = get_jlpt_level(found_level)
                max_level = max(max_level, level)
                details[detail_key] = found_level
            else:
                details[detail_key] = unknown_vocab_tag(token, detail_key=detail_key, proper_nouns=proper_nouns)
    except Exception as e:
        print(f"Error analyzing vocabulary in '{sentence}': {e}")

    details_str = ','.join([f"{k}:{v}" for k, v in details.items()]) if details else '-'
    return numeric_to_jlpt(max_level), details_str

def analyze_vocab_pedagogical(sentence, vocab_map, pedagogical_map, ignore_katakana=False, grammar_matches=None, proper_nouns=None):
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
        tokens = list(tokenizer.tokenize(sentence))
        compound_matches, consumed_by_compound = find_compound_matches(tokens, vocab_map, pedagogical_map)

        for idx, token in enumerate(tokens):
            # Compound check must happen before any filtering
            if idx in compound_matches:
                word, strict_level, peda_entry, _ = compound_matches[idx]
                detail_key = word
                if strict_level:
                    if should_skip_vocab_due_to_grammar(detail_key, strict_level, grammar_matches):
                        continue
                    strict_num = get_jlpt_level(strict_level)
                    max_strict = max(max_strict, strict_num)
                    if peda_entry:
                        peda_level, peda_source = peda_entry
                        peda_num = get_jlpt_level(peda_level)
                        if peda_num < strict_num:
                            max_peda = max(max_peda, peda_num)
                            details[detail_key] = f"{peda_level}@{peda_source}"
                        else:
                            max_peda = max(max_peda, strict_num)
                            details[detail_key] = strict_level
                    else:
                        max_peda = max(max_peda, strict_num)
                        details[detail_key] = strict_level
                elif peda_entry:
                    peda_level, peda_source = peda_entry
                    peda_num = get_jlpt_level(peda_level)
                    max_peda = max(max_peda, peda_num)
                    details[detail_key] = f"{peda_level}@{peda_source}"
                else:
                    details[detail_key] = unknown_vocab_tag(token, detail_key=detail_key, proper_nouns=proper_nouns)
                continue

            if idx in consumed_by_compound:
                continue

            if not should_count_for_vocab(token):
                continue
            if is_tokenization_artifact(token):
                continue
            # Honorific prefix handled as grammar, skip in vocab
            if is_honorific_prefix(token):
                continue

            surface = token.surface
            base_form = token.base_form if hasattr(token, 'base_form') else surface
            reading = getattr(token, 'reading', '') if hasattr(token, 'reading') else ''

            if ignore_katakana and (is_katakana_word(surface) or is_katakana_word(base_form)):
                continue

            counter_level = get_counter_override_level(token)
            if counter_level:
                detail_key = surface if surface else base_form
                if detail_key and is_meaningful_token_text(detail_key):
                    counter_num = get_jlpt_level(counter_level)
                    max_strict = max(max_strict, counter_num)
                    max_peda = max(max_peda, counter_num)
                    details[detail_key] = counter_level
                continue

            lookup_candidates = candidate_forms_for_lookup(base_form, surface, reading=reading)
            strict_level, _ = pick_best_vocab_level(vocab_map, lookup_candidates)

            detail_key = base_form if base_form and base_form != '*' else surface
            if not detail_key:
                continue
            if not is_meaningful_token_text(detail_key):
                continue

            # Check pedagogical override (for base_form or surface)
            peda_entry, _ = pick_best_pedagogical_entry(pedagogical_map, lookup_candidates)

            if strict_level:
                if should_skip_vocab_due_to_grammar(detail_key, strict_level, grammar_matches):
                    continue
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
                    details[detail_key] = unknown_vocab_tag(token, detail_key=detail_key, proper_nouns=proper_nouns)
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

def analyze_grammar(sentence, grammar_patterns, precomputed_matches=None):
    """
    Analyze grammar patterns in sentence and return highest JLPT level.
    Matches regex patterns from grammar_patterns dataframe.
    """
    max_level = 0
    details = OrderedDict()
    
    try:
        matches = precomputed_matches if precomputed_matches is not None else detect_grammar_matches(sentence, grammar_patterns)
        for pattern, jlpt_level in matches:
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
    proper_nouns_file='data/proper_nouns.csv',
    max_rows=None,
    offset=None,
    ids=None
):
    """
    Main function: reads input CSV, analyzes sentences, and writes output CSV
    
    Input CSV format: id;ja
    Output CSV format: id;sentence;vocab_level;kanji_level;grammar_level
    """
    
    vocab_map = load_level_map(vocab_file, 'word')
    kanji_map = load_level_map(kanji_file, 'kanji')
    pedagogical_map = load_pedagogical_map(pedagogical_file)
    proper_nouns = load_proper_nouns(proper_nouns_file)
    print(f"Loaded vocab entries: {len(vocab_map)}")
    print(f"Loaded kanji entries: {len(kanji_map)}")
    print(f"Loaded pedagogical overrides: {len(pedagogical_map)}")
    print(f"Loaded proper nouns: {len(proper_nouns)}")

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

    if 'id' not in df.columns:
        candidate_id_cols = [col for col in df.columns if col != 'sentence']
        if candidate_id_cols:
            df = df.rename(columns={candidate_id_cols[0]: 'id'})

    if 'id' not in df.columns:
        # Final fallback: use row index as id to keep processing possible
        df = df.reset_index().rename(columns={'index': 'id'})

    if ids:
        ids_set = {str(x).strip() for x in ids if str(x).strip() != ''}
        if ids_set:
            df = df[df['id'].astype(str).isin(ids_set)].copy()

    if offset is not None and offset > 0:
        df = df.iloc[offset:].copy()

    if max_rows is not None:
        df = df.head(max_rows).copy()
    
    print(f"Processing {len(df)} sentences...")
    
    # Analyze each sentence
    vocab_levels = []
    vocab_details = []
    no_katakana_levels = []
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
        analysis_sentence = clean_sentence_for_analysis(sentence)

        grammar_matches = detect_grammar_matches(analysis_sentence, grammar_patterns)

        vocab_level, vocab_detail = analyze_vocabulary(
            analysis_sentence,
            vocab_map,
            grammar_matches=grammar_matches,
            proper_nouns=proper_nouns
        )
        peda_level, peda_detail = analyze_vocab_pedagogical(
            analysis_sentence,
            vocab_map,
            pedagogical_map,
            grammar_matches=grammar_matches,
            proper_nouns=proper_nouns
        )
        no_kata_level, _ = analyze_vocab_pedagogical(
            analysis_sentence,
            vocab_map,
            pedagogical_map,
            ignore_katakana=True,
            grammar_matches=grammar_matches,
            proper_nouns=proper_nouns
        )

        # Keep pedagogical level unless removing katakana lowers the level.
        no_kata_num = get_jlpt_level(no_kata_level)
        peda_num = get_jlpt_level(peda_level)
        final_no_kata_level = no_kata_level if (no_kata_num > 0 and no_kata_num < peda_num) else peda_level

        kanji_level, kanji_detail = analyze_kanji(analysis_sentence, kanji_map)
        grammar_level, grammar_detail = analyze_grammar(analysis_sentence, grammar_patterns, precomputed_matches=grammar_matches)

        vocab_levels.append(vocab_level)
        vocab_details.append(vocab_detail)
        no_katakana_levels.append(final_no_kata_level)
        vocab_peda_levels.append(peda_level)
        vocab_peda_details.append(peda_detail)
        kanji_levels.append(kanji_level)
        kanji_details.append(kanji_detail)
        grammar_levels.append(grammar_level)
        grammar_details.append(grammar_detail)
    
    # Create output dataframe
    output_df = df.copy()
    output_df.columns = ['id', 'sentence']
    output_df['jlpt_no_katakana'] = no_katakana_levels
    output_df['vocab_jlpt_pedagogical'] = vocab_peda_levels
    output_df['vocab_pedagogical_details'] = vocab_peda_details
    output_df['vocab_jlpt_strict'] = vocab_levels
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


def resolve_output_file(user_output, max_rows=None, offset=None):
    """
    Resolve output path with only two default names:
      - full run: output/sentences-with-levels.csv
      - test run (offset or max_rows used): output/sentences-with-levels-test.csv
    If user_output is provided explicitly, keep it.
    """
    if user_output:
        return user_output

    is_test_run = (max_rows is not None) or (offset is not None and offset > 0)
    if is_test_run:
        return 'output/sentences-with-levels-test.csv'
    return 'output/sentences-with-levels.csv'

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='JLPT analyzer for Japanese sentences')
    parser.add_argument('--input', default='input/sentences-only.csv', help='Input CSV path')
    parser.add_argument('--output', default=None, help='Output CSV path (optional; auto-selects total/test filename if omitted)')
    parser.add_argument('--grammar', default='data/jlpt_grammar.csv', help='Grammar patterns CSV path')
    parser.add_argument('--vocab', default='data/jlpt_vocab.csv', help='Vocabulary JLPT CSV path')
    parser.add_argument('--kanji', default='data/jlpt_kanji.csv', help='Kanji JLPT CSV path')
    parser.add_argument('--proper-nouns', default='data/proper_nouns.csv', help='Proper nouns CSV path')
    parser.add_argument('--max-rows', type=int, default=None, help='Process only first N rows (after offset)')
    parser.add_argument('--offset', type=int, default=None, help='Skip first N rows before processing')
    parser.add_argument('--ids', default=None, help='Comma-separated IDs to process (e.g. 4058,4372,4434,4498)')
    parser.add_argument('--pedagogical', default='data/jlpt_vocab_pedagogical.csv', help='Pedagogical overrides CSV path')
    args = parser.parse_args()

    ids_list = None
    if args.ids:
        ids_list = [part.strip() for part in str(args.ids).split(',') if part.strip()]

    output_file = resolve_output_file(
        user_output=args.output,
        max_rows=args.max_rows,
        offset=args.offset,
    )

    result = process_sentences(
        input_file=args.input,
        output_file=output_file,
        grammar_file=args.grammar,
        vocab_file=args.vocab,
        kanji_file=args.kanji,
        proper_nouns_file=args.proper_nouns,
        pedagogical_file=args.pedagogical,
        max_rows=args.max_rows,
        offset=args.offset,
        ids=ids_list
    )
    
    # Show sample
    print("\nSample of results:")
    print(result.head(10))
