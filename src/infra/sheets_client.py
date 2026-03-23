from collections import Counter
from datetime import datetime
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

from ..domain.asset_rules import (
    format_euro,
    format_units,
    map_asset_display,
    map_compte,
    map_type_label,
    parse_amount,
    parse_units,
)
from ..domain.datetime_utils import parse_french_date, to_french_date_label
from ..domain.dedup import key_from_sheet_row

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def connect(sa_path: Path, spreadsheet_id: str, sheet_name: str):
    creds = Credentials.from_service_account_file(str(sa_path), scopes=SCOPES)
    gc = gspread.authorize(creds)
    ss = gc.open_by_key(spreadsheet_id)
    ws = ss.worksheet(sheet_name)
    return ss, ws


def get_all_sheet_data(ws) -> tuple[Counter, list]:
    """Return (Counter of keys, list of (row_index_1based, datetime) for dates)."""
    keys = Counter()
    dates = []
    rows = ws.get_all_values()
    if not rows:
        return keys, dates

    for i, row in enumerate(rows[1:], start=2):  # row 1 = header
        if len(row) < 7 or not row[0].strip():
            continue
        date_fr = row[0]
        asset = row[3]
        montant = parse_amount(row[4])
        units = parse_units(row[5])
        try:
            key = key_from_sheet_row(date_fr, asset, montant, units)
        except ValueError:
            continue
        keys[key] += 1

        try:
            parsed_date = parse_french_date(date_fr)
        except ValueError:
            parsed_date = datetime.min
        dates.append((i, parsed_date))

    return keys, dates


def find_insert_position(sheet_dates, new_dt) -> int:
    if not sheet_dates:
        return 2
    for row_idx, dt in sheet_dates:
        if dt > new_dt:
            return row_idx
    return sheet_dates[-1][0] + 1


def register_insert(sheet_dates, pos: int, dt) -> list:
    updated = []
    for row_idx, row_dt in sheet_dates:
        if row_idx >= pos:
            updated.append((row_idx + 1, row_dt))
        else:
            updated.append((row_idx, row_dt))
    updated.append((pos, dt))
    updated.sort(key=lambda x: x[0])
    return updated


def insert_row(ws, row: list, pos: int) -> None:
    ws.insert_row(row, pos, value_input_option="USER_ENTERED")


def to_sheet_row(row: dict) -> list:
    t = row.get("type", "buy")
    name = row.get("asset_name", "")
    compte = map_compte(t, name)
    asset = map_asset_display(name, compte)
    return [
        to_french_date_label(row["date"]),
        map_type_label(t),
        compte,
        asset,
        format_euro(row.get("total", 0)),
        format_units(row.get("units", 0)),
        format_euro(row.get("asset_price", 0)),
        format_euro(row.get("fees", 0)),
    ]
