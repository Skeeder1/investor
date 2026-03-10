# Project Guidelines

## Overview

Trade Republic Screenshot → CSV Extractor. Extracts transaction data from Trade Republic app screenshots using AI vision (OpenRouter / Qwen 3.5-Flash) and outputs structured CSV.

## Architecture

```
main.py                    → CLI entry point (argparse, dotenv, truststore)
src/processor.py           → Orchestrator: manifest → encode → LLM → validate → dedup → CSV
src/llm.py                 → OpenRouter API client + prompt loading from prompts/
src/validation.py          → Validates LLM JSON output, cross-checks math (5% tolerance)
src/csv_writer.py          → 2-tier deduplication (batch + existing CSV) + sorted CSV write
src/manifest.py            → SHA-256 image hash manifest (prevents re-processing)
src/image.py               → Base64 encoding + MIME type detection
src/models.py              → Transaction dataclass (10 fields)
prompts/extraction.md      → LLM extraction prompt (editable without code changes)
```

**Data flow**: Screenshots → SHA-256 filter → base64 encode → OpenRouter vision API → JSON parse → validate → deduplicate → CSV

**Two deduplication layers**:
1. **Manifest** (`output/.processed_images.json`): SHA-256 hash prevents re-sending same image to API
2. **CSV key** `(date, time, asset_name, total)`: prevents duplicate rows in output

## Build and Test

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

Run: `python main.py` (defaults: `input/` → `output/transactions.csv`)

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

## Critical Rules

- **⛔ NE JAMAIS exécuter `python main.py` sans `--test`** : chaque run sans `--test` fait N appels LLM payants. Copilot est interdit de lancer le programme complet. Toujours utiliser `python main.py --test` pour valider le code. Seul l'utilisateur lance le programme complet.
- **`--test` = 1 seul appel LLM** : le flag `--test` bride l'exécution à 1 image, peu importe le nombre d'images dans `input/`.
- **Prompt ↔ Code alignment**: The validation in `src/validation.py` must accept ALL statuses the prompt marks as valid (✅). Currently: `"completed"` and `"executed"`. If the prompt changes, update `valid_statuses` in validation.
- **Manifest tracks success only**: Failed API calls must NOT be added to the manifest (allows retry on next run).
- **Never hardcode the API key** — always read from `OPENROUTER_API_KEY` env var via `.env`.
- Keep dependencies minimal — stdlib only where possible (no `requests`, uses `urllib.request`).
