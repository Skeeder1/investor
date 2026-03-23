import csv
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from ..domain.dedup import deduplicate, key_from_csv_row
from ..domain.models import Transaction

FIELDNAMES = [
    "date",
    "time",
    "asset_name",
    "type",
    "asset_price",
    "units",
    "fees",
    "total",
    "source_file",
]


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, "r", newline="", encoding="utf-8-sig") as f:
        first = f.readline()
        if not first.startswith("sep="):
            f.seek(0)
        return list(csv.DictReader(f, delimiter=";"))


def load_known_assets_and_files(path: Path) -> tuple[set[str], set[str]]:
    rows = read_csv(path)
    known_assets: set[str] = set()
    processed_files: set[str] = set()
    for row in rows:
        if row.get("asset_name"):
            known_assets.add(row["asset_name"])
        if row.get("source_file"):
            processed_files.add(row["source_file"])
    return known_assets, processed_files


def write_csv(rows: list[dict], path: Path) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        f.write("sep=;\n")
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)


def deduplicate_and_write(transactions: list[Transaction], output_csv: str) -> tuple[int, int]:
    """Deduplicate transactions against existing CSV and write results.

    Returns (new_count, duplicate_count).
    """
    csv_path = Path(output_csv)
    existing_rows = read_csv(csv_path)

    existing_keys = Counter(key_from_csv_row(row) for row in existing_rows)
    unique_new = deduplicate(transactions, existing_keys)
    duplicates = len(transactions) - len(unique_new)

    if not unique_new:
        return 0, duplicates

    new_rows = []
    for tx in unique_new:
        row = asdict(tx)
        del row["status"]
        new_rows.append(row)

    all_rows = existing_rows + new_rows
    all_rows.sort(key=lambda r: (r["date"], r["time"]))
    write_csv(all_rows, csv_path)
    return len(unique_new), duplicates
