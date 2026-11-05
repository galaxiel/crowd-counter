"""Chemin des ressources embarquées — icône de l'application.

Le même fichier d'icône sert à TROIS endroits : l'icône du `.exe` (gravée
dans l'exécutable par PyInstaller, voir `crowd-counter.spec`), la barre de
titre et la barre des tâches pendant que l'app tourne (`QIcon`), et
l'écran d'installation. Les deux derniers la chargent depuis le disque :
en exécutable gelé, elle vit dans `sys._MEIPASS` (le même mécanisme que
`config/default.json`, voir `tests/test_config_gelee.py`) ; depuis les
sources, elle est relative à CE fichier, pas au dossier courant — un
lancement depuis ailleurs ne doit pas la perdre.

Ce module n'importe pas PySide6 : `main.py` le consomme AVANT que
`interface.app` (qui importe cv2) soit importable dans le binaire gelé.
"""

from __future__ import annotations

import pathlib
import sys

#: Chemin de l'icône, relatif à la racine du projet (ou de `_MEIPASS`).
NOM_ICONE = "resources/crowd-counter.ico"

_RACINE = pathlib.Path(__file__).resolve().parent.parent


def chemin_ressource(nom_relatif: str) -> pathlib.Path:
    """Chemin absolu d'une ressource, gelé ou depuis les sources."""
    if getattr(sys, "frozen", False):
        return pathlib.Path(sys._MEIPASS) / nom_relatif
    return _RACINE / nom_relatif


def chemin_icone() -> pathlib.Path:
    """Chemin de l'icône de l'application."""
    return chemin_ressource(NOM_ICONE)


def appliquer_icone_classe(hwnd: int) -> bool:
    """Pose l'icône de CLASSE de fenêtre (Windows). Correctif du 05/11/2026.

    **Le bug, mesuré.** Qt enregistre la classe de fenêtre « QWindowIcon »
    avec une icône par DÉFAUT (blanche/verte, son propre dessin), et pour
    cette application la barre des tâches affiche CETTE icône de classe au
    lieu de l'icône de fenêtre. Pourtant tout le reste est correct : l'exe
    (ExtractAssociatedIcon), l'icône de fenêtre (`WM_GETICON`, tailles BIG/
    SMALL/SMALL2) et l'icône vue par le shell pour le fichier
    (`SHGetFileInfo`) sont tous la foule cyan. Reproduction : l'app depuis
    les sources la reproduit, une fenêtre Qt minimale (mêmes Qt 6.12,
    python, AUMID, icônes) NON — le déclencheur est donc dans le code de
    l'app, pas dans l'empaquetage ni dans l'AUMID (piste non résolue à ce
    stade, voir ETAT_PROJET.md 05/11).

    **Le correctif.** Poser l'icône de CLASSE (`GCLP_HICON` et
    `GCLP_HICONSM`) sur la foule rend le résultat correct QUEL QUE SOIT le
    chemin de résolution choisi par le shell. À appeler AVANT le premier
    `show()` : le shell lit l'icône quand la fenêtre apparaît — la poser
    après serait trop tard. `hwnd` s'obtient par `int(widget.winId())`,
    qui force la création native.

    Échec silencieux (rend `False`) : c'est de la cosmétique, jamais une
    condition de démarrage. Hors Windows, ne fait rien.
    """
    if sys.platform != "win32":
        return False
    try:
        import ctypes

        u = ctypes.windll.user32
        u.LoadImageW.restype = ctypes.c_void_p
        u.SetClassLongPtrW.restype = ctypes.c_void_p
        chemin = str(chemin_icone())
        # IMAGE_ICON=1 ; LR_LOADFROMFILE=0x10, LR_DEFAULTSIZE=0x40.
        grand = u.LoadImageW(None, chemin, 1, 0, 0, 0x10 | 0x40)
        petit = u.LoadImageW(None, chemin, 1, 16, 16, 0x10)
        if not grand and not petit:
            return False
        if grand:
            u.SetClassLongPtrW(hwnd, -14, grand)  # GCLP_HICON
        if petit:
            u.SetClassLongPtrW(hwnd, -34, petit)  # GCLP_HICONSM
        return True
    except OSError:
        return False
