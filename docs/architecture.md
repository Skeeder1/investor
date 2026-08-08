# Architecture

Parcours détaillé du pipeline. Chaque affirmation de ce document renvoie au fichier
et, quand c'est utile, à la fonction qui l'implémente.

## Vue d'ensemble

Le programme est une chaîne de transformation à sens unique, sans état partagé entre
modules : chaque étape reçoit une valeur et en renvoie une autre. Le seul état
persistant est le fichier CSV de sortie.

```
main.py            arguments, .env, garde-fous, puis délègue
  └─ processor.process_screenshots()          orchestration + rapport
       ├─ image.encode_image()                fichier      → (base64, MIME)
       ├─ llm.call_openrouter()               image        → dict JSON
       ├─ validation.validate_transaction()   dict         → (Transaction | None, avertissements)
       ├─ assets.normalize_asset_name()       nom d'actif  → (nom retenu, corrigé ?)
       └─ csv_writer.deduplicate_and_write()  Transactions → CSV
```

## Étape par étape

### 1. `main.py` — entrée CLI

Trois responsabilités, toutes exécutées **avant** le moindre appel payant :

1. `truststore.inject_into_ssl()` est appelé **avant** l'import de `src.processor`.
   L'ordre est volontaire : l'injection doit précéder toute création de contexte SSL.
2. La clé `OPENROUTER_API_KEY` est chargée depuis `.env` (python-dotenv) puis lue
   dans l'environnement. Absente, le programme sort en code 1 sans rien appeler.
3. Le CSV de sortie est ouvert en mode append pour vérifier qu'il n'est pas verrouillé
   par un autre programme (Excel, typiquement). En cas de `PermissionError`, le
   programme boucle en affichant la marche à suivre plutôt que d'échouer en fin de
   traitement, après avoir consommé tous les appels API.

### 2. `processor.py` — orchestration

**Sélection des images.** `IMAGE_EXTENSIONS` retient `.png`, `.jpg`, `.jpeg`,
`.webp`, `.heic`. Le dossier est parcouru sans récursion et trié par nom.

**Filtrage des images déjà traitées.** `_load_assets_from_csv()` lit le CSV de sortie
une seule fois et en extrait deux ensembles :

- `processed_files` — l'ensemble des valeurs de la colonne `source_file` ;
- `known_assets` — l'ensemble des valeurs de la colonne `asset_name`.

Ce sont les deux seules formes d'état du programme, et elles proviennent du fichier
de sortie lui-même. Une image dont le nom figure dans `processed_files` est comptée
comme « déjà traitée » et n'est jamais renvoyée à l'API.

**Boucle de traitement.** Chaque image est isolée dans son propre `try`. Deux
familles d'erreurs sont distinguées : `json.JSONDecodeError` (le modèle n'a pas
renvoyé du JSON exploitable) et toute autre exception (réseau, API, fichier). Dans
les deux cas, l'erreur est collectée et la boucle continue.

**Sauvegarde intermédiaire.** Toutes les 10 images, le lot courant est écrit puis la
liste en mémoire est vidée. Une interruption ne coûte donc au plus que 9 extractions.

**Cadence.** `time.sleep(delay)` entre deux images, sauf après la dernière.

**Rapport final.** Avertissements et erreurs sont accumulés pendant toute la boucle
et affichés d'un bloc à la fin, suivis d'un résumé
`ajoutée(s) / doublon(s) / erreur(s) / ignorée(s)`.

> **Effet de bord destructif** — lorsque le modèle renvoie le statut `failed`, le
> fichier image est supprimé du disque (`img_path.unlink()`), sans confirmation. C'est
> le seul endroit du programme qui écrit hors de `output/`.

### 3. `image.py` — encodage

Encodage base64 du fichier et déduction du type MIME depuis l'extension, avec
`image/png` par défaut. Le couple alimente une *data URL* consommée par l'API.

### 4. `llm.py` — client OpenRouter

Deux fonctions, une par usage :

- `call_openrouter(image_b64, mime_type, api_key)` — appel vision. Le prompt est
  chargé depuis `prompts/extraction.md` à chaque appel, `temperature = 0.0`,
  `max_tokens = 1000`, délai d'attente 60 s. La réponse est débarrassée d'éventuelles
  fences Markdown (` ```json `) avant `json.loads`.
- `call_openrouter_text(prompt, api_key)` — appel texte court utilisé par la
  normalisation des noms d'actifs. `max_tokens = 200`, délai d'attente 30 s.

Le transport est `urllib.request` : aucune dépendance HTTP tierce. Le modèle est
figé dans la constante `OPENROUTER_MODEL`.

### 5. `validation.py` — contrôles métier

`validate_transaction(data, filename)` renvoie `(Transaction | None, list[str])`. Elle
ne lève jamais d'exception : une donnée invalide produit `None` et un message.

Contrôles appliqués, dans l'ordre :

| Contrôle | Comportement |
|---|---|
| `status == "not_a_transaction"` | rejet, message `SKIP` |
| `status` hors de `("completed", "executed")` | rejet, message `SKIP` |
| `type` hors de `("buy", "sell", "pea")` | avertissement, repli sur `buy` |
| conversion en `float` des 4 montants | rejet si `ValueError`/`TypeError` |
| `unités × prix + frais ≈ total` (achat)<br>`unités × prix − frais ≈ total` (vente) | avertissement si l'écart relatif dépasse 5 % ; **non appliqué** aux opérations `pea` |
| `confidence == "low"` | avertissement |
| champ `notes` non vide | avertissement |

Le repli sur `buy` en cas de type inconnu est un choix assumé : il produit une ligne
signalée plutôt qu'une perte silencieuse de données.

### 6. `assets.py` — cohérence des libellés

`normalize_asset_name(candidate, known_assets, api_key)` renvoie
`(nom retenu, a été corrigé ?)` et suit un chemin à coût croissant :

1. correspondance exacte dans `known_assets` → retour immédiat, **aucun appel LLM** ;
2. `known_assets` vide (première transaction) → le nom est adopté tel quel ;
3. sinon, un appel texte court soumet le candidat et la liste des noms connus ; le
   modèle répond soit par un nom existant, soit par `NEW`.

Le garde-fou est en sortie : si la réponse ne figure pas **exactement** dans
`known_assets`, elle est ignorée et le candidat conservé. Le modèle ne peut donc
jamais introduire un nom qu'il aurait inventé.

Toute correction effective remonte en avertissement, sous la forme
`FIX fichier: 'ancien' → 'nouveau'`.

### 7. `csv_writer.py` — déduplication et écriture

Clé d'unicité : `(date, time, asset_name, total)`, via `_tx_key()`, qui accepte
indifféremment une `Transaction` ou une ligne de CSV — d'où la conversion du total en
chaîne, pour que les deux origines produisent des clés comparables.

`deduplicate_and_write()` :

1. relit le CSV existant (lignes et clés) ;
2. écarte les doublons **internes au lot** et **vis-à-vis de l'existant** ;
3. si des lignes subsistent, fusionne, trie par `(date, time)` et **réécrit
   intégralement** le fichier.

La réécriture complète est ce qui permet de conserver un fichier trié malgré des
traitements incrémentaux ; elle implique de charger tout le CSV en mémoire, ce qui
reste sans conséquence à cette échelle (quelques milliers de lignes).

Le champ `status` est retiré avant écriture : à ce stade il vaut nécessairement
`completed` ou `executed`, la validation ayant écarté le reste.

### 8. `models.py` — le contrat

`Transaction` est une `dataclass` de 10 champs. Elle constitue la frontière entre
« sortie du modèle, non fiable » et « donnée validée » : rien ne la traverse sans être
passé par `validation.py`.

## Format du CSV

```
sep=;                                              ← directive de séparateur pour Excel
date;time;asset_name;type;asset_price;units;fees;total;source_file
```

Encodage `utf-8-sig` (UTF-8 avec BOM). Les deux détails — ligne `sep=;` et BOM — sont
ce qui permet l'ouverture directe en double-clic sous Excel, accents compris. À la
lecture, le programme saute la première ligne si et seulement si elle commence par
`sep=`, ce qui lui permet de relire aussi bien ses propres fichiers qu'un CSV
dépourvu de cette directive.
