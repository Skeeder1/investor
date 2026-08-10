# Plan de restructuration — Projet "investe"

## Contexte

Le projet **investe** extrait des transactions d'investissement depuis des captures d'écran via l'API vision OpenRouter, les écrit en CSV, et les synchronise vers Google Sheets. L'architecture actuelle est un `src/` plat mélangeant domaine, infrastructure et orchestration, avec du code dupliqué (dedup, dates, couleurs ANSI) et aucun test. Ce plan restructure le projet en 3 couches propres (Domaine / Application / Infrastructure) tout en unifiant la logique dupliquée.

---

## Architecture cible

```
investe/
├── .env                              # Secrets uniquement (OPENROUTER_API_KEY)
├── .gitignore
├── CONFIG.yaml                       # Config non-secrets (étendu avec section llm:)
├── README.md                         # Mis à jour avec nouvelles commandes
├── requirements.txt
├── main.py                           # ~80 lignes — CLI unique avec sous-commandes
├── prompts/
│   └── extraction.md                 # Prompt LLM (inchangé)
├── input/
│   └── .gitkeep
├── output/
│   └── transactions.csv
│
├── src/
│   ├── __init__.py
│   ├── config.py                     # Config Pydantic + chargement YAML (+ section LLM)
│   ├── display.py                    # Couleurs ANSI + helpers d'affichage consolidés
│   │
│   ├── domain/                       # Logique pure, aucun I/O
│   │   ├── __init__.py
│   │   ├── models.py                 # Dataclass Transaction (10 champs)
│   │   ├── validation.py             # validate_transaction() → (Transaction | None, warnings)
│   │   ├── dedup.py                  # Clé de dédup unifiée CSV + Sheets
│   │   ├── datetime_utils.py         # Parsing/formatage dates + mois français
│   │   └── asset_rules.py            # map_type, map_compte, format_euro, format_units...
│   │
│   ├── infra/                        # Adaptateurs I/O (1 système externe = 1 fichier)
│   │   ├── __init__.py
│   │   ├── llm_client.py             # Appels API OpenRouter (vision + texte)
│   │   ├── image_encoder.py          # Encodage base64 + IMAGE_EXTENSIONS
│   │   ├── csv_store.py              # Lecture/écriture CSV + dedup
│   │   └── sheets_client.py          # Connexion gspread, lecture/insertion Sheets
│   │
│   └── app/                          # Cas d'usage / orchestration
│       ├── __init__.py
│       ├── extract.py                # Pipeline extraction screenshots
│       ├── sync.py                   # Pipeline sync CSV → Sheets
│       └── normalize.py              # Normalisation fuzzy des noms d'actifs via LLM
│
├── tests/
│   ├── __init__.py
│   ├── test_all.py                   # Runner global
│   ├── unitaires/
│   │   ├── __init__.py
│   │   ├── test_models.py
│   │   ├── test_validation.py
│   │   ├── test_dedup.py
│   │   ├── test_datetime_utils.py
│   │   └── test_asset_rules.py
│   ├── integration/
│   │   ├── __init__.py
│   │   ├── test_csv_store.py
│   │   └── test_extract_pipeline.py
│   └── e2e/
│       ├── __init__.py
│       └── test_full_pipeline.py
│
└── tempo/test/                       # Tests temporaires (cf. CLAUDE.md)
```

---

## Mapping migration : fichier actuel → cible

| Fichier actuel | Fichier(s) cible | Ce qui bouge |
|---|---|---|
| `src/models.py` | `src/domain/models.py` | Déplacement direct |
| `src/validation.py` | `src/domain/validation.py` | Déplacement, mise à jour imports |
| `src/datetime_utils.py` | `src/domain/datetime_utils.py` | + ajout `FRENCH_MONTHS`, `parse_french_date` depuis sync_sheets |
| `src/assets.py` | `src/app/normalize.py` | Déplacement, ajout param `model` |
| `src/image.py` | `src/infra/image_encoder.py` | + ajout `IMAGE_EXTENSIONS` depuis processor |
| `src/llm.py` | `src/infra/llm_client.py` | Suppression model hardcodé, accepte `model` en param |
| `src/csv_writer.py` | `src/infra/csv_store.py` | + merge `read_csv` de sync_sheets + `_load_assets_from_csv` de processor |
| `src/processor.py` | `src/app/extract.py` + `src/display.py` | Orchestration → extract.py, couleurs ANSI → display.py |
| `src/config.py` | `src/config.py` | Reste en place, + ajout `LLMConfigSection` |
| `tools/sync_sheets.py` | `src/app/sync.py` + `src/infra/sheets_client.py` + `src/domain/asset_rules.py` | Éclaté en 3 |
| `tools/_write.py` | **SUPPRIMÉ** | Code mort |
| `tools/__init__.py` | **SUPPRIMÉ** | Dossier tools/ supprimé |
| `main.py` | `main.py` | Réécriture avec sous-commandes |

---

## Contenu détaillé de chaque module

### `src/domain/models.py`
```python
@dataclass Transaction:  # 10 champs: date, time, asset_name, asset_price, units, fees, total, type, status, source_file
```

### `src/domain/dedup.py` — Clé unifiée CSV + Sheets
```python
def transaction_key(date_iso: str, asset_name: str, total: float, units: float) -> tuple
    # Clé canonique: (date_iso, asset_lower, round(total,2), round(units,4))

def key_from_transaction(tx: Transaction) -> tuple
def key_from_csv_row(row: dict) -> tuple
def key_from_sheet_row(date_fr: str, asset: str, montant: float, units: float) -> tuple
    # Convertit date FR → ISO en interne

def deduplicate(new_items: list, existing_keys: Counter) -> list
    # Counter-based pour gérer les doublons légitimes (même actif, même jour, même montant)
```

### `src/domain/datetime_utils.py` — Consolidé
```python
FRENCH_MONTHS: dict[int, str]       # janvier..décembre
FRENCH_MONTHS_REV: dict[str, int]   # inverse

def parse_date_any(value: str) -> datetime
def normalize_date_iso(value: str) -> str
def normalize_time_hhmm(value: str) -> str
def to_french_date_label(value: str) -> str
def parse_french_date(text: str) -> datetime  # "26 mai 2025" → datetime
```

### `src/domain/asset_rules.py` — Règles métier extraites de sync_sheets
```python
def map_type_label(tx_type: str) -> str       # buy/pea→"Achat", sell→"Vente"
def map_compte(tx_type: str, name: str) -> str  # →"CTO"|"PEA"
def map_asset_display(name: str, compte: str) -> str
def format_euro(value: float) -> str          # "2 910,26 €"
def format_units(value: float) -> str         # "0,163213"
def parse_amount(text: str) -> float          # "2 910,26 €" → 2910.26
def parse_units(text: str) -> float           # "0,163213" → 0.163213
```

### `src/domain/validation.py`
```python
def validate_transaction(data: dict, filename: str) -> tuple[Optional[Transaction], list[str]]
```

### `src/infra/llm_client.py`
```python
OPENROUTER_URL: str  # constante
def load_prompt(name: str = "extraction") -> str
def call_vision(image_b64: str, mime_type: str, api_key: str, model: str) -> dict
def call_text(prompt: str, api_key: str, model: str) -> str
```

### `src/infra/image_encoder.py`
```python
IMAGE_EXTENSIONS: set[str]  # {".png", ".jpg", ".jpeg", ".webp", ".heic"}
def encode_image(image_path: str) -> tuple[str, str]
```

### `src/infra/csv_store.py`
```python
FIELDNAMES: list[str]
def read_csv(path: Path) -> list[dict]
def load_known_assets_and_files(path: Path) -> tuple[set[str], set[str]]
def write_csv(rows: list[dict], path: Path) -> None
def deduplicate_and_write(transactions: list[Transaction], output_csv: str) -> tuple[int, int]
```

### `src/infra/sheets_client.py`
```python
SCOPES: list[str]
def connect(sa_path: Path, spreadsheet_id: str, sheet_name: str) -> tuple
def get_all_sheet_data(ws) -> tuple[Counter, list]
def find_insert_position(sheet_dates, new_dt) -> int
def register_insert(sheet_dates, pos, dt) -> list
def insert_row(ws, row: list, pos: int) -> None
def to_sheet_row(row: dict) -> list  # utilise domain.asset_rules
```

### `src/app/extract.py`
```python
def process_screenshots(input_dir, output_csv, api_key, model, delay, test_mode, quarantine_dir) -> dict
```

### `src/app/sync.py`
```python
def sync_csv_to_sheet(csv_path, mode, limit, spreadsheet_id, sheet_name, sa_path) -> dict
```

### `src/app/normalize.py`
```python
def normalize_asset_name(candidate: str, known_assets: set, api_key: str, model: str) -> tuple[str, bool]
```

### `src/display.py`
```python
RESET, BOLD, DIM, GREEN, YELLOW, RED, CYAN, BLUE, MAGENTA: str
def c(text: str, *codes: str) -> str
def header(title: str) -> None
def sep() -> None
def stat(label: str, value: str, color: str) -> None
```

### `main.py` — CLI avec sous-commandes
```
python main.py extract [input_dir] [-o OUTPUT] [--delay SECS] [--test]
python main.py sync [--mode {send,dry-run,confirm}] [--limit N]
python main.py all [options extract + sync]       # ou simplement: python main.py
```
`python main.py` sans sous-commande → défaut `all` (rétrocompatible).

---

## Graphe d'imports (aucune dépendance circulaire)

```
main.py
  → src.config
  → src.app.extract
  │    → src.domain.{models, validation, dedup}
  │    → src.infra.{llm_client, image_encoder, csv_store}
  │    → src.app.normalize → src.infra.llm_client
  │    → src.display
  → src.app.sync
       → src.domain.{dedup, datetime_utils, asset_rules}
       → src.infra.{csv_store, sheets_client}
       → src.display

Règles:
  domain/ → rien d'extérieur au domain
  infra/  → domain/ uniquement
  app/    → domain/ + infra/
  main.py → app/ + config
```

---

## CONFIG.yaml étendu

```yaml
app:
  mode: all
  delay: 1.0
  test: false

paths:
  input_dir: input
  output_csv: output/transactions.csv
  quarantine_dir: output/quarantine

llm:                                    # NOUVELLE SECTION
  model: "qwen/qwen3.5-flash-02-23"
  max_tokens_vision: 1000
  max_tokens_text: 200
  temperature: 0.0

google_sheets:
  sync_enabled: true
  sync_mode: send
  sync_limit: null
  spreadsheet_id: ""
  sheet_name: "⚪ CTO"
  service_account_path: "~/.config/clef_google/service-account.json"
```

`OPENROUTER_API_KEY` reste exclusivement dans `.env` / variable d'environnement.

---

## Phases d'implémentation

### Phase 1 — Fondations (aucun changement de comportement)
- [x] Créer les dossiers: `src/domain/`, `src/infra/`, `src/app/`, `tests/unitaires/`, `tests/integration/`, `tests/e2e/`, `tempo/test/`
- [x] Créer `src/display.py` — extraire couleurs ANSI de processor.py et sync_sheets.py
- [x] Déplacer `src/models.py` → `src/domain/models.py`
- [x] Déplacer `src/datetime_utils.py` → `src/domain/datetime_utils.py` + merger `FRENCH_MONTHS`, `parse_french_date` depuis sync_sheets
- [x] Créer tous les `__init__.py`
- [x] Mettre à jour les imports dans les fichiers qui référencent models et datetime_utils
- [x] Validation : `python main.py --test` fonctionne (arrêt attendu ici car `input/` est vide)

### Phase 2 — Couche Domaine
- [x] Créer `src/domain/dedup.py` avec clé de dédup unifiée
- [x] Créer `src/domain/asset_rules.py` (extraire de sync_sheets.py)
- [x] Déplacer `src/validation.py` → `src/domain/validation.py`
- [x] Mettre à jour tous les imports
- [x] Validation : `python main.py --test` fonctionne (arrêt attendu ici car `input/` est vide)

### Phase 3 — Couche Infrastructure
- [x] Déplacer `src/llm.py` → `src/infra/llm_client.py` (supprimer model hardcodé)
- [x] Déplacer `src/image.py` → `src/infra/image_encoder.py` (+ IMAGE_EXTENSIONS)
- [x] Créer `src/infra/csv_store.py` (merger csv_writer + read_csv + _load_assets_from_csv)
- [x] Créer `src/infra/sheets_client.py` (extraire I/O gspread de sync_sheets.py)
- [x] Ajouter `LLMConfigSection` dans `src/config.py`
- [x] Mettre à jour CONFIG.yaml avec la section `llm:`
- [x] Validation : `python main.py --test` fonctionne (arrêt attendu ici car `input/` est vide)

### Phase 4 — Couche Application
- [x] Créer `src/app/extract.py` depuis processor.py (orchestration seule)
- [x] Créer `src/app/sync.py` depuis sync_sheets.py (orchestration seule)
- [x] Déplacer `src/assets.py` → `src/app/normalize.py` (+ param model)
- [x] Validation : `python main.py --test` et `python main.py --mode sync --sync-mode dry-run`
  Résultat actuel: extraction stop attendue car `input/` est vide; sync dry-run OK (équivalent CLI phase 5: `python main.py sync --mode dry-run`).

### Phase 5 — CLI et nettoyage
- [x] Réécrire `main.py` avec sous-commandes (extract/sync/all)
- [x] Supprimer `tools/_write.py`, `tools/sync_sheets.py`, `tools/__init__.py`
- [x] Supprimer les anciens fichiers `src/` déplacés (processor.py, csv_writer.py, image.py, llm.py, assets.py, models.py, validation.py, datetime_utils.py)
- [x] Supprimer le dossier `tools/`
- [x] Mettre à jour README.md avec nouvelles commandes et structure
- [x] Vérifier qu'aucun import cassé ne subsiste (`python -c "from src.app.extract import process_screenshots; from src.app.sync import sync_csv_to_sheet"`)
  Vérification effectuée via `python -c "import src.domain.models; import src.infra.llm_client; import src.app.extract; import src.app.sync"` + `python -m compileall src`.
- [x] **Validation** : pipeline complet `python main.py extract --test` puis `python main.py sync --mode dry-run`
  Résultat actuel: extract s'arrête car `input/` est vide (attendu ici), sync dry-run OK.

### Phase 6 — Tests
- [x] Créer `tests/test_all.py` (runner pytest)
- [x] `tests/unitaires/test_models.py` — instanciation Transaction
- [x] `tests/unitaires/test_validation.py` — cas valides, invalides, edge cases
- [x] `tests/unitaires/test_dedup.py` — clé unifiée, dédup avec Counter
- [x] `tests/unitaires/test_datetime_utils.py` — parsing toutes les variantes de dates
- [x] `tests/unitaires/test_asset_rules.py` — map_type, map_compte, format_euro, parse_amount
- [x] `tests/integration/test_csv_store.py` — cycle lecture/écriture/dedup avec fichiers temp
- [x] `tests/integration/test_extract_pipeline.py` — mock LLM, test encode→validate→dedup→write
- [x] `tests/e2e/test_full_pipeline.py` — pipeline complet avec fixture
- [x] **Validation** : `python tests/test_all.py` — tous les tests passent

---

## Vérification finale

- [ ] `python main.py extract --test` → extrait 1 image, écrit CSV
- [x] `python main.py sync --mode dry-run` → affiche les lignes à envoyer sans modifier Sheets
- [x] `python main.py` (sans args) → mode `all` par défaut, rétrocompatible
- [x] `python tests/test_all.py` → tous les tests verts
- [x] Aucun import cassé : `python -c "import src.domain.models; import src.infra.llm_client; import src.app.extract; import src.app.sync"`
- [x] Aucun fichier orphelin dans `src/` (les anciens fichiers sont supprimés)
- [x] `tools/` n'existe plus
- [x] CONFIG.yaml contient la section `llm:` et est cohérent avec le code
