"""États explicites des boutons de session (lot 6, section 4 du rapport).

La robe « primaire » (bleue) suit le geste que l'opérateur doit faire
ensuite : « Lancer » au repos, « Pause/Reprendre » pendant une session
ouverte, « Recommencer » une fois l'analyse finie. Un seul bouton la porte
à la fois — et « Lancer » est GRISÉ en pause : on ne relance pas une analyse
suspendue, on la reprend.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from interface.app import FenetrePrincipale  # noqa: E402


@pytest.fixture
def application():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def fenetre(application):
    f = FenetrePrincipale()
    yield f
    f.close()


class FauxCapture:
    def get(self, prop):
        return 0.0

    def read(self):
        return False, None

    def set(self, prop, value):
        pass

    def release(self):
        pass


def _prete(f):
    """Vidéo + ligne : « Lancer » est offert, sans session ouverte."""
    f.cap = FauxCapture()
    f.definir_ligne((300.0, 20.0), (300.0, 460.0))
    f._maj_boutons()


def _primaires(f):
    return [
        b
        for b in (f.btn_lancer, f.btn_pause, f.btn_recommencer)
        if b.objectName() == "primaire"
    ]


def test_lancer_primaire_au_repos(fenetre):
    _prete(fenetre)
    assert fenetre.btn_lancer.objectName() == "primaire"
    assert _primaires(fenetre) == [fenetre.btn_lancer]


def test_lancer_grise_en_pause(fenetre):
    _prete(fenetre)
    fenetre._ouvrir_session()
    fenetre._basculer_pause()  # ouvre la pause
    assert fenetre._session_ouverte is True
    assert fenetre._en_analyse is False
    assert not fenetre.btn_lancer.isEnabled()


def test_reprendre_primaire_en_pause(fenetre):
    _prete(fenetre)
    fenetre._ouvrir_session()
    fenetre._basculer_pause()
    assert fenetre.btn_pause.text() == "Reprendre"
    assert fenetre.btn_pause.objectName() == "primaire"
    assert _primaires(fenetre) == [fenetre.btn_pause]


def test_pause_primaire_pendant_analyse(fenetre):
    _prete(fenetre)
    fenetre._ouvrir_session()  # analyse en cours, pas pause
    assert fenetre._en_analyse is True
    assert fenetre.btn_pause.objectName() == "primaire"
    assert _primaires(fenetre) == [fenetre.btn_pause]


def test_recommencer_primaire_apres_arret(fenetre):
    _prete(fenetre)
    fenetre._ouvrir_session()
    fenetre.arreter()
    assert fenetre._une_analyse_faite is True
    assert fenetre.btn_recommencer.isEnabled()
    assert fenetre.btn_recommencer.objectName() == "primaire"
    assert fenetre.btn_lancer.objectName() != "primaire"
    assert _primaires(fenetre) == [fenetre.btn_recommencer]


def test_retour_au_repos_rend_lancer_primaire(fenetre):
    _prete(fenetre)
    fenetre._ouvrir_session()
    fenetre.arreter()
    assert fenetre.btn_recommencer.objectName() == "primaire"
    # Nouvel essai annulé avant tout compte : plus d'analyse faite.
    fenetre._reset_analyse()
    fenetre._maj_boutons()
    assert fenetre.btn_lancer.objectName() == "primaire"
    assert _primaires(fenetre) == [fenetre.btn_lancer]