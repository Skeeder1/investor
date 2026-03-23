# Trade Republic Screenshot -> CSV Extractor

Extrait automatiquement les donnees de transactions depuis des captures d'ecran Trade Republic avec un modele de vision (OpenRouter), ecrit un CSV dedupplique, puis peut synchroniser le resultat vers Google Sheets.

## Structure du projet

```text
├── main.py                  # CLI a sous-commandes: all / extract / sync
├── requirements.txt         # Dependances Python
├── CONFIG.yaml              # Configuration non sensible
├── .env                     # Secrets (non versionne)
├── prompts/
│   └── extraction.md        # Prompt d'extraction
├── src/
│   ├── __init__.py
│   ├── config.py            # Chargement config (CLI > YAML > env > defaults)
│   ├── display.py           # Helpers d'affichage console
│   ├── app/
│   │   ├── extract.py       # Orchestration extraction
│   │   ├── normalize.py     # Orchestration normalisation nom d'actif
│   │   └── sync.py          # Orchestration sync Google Sheets
│   ├── domain/
│   │   ├── models.py        # Dataclass Transaction
│   │   ├── datetime_utils.py
│   │   ├── validation.py
│   │   ├── dedup.py
│   │   └── asset_rules.py
│   └── infra/
│       ├── llm_client.py
│       ├── image_encoder.py
│       ├── csv_store.py
│       └── sheets_client.py
├── input/                   # Screenshots a traiter
└── output/                  # CSV genere
```

## Installation

```bash
python -m venv .venv
.venv\Scripts\activate       # Windows
pip install -r requirements.txt
```

## Configuration

La configuration non sensible est dans CONFIG.yaml:

```yaml
app:
  mode: all
  delay: 1.0
  test: false

paths:
  input_dir: input
  output_csv: output/transactions.csv
  quarantine_dir: output/quarantine

llm:
  model: qwen/qwen3.5-flash-02-23
  max_tokens_vision: 1000
  max_tokens_text: 200
  temperature: 0.0

google_sheets:
  sync_enabled: true
  sync_mode: send
  sync_limit:
  spreadsheet_id: "1edxyVxRjEtYAWVETnV7398yXxCOCs9pyuhJhcuaU3xU"
  sheet_name: "⚪ CTO"
  service_account_path: "~/.config/clef_google/service-account.json"
```

Le secret OPENROUTER_API_KEY doit rester dans l'environnement (ou .env):

```bash
OPENROUTER_API_KEY=sk-or-v1-...
```

Priorite de resolution: CLI > CONFIG.yaml > env > defaults.

## Utilisation

### Workflow complet

```bash
python main.py
python main.py all
python main.py all ./input --delay 1.5 --sync-mode dry-run
```

### Extraction uniquement

```bash
python main.py extract
python main.py extract ./input --test
python main.py extract -o output/transactions.csv --delay 1.2
```

### Synchronisation uniquement

```bash
python main.py sync --mode dry-run
python main.py sync --mode confirm --sync-limit 20
python main.py sync --mode send
```

Compatibilite conservee: lancer sans sous-commande reste equivalent a all.

### Options principales

- all: input_dir, -o/--output, --delay, --test, --sync/--no-sync, --sync-mode, --sync-limit
- extract: input_dir, -o/--output, --delay, --test
- sync: -o/--output, --mode (send|dry-run|confirm), --sync-limit

## Fonctionnalites

- Extraction par vision AI via OpenRouter
- Validation metier + tolerance de coherence numerique
- Deduplication des transactions (date + heure + actif + montant)
- Skip des images deja traitees via source_file dans le CSV
- CSV Excel-compatible: separateur ; et encodage UTF-8 BOM
- Sync Google Sheets avec insertion chronologique
- Contrat de date canonique: YYYY-MM-DD dans le CSV
- Failed en quarantine: les captures failed sont deplacees vers output/quarantine
- Prompt modifiable dans prompts/extraction.md
