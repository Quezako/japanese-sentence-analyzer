#!/usr/bin/env python3
import argparse
import csv
import json
import re
from pathlib import Path

HEADER_RE = re.compile(r'^(?P<unknown>[^;]+):\?;(?P<sentence>.*);(?P<id>\d+)\s*$')
GRAMMAR_MARKER_RE = re.compile(r'^\s*[*-]?\s*(grammar|grammaire)\s*:\s*$', re.IGNORECASE)
VOCAB_MARKER_RE = re.compile(r'^\s*[*-]?\s*(vocab|vocabulaire)\s*:\s*$', re.IGNORECASE)
LEVEL_RE = re.compile(r'\bN\s*([1-5])\b', re.IGNORECASE)


def clean_text(text: str) -> str:
    value = text.strip()
    value = re.sub(r'<[^>]+>', '', value)
    value = value.replace('**', '').replace('*', '').strip()
    value = value.strip('"“”「」[]')
    value = re.sub(r'\s+', ' ', value)
    return value.strip()


def normalize_head(head: str) -> str:
    head = clean_text(head)
    head = re.sub(r'（[^）]*）', '', head)
    head = re.sub(r'\([^)]*\)', '', head)
    head = re.sub(r'\s+', ' ', head).strip()
    return head


def extract_level(line: str):
    m = LEVEL_RE.search(line)
    if not m:
        return None
    return f"N{m.group(1)}"


def looks_grammar(line: str, head: str) -> bool:
    raw = f"{head} {line}".lower()
    if any(k in raw for k in [
        'conditionnel', 'expressif', 'volitif', 'honorifique', 'particule',
        'forme', 'grammaire', 'auxiliaire'
    ]):
        return True

    if re.search(r'\b(v|n|adj)\S*', head, re.IGNORECASE):
        return True

    if any(x in head for x in ['〜', '～', '/', '＋']):
        return True

    if ' ' in head:
        jp_chunks = re.findall(r'[\u3040-\u30ff\u4e00-\u9fff]+', head)
        if len(jp_chunks) >= 2:
            return True

    return False


def is_strong_grammar_head(head: str) -> bool:
    h = head.strip()
    if re.match(r'^(V|N|Adj|A)[^\s]*', h, re.IGNORECASE):
        return True
    if any(x in h for x in ['〜', '～']):
        return True
    if '連用形' in h or '辞書' in h:
        return True
    return False


def split_vocab_head(head: str):
    if '/' not in head:
        return [head]
    parts = [clean_text(p) for p in head.split('/')]
    parts = [p for p in parts if p]
    if len(parts) <= 1:
        return [head]
    # Keep grammar-like slash patterns intact (e.g. Vても / Vなくても)
    if any(re.search(r'\b(V|N|Adj)\b|〜|～', p, re.IGNORECASE) for p in parts):
        return [head]
    return parts


def parse_entry_line(line: str):
    line = line.strip()
    if not line:
        return None, None

    line = re.sub(r'^\s*[*-]\s*', '', line).strip()

    if '→' in line:
        head = line.split('→', 1)[0]
    elif '->' in line:
        head = line.split('->', 1)[0]
    elif '：' in line:
        head = line.split('：', 1)[0]
    elif ':' in line:
        head = line.split(':', 1)[0]
    else:
        return None, extract_level(line)

    head = normalize_head(head)
    level = extract_level(line)
    if not head:
        return None, level
    return head, level


def strip_inline_marker(line: str):
    line2 = line.strip()
    m = re.match(r'^\s*[*-]?\s*(grammar|grammaire)\s*:\s*(.+)$', line2, re.IGNORECASE)
    if m:
        return 'grammar', m.group(2).strip()
    m = re.match(r'^\s*[*-]?\s*(vocab|vocabulaire)\s*:\s*(.+)$', line2, re.IGNORECASE)
    if m:
        return 'vocab', m.group(2).strip()
    return None, line


def parse_blocks(lines):
    headers = []
    for i, line in enumerate(lines, start=1):
        if HEADER_RE.match(line):
            headers.append(i)

    blocks = []
    for idx, start in enumerate(headers):
        end = headers[idx + 1] - 1 if idx + 1 < len(headers) else len(lines)
        m = HEADER_RE.match(lines[start - 1])
        block_lines = lines[start - 1:end]
        blocks.append({
            'start_line': start,
            'end_line': end,
            'unknown': m.group('unknown').strip(),
            'sentence': m.group('sentence').strip(),
            'id': m.group('id').strip(),
            'body_lines': block_lines[1:],
        })

    return blocks


def extract_candidates(blocks):
    grammar = []
    vocab = []

    diagnostics = {
        'blocks_total': len(blocks),
        'blocks_with_grammar_marker': 0,
        'blocks_with_vocab_marker': 0,
        'blocks_without_any_marker': 0,
        'blocks_with_no_extracted_entries': 0,
        'malformed_lines': [],
    }

    for block in blocks:
        state = None
        block_has_grammar_marker = False
        block_has_vocab_marker = False
        extracted_in_block = 0

        for raw in block['body_lines']:
            line = raw.strip()
            if not line:
                continue

            inline_state, line = strip_inline_marker(line)
            if inline_state:
                state = inline_state

            if GRAMMAR_MARKER_RE.match(line):
                state = 'grammar'
                block_has_grammar_marker = True
                continue

            if VOCAB_MARKER_RE.match(line):
                state = 'vocab'
                block_has_vocab_marker = True
                continue

            entry, level = parse_entry_line(line)
            if not entry:
                diagnostics['malformed_lines'].append({
                    'id': block['id'],
                    'line': line,
                })
                continue

            inferred_type = state
            if inferred_type is None:
                inferred_type = 'grammar' if looks_grammar(line, entry) else 'vocab'
            else:
                # Recover from section mistakes only with strong syntax hints
                if inferred_type == 'vocab' and is_strong_grammar_head(entry):
                    inferred_type = 'grammar'

            if inferred_type == 'vocab':
                entries = split_vocab_head(entry)
            else:
                entries = [entry]

            for item in entries:
                record = {
                    'id': block['id'],
                    'unknown': block['unknown'],
                    'entry': item,
                    'level': level,
                    'source_line': line,
                    'block_start_line': block['start_line'],
                }
                if inferred_type == 'grammar':
                    grammar.append(record)
                else:
                    vocab.append(record)
                extracted_in_block += 1

        if block_has_grammar_marker:
            diagnostics['blocks_with_grammar_marker'] += 1
        if block_has_vocab_marker:
            diagnostics['blocks_with_vocab_marker'] += 1
        if not block_has_grammar_marker and not block_has_vocab_marker:
            diagnostics['blocks_without_any_marker'] += 1
        if extracted_in_block == 0:
            diagnostics['blocks_with_no_extracted_entries'] += 1

    return grammar, vocab, diagnostics


def load_data_value_set(data_dir: Path):
    values = set()
    for csv_file in data_dir.rglob('*.csv'):
        try:
            with csv_file.open('r', encoding='utf-8', newline='') as f:
                reader = csv.reader(f, delimiter='|')
                for row in reader:
                    for cell in row:
                        cell = cell.strip()
                        if cell:
                            values.add(cell)
        except Exception:
            continue
    return values


def load_target_existing(path: Path, key_col: str):
    existing = set()
    if not path.exists():
        return existing
    with path.open('r', encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f, delimiter='|')
        for row in reader:
            val = (row.get(key_col) or '').strip()
            if val:
                existing.add(val)
    return existing


def dedupe_by_entry(candidates):
    best = {}
    for rec in candidates:
        entry = rec['entry'].strip()
        if not entry:
            continue
        prev = best.get(entry)
        if prev is None:
            best[entry] = rec
            continue

        prev_lvl = prev.get('level') or ''
        curr_lvl = rec.get('level') or ''

        if not prev_lvl and curr_lvl:
            best[entry] = rec
    return list(best.values())


def append_rows(path: Path, rows, fieldnames):
    with path.open('a', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter='|')
        for row in rows:
            writer.writerow(row)


def write_csv(path: Path, rows, fieldnames):
    with path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter='|')
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main():
    parser = argparse.ArgumentParser(description='Analyse le fichier manuel et propose/ajoute les points grammar & vocab manquants.')
    parser.add_argument('--input', default='output/sentences-reprocessed-ids.csv')
    parser.add_argument('--data-dir', default='data')
    parser.add_argument('--grammar-target', default='data/jlpt_grammar.csv')
    parser.add_argument('--vocab-target', default='data/jlpt_vocab_pedagogical.csv')
    parser.add_argument('--report-json', default='output/manual-notes-report.json')
    parser.add_argument('--missing-grammar-csv', default='output/manual-notes-missing-grammar.csv')
    parser.add_argument('--missing-vocab-csv', default='output/manual-notes-missing-vocab.csv')
    parser.add_argument('--apply', action='store_true', help='Ajoute directement les lignes manquantes dans les fichiers cibles')
    args = parser.parse_args()

    input_path = Path(args.input)
    data_dir = Path(args.data_dir)
    grammar_target = Path(args.grammar_target)
    vocab_target = Path(args.vocab_target)

    with input_path.open('r', encoding='utf-8') as f:
        lines = [ln.rstrip('\n') for ln in f]

    blocks = parse_blocks(lines)
    grammar_candidates, vocab_candidates, diagnostics = extract_candidates(blocks)

    grammar_candidates = dedupe_by_entry(grammar_candidates)
    vocab_candidates = dedupe_by_entry(vocab_candidates)

    data_values = load_data_value_set(data_dir)

    missing_grammar = []
    for rec in grammar_candidates:
        entry = rec['entry']
        if entry not in data_values:
            if rec.get('level'):
                missing_grammar.append({
                    'pattern': entry,
                    'jlpt_level': rec['level'],
                    'source': 'manual-notes',
                    'id': rec['id'],
                    'unknown': rec['unknown'],
                    'source_line': rec['source_line'],
                })

    missing_vocab = []
    for rec in vocab_candidates:
        entry = rec['entry']
        if entry not in data_values:
            if rec.get('level'):
                missing_vocab.append({
                    'word': entry,
                    'jlpt_level': rec['level'],
                    'source': 'manual-notes',
                    'id': rec['id'],
                    'unknown': rec['unknown'],
                    'source_line': rec['source_line'],
                })

    write_csv(
        Path(args.missing_grammar_csv),
        missing_grammar,
        ['pattern', 'jlpt_level', 'source', 'id', 'unknown', 'source_line'],
    )
    write_csv(
        Path(args.missing_vocab_csv),
        missing_vocab,
        ['word', 'jlpt_level', 'source', 'id', 'unknown', 'source_line'],
    )

    applied = {'grammar_added': 0, 'vocab_added': 0}

    if args.apply:
        existing_grammar = load_target_existing(grammar_target, 'pattern')
        existing_vocab = load_target_existing(vocab_target, 'word')

        grammar_to_add = [
            {'pattern': r['pattern'], 'jlpt_level': r['jlpt_level'], 'source': r['source']}
            for r in missing_grammar
            if r['pattern'] not in existing_grammar
        ]
        vocab_to_add = [
            {'word': r['word'], 'jlpt_level': r['jlpt_level'], 'source': r['source']}
            for r in missing_vocab
            if r['word'] not in existing_vocab
        ]

        append_rows(grammar_target, grammar_to_add, ['pattern', 'jlpt_level', 'source'])
        append_rows(vocab_target, vocab_to_add, ['word', 'jlpt_level', 'source'])

        applied['grammar_added'] = len(grammar_to_add)
        applied['vocab_added'] = len(vocab_to_add)

    report = {
        'input_file': str(input_path),
        'total_lines': len(lines),
        'headers_detected': len(blocks),
        'diagnostics': diagnostics,
        'extracted': {
            'grammar_candidates': len(grammar_candidates),
            'vocab_candidates': len(vocab_candidates),
            'missing_grammar_with_level': len(missing_grammar),
            'missing_vocab_with_level': len(missing_vocab),
        },
        'applied': applied,
        'outputs': {
            'report_json': args.report_json,
            'missing_grammar_csv': args.missing_grammar_csv,
            'missing_vocab_csv': args.missing_vocab_csv,
        },
    }

    report_path = Path(args.report_json)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
