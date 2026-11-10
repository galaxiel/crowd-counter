"""Pastille « Modèle » près de « Lancer » (lot 6, section 4.1 du rapport).

L'opérateur doit voir d'un coup d'œil si le modèle choisi est TROUVÉ sur le
poste (pastille verte) ou ABSENT (pastille ambre) — et pouvoir cliquer la
pastille pour aller choisir le modèle dans les réglages. Avant ce lot, le
libellé permanent ne disait que le nom, jamais s'il existait.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pathlib  # noqa: E402

import pytest  # noqa: E402

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QPushButton  # noqa: E402

import interface.app as module_app  # noqa: E402
from interface.app import FenetrePrincipale  # noqa: E402


@pytest.fixture
def application():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def fenetre(application):
    f = FenetrePrincipale()
    yield f
    f.close()


def test_badge_modele_est_cliquable(fenetre):
    assert isinstance(fenetre.label_modele, QPushButton)
    assert fenetre.label_modele.objectName() == "badge_modele"


def test_badge_modele_signale_trouve(fenetre, monkeypatch):
    monkeypatch.setattr(
        module_app, "resoudre_modele", lambda modele: pathlib.Path("tetes-medium.onnx")
    )
    fenetre.config.modele = "tetes-medium.onnx"
    fenetre._maj_label_modele()
    assert fenetre.label_modele.property("trouve") is True
    assert "tetes-medium.onnx" in fenetre.label_modele.text()


def test_badge_modele_signale_absent(fenetre, monkeypatch):
    monkeypatch.setattr(module_app, "resoudre_modele", lambda modele: None)
    fenetre.config.modele = "fantome.onnx"
    fenetre._maj_label_modele()
    assert fenetre.label_modele.property("trouve") is False


def test_badge_modele_clic_ouvre_les_reglages(fenetre, monkeypatch):
    appels = []
    monkeypatch.setattr(fenetre.panneau, "focus_modele", lambda: appels.append(1))
    fenetre.panneau.setEnabled(True)
    fenetre.label_modele.click()
    assert appels == [1]


def test_badge_modele_clic_ignore_si_reglages_verrouilles(fenetre, monkeypatch):
    appels = []
    monkeypatch.setattr(fenetre.panneau, "focus_modele", lambda: appels.append(1))
    fenetre.panneau.setEnabled(False)  # session ouverte : réglages figés
    fenetre.label_modele.click()
    assert appels == []