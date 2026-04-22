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


def load_word_level_source_map(file_path, word_col='word', level_col='jlpt_level', source_name='source'):
    """Load a generic word->(level, source) map from a pipe-separated CSV."""
    if not file_path or not os.path.exists(file_path):
        return {}
    try:
        df = pd.read_csv(file_path, sep='|', dtype=str).fillna('')
    except Exception:
        return {}

    if word_col not in df.columns or level_col not in df.columns:
        return {}

    mapping = {}
    for _, row in df.iterrows():
        word = str(row.get(word_col, '')).strip()
        level = str(row.get(level_col, '')).strip().upper()
        if not word or level not in {'N1', 'N2', 'N3', 'N4', 'N5'}:
            continue
        source = str(row.get(source_name, '')).strip() if source_name in df.columns else ''
        source = source if source else source_name

        existing = mapping.get(word)
        if existing is None or get_jlpt_level(level) < get_jlpt_level(existing[0]):
            mapping[word] = (level, source)
    return mapping


def load_word_raw_source_map(file_path, word_col='word', raw_col='jlpt_level_raw', source_name='source'):
    """Load a generic word->(raw_level, source) map for non-standard fallback labels such as NA5."""
    if not file_path or not os.path.exists(file_path):
        return {}
    try:
        df = pd.read_csv(file_path, sep='|', dtype=str).fillna('')
    except Exception:
        return {}

    if word_col not in df.columns or raw_col not in df.columns:
        return {}

    mapping = {}
    for _, row in df.iterrows():
        word = str(row.get(word_col, '')).strip()
        raw_level = str(row.get(raw_col, '')).strip().upper()
        if not word or not raw_level or raw_level == 'NUNCLASSIFIED':
            continue
        source = str(row.get(source_name, '')).strip() if source_name in df.columns else ''
        source = source if source else source_name
        mapping.setdefault(word, (raw_level, source))
    return mapping


def merge_pedagogical_maps(primary_map, fallback_map):
    """Merge fallback entries into pedagogical map, keeping the easiest level."""
    merged = dict(primary_map)
    for word, (level, source) in fallback_map.items():
        existing = merged.get(word)
        if existing is None or get_jlpt_level(level) < get_jlpt_level(existing[0]):
            merged[word] = (level, source)
    return merged


def load_open_anki_jlpt(folder_path):
    """
    Load vocabulary from open-anki-jlpt CSV files (n1.csv … n5.csv).
    Format: expression,reading,meaning,tags,guid
    Level is derived from the file name (n5 → N5, etc.).
    Returns dict: word -> (level, source)
    """
    if not folder_path or not os.path.exists(folder_path):
        return {}

    level_files = {
        'N5': 'n5.csv',
        'N4': 'n4.csv',
        'N3': 'n3.csv',
        'N2': 'n2.csv',
        'N1': 'n1.csv',
    }

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
    for level, filename in level_files.items():
        filepath = os.path.join(folder_path, filename)
        if not os.path.exists(filepath):
            continue
        try:
            df = pd.read_csv(filepath, dtype=str).fillna('')
        except Exception:
            continue
        if 'expression' not in df.columns:
            continue
        for _, row in df.iterrows():
            word = str(row['expression']).strip()
            if not word:
                continue
            existing = mapping.get(word)
            if existing is None or get_jlpt_level(level) < get_jlpt_level(existing[0]):
                mapping[word] = (level, 'open-anki')

            # Also index hiragana reading alias for kanji entries
            reading_col = 'reading' if 'reading' in df.columns else None
            if reading_col:
                reading = str(row.get(reading_col, '')).strip()
                if reading and reading != word and re.search(r'[\u3400-\u9fff々〆ヶ]', word):
                    hira = _kata_to_hira(reading)
                    if hira and hira != word:
                        existing_hira = mapping.get(hira)
                        if existing_hira is None or get_jlpt_level(level) < get_jlpt_level(existing_hira[0]):
                            mapping[hira] = (level, 'open-anki')
    return mapping


def load_common_words(file_path):
    """Load common non-JLPT words to tag as CO when unknown."""
    if not file_path or not os.path.exists(file_path):
        return set()

    try:
        df = pd.read_csv(file_path, sep='|', dtype=str).fillna('')
    except Exception:
        return set()

    if 'word' not in df.columns:
        return set()

    words = set()
    for value in df['word']:
        word = str(value).strip()
        if word:
            words.add(word)
    return words


def load_word_variants(file_path):
    """Load word->set(variants) mapping from a pipe-separated CSV."""
    if not file_path or not os.path.exists(file_path):
        return {}

    try:
        df = pd.read_csv(file_path, sep='|', dtype=str).fillna('')
    except Exception:
        return {}

    if 'word' not in df.columns or 'variant' not in df.columns:
        return {}

    mapping = {}
    for _, row in df.iterrows():
        word = str(row.get('word', '')).strip()
        variant = str(row.get('variant', '')).strip()
        if not word or not variant or word == variant:
            continue
        mapping.setdefault(word, set()).add(variant)

    return mapping


def expand_candidates_with_variants(candidates, variants_map, max_new=20):
    """Expand candidate forms with known lexical variants from JMdict."""
    if not candidates or not variants_map:
        return candidates

    expanded = list(candidates)
    seen = set(candidates)
    queue = list(candidates)
    added = 0

    while queue and added < max_new:
        current = queue.pop(0)
        for variant in variants_map.get(current, set()):
            if not variant or variant in seen:
                continue
            expanded.append(variant)
            seen.add(variant)
            queue.append(variant)
            added += 1
            if added >= max_new:
                break

    return expanded


def load_grammar_patterns(primary_file, fallback_file='data/grammar_patterns.csv'):
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
    if major in {'名詞', '動詞', '形容詞', '副詞', '感動詞', '連体詞'}:
        return True
    return False


def is_proper_noun_token(token):
    pos = token.part_of_speech.split(',')
    major = pos[0] if len(pos) > 0 else ''
    sub1 = pos[1] if len(pos) > 1 else ''
    return major == '名詞' and sub1 == '固有名詞'


HONORIFIC_SUFFIXES = {'さん', '様', 'さま', 'くん', 'ちゃん'}

def is_kanji_or_katakana_word(text):
    """Return True if text is composed only of kanji or katakana (typical name form)."""
    if not text:
        return False
    return bool(re.fullmatch(r'[\u4e00-\u9fff々\u30A0-\u30FF\uFF66-\uFF9FA-Za-zＡ-Ｚａ-ｚ]+', text))


def unknown_vocab_tag(token, detail_key=None, proper_nouns=None, common_words=None, candidates=None, prev_token=None, next_token=None):
    # Mot romaji/alphanumérique (A-Z0-9...) = élément étranger, traité N5
    if detail_key and re.fullmatch(r'[A-Za-z0-9]+', detail_key):
        return 'N5'
    # Katakana inconnu hors listes JLPT → tag KA
    if detail_key and is_katakana_word(detail_key):
        return 'KA'
    if detail_key and proper_nouns and detail_key in proper_nouns:
        return 'PN'
    if is_proper_noun_token(token):
        return 'PN'

    # Honorific suffix detection: if current token is an honorific suffix,
    # and the previous token is kanji or katakana → it was a proper name
    if detail_key in HONORIFIC_SUFFIXES:
        if prev_token is not None:
            prev_surface = prev_token.surface if hasattr(prev_token, 'surface') else ''
            if is_kanji_or_katakana_word(prev_surface):
                return 'PN'

    # Previous token is an honorific suffix → current is the name it referred to
    if prev_token is not None:
        prev_surface = prev_token.surface if hasattr(prev_token, 'surface') else ''
        if prev_surface in HONORIFIC_SUFFIXES and is_kanji_or_katakana_word(detail_key or ''):
            return 'PN'

    # Next token is an honorific suffix → current token is a proper name
    if next_token is not None:
        next_surface = next_token.surface if hasattr(next_token, 'surface') else ''
        if next_surface in HONORIFIC_SUFFIXES and is_kanji_or_katakana_word(detail_key or ''):
            return 'PN'

    candidate_values = []
    if detail_key:
        candidate_values.append(detail_key)
    if candidates:
        candidate_values.extend([str(c).strip() for c in candidates if c and str(c).strip()])

    if common_words:
        for value in candidate_values:
            if value in common_words:
                return 'CO'
    return '?'


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


def get_basic_counting_override_level(token):
    """Detect basic counting forms (e.g. ５月, ３つ) as N5."""
    surface = token.surface if hasattr(token, 'surface') else ''
    if not surface:
        return None
    text = str(surface).strip()
    if not text:
        return None

    number_prefix = r'[0-9０-９一二三四五六七八九十百千万何]+'
    basic_suffixes = r'(月|か月|ヶ月|つ)'
    if re.fullmatch(number_prefix + basic_suffixes, text):
        return 'N5'
    return None


def clean_sentence_for_analysis(sentence):
    """Remove HTML tags/entities and normalize whitespace before analysis."""
    text = html.unescape(str(sentence))
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(
        r'(?<=[\u3040-\u30ff\u3400-\u9fff々〆ヶ0-9０-９])\s+(?=[\u3040-\u30ff\u3400-\u9fff々〆ヶ0-9０-９])',
        '',
        text,
    )
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


def is_hiragana_word(text):
    if not text:
        return False
    return bool(re.fullmatch(r'[ぁ-ゖー]+', text))


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


def potential_to_base(word):
    """
    Reconstruit la forme de dictionnaire d’un verbe potentiel godan en -\u3048\u308b.
    Ex: \u8a00\u3048\u308b \u2192 \u8a00\u3046, \u66f8\u3051\u308b \u2192 \u66f8\u304f, \u8ac7\u305b\u308b \u2192 \u8ac7\u3059, \u4f1a\u3048\u308b \u2192 \u4f1a\u3046, \u8074\u304d\u53d6\u308c\u308b \u2192 \u8074\u304d\u53d6\u308b
    Renvoie None si le mot ne correspond pas au pattern.
    """
    e_to_u = {
        '\u3051': '\u304f',  # ke → ku
        '\u305b': '\u3059',  # se → su
        '\u3066': '\u3064',  # te → tsu
        '\u306d': '\u306c',  # ne → nu
        '\u3079': '\u3076',  # be → bu
        '\u3081': '\u3080',  # me → mu
        '\u308c': '\u308b',  # re → ru
        '\u3052': '\u3050',  # ge → gu
        '\u305c': '\u305a',  # ze → zu
        '\u3067': '\u3065',  # de → du
        '\u3078': '\u3075',  # he → fu
        '\u3048': '\u3046',  # e → u
    }
    if not word or not word.endswith('\u308b') or len(word) < 3:
        return None
    pre = word[:-1]  # retire le \u308b final
    if not pre:
        return None
    last_kana = pre[-1]
    if last_kana not in e_to_u:
        return None
    return pre[:-1] + e_to_u[last_kana]


def tokenization_repair_candidates(word):
    """Generate lookup candidates for common clipped-token artifacts."""
    if not word:
        return []

    form = str(word).strip()
    if not form:
        return []

    repaired = []

    if form.startswith('ょう'):
        repaired.append('いじ' + form)
        repaired.append('以上' + form[2:])
        repaired.extend(['いじょう', '以上'])

    if form.startswith('ゅう'):
        repaired.append('り' + form)

    if 'とはなした' in form:
        repaired.extend(['話す', 'はなす'])

    if form.startswith('ぺき'):
        repaired.append('かん' + form)
        repaired.append('完' + form)
        repaired.append('完璧')

    if form == 'はべる':
        repaired.extend(['べんり', '便利'])

    if form == 'だする':
        repaired.extend(['だす', '出す'])

    if form == 'むには':
        repaired.extend(['すむには', '住むには'])

    if form == 'もってこい':
        repaired.extend(['もってくる', '持ってくる'])

    if form == 'よがる':
        repaired.extend(['つよがる', '強がる'])

    return list(dict.fromkeys([x for x in repaired if x]))


def renyoukei_to_dictionary(word):
    """Convert a likely ren'yōkei stem (歩き, 言い, ふり...) to dictionary form."""
    kana_map = {
        'い': 'う',
        'き': 'く',
        'ぎ': 'ぐ',
        'し': 'す',
        'ち': 'つ',
        'に': 'ぬ',
        'び': 'ぶ',
        'み': 'む',
        'り': 'る',
    }
    if not word or len(word) < 2:
        return None
    last = word[-1]
    if last not in kana_map:
        return None
    return word[:-1] + kana_map[last]


def strip_trailing_particle(word):
    """Strip one trailing sentence particle to recover dictionary candidate (e.g. 本当は -> 本当)."""
    if not word or len(word) < 2:
        return None
    trailing_particles = {'は', 'が', 'を', 'に', 'で', 'と', 'も', 'の', 'ね', 'よ', 'か'}
    if word[-1] in trailing_particles:
        return word[:-1]
    return None


def infer_productive_suffix_level(token_text, vocab_map, pedagogical_map=None, variants_map=None):
    """
    Infer a JLPT level for productive formations (Vmasu+続ける/直す/始める, V+づらい, A+さ...).
    Returns (level, source) or (None, None).
    """
    if not token_text:
        return None, None
    text = str(token_text).strip()
    if len(text) < 2:
        return None, None

    suffix_levels = [
        ('つづける', 'N4'),
        ('続ける', 'N4'),
        ('なおす', 'N3'),
        ('直す', 'N3'),
        ('はじめる', 'N3'),
        ('始める', 'N3'),
        ('づらい', 'N3'),
        ('にくい', 'N3'),
        ('やすい', 'N4'),
        ('たて', 'N3'),
        ('さ', 'N3'),
    ]

    for suffix, suffix_level in suffix_levels:
        if not text.endswith(suffix):
            continue
        stem = text[:-len(suffix)]
        if not stem:
            continue

        stem_candidates = [stem]
        stem_stripped = strip_trailing_particle(stem)
        if stem_stripped:
            stem_candidates.append(stem_stripped)
        stem_dict = renyoukei_to_dictionary(stem)
        if stem_dict:
            stem_candidates.append(stem_dict)
        if stem_stripped:
            stripped_dict = renyoukei_to_dictionary(stem_stripped)
            if stripped_dict:
                stem_candidates.append(stripped_dict)

        stem_candidates = list(dict.fromkeys(stem_candidates))
        if variants_map:
            stem_candidates = expand_candidates_with_variants(stem_candidates, variants_map)

        strict_level, _ = pick_best_vocab_level(vocab_map, stem_candidates)
        peda_level = None
        if pedagogical_map:
            peda_entry, _ = pick_best_pedagogical_entry(pedagogical_map, stem_candidates)
            if peda_entry:
                peda_level = peda_entry[0]

        base_level = strict_level
        if peda_level and (not base_level or get_jlpt_level(peda_level) < get_jlpt_level(base_level)):
            base_level = peda_level
        if not base_level:
            continue

        combined_num = max(get_jlpt_level(base_level), get_jlpt_level(suffix_level))
        return numeric_to_jlpt(combined_num), f'heuristic-suffix:{suffix}'

    return None, None


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

        stripped = strip_trailing_particle(form)
        if stripped:
            candidates.append(stripped)

        renyoukei_dict = renyoukei_to_dictionary(form)
        if renyoukei_dict:
            candidates.append(renyoukei_dict)
        if stripped:
            stripped_dict = renyoukei_to_dictionary(stripped)
            if stripped_dict:
                candidates.append(stripped_dict)

        # Si la forme ressemble à un potentiel godan, ajouter aussi la base dict.
        non_potential = potential_to_base(form)
        if non_potential and non_potential not in candidates:
            candidates.append(non_potential)

        candidates.extend(tokenization_repair_candidates(form))
    return list(dict.fromkeys(candidates))


def detect_katakana_honorific_name(tokens, start_idx, suffixes):
    """Return (combined_name, end_idx) for katakana-sequence + honorific suffix, else (None, None)."""
    if start_idx < 0 or start_idx >= len(tokens):
        return None, None

    current = tokens[start_idx]
    current_surface = current.surface if hasattr(current, 'surface') else ''
    if not is_katakana_word(current_surface):
        return None, None

    name_parts = [current_surface]
    idx = start_idx + 1
    while idx < len(tokens):
        surface = tokens[idx].surface if hasattr(tokens[idx], 'surface') else ''
        if surface in suffixes:
            return ''.join(name_parts), idx
        if is_katakana_word(surface):
            name_parts.append(surface)
            idx += 1
            continue
        break

    return None, None


def infer_purpose_stem_candidates(tokens, idx):
    """Infer dictionary-form candidates for Xにいく/くる purpose pattern (e.g. ききにいく -> 聞く)."""
    if idx < 0 or idx + 2 >= len(tokens):
        return []

    token = tokens[idx]
    stem = token.surface if hasattr(token, 'surface') else ''
    if not stem or not is_hiragana_word(stem):
        return []

    next_token = tokens[idx + 1]
    next_surface = next_token.surface if hasattr(next_token, 'surface') else ''
    if next_surface != 'に':
        return []

    next_next = tokens[idx + 2]
    next_next_base = next_next.base_form if hasattr(next_next, 'base_form') else (next_next.surface if hasattr(next_next, 'surface') else '')
    if next_next_base not in {'いく', 'くる', '行く', '来る'}:
        return []

    prev_token = tokens[idx - 1] if idx > 0 else None
    prev_surface = prev_token.surface if prev_token is not None and hasattr(prev_token, 'surface') else ''
    if prev_surface not in {'を', 'が'}:
        return []

    godan_map = {
        'い': 'う', 'き': 'く', 'ぎ': 'ぐ', 'し': 'す', 'ち': 'つ',
        'に': 'ぬ', 'び': 'ぶ', 'み': 'む', 'り': 'る'
    }
    candidates = []
    last_char = stem[-1]
    if last_char in godan_map and len(stem) >= 1:
        candidates.append(stem[:-1] + godan_map[last_char])
    candidates.append(stem + 'る')
    return list(dict.fromkeys(candidates))


def is_likely_katakana_name_by_context(tokens, idx, has_katakana_proper_noun):
    """Heuristic: katakana noun near particles in a sentence that already contains a katakana PN."""
    if not has_katakana_proper_noun or idx < 0 or idx >= len(tokens):
        return False

    token = tokens[idx]
    surface = token.surface if hasattr(token, 'surface') else ''
    if not is_katakana_word(surface):
        return False

    pos = token.part_of_speech.split(',')
    major = pos[0] if len(pos) > 0 else ''
    sub1 = pos[1] if len(pos) > 1 else ''
    if major != '名詞' or sub1 == '固有名詞':
        return False

    prev_surface = tokens[idx - 1].surface if idx > 0 and hasattr(tokens[idx - 1], 'surface') else ''
    next_surface = tokens[idx + 1].surface if idx + 1 < len(tokens) and hasattr(tokens[idx + 1], 'surface') else ''
    particles = {'は', 'が', 'を', 'に', 'へ', 'で', 'と', 'も', 'の', 'や'}
    return prev_surface in particles or next_surface in particles


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


def pick_first_raw_fallback_entry(raw_fallback_map, candidates):
    """Return the first matching non-standard fallback entry found among candidates."""
    for cand in candidates:
        entry = raw_fallback_map.get(cand)
        if entry:
            return entry, cand
    return None, None


def has_non_katakana_unknown(details_str):
    """Return True if details contain an unknown token (?:) that is not katakana."""
    if not details_str or details_str == '-':
        return False

    for part in str(details_str).split(','):
        piece = part.strip()
        if not piece or ':' not in piece:
            continue
        key, _sep, value = piece.rpartition(':')
        key = key.strip()
        value = value.strip()
        if value != '?':
            continue
        if not key:
            continue
        if not is_katakana_word(key):
            return True
    return False


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

    # Single hiragana token analyzed as an independent verb is usually noise,
    # except for very common beginner verbs like いる that Janome may split as い + ます.
    if re.fullmatch(r'[ぁ-ゖ]', surface) and len(base_form) >= 2 and base_form not in {'いる'}:
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
                if variant == 'が':
                    # Match adversative/clause-final が, not the regular subject marker.
                    matched = bool(re.search(r'が(?=[、。]|$)', sentence))
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


def should_skip_vocab_due_to_grammar(detail_key, vocab_level, grammar_matches, lookup_candidates=None):
    """Suppress a vocab token if it is part of an easier matched grammar expression."""
    if not detail_key or not vocab_level or not grammar_matches:
        return False
    if len(detail_key) < 2:
        return False

    terms = {str(detail_key).strip()}
    if lookup_candidates:
        for candidate in lookup_candidates:
            text = str(candidate).strip()
            if len(text) >= 2:
                terms.add(text)

    vocab_num = get_jlpt_level(vocab_level)
    for pattern, grammar_level in grammar_matches:
        grammar_num = get_jlpt_level(grammar_level)
        if grammar_num <= 0 or grammar_num >= vocab_num:
            continue
        if not pattern:
            continue
        pattern = str(pattern).strip()
        if not pattern:
            continue
        for term in terms:
            if pattern == term:
                return True
            if len(pattern) <= len(term):
                continue
            if term in pattern:
                return True
    return False

def find_compound_matches(tokens, vocab_map, pedagogical_map=None, raw_fallback_map=None):
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
                sub1 = pos[1] if len(pos) > 1 else ''
                if major in {'助詞', '助動詞', '記号'}:
                    blocked = True
                    break
                if major == '名詞' and sub1 == '数':
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

            raw_entry, raw_word = (None, None)
            if raw_fallback_map:
                raw_entry, raw_word = pick_first_raw_fallback_entry(raw_fallback_map, candidates)

            matched_word = strict_word or peda_word or raw_word

            if matched_word:
                matches[i] = (matched_word, strict_level, peda_entry, raw_entry, set(range(i, i + size)))
                consumed.update(range(i, i + size))
                break  # don't try smaller size for same start index

    return matches, consumed


def analyze_vocabulary(sentence, vocab_map, grammar_matches=None, proper_nouns=None, common_words=None, supplemental_map=None, raw_fallback_map=None, variants_map=None):
    """
    Analyze vocabulary in sentence and return highest JLPT level.
    Uses janome tokenizer to handle conjugated verbs and complex words.
    """
    max_level = 0
    details = OrderedDict()
    
    try:
        tokens = list(tokenizer.tokenize(sentence))
        compound_matches, consumed_by_compound = find_compound_matches(tokens, vocab_map, supplemental_map, raw_fallback_map)
        consumed_by_name_span = set()
        has_katakana_proper_noun = any(
            is_katakana_word(tok.surface if hasattr(tok, 'surface') else '') and is_proper_noun_token(tok)
            for tok in tokens
        )

        for idx, token in enumerate(tokens):
            if idx in consumed_by_name_span:
                continue
            prev_token = tokens[idx - 1] if idx > 0 else None
            next_token = tokens[idx + 1] if idx < len(tokens) - 1 else None

            merged_name, honorific_idx = detect_katakana_honorific_name(tokens, idx, HONORIFIC_SUFFIXES)
            if merged_name:
                details[merged_name] = 'PN'
                suffix_surface = tokens[honorific_idx].surface if hasattr(tokens[honorific_idx], 'surface') else ''
                if suffix_surface:
                    details[suffix_surface] = 'PN'
                for consumed_idx in range(idx + 1, honorific_idx + 1):
                    consumed_by_name_span.add(consumed_idx)
                continue
            # Compound check must happen before any filtering
            if idx in compound_matches:
                word, strict_level, supplemental_entry, raw_entry, _ = compound_matches[idx]
                effective_level = strict_level
                if not effective_level and supplemental_map and supplemental_entry:
                    effective_level = supplemental_entry[0]

                if effective_level:
                    if should_skip_vocab_due_to_grammar(word, effective_level, grammar_matches):
                        continue
                    level = get_jlpt_level(effective_level)
                    max_level = max(max_level, level)
                    details[word] = effective_level
                elif raw_entry:
                    raw_level, raw_source = raw_entry
                    details[word] = f"{raw_level}@{raw_source}"
                else:
                    details[word] = unknown_vocab_tag(
                        token,
                        detail_key=word,
                        proper_nouns=proper_nouns,
                        common_words=common_words,
                        prev_token=prev_token,
                        next_token=next_token,
                    )
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
            # Honorific suffix (さん, 様, …): tag as PN and skip
            if token.surface in HONORIFIC_SUFFIXES:
                detail_key = token.surface
                if is_kanji_or_katakana_word(prev_token.surface if prev_token else ''):
                    details[detail_key] = 'PN'
                continue

            surface = token.surface
            base_form = token.base_form if hasattr(token, 'base_form') else surface
            reading = getattr(token, 'reading', '') if hasattr(token, 'reading') else ''

            basic_counting_level = get_basic_counting_override_level(token)
            if basic_counting_level:
                detail_key = surface if surface else base_form
                if detail_key and is_meaningful_token_text(detail_key):
                    level = get_jlpt_level(basic_counting_level)
                    max_level = max(max_level, level)
                    details[detail_key] = basic_counting_level
                continue

            counter_level = get_counter_override_level(token)
            if counter_level:
                detail_key = surface if surface else base_form
                if detail_key and is_meaningful_token_text(detail_key):
                    level = get_jlpt_level(counter_level)
                    max_level = max(max_level, level)
                    details[detail_key] = counter_level
                continue

            # Proper nouns (固有名詞) → tag PN immediately, do not look up in vocab
            if is_proper_noun_token(token):
                detail_key = surface if surface else base_form
                if detail_key and is_meaningful_token_text(detail_key):
                    details[detail_key] = 'PN'
                continue

            if is_likely_katakana_name_by_context(tokens, idx, has_katakana_proper_noun):
                detail_key = surface if surface else base_form
                if detail_key and is_meaningful_token_text(detail_key):
                    details[detail_key] = 'PN'
                continue

            lookup_candidates = candidate_forms_for_lookup(base_form, surface, reading=reading)
            lookup_candidates.extend(infer_purpose_stem_candidates(tokens, idx))
            lookup_candidates = list(dict.fromkeys(lookup_candidates))
            lookup_candidates = expand_candidates_with_variants(lookup_candidates, variants_map)
            found_level, _ = pick_best_vocab_level(vocab_map, lookup_candidates)

            if not found_level and supplemental_map:
                supplemental_entry, _ = pick_best_pedagogical_entry(supplemental_map, lookup_candidates)
                if supplemental_entry:
                    found_level = supplemental_entry[0]

            detail_key = base_form if base_form and base_form != '*' else surface
            if not detail_key:
                continue
            if not is_meaningful_token_text(detail_key):
                continue

            if not found_level:
                inferred_level, _ = infer_productive_suffix_level(
                    detail_key,
                    vocab_map,
                    pedagogical_map=supplemental_map,
                    variants_map=variants_map,
                )
                if inferred_level:
                    found_level = inferred_level

            raw_entry = None
            if not found_level and raw_fallback_map:
                raw_entry, _ = pick_first_raw_fallback_entry(raw_fallback_map, lookup_candidates)

            if found_level:
                if should_skip_vocab_due_to_grammar(detail_key, found_level, grammar_matches, lookup_candidates):
                    continue
                level = get_jlpt_level(found_level)
                max_level = max(max_level, level)
                details[detail_key] = found_level
            elif raw_entry:
                raw_level, raw_source = raw_entry
                details[detail_key] = f"{raw_level}@{raw_source}"
            else:
                details[detail_key] = unknown_vocab_tag(
                    token,
                    detail_key=detail_key,
                    proper_nouns=proper_nouns,
                    common_words=common_words,
                    candidates=lookup_candidates,
                    prev_token=prev_token,
                    next_token=next_token,
                )
    except Exception as e:
        print(f"Error analyzing vocabulary in '{sentence}': {e}")

    details_str = ','.join([f"{k}:{v}" for k, v in details.items()]) if details else '-'
    return numeric_to_jlpt(max_level), details_str

def analyze_vocab_pedagogical(sentence, vocab_map, pedagogical_map, ignore_katakana=False, grammar_matches=None, proper_nouns=None, common_words=None, raw_fallback_map=None, variants_map=None):
    """
    Same as analyze_vocabulary but overrides levels from pedagogical_map.
    Returns (level, details_str) only if the result differs from the strict analysis.
    details format: 'word:N5@minna'
    Returns ('-', '-') if identical to strict.
    """
    max_strict = 0
    max_peda = 0
    details = OrderedDict()
    used_raw_fallback = False

    try:
        tokens = list(tokenizer.tokenize(sentence))
        compound_matches, consumed_by_compound = find_compound_matches(tokens, vocab_map, pedagogical_map, raw_fallback_map)
        consumed_by_name_span = set()
        has_katakana_proper_noun = any(
            is_katakana_word(tok.surface if hasattr(tok, 'surface') else '') and is_proper_noun_token(tok)
            for tok in tokens
        )

        for idx, token in enumerate(tokens):
            if idx in consumed_by_name_span:
                continue
            prev_token = tokens[idx - 1] if idx > 0 else None
            next_token = tokens[idx + 1] if idx < len(tokens) - 1 else None

            merged_name, honorific_idx = detect_katakana_honorific_name(tokens, idx, HONORIFIC_SUFFIXES)
            if merged_name:
                details[merged_name] = 'PN'
                suffix_surface = tokens[honorific_idx].surface if hasattr(tokens[honorific_idx], 'surface') else ''
                if suffix_surface:
                    details[suffix_surface] = 'PN'
                for consumed_idx in range(idx + 1, honorific_idx + 1):
                    consumed_by_name_span.add(consumed_idx)
                continue
            # Compound check must happen before any filtering
            if idx in compound_matches:
                word, strict_level, peda_entry, raw_entry, _ = compound_matches[idx]
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
                    if should_skip_vocab_due_to_grammar(detail_key, peda_level, grammar_matches, [detail_key]):
                        continue
                    peda_num = get_jlpt_level(peda_level)
                    max_peda = max(max_peda, peda_num)
                    details[detail_key] = f"{peda_level}@{peda_source}"
                elif raw_entry:
                    raw_level, raw_source = raw_entry
                    details[detail_key] = f"{raw_level}@{raw_source}"
                    used_raw_fallback = True
                else:
                    details[detail_key] = unknown_vocab_tag(
                        token,
                        detail_key=detail_key,
                        proper_nouns=proper_nouns,
                        common_words=common_words,
                        prev_token=prev_token,
                        next_token=next_token,
                    )
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
            # Honorific suffix (さん, 様, …): tag as PN and skip
            if token.surface in HONORIFIC_SUFFIXES:
                detail_key = token.surface
                if is_kanji_or_katakana_word(prev_token.surface if prev_token else ''):
                    details[detail_key] = 'PN'
                continue

            surface = token.surface
            base_form = token.base_form if hasattr(token, 'base_form') else surface
            reading = getattr(token, 'reading', '') if hasattr(token, 'reading') else ''

            # Proper nouns (固有名詞) → tag PN immediately, do not look up in vocab
            if is_proper_noun_token(token):
                detail_key = surface if surface else base_form
                if detail_key and is_meaningful_token_text(detail_key):
                    details[detail_key] = 'PN'
                continue

            if is_likely_katakana_name_by_context(tokens, idx, has_katakana_proper_noun):
                detail_key = surface if surface else base_form
                if detail_key and is_meaningful_token_text(detail_key):
                    details[detail_key] = 'PN'
                continue

            if ignore_katakana and (is_katakana_word(surface) or is_katakana_word(base_form)):
                continue

            basic_counting_level = get_basic_counting_override_level(token)
            if basic_counting_level:
                detail_key = surface if surface else base_form
                if detail_key and is_meaningful_token_text(detail_key):
                    counting_num = get_jlpt_level(basic_counting_level)
                    max_strict = max(max_strict, counting_num)
                    max_peda = max(max_peda, counting_num)
                    details[detail_key] = basic_counting_level
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
            lookup_candidates.extend(infer_purpose_stem_candidates(tokens, idx))
            lookup_candidates = list(dict.fromkeys(lookup_candidates))
            lookup_candidates = expand_candidates_with_variants(lookup_candidates, variants_map)
            strict_level, _ = pick_best_vocab_level(vocab_map, lookup_candidates)

            detail_key = base_form if base_form and base_form != '*' else surface
            if not detail_key:
                continue
            if not is_meaningful_token_text(detail_key):
                continue

            # Check pedagogical override (for base_form or surface)
            peda_entry, _ = pick_best_pedagogical_entry(pedagogical_map, lookup_candidates)
            raw_entry = None
            if not strict_level and not peda_entry and raw_fallback_map:
                raw_entry, _ = pick_first_raw_fallback_entry(raw_fallback_map, lookup_candidates)

            if strict_level:
                if should_skip_vocab_due_to_grammar(detail_key, strict_level, grammar_matches, lookup_candidates):
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
                    if should_skip_vocab_due_to_grammar(detail_key, peda_level, grammar_matches, lookup_candidates):
                        continue
                    peda_num = get_jlpt_level(peda_level)
                    max_peda = max(max_peda, peda_num)
                    details[detail_key] = f"{peda_level}@{peda_source}"
                else:
                    inferred_level, inferred_source = infer_productive_suffix_level(
                        detail_key,
                        vocab_map,
                        pedagogical_map=pedagogical_map,
                        variants_map=variants_map,
                    )
                    if inferred_level:
                        if should_skip_vocab_due_to_grammar(detail_key, inferred_level, grammar_matches, lookup_candidates):
                            continue
                        inferred_num = get_jlpt_level(inferred_level)
                        max_peda = max(max_peda, inferred_num)
                        details[detail_key] = f"{inferred_level}@{inferred_source}"
                    elif raw_entry:
                        raw_level, raw_source = raw_entry
                        details[detail_key] = f"{raw_level}@{raw_source}"
                        used_raw_fallback = True
                    else:
                        details[detail_key] = unknown_vocab_tag(
                            token,
                            detail_key=detail_key,
                            proper_nouns=proper_nouns,
                            common_words=common_words,
                            candidates=lookup_candidates,
                            prev_token=prev_token,
                            next_token=next_token,
                        )
    except Exception as e:
        print(f"Error in pedagogical vocab analysis for '{sentence}': {e}")

    details_str = ','.join([f"{k}:{v}" for k, v in details.items()]) if details else '-'

    if max_peda == max_strict:
        # No difference: return same level as strict, no details needed
        if used_raw_fallback:
            return numeric_to_jlpt(max_strict), details_str
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
    bunpro_vocab_file='data/bunpro-voc-jlpt.csv',
    bunpro_api_file='data/bunpro-jlpt-api.csv',
    proper_nouns_file='data/proper_nouns.csv',
    common_vocab_file='data/common_vocab.csv',
    variants_file='data/jmdict_word_variants.csv',
    open_anki_folder='data/open-anki-jlpt',
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
    bunpro_fallback = load_word_level_source_map(
        bunpro_vocab_file,
        word_col='word',
        level_col='jlpt_level',
        source_name='bunpro',
    )
    pedagogical_map = merge_pedagogical_maps(pedagogical_map, bunpro_fallback)

    bunpro_api_by_word = load_word_level_source_map(
        bunpro_api_file,
        word_col='word',
        level_col='jlpt_level',
        source_name='bunpro-api',
    )
    bunpro_api_fallback = bunpro_api_by_word
    pedagogical_map = merge_pedagogical_maps(pedagogical_map, bunpro_api_fallback)
    bunpro_api_raw_fallback = load_word_raw_source_map(
        bunpro_api_file,
        word_col='word',
        raw_col='jlpt_level_raw',
        source_name='bunpro-api-raw',
    )

    open_anki_fallback = load_open_anki_jlpt(open_anki_folder)
    pedagogical_map = merge_pedagogical_maps(pedagogical_map, open_anki_fallback)
    proper_nouns = load_proper_nouns(proper_nouns_file)
    common_words = load_common_words(common_vocab_file)
    variants_map = load_word_variants(variants_file)
    print(f"Loaded vocab entries: {len(vocab_map)}")
    print(f"Loaded kanji entries: {len(kanji_map)}")
    print(f"Loaded pedagogical overrides: {len(pedagogical_map)}")
    print(f"Loaded Bunpro fallback entries: {len(bunpro_fallback)}")
    print(f"Loaded Bunpro API fallback entries: {len(bunpro_api_fallback)}")
    print(f"Loaded Bunpro API raw fallback entries: {len(bunpro_api_raw_fallback)}")
    print(f"Loaded Open-Anki-JLPT entries: {len(open_anki_fallback)}")
    print(f"Loaded proper nouns: {len(proper_nouns)}")
    print(f"Loaded common words (CO): {len(common_words)}")
    print(f"Loaded word variants: {len(variants_map)}")

    grammar_patterns = load_grammar_patterns(grammar_file, fallback_file='data/grammar_patterns.csv')

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
            proper_nouns=proper_nouns,
            common_words=common_words,
            supplemental_map=pedagogical_map,
            raw_fallback_map=bunpro_api_raw_fallback,
            variants_map=variants_map,
        )
        peda_level, peda_detail = analyze_vocab_pedagogical(
            analysis_sentence,
            vocab_map,
            pedagogical_map,
            grammar_matches=grammar_matches,
            proper_nouns=proper_nouns,
            common_words=common_words,
            raw_fallback_map=bunpro_api_raw_fallback,
            variants_map=variants_map,
        )
        no_kata_level, _ = analyze_vocab_pedagogical(
            analysis_sentence,
            vocab_map,
            pedagogical_map,
            ignore_katakana=True,
            grammar_matches=grammar_matches,
            proper_nouns=proper_nouns,
            common_words=common_words,
            raw_fallback_map=bunpro_api_raw_fallback,
            variants_map=variants_map,
        )

        # Keep pedagogical level unless removing katakana lowers the level.
        no_kata_num = get_jlpt_level(no_kata_level)
        peda_num = get_jlpt_level(peda_level)
        final_no_kata_level = no_kata_level if (no_kata_num > 0 and no_kata_num < peda_num) else peda_level

        # If there is an unknown non-katakana token, mark vocab levels as unknown.
        if has_non_katakana_unknown(vocab_detail):
            vocab_level = '?'
            peda_level = '?'
            final_no_kata_level = '?'

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


def filter_unknown_vocab_rows(output_df, detail_columns=None):
    """
    Debug helper: keep only rows containing unknown vocab markers ':?'
    in one of the specified detail columns.
    """
    if output_df is None or output_df.empty:
        return output_df

    if not detail_columns:
        detail_columns = ['vocab_details', 'vocab_pedagogical_details']

    valid_columns = [col for col in detail_columns if col in output_df.columns]
    if not valid_columns:
        return output_df.iloc[0:0].copy()

    mask = pd.Series(False, index=output_df.index)
    for col in valid_columns:
        mask = mask | output_df[col].fillna('').astype(str).str.contains(':\\?', regex=True)

    filtered_df = output_df[mask].copy()
    return filtered_df

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='JLPT analyzer for Japanese sentences')
    parser.add_argument('--input', default='input/sentences-only.csv', help='Input CSV path')
    parser.add_argument('--output', default=None, help='Output CSV path (optional; auto-selects total/test filename if omitted)')
    parser.add_argument('--grammar', default='data/jlpt_grammar.csv', help='Grammar patterns CSV path')
    parser.add_argument('--vocab', default='data/jlpt_vocab.csv', help='Vocabulary JLPT CSV path')
    parser.add_argument('--kanji', default='data/jlpt_kanji.csv', help='Kanji JLPT CSV path')
    parser.add_argument('--bunpro-vocab', default='data/bunpro-voc-jlpt.csv', help='Bunpro vocab CSV path')
    parser.add_argument('--bunpro-api', default='data/bunpro-jlpt-api.csv', help='Bunpro API vocab CSV path')
    parser.add_argument('--proper-nouns', default='data/proper_nouns.csv', help='Proper nouns CSV path')
    parser.add_argument('--common-vocab', default='data/common_vocab.csv', help='Common non-JLPT vocab CSV path for CO tagging')
    parser.add_argument('--variants', default='data/jmdict_word_variants.csv', help='Word variants CSV path for lexical variant lookup')
    parser.add_argument('--max-rows', type=int, default=None, help='Process only first N rows (after offset)')
    parser.add_argument('--offset', type=int, default=None, help='Skip first N rows before processing')
    parser.add_argument('--ids', default=None, help='Comma-separated IDs to process (e.g. 4058,4372,4434,4498)')
    parser.add_argument('--pedagogical', default='data/jlpt_vocab_pedagogical.csv', help='Pedagogical overrides CSV path')
    parser.add_argument('--open-anki', default='data/open-anki-jlpt', help='Folder containing open-anki-jlpt CSV files (n1.csv…n5.csv)')
    parser.add_argument('--unknown-only', action='store_true', help="Debug mode: keep only rows with ':?' unknown vocab markers")
    parser.add_argument('--unknown-columns', default='vocab_details,vocab_pedagogical_details', help='Comma-separated detail columns scanned by --unknown-only')
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
        bunpro_vocab_file=args.bunpro_vocab,
        bunpro_api_file=args.bunpro_api,
        proper_nouns_file=args.proper_nouns,
        common_vocab_file=args.common_vocab,
        variants_file=args.variants,
        pedagogical_file=args.pedagogical,
        open_anki_folder=args.open_anki,
        max_rows=args.max_rows,
        offset=args.offset,
        ids=ids_list
    )

    if args.unknown_only:
        unknown_columns = [c.strip() for c in str(args.unknown_columns).split(',') if c.strip()]
        filtered = filter_unknown_vocab_rows(result, detail_columns=unknown_columns)
        print(f"Debug unknown-only filter: {len(filtered)}/{len(result)} rows kept")
        print(f"Writing filtered debug output to {output_file}...")
        filtered.to_csv(output_file, sep=';', index=False, encoding='utf-8')
        result = filtered
    
    # Show sample
    print("\nSample of results:")
    print(result.head(10))
