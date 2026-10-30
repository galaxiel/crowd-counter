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


@pytest.fixture(scope="session", autouse=True)
def fermeture_qt_protegee():
    """Détruit la QApplication dans un ordre maîtrisé, avant la sortie.

    PySide6 sur Linux (CI, `QT_QPA_PLATFORM=offscreen`) segfault à la
    fermeture de l'INTERPRÉTEUR si on laisse le GC finaliser les objets Qt
    dans un ordre arbitraire : « QObject: shared QObject was deleted
    directly », puis SIGSEGV — code de sortie 139 alors que TOUS les tests
    sont passés. Le crash n'est donc pas un échec de test : c'est la
    destruction des restes Qt au moment de quitter Python.

    Ici, une seule fenêtre de premier niveau reste vivante en fin de session
    (le `QApplication.instance()` partagé et les widgets des tests). On ferme
    et on supprime les top-level widgets PENDANT la session, quand l'ordre
    de destruction est encore le nôtre, puis on quitte l'événement — la
    sortie de l'interpréteur ne trouve plus rien à détruire.

    Sur Windows, cette destruction ordonnée est tout aussi valide : Qt
    n'autorise qu'une QApplication par process, les widgets fermés ici ne
    servent plus personne.
    """
    yield
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        return  # PySide6 absent : rien à fermer
    app = QApplication.instance()
    if app is None:
        return
    for fenetre in app.topLevelWidgets():
        fenetre.close()
        fenetre.deleteLater()
    app.processEvents()
    # `deleteLater()` n'est consommé QUE par une boucle d'événements qui
    # se rendrait au retour du posteur ; `processEvents()` ne garantit pas
    # les suppressions différées. `sendPostedEvents(None, DeferredDelete)`
    # les vide explicitement — sans quoi les widgets survivraient encore à
    # la session, exactement le scénario de crash.
    from PySide6.QtCore import QEvent, QCoreApplication

    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


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
