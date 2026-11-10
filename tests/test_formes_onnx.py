"""Formes ONNX exigées au chargement (lot 4 de l'audit).

Le compteur analyse par LOTS de 4 images et lit la sortie comme
`(B, 5, N)` — cx, cy, w, h, score d'un modèle TÊTE UNIQUE. Deux modèles
légitimes en apparence produisent un décompte faux ou un plantage :

- un batch FIGÉ à 1 : `detecter_lot` concatène 4 tenseurs, le graphe refuse
  chaque lot — l'analyse ne démarre jamais ;
- un modèle multi-classes (COCO, 84 lignes) : lire `s[4]` comme score tombe
  par hasard sur une classe, le décompte est silencieusement faux.

Les modèles livrés (`tetes-*.onnx`) ont `['batch', 3, 'height', 'width']`
en entrée et `['batch', 5, 'anchors']` en sortie : la validation doit les
ACCEPTER, et refuser les deux cas ci-dessus avec un message qui dit quoi
faire. Aucune inférence ici : de faux tenseurs de métadonnées.
"""

from __future__ import annotations

import pathlib

import pytest

from compteur import detecteur
from compteur.detecteur import ChoixPeripherique, valider_formes


class Noeud:
    def __init__(self, name, shape):
        self.name = name
        self.shape = shape


class SessionFormes:
    """Le contrat de métadonnées ONNX Runtime, sans graphe réel."""

    def __init__(self, entree, sortie):
        self._entree = entree
        self._sortie = sortie

    def get_inputs(self):
        return [Noeud("images", self._entree)]

    def get_outputs(self):
        return [Noeud("output0", self._sortie)]

    def get_providers(self):
        return ["CPUExecutionProvider"]


TETE = (["batch", 3, "height", "width"], ["batch", 5, "anchors"])


def test_modele_tete_dynamique_accepte():
    valider_formes(SessionFormes(*TETE))  # ne lève pas


def test_batch_statique_refuse():
    session = SessionFormes([1, 3, 640, 640], ["batch", 5, "anchors"])
    with pytest.raises(ValueError, match="lot"):
        valider_formes(session)


def test_sortie_multi_classes_refusee():
    session = SessionFormes(["batch", 3, "height", "width"], ["batch", 84, "anchors"])
    with pytest.raises(ValueError, match="5"):
        valider_formes(session)


def test_canaux_non_rgb_refuse():
    session = SessionFormes(["batch", 1, "height", "width"], ["batch", 5, "anchors"])
    with pytest.raises(ValueError, match="3"):
        valider_formes(session)


def test_charger_modele_applique_la_validation(tmp_path, monkeypatch):
    """Le garde-fou vit dans `charger_modele` : un graphe invalide est refusé
    AVANT d'être rendu à l'appelant, pas au premier lot."""
    graphe = tmp_path / "invalide.onnx"
    graphe.write_bytes(b"")
    monkeypatch.setattr(detecteur, "resoudre_modele", lambda chemin: graphe)
    monkeypatch.setattr(
        detecteur, "choix_peripherique",
        lambda p: ChoixPeripherique("CPUExecutionProvider", "CPU", False),
    )

    class FauxOrt:
        @staticmethod
        def InferenceSession(chemin, providers=None):
            return SessionFormes([1, 3, 640, 640], ["batch", 5, "anchors"])

    monkeypatch.setattr(detecteur, "_session_onnxruntime", lambda: FauxOrt)
    with pytest.raises(ValueError, match="lot"):
        detecteur.charger_modele(str(graphe), "cpu")