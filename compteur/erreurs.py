"""Emplacements et erreurs partagés du paquet `compteur`.

Depuis la v3 (moteur ONNX Runtime embarqué), il n'y a plus de
téléchargement de torch : ce module ne garde que ce qui survit à ce
retrait — le dossier de données de l'application et les exceptions du
système de mise à jour.
"""

from __future__ import annotations

import os
import pathlib


def dossier_cache() -> pathlib.Path:
    r"""Racine des données de l'application : `%LOCALAPPDATA%\CompteurManifestation`.

    **Pas de `C:\Program Files`, et donc pas de droits administrateur.** Un
    logiciel de terrain qui déclenche un UAC perd la moitié de ses
    utilisateurs : `%LOCALAPPDATA%` est en écriture pour l'utilisateur
    connecté, sans privilège.
    """
    base = os.environ.get("LOCALAPPDATA")
    if not base:  # pragma: no cover — toujours défini sous Windows
        base = str(pathlib.Path.home())
    return pathlib.Path(base) / "CompteurManifestation"


class ErreurInstallation(Exception):
    """Base des erreurs d'installation bloquantes, avec message opérateur."""

    def __init__(self, message: str, details: str = "") -> None:
        super().__init__(message)
        self.details = details


class ErreurReseau(ErreurInstallation):
    """Coupure réseau pendant la résolution ou le téléchargement."""

    def __init__(self, quoi: str, cause: str = "") -> None:
        super().__init__(
            f"La connexion a été interrompue pendant l'installation de "
            f"{quoi}. Relancez le logiciel : le téléchargement reprendra "
            f"où il s'est arrêté.",
            details=cause,
        )


class ErreurDisque(ErreurInstallation):
    """Pas assez de place sur le disque."""

    def __init__(self, manque: int) -> None:
        super().__init__(
            f"Espace disque insuffisant : il manque environ "
            f"{manque / (1024 ** 3):.1f} Go. Libérez de la place, ou "
            f"choisissez la version CPU, beaucoup plus légère.",
            details=f"manque {manque} octets",
        )


class Annulation(Exception):
    """Levée par le callback pour interrompre l'installation.

    Porter l'annulation dans une exception permet de la faire lever depuis
    n'importe quel point, sans multiplier les tests `if annule: return`.
    """
