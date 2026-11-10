"""Boutons « Copier le bilan » / « Enregistrer » du récapitulatif (lot 6).

Le résultat ne doit plus disparaître avec la fenêtre : l'opérateur peut le
copier dans le presse-papiers ou l'enregistrer (JSON du bilan + CSV des
franchissements). Les boutons ne sont actifs qu'APRÈS un résultat affiché —
copier un récap vide n'a pas de sens.
"""

from __future__ import annotations

import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QFileDialog, QPushButton  # noqa: E402

from compteur.types import Evenement, Resultat  # noqa: E402
from interface.recap import PanneauRecap  # noqa: E402


@pytest.fixture
def application():
    return QApplication.instance() or QApplication([])


class FauxPressePapiers:
    def __init__(self):
        self.texte = ""

    def setText(self, texte):
        self.texte = texte

    def text(self):
        return self.texte


def _resultat() -> Resultat:
    return Resultat(
        total=2,
        evenements=[
            Evenement(frame=1, timestamp_s=0.04, x=1.0, y=2.0, track_id=1),
            Evenement(frame=2, timestamp_s=0.08, x=2.0, y=3.0, track_id=2),
        ],
        modele="tetes-medium.onnx",
        nb_frames=10,
        duree_video_s=1.0,
    )


def test_recap_a_deux_boutons(application):
    p = PanneauRecap()
    assert isinstance(p.btn_copier, QPushButton)
    assert isinstance(p.btn_enregistrer, QPushButton)


def test_boutons_desactives_sans_resultat(application):
    p = PanneauRecap()
    assert not p.btn_copier.isEnabled()
    assert not p.btn_enregistrer.isEnabled()


def test_copier_met_le_bilan_dans_le_presse_papiers(application, monkeypatch):
    faux = FauxPressePapiers()
    monkeypatch.setattr(QApplication, "clipboard", staticmethod(lambda: faux))
    p = PanneauRecap()
    p.afficher(_resultat())
    assert p.btn_copier.isEnabled()
    p.btn_copier.click()
    assert "2" in faux.texte
    assert "tetes-medium.onnx" in faux.texte


def test_enregistrer_ecrit_json_et_csv(application, tmp_path, monkeypatch):
    p = PanneauRecap()
    p.afficher(_resultat())
    cible = tmp_path / "bilan.json"
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(cible), ""))
    )
    p.btn_enregistrer.click()
    assert cible.is_file()
    assert (tmp_path / "bilan.csv").is_file()
    assert json.loads(cible.read_text(encoding="utf-8"))["total"] == 2
    assert "track_id" in (tmp_path / "bilan.csv").read_text(encoding="utf-8")


def test_enregistrer_annule_n_ecrit_rien(application, tmp_path, monkeypatch):
    p = PanneauRecap()
    p.afficher(_resultat())
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: ("", ""))
    )
    p.btn_enregistrer.click()
    assert list(tmp_path.iterdir()) == []


def test_effacer_desactive_les_boutons(application):
    p = PanneauRecap()
    p.afficher(_resultat())
    assert p.btn_copier.isEnabled()
    p.effacer()
    assert not p.btn_copier.isEnabled()
    assert not p.btn_enregistrer.isEnabled()