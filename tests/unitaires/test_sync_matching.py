from collections import Counter

from src.app.sync import _split_new_rows_with_relaxed_match


def test_split_new_rows_matches_strict_first():
    existing = Counter({("2026-01-01", "solana", 30.0, 0.391): 1})
    csv_entries = [
        (("2026-01-01", "solana", 30.0, 0.391), {"id": "a"}),
    ]

    new_rows, matched_exact, matched_relaxed = _split_new_rows_with_relaxed_match(csv_entries, existing)

    assert new_rows == []
    assert matched_exact == 1
    assert matched_relaxed == 0


def test_split_new_rows_matches_relaxed_when_units_differ():
    existing = Counter({("2026-01-01", "solana", 30.0, 0.391): 1})
    csv_entries = [
        (("2026-01-01", "solana", 30.0, 0.390994), {"id": "a"}),
    ]

    new_rows, matched_exact, matched_relaxed = _split_new_rows_with_relaxed_match(csv_entries, existing)

    assert new_rows == []
    assert matched_exact == 0
    assert matched_relaxed == 1


def test_split_new_rows_keeps_true_new_row():
    existing = Counter({("2026-01-01", "solana", 30.0, 0.391): 1})
    csv_entries = [
        (("2026-01-02", "solana", 50.0, 0.25), {"id": "new"}),
    ]

    new_rows, matched_exact, matched_relaxed = _split_new_rows_with_relaxed_match(csv_entries, existing)

    assert new_rows == [{"id": "new"}]
    assert matched_exact == 0
    assert matched_relaxed == 0
