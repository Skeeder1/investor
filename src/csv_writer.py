import csv
from dataclasses import asdict
from pathlib import Path

from .models import Transaction

FIELDNAMES = [
    "date", "time", "asset_name", "type",
    "asset_price", "units", "fees", "total", "source_file",
]


def _tx_key(t) -> tuple:
    """Unique key: date + time + asset_name + total."""
    if isinstance(t, Transaction):
        return (t.date, t.time, t.asset_name, str(t.total))
    # dict from CSV row
    return (t.get("date", ""), t.get("time", ""), t.get("asset_name", ""), t.get("total", ""))


def deduplicate_and_write(
    transactions: list[Transaction],
    output_csv: str,
) -> tuple[int, int]:
    """Deduplicate transactions against existing CSV and write results.

    Returns (new_count, duplicate_count).
    """
    # Load keys already present in the CSV output file
    existing_keys: set = set()
    existing_rows: list[dict] = []
    csv_path = Path(output_csv)

    if csv_path.exists():
        with open(csv_path, "r", newline="", encoding="utf-8-sig") as f:
            first = f.readline()
            if not first.startswith("sep="):
                f.seek(0)
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                existing_rows.append(row)
                existing_keys.add(_tx_key(row))

    # Deduplicate within the current batch
    seen: set = set()
    duplicates = 0
    unique_new: list[Transaction] = []

    for tx in transactions:
        k = _tx_key(tx)
        if k in seen or k in existing_keys:
            duplicates += 1
        else:
            seen.add(k)
            unique_new.append(tx)

    # Write CSV
    if unique_new:
        new_rows = []
        for tx in unique_new:
            row = asdict(tx)
            del row["status"]
            new_rows.append(row)

        all_rows = existing_rows + new_rows
        all_rows.sort(key=lambda r: (r["date"], r["time"]))

        with open(output_csv, "w", newline="", encoding="utf-8-sig") as f:
            f.write("sep=;\n")
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES, delimiter=";")
            writer.writeheader()
            writer.writerows(all_rows)

        return len(unique_new), duplicates

    return 0, duplicates
