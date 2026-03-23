# Trade Republic Screenshot → CSV Extractor

Extrait automatiquement les données de transactions depuis des captures d'écran Trade Republic en utilisant un modèle de vision (LLM) via l'API OpenRouter.

## Structure du projet

```text
├── main.py                  # Point d'entrée CLI
├── requirements.txt         # Dépendances Python
├── .env                     # Clé API (non versionné)
├── prompts/
│   └── extraction.md        # Prompt d'extraction (modifiable)
├── src/
│   ├── __init__.py
│   ├── models.py            # Dataclass Transaction
│   ├── image.py             # Encodage base64 des images
│   ├── llm.py               # Appel OpenRouter API
│   ├── validation.py        # Validation des données extraites
│   ├── assets.py            # Normalisation des noms d'actifs
│   ├── csv_writer.py        # Déduplication & écriture CSV
│   └── processor.py         # Orchestrateur principal
├── tools/
│   └── sync_sheets.py       # Sync CSV → Google Sheets
├── input/                   # Screenshots à traiter
└── output/                  # CSV généré
```

## Installation

```bash
python -m venv .venv
.venv\Scripts\activate       # Windows
pip install -r requirements.txt
```

## Configuration

Créer un fichier `.env` à la racine :

```bash
OPENROUTER_API_KEY=sk-or-v1-...
```

## Utilisation

```bash
python main.py ./input/
python main.py ./input/ -o output/transactions.csv --delay 1.5
python main.py --test --sync-mode dry-run
```

Par défaut, `main.py` exécute le workflow complet:

1. extraction des images restantes → CSV
2. synchronisation Google Sheets automatique en mode `send`

### Options

- `input_dir`: dossier contenant les screenshots (défaut: `input`)
- `-o, --output`: fichier CSV de sortie (défaut: `output/transactions.csv`)
- `--delay`: délai entre appels API en secondes (défaut: `1.0`)
- `--test`: limite à 1 seul appel LLM (défaut: désactivé)
- `--sync / --no-sync`: active/désactive la sync Sheets après extraction (défaut: `--sync`)
- `--sync-mode`: mode sync (`send`, `dry-run`, `confirm`) (défaut: `send`)
- `--sync-limit`: limite le nombre de lignes envoyées au sheet

## Fonctionnalités

- **Extraction par vision AI** : Qwen3.5-Flash via OpenRouter
- **Déduplication** : évite les doublons (date + heure + actif + montant)
- **Skip des images déjà traitées** : basé sur `source_file` dans le CSV
- **CSV Excel-compatible** : séparateur `;`, encodage UTF-8 BOM
- **Sync Google Sheets intégrée au main** : enchaînement automatique après extraction
- **Prompt modifiable** : éditer `prompts/extraction.md` sans toucher au code
