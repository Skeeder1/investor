import argparse
import sys
from collections import Counter
from pathlib import Path
from typing import Optional

import gspread

from ..config import load_configuration, resolve_path_str
from ..display import BOLD, CYAN, DIM, GREEN, MAGENTA, RED, WHITE, YELLOW, c, header, sep, stat
from ..domain.datetime_utils import parse_date_any
from ..domain.dedup import key_from_csv_row
from ..infra.csv_store import read_csv
from ..infra.sheets_client import (
    connect,
    find_insert_position,
    get_all_sheet_data,
    insert_row,
    register_insert,
    to_sheet_row,
)

CSV_PATH = Path(__file__).resolve().parent.parent.parent / "output" / "transactions.csv"


def _relaxed_key_from_exact(exact_key: tuple) -> tuple:
    return (exact_key[0], exact_key[1], exact_key[2])


def _split_new_rows_with_relaxed_match(csv_entries: list[tuple[tuple, dict]], existing: Counter) -> tuple[list[dict], int, int]:
    """Split CSV rows into new rows vs duplicates.

    Matching strategy:
    1) Strict key: (date, asset, total, units)
    2) Relaxed key fallback: (date, asset, total)
    """
    existing_relaxed = Counter()
    for key, count in existing.items():
        existing_relaxed[_relaxed_key_from_exact(key)] += count

    used_exact = Counter()
    used_relaxed = Counter()
    new_rows: list[dict] = []
    matched_exact = 0
    matched_relaxed = 0

    for key, row in csv_entries:
        relaxed_key = _relaxed_key_from_exact(key)
        used_exact[key] += 1
        used_relaxed[relaxed_key] += 1

        if used_exact[key] <= existing.get(key, 0):
            matched_exact += 1
            continue

        if used_relaxed[relaxed_key] <= existing_relaxed.get(relaxed_key, 0):
            matched_relaxed += 1
            continue

        new_rows.append(row)

    return new_rows, matched_exact, matched_relaxed


def _c(color, text):
    return c(text, color)


def _row_display(idx, total, sr, compact=False):
    num = f"[{idx}/{total}]"
    date = _c(CYAN, sr[0])
    tx_type = _c(GREEN, sr[1]) if sr[1] == "Achat" else _c(RED, sr[1])
    compte = _c(MAGENTA, sr[2])
    asset = _c(BOLD + WHITE, sr[3])
    montant = _c(YELLOW, sr[4])
    units = _c(DIM, sr[5])
    if compact:
        return f"  {_c(DIM, num)} {date} {tx_type} {compte} {asset} {montant}"
    return f"  {_c(DIM, num)} {date} | {tx_type} | {compte} | {asset} | {montant} | {units}"


def sync_csv_to_sheet(
    csv_path: str | Path = CSV_PATH,
    mode: str = "dry-run",
    limit: Optional[int] = None,
    spreadsheet_id: Optional[str] = None,
    sheet_name: Optional[str] = None,
    service_account_path: Optional[str | Path] = None,
) -> dict:
    valid_modes = {"send", "dry-run", "confirm"}
    if mode not in valid_modes:
        raise ValueError(f"Mode invalide: {mode} (attendu: {', '.join(sorted(valid_modes))})")

    dry_run = mode == "dry-run"
    confirm_mode = mode == "confirm"
    config_data = load_configuration({}).model_dump()
    gs_cfg = config_data.get("google_sheets", {})

    spreadsheet_id = spreadsheet_id or str(gs_cfg.get("spreadsheet_id", ""))
    sheet_name = sheet_name or str(gs_cfg.get("sheet_name", ""))
    if service_account_path is None:
        service_account_path = resolve_path_str(
            str(gs_cfg.get("service_account_path", "~/.config/clef_google/service-account.json"))
        )
    else:
        service_account_path = Path(service_account_path).expanduser()

    header("SYNC CSV → Google Sheets")

    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV introuvable : {csv_path}")

    rows = read_csv(csv_path)

    if not service_account_path.exists():
        raise FileNotFoundError(f"Service account introuvable : {service_account_path}")

    ss, ws = connect(service_account_path, spreadsheet_id, sheet_name)
    existing, sheet_dates = get_all_sheet_data(ws)

    csv_entries = []
    for row in rows:
        key = key_from_csv_row(row)
        csv_entries.append((key, row))

    new_rows, matched_exact, matched_relaxed = _split_new_rows_with_relaxed_match(csv_entries, existing)
    matched = matched_exact + matched_relaxed

    stat("Spreadsheet", ss.title, CYAN)
    stat("Sheet", sheet_name, CYAN)
    stat("CSV", f"{len(rows)} lignes", WHITE)
    stat("Sheet existant", f"{sum(existing.values())} lignes", WHITE)
    stat("Doublons detectes", str(matched), YELLOW)
    stat("  dont stricts", str(matched_exact), DIM)
    stat("  dont toleres units", str(matched_relaxed), DIM)
    stat("Nouvelles lignes", str(len(new_rows)), GREEN if new_rows else YELLOW)
    stat("Mode", mode, MAGENTA)
    sep()

    if not new_rows:
        print(_c(GREEN + BOLD, "\n  ✔ Rien a synchroniser — le sheet est a jour.\n"))
        return {
            "sent": 0,
            "mode": mode,
            "new_rows": 0,
            "matched": matched,
            "matched_exact": matched_exact,
            "matched_relaxed": matched_relaxed,
        }

    if limit:
        new_rows = new_rows[:limit]
        print(_c(DIM, f"  Limite a {limit} ligne(s)"))

    prepared = []
    for row in new_rows:
        sheet_row = to_sheet_row(row)
        dt = parse_date_any(row["date"])
        prepared.append((sheet_row, dt))
    total = len(prepared)

    if dry_run:
        print(_c(YELLOW + BOLD, "\n  ⚠  Mode dry-run (aucune ecriture)\n"))
        sim_dates = list(sheet_dates)
        for i, (sheet_row, dt) in enumerate(prepared, 1):
            pos = find_insert_position(sim_dates, dt)
            print(_row_display(i, total, sheet_row) + _c(DIM, f"  → ligne {pos}"))
            sim_dates = register_insert(sim_dates, pos, dt)
        sep()
        send_cmd = "python main.py sync --mode send"
        confirm_cmd = "python main.py sync --mode confirm"
        if limit:
            send_cmd += f" --limit {limit}"
            confirm_cmd += f" --limit {limit}"
        print(_c(DIM, f"  Pour envoyer {total} ligne(s) :"))
        print(_c(GREEN, f"    {send_cmd}"))
        print(_c(MAGENTA, f"    {confirm_cmd}  (validation ligne par ligne)\n"))
        return {
            "sent": 0,
            "mode": mode,
            "new_rows": total,
            "matched": matched,
            "matched_exact": matched_exact,
            "matched_relaxed": matched_relaxed,
        }

    if confirm_mode:
        print(_c(MAGENTA + BOLD, "\n  ℹ  Mode confirmation : Entree=envoyer, C=annuler, Q=quitter\n"))
        sent = 0
        skipped = 0
        grid_size = ws.row_count
        for i, (sheet_row, dt) in enumerate(prepared, 1):
            pos = find_insert_position(sheet_dates, dt)
            pos = max(2, min(pos, grid_size))
            print(_row_display(i, total, sheet_row) + _c(DIM, f"  → ligne {pos}"))
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
            insert_row(ws, sheet_row, pos)
            sheet_dates = register_insert(sheet_dates, pos, dt)
            grid_size += 1
            sent += 1
            print(_c(GREEN, f"    ✔ Envoye (ligne {pos})"))

        sep()
        stat("Envoyees", str(sent), GREEN)
        stat("Annulees", str(skipped), RED)
        stat("Non traitees", str(total - sent - skipped), DIM)
        print()
        return {
            "sent": sent,
            "mode": mode,
            "new_rows": total,
            "matched": matched,
            "matched_exact": matched_exact,
            "matched_relaxed": matched_relaxed,
        }

    print()
    sent = 0
    grid_size = ws.row_count
    for i, (sheet_row, dt) in enumerate(prepared, 1):
        pos = find_insert_position(sheet_dates, dt)
        pos = max(2, min(pos, grid_size))
        insert_row(ws, sheet_row, pos)
        sheet_dates = register_insert(sheet_dates, pos, dt)
        grid_size += 1
        sent += 1
        print(_c(GREEN, "  ✔") + _row_display(i, total, sheet_row, compact=True) + _c(DIM, f" → L{pos}"))

    sep()
    print(_c(GREEN + BOLD, f"\n  ✔ {sent} ligne(s) inseree(s) chronologiquement !\n"))
    return {
        "sent": sent,
        "mode": mode,
        "new_rows": total,
        "matched": matched,
        "matched_exact": matched_exact,
        "matched_relaxed": matched_relaxed,
    }


def main():
    parser = argparse.ArgumentParser(description="Sync CSV -> Google Sheets (CTO)")
    parser.add_argument("--limit", type=int, help="Nombre de lignes a transferer")
    parser.add_argument("--dry-run", action="store_true", help="Forcer le mode test (aucune ecriture)")
    parser.add_argument("--send", action="store_true", help="Activer l'envoi API en mode auto")
    parser.add_argument("--confirm", action="store_true", help="Validation interactive avant chaque envoi")
    parser.add_argument("--csv", default=str(CSV_PATH), help="Chemin du CSV")
    parser.add_argument("--spreadsheet-id", help="ID du spreadsheet (prioritaire sur CONFIG.yaml)")
    parser.add_argument("--sheet-name", help="Nom de l'onglet (prioritaire sur CONFIG.yaml)")
    parser.add_argument("--service-account", help="Chemin service account (prioritaire sur CONFIG.yaml)")
    args = parser.parse_args()

    mode = "dry-run"
    if args.confirm:
        mode = "confirm"
    elif args.send:
        mode = "send"
    if args.dry_run:
        mode = "dry-run"

    try:
        sync_csv_to_sheet(
            csv_path=args.csv,
            mode=mode,
            limit=args.limit,
            spreadsheet_id=args.spreadsheet_id,
            sheet_name=args.sheet_name,
            service_account_path=args.service_account,
        )
    except (FileNotFoundError, ValueError, OSError, gspread.exceptions.GSpreadException) as e:
        print(_c(RED, f"\n  ✘ Sync error: {e}\n"))
        sys.exit(1)


if __name__ == "__main__":
    main()
