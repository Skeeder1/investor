# Project Guidelines

## Overview

Trade Republic Screenshot → CSV Extractor. Extrait les données de transactions
depuis des captures d'écran de l'application Trade Republic via un modèle de vision
(OpenRouter / `qwen/qwen3.5-flash-02-23`) et produit un CSV structuré.

Documentation détaillée : [`README.md`](../README.md),
[`docs/architecture.md`](../docs/architecture.md),
[`docs/decisions-techniques.md`](../docs/decisions-techniques.md).

## Architecture

```
main.py                    → Point d'entrée CLI (argparse, dotenv, truststore, verrou CSV)
src/processor.py           → Orchestrateur : filtrage → encodage → LLM → validation → dédup → CSV
src/llm.py                 → Client OpenRouter (vision + texte) + chargement du prompt
src/validation.py          → Valide le JSON du LLM, contrôle arithmétique (tolérance 5 %)
src/assets.py              → Normalisation des noms d'actifs (fuzzy matching par LLM)
src/csv_writer.py          → Déduplication (lot + CSV existant) + écriture triée
src/image.py               → Encodage base64 + détection du type MIME
src/models.py              → Dataclass Transaction (10 champs)
prompts/extraction.md      → Prompt d'extraction (modifiable sans toucher au code)
```

**Flux de données** : captures → filtrage des images déjà traitées → encodage base64
→ API vision OpenRouter → parsing JSON → validation → normalisation du nom d'actif →
déduplication → CSV.

**Le CSV de sortie est l'unique état du programme.** Il n'existe aucun fichier
manifeste séparé. `processor._load_assets_from_csv()` en extrait deux ensembles :

- `processed_files` ← colonne `source_file` : les images déjà traitées, jamais
  renvoyées à l'API ;
- `known_assets` ← colonne `asset_name` : le référentiel de normalisation.

**Deux couches de déduplication**, qui ne protègent pas de la même chose :

1. **Nom de fichier** (`processor.py`) — protège le budget : ne pas payer deux fois
   la même extraction.
2. **Clé métier** `(date, time, asset_name, total)` (`csv_writer.py`) — protège
   l'intégrité : pas de ligne en double, y compris au sein d'un même lot.

## Build and Test

```bash
python3 -m venv .venv
source .venv/bin/activate       # Linux / macOS
# .venv\Scripts\activate        # Windows
pip install -r requirements.txt
cp .env.example .env            # puis renseigner OPENROUTER_API_KEY
```

Lancement : `python main.py` (par défaut `input/` → `output/transactions.csv`).

Aucune suite de tests automatisés. Les couches pures — `validation.py`,
`csv_writer.py`, `assets.py` (chemin de correspondance exacte) — sont testables hors
ligne, sans aucun appel API ni clé.

## Conventions

- **Langue** : commentaires et documentation en français, identifiants de code en anglais
- **Style** : `snake_case` pour fonctions et modules, `PascalCase` pour les classes, `UPPER_CASE` pour les constantes
- **Imports** : bibliothèque standard → tierce → relative (`from .module import func`)
- **Pas d'état partagé** : approche fonctionnelle, une responsabilité par module
- **Gestion d'erreur** : la validation renvoie `tuple[Optional[Transaction], list[str]]` — `None` + avertissements, jamais d'exception sur une sortie LLM invalide
- **Prompt externe** : modifier `prompts/extraction.md` plutôt que le code Python
- **Format CSV** : ligne `sep=;` + UTF-8 BOM (`utf-8-sig`) pour la compatibilité Excel
- **SSL** : `truststore.inject_into_ssl()` doit rester appelé **avant** l'import de `src.processor` dans `main.py`

## Critical Rules

- **⛔ NE JAMAIS exécuter `python main.py` sans `--test`.** Chaque exécution normale
  déclenche un appel LLM payant par image. Toujours utiliser `python main.py --test`
  pour valider une modification. Seul l'utilisateur lance le traitement complet.
- **`--test` limite à 1 image**, quel qu'en soit le nombre dans `input/`. Cela
  représente 1 appel vision, **plus éventuellement 1 appel texte** si le nom d'actif
  extrait est inconnu du CSV (`assets.normalize_asset_name`) — donc jusqu'à 2 appels.
- **Préférer les tests hors ligne.** `validate_transaction`, `deduplicate_and_write` et
  `_load_assets_from_csv` s'exercent avec des dictionnaires et un CSV factices, sans
  aucun appel réseau. Utiliser `--test` seulement lorsque le chemin LLM lui-même est
  en cause.
- **Alignement prompt ↔ code** : `src/validation.py` doit accepter tous les statuts
  que `prompts/extraction.md` marque comme valides (✅). Aujourd'hui `"completed"` et
  `"executed"`. Toute évolution du prompt impose de revoir `valid_statuses`.
- **Effet de bord destructif** : un statut `failed` provoque la **suppression du
  fichier image** (`img_path.unlink()` dans `processor.py`). C'est le seul endroit du
  programme qui écrit hors de `output/`. Ne pas en ajouter d'autre sans nécessité.
- **Ne jamais coder la clé API en dur** — toujours via `OPENROUTER_API_KEY` et `.env`.
- **Garde-fou de la normalisation d'actifs** : la réponse du LLM n'est retenue que si
  elle figure **exactement** dans `known_assets`. Ne pas relâcher ce contrôle, sans
  quoi le modèle pourrait introduire des libellés inventés.
- **Dépendances minimales** — bibliothèque standard autant que possible (pas de
  `requests`, on utilise `urllib.request`).
