import argparse
import csv
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Optional

import gspread
from google.oauth2.service_account import Credentials

SPREADSHEET_ID = "1edxyVxRjEtYAWVETnV7398yXxCOCs9pyuhJhcuaU3xU"
SHEET_NAME = "\u26aa CTO"
CSV_PATH = Path(__file__).resolve().parent.parent / "output" / "transactions.csv"
SERVICE_ACCOUNT_PATH = Path.home() / ".config" / "clef_google" / "service-account.json"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# ── ANSI colors ──────────────────────────────────────────────
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
RED = "\033[31m"
MAGENTA = "\033[35m"
WHITE = "\033[97m"
BG_BLUE = "\033[44m"


def _c(color, text):
    return f"{color}{text}{RESET}"


def _header(title):
    w = 60
    border = _c(CYAN, "\u2550" * w)
    print(f"\n{border}")
    print(_c(BOLD + WHITE + BG_BLUE, f"  {title.center(w - 2)}  "))
    print(f"{border}")


def _sep():
    print(_c(DIM, "\u2500" * 60))


def _stat(label, value, color=WHITE):
    print(f"  {_c(DIM, label + ' :'):.<40} {_c(color + BOLD, value)}")


_MOIS = {
    1: "janvier", 2: "f\u00e9vrier", 3: "mars", 4: "avril",
    5: "mai", 6: "juin", 7: "juillet", 8: "ao\u00fbt",
    9: "septembre", 10: "octobre", 11: "novembre", 12: "d\u00e9cembre",
}

_MOIS_REV = {v: k for k, v in _MOIS.items()}


def _parse_date_fr(text):
    """Parse '26 mai 2025' -> datetime."""
    parts = text.strip().split()
    if len(parts) != 3:
        return datetime.min
    try:
        day = int(parts[0])
        month = _MOIS_REV.get(parts[1].lower(), 0)
        year = int(parts[2])
        return datetime(year, month, day)
    except (ValueError, TypeError):
        return datetime.min


def _format_date_fr(date_str):
    dt = datetime.strptime(date_str, "%d/%m/%Y")
    return f"{dt.day:02d} {_MOIS[dt.month]} {dt.year}"


def _format_euro(value):
    v = float(value)
    if v == 0.0:
        return "0,00 \u20ac"
    formatted = f"{v:,.2f}".replace(",", " ").replace(".", ",")
    return formatted + " \u20ac"


def _format_units(value):
    s = f"{float(value):.6f}".rstrip("0")
    if s.endswith("."):
        s += "0"
    return s.replace(".", ",")


def _parse_amount(text):
    """Parse un montant du sheet ('2 910,26 €' ou '14,44') en float."""
    if not text or not text.strip():
        return 0.0
    s = text.strip().rstrip("€").strip()
    s = s.replace("\u00a0", "").replace(" ", "")
    s = s.replace(",", ".")
    try:
        return round(float(s), 2)
    except ValueError:
        return 0.0


def _parse_units(text):
    """Parse des unites du sheet ('0,163213') en float."""
    if not text or not text.strip():
        return 0.0
    s = text.strip().replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def _make_key(date_fr, type_ordre, asset, montant_float, units_float):
    """Cle de dedup : (date, type, actif, montant entier, unites a 2 dec)."""
    return (
        date_fr.strip().lower(),
        type_ordre.strip().lower(),
        asset.strip().lower(),
        int(montant_float),
        round(units_float, 2),
    )


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


def _get_all_sheet_data(ws):
    """Retourne (Counter des cles, liste de (row_index_1based, datetime) pour les dates)."""
    keys = Counter()
    dates = []  # [(row_index_1based, datetime), ...]
    rows = ws.get_all_values()
    if not rows:
        return keys, dates
    for i, row in enumerate(rows[1:], start=2):  # row 1 = header
        if len(row) < 7 or not row[0].strip():
            continue
        date_fr = row[0]
        type_ordre = row[1]
        asset = row[3]
        montant = _parse_amount(row[4])
        units = _parse_units(row[5])
        key = _make_key(date_fr, type_ordre, asset, montant, units)
        keys[key] += 1
        dates.append((i, _parse_date_fr(date_fr)))
    return keys, dates


def _find_insert_pos(sheet_dates, new_dt):
    """Trouve la position (1-based) ou inserer pour garder l'ordre chronologique."""
    if not sheet_dates:
        return 2  # apres le header
    # Chercher la premiere date strictement apres new_dt
    for row_idx, dt in sheet_dates:
        if dt > new_dt:
            return row_idx
    # Toutes les dates sont <= new_dt : inserer apres la derniere
    return sheet_dates[-1][0] + 1


def _register_insert(sheet_dates, pos, dt):
    """Met a jour les index de lignes en memoire apres une insertion a `pos`."""
    updated = []
    for row_idx, row_dt in sheet_dates:
        if row_idx >= pos:
            updated.append((row_idx + 1, row_dt))
        else:
            updated.append((row_idx, row_dt))
    updated.append((pos, dt))
    updated.sort(key=lambda x: x[0])
    return updated


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


def _row_display(idx, total, sr, compact=False):
    """Formate une ligne pour l'affichage."""
    num = f"[{idx}/{total}]"
    date = _c(CYAN, sr[0])
    typ = _c(GREEN, sr[1]) if sr[1] == "Achat" else _c(RED, sr[1])
    compte = _c(MAGENTA, sr[2])
    asset = _c(BOLD + WHITE, sr[3])
    montant = _c(YELLOW, sr[4])
    units = _c(DIM, sr[5])
    if compact:
        return f"  {_c(DIM, num)} {date} {typ} {compte} {asset} {montant}"
    return f"  {_c(DIM, num)} {date} | {typ} | {compte} | {asset} | {montant} | {units}"


def sync_csv_to_sheet(
    csv_path: str | Path = CSV_PATH,
    mode: str = "dry-run",
    limit: Optional[int] = None,
) -> dict:
    """Synchronise le CSV vers Google Sheets.

    mode: "send", "dry-run" ou "confirm"
    """
    valid_modes = {"send", "dry-run", "confirm"}
    if mode not in valid_modes:
        raise ValueError(f"Mode invalide: {mode} (attendu: {', '.join(sorted(valid_modes))})")

    dry_run = mode == "dry-run"
    confirm_mode = mode == "confirm"

    # ── Chargement CSV ───────────────────────────────────────
    _header("SYNC CSV → Google Sheets")

    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV introuvable : {csv_path}")

    rows = read_csv(csv_path)

    if not SERVICE_ACCOUNT_PATH.exists():
        raise FileNotFoundError(f"Service account introuvable : {SERVICE_ACCOUNT_PATH}")

    # ── Connexion Google Sheets ──────────────────────────────
    creds = Credentials.from_service_account_file(str(SERVICE_ACCOUNT_PATH), scopes=SCOPES)
    gc = gspread.authorize(creds)
    ss = gc.open_by_key(SPREADSHEET_ID)
    ws = ss.worksheet(SHEET_NAME)

    existing, sheet_dates = _get_all_sheet_data(ws)

    # ── Deduplication ────────────────────────────────────────
    csv_entries = []
    for row in rows:
        sheet_row = to_sheet_row(row)
        montant = round(float(row.get("total", 0)), 2)
        units = float(row.get("units", 0))
        key = _make_key(sheet_row[0], sheet_row[1], sheet_row[3], montant, units)
        csv_entries.append((key, row))

    used = Counter()
    new_rows = []
    for key, row in csv_entries:
        used[key] += 1
        if used[key] > existing.get(key, 0):
            new_rows.append(row)

    total_csv_keys = Counter(k for k, _ in csv_entries)
    matched = sum(min(total_csv_keys[k], existing.get(k, 0)) for k in total_csv_keys)

    # ── Panel de statistiques ────────────────────────────────
    _stat("Spreadsheet", ss.title, CYAN)
    _stat("Sheet", SHEET_NAME, CYAN)
    _stat("CSV", f"{len(rows)} lignes", WHITE)
    _stat("Sheet existant", f"{sum(existing.values())} lignes", WHITE)
    _stat("Doublons detectes", str(matched), YELLOW)
    _stat("Nouvelles lignes", str(len(new_rows)), GREEN if new_rows else YELLOW)
    _stat("Mode", mode, MAGENTA)
    _sep()

    if not new_rows:
        print(_c(GREEN + BOLD, "\n  ✔ Rien a synchroniser — le sheet est a jour.\n"))
        return {"sent": 0, "mode": mode, "new_rows": 0, "matched": matched}

    if limit:
        new_rows = new_rows[:limit]
        print(_c(DIM, f"  Limite a {limit} ligne(s)"))

    # Preparer les lignes avec leur date pour tri chronologique
    prepared = []
    for r in new_rows:
        sr = to_sheet_row(r)
        dt = datetime.strptime(r["date"], "%d/%m/%Y")
        prepared.append((sr, dt))
    total = len(prepared)

    # ── Mode dry-run ─────────────────────────────────────────
    if dry_run:
        print(_c(YELLOW + BOLD, "\n  ⚠  Mode dry-run (aucune ecriture)\n"))
        sim_dates = list(sheet_dates)
        for i, (sr, dt) in enumerate(prepared, 1):
            pos = _find_insert_pos(sim_dates, dt)
            print(_row_display(i, total, sr) + _c(DIM, f"  → ligne {pos}"))
            sim_dates = _register_insert(sim_dates, pos, dt)
        _sep()
        send_cmd = "python -m tools.sync_sheets --send"
        confirm_cmd = "python -m tools.sync_sheets --confirm"
        if limit:
            send_cmd += f" --limit {limit}"
            confirm_cmd += f" --limit {limit}"
        print(_c(DIM, f"  Pour envoyer {total} ligne(s) :"))
        print(_c(GREEN, f"    {send_cmd}"))
        print(_c(MAGENTA, f"    {confirm_cmd}  (validation ligne par ligne)\n"))
        return {"sent": 0, "mode": mode, "new_rows": total, "matched": matched}

    # ── Mode confirm (interactif) ────────────────────────────
    if confirm_mode:
        print(_c(MAGENTA + BOLD, "\n  ℹ  Mode confirmation : Entree=envoyer, C=annuler, Q=quitter\n"))
        sent = 0
        skipped = 0
        grid_size = ws.row_count
        for i, (sr, dt) in enumerate(prepared, 1):
            pos = _find_insert_pos(sheet_dates, dt)
            pos = max(2, min(pos, grid_size))
            print(_row_display(i, total, sr) + _c(DIM, f"  → ligne {pos}"))
            try:
                choice = input(_c(DIM, "    [Entree/C/Q] > ")).strip().lower()
            except (EOFError, KeyboardInterrupt):
                print(_c(RED, "\n  Interruption."))
                break
            if choice == "q":
                print(_c(YELLOW, "  Abandon."))
                break
            if choice == "c":
                skipped += 1
                print(_c(RED, "    ✘ Annule"))
                continue
            ws.insert_row(sr, pos, value_input_option="USER_ENTERED")
            sheet_dates = _register_insert(sheet_dates, pos, dt)
            grid_size += 1
            sent += 1
            print(_c(GREEN, f"    ✔ Envoye (ligne {pos})"))

        _sep()
        _stat("Envoyees", str(sent), GREEN)
        _stat("Annulees", str(skipped), RED)
        _stat("Non traitees", str(total - sent - skipped), DIM)
        print()
        return {"sent": sent, "mode": mode, "new_rows": total, "matched": matched}

    # ── Mode auto ────────────────────────────────────────────
    print()
    sent = 0
    grid_size = ws.row_count
    for i, (sr, dt) in enumerate(prepared, 1):
        pos = _find_insert_pos(sheet_dates, dt)
        pos = max(2, min(pos, grid_size))
        ws.insert_row(sr, pos, value_input_option="USER_ENTERED")
        sheet_dates = _register_insert(sheet_dates, pos, dt)
        grid_size += 1
        sent += 1
        print(_c(GREEN, "  ✔") + _row_display(i, total, sr, compact=True) + _c(DIM, f" → L{pos}"))

    _sep()
    print(_c(GREEN + BOLD, f"\n  ✔ {sent} ligne(s) inseree(s) chronologiquement !\n"))
    return {"sent": sent, "mode": mode, "new_rows": total, "matched": matched}


def main():
    p = argparse.ArgumentParser(description="Sync CSV -> Google Sheets (CTO)")
    p.add_argument("--limit", type=int, help="Nombre de lignes a transferer")
    p.add_argument("--dry-run", action="store_true", help="Forcer le mode test (aucune ecriture)")
    p.add_argument("--send", action="store_true", help="Activer l'envoi API en mode auto")
    p.add_argument("--confirm", action="store_true", help="Validation interactive avant chaque envoi")
    p.add_argument("--csv", default=str(CSV_PATH), help="Chemin du CSV")
    args = p.parse_args()

    # Par defaut, le script est en mode test (aucun envoi API).
    mode = "dry-run"
    if args.confirm:
        mode = "confirm"
    elif args.send:
        mode = "send"
    if args.dry_run:
        mode = "dry-run"

    try:
        sync_csv_to_sheet(csv_path=args.csv, mode=mode, limit=args.limit)
    except Exception as e:
        print(_c(RED, f"\n  ✘ Sync error: {e}\n"))
        sys.exit(1)


if __name__ == "__main__":
    main()
