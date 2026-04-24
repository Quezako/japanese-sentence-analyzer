# Liste de tokens parasites à ignorer dans le scoring JLPT
PARASITE_TOKENS = {'間', 'たん', '真下', 'しん'}
# Particules japonaises de base
PARTICULES = {'は', 'が', 'を', 'に', 'へ', 'で', 'と', 'も', 'の', 'や'}
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
                            try:
                                reading_tokens = list(tokenizer.tokenize(hira))
                            except Exception:
                                reading_tokens = []
                            if len(reading_tokens) != 1:
                                continue
                            if not getattr(reading_tokens[0], 'part_of_speech', '').startswith('名詞'):
                                continue
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
                            try:
                                reading_tokens = list(tokenizer.tokenize(hira))
                            except Exception:
                                reading_tokens = []
                            if len(reading_tokens) != 1:
                                continue
                            if not getattr(reading_tokens[0], 'part_of_speech', '').startswith('名詞'):
                                continue
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
                        try:
                            reading_tokens = list(tokenizer.tokenize(hira))
                        except Exception:
                            reading_tokens = []
                        if len(reading_tokens) != 1:
                            continue
                        if not getattr(reading_tokens[0], 'part_of_speech', '').startswith('名詞'):
                            continue
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

HIRAGANA_KANJI_BLOCKLIST = {
    'どこ': {'何処'},
    'いる': {'煎る'},
    'いい': {'伊井', '委員'},
    'い': {'煎る'},
    'さいき': {'細工'},
    'しん': {'寝'},
    'しんせつ': {'切ない'},
    'せつ': {'切ない'},
    'たいせつ': {'切ない'},
    'ました': {'真下'},
    'はなした': {'貼る'},
    'ねる': {'練る'},
    'とって': {'取って'},
    'とんだ': {'飛んだ'},
    'でかける': {'出掛ける'},
    'はかない': {'儚い'},
}

TRAILING_PARTICLES = {'は', 'が', 'を', 'に', 'へ', 'で', 'と', 'も', 'の'}

def is_kanji_or_katakana_word(text):
    """Return True if text is composed only of kanji or katakana (typical name form)."""
    if not text:
        return False
    return bool(re.fullmatch(r'[\u4e00-\u9fff々\u30A0-\u30FF\uFF66-\uFF9FA-Za-zＡ-Ｚａ-ｚ]+', text))


def filter_lookup_candidates_by_surface(surface_text, candidates):
    """Filter obvious kana→kanji hallucinations for a given hiragana surface."""
    if not candidates:
        return []

    surface = str(surface_text or '').strip()
    blocked = HIRAGANA_KANJI_BLOCKLIST.get(surface, set())
    candidate_set = {str(c).strip() for c in candidates if c and str(c).strip()}

    filtered = []
    for cand in candidates:
        cand_text = str(cand).strip() if cand is not None else ''
        if not cand_text:
            continue

        if surface == 'がい' and cand_text == 'がい':
            continue

        if blocked and cand_text in blocked:
            continue

        if re.search(r'[\u3400-\u9fff々〆ヶ]', cand_text) and cand_text[-1] in TRAILING_PARTICLES:
            stripped = strip_trailing_particle(cand_text)
            if stripped and stripped in candidate_set:
                continue

        filtered.append(cand)

    return list(dict.fromkeys(filtered))


def unknown_vocab_tag(
    token,
    detail_key=None,
    proper_nouns=None,
    common_words=None,
    candidates=None,
    prev_token=None,
    next_token=None,
    bunpro_unclassified_words=None,
    bunpro_all_words=None,
):
    # Mot romaji/alphanumérique ASCII ou fullwidth (ＡＪＬＰＴ, ＬＤＫ, etc.) → N5
    if detail_key and re.fullmatch(r'[A-Za-z0-9Ａ-Ｚａ-ｚ０-９]+', detail_key):
        return 'N5'
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

    # Katakana unknown tagging is a last resort:
    # - KA  => found in Bunpro API but explicitly NUNCLASSIFIED
    # - KA? => katakana token absent from Bunpro API and all known data sources
    is_katakana_candidate = any(is_katakana_word(value) for value in candidate_values)
    if is_katakana_candidate and candidate_values:
        if bunpro_unclassified_words:
            for value in candidate_values:
                if value in bunpro_unclassified_words:
                    return 'KA'

        if bunpro_all_words:
            for value in candidate_values:
                if value in bunpro_all_words:
                    return '?'

        return 'KA?'

    # Mot présent dans Bunpro mais sans niveau JLPT (NUNCLASSIFIED) → UNC
    if bunpro_all_words and candidate_values:
        for value in candidate_values:
            if value in bunpro_all_words:
                return 'UNC'
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
    text = text.replace('\u3000', ' ')
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _word_tokens_are_grammatical_only(word_tokens):
    """Return True if all tokens produced by tokenizing a kanji word are purely grammatical
    (particles, auxiliaries, dependent verbs like する/いる/ある/くる/なる).
    Used to decide whether the hiragana reading of a word should be excluded from hira_map,
    because it would be indistinguishable from a grammatical sequence in a running sentence.

    A token is a genuine *content* token (→ return False) when:
      - major POS is 名詞/形容詞/副詞/連体詞 and sub-POS is NOT 非自立/接尾/数
      - major POS is 動詞,自立 with a base form that is not a common grammatical helper
        (する, いる, ある, くる, 来る, なる, もらう, やる, あげる).
    """
    _grammatical_verb_bases = {'する', 'いる', 'ある', 'くる', '来る', 'なる', 'もらう', 'やる', 'あげる'}

    for tok in word_tokens:
        pos  = tok.part_of_speech.split(',')
        major = pos[0] if pos else ''
        sub1  = pos[1] if len(pos) > 1 else ''

        if major in {'助詞', '助動詞', '記号', '接続詞', '感動詞', '接頭詞', '接尾詞'}:
            continue
        if major in {'名詞', '形容詞', '副詞', '連体詞'} and sub1 not in {'非自立', '接尾', '数'}:
            return False  # genuine content word
        if major == '動詞' and sub1 == '自立':
            base = (tok.base_form or '') if hasattr(tok, 'base_form') else ''
            if base and base != '*' and base not in _grammatical_verb_bases:
                return False  # genuine content verb
        # anything else is grammatical → keep looping

    return True  # only grammatical tokens found


def build_hiragana_to_kanji_map(vocab_map, supplemental_map=None):
    """Build a map: hiragana_reading -> kanji_form for all known multi-char kanji words.
    Used to post-normalize hiragana tokens produced by Janome tokenization.
    Only generates entries where the hiragana reading is pure hiragana (no kanji).

    Readings whose *kanji word* tokenizes to purely grammatical tokens (e.g. 指定 → し+て+い
    = 〜している) are excluded to prevent false-positive vocab matches on grammatical
    constructions inside sentences.  The check is done on the kanji word tokens (not the
    hiragana reading string) to avoid Janome mis-tokenizing double-consonant kana sequences
    like にっき which would otherwise be incorrectly excluded.
    """
    hira_map = {}

    def _kata_to_hira(text):
        return ''.join(chr(ord(c) - 0x60) if 0x30A1 <= ord(c) <= 0x30F6 else c for c in text)

    # Collect all kanji words from vocab maps
    kanji_words = {}
    for word in vocab_map:
        if re.search(r'[\u4e00-\u9fff]', word) and len(word) >= 2:
            kanji_words[word] = vocab_map[word]
    if supplemental_map:
        for word in supplemental_map:
            if re.search(r'[\u4e00-\u9fff]', word) and len(word) >= 2 and word not in kanji_words:
                entry = supplemental_map[word]
                kanji_words[word] = entry[0] if isinstance(entry, tuple) else entry

    for word in kanji_words:
        try:
            toks = list(tokenizer.tokenize(word))
            reading = ''.join(
                _kata_to_hira(getattr(tok, 'reading', '') or tok.surface)
                if (getattr(tok, 'reading', '') and getattr(tok, 'reading', '') != '*')
                else tok.surface
                for tok in toks
            )
            # Only map if reading is pure hiragana and differs from word (which has kanji)
            if not (reading and reading != word and re.fullmatch(r'[ぁ-ゖー]+', reading) and len(reading) >= 2):
                continue
            # Exclude words whose kanji tokenization is entirely grammatical (e.g. 指定 = し+て+い).
            # We test the kanji tokens (not the hiragana reading) to avoid Janome mis-tokenizing
            # double-consonant kana sequences such as にっき.
            if _word_tokens_are_grammatical_only(toks):
                continue
            # Prefer shorter (simpler) kanji form if collision
            if reading not in hira_map or len(word) < len(hira_map[reading]):
                hira_map[reading] = word
        except Exception:
            pass

    return hira_map


def normalize_hiragana_in_sentence(sentence, hira_map=None):
    """No longer used for whole-sentence substitution. See enrich_candidates_with_hira_map."""
    return sentence


def candidate_to_hiragana_key(text):
    """Return the full-hiragana reading key for a candidate when Janome can derive it."""
    if not text:
        return ''
    candidate = str(text).strip()
    if not candidate:
        return ''
    if re.fullmatch(r'[ぁ-ゖー]+', candidate):
        return candidate

    try:
        toks = list(tokenizer.tokenize(candidate))
    except Exception:
        return ''

    parts = []
    for tok in toks:
        reading = getattr(tok, 'reading', '') if hasattr(tok, 'reading') else ''
        surface = tok.surface if hasattr(tok, 'surface') else ''
        if reading and reading != '*':
            parts.append(katakana_to_hiragana(reading))
        elif surface:
            parts.append(surface)

    reading_key = ''.join(parts)
    if reading_key and re.fullmatch(r'[ぁ-ゖー]+', reading_key):
        return reading_key
    return ''


def enrich_candidates_with_hira_map(candidates, hira_map):
    """Add canonical kanji forms for *pure hiragana* candidates via reading lookup.

    Conservative rule: do NOT enrich mixed candidates (kanji+hiragana, particles+kanji, etc.).
    This avoids false positives such as `へ行き` -> `へいき` -> `兵器`.
    """
    if not hira_map or not candidates:
        return candidates
    extra = []
    for cand in candidates:
        cand_text = str(cand).strip()
        if not cand_text:
            continue
        if not re.fullmatch(r'[ぁ-ゖー]+', cand_text):
            continue
        reading_key = candidate_to_hiragana_key(cand)
        if reading_key and reading_key in hira_map:
            kanji_form = hira_map[reading_key]
            if kanji_form not in candidates:
                extra.append(kanji_form)
    return candidates + extra if extra else candidates


def get_small_kana_prefix_candidates(tokens, idx, hira_map, max_prefix_len=8):
    """When token[idx+1] starts with a small kana (artifact of mis-segmentation),
    try concatenating token[idx].surface with the beginning of token[idx+1].surface
    to reconstruct the original multi-char word, then look it up in hira_map."""
    if not hira_map or idx < 0 or idx >= len(tokens) - 1:
        return []
    current_surface = tokens[idx].surface if hasattr(tokens[idx], 'surface') else ''
    if not re.fullmatch(r'[ぁ-ゖー]+', current_surface):
        return []
    next_surface = tokens[idx + 1].surface if hasattr(tokens[idx + 1], 'surface') else ''
    if not next_surface or next_surface[0] not in SMALL_KANA:
        return []
    # Try current + increasing prefix of next_surface
    candidates = []
    for end in range(1, min(len(next_surface) + 1, max_prefix_len + 1)):
        merged = current_surface + next_surface[:end]
        if merged in hira_map:
            candidates.append(hira_map[merged])
            candidates.append(merged)
    return list(dict.fromkeys(candidates))


def get_prev_token_join_candidates(tokens, idx, max_prefix_len=8):
    """Join the previous token with the current kana token to recover split mixed forms."""
    if idx <= 0 or idx >= len(tokens):
        return []

    prev_surface = tokens[idx - 1].surface if hasattr(tokens[idx - 1], 'surface') else ''
    current_surface = tokens[idx].surface if hasattr(tokens[idx], 'surface') else ''
    current_base = tokens[idx].base_form if hasattr(tokens[idx], 'base_form') else current_surface

    if not prev_surface or not current_surface:
        return []
    if not re.search(r'[\u3040-\u30ff\u3400-\u9fff々〆ヶ]', prev_surface):
        return []
    if not re.fullmatch(r'[ぁ-ゖー]+', current_surface):
        return []

    # Conservative guard: only allow joins when previous token contains kanji or katakana.
    # This prevents pure-hiragana joins like は+いい -> はいい or まし+た -> ました,
    # which create many false positives via hira_map (e.g. 廃位 / 真下).
    if not re.search(r'[\u3400-\u9fff々〆ヶ\u30A0-\u30FF\uFF66-\uFF9F]', prev_surface):
        return []

    candidates = [prev_surface + current_surface]
    if current_base and current_base != '*' and re.fullmatch(r'[ぁ-ゖー]+', current_base):
        candidates.append(prev_surface + current_base)

    for end in range(1, min(len(current_surface), max_prefix_len) + 1):
        candidates.append(prev_surface + current_surface[:end])
    if current_base and current_base != '*':
        for end in range(1, min(len(current_base), max_prefix_len) + 1):
            candidates.append(prev_surface + current_base[:end])

    expanded = []
    for cand in candidates:
        expanded.append(cand)
        non_potential = potential_to_base(cand)
        if non_potential:
            expanded.append(non_potential)

    return list(dict.fromkeys([cand for cand in expanded if cand]))


def get_prev_kana_sequence_join_candidates(tokens, idx, max_back_tokens=4):
    """Join contiguous previous kana tokens with current token (e.g. ね+み+ー -> ねみー)."""
    if idx <= 0 or idx >= len(tokens):
        return []

    current_surface = tokens[idx].surface if hasattr(tokens[idx], 'surface') else ''
    current_base = tokens[idx].base_form if hasattr(tokens[idx], 'base_form') else current_surface
    if not current_surface or not re.fullmatch(r'[ぁ-ゖー]+', current_surface):
        return []

    seq = []
    pointer = idx - 1
    while pointer >= 0 and len(seq) < max_back_tokens:
        prev_surface = tokens[pointer].surface if hasattr(tokens[pointer], 'surface') else ''
        if not prev_surface or not re.fullmatch(r'[ぁ-ゖー]+', prev_surface):
            break
        seq.append(prev_surface)
        pointer -= 1

    if not seq:
        return []

    seq = list(reversed(seq))
    # Conservative mode: only join when there is an explicit artifact signal
    # (small kana boundary or standalone prolonged mark token).
    all_parts = seq + [current_surface]
    has_artifact_signal = any(
        (part and (part[0] in SMALL_KANA or part == 'ー'))
        for part in all_parts
    )
    if not has_artifact_signal:
        return []

    candidates = []
    for size in range(1, len(seq) + 1):
        prefix = ''.join(seq[-size:])
        candidates.append(prefix + current_surface)
        if current_base and current_base != '*' and re.fullmatch(r'[ぁ-ゖー]+', current_base):
            candidates.append(prefix + current_base)

    return list(dict.fromkeys([cand for cand in candidates if cand]))


def get_prev_honorific_residue_candidates(tokens, idx):
    """Recover compounds like お釣り / お腹 when the previous consumed token ends with お/ご."""
    if idx <= 0 or idx >= len(tokens):
        return []

    prev_surface = tokens[idx - 1].surface if hasattr(tokens[idx - 1], 'surface') else ''
    current_surface = tokens[idx].surface if hasattr(tokens[idx], 'surface') else ''
    current_base = tokens[idx].base_form if hasattr(tokens[idx], 'base_form') else current_surface

    if not prev_surface or prev_surface[-1] not in {'お', 'ご'}:
        return []
    if not current_surface or not is_meaningful_token_text(current_surface):
        return []

    candidates = [prev_surface[-1] + current_surface]
    if current_base and current_base != '*':
        candidates.append(prev_surface[-1] + current_base)
    return list(dict.fromkeys([cand for cand in candidates if cand]))


def expand_compound_lookup_candidates(candidates, variants_map=None, hira_map=None):
    """Apply lightweight normalization helpers to compound lookup candidates."""
    expanded = list(dict.fromkeys([cand for cand in candidates if cand]))
    extra = []
    for cand in expanded:
        non_potential = potential_to_base(cand)
        if non_potential:
            extra.append(non_potential)
    expanded.extend(extra)
    expanded = list(dict.fromkeys(expanded))
    expanded = expand_candidates_with_variants(expanded, variants_map)
    expanded = enrich_candidates_with_hira_map(expanded, hira_map)
    return expanded


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


def choose_preferred_detail_key(original_key, matched_key):
    """Prefer the matched key only when it is clearly more informative than the original token form."""
    if not matched_key:
        return original_key
    if not original_key:
        return matched_key

    original = str(original_key).strip()
    matched = str(matched_key).strip()
    if not matched:
        return original
    if matched == original:
        return matched

    original_kanji = len(re.findall(r'[\u3400-\u9fff々〆ヶ]', original))
    matched_kanji = len(re.findall(r'[\u3400-\u9fff々〆ヶ]', matched))

    if matched_kanji > original_kanji:
        return matched
    if matched_kanji > 0 and original_kanji == 0:
        return matched
    if matched_kanji > 0 and matched[0] in {'お', 'ご'} and len(matched) >= len(original):
        return matched
    if matched_kanji > 0 and any(p in matched for p in ('を', 'に', 'が', 'の')):
        return matched

    return original


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
            candidates.append(form[1:] + 'る')
            candidates.append(form + 'する')
            candidates.append(form[1:] + 'する')

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
    filtered_candidates = []
    for cand in candidates:
        # cand peut être une string ou un dict selon le pipeline, on gère les deux
        surface = cand['surface'] if isinstance(cand, dict) and 'surface' in cand else cand
        # Ignore les tokens parasites
        if surface in PARASITE_TOKENS:
            continue
        # Ignore les combinaisons mot+particule (ex: うちに)
        for p in PARTICULES:
            if surface.endswith(p) and len(surface) > len(p):
                root = surface[:-len(p)]
                if root in vocab_map:
                    break  # On ignore ce token
        else:
            filtered_candidates.append(cand)
    for cand in filtered_candidates:
        level = vocab_map.get(cand) if not isinstance(cand, dict) else vocab_map.get(cand.get('surface', ''))
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
    filtered_candidates = []
    for cand in candidates:
        surface = cand['surface'] if isinstance(cand, dict) and 'surface' in cand else cand
        if surface in PARASITE_TOKENS:
            continue
        for p in PARTICULES:
            if surface.endswith(p) and len(surface) > len(p):
                root = surface[:-len(p)]
                if root in pedagogical_map:
                    break
        else:
            filtered_candidates.append(cand)

    for cand in filtered_candidates:
        entry = pedagogical_map.get(cand) if not isinstance(cand, dict) else pedagogical_map.get(cand.get('surface', ''))
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


def pick_hiragana_vs_kanji_easier_level(surface, lookup_candidates, vocab_map, pedagogical_map=None):
    """For a token written entirely in hiragana, compare hiragana-only vs kanji-containing
    candidate groups and return the easier JLPT level.

    Rules:
    - Apply only when token surface is 100% hiragana.
    - Build two candidate groups:
      * hiragana-only candidates
      * candidates containing kanji
    - Compute best level in each group using strict vocab and (optionally) pedagogical map.
    - If both groups have a level, return the easier one (tie -> prefer hiragana).
    - If one group is missing, return (None, None) and let normal flow continue.
    """
    if not surface or not re.fullmatch(r'[ぁ-ゖー]+', str(surface)):
        return None, None
    if not lookup_candidates:
        return None, None

    hira_candidates = [
        cand for cand in lookup_candidates
        if cand and re.fullmatch(r'[ぁ-ゖー]+', str(cand))
    ]
    kanji_candidates = [
        cand for cand in lookup_candidates
        if cand and re.search(r'[\u3400-\u9fff々〆ヶ]', str(cand))
    ]

    if not hira_candidates or not kanji_candidates:
        return None, None

    def _best_level(candidates):
        best_level = None
        best_candidate = None

        strict_level, strict_candidate = pick_best_vocab_level(vocab_map, candidates)
        if strict_level:
            best_level = strict_level
            best_candidate = strict_candidate

        if pedagogical_map:
            peda_entry, peda_candidate = pick_best_pedagogical_entry(pedagogical_map, candidates)
            if peda_entry:
                peda_level = peda_entry[0]
                if (
                    best_level is None
                    or get_jlpt_level(peda_level) < get_jlpt_level(best_level)
                    or (
                        get_jlpt_level(peda_level) == get_jlpt_level(best_level)
                        and peda_candidate
                        and re.fullmatch(r'[ぁ-ゖー]+', str(peda_candidate))
                    )
                ):
                    best_level = peda_level
                    best_candidate = peda_candidate

        return best_level, best_candidate

    hira_level, hira_candidate = _best_level(hira_candidates)
    kanji_level, kanji_candidate = _best_level(kanji_candidates)

    if not hira_level or not kanji_level:
        return None, None

    if get_jlpt_level(hira_level) <= get_jlpt_level(kanji_level):
        return hira_level, hira_candidate
    return kanji_level, kanji_candidate


def get_raw_level_priority(raw_label):
    """Parse numeric priority from Bunpro raw labels like NA4, NA10, NE1.
    Higher number = more advanced in Bunpro curriculum (harder, further from JLPT)."""
    match = re.match(r'^N[AE](\d+)$', str(raw_label).strip().upper())
    return int(match.group(1)) if match else 0


def is_raw_level_harder(new_label, current_label):
    """Return True if new_label is harder than current_label (or current is None)."""
    if current_label is None:
        return True
    return get_raw_level_priority(new_label) > get_raw_level_priority(current_label)


def diff_details_str(peda_str, strict_str):
    """Return only the entries from peda_str that differ from strict_str.
    Entries identical in both are removed. Returns '-' if nothing differs."""
    if not peda_str or peda_str == '-':
        return '-'
    if not strict_str or strict_str == '-':
        return peda_str
    strict_dict = {}
    for item in str(strict_str).split(','):
        item = item.strip()
        if ':' in item:
            k, v = item.split(':', 1)
            strict_dict[k.strip()] = v.strip()
    diff_parts = []
    for item in str(peda_str).split(','):
        item = item.strip()
        if ':' in item:
            k, v = item.split(':', 1)
            k = k.strip(); v = v.strip()
            if strict_dict.get(k) != v:
                diff_parts.append(f"{k}:{v}")
    return ','.join(diff_parts) if diff_parts else '-'


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


def best_level_from_details(*details_candidates):
    """Infer best non-empty level/tag from one or more details strings.
    Priority: JLPT > PN > CO > KA > KA? > ?"""
    max_jlpt = 0
    has_pn = False
    has_co = False
    has_ka = False
    has_ka_unknown = False
    has_unknown = False

    for details_str in details_candidates:
        if not details_str or details_str == '-':
            continue
        for part in str(details_str).split(','):
            piece = part.strip()
            if not piece or ':' not in piece:
                continue
            _key, _sep, raw_value = piece.rpartition(':')
            value = str(raw_value).strip()
            if not value:
                continue
            normalized = value.split('@', 1)[0].strip().upper()
            jlpt_num = get_jlpt_level(normalized)
            if jlpt_num > 0:
                max_jlpt = max(max_jlpt, jlpt_num)
                continue
            if normalized == 'PN':
                has_pn = True
            elif normalized == 'CO':
                has_co = True
            elif normalized == 'KA':
                has_ka = True
            elif normalized == 'KA?':
                has_ka_unknown = True
            elif normalized == '?':
                has_unknown = True

    if max_jlpt > 0:
        return numeric_to_jlpt(max_jlpt)
    if has_pn:
        return 'PN'
    if has_co:
        return 'CO'
    if has_ka:
        return 'KA'
    if has_ka_unknown:
        return 'KA?'
    if has_unknown:
        return '?'
    return '?'


def apply_level_fallback(level, *details_candidates):
    """Keep explicit level when present, otherwise infer from details."""
    if level and str(level).strip() and str(level).strip() != '-':
        return level
    return best_level_from_details(*details_candidates)


def merge_sentence_level_with_grammar(level, grammar_level):
    """Keep the harder level between sentence vocab level and detected grammar level."""
    level_num = get_jlpt_level(level)
    grammar_num = get_jlpt_level(grammar_level)
    merged_num = max(level_num, grammar_num)
    if merged_num > 0:
        return numeric_to_jlpt(merged_num)
    return level


def extract_vocab_tags_from_details(details_str):
    """Extract normalized detail tags (N*, PN, CO, KA, KA?, UNC, ?)."""
    tags = []
    if not details_str or details_str == '-':
        return tags

    for part in str(details_str).split(','):
        piece = part.strip()
        if not piece or ':' not in piece:
            continue
        _key, _sep, raw_value = piece.rpartition(':')
        value = str(raw_value).strip()
        if not value:
            continue
        normalized = value.split('@', 1)[0].strip().upper()
        tags.append(normalized)
    return tags


def extract_jlpt_tags_from_details(*details_strs):
    """Extract JLPT-only tags from one or more detail strings."""
    tags = []
    for details_str in details_strs:
        for tag in extract_vocab_tags_from_details(details_str):
            if get_jlpt_level(tag) > 0:
                tags.append(tag)
    return tags


def harmonize_single_hard_outlier(level, *details_strs):
    """Downgrade a lone N1/N2 outlier when the rest of the sentence strongly supports an easier level.

    This is a decision-aid heuristic for obvious incoherence cases:
    a single hard vocab hit should not dominate when several independent
    vocab/grammar clues are all easier.
    """
    normalized = str(level).strip() if level is not None else ''
    current_num = get_jlpt_level(normalized)
    if current_num < 4:
        return normalized

    strong_grammar_markers = {
        'ないではいられ',
        'なにより',
        '何より',
        'かとおもったら',
        'かと思ったら',
        'わりに',
    }
    joined_details = ' '.join(str(part) for part in details_strs if part)
    if any(marker in joined_details for marker in strong_grammar_markers):
        return normalized

    jlpt_tags = extract_jlpt_tags_from_details(*details_strs)
    if not jlpt_tags:
        return normalized

    hard_tags = [tag for tag in jlpt_tags if get_jlpt_level(tag) >= 4]
    supporting_tags = [tag for tag in jlpt_tags if 0 < get_jlpt_level(tag) < 4]

    if len(hard_tags) != 1:
        return normalized
    if len(supporting_tags) < 4:
        return normalized

    hard_num = get_jlpt_level(hard_tags[0])
    supporting_num = max(get_jlpt_level(tag) for tag in supporting_tags)

    if supporting_num <= 0 or supporting_num >= hard_num:
        return normalized

    if hard_num - supporting_num < 2:
        return normalized

    return numeric_to_jlpt(supporting_num)


def adjust_nominal_only_level(level, details_str, grammar_level):
    """Convert PN/CO-only vocab summaries into JLPT levels using grammar/default rules."""
    tags = extract_vocab_tags_from_details(details_str)
    if not tags:
        return level

    grammar_norm = str(grammar_level).strip() if grammar_level is not None else ''
    has_grammar_level = get_jlpt_level(grammar_norm) > 0
    unique_tags = set(tags)

    # If only proper nouns were detected in vocab:
    # - use grammar level when available
    # - otherwise default to N5
    if unique_tags == {'PN'}:
        return grammar_norm if has_grammar_level else 'N5'

    # If detected vocab is only from nominal buckets (PN/CO/KA/KA?),
    # prefer grammar when available, else default to beginner level N5.
    if unique_tags.issubset({'PN', 'CO', 'KA', 'KA?'}):
        return grammar_norm if has_grammar_level else 'N5'

    return level


def backfill_level_from_sentence_context(level, grammar_level, kanji_level):
    """When vocab stays unknown, backfill with sentence-level JLPT clues."""
    normalized = str(level).strip() if level is not None else ''
    if get_jlpt_level(normalized) > 0:
        return normalized
    if normalized in {'PN', 'CO', 'KA', 'KA?', 'UNC'}:
        return normalized

    grammar_norm = str(grammar_level).strip() if grammar_level is not None else ''
    if get_jlpt_level(grammar_norm) > 0:
        return grammar_norm

    kanji_norm = str(kanji_level).strip() if kanji_level is not None else ''
    if get_jlpt_level(kanji_norm) > 0:
        return kanji_norm

    return '?' if normalized in {'', '-'} else normalized


def infer_sentence_special_vocab_level(sentence):
    """Detect very short non-lexical sentences and colloquial utterances for fallback tagging."""
    text = str(sentence).strip()
    if not text:
        return None

    compact = re.sub(r'[\s"“”「」『』()（）\[\]{}。、,，．・!！?？…]+', '', text)
    if not compact:
        return None

    if re.fullmatch(r'[A-Za-z0-9Ａ-Ｚａ-ｚ０-９]+', compact):
        return 'N5'

    if re.fullmatch(r'[0-9０-９一二三四五六七八九十百千万億兆/:+\-=×÷\.．,，]+', compact):
        return 'N5'

    # Beginner numeric expressions fully written in hiragana.
    number_hira_pattern = (
        r'(いち|に|さん|し|よん|ご|ろく|なな|しち|はち|きゅう|く|'
        r'じゅう|ひゃく|びゃく|ぴゃく|せん|ぜん|まん|おく|ちょう|'
        r'ぷん|ふん|ご|かん|にち|じ|ぶん)+'
    )
    if re.fullmatch(number_hira_pattern, compact):
        return 'N5'

    if compact in {'え', 'ね', 'おっ', 'みなかった'}:
        return 'N5'

    if compact in {'ちゅうううう', 'きたねー', 'はえー', 'よえー'}:
        return 'CO'

    if re.fullmatch(r'[ぁ-ゖー]{2,}', compact) and ('ー' in compact or re.search(r'(.)\1\1', compact)):
        return 'CO'

    return None


SMALL_KANA = frozenset('ぁぃぅぇぉゃゅょっ')


def is_tokenization_artifact(token):
    """Detect Janome artifacts like いつ -> い(いる)+つ and ignore them."""
    surface = token.surface if hasattr(token, 'surface') else ''
    base_form = token.base_form if hasattr(token, 'base_form') else surface
    pos = token.part_of_speech.split(',')
    major = pos[0] if len(pos) > 0 else ''

    if not surface:
        return False

    # Surface starting with a small kana is always a mis-segmentation artifact.
    # (e.g. ちゅうしん split as ちゅうし+ん, then ちゅうし as ちゅうし(ちゅうする)+ん → ゅうして residue)
    if surface[0] in SMALL_KANA:
        return True

    if major != '動詞':
        return False
    if not base_form:
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

    def _is_hiragana_pattern(text):
        return bool(text) and bool(re.fullmatch(r'[ぁ-ゖー]+', text))

    def _match_hiragana_with_boundaries(pattern_text, full_text):
        """Match pure-hiragana grammar patterns only at kana boundaries.
        Prevents false positives such as そこで detected inside あそこ+で.
        """
        if pattern_text not in full_text:
            return False
        for m in re.finditer(re.escape(pattern_text), full_text):
            start = m.start()
            end = m.end()
            prev_char = full_text[start - 1] if start > 0 else ''
            next_char = full_text[end] if end < len(full_text) else ''
            prev_is_hira = bool(prev_char) and bool(re.fullmatch(r'[ぁ-ゖー]', prev_char))
            next_is_hira = bool(next_char) and bool(re.fullmatch(r'[ぁ-ゖー]', next_char))
            if not prev_is_hira and not next_is_hira:
                return True
        return False

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
                if variant == 'ないほうがいい':
                    matched = variant in sentence
                    if matched:
                        key = (variant, jlpt_level)
                        if key not in seen:
                            matches.append(key)
                            seen.add(key)
                    continue
                if variant == 'ほうがいい':
                    matched = variant in sentence and 'ないほうがいい' not in sentence
                    if matched:
                        key = (variant, jlpt_level)
                        if key not in seen:
                            matches.append(key)
                            seen.add(key)
                    continue
                if _is_hiragana_pattern(variant):
                    matched = _match_hiragana_with_boundaries(variant, sentence)
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


def grammar_pattern_core(pattern):
    """Extract a comparable core from grammar patterns like Vがたい, べくもない, NはN."""
    if not pattern:
        return ''
    text = str(pattern).strip()
    text = re.sub(r'[A-Za-zＡ-Ｚａ-ｚ]', '', text)
    text = re.sub(r'[〜~＋+→・*／/\s「」『』（）()\[\]<>:：.,，]', '', text)
    return text


def should_skip_unknown_due_to_grammar(detail_key, grammar_matches, lookup_candidates=None, next_token=None):
    """Suppress unknown vocab fragments when a matched grammar pattern already explains them."""
    if not detail_key or not grammar_matches:
        return False

    terms = {str(detail_key).strip()}
    if lookup_candidates:
        terms.update(str(candidate).strip() for candidate in lookup_candidates if str(candidate).strip())
    if next_token is not None and hasattr(next_token, 'surface'):
        next_surface = str(next_token.surface).strip()
        if next_surface:
            terms.update({term + next_surface for term in list(terms) if term})

    comparable_terms = set()
    for term in terms:
        if not term or len(term) < 2:
            continue
        comparable_terms.add(term)
        for start in range(1, len(term) - 1):
            suffix = term[start:]
            if len(suffix) >= 2:
                comparable_terms.add(suffix)

    for pattern, _grammar_level in grammar_matches:
        core = grammar_pattern_core(pattern)
        if not core or len(core) < 2:
            continue
        for term in comparable_terms:
            if term == core or term in core or core in term:
                return True
    return False


def find_proper_noun_spans(tokens, proper_nouns, max_size=6):
    """Find exact multi-token proper noun spans like 鬼滅の刃 or 牧瀬紅莉栖."""
    if not tokens or not proper_nouns:
        return {}, set()

    matches = {}
    consumed = set()
    n = len(tokens)

    for size in range(max_size, 1, -1):
        for i in range(n - size + 1):
            if any(idx in consumed for idx in range(i, i + size)):
                continue
            group = tokens[i:i + size]
            blocked = False
            has_name_like_token = False
            for token in group:
                surface = token.surface if hasattr(token, 'surface') else ''
                pos = token.part_of_speech.split(',')
                major = pos[0] if len(pos) > 0 else ''
                if not surface or major == '記号':
                    blocked = True
                    break
                if is_proper_noun_token(token) or re.search(r'[\u3400-\u9fff々\u30A0-\u30FF\uFF66-\uFF9F]', surface):
                    has_name_like_token = True
            if blocked:
                continue

            surface_join = ''.join(token.surface for token in group)
            if has_name_like_token and surface_join in proper_nouns:
                indices = set(range(i, i + size))
                matches[i] = (surface_join, indices)
                consumed.update(indices)

    return matches, consumed

def find_compound_matches(tokens, vocab_map, pedagogical_map=None, raw_fallback_map=None, variants_map=None, hira_map=None):
    """
    Pre-pass: detect compound words split across consecutive tokens.
    Returns a dict: token_index -> (compound_word, strict_level, peda_entry)
    for the FIRST token of each matched compound. Consumed indices are also returned.
    Tries bigrammes and trigrammes (surface and base_form combinations).
    Also tries hiragana surface concatenations against hira_map (kanji reading map).
    """
    matches = {}   # first_index -> (word, strict_level, peda_entry)
    consumed = set()
    n = len(tokens)

    # Extra pass: try hiragana-surface concatenations that match hira_map
    # This handles cases like ちゅうしん → 中心 where Janome splits into ちゅうし + ん
    # Also handles cases like はいしゃく → 拝借 where token[0]=はいし, token[1]=ゃく...
    if hira_map:
        for size in (5, 4, 3, 2):
            for i in range(n - size + 1):
                if i in consumed:
                    continue
                group = tokens[i:i + size]
                # Only consider groups where all tokens have hiragana surfaces
                all_hira = all(
                    bool(re.fullmatch(r'[ぁ-ゖー]+', t.surface if hasattr(t, 'surface') else ''))
                    for t in group
                )
                if not all_hira:
                    continue
                # Conservative mode: run this hira_map group pass only for likely
                # tokenization artifacts (small kana boundary or standalone ー token).
                artifact_in_group = any(
                    ((t.surface if hasattr(t, 'surface') else '')[:1] in SMALL_KANA)
                    or ((t.surface if hasattr(t, 'surface') else '') == 'ー')
                    for t in group
                )
                if not artifact_in_group:
                    continue
                surfaces = ''.join(t.surface for t in group)
                # For groups containing long artifact tokens (starting with small kana),
                # also try using only the prefix of that artifact token that forms a known word
                # Try longer prefixes first (greedy match = prefer longer words)
                candidate_keys = [surfaces]
                for j, tok in enumerate(group):
                    tok_surf = tok.surface if hasattr(tok, 'surface') else ''
                    if tok_surf and tok_surf[0] in SMALL_KANA and j > 0:
                        # Case A: surfaces of tokens[i..i+j-1] + prefix of tok_surf (longest first)
                        prefix_base = ''.join(t.surface for t in group[:j])
                        for end in range(min(len(tok_surf), 8), 0, -1):
                            candidate_keys.append(prefix_base + tok_surf[:end])
                        # Case B: suffix of token[j-1] + prefix of tok_surf
                        # Handles: e.g. 'らち'+'ゅうこく' → try 'ち'+'ゅうこく'='ちゅうこく'
                        prev_surf = group[j - 1].surface if hasattr(group[j - 1], 'surface') else ''
                        for suf_start in range(1, len(prev_surf)):
                            suffix_of_prev = prev_surf[suf_start:]
                            for end in range(min(len(tok_surf), 8), 0, -1):
                                candidate_keys.append(suffix_of_prev + tok_surf[:end])
                # Deduplicate preserving order
                seen_k = set()
                candidate_keys = [k for k in candidate_keys if k not in seen_k and not seen_k.add(k)]
                found_key = None
                for cand in candidate_keys:
                    if cand in hira_map:
                        found_key = cand
                        break
                if not found_key:
                    continue
                # Guard: reject groups whose tokens are ALL grammatical (particles, auxiliaries,
                # dependent verbs).  This prevents し+て+い being matched as 指定 (してい).
                # At least one token must be a content word (名詞自立, 形容詞自立, 動詞自立 with
                # a non-helper base, etc.) for the group to be a real lexical word.
                if _word_tokens_are_grammatical_only(group):
                    continue
                kanji_form = hira_map[found_key]
                strict_level, _ = pick_best_vocab_level(vocab_map, [kanji_form, found_key])
                peda_entry, _ = pick_best_pedagogical_entry(pedagogical_map, [kanji_form, found_key]) if pedagogical_map else (None, None)
                raw_entry, _ = pick_first_raw_fallback_entry(raw_fallback_map, [kanji_form, found_key]) if raw_fallback_map else (None, None)
                if strict_level or peda_entry or raw_entry:
                    matched_word = kanji_form
                    matches[i] = (matched_word, strict_level, peda_entry, raw_entry, set(range(i, i + size)))
                    consumed.update(range(i, i + size))

    # Exact phrase pass: allow particles/auxiliaries when the joined surface/base
    # matches a known expression (e.g. 無下に, 駄々をこねる, 手が離せない, 逆鱗に触れる).
    for size in (5, 4, 3, 2):
        for i in range(n - size + 1):
            if i in consumed:
                continue
            group = tokens[i:i + size]

            if size == 2:
                first_pos = group[0].part_of_speech.split(',') if hasattr(group[0], 'part_of_speech') else []
                second_pos = group[1].part_of_speech.split(',') if hasattr(group[1], 'part_of_speech') else []
                first_major = first_pos[0] if len(first_pos) > 0 else ''
                second_major = second_pos[0] if len(second_pos) > 0 else ''
                second_surface = group[1].surface if hasattr(group[1], 'surface') else ''
                if first_major == '名詞' and second_major == '助詞' and second_surface == 'の':
                    continue

            # Conservative guard for all-hiragana groups containing function words.
            # These groups are a major source of false positives such as:
            #   は + いい  -> はいい -> 廃位 (N1)
            #   まし + た   -> ました -> 真下 (N1)
            # Keep only explicitly declared pedagogical expressions in this branch.
            all_hira_group = all(
                bool(re.fullmatch(r'[ぁ-ゖー]+', (t.surface if hasattr(t, 'surface') else '')))
                for t in group
            )
            if all_hira_group:
                has_function_token = False
                for t in group:
                    pos = t.part_of_speech.split(',')
                    major = pos[0] if len(pos) > 0 else ''
                    if major in {'助詞', '助動詞', '記号', '接続詞', '接頭詞'}:
                        has_function_token = True
                        break

                has_artifact_signal = any(
                    ((t.surface if hasattr(t, 'surface') else '')[:1] in SMALL_KANA)
                    or ((t.surface if hasattr(t, 'surface') else '') == 'ー')
                    for t in group
                )

                if has_function_token and not has_artifact_signal:
                    joined_surface = ''.join(t.surface for t in group)
                    allowed_declared_expression = (
                        bool(pedagogical_map)
                        and joined_surface in pedagogical_map
                        and re.fullmatch(r'[ぁ-ゖー]+', joined_surface)
                    )
                    if not allowed_declared_expression:
                        continue

            surfaces = ''.join(t.surface for t in group)
            bases = ''.join(
                (t.base_form if hasattr(t, 'base_form') and t.base_form and t.base_form != '*' else t.surface)
                for t in group
            )
            last = group[-1]
            last_base = last.base_form if hasattr(last, 'base_form') and last.base_form and last.base_form != '*' else last.surface

            candidates = [surfaces, bases]
            if size >= 2:
                candidates.append(''.join(t.surface for t in group[:-1]) + last_base)

            # Conservative mode: disable aggressive "suffix of previous token" recombination.
            # This heuristic creates many false positives (e.g. 日本+の -> 本の, etc.).
            # We prefer under-detection over over-detection for JLPT estimation stability.

            candidates = expand_compound_lookup_candidates(candidates, variants_map=None, hira_map=hira_map)
            candidates = filter_lookup_candidates_by_surface(surfaces, candidates)

            strict_level, strict_word = pick_best_vocab_level(vocab_map, candidates)
            peda_entry, peda_word = (None, None)
            if pedagogical_map:
                peda_entry, peda_word = pick_best_pedagogical_entry(pedagogical_map, candidates)
            raw_entry, raw_word = (None, None)
            if raw_fallback_map:
                raw_entry, raw_word = pick_first_raw_fallback_entry(raw_fallback_map, candidates)

            matched_word = strict_word or peda_word or raw_word
            is_hiragana_expression = (
                matched_word
                and pedagogical_map
                and str(matched_word) in pedagogical_map
                and re.fullmatch(r'[ぁ-ゖー]+', str(matched_word))
            )
            if matched_word and len(str(matched_word)) >= 2 and (
                re.search(r'[\u3400-\u9fff々〆ヶ]', str(matched_word)) or is_hiragana_expression
            ):
                matches[i] = (matched_word, strict_level, peda_entry, raw_entry, set(range(i, i + size)))
                consumed.update(range(i, i + size))

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

            candidates = expand_compound_lookup_candidates(candidates, variants_map=variants_map, hira_map=hira_map)

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


def analyze_vocabulary(sentence, vocab_map, grammar_matches=None, proper_nouns=None, common_words=None, supplemental_map=None, raw_fallback_map=None, variants_map=None, bunpro_unclassified_words=None, bunpro_all_words=None, hira_map=None):
    """
    Analyze vocabulary in sentence and return highest JLPT level.
    Uses janome tokenizer to handle conjugated verbs and complex words.
    """
    max_level = 0
    raw_max_label = None
    details = OrderedDict()
    
    try:
        tokens = list(tokenizer.tokenize(sentence))
        proper_noun_spans, consumed_by_proper_noun = find_proper_noun_spans(tokens, proper_nouns)
        compound_matches, consumed_by_compound = find_compound_matches(tokens, vocab_map, supplemental_map, raw_fallback_map, variants_map=variants_map, hira_map=hira_map)
        consumed_by_name_span = set()
        has_katakana_proper_noun = any(
            is_katakana_word(tok.surface if hasattr(tok, 'surface') else '') and is_proper_noun_token(tok)
            for tok in tokens
        )

        for idx, token in enumerate(tokens):
            if idx in consumed_by_name_span:
                continue
            if idx in proper_noun_spans:
                word, span = proper_noun_spans[idx]
                details[word] = 'PN'
                consumed_by_name_span.update(span)
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
                if supplemental_map and supplemental_entry:
                    supp_level = supplemental_entry[0]
                    if (not effective_level) or (get_jlpt_level(supp_level) < get_jlpt_level(effective_level)):
                        effective_level = supp_level

                if effective_level:
                    if should_skip_vocab_due_to_grammar(word, effective_level, grammar_matches):
                        continue
                    level = get_jlpt_level(effective_level)
                    max_level = max(max_level, level)
                    details[word] = effective_level
                elif raw_entry:
                    raw_level, raw_source = raw_entry
                    details[word] = f"{raw_level}@{raw_source}"
                    if is_raw_level_harder(raw_level, raw_max_label):
                        raw_max_label = raw_level
                else:
                    details[word] = unknown_vocab_tag(
                        token,
                        detail_key=word,
                        proper_nouns=proper_nouns,
                        common_words=common_words,
                        prev_token=prev_token,
                        next_token=next_token,
                        bunpro_unclassified_words=bunpro_unclassified_words,
                        bunpro_all_words=bunpro_all_words,
                    )
                continue

            if idx in consumed_by_compound:
                continue
            if idx in consumed_by_proper_noun:
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
                pn_candidates = candidate_forms_for_lookup(base_form, surface, reading=reading)
                pn_candidates = list(dict.fromkeys(pn_candidates))
                pn_candidates = expand_candidates_with_variants(pn_candidates, variants_map)
                pn_candidates = enrich_candidates_with_hira_map(pn_candidates, hira_map)
                pn_strict_level, _ = pick_best_vocab_level(vocab_map, pn_candidates)
                pn_supp_entry, _ = pick_best_pedagogical_entry(supplemental_map, pn_candidates) if supplemental_map else (None, None)
                if not pn_strict_level and not pn_supp_entry:
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
            lookup_candidates.extend(get_small_kana_prefix_candidates(tokens, idx, hira_map))
            lookup_candidates.extend(get_prev_token_join_candidates(tokens, idx))
            lookup_candidates.extend(get_prev_kana_sequence_join_candidates(tokens, idx))
            honorific_residue_candidates = get_prev_honorific_residue_candidates(tokens, idx)
            lookup_candidates.extend(honorific_residue_candidates)
            lookup_candidates = list(dict.fromkeys(lookup_candidates))
            lookup_candidates = expand_candidates_with_variants(lookup_candidates, variants_map)
            lookup_candidates = enrich_candidates_with_hira_map(lookup_candidates, hira_map)
            lookup_candidates = filter_lookup_candidates_by_surface(surface, lookup_candidates)
            found_level, found_candidate = pick_best_vocab_level(vocab_map, lookup_candidates)

            supplemental_entry = None
            supplemental_candidate = None

            if honorific_residue_candidates:
                honorific_strict_level, honorific_strict_candidate = pick_best_vocab_level(vocab_map, honorific_residue_candidates)
                if honorific_strict_level:
                    found_level = honorific_strict_level
                    found_candidate = honorific_strict_candidate

            if not found_level and supplemental_map:
                supplemental_entry, supplemental_candidate = pick_best_pedagogical_entry(supplemental_map, lookup_candidates)
                if supplemental_entry:
                    found_level = supplemental_entry[0]
            if honorific_residue_candidates and supplemental_map:
                honorific_supp_entry, honorific_supp_candidate = pick_best_pedagogical_entry(supplemental_map, honorific_residue_candidates)
                if honorific_supp_entry:
                    supplemental_entry = honorific_supp_entry
                    supplemental_candidate = honorific_supp_candidate
                    found_level = honorific_supp_entry[0]
                    found_candidate = None

            # For pure-hiragana tokens, compare hiragana form vs kanji-mapped form
            # and keep the easier level to avoid overestimating difficulty.
            hira_preferred_level, hira_preferred_candidate = pick_hiragana_vs_kanji_easier_level(
                surface,
                lookup_candidates,
                vocab_map,
                pedagogical_map=supplemental_map,
            )
            if hira_preferred_level:
                if not found_level or get_jlpt_level(hira_preferred_level) < get_jlpt_level(found_level):
                    found_level = hira_preferred_level
                    found_candidate = hira_preferred_candidate
                elif (
                    get_jlpt_level(hira_preferred_level) == get_jlpt_level(found_level)
                    and hira_preferred_candidate
                    and re.fullmatch(r'[ぁ-ゖー]+', str(hira_preferred_candidate))
                ):
                    found_candidate = hira_preferred_candidate

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
                raw_entry, raw_candidate = pick_first_raw_fallback_entry(raw_fallback_map, lookup_candidates)
            else:
                raw_candidate = None

            if surface and re.fullmatch(r'[ぁ-ゖー]+', str(surface)):
                preferred_hira_candidate = None
                if supplemental_candidate and re.fullmatch(r'[ぁ-ゖー]+', str(supplemental_candidate)):
                    preferred_hira_candidate = supplemental_candidate
                elif found_candidate and re.fullmatch(r'[ぁ-ゖー]+', str(found_candidate)):
                    preferred_hira_candidate = found_candidate
                elif raw_candidate and re.fullmatch(r'[ぁ-ゖー]+', str(raw_candidate)):
                    preferred_hira_candidate = raw_candidate

                if preferred_hira_candidate:
                    detail_key = preferred_hira_candidate
                elif found_candidate:
                    detail_key = choose_preferred_detail_key(detail_key, found_candidate)
                elif supplemental_candidate:
                    detail_key = choose_preferred_detail_key(detail_key, supplemental_candidate)
                elif raw_candidate:
                    detail_key = choose_preferred_detail_key(detail_key, raw_candidate)
            else:
                if found_candidate:
                    detail_key = choose_preferred_detail_key(detail_key, found_candidate)
                elif supplemental_candidate:
                    detail_key = choose_preferred_detail_key(detail_key, supplemental_candidate)
                elif raw_candidate:
                    detail_key = choose_preferred_detail_key(detail_key, raw_candidate)

            if found_level:
                if should_skip_vocab_due_to_grammar(detail_key, found_level, grammar_matches, lookup_candidates):
                    continue
                level = get_jlpt_level(found_level)
                max_level = max(max_level, level)
                details[detail_key] = found_level
            elif raw_entry:
                raw_level, raw_source = raw_entry
                details[detail_key] = f"{raw_level}@{raw_source}"
                if is_raw_level_harder(raw_level, raw_max_label):
                    raw_max_label = raw_level
            else:
                if should_skip_unknown_due_to_grammar(detail_key, grammar_matches, lookup_candidates=lookup_candidates, next_token=next_token):
                    continue
                details[detail_key] = unknown_vocab_tag(
                    token,
                    detail_key=detail_key,
                    proper_nouns=proper_nouns,
                    common_words=common_words,
                    candidates=lookup_candidates,
                    prev_token=prev_token,
                    next_token=next_token,
                    bunpro_unclassified_words=bunpro_unclassified_words,
                    bunpro_all_words=bunpro_all_words,
                )
    except Exception as e:
        print(f"Error analyzing vocabulary in '{sentence}': {e}")

    details_str = ','.join([f"{k}:{v}" for k, v in details.items()]) if details else '-'
    if raw_max_label is not None:
        return raw_max_label, details_str
    return numeric_to_jlpt(max_level), details_str

def analyze_vocab_pedagogical(sentence, vocab_map, pedagogical_map, ignore_katakana=False, grammar_matches=None, proper_nouns=None, common_words=None, raw_fallback_map=None, variants_map=None, bunpro_unclassified_words=None, bunpro_all_words=None, hira_map=None):
    """
    Same as analyze_vocabulary but overrides levels from pedagogical_map.
    Returns (level, details_str) only if the result differs from the strict analysis.
    details format: 'word:N5@minna'
    Returns ('-', '-') if identical to strict.
    """
    max_strict = 0
    max_peda = 0
    raw_max_label = None
    details = OrderedDict()
    used_raw_fallback = False

    try:
        tokens = list(tokenizer.tokenize(sentence))
        proper_noun_spans, consumed_by_proper_noun = find_proper_noun_spans(tokens, proper_nouns)
        compound_matches, consumed_by_compound = find_compound_matches(tokens, vocab_map, pedagogical_map, raw_fallback_map, variants_map=variants_map, hira_map=hira_map)
        consumed_by_name_span = set()
        has_katakana_proper_noun = any(
            is_katakana_word(tok.surface if hasattr(tok, 'surface') else '') and is_proper_noun_token(tok)
            for tok in tokens
        )

        for idx, token in enumerate(tokens):
            if idx in consumed_by_name_span:
                continue
            if idx in proper_noun_spans:
                word, span = proper_noun_spans[idx]
                details[word] = 'PN'
                consumed_by_name_span.update(span)
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
                    if is_raw_level_harder(raw_level, raw_max_label):
                        raw_max_label = raw_level
                else:
                    details[detail_key] = unknown_vocab_tag(
                        token,
                        detail_key=detail_key,
                        proper_nouns=proper_nouns,
                        common_words=common_words,
                        prev_token=prev_token,
                        next_token=next_token,
                        bunpro_unclassified_words=bunpro_unclassified_words,
                        bunpro_all_words=bunpro_all_words,
                    )
                continue

            if idx in consumed_by_compound:
                continue
            if idx in consumed_by_proper_noun:
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
                pn_candidates = candidate_forms_for_lookup(base_form, surface, reading=reading)
                pn_candidates = list(dict.fromkeys(pn_candidates))
                pn_candidates = expand_candidates_with_variants(pn_candidates, variants_map)
                pn_candidates = enrich_candidates_with_hira_map(pn_candidates, hira_map)
                pn_strict_level, _ = pick_best_vocab_level(vocab_map, pn_candidates)
                pn_peda_entry, _ = pick_best_pedagogical_entry(pedagogical_map, pn_candidates) if pedagogical_map else (None, None)
                if not pn_strict_level and not pn_peda_entry:
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
            lookup_candidates.extend(get_small_kana_prefix_candidates(tokens, idx, hira_map))
            lookup_candidates.extend(get_prev_token_join_candidates(tokens, idx))
            lookup_candidates.extend(get_prev_kana_sequence_join_candidates(tokens, idx))
            honorific_residue_candidates = get_prev_honorific_residue_candidates(tokens, idx)
            lookup_candidates.extend(honorific_residue_candidates)
            lookup_candidates = list(dict.fromkeys(lookup_candidates))
            lookup_candidates = expand_candidates_with_variants(lookup_candidates, variants_map)
            lookup_candidates = enrich_candidates_with_hira_map(lookup_candidates, hira_map)
            lookup_candidates = filter_lookup_candidates_by_surface(surface, lookup_candidates)
            strict_level, strict_candidate = pick_best_vocab_level(vocab_map, lookup_candidates)

            if honorific_residue_candidates:
                honorific_strict_level, honorific_strict_candidate = pick_best_vocab_level(vocab_map, honorific_residue_candidates)
                if honorific_strict_level:
                    strict_level = honorific_strict_level
                    strict_candidate = honorific_strict_candidate

            detail_key = base_form if base_form and base_form != '*' else surface
            if not detail_key:
                continue
            if not is_meaningful_token_text(detail_key):
                continue

            # Check pedagogical override (for base_form or surface)
            peda_entry, peda_candidate = pick_best_pedagogical_entry(pedagogical_map, lookup_candidates)
            if honorific_residue_candidates:
                honorific_peda_entry, honorific_peda_candidate = pick_best_pedagogical_entry(pedagogical_map, honorific_residue_candidates)
                if honorific_peda_entry:
                    peda_entry = honorific_peda_entry
                    peda_candidate = honorific_peda_candidate
                    strict_level = None
                    strict_candidate = None

            # For pure-hiragana tokens, compare hiragana form vs kanji-mapped form
            # and keep the easier level to avoid overestimating difficulty.
            hira_preferred_level, hira_preferred_candidate = pick_hiragana_vs_kanji_easier_level(
                surface,
                lookup_candidates,
                vocab_map,
                pedagogical_map=pedagogical_map,
            )
            if hira_preferred_level:
                if not strict_level or get_jlpt_level(hira_preferred_level) < get_jlpt_level(strict_level):
                    strict_level = hira_preferred_level
                    strict_candidate = hira_preferred_candidate
                elif (
                    get_jlpt_level(hira_preferred_level) == get_jlpt_level(strict_level)
                    and hira_preferred_candidate
                    and re.fullmatch(r'[ぁ-ゖー]+', str(hira_preferred_candidate))
                ):
                    strict_candidate = hira_preferred_candidate
            raw_entry = None
            if not strict_level and not peda_entry and raw_fallback_map:
                raw_entry, raw_candidate = pick_first_raw_fallback_entry(raw_fallback_map, lookup_candidates)
            else:
                raw_candidate = None

            if surface and re.fullmatch(r'[ぁ-ゖー]+', str(surface)):
                preferred_hira_candidate = None
                if peda_candidate and re.fullmatch(r'[ぁ-ゖー]+', str(peda_candidate)):
                    preferred_hira_candidate = peda_candidate
                elif strict_candidate and re.fullmatch(r'[ぁ-ゖー]+', str(strict_candidate)):
                    preferred_hira_candidate = strict_candidate
                elif raw_candidate and re.fullmatch(r'[ぁ-ゖー]+', str(raw_candidate)):
                    preferred_hira_candidate = raw_candidate

                if preferred_hira_candidate:
                    detail_key = preferred_hira_candidate
                elif strict_candidate:
                    detail_key = choose_preferred_detail_key(detail_key, strict_candidate)
                elif peda_candidate:
                    detail_key = choose_preferred_detail_key(detail_key, peda_candidate)
                elif raw_candidate:
                    detail_key = choose_preferred_detail_key(detail_key, raw_candidate)
            else:
                if strict_candidate:
                    detail_key = choose_preferred_detail_key(detail_key, strict_candidate)
                elif peda_candidate:
                    detail_key = choose_preferred_detail_key(detail_key, peda_candidate)
                elif raw_candidate:
                    detail_key = choose_preferred_detail_key(detail_key, raw_candidate)

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
                        if is_raw_level_harder(raw_level, raw_max_label):
                            raw_max_label = raw_level
                    else:
                        if should_skip_unknown_due_to_grammar(detail_key, grammar_matches, lookup_candidates=lookup_candidates, next_token=next_token):
                            continue
                        details[detail_key] = unknown_vocab_tag(
                            token,
                            detail_key=detail_key,
                            proper_nouns=proper_nouns,
                            common_words=common_words,
                            candidates=lookup_candidates,
                            prev_token=prev_token,
                            next_token=next_token,
                            bunpro_unclassified_words=bunpro_unclassified_words,
                            bunpro_all_words=bunpro_all_words,
                        )
    except Exception as e:
        print(f"Error in pedagogical vocab analysis for '{sentence}': {e}")

    details_str = ','.join([f"{k}:{v}" for k, v in details.items()]) if details else '-'

    if raw_max_label is not None:
        return raw_max_label, details_str

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
    # Bunpro API sets used for last-resort katakana tagging.
    bunpro_api_all_words = set()
    bunpro_api_unclassified_words = set()
    if bunpro_api_file and os.path.exists(bunpro_api_file):
        try:
            _bp_df = pd.read_csv(bunpro_api_file, sep='|', dtype=str).fillna('')
            if 'word' in _bp_df.columns:
                for _, row in _bp_df.iterrows():
                    word = str(row.get('word', '')).strip()
                    if not word:
                        continue
                    bunpro_api_all_words.add(word)
                    raw_level = str(row.get('jlpt_level_raw', '')).strip().upper()
                    if raw_level == 'NUNCLASSIFIED':
                        bunpro_api_unclassified_words.add(word)
        except Exception:
            pass

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
    print(f"Loaded Bunpro API unclassified entries: {len(bunpro_api_unclassified_words)}")
    print(f"Loaded Open-Anki-JLPT entries: {len(open_anki_fallback)}")
    print(f"Loaded proper nouns: {len(proper_nouns)}")
    print(f"Loaded common words (CO): {len(common_words)}")
    print(f"Loaded word variants: {len(variants_map)}")

    grammar_patterns = load_grammar_patterns(grammar_file, fallback_file='data/grammar_patterns.csv')

    print(f"Loaded grammar patterns: {len(grammar_patterns)}")

    # Build hiragana→kanji normalization map from all vocabulary sources
    hira_to_kanji = build_hiragana_to_kanji_map(vocab_map, supplemental_map=pedagogical_map)
    print(f"Built hiragana-kanji map: {len(hira_to_kanji)} entries")
    
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
    no_katakana_details = []
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
            bunpro_unclassified_words=bunpro_api_unclassified_words,
            bunpro_all_words=bunpro_api_all_words,
            hira_map=hira_to_kanji,
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
            bunpro_unclassified_words=bunpro_api_unclassified_words,
            bunpro_all_words=bunpro_api_all_words,
            hira_map=hira_to_kanji,
        )
        # Déduplication : ne garder dans peda_detail que ce qui diffère de vocab_detail
        if peda_detail != '-':
            peda_detail = diff_details_str(peda_detail, vocab_detail)
        no_kata_level, no_kata_detail = analyze_vocab_pedagogical(
            analysis_sentence,
            vocab_map,
            pedagogical_map,
            ignore_katakana=True,
            grammar_matches=grammar_matches,
            proper_nouns=proper_nouns,
            common_words=common_words,
            raw_fallback_map=bunpro_api_raw_fallback,
            variants_map=variants_map,
            bunpro_unclassified_words=bunpro_api_unclassified_words,
            bunpro_all_words=bunpro_api_all_words,
            hira_map=hira_to_kanji,
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

        vocab_level = apply_level_fallback(vocab_level, vocab_detail)
        peda_level = apply_level_fallback(peda_level, peda_detail, vocab_detail)
        final_no_kata_level = apply_level_fallback(final_no_kata_level, no_kata_detail, peda_detail, vocab_detail)

        peda_reference_detail = peda_detail if peda_detail and peda_detail != '-' else vocab_detail
        no_kata_reference_detail = no_kata_detail if no_kata_detail and no_kata_detail != '-' else peda_reference_detail

        vocab_level = adjust_nominal_only_level(vocab_level, vocab_detail, grammar_level)
        peda_level = adjust_nominal_only_level(peda_level, peda_reference_detail, grammar_level)
        final_no_kata_level = adjust_nominal_only_level(final_no_kata_level, no_kata_reference_detail, grammar_level)

        vocab_level = backfill_level_from_sentence_context(vocab_level, grammar_level, kanji_level)
        peda_level = backfill_level_from_sentence_context(peda_level, grammar_level, kanji_level)
        final_no_kata_level = backfill_level_from_sentence_context(final_no_kata_level, grammar_level, kanji_level)
        final_no_kata_level = merge_sentence_level_with_grammar(final_no_kata_level, grammar_level)

        final_no_kata_level = harmonize_single_hard_outlier(
            final_no_kata_level,
            no_kata_reference_detail,
            grammar_detail,
        )

        sentence_special_level = infer_sentence_special_vocab_level(analysis_sentence)
        if sentence_special_level:
            if vocab_level == '?':
                vocab_level = sentence_special_level
            if peda_level == '?':
                peda_level = sentence_special_level
            if final_no_kata_level == '?':
                final_no_kata_level = sentence_special_level

        vocab_levels.append(vocab_level)
        vocab_details.append(vocab_detail)
        no_katakana_levels.append(final_no_kata_level)
        vocab_peda_levels.append(peda_level)
        vocab_peda_details.append(peda_detail)
        no_katakana_details.append(no_kata_detail)
        kanji_levels.append(kanji_level)
        kanji_details.append(kanji_detail)
        grammar_levels.append(grammar_level)
        grammar_details.append(grammar_detail)
    
    # Create output dataframe from canonical input columns only
    output_df = df[['id', 'sentence']].copy()
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
    try:
        print(result.head(10).to_string())
    except UnicodeEncodeError:
        print(result.head(10).to_string().encode('ascii', errors='replace').decode('ascii'))
