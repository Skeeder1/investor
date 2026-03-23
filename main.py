"""
Trade Republic Screenshot -> CSV Extractor
==========================================
Extrait les données de transactions depuis des captures d'écran Trade Republic
en utilisant l'API OpenRouter.

Usage:
    python main.py
    python main.py ./input/
    python main.py --test
"""

import argparse
import sys
import time

import truststore
from dotenv import load_dotenv

truststore.inject_into_ssl()

from src.app.extract import process_screenshots
from src.app.sync import sync_csv_to_sheet
from src.config import load_configuration, resolve_path_str


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Extract Trade Republic transactions from screenshots"
    )
    subparsers = parser.add_subparsers(dest="command")

    def add_extract_options(cmd_parser: argparse.ArgumentParser, include_sync_options: bool) -> None:
        cmd_parser.add_argument("input_dir", nargs="?", default=None, help="Directory containing screenshots")
        cmd_parser.add_argument("-o", "--output", default=None, help="Output CSV file")
        cmd_parser.add_argument("--delay", type=float, default=None, help="Delay between API calls in seconds")
        cmd_parser.add_argument("--test", action="store_true", help="Mode test : limite a 1 seul appel LLM")
        if include_sync_options:
            cmd_parser.add_argument("--sync", dest="sync", action="store_true", default=None, help="Activer sync Google Sheets")
            cmd_parser.add_argument("--no-sync", dest="sync", action="store_false", help="Desactiver sync Google Sheets")
            cmd_parser.add_argument("--sync-mode", choices=("send", "dry-run", "confirm"), default=None, help="Mode de sync")
            cmd_parser.add_argument("--sync-limit", type=int, help="Limiter les lignes")

    parser_all = subparsers.add_parser("all", help="Extraction puis sync (workflow complet)")
    add_extract_options(parser_all, include_sync_options=True)

    parser_extract = subparsers.add_parser("extract", help="Extraction uniquement")
    add_extract_options(parser_extract, include_sync_options=False)

    parser_sync = subparsers.add_parser("sync", help="Synchronisation Google Sheets uniquement")
    parser_sync.add_argument("-o", "--output", default=None, help="CSV a synchroniser")
    parser_sync.add_argument("--mode", dest="sync_mode", choices=("send", "dry-run", "confirm"), default=None, help="Mode de sync")
    parser_sync.add_argument("--sync-limit", type=int, help="Limiter les lignes")

    argv = sys.argv[1:]
    if not argv or argv[0].startswith("-") or argv[0] not in {"all", "extract", "sync"}:
        argv = ["all", *argv]

    args = parser.parse_args(argv)

    cli_args: dict = {}
    if getattr(args, "input_dir", None) is not None:
        cli_args["input_dir"] = args.input_dir
    if getattr(args, "output", None) is not None:
        cli_args["output"] = args.output
    if getattr(args, "delay", None) is not None:
        cli_args["delay"] = args.delay
    if getattr(args, "test", False):
        cli_args["test"] = True
    if hasattr(args, "sync") and args.sync is not None:
        cli_args["sync"] = args.sync
    if getattr(args, "sync_mode", None) is not None:
        cli_args["sync_mode"] = args.sync_mode
    if getattr(args, "sync_limit", None) is not None:
        cli_args["sync_limit"] = args.sync_limit

    cli_args["mode"] = args.command

    config = load_configuration(cli_args)

    run_extract = config.app.mode in ("all", "extract")
    run_sync = config.app.mode in ("all", "sync")

    if not config.google_sheets.sync_enabled:
        run_sync = False
    if config.google_sheets.sync_enabled and config.app.mode == "extract":
        run_sync = False

    # Verifier que le CSV n'est pas ouvert (ex: Excel) uniquement si extraction active
    csv_path = resolve_path_str(config.paths.output_csv)
    if run_extract and csv_path.exists():
        warned = False
        while True:
            try:
                with open(csv_path, "a", encoding="utf-8-sig"):
                    break
            except PermissionError:
                if not warned:
                    print(f"\033[33m⚠️ Le fichier est ouvert par un autre programme : {csv_path}\033[0m")
                    print("\033[33m   Fermez-le puis appuyez sur Entrée, ou attendez...\033[0m")
                    warned = True
                time.sleep(1)

    if run_extract:
        if not config.openrouter_api_key:
            print("Error: No API key. Set OPENROUTER_API_KEY in .env file.")
            sys.exit(3)

        if config.app.test:
            print("⚠️ Mode test activé — 1 seul appel LLM.")

        process_screenshots(
            input_dir=str(resolve_path_str(config.paths.input_dir)),
            output_csv=str(csv_path),
            api_key=config.openrouter_api_key,
            model=config.llm.model,
            delay=config.app.delay,
            test_mode=config.app.test,
            quarantine_dir=str(resolve_path_str(config.paths.quarantine_dir)),
        )

    if not run_sync:
        if config.app.mode == "sync":
            print("\nℹ️ Synchronisation desactivee par config ou --no-sync.")
        else:
            print("\nℹ️ Synchronisation Google Sheets desactivee.")
        return

    print(f"\n📤 Synchronisation Google Sheets (mode={config.google_sheets.sync_mode})...")
    try:
        result = sync_csv_to_sheet(
            csv_path=str(csv_path),
            mode=config.google_sheets.sync_mode,
            limit=config.google_sheets.sync_limit,
            spreadsheet_id=config.google_sheets.spreadsheet_id,
            sheet_name=config.google_sheets.sheet_name,
            service_account_path=resolve_path_str(config.google_sheets.service_account_path),
        )
        sent = result.get("sent", 0)
        print(f"✅ Synchronisation terminee ({sent} ligne(s) envoyee(s)).")
    except (ImportError, FileNotFoundError, ValueError, OSError) as e:
        print(f"⚠️ Sync Sheets echouee (non bloquant): {e}")

if __name__ == "__main__":
    main()
