"""Test de non-régression : la progression de la mise à jour arrive sur le fil IHM.

Le bug réel (04/11, conditions réelles) : la progression était branchée sur
une lambda SANS objet récepteur, donc exécutée dans le thread ÉMETTEUR —
`dialogue.setValue` appelé depuis le thread réseau, fenêtre « ne réponds
plus » dès le premier bloc. Le fix route la progression par un slot de la
fenêtre ; ce test émet depuis un fil secondaire et vérifie que le slot
s'exécute bien sur le fil principal.
"""

import pathlib
import threading
import time

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from interface.app import _InstallationMaj, FenetrePrincipale  # noqa: E402


@pytest.fixture
def application():
    app = QApplication.instance() or QApplication([])
    yield app


def test_la_progression_est_traitee_sur_le_fil_ihm(application):
    fenetre = FenetrePrincipale()
    try:
        vus: list[tuple[int, int]] = []  # (valeur, ident du fil)

        class DialogueFaux:
            def setValue(self, valeur):
                vus.append((valeur, threading.get_ident()))

        fenetre._dialogue_maj = DialogueFaux()
        worker = _InstallationMaj(
            {"version": "x", "url_zip": "", "taille_zip": 0,
             "sha256": "", "url_page": ""},
            pathlib.Path("."),
        )
        worker.progression.connect(fenetre._maj_progression)

        fil = threading.Thread(target=lambda: worker.progression.emit(1, 2))
        fil.start()
        fil.join()

        fin = time.monotonic() + 5.0
        while not vus and time.monotonic() < fin:
            QApplication.processEvents()

        assert vus, "la progression n'est jamais arrivée"
        assert vus[0][0] == 50
        assert vus[0][1] == threading.get_ident(), (
            "le slot s'est exécuté sur le fil ÉMETTEUR : toucher un widget "
            "Qt depuis le thread réseau gèle l'interface (bug réel du 04/11)"
        )
    finally:
        fenetre.close()
