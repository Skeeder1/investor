import json
import sys
import time
from pathlib import Path

from .assets import normalize_asset_name
from .csv_writer import deduplicate_and_write
from .image import encode_image
from .llm import OPENROUTER_MODEL, call_openrouter
from .models import Transaction
from .validation import validate_transaction

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".heic"}

# ─── ANSI color helpers ───────────────────────────────────────────────────────
_RESET  = "\033[0m"
_BOLD   = "\033[1m"
_DIM    = "\033[2m"
_GREEN  = "\033[32m"
_YELLOW = "\033[33m"
_RED    = "\033[31m"
_CYAN   = "\033[36m"
_BLUE   = "\033[34m"
_MAGENTA= "\033[35m"

def _c(text: str, *codes: str) -> str:
    return "".join(codes) + str(text) + _RESET


def _load_assets_from_csv(output_csv: str) -> tuple[set[str], set[str]]:
    """Extract unique asset names and processed image filenames from the CSV (in RAM).

    Returns (known_assets, processed_filenames).
    """
    import csv
    csv_path = Path(output_csv)
    if not csv_path.exists():
        return set(), set()
    with open(csv_path, "r", newline="", encoding="utf-8-sig") as f:
        first = f.readline()
        if not first.startswith("sep="):
            f.seek(0)
        reader = csv.DictReader(f, delimiter=";")
        known_assets: set[str] = set()
        processed_files: set[str] = set()
        for row in reader:
            if row.get("asset_name"):
                known_assets.add(row["asset_name"])
            if row.get("source_file"):
                processed_files.add(row["source_file"])
    return known_assets, processed_files


def process_screenshots(
    input_dir: str,
    output_csv: str,
    api_key: str = "",
    delay: float = 1.0,
    test_mode: bool = False,
):
    """Process all screenshots in a directory."""
    input_path = Path(input_dir)
    images = sorted([
        f for f in input_path.iterdir()
        if f.suffix.lower() in IMAGE_EXTENSIONS
    ])

    if not images:
        print(_c(f"Aucune image trouvée dans {input_dir}", _RED, _BOLD))
        sys.exit(1)

    # Ensure output directory exists
    output_dir = Path(output_csv).parent
    output_dir.mkdir(parents=True, exist_ok=True)

    # ─── Load known assets + processed filenames from CSV (in RAM) ────────
    known_assets, processed_files = _load_assets_from_csv(output_csv)

    new_images: list[Path] = []
    already_done = 0
    for img in images:
        if img.name in processed_files:
            already_done += 1
        else:
            new_images.append(img)

    print(_c("─" * 60, _DIM))
    print(f"  {_c('Images totales', _BOLD)}  : {_c(len(images), _CYAN)}")
    print(f"  {_c('Déjà traitées', _BOLD)}  : {_c(already_done, _DIM)}")
    print(f"  {_c('À traiter     ', _BOLD)}  : {_c(len(new_images), _CYAN, _BOLD)}")
    print(f"  {_c('Modèle        ', _BOLD)}  : {_c(OPENROUTER_MODEL, _DIM)}")
    print(f"  {_c('Sortie        ', _BOLD)}  : {_c(output_csv, _DIM)}")
    print(_c("─" * 60, _DIM))

    if not new_images:
        print(_c("\n✅ Rien à faire — toutes les images ont déjà été traitées.", _GREEN))
        return

    if test_mode:
        new_images = new_images[:1]
        print(_c("⚠️  Mode test — limité à 1 image.", _YELLOW))

    # ─── Process new images ───────────────────────────────────────────────
    transactions: list[Transaction] = []
    all_warnings: list[str] = []
    errors: list[str] = []
    skip_count = 0
    total_new = 0
    total_dup = 0

    for i, img_path in enumerate(new_images, 1):
        prefix = _c(f"[{i}/{len(new_images)}]", _DIM)
        name   = _c(img_path.name, _BOLD)
        print(f"{prefix} {name} ...", end=" ", flush=True)

        try:
            img_b64, mime_type = encode_image(str(img_path))
            data = call_openrouter(img_b64, mime_type, api_key)

            tx, warnings = validate_transaction(data, img_path.name)
            all_warnings.extend(warnings)

            if tx:
                # Normalize asset name against known registry
                final_name, was_corrected = normalize_asset_name(
                    tx.asset_name, known_assets, api_key
                )
                if was_corrected:
                    all_warnings.append(
                        f"FIX {img_path.name}: '{tx.asset_name}' → '{final_name}'"
                    )
                    tx = Transaction(
                        date=tx.date, time=tx.time, asset_name=final_name,
                        asset_price=tx.asset_price, units=tx.units, fees=tx.fees,
                        total=tx.total, type=tx.type, status=tx.status,
                        source_file=tx.source_file,
                    )
                known_assets.add(tx.asset_name)
                transactions.append(tx)
                type_label = {"buy": _c("BUY", _GREEN, _BOLD), "sell": _c("SELL", _RED, _BOLD), "pea": _c("PEA", _MAGENTA, _BOLD)}.get(tx.type, _c(tx.type.upper(), _CYAN, _BOLD))
                print(f"{_c('OK', _GREEN)} {type_label} {_c(tx.total, _BOLD)}€  {_c(tx.asset_name, _CYAN)}")
            else:
                skip_count += 1
                reason = warnings[0].split(': ', 1)[1] if warnings else 'unknown'
                print(f"{_c('SKIP', _YELLOW)}  {_c(reason, _DIM)}")
                if data.get("status") == "failed":
                    img_path.unlink()
                    print(f"  {_c('🗑', _RED)} {img_path.name} supprimée (transaction échouée)")

        except json.JSONDecodeError as e:
            err = f"ERROR {img_path.name}: LLM returned invalid JSON - {e}"
            errors.append(err)
            print(_c("JSON ERROR", _RED, _BOLD))

        except Exception as e:
            err = f"ERROR {img_path.name}: {e}"
            errors.append(err)
            print(_c(f"ERROR: {e}", _RED))

        # Checkpoint toutes les 10 images
        if i % 10 == 0 and transactions:
            checkpoint_count, checkpoint_dup = deduplicate_and_write(transactions, output_csv)
            total_new += checkpoint_count
            total_dup += checkpoint_dup
            transactions.clear()
            print(_c(f"  ──  checkpoint: {checkpoint_count} transaction(s) sauvegardée(s)  ──", _DIM))

        # Rate limiting
        if i < len(new_images):
            time.sleep(delay)

    # ─── Deduplication & CSV write ────────────────────────────────────────
    print(_c("─" * 60, _DIM))

    last_new, last_dup = deduplicate_and_write(transactions, output_csv)
    total_new += last_new
    total_dup += last_dup

    if total_new:
        print(_c(f"\n✅  {total_new} transaction(s) ajoutée(s) → {output_csv}", _GREEN, _BOLD))
    elif total_new == 0 and skip_count == 0 and not errors:
        print(_c("\n⚠️   Aucune transaction valide trouvée", _YELLOW))
    else:
        print(_c("\n⚠️   Aucune nouvelle transaction (toutes déjà présentes)", _YELLOW))

    # ─── Report ───────────────────────────────────────────────────────────
    if total_dup:
        print(_c(f"⏭️   {total_dup} doublon(s) ignoré(s)", _DIM))

    if all_warnings:
        print(f"\n{_c(f'⚠️  Avertissements ({len(all_warnings)})', _YELLOW, _BOLD)}")
        for w in all_warnings:
            print(f"  {_c(w, _YELLOW)}")

    if errors:
        print(f"\n{_c(f'❌  Erreurs ({len(errors)})', _RED, _BOLD)}")
        for e in errors:
            print(f"  {_c(e, _RED)}")

    # Summary
    parts = [
        _c(f"{total_new} ajoutée(s)", _GREEN if total_new else _DIM),
        _c(f"{total_dup} doublon(s)", _DIM),
        _c(f"{len(errors)} erreur(s)", _RED if errors else _DIM),
        _c(f"{skip_count} ignorée(s)", _YELLOW if skip_count else _DIM),
    ]
    print(f"\n{_c('Résumé', _BOLD)}  {'  /  '.join(parts)}")
