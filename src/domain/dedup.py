from collections import Counter
from typing import Any

from .asset_rules import map_asset_display, map_compte
from .datetime_utils import normalize_date_iso, parse_french_date
from .models import Transaction

def transaction_key(date_iso: str, asset_name: str, total: float, units: float) -> tuple:
    """Canonical dedup key used by both CSV and Sheets flows."""
    return (
        str(date_iso).strip(),
        str(asset_name).strip().lower(),
        round(float(total), 2),
        round(float(units), 4),
    )


def key_from_transaction(tx: Transaction) -> tuple:
    return transaction_key(tx.date, tx.asset_name, tx.total, tx.units)


def key_from_csv_row(row: dict) -> tuple:
    date_raw = row.get("date", "")
    try:
        date_iso = normalize_date_iso(str(date_raw))
    except Exception:
        date_iso = date_raw

    asset_name_raw = str(row.get("asset_name", ""))
    tx_type = str(row.get("type", ""))
    compte = map_compte(tx_type, asset_name_raw)
    asset_name = map_asset_display(asset_name_raw, compte)

    total = row.get("total", 0)
    units = row.get("units", 0)
    return transaction_key(date_iso, asset_name, total, units)


def key_from_sheet_row(date_fr: str, asset: str, montant: float, units: float) -> tuple:
    date_iso = parse_french_date(date_fr).strftime("%Y-%m-%d")
    return transaction_key(date_iso, asset, montant, units)


def _infer_key(item: Any) -> tuple:
    if isinstance(item, Transaction):
        return key_from_transaction(item)
    if isinstance(item, dict):
        return key_from_csv_row(item)
    raise TypeError(f"Unsupported item type for dedup: {type(item)!r}")


def deduplicate(new_items: list, existing_keys: Counter) -> list:
    """Keep only occurrences that exceed what already exists, preserving order."""
    seen = Counter()
    kept: list = []

    for item in new_items:
        key = _infer_key(item)
        seen[key] += 1
        if seen[key] > existing_keys.get(key, 0):
            kept.append(item)

    return kept
