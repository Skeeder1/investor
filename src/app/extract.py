import json
import shutil
import sys
import time
from pathlib import Path

from ..display import BOLD, CYAN, DIM, GREEN, MAGENTA, RED, YELLOW, c
from ..domain.models import Transaction
from ..domain.validation import validate_transaction
from ..infra.csv_store import deduplicate_and_write, load_known_assets_and_files
from ..infra.image_encoder import IMAGE_EXTENSIONS, encode_image
from ..infra.llm_client import call_vision
from .normalize import normalize_asset_name


def process_screenshots(
    input_dir: str,
    output_csv: str,
    api_key: str = "",
    model: str = "qwen/qwen3.5-flash-02-23",
    delay: float = 1.0,
    test_mode: bool = False,
    quarantine_dir: str | None = None,
):
    """Process all screenshots in a directory."""
    input_path = Path(input_dir)
    images = sorted([f for f in input_path.iterdir() if f.suffix.lower() in IMAGE_EXTENSIONS])

    if not images:
        print(c(f"Aucune image trouvée dans {input_dir}", RED, BOLD))
        sys.exit(1)

    output_dir = Path(output_csv).parent
    output_dir.mkdir(parents=True, exist_ok=True)

    known_assets, processed_files = load_known_assets_and_files(Path(output_csv))

    new_images: list[Path] = []
    already_done = 0
    for img in images:
        if img.name in processed_files:
            already_done += 1
        else:
            new_images.append(img)

    print(c("─" * 60, DIM))
    print(f"  {c('Images totales', BOLD)}  : {c(len(images), CYAN)}")
    print(f"  {c('Déjà traitées', BOLD)}  : {c(already_done, DIM)}")
    print(f"  {c('À traiter     ', BOLD)}  : {c(len(new_images), CYAN, BOLD)}")
    print(f"  {c('Modèle        ', BOLD)}  : {c(model, DIM)}")
    print(f"  {c('Sortie        ', BOLD)}  : {c(output_csv, DIM)}")
    print(c("─" * 60, DIM))

    if not new_images:
        print(c("\n✅ Rien à faire — toutes les images ont déjà été traitées.", GREEN))
        return

    if test_mode:
        new_images = new_images[:1]
        print(c("⚠️  Mode test — limité à 1 image.", YELLOW))

    quarantine_path = Path(quarantine_dir) if quarantine_dir else None
    if quarantine_path:
        quarantine_path.mkdir(parents=True, exist_ok=True)

    transactions: list[Transaction] = []
    all_warnings: list[str] = []
    errors: list[str] = []
    skip_count = 0
    total_new = 0
    total_dup = 0

    for i, img_path in enumerate(new_images, 1):
        prefix = c(f"[{i}/{len(new_images)}]", DIM)
        name = c(img_path.name, BOLD)
        print(f"{prefix} {name} ...", end=" ", flush=True)

        try:
            img_b64, mime_type = encode_image(str(img_path))
            data = call_vision(img_b64, mime_type, api_key, model)

            tx, warnings = validate_transaction(data, img_path.name)
            all_warnings.extend(warnings)

            if tx:
                final_name, was_corrected = normalize_asset_name(
                    tx.asset_name, known_assets, api_key, model=model
                )
                if was_corrected:
                    all_warnings.append(f"FIX {img_path.name}: '{tx.asset_name}' → '{final_name}'")
                    tx = Transaction(
                        date=tx.date,
                        time=tx.time,
                        asset_name=final_name,
                        asset_price=tx.asset_price,
                        units=tx.units,
                        fees=tx.fees,
                        total=tx.total,
                        type=tx.type,
                        status=tx.status,
                        source_file=tx.source_file,
                    )

                known_assets.add(tx.asset_name)
                transactions.append(tx)
                type_label = {
                    "buy": c("BUY", GREEN, BOLD),
                    "sell": c("SELL", RED, BOLD),
                    "pea": c("PEA", MAGENTA, BOLD),
                }.get(tx.type, c(tx.type.upper(), CYAN, BOLD))
                print(f"{c('OK', GREEN)} {type_label} {c(tx.total, BOLD)}€  {c(tx.asset_name, CYAN)}")
            else:
                skip_count += 1
                reason = warnings[0].split(': ', 1)[1] if warnings else 'unknown'
                print(f"{c('SKIP', YELLOW)}  {c(reason, DIM)}")
                if data.get("status") == "failed" and quarantine_path:
                    target = quarantine_path / img_path.name
                    suffix = 1
                    while target.exists():
                        target = quarantine_path / f"{img_path.stem}_{suffix}{img_path.suffix}"
                        suffix += 1
                    shutil.move(str(img_path), str(target))
                    print(f"  {c('!', YELLOW)} {img_path.name} deplacee vers quarantine")

        except json.JSONDecodeError as e:
            errors.append(f"ERROR {img_path.name}: LLM returned invalid JSON - {e}")
            print(c("JSON ERROR", RED, BOLD))

        except (OSError, ValueError, RuntimeError) as e:
            errors.append(f"ERROR {img_path.name}: {e}")
            print(c(f"ERROR: {e}", RED))

        if i % 10 == 0 and transactions:
            checkpoint_count, checkpoint_dup = deduplicate_and_write(transactions, output_csv)
            total_new += checkpoint_count
            total_dup += checkpoint_dup
            transactions.clear()
            print(c(f"  ──  checkpoint: {checkpoint_count} transaction(s) sauvegardée(s)  ──", DIM))

        if i < len(new_images):
            time.sleep(delay)

    print(c("─" * 60, DIM))

    last_new, last_dup = deduplicate_and_write(transactions, output_csv)
    total_new += last_new
    total_dup += last_dup

    if total_new:
        print(c(f"\n✅  {total_new} transaction(s) ajoutée(s) → {output_csv}", GREEN, BOLD))
    elif total_new == 0 and skip_count == 0 and not errors:
        print(c("\n⚠️   Aucune transaction valide trouvée", YELLOW))
    else:
        print(c("\n⚠️   Aucune nouvelle transaction (toutes déjà présentes)", YELLOW))

    if total_dup:
        print(c(f"⏭️   {total_dup} doublon(s) ignoré(s)", DIM))

    if all_warnings:
        print(f"\n{c(f'⚠️  Avertissements ({len(all_warnings)})', YELLOW, BOLD)}")
        for warning in all_warnings:
            print(f"  {c(warning, YELLOW)}")

    if errors:
        print(f"\n{c(f'❌  Erreurs ({len(errors)})', RED, BOLD)}")
        for err in errors:
            print(f"  {c(err, RED)}")

    parts = [
        c(f"{total_new} ajoutée(s)", GREEN if total_new else DIM),
        c(f"{total_dup} doublon(s)", DIM),
        c(f"{len(errors)} erreur(s)", RED if errors else DIM),
        c(f"{skip_count} ignorée(s)", YELLOW if skip_count else DIM),
    ]
    print(f"\n{c('Résumé', BOLD)}  {'  /  '.join(parts)}")
