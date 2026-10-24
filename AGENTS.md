# crowd-counter — instructions agents

Compteur de personnes franchissant une ligne virtuelle dans une vidéo de manifestation.
App desktop PySide6, moteur de comptage YOLO + tracker IoU, Python 3.11.

Ce fichier s'adresse à tout agent qui ouvre ce dépôt (Hermes, Claude Code, Codex, OpenCode, dsh).
Il ne remplace pas `README.md` (public, en anglais) ni `docs/`.

## Interpréteur — le piège principal

```bash
cd "D:/Bureau/projet manif/crowd-counter"
/c/Python311/python -m pytest tests/ -v
```

`/c/Python311/python` est le seul interpréteur avec pytest + cv2 + torch CUDA + ultralytics.
Il lui manque PySide6 et pyinstaller ; l'environnement de build est `D:\build-env-tmp`.

Avant de travailler, vérifier d'un coup :

```bash
/c/Python311/python -c "import pytest,cv2,torch,ultralytics;print(torch.__version__, torch.cuda.is_available())"
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

## Configuration de référence

Vidéo de test : `D:\Bureau\manif_test.mp4` (1280x720, 7399 frames), ligne verticale x=640.

**Le sens par défaut `+1` ne compte RIEN sur cette vidéo. `sens=-1` compte 315.**
Tous les diagnostics faits avec `+1` sont faux : une « preuve » que le compteur est cassé avec ce
réglage ne prouve rien.

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
