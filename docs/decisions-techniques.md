# Décisions techniques

Chaque décision est présentée avec l'alternative écartée et le coût accepté. Les
décisions sont reconstituées à partir du code : elles décrivent l'état actuel du
projet et ce qu'il implique, pas une chronologie de développement.

---

## 1. Le prompt est un fichier, pas une chaîne de caractères

**Décision.** `prompts/extraction.md` est lu à l'exécution par `llm.load_prompt()`.

**Pourquoi.** C'est l'élément le plus volatil du projet : toute évolution de
l'interface Trade Republic se corrige dans le prompt, jamais dans le code. Séparer ce
qui change souvent de ce qui change peu permet d'itérer sans risque de régression, et
rend le prompt lisible et versionnable comme un document.

**Écarté.** Prompt en constante Python — chaque ajustement devient une modification de
code, et le prompt de 74 lignes devient illisible noyé dans un module.

**Coût.** Un couplage implicite à surveiller : les statuts déclarés valides dans le
prompt doivent rester alignés sur `valid_statuses` dans `src/validation.py`
(aujourd'hui `completed` et `executed`). Rien ne le vérifie automatiquement.

---

## 2. Le CSV de sortie sert d'état

**Décision.** Aucun fichier d'état séparé. La colonne `source_file` tient lieu de
registre des images traitées, la colonne `asset_name` de référentiel des actifs.

**Pourquoi.** L'information est déjà dans la sortie. Un fichier d'état séparé
introduirait une seconde source de vérité, donc un risque permanent de désynchronisation
— un CSV supprimé et un manifeste conservé donneraient un programme convaincu d'avoir
déjà tout traité, pour un fichier vide.

**Écarté.** Manifeste d'empreintes SHA-256 dans un JSON dédié. Plus robuste sur le
plan de l'identification (immunisé au renommage), mais deux fichiers à garder
cohérents.

**Coût.** Deux angles morts, tous deux documentés en *Limites* du README :

- une capture renommée est renvoyée à l'API (le doublon est bloqué en aval, l'appel
  est facturé) ;
- une capture qui ne produit aucune ligne — `rejected`, `pending`, écran non
  transactionnel — n'entre jamais dans `source_file` et repart à l'API à chaque
  exécution.

---

## 3. Deux couches de déduplication distinctes

**Décision.** Un filtre par nom de fichier en amont (`processor.py`), un filtre par
clé métier en aval (`csv_writer.py`).

**Pourquoi.** Les deux ne protègent pas de la même chose. Le premier protège le
**budget** : ne pas payer deux fois la même extraction. Le second protège
l'**intégrité** : deux captures différentes du même écran, ou une même transaction
photographiée deux fois, ne doivent produire qu'une ligne. Supprimer l'un ou l'autre
laisse un trou distinct.

**Clé métier retenue.** `(date, time, asset_name, total)`. L'horodatage à la minute
combiné au montant rend une collision légitime très improbable ; y ajouter `units` ou
`asset_price` fragiliserait la clé en la rendant sensible aux écarts d'arrondi de
lecture.

**Coût.** La déduplication interne au lot et celle vis-à-vis de l'existant partagent
la même fonction `_tx_key()`, qui doit donc accepter deux types d'entrée
(`Transaction` et ligne de CSV) et normaliser le total en chaîne pour que les clés
restent comparables.

---

## 4. Un LLM pour rapprocher les noms d'actifs

**Décision.** Un nom d'actif inconnu déclenche un appel texte court comparant le
candidat aux noms déjà enregistrés (`src/assets.py`).

**Pourquoi.** Le modèle de vision retranscrit parfois « Core S&P500 USD Acc » là où le
référentiel contient « Core S&P 500 USD (Acc) ». Non traité, l'actif se dédouble et
tout agrégat par actif devient faux.

**Écarté.** Distance de Levenshtein ou `difflib`. Une distance ne fait pas la
différence entre une faute de frappe et deux produits réellement distincts aux noms
proches : « iShares Core S&P 500 » et « iShares Core S&P 400 » sont à une lettre l'un
de l'autre et n'ont rien à voir. La comparaison demande une compréhension sémantique.

**Garde-fous.**

- L'appel n'a lieu **qu'en cas d'échec de la correspondance exacte** : sur un CSV
  déjà nourri, la quasi-totalité des lignes n'en consomme aucun.
- La réponse n'est retenue que si elle figure **exactement** dans les noms connus.
  Le modèle ne peut donc pas introduire un libellé inventé — au pire, il ne corrige
  rien.
- Toute correction est tracée dans le rapport (`FIX fichier: 'ancien' → 'nouveau'`).

**Coût.** Un appel supplémentaire pour chaque actif rencontré pour la première fois,
et une correction possiblement erronée — visible dans le rapport, jamais silencieuse.

---

## 5. Valider plutôt que faire confiance

**Décision.** Un contrôle arithmétique croisé (`unités × prix ± frais ≈ total`,
tolérance 5 %) double la sortie du modèle.

**Pourquoi.** Le modèle peut lire correctement quatre nombres et se tromper sur un
seul. Le contrôle exploite la redondance déjà présente à l'écran : les quatre valeurs
sont liées par une relation connue. Une erreur de lecture isolée rompt la relation et
se signale d'elle-même.

**Pourquoi 5 %.** Les montants affichés sont arrondis (unités à 6 décimales, prix à
2) : une tolérance stricte produirait un bruit d'avertissements permanent. 5 % laisse
passer l'arrondi et attrape les erreurs de lecture réelles, d'un ordre de grandeur
supérieur.

**Exception.** Les opérations PEA n'affichent pas de ligne « unités × prix » ; le
contrôle est explicitement désactivé pour `type == "pea"`, faute de quoi chaque ligne
PEA produirait un avertissement.

---

## 6. Signaler plutôt qu'interrompre

**Décision.** `validate_transaction()` renvoie `(Transaction | None, list[str])` et ne
lève jamais d'exception. La boucle de traitement isole chaque image dans son propre
`try`. Les incidents sont accumulés et affichés à la fin.

**Pourquoi.** Un lot représente des dizaines d'appels payants. Échouer sur la
trente-septième image et perdre les trente-six précédentes est le pire scénario
possible. Le programme traite donc tout ce qu'il peut et rend compte de ce qu'il n'a
pas pu.

**Complément.** La sauvegarde intermédiaire toutes les 10 images borne à 9 extractions
la perte maximale en cas d'interruption brutale.

**Coût.** Une erreur systématique — clé invalide, modèle indisponible — n'arrête pas
le programme : elle produit N échecs successifs avant le rapport final.

---

## 7. Dépendances minimales

**Décision.** Deux dépendances externes (`python-dotenv`, `truststore`). Les appels
HTTP passent par `urllib.request` de la bibliothèque standard.

**Pourquoi.** Un utilitaire personnel relancé quelques fois par mois doit s'installer
sans surprise des mois plus tard. Le besoin HTTP se limite à deux requêtes POST JSON :
`requests` n'apporterait rien qui justifie la dépendance.

**`truststore`.** `truststore.inject_into_ssl()` expose le magasin de certificats du
système d'exploitation à travers l'API `ssl.SSLContext`. Les certificats suivent alors
les mises à jour du système, les intermédiaires manquants sont récupérés et les listes
de révocation sont vérifiées — ce qu'un ensemble figé embarqué dans un paquet Python
ne permet pas. C'est aussi ce qui rend le programme fonctionnel derrière un proxy à
autorité de certification interne, sans configuration.

**`certifi` retiré.** Il figurait dans `requirements.txt` sans être importé nulle
part. `truststore` est précisément conçu pour s'y substituer — c'est l'objet annoncé
du paquet — et n'a lui-même aucune dépendance. La ligne a donc été supprimée.

**Plancher de version.** Python 3.10+ n'est pas un choix mais une contrainte :
`truststore` et `python-dotenv` déclarent tous deux `requires_python >= 3.10`. Le code
du projet, lui, ne dépasse pas les annotations génériques natives (`list[str]`,
`tuple[...]`), disponibles depuis 3.9.

---

## 8. Un CSV réellement ouvrable dans Excel

**Décision.** Écriture en `utf-8-sig` (UTF-8 avec BOM), précédée d'une ligne `sep=;`.

**Pourquoi.** La destination du fichier est un tableur. Sans BOM, Excel interprète le
fichier en encodage local et « Société Générale » devient « SociÃ©tÃ© GÃ©nÃ©rale ».
Sans la ligne `sep=;`, il place toute la ligne dans une seule colonne. Les deux
détails ensemble donnent un fichier qui s'ouvre correctement en double-clic, sans
assistant d'importation.

**Symétrie en lecture.** Le programme relit ses fichiers en `utf-8-sig` et saute la
première ligne uniquement si elle commence par `sep=`, ce qui lui permet de relire
aussi bien sa propre sortie qu'un CSV standard.

**Précaution associée.** Excel verrouille les fichiers qu'il a ouverts. `main.py`
teste donc l'accès en écriture **avant** de commencer et attend, plutôt que de perdre
le résultat de tous les appels API au moment de l'écriture finale.
