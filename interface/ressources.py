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
