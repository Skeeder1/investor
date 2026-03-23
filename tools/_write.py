"""Bootstrap: writes the final sync_sheets.py content."""
from pathlib import Path

content = """\
import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

SPREADSHEET_ID = "1edxyVxRjEtYAWVETnV7398yXxCOCs9pyuhJhcuaU3xU"
SHEET_NAME = "\\u26aa CTO"
CSV_PATH = Path(__file__).resolve().parent.parent / "output" / "transactions.csv"
SERVICE_ACCOUNT_PATH = Path.home() / ".config" / "clef_google" / "service-account.json"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

_MOIS = {
    1: "janvier", 2: "f\\u00e9vrier", 3: "mars", 4: "avril",
    5: "mai", 6: "juin", 7: "juillet", 8: "ao\\u00fbt",
    9: "septembre", 10: "octobre", 11: "novembre", 12: "d\\u00e9cembre",
}


def _format_date_fr(date_str):
    dt = datetime.strptime(date_str, "%d/%m/%Y")
    return f"{dt.day:02d} {_MOIS[dt.month]} {dt.year}"


def _format_euro(value):
    v = float(value)
    if v == 0.0:
        return "0,00 \\u20ac"
    formatted = f"{v:,.2f}".replace(",", " ").replace(".", ",")
    return formatted + " \\u20ac"


def _format_units(value):
    s = f"{float(value):.6f}".rstrip("0")
    if s.endswith("."):
        s += "0"
    return s.replace(".", ",")


def _map_type(t):
    return "Achat" if t in ("buy", "pea") else "Vente"


def _map_compte(t, name):
    if t == "pea":
        return "PEA"
    if "S&P 500 EUR" in name:
        return "PEA"
    return "CTO"


def _map_asset(name, compte):
    if compte == "PEA" and "S&P 500 EUR" in name:
        return "S&P 500"
    return name


def read_csv(path):
    with open(path, "r", newline="", encoding="utf-8-sig") as f:
        first = f.readline()
        if not first.startswith("sep="):
            f.seek(0)
        return list(csv.DictReader(f, delimiter=";"))


def get_existing_keys(ws):
    keys = set()
    for row in ws.get_all_values()[1:]:
        if len(row) >= 5 and row[0]:
            keys.add((row[0], row[3], row[4]))
    return keys


def to_sheet_row(row):
    t = row.get("type", "buy")
    name = row.get("asset_name", "")
    compte = _map_compte(t, name)
    asset = _map_asset(name, compte)
    return [
        _format_date_fr(row["date"]),
        _map_type(t),
        compte,
        asset,
        _format_euro(row.get("total", 0)),
        _format_units(row.get("units", 0)),
        _format_euro(row.get("asset_price", 0)),
        _format_euro(row.get("fees", 0)),
    ]


def main():
    p = argparse.ArgumentParser(description="Sync CSV -> Google Sheets (CTO)")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--limit", type=int, help="Nombre de lignes a transferer")
    g.add_argument("--all", action="store_true", help="Transferer toutes les lignes manquantes")
    p.add_argument("--dry-run", action="store_true", help="Afficher sans ecrire (defaut si ni --limit ni --all)")
    p.add_argument("--csv", default=str(CSV_PATH), help="Chemin du CSV")
    args = p.parse_args()

    dry_run = args.dry_run or (args.limit is None and not args.all)

    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"CSV introuvable : {csv_path}")
        sys.exit(1)

    rows = read_csv(csv_path)
    print(f"CSV : {len(rows)} lignes lues")

    if not SERVICE_ACCOUNT_PATH.exists():
        print(f"Service account introuvable : {SERVICE_ACCOUNT_PATH}")
        sys.exit(1)

    creds = Credentials.from_service_account_file(str(SERVICE_ACCOUNT_PATH), scopes=SCOPES)
    gc = gspread.authorize(creds)
    ss = gc.open_by_key(SPREADSHEET_ID)
    ws = ss.worksheet(SHEET_NAME)
    print(f"Sheet : {ss.title} -> {SHEET_NAME}")

    existing = get_existing_keys(ws)
    print(f"Lignes existantes dans le sheet : {len(existing)}")

    new_rows = []
    for row in rows:
        t = row.get("type", "buy")
        name = row.get("asset_name", "")
        compte = _map_compte(t, name)
        asset = _map_asset(name, compte)
        key = (_format_date_fr(row["date"]), asset, _format_euro(row.get("total", 0)))
        if key not in existing:
            new_rows.append(row)

    print(f"Nouvelles lignes a ajouter : {len(new_rows)}")

    if not new_rows:
        print("Rien a synchroniser -- le sheet est a jour.")
        return

    if args.limit:
        new_rows = new_rows[:args.limit]
        print(f"Limite a {args.limit} ligne(s)")

    sheet_rows = [to_sheet_row(r) for r in new_rows]

    if dry_run:
        print("\\n-- Mode dry-run (aucune ecriture) --")
        for i, sr in enumerate(sheet_rows, 1):
            print(f"  [{i}] {sr[0]} | {sr[2]} | {sr[3]} | {sr[4]}")
        print(f"\\nRelance avec --limit {len(sheet_rows)} ou --all pour ecrire")
        return

    for i, sr in enumerate(sheet_rows, 1):
        ws.append_row(sr, value_input_option="USER_ENTERED")
        print(f"  [{i}/{len(sheet_rows)}] {sr[0]} | {sr[2]} | {sr[3]} | {sr[4]}")

    print(f"\\n{len(sheet_rows)} ligne(s) ajoutee(s) !")


if __name__ == "__main__":
    main()
"""

out = Path(__file__).parent / "sync_sheets.py"
out.write_text(content, encoding="utf-8")
print(f"Written {len(content)} chars to {out}")

