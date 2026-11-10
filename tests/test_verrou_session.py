"""Indicateur de verrou de session (lot 6, section 4.2-4.3 du rapport).

Pendant une session ouverte (analyse OU pause), la ligne et le sens sont
figés et les réglages ne s'appliquent qu'au prochain lancement. Un bandeau
discret sous la vidéo le dit — l'opérateur ne clique pas pour déplacer une
ligne qui refuserait, et ne change pas un réglage sans effet. En pause, le
statut nomme explicitement le verrou : « En pause — ligne et sens verrouillés ».
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
    f.cap = FauxCapture()
    f.definir_ligne((300.0, 20.0), (300.0, 460.0))
    f._maj_boutons()


def test_verrou_masque_au_repos(fenetre):
    _prete(fenetre)
    assert fenetre.label_verrou.isHidden()


def test_verrou_visible_pendant_analyse(fenetre):
    _prete(fenetre)
    fenetre._ouvrir_session()
    assert not fenetre.label_verrou.isHidden()


def test_verrou_visible_en_pause(fenetre):
    _prete(fenetre)
    fenetre._ouvrir_session()
    fenetre._basculer_pause()
    assert not fenetre.label_verrou.isHidden()


def test_verrou_masque_apres_arret(fenetre):
    _prete(fenetre)
    fenetre._ouvrir_session()
    fenetre.arreter()
    assert fenetre.label_verrou.isHidden()


def test_verrou_dit_reglages_au_prochain_lancement(fenetre):
    assert "prochain lancement" in fenetre.label_verrou.text()


def test_pause_nomme_ligne_et_sens_verrouilles(fenetre):
    _prete(fenetre)
    fenetre._ouvrir_session()
    fenetre._basculer_pause()
    statut = fenetre.label_statut.text().lower()
    assert "pause" in statut
    assert "verrouill" in statut
    assert "sens" in statut