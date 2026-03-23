from pathlib import Path

from src.domain.models import Transaction
from src.infra.csv_store import deduplicate_and_write, read_csv


def _tx(source: str, asset: str, total: float, units: float) -> Transaction:
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


def test_read_csv_missing_file_returns_empty(tmp_path: Path):
    missing = tmp_path / "missing.csv"
    assert read_csv(missing) == []


def test_deduplicate_and_write_cycle(tmp_path: Path):
    csv_path = tmp_path / "transactions.csv"

    first_batch = [
        _tx("a.png", "Bitcoin", 100.0, 0.1),
        _tx("b.png", "Ethereum", 50.0, 0.05),
    ]
    new_count, dup_count = deduplicate_and_write(first_batch, str(csv_path))

    assert new_count == 2
    assert dup_count == 0

    second_batch = [
        _tx("c.png", "Bitcoin", 100.0, 0.1),  # doublon metier
        _tx("d.png", "Solana", 75.0, 0.3),
    ]
    new_count2, dup_count2 = deduplicate_and_write(second_batch, str(csv_path))

    assert new_count2 == 1
    assert dup_count2 == 1

    rows = read_csv(csv_path)
    assert len(rows) == 3
    assert [r["asset_name"] for r in rows] == ["Bitcoin", "Ethereum", "Solana"]
