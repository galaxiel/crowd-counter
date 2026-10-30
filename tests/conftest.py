"""Configuration commune à la suite de tests.

La suite doit tourner depuis n'importe quel répertoire de travail : les scripts
lancés depuis ailleurs (tâche 7) et PyInstaller (tâche 12, depuis `dist/`)
n'ont pas le dépôt comme dossier courant. On insère donc la racine du dépôt
dans `sys.path` et on ancre les chemins sur l'emplacement de ce fichier plutôt
que sur le CWD.
"""

import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent

if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))


@pytest.fixture(autouse=True)
def memoire_video_isolee(tmp_path, monkeypatch):
    """La mémoire du dernier dossier vidéo reste DANS le test.

    `charger_video` écrit `config/local_dossier_video.json` à chaque vidéo
    ouverte. Sans ce détournement, la suite réécrirait ce fichier dans le
    dépôt à chaque exécution — un test doit laisser le dépôt tel qu'il
    l'a trouvé.

    `interface.app` peut être indisponible (PySide6 absent, la suite le
    saute alors propreusement) : il n'y a alors aucune mémoire à détourner.
    """
    try:
        import interface.app
    except ImportError:
        return
    monkeypatch.setattr(
        interface.app,
        "FICHIER_MEMOIRE_VIDEO",
        tmp_path / "local_dossier_video.json",
    )
