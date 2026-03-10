# Trade Republic Screenshot → CSV Extractor

Extrait automatiquement les données de transactions depuis des captures d'écran Trade Republic en utilisant un modèle de vision (LLM) via l'API OpenRouter.

## Structure du projet

```
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
│   ├── manifest.py          # Manifest SHA-256 (évite le re-traitement)
│   ├── csv_writer.py        # Déduplication & écriture CSV
│   └── processor.py         # Orchestrateur principal
├── input/                   # Screenshots à traiter
└── output/                  # CSV généré + manifest
```

## Installation

```bash
python -m venv .venv
.venv\Scripts\activate       # Windows
pip install -r requirements.txt
```

## Configuration

Créer un fichier `.env` à la racine :

```
OPENROUTER_API_KEY=sk-or-v1-...
```

## Utilisation

```bash
python main.py ./input/
python main.py ./input/ -o output/transactions.csv --delay 1.5
```

### Options

| Argument       | Description                          | Défaut                     |
|----------------|--------------------------------------|----------------------------|
| `input_dir`    | Dossier contenant les screenshots    | *(obligatoire)*            |
| `-o, --output` | Fichier CSV de sortie                | `output/transactions.csv`  |
| `--delay`      | Délai entre appels API (secondes)    | `1.0`                      |

## Fonctionnalités

- **Extraction par vision AI** : Qwen3.5-Flash via OpenRouter
- **Déduplication** : évite les doublons (date + heure + actif + montant)
- **Manifest d'images** : SHA-256, ne re-traite jamais la même image
- **CSV Excel-compatible** : séparateur `;`, encodage UTF-8 BOM
- **Prompt modifiable** : éditer `prompts/extraction.md` sans toucher au code
