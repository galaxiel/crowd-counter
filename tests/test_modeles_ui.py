"""Modèles et profils côté écran (lot 4 de l'audit).

Le moteur v3 ne charge QUE des `.onnx` (`charger_modele` refuse un `.pt`).
L'écran, lui, parlait encore de `.pt` : le glob d'`_etat_du_modele` ne
voyait aucun poids sur une installation neuve en ONNX et conseillait de
déposer un `.pt` — que le moteur refuserait ensuite. Ces tests verrouillent
la cohérence : ce que l'écran annonce est ce que le moteur accepte.

Deux autres défauts audités : un nom de profil pouvait sortir du dossier
des profils (séparateur, « .. »), et l'opérateur ne voyait quel modèle
allait tourner qu'en ouvrant les réglages ou en chargeant une vidéo.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pathlib  # noqa: E402

import pytest  # noqa: E402

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QFileDialog  # noqa: E402

from compteur.config import Config  # noqa: E402
from interface.app import FenetrePrincipale  # noqa: E402
from interface.panneau_reglages import PanneauReglages  # noqa: E402


@pytest.fixture
def application():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def fenetre(application):
    f = FenetrePrincipale()
    yield f
    f.close()


# -- Ce que l'écran annonce du modèle -------------------------------------


def test_etat_du_modele_liste_les_onnx_presents(application, fenetre, tmp_path, monkeypatch):
    """Un `.onnx` présent est un modèle disponible, pas « aucun modèle ».

    Le glob `*.pt` de la v2 ne voyait rien sur une installation neuve en
    ONNX : l'écran conseillait de déposer un poids alors qu'il y en avait un.
    """
    import interface.app as module_app

    poids = tmp_path / "modeles"
    poids.mkdir()
    (poids / "tetes-medium.onnx").write_bytes(b"")
    monkeypatch.setattr(module_app, "dossiers_modeles", lambda: (poids,))
    f = fenetre
    f.config.modele = "absent.onnx"
    texte = f._etat_du_modele()
    assert "introuvable" in texte.lower()
    assert "disponible" in texte.lower()
    assert "aucun modèle" not in texte.lower()


def test_etat_du_modele_installation_neuve_parle_onnx(application, fenetre, monkeypatch):
    """Installation neuve : le message dit de déposer un `.onnx`, pas un `.pt`.

    Un `.pt` déposé serait refusé par `charger_modele` : le conseil de
    l'écran doit nommer le format que le moteur accepte réellement.
    """
    import interface.app as module_app

    monkeypatch.setattr(module_app, "dossiers_modeles", lambda: ())
    f = fenetre
    f.config.modele = "fantome.onnx"
    texte = f._etat_du_modele()
    assert ".onnx" in texte
    assert ".pt" not in texte


def test_aide_modele_parle_onnx(application):
    """L'infobulle du champ Modèle annonce le format `.onnx`."""
    p = PanneauReglages(Config())
    assert ".onnx" in p._modele.toolTip()


def test_parcourir_modele_filtre_onnx(application, monkeypatch):
    """L'explorateur propose les `.onnx` — pas les `.pt` que le moteur refuse."""
    capture = {}

    def faux_dialogue(parent, titre, depart, filtre):
        capture["filtre"] = filtre
        return "", ""

    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(faux_dialogue))
    p = PanneauReglages(Config())
    p._on_parcourir_modele()
    assert "*.onnx" in capture["filtre"]
    assert "*.pt" not in capture["filtre"]


# -- Nom de profil assaini -------------------------------------------------


def test_profil_nom_ne_sort_pas_du_dossier(application, tmp_path):
    """Un nom avec « .. » et un séparateur ne doit pas écrire ailleurs.

    Sans assainissement, `../evasion` résolvait hors du dossier des profils :
    un nom tapé avec un slash (ou un profil écrit à la main) pouvait écraser
    un fichier arbitraire sur le disque.
    """
    p = PanneauReglages(Config())
    cible = tmp_path / "profils"
    chemin = p.enregistrer_profil("../evasion", dossier=cible)
    assert chemin.parent == cible
    assert chemin.is_file()
    assert not (tmp_path / "evasion.json").exists()


def test_profil_nom_assaini_aller_retour(application, tmp_path):
    """Le nom assaini à l'écriture l'est aussi à la lecture : le profil revient.

    Si seul `enregistrer_profil` assainissait, `charger_profil` chercherait
    le nom brut et ne retrouverait jamais le fichier écrit.
    """
    p = PanneauReglages(Config())
    p.definir_seuil(0.37)
    p.enregistrer_profil("vue/loin", dossier=tmp_path)
    p2 = PanneauReglages(Config())
    assert p2.charger_profil("vue/loin", dossier=tmp_path) is True
    assert p2.lire().seuil_confiance == pytest.approx(0.37)


# -- Libellé permanent du modèle ------------------------------------------


def test_label_modele_permanent_reflete_la_config(application, fenetre):
    """L'opérateur voit quel modèle va tourner sans ouvrir les réglages.

    Le libellé est permanent (près de « Lancer ») et suit la config : avant
    ce lot, il fallait charger une vidéo ou ouvrir le panneau pour le savoir.
    """
    f = fenetre
    assert hasattr(f, "label_modele"), "libellé permanent absent"
    f.panneau._modele.setCurrentText("tetes-medium.onnx")
    assert "tetes-medium.onnx" in f.label_modele.text()