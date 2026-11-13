# crowd-counter — instructions agents

Compteur de personnes franchissant une ligne virtuelle dans une vidéo de manifestation.
App desktop PySide6, moteur de comptage YOLO + tracker IoU, Python 3.11.

Ce fichier s'adresse à tout agent qui ouvre ce dépôt (Hermes, Claude Code, Codex, OpenCode, dsh).
Il ne remplace pas `README.md` (public, en anglais) ni `docs/`.
Les lots livrés et les candidats à venir sont dans `ROADMAP.md` — ne pas commencer
un candidat sans validation explicite de l'opérateur.

## Interpréteur — le piège principal

```bash
cd "D:/Bureau/Applications/crowd-counter"
/c/Python311/python -m pytest tests/ -v
```

`/c/Python311/python` est le seul interpréteur complet : pytest, cv2, PySide6,
onnxruntime-directml (moteur v3), numpy, pyinstaller. torch/ultralytics y sont
aussi, mais uniquement pour le DEV (export .pt -> .onnx, fine-tuning) — le
moteur livré ne les touche plus. Vérifié le 06/11/2026.

Deux environnements gitignorés, supprimables et recréables vivent dans le dépôt :

- `venv-temp/` — la suite de tests (aucune inférence réelle, ONNX Runtime CPU suffit) ;
- `build-env/` — construire l'exe (requirements-dev : PyInstaller + onnxruntime-directml), procédure dans `docs/BUILDING.md`.

Ne jamais réinstaller un environnement qui existe déjà.

Avant de travailler, vérifier d'un coup :

```bash
/c/Python311/python -c "import pytest,cv2,PySide6,numpy,onnxruntime;print(onnxruntime.__version__, onnxruntime.get_available_providers())"
```

- Le provider actif se lit sur la SESSION CRÉÉE (`session.get_providers()`), pas sur
  `get_available_providers()` — celui-ci liste CUDA même quand ses DLL manquent, et la
  session retombe ALORS silencieusement sur CPU (mesuré le 06/11/2026).
- Cet environnement s'est corrompu plusieurs fois (numpy sans `dist-info`, torch CPU en remplacement).

## Conventions de travail

- **Ne pas construire d'exécutable sans demande explicite.** PyInstaller ne se lance que sur les mots
  « lance la reconstruction ».
- **Ne pas publier de release sans demande explicite.** `master` peut être en avance sur la dernière
  release : ce n'est pas un oubli à réparer.
- **Une release publie TOUJOURS deux assets** : le zip **et** son `.zip.sha256` (l'updater le lit ;
  sans lui il perd la vérification du téléchargement, sans aucune erreur visible). Le zip **garde le
  dossier `CompteurManifestation/`** à sa racine : l'updater cherche `staging/<nom>/<exe>` et refuse
  un zip plat (« archive inattendue »). Hash généré depuis `dist/` pour que l'asset nomme le fichier
  et non un chemin local. Procédure complète : `docs/BUILDING.md` §« Publishing a release ».
- **Ne pas ajouter de fonctionnalité non demandée** (bouton, détection automatique, optimisation).
- **Mesurer avant d'affirmer.** Un chiffre arrive toujours avec son périmètre : segment de frames,
  réglage `sens`, résolution, matériel.
- **Mise à jour auto : un bug d'updater exige UNE installation manuelle.** Le code
  d'updater qui tourne pendant une mise à jour est celui de la version INSTALLÉE —
  jamais refaire tester la mise à jour depuis une version dont le code d'updater est
  bugué (le correctif ne peut pas se livrer lui-même). Le script d'échange journalise
  dans `%LOCALAPPDATA%\CompteurManifestation\journal-mise-a-jour.log`.
- **Build : purger `dist/CompteurManifestation` AVANT de rebuild** (le COLLECT refuse un
  dossier non vide) et lancer `tools/copier_modeles.py` APRÈS le build (il copie dans le
  dist présent, même périmé). Sous Git Bash, `Compress-Archive` veut un chemin Windows :
  `cygpath -w`.
- **Aucun chemin d'OS en dur dans un test** (`QUrl.toLocalFile()` diffère entre
  Windows et Linux — CI déjà rougie une fois) : fixtures `tmp_path` + comparer via
  `pathlib.Path`.
- Le compte de référence se fait sur le segment **frames 3600-4500** (2 min → 2 min 30).
- **Moteur v3 = ONNX** : les modèles livrés sont des `.onnx` (export ultralytics
  depuis les `.pt` source, gardés sur le poste de dev). Parité prouvée : 2 896/2 896
  détections jumelées, comptes à ±1 — `docs/design/v3-onnx-proposition.md`.
  Pièges PIQURÉS par la mesure : le graphe attend du RGB (BGR = −7 détections), et le
  NMS ne se réimplémente PAS (version maison = −1 à −3/frame).

## Tests

- Porte de routine rapide : `python -m pytest tests/ -q -m "not slow"` (**783 tests, ~18 s, 0 échec**).
- Suite complète : `python -m pytest tests/ -q` — **783 passés, 1 sauté, ~15-30 s** (vérifié le 13/11/2026,
  après les deux annotateurs ; 28 cas ajoutés en TDD).
  Le seul test `slow` est `test_detecteur.py::test_parcite_des_detections_contre_l_ancien_chemin_torch` :
  parité ONNX↔torch, **dev uniquement** (exige torch+ultralytics, un graphe `tetes-medium-1280.onnx`
  exporté et la vidéo de référence) — il se saute sur CI et machine neuve (`importorskip` + fichier absent).
  La suite ne fait aucune inférence réelle (fausse session) : le saut est normal, pas une régression.
- CI GitHub Actions (`.github/workflows/tests.yml`) lance la passe rapide à chaque push :
  Ubuntu, ONNX Runtime CPU (marqueur de plateforme dans requirements.txt), `QT_QPA_PLATFORM=offscreen`,
  `docs/BUILDING.md`. Elle ne valide pas le comptage, seulement la cohérence du code.
- **Encodage des sous-processus de test** : un enfant qui écrit des accents (« ÉCHEC »)
  sur une machine francophone sort du CP1252 ; le fix est `PYTHONIOENCODING=utf-8` côté
  enfant (helper `_dry_run`), jamais `errors="replace"` côté parent.
- Des tracebacks qui citent un ancien nom de dossier (`crowd-counter-v2`) viennent de
  `__pycache__` périmés après un renommage : purger les `__pycache__` du dépôt
  (hors `venv-temp/`, `build-env/`), Python les régénère.

## Pièges Qt (interface/) — lus dans le code, payés en production

- `QThread.quit()` appelé **avant** `exec()` est un no-op : le thread n'a pas encore de
  boucle d'événements. Le `closeEvent` doit itérer (`quit()` + `processEvents()`) et
  **ne jamais détruire un QThread en marche** — attendre sa fin, bornée.
- Un worker thread doit rester **référencé** par un attribut de fenêtre : sans ça, le GC
  le collecte en pleine exécution et le processus crash sans message.
- Un `wait()` bloquant dans un test empêche la livraison des signaux du worker : dans les
  tests, **pomper** (`processEvents`) jusqu'à l'événement attendu.
- `Qt.Key_Escape.toString()` renvoie **`"Esc"`** et non `"Escape"` — comparer la touche
  via la chaîne sérialisée, pas le nom littéral.
- **Toute connexion Qt cross-thread passe par un slot d'un QObject récepteur,
  JAMAIS une lambda nue** : une connexion sans récepteur s'exécute dans le
  thread ÉMETTEUR — toucher un widget depuis le thread réseau gèle l'interface
  (bug réel 04/11, « ne réponds plus » pendant une mise à jour ; test de
  non-régression dans `tests/test_maj_ui.py`).
- Le chargement du modèle (v2.5) tourne dans un worker : toute logique qui doit être
  SYNCHRONE et certaine (validation d'un chemin de modèle) se fait **avant** de lancer le
  thread, pas dedans.
- **Changer un `objectName` ou une propriété dynamique ne réapplique PAS le QSS tout seul** :
  il faut `widget.style().unpolish(widget)` puis `polish(widget)`. Sans ça, le bouton primaire
  change de nom mais garde l'ancien style (lot 6, `_maj_bouton_primaire` / pastille modèle).
- **`QToolBox` (accordéon) dimensionne son `sizeHint` sur la page la PLUS HAUTE**, pas la page
  courante : déplier l'aide ne change pas la hauteur du panneau entier. Pour mesurer l'effet
  d'un encart, lire `accordeon.currentWidget().sizeHint()`, pas celui du panneau (lot 6).
- **Tests Qt offscreen : `isVisible()` teste toute la chaîne d'ancêtres** (False si la fenêtre
  n'est pas `show()`), alors que **`isHidden()` reflète le flag propre du widget**. Pour asserter
  la visibilité d'un sous-widget sans afficher la fenêtre, utiliser `isHidden()` (lot 6, verrou).
- **État de session à DEUX drapeaux** : `_en_analyse` (le timer tourne) vs `_session_ouverte`
  (analyse engagée, non terminée, pause comprise). La pause ne lève que le premier. Les réglages,
  la ligne et le sens sont gelés tant que `_session_ouverte` ; « s'appliquent au prochain lancement ».

## Configuration de référence

Vidéo de test : `D:\Bureau\manif_test.mp4` (1280x720, 7399 frames), ligne verticale x=640.

**Le sens par défaut `+1` ne compte RIEN sur cette vidéo. `sens=-1` compte 315.**
Tous les diagnostics faits avec `+1` sont faux : une « preuve » que le compteur est cassé avec ce
réglage ne prouve rien.

**`imgsz` : le harnais et l'app ne mesurent pas à la même taille.** Le harnais
`tools/mesurer_reference.py` utilise `taille_entree` par défaut de `Config` (640),
mais l'application, en résolution automatique (`taille_entree_automatique`), analyse
cette vidéo à **1280**. Mesuré le 30/10/2026 sur frames 3600-4500, `sens=-1`,
`tetes-medium.pt` : **640 → 32 comptés (~47 i/s), 704 → 32 (~51 i/s), 1280 → 36
(~30 i/s)** — répétable sur 3 passes. Un « 32 » de harnais et un « 36 » d'app ne
sont donc PAS deux mesures de la même chose. Trancher lequel est juste exige le
banc de vérité terrain : `tools/verite_terrain.py comparer` (l'app utilise déjà la
résolution auto de l'app par défaut, `--imgsz` pour forcer). L'annotation frame par
frame se pose au clic avec `tools/annotateur.py` (13/11) : même format de sortie,
relu par `comparer`. Pour l'entraînement : `tools/annotateur_boites.py` (13/11,
outil séparé) — boîtes au moment visible, export YOLO.

## Architecture

- `compteur/` ne doit **jamais** importer PySide6, tkinter, PyQt ou wx — verrouillé par
  `tests/test_isolation_ui.py`. Le moteur reste appelable sans écran.
- `config/default.json` et la dataclass `Config` doivent rester synchronisés (test dédié).
- La bande de détection est symétrique, 250 px avant / 250 px après la ligne, définie comme
  constantes dans `compteur/config.py`.
- Une couche d'affichage consomme l'**historique** d'événements du moteur, pas ceux de la frame
  courante : l'affichage peut sauter des frames.
- **Affichage des tracks : décorrélation stricte d'avec le comptage (v3.1).** Le moteur expose
  `Track.absent` (frames consécutives sans détection — informatif). L'interface seule en fait
  quelque chose : une track perdue brièvement est DESSINÉE extrapolée (dernière vitesse connue,
  `overlay.positions_extrapolees`, constante `FRAMES_EXTRAPOLATION = 3`), masquée au-delà — au
  lieu du carré figé sur du vide (artefact signalé par l'opérateur, v3.0). La carte de positions
  d'affichage ne remonte JAMAIS au moteur. Leçon de l'essai rejeté (06/11/2026, ETAT_PROJET) :
  tout repli d'appariement côté TRACKER vole des identités dans une foule dense et double-compte
  — ne pas « améliorer » le matching sans repasser la batterie complète.

## Le binaire gelé n'est pas la source

La suite de tests passe sur l'arbre source ; le `.exe` n'a que ce que le build lui a donné. Après
toute modification des exclusions de paquets, lancer le binaire et vérifier sa fenêtre — un code de
sortie 0 ne prouve rien.

## Licence

MIT pour le code uniquement. Les poids `.pt` (`tetes-*.pt`) ne sont pas dans le dépôt et gardent
leurs licences d'origine (Ultralytics, SCUT-HEAD).
