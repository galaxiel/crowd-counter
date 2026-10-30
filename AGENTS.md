# crowd-counter — instructions agents

Compteur de personnes franchissant une ligne virtuelle dans une vidéo de manifestation.
App desktop PySide6, moteur de comptage YOLO + tracker IoU, Python 3.11.

Ce fichier s'adresse à tout agent qui ouvre ce dépôt (Hermes, Claude Code, Codex, OpenCode, dsh).
Il ne remplace pas `README.md` (public, en anglais) ni `docs/`.
Les lots livrés et les candidats à venir sont dans `ROADMAP.md` — ne pas commencer
un candidat sans validation explicite de l'opérateur.

## Interpréteur — le piège principal

```bash
cd "D:/Bureau/projet manif/crowd-counter"
/c/Python311/python -m pytest tests/ -v
```

`/c/Python311/python` est le seul interpréteur complet : pytest, cv2, PySide6, torch CUDA
(`2.14.1+cu126`), ultralytics 8.4, numpy, pyinstaller 6.22. Vérifié le 28/10/2026.

Deux environnements gitignorés, supprimables et recréables vivent dans le dépôt :

- `venv-temp/` — la suite de tests (torch **CPU** suffit : elle ne fait aucune inférence) ;
- `build-env/` — construire l'exe (torch CUDA + PyInstaller), procédure dans `docs/BUILDING.md`.

Ne jamais réinstaller un environnement qui existe déjà.

Avant de travailler, vérifier d'un coup :

```bash
/c/Python311/python -c "import pytest,cv2,PySide6,torch,ultralytics,numpy;print(torch.__version__, torch.cuda.is_available())"
```

- `torch.__version__` doit contenir `+cu126`. Un torch CPU s'installe silencieusement et affiche
  `cuda.is_available() == False` sans erreur — ne jamais annoncer un débit GPU avant ce contrôle.
- Cet environnement s'est corrompu plusieurs fois (numpy sans `dist-info`, torch CPU en remplacement).

## Conventions de travail

- **Ne pas construire d'exécutable sans demande explicite.** PyInstaller ne se lance que sur les mots
  « lance la reconstruction ».
- **Ne pas ajouter de fonctionnalité non demandée** (bouton, détection automatique, optimisation).
- **Mesurer avant d'affirmer.** Un chiffre arrive toujours avec son périmètre : segment de frames,
  réglage `sens`, résolution, matériel.
- Le compte de référence se fait sur le segment **frames 3600-4500** (2 min → 2 min 30).

## Tests

- Porte de routine rapide : `python -m pytest tests/ -q -m "not slow"` (553 tests, ~15 s).
- Suite complète (62 tests `slow` en plus : sous-processus `installer.py`, détection GPU réelle) :
  `python -m pytest tests/ -q` — **615 tests, ~10 s, 0 échec** (vérifié le 30/10/2026).
  La suite ne charge jamais torch en inférence : elle est lente par nature uniquement
  à cause des sous-processus.
- CI GitHub Actions (`.github/workflows/tests.yml`) lance la passe rapide à chaque push :
  Ubuntu, torch CPU, `QT_QPA_PLATFORM=offscreen`, purge opencv-headless identique à
  `docs/BUILDING.md`. Elle ne valide pas le comptage, seulement la cohérence du code.
- Un échec dans `tests/test_peripherique.py` en mode slow est presque toujours
  l'**encodage de la console** : un sous-processus écrit des accents (« ÉCHEC ») en CP1252
  sur une machine francophone. Le fix est `PYTHONIOENCODING=utf-8` côté enfant
  (helper `_dry_run`), jamais `errors="replace"` côté parent.
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
- Le chargement du modèle (v2.5) tourne dans un worker : toute logique qui doit être
  SYNCHRONE et certaine (validation d'un chemin de modèle) se fait **avant** de lancer le
  thread, pas dedans.

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
résolution auto de l'app par défaut, `--imgsz` pour forcer).

## Architecture

- `compteur/` ne doit **jamais** importer PySide6, tkinter, PyQt ou wx — verrouillé par
  `tests/test_isolation_ui.py`. Le moteur reste appelable sans écran.
- `config/default.json` et la dataclass `Config` doivent rester synchronisés (test dédié).
- La bande de détection est symétrique, 250 px avant / 250 px après la ligne, définie comme
  constantes dans `compteur/config.py`.
- Une couche d'affichage consomme l'**historique** d'événements du moteur, pas ceux de la frame
  courante : l'affichage peut sauter des frames.

## Le binaire gelé n'est pas la source

La suite de tests passe sur l'arbre source ; le `.exe` n'a que ce que le build lui a donné. Après
toute modification des exclusions de paquets, lancer le binaire et vérifier sa fenêtre — un code de
sortie 0 ne prouve rien.

## Pistes déjà testées et mortes — ne pas retester

- analyser la bande à sa résolution native (720 au lieu de 1280) : −14 % de comptes ;
- sauter une frame sur deux : −13,4 % de comptes (le tracker perd l'association) ;
- ByteTrack : moins fiable que l'IoU simple à cette taille de tête (20-29 px) ;
- densimétrie / comptage par zone, mémoire prédictive de trajectoire.

Augmenter `survie_max` au-delà de 30 ne gagne que 3 % de compte mais fausse `presents_max`.

## Licence

MIT pour le code uniquement. Les poids `.pt` (`tetes-*.pt`) ne sont pas dans le dépôt et gardent
leurs licences d'origine (Ultralytics, SCUT-HEAD).
