#!/usr/bin/env python3
import argparse
import csv
import sys
from pathlib import Path

DEFAULT_COLUMNS = [
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

COARSE_COLUMNS = [
    'sentence',
    'jlpt_no_katakana',
    'vocab_jlpt_pedagogical',
    'vocab_jlpt_strict',
    'kanji_jlpt',
    'grammar_jlpt',
]


def load_csv_by_id(path: Path):
    if not path.exists():
        return {}
    with path.open('r', encoding='utf-8', newline='') as file:
        reader = csv.DictReader(file, delimiter=';')
        rows = {}
        for row in reader:
            row_id = str(row.get('id', '')).strip()
            if not row_id:
                continue
            rows[row_id] = {key: (value if value is not None else '') for key, value in row.items()}
        return rows


def normalize(value):
    return str(value or '').strip()


def compare_rows(expected, actual, columns):
    diffs = []
    for column in columns:
        exp_val = normalize(expected.get(column, ''))
        act_val = normalize(actual.get(column, ''))
        if exp_val != act_val:
            diffs.append((column, exp_val, act_val))
    return diffs


def find_cross_file_duplicates(named_rows):
    """Return mapping id -> [file labels] for IDs present in multiple files."""
    id_sources = {}
    for label, rows in named_rows.items():
        for row_id in rows.keys():
            id_sources.setdefault(row_id, []).append(label)
    return {row_id: sources for row_id, sources in id_sources.items() if len(sources) > 1}


def main():
    parser = argparse.ArgumentParser(description='Regression check for sentence analyzer outputs.')
    parser.add_argument('--current', required=True, help='Current output CSV to validate.')
    parser.add_argument(
        '--validated',
        default='tests/regression/validated_cases.csv',
        help='CSV containing manually validated (gold) lines.',
    )
    parser.add_argument(
        '--review-over',
        default='tests/regression/review_overestimated_cases.csv',
        help='CSV containing overestimated lines to review (non-blocking).',
    )
    parser.add_argument(
        '--review-under',
        default='tests/regression/review_underestimated_cases.csv',
        help='CSV containing underestimated lines to review (non-blocking).',
    )
    parser.add_argument(
        '--waiting-review',
        '--accepted',
        dest='waiting_review',
        default='tests/regression/waiting_review_cases.csv',
        help='CSV containing lines not yet manually validated (coarse checks).',
    )
    parser.add_argument(
        '--columns',
        default=','.join(DEFAULT_COLUMNS),
        help='Comma-separated list of columns compared for regressions.',
    )
    parser.add_argument(
        '--waiting-review-columns',
        '--accepted-columns',
        dest='waiting_review_columns',
        default=','.join(COARSE_COLUMNS),
        help='Comma-separated columns compared for waiting-review (coarse) cases.',
    )
    parser.add_argument(
        '--fail-on-waiting-review',
        '--fail-on-accepted',
        dest='fail_on_waiting_review',
        action='store_true',
        help='Also fail when waiting-review (coarse) cases change.',
    )
    args = parser.parse_args()

    current_path = Path(args.current)
    validated_path = Path(args.validated)
    review_over_path = Path(args.review_over)
    review_under_path = Path(args.review_under)
    waiting_review_path = Path(args.waiting_review)
    columns = [column.strip() for column in args.columns.split(',') if column.strip()]
    waiting_review_columns = [column.strip() for column in args.waiting_review_columns.split(',') if column.strip()]

    current_rows = load_csv_by_id(current_path)
    validated_rows = load_csv_by_id(validated_path)
    review_over_rows = load_csv_by_id(review_over_path)
    review_under_rows = load_csv_by_id(review_under_path)
    waiting_review_rows = load_csv_by_id(waiting_review_path)

    duplicates = find_cross_file_duplicates({
        'validated': validated_rows,
        'waiting_review': waiting_review_rows,
        'review_over': review_over_rows,
        'review_under': review_under_rows,
    })

    regressions = []
    missing_in_current = []
    waiting_review_changes = []
    waiting_review_missing = []

    for row_id, expected_row in validated_rows.items():
        current_row = current_rows.get(row_id)
        if current_row is None:
            missing_in_current.append(row_id)
            continue
        diffs = compare_rows(expected_row, current_row, columns)
        if diffs:
            regressions.append((row_id, diffs))

    print(f'Current rows: {len(current_rows)}')
    print(f'Validated cases: {len(validated_rows)}')
    print(f'Waiting-review cases: {len(waiting_review_rows)}')
    print(f'Review overestimated: {len(review_over_rows)}')
    print(f'Review underestimated: {len(review_under_rows)}')

    if duplicates:
        print('\n[ERROR] Duplicate IDs across regression files:')
        for row_id, sources in sorted(duplicates.items(), key=lambda item: item[0]):
            joined = ', '.join(sources)
            print(f'  - {row_id}: {joined}')

    if missing_in_current:
        print('\n[ERROR] Missing validated IDs in current output:')
        for row_id in missing_in_current:
            print(f'  - {row_id}')

    if regressions:
        print('\n[ERROR] Regressions detected on validated cases:')
        for row_id, diffs in regressions:
            print(f'  - id={row_id}')
            for column, expected, actual in diffs:
                print(f'      {column}: expected="{expected}" | actual="{actual}"')
    else:
        print('\n[OK] No regression detected on validated cases.')

    for row_id, expected_row in waiting_review_rows.items():
        current_row = current_rows.get(row_id)
        if current_row is None:
            waiting_review_missing.append(row_id)
            continue
        diffs = compare_rows(expected_row, current_row, waiting_review_columns)
        if diffs:
            waiting_review_changes.append((row_id, diffs))

    if waiting_review_missing:
        print('\n[WARN] Missing waiting-review IDs in current output:')
        for row_id in waiting_review_missing:
            print(f'  - {row_id}')

    if waiting_review_changes:
        print('\n[WAITING_REVIEW] Coarse changes detected (review before promoting to gold):')
        for row_id, diffs in waiting_review_changes:
            print(f'  - id={row_id}')
            for column, expected, actual in diffs:
                print(f'      {column}: expected="{expected}" | actual="{actual}"')
    elif waiting_review_rows:
        print('\n[OK] No coarse change on waiting-review cases.')

    def print_review_block(title, rows):
        changed = 0
        if rows:
            print(f'\n[{title}] Cases to inspect manually (non-blocking):')
            for row_id, expected_row in rows.items():
                current_row = current_rows.get(row_id)
                if current_row is None:
                    print(f'  - id={row_id}: missing in current output')
                    continue
                diffs = compare_rows(expected_row, current_row, columns)
                status = 'changed' if diffs else 'unchanged'
                if diffs:
                    changed += 1
                note = normalize(expected_row.get('note', ''))
                note_part = f' | note={note}' if note else ''
                print(f'  - id={row_id}: {status}{note_part}')
        return changed

    review_changed_over = print_review_block('REVIEW_OVER', review_over_rows)
    review_changed_under = print_review_block('REVIEW_UNDER', review_under_rows)

    has_error = bool(missing_in_current or regressions or duplicates)
    if args.fail_on_waiting_review and (waiting_review_missing or waiting_review_changes):
        has_error = True
    total_review = len(review_over_rows) + len(review_under_rows)
    total_review_changed = review_changed_over + review_changed_under
    if total_review:
        print(f'\nReview summary: {total_review_changed} changed / {total_review} total.')

    return 1 if has_error else 0


if __name__ == '__main__':
    raise SystemExit(main())
