"""Point d'entrée : ``python main.py`` (et l'exécutable gelé).

Rien de lourd ici. Le thème est posé avant la construction de la fenêtre, et
la fenêtre ne charge AUCUN modèle à l'ouverture (voir `interface.app`) : le
premier écran doit s'afficher immédiatement, même sans poids sur le disque.

**Depuis la v3, plus aucune machinerie d'installation.** Le moteur est
ONNX Runtime, embarqué dans l'exécutable : pas de venv à reconstruire, pas
de téléchargement, pas d'écran d'installation — le double-clic ouvre la
fenêtre principale.
"""

from __future__ import annotations

import logging
import os
import pathlib
import sys

from PySide6.QtWidgets import QApplication

log = logging.getLogger(__name__)


def ancrer_dossier_courant() -> None:
    """Ramène le dossier courant au dossier de l'exe (gelé seulement).

    L'application lit des dossiers RELATIFS à son installation :
    `config/profils/`, `modeles/`, `config/local_*.json`. Lancée par
    double-clic, son dossier courant est déjà le bon ; relancée par le bat
    d'échange de la mise à jour, il ne l'était PAS (bug du 05/11 : l'app
    repartait du dossier PARENT — profils vides, fichiers mémoire écrits
    dans le parent). L'app s'ancre donc elle-même : quel que soit le
    lanceur, le dossier courant redevient celui de l'exe. Hors exe gelé
    (dev, tests), aucune action — le dossier courant appartient à celui
    qui lance.
    """
    if getattr(sys, "frozen", False):
        dossier_exe = pathlib.Path(sys.executable).resolve().parent
        if pathlib.Path.cwd() != dossier_exe:
            log.info("dossier courant réancré sur l'exe : %s", dossier_exe)
            os.chdir(dossier_exe)


def main() -> int:
    ancrer_dossier_courant()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    app = QApplication(sys.argv)

    # Identité de barre des tâches (AppUserModelID). Sans elle, Windows
    # rattache l'app à son exe et peut afficher l'icône EN CACHE des builds
    # précédents (le chemin ne change pas d'un build à l'autre, le cache
    # d'icônes de l'Explorateur si). L'AUMID explicite donne à l'app sa
    # propre identité de taskbar, regroupement compris. Windows uniquement,
    # échec ignoré : c'est de la cosmétique, jamais une condition.
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "galaxiel.CompteurManifestation"
            )
        except OSError:
            pass

    # Thème mémorisé du poste (config/local_theme.json) — relu ICI, avant
    # toute fenêtre.
    from interface.style import appliquer_style, lire_modele_theme

    appliquer_style(app, lire_modele_theme())

    # Icône au niveau APPLICATION : les dialogues et la barre des tâches
    # l'ont dès le premier instant. La fenêtre principale la repositionne
    # elle-même (`interface.app`) pour rester correcte même construite hors
    # de `main.py` (tests).
    from PySide6.QtGui import QIcon

    from interface.ressources import chemin_icone

    icone = QIcon(str(chemin_icone()))
    if not icone.isNull():
        app.setWindowIcon(icone)

    from interface.app import FenetrePrincipale

    fenetre = FenetrePrincipale()
    fenetre.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
