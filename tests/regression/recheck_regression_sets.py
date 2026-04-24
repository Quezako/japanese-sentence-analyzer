#!/usr/bin/env python3
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from process_sentences import process_sentences

INPUT_FILE = ROOT / 'input' / 'sentences-only.csv'

OVER_CASES = ROOT / 'tests' / 'regression' / 'review_overestimated_cases.csv'
UNDER_CASES = ROOT / 'tests' / 'regression' / 'review_underestimated_cases.csv'
VALIDATED_CASES = ROOT / 'tests' / 'regression' / 'validated_cases.csv'

OVER_RECHECK_TMP = ROOT / 'output' / '_overestimated_recheck_tmp.csv'
OUT_OVER_UNCHANGED = ROOT / 'output' / 'overestimated_unchanged.csv'
OUT_OVER_CHANGED = ROOT / 'output' / 'overestimated_changed.csv'
OUT_UNDER = ROOT / 'output' / 'underestimated_recheck.csv'
OUT_VALIDATED_DIFF = ROOT / 'output' / 'validated_diff.csv'
OUT_VALIDATED_LEVEL_DIFF_GE2 = ROOT / 'output' / 'validated_level_diff_ge2.csv'

VALIDATED_RECHECK_TMP = ROOT / 'output' / '_validated_recheck_tmp.csv'

COMPARE_COLUMNS = [
    'sentence',
    'jlpt_no_katakana',
    'vocab_jlpt_pedagogical',
    'vocab_pedagogical_details',
    'vocab_jlpt_strict',
    'vocab_details',
    'kanji_jlpt',
    'kanji_details',
    'grammar_jlpt',
    'grammar_details',
]


def jlpt_to_numeric(level: str):
    normalized = str(level or '').strip().upper()
    mapping = {'N5': 1, 'N4': 2, 'N3': 3, 'N2': 4, 'N1': 5}
    return mapping.get(normalized)


def load_rows_by_id(path: Path):
    if not path.exists():
        return {}
    with path.open('r', encoding='utf-8', newline='') as file:
        reader = csv.DictReader(file, delimiter=';')
        rows = {}
        for row in reader:
            row_id = str(row.get('id', '')).strip()
            if not row_id:
                continue
            rows[row_id] = row
        return rows


def load_ids(path: Path):
    return list(load_rows_by_id(path).keys())


def run_recheck(ids, output_path: Path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not ids:
        with output_path.open('w', encoding='utf-8', newline='') as file:
            writer = csv.writer(file, delimiter=';')
            writer.writerow(['id'])
        return

    process_sentences(
        input_file=str(INPUT_FILE),
        output_file=str(output_path),
        ids=ids,
    )


def rows_different(expected_row, actual_row):
    for column in COMPARE_COLUMNS:
        expected = str(expected_row.get(column, '') or '').strip()
        actual = str(actual_row.get(column, '') or '').strip()
        if expected != actual:
            return True
    return False


def write_validated_diff(expected_rows, actual_rows, output_path: Path):
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = []
    if actual_rows:
        first_row = next(iter(actual_rows.values()))
        fieldnames = list(first_row.keys())
    elif expected_rows:
        first_row = next(iter(expected_rows.values()))
        fieldnames = [k for k in first_row.keys() if k != 'note']

    if not fieldnames:
        fieldnames = ['id']

    diff_rows = []
    for row_id, expected in expected_rows.items():
        actual = actual_rows.get(row_id)
        if not actual:
            continue
        if rows_different(expected, actual):
            diff_rows.append(actual)

    with output_path.open('w', encoding='utf-8', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, delimiter=';')
        writer.writeheader()
        writer.writerows(diff_rows)

    return len(diff_rows)


def write_validated_level_diff(expected_rows, actual_rows, output_path: Path, min_diff: int = 2):
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        'id',
        'sentence',
        'expected_jlpt_no_katakana',
        'actual_jlpt_no_katakana',
        'abs_level_diff',
        'direction',
    ]

    rows = []
    for row_id, expected in expected_rows.items():
        actual = actual_rows.get(row_id)
        if not actual:
            continue

        expected_level = str(expected.get('jlpt_no_katakana', '') or '').strip().upper()
        actual_level = str(actual.get('jlpt_no_katakana', '') or '').strip().upper()

        expected_num = jlpt_to_numeric(expected_level)
        actual_num = jlpt_to_numeric(actual_level)
        if expected_num is None or actual_num is None:
            continue

        abs_diff = abs(actual_num - expected_num)
        if abs_diff < min_diff:
            continue

        direction = 'harder_than_expected' if actual_num > expected_num else 'easier_than_expected'
        rows.append(
            {
                'id': row_id,
                'sentence': actual.get('sentence', expected.get('sentence', '')),
                'expected_jlpt_no_katakana': expected_level,
                'actual_jlpt_no_katakana': actual_level,
                'abs_level_diff': abs_diff,
                'direction': direction,
            }
        )

    with output_path.open('w', encoding='utf-8', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, delimiter=';')
        writer.writeheader()
        writer.writerows(rows)

    return len(rows)


def split_rows_by_diff(expected_rows, actual_rows):
    unchanged_rows = []
    changed_rows = []
    missing_count = 0

    for row_id, expected in expected_rows.items():
        actual = actual_rows.get(row_id)
        if not actual:
            missing_count += 1
            continue
        if rows_different(expected, actual):
            changed_rows.append(actual)
        else:
            unchanged_rows.append(actual)

    return unchanged_rows, changed_rows, missing_count


def write_rows(rows, output_path: Path, expected_rows=None):
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = []
    if rows:
        fieldnames = list(rows[0].keys())
    elif expected_rows:
        first_row = next(iter(expected_rows.values())) if expected_rows else {}
        fieldnames = [key for key in first_row.keys() if key != 'note']

    if not fieldnames:
        fieldnames = ['id']

    with output_path.open('w', encoding='utf-8', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, delimiter=';')
        writer.writeheader()
        writer.writerows(rows)


def main():
    over_ids = load_ids(OVER_CASES)
    under_ids = load_ids(UNDER_CASES)
    validated_ids = load_ids(VALIDATED_CASES)

    print(f'Overestimated IDs: {len(over_ids)}')
    print(f'Underestimated IDs: {len(under_ids)}')
    print(f'Validated IDs: {len(validated_ids)}')

    print('\n[1/3] Recheck overestimated IDs...')
    run_recheck(over_ids, OVER_RECHECK_TMP)

    expected_over = load_rows_by_id(OVER_CASES)
    actual_over = load_rows_by_id(OVER_RECHECK_TMP)
    over_unchanged, over_changed, over_missing = split_rows_by_diff(expected_over, actual_over)
    write_rows(over_unchanged, OUT_OVER_UNCHANGED, expected_rows=expected_over)
    write_rows(over_changed, OUT_OVER_CHANGED, expected_rows=expected_over)
    print(f'Written: {OUT_OVER_UNCHANGED} ({len(over_unchanged)} rows)')
    print(f'Written: {OUT_OVER_CHANGED} ({len(over_changed)} rows)')
    if over_missing:
        print(f'Overestimated missing IDs in recheck: {over_missing}')
    if OVER_RECHECK_TMP.exists():
        OVER_RECHECK_TMP.unlink()

    print('\n[2/3] Recheck underestimated IDs...')
    run_recheck(under_ids, OUT_UNDER)
    print(f'Written: {OUT_UNDER}')

    print('\n[3/3] Recheck validated IDs + diff...')
    run_recheck(validated_ids, VALIDATED_RECHECK_TMP)

    expected_validated = load_rows_by_id(VALIDATED_CASES)
    actual_validated = load_rows_by_id(VALIDATED_RECHECK_TMP)
    diff_count = write_validated_diff(expected_validated, actual_validated, OUT_VALIDATED_DIFF)
    print(f'Written: {OUT_VALIDATED_DIFF} ({diff_count} differing rows)')
    ge2_count = write_validated_level_diff(
        expected_validated,
        actual_validated,
        OUT_VALIDATED_LEVEL_DIFF_GE2,
        min_diff=2,
    )
    print(f'Written: {OUT_VALIDATED_LEVEL_DIFF_GE2} ({ge2_count} rows with abs diff >= 2)')

    try:
        VALIDATED_RECHECK_TMP.unlink()
    except FileNotFoundError:
        pass


if __name__ == '__main__':
    main()
