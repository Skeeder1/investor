from collections import Counter

from src.domain.dedup import (
    deduplicate,
    key_from_csv_row,
    key_from_sheet_row,
    key_from_transaction,
    transaction_key,
)
from src.domain.models import Transaction

def _tx(asset: str, total: float, units: float, source: str) -> Transaction:
    return Transaction(
        date="2026-03-01",
        time="09:00",
        asset_name=asset,
        asset_price=1.0,
        units=units,
        fees=0.0,
        total=total,
        type="buy",
        status="completed",
        source_file=source,
    )


def test_transaction_key_is_normalized():
    key = transaction_key("2026-03-01", "  Bitcoin  ", 100.004, 0.123456)
    assert key == ("2026-03-01", "bitcoin", 100.0, 0.1235)


def test_key_from_transaction():
    tx = _tx("Ethereum", 150.0, 0.05, "a.png")
    assert key_from_transaction(tx) == ("2026-03-01", "ethereum", 150.0, 0.05)


def test_key_from_csv_row_normalizes_french_date_to_iso():
    key = key_from_csv_row(
        {
            "date": "02/08/2025",
            "asset_name": "Bitcoin",
            "total": 100,
            "units": 0.1,
        }
    )
    assert key == ("2025-08-02", "bitcoin", 100.0, 0.1)


def test_key_from_csv_row_normalizes_pea_asset_name_to_sheet_display():
    key = key_from_csv_row(
        {
            "date": "02/01/2026",
            "asset_name": "S&P 500 EUR (Acc)",
            "type": "buy",
            "total": 58.89,
            "units": 0.0,
        }
    )
    assert key == ("2026-01-02", "s&p 500", 58.89, 0.0)


def test_key_from_sheet_row_uses_french_date_parsing():
    key = key_from_sheet_row("02 février 2026", "Bitcoin", 123.45, 0.001)
    assert key == ("2026-02-02", "bitcoin", 123.45, 0.001)


def test_deduplicate_with_existing_counter_and_new_duplicates():
    t1 = _tx("Bitcoin", 100, 0.1, "1.png")
    t2 = _tx("Bitcoin", 100, 0.1, "2.png")
    t3 = _tx("Ethereum", 50, 0.02, "3.png")

    existing = Counter({key_from_transaction(t1): 1})
    kept = deduplicate([t1, t2, t3], existing)

    assert kept == [t2, t3]
