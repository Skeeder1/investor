"""
Trade Republic Screenshot → CSV Extractor
==========================================
Extrait les données de transactions depuis des captures d'écran Trade Republic
en utilisant l'API OpenRouter (modèle Qwen3.5-Flash vision).

Usage:
    python main.py
    python main.py ./input/
    python main.py ./input/ -o output/transactions.csv
    python main.py --test          # 1 seul appel LLM (pour tests)
"""

import argparse
import os
import sys
import time
from pathlib import Path

import truststore
from dotenv import load_dotenv

truststore.inject_into_ssl()

from src.processor import process_screenshots


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Extract Trade Republic transactions from screenshots"
    )
    parser.add_argument("input_dir", nargs="?", default="input", help="Directory containing screenshots (default: input)")
    parser.add_argument("-o", "--output", default="output/transactions.csv", help="Output CSV file")
    parser.add_argument(
        "--delay", type=float, default=1.0,
        help="Delay between API calls in seconds (default: 1.0)"
    )
    parser.add_argument(
        "--test", action="store_true",
        help="Mode test : limite à 1 seul appel LLM (évite les coûts)"
    )
    args = parser.parse_args()

    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        print("Error: No API key. Set OPENROUTER_API_KEY in .env file.")
        sys.exit(1)

    # Vérifier que le CSV n'est pas ouvert (ex: Excel)
    csv_path = Path(args.output)
    if csv_path.exists():
        warned = False
        while True:
            try:
                with open(csv_path, "a", encoding="utf-8-sig"):
                    break
            except PermissionError:
                if not warned:
                    print(f"\033[33m⚠️  Le fichier est ouvert par un autre programme : {args.output}\033[0m")
                    print("\033[33m   Fermez-le puis appuyez sur Entrée, ou attendez...\033[0m")
                    warned = True
                time.sleep(1)

    if args.test:
        print("⚠️  Mode test activé — 1 seul appel LLM.")

    process_screenshots(
        input_dir=args.input_dir,
        output_csv=args.output,
        api_key=api_key,
        delay=args.delay,
        test_mode=args.test,
    )


if __name__ == "__main__":
    main()
