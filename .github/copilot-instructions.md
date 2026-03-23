# Project Guidelines

## Overview

Trade Republic Screenshot → CSV Extractor. Extracts transaction data from Trade Republic app screenshots using AI vision (OpenRouter / Qwen 3.5-Flash) and outputs structured CSV.

## Architecture

```
main.py                    → CLI entry point (argparse, dotenv, truststore)
src/processor.py           → Orchestrator: list images → encode → LLM → validate → dedup → CSV
src/llm.py                 → OpenRouter API client + prompt loading from prompts/
src/validation.py          → Validates LLM JSON output, cross-checks math (5% tolerance)
src/csv_writer.py          → 2-tier deduplication (batch + existing CSV) + sorted CSV write
src/assets.py              → Asset name normalization against known assets
src/image.py               → Base64 encoding + MIME type detection
src/models.py              → Transaction dataclass (10 fields)
prompts/extraction.md      → LLM extraction prompt (editable without code changes)
tools/sync_sheets.py       → Optional CSV → Google Sheets sync utility
convert_HEIC_to_png.py     → Optional HEIC/HEIF preprocessing utility
```

**Data flow**: Screenshots → already-processed filename filter (from CSV `source_file`) → base64 encode → OpenRouter vision API → JSON parse → validate → deduplicate → CSV

**Two deduplication layers**:
1. **Processed filenames from CSV** (`source_file` column): prevents re-sending the same image to API
2. **CSV key** `(date, time, asset_name, total)`: prevents duplicate rows in output

**Checkpoint behavior**:
- Processing is checkpointed every 10 images (`deduplicate_and_write`) to reduce data loss and duplicate processing after interruptions.

## Build and Test

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

Run: `python main.py` (defaults: `input/` → `output/transactions.csv`)

Safe validation run: `python main.py --test` (max 1 image / 1 LLM call)

No automated test suite — test manually with screenshots in `input/`.

## Conventions

- **Language**: French comments/docs, English code identifiers
- **Style**: snake_case functions/modules, PascalCase classes, UPPER_CASE constants
- **Imports**: stdlib → third-party → relative (`from .module import func`)
- **No shared state**: functional approach, each module has a single responsibility
- **Error handling**: validation returns `tuple[Optional[Transaction], list[str]]` — graceful None + warnings, never crashes on bad LLM output
- **Prompt is external**: modify `prompts/extraction.md` to change extraction logic, not Python code
- **CSV format**: `sep=;` header line + UTF-8 BOM (`utf-8-sig`) for Excel compatibility
- **SSL**: `truststore.inject_into_ssl()` required at startup (Windows cert store)
- **Dependencies**: keep dependencies minimal (prefer stdlib; use `urllib.request` over `requests`)

## Critical Rules

- **⛔ NE JAMAIS exécuter `python main.py` sans `--test`** : chaque run sans `--test` fait N appels LLM payants. Copilot est interdit de lancer le programme complet. Toujours utiliser `python main.py --test` pour valider le code. Seul l'utilisateur lance le programme complet.
- **`--test` = 1 seul appel LLM** : le flag `--test` bride l'exécution à 1 image, peu importe le nombre d'images dans `input/`.
- **Prompt ↔ Code alignment**: The validation in `src/validation.py` must accept ALL statuses the prompt marks as valid (✅). Currently: `"completed"` and `"executed"`. If the prompt changes, update `valid_statuses` in validation.
- **Processed-file tracking must reflect success only**: Failed API calls must NOT be recorded in CSV `source_file` tracking (allows retry on next run).
- **Import order safety**: Keep `truststore.inject_into_ssl()` before importing `src.processor` in `main.py`.
- **Never hardcode the API key** — always read from `OPENROUTER_API_KEY` env var via `.env`.

## Reference-First Docs

- Use `README.md` for user-facing setup/usage.
- Use `prompts/extraction.md` as the single source of truth for extraction behavior.
- Link to implementation files instead of duplicating detailed logic in instructions.
