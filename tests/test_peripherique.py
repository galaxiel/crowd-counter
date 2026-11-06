"""Tests du sélecteur de périphérique (providers ONNX Runtime) et de l'installateur.

Trois objets distincts, trois raisons d'être distincts :

- `Config.peripherique` est un réglage, comme la résolution d'analyse ;
- `detecteur.choix_peripherique` est une DÉCISION, qui dépend de ce que le
  paquet installé propose réellement — la décision est testée en simulant
  les providers disponibles, jamais en interrogeant la machine ;
- l'installateur choisit un paquet, ce qui n'a rien à voir avec le choix
  d'un périphérique à l'exécution.

CONTRAT v3 (moteur ONNX, changé le 06/11) : le réglage « cuda » signifie
« accélération GPU exigée » — le provider réellement retenu est DirectML
d'abord (il couvre NVIDIA, AMD et Intel), CUDA sinon. Un `auto` qui tombe
sur le CPU est le cas NORMAL d'une machine sans GPU compatible : silencieux.
Un réglage explicite non honoré reste un repli CPU AVEC avertissement
(leçon v2 conservée : basculer en le disant, jamais planter).
"""

from __future__ import annotations

import pytest

from compteur.config import (
    PERIPHERIQUE_AUTO,
    PERIPHERIQUE_CPU,
    PERIPHERIQUE_CUDA,
    PERIPHERIQUES,
    Config,
    mode_peripherique,
)
from compteur.detecteur import (
    LIBELLE_CPU,
    choix_peripherique,
    libelle_peripherique,
)


def _simuler(monkeypatch, disponibles: list[str]):
    monkeypatch.setattr(
        "compteur.detecteur.providers_disponibles", lambda: list(disponibles)
    )


# -- Configuration -------------------------------------------------------


def test_peripherique_vaut_auto_par_defaut():
    """`auto` est le seul mode qui marche sur une machine inconnue."""
    assert Config().peripherique == PERIPHERIQUE_AUTO


def test_le_fichier_versionne_port_le_meme_defaut():
    """Le fichier `config/default.json` ne doit pas diverger du dataclass."""
    defauts = Config.defauts()
    assert defauts.peripherique == Config().peripherique


def test_les_trois_modes_existent():
    assert PERIPHERIQUES == ("auto", "cuda", "cpu")


@pytest.mark.parametrize("mode", PERIPHERIQUES)
def test_un_profil_peut_porter_n_importe_quel_mode(mode, tmp_path):
    """Aller-retour JSON complet, comme un profil enregistré."""
    p = tmp_path / "profil.json"
    Config(peripherique=mode).vers_fichier(p)
    assert Config.depuis_fichier(p).peripherique == mode


def test_un_mode_inconnu_tombe_sur_auto():
    """Un profil à la main ne doit pas rendre le moteur inutilisable."""
    assert mode_peripherique("rocm") == PERIPHERIQUE_AUTO
    assert mode_peripherique(None) == PERIPHERIQUE_AUTO


# -- La décision : auto, gpu exigé, cpu exigé ----------------------------


def test_auto_prend_dml_quand_present(monkeypatch):
    """DirectML d'abord : il couvre TOUTES les cartes (NVIDIA, AMD, Intel)."""
    _simuler(monkeypatch, ["DmlExecutionProvider", "CPUExecutionProvider"])
    c = choix_peripherique(PERIPHERIQUE_AUTO)
    assert c.device == "DmlExecutionProvider"
    assert c.cuda is True
    assert c.avertissement is None


def test_auto_prend_cuda_sans_dml(monkeypatch):
    _simuler(monkeypatch, ["CUDAExecutionProvider", "CPUExecutionProvider"])
    c = choix_peripherique(PERIPHERIQUE_AUTO)
    assert c.device == "CUDAExecutionProvider"
    assert c.cuda is True
    assert c.avertissement is None


def test_auto_replie_sur_cpu_silencieusement(monkeypatch):
    """Pas de GPU : le CPU est le comportement attendu d'une machine sans
    carte compatible — pas une panne, donc pas d'avertissement."""
    _simuler(monkeypatch, ["CPUExecutionProvider"])
    c = choix_peripherique(PERIPHERIQUE_AUTO)
    assert c.device == "CPUExecutionProvider"
    assert c.libelle == LIBELLE_CPU
    assert c.avertissement is None


def test_gpu_exige_replie_sur_cpu_avec_avertissement(monkeypatch):
    """Le cas central : GPU exigé mais indisponible.

    Le contrat est une BASCULE avec message, pas une exception : sur le
    terrain, une analyse plus lente qui rend un chiffre vaut mieux qu'un
    plantage. Le message doit nommer la cause.
    """
    _simuler(monkeypatch, ["CPUExecutionProvider"])
    c = choix_peripherique(PERIPHERIQUE_CUDA)
    assert c.device == "CPUExecutionProvider"
    assert c.avertissement is not None
    assert "GPU" in c.avertissement


def test_gpu_exige_sur_machine_graphique_n_avertit_pas(monkeypatch):
    _simuler(monkeypatch, ["DmlExecutionProvider", "CPUExecutionProvider"])
    c = choix_peripherique(PERIPHERIQUE_CUDA)
    assert c.cuda is True
    assert c.avertissement is None


def test_cpu_force_le_cpu_meme_avec_un_gpu(monkeypatch):
    """Le remède quand le GPU plante sur une scène particulière : un choix,
    silencieux — l'opérateur l'a fait exprès."""
    _simuler(monkeypatch, ["DmlExecutionProvider", "CPUExecutionProvider"])
    c = choix_peripherique(PERIPHERIQUE_CPU)
    assert c.device == "CPUExecutionProvider"
    assert c.cuda is False
    assert c.avertissement is None


# -- Libellé affiché -----------------------------------------------------


def test_le_libelle_annonce_le_gpu(monkeypatch):
    _simuler(monkeypatch, ["DmlExecutionProvider", "CPUExecutionProvider"])
    texte = libelle_peripherique(PERIPHERIQUE_AUTO)
    assert texte.startswith("Calcul : ")
    assert "DirectML" in texte


def test_le_libelle_annonce_le_cpu_sans_gpu(monkeypatch):
    """L'opérateur doit voir « CPU » et non un nom de provider brut."""
    _simuler(monkeypatch, ["CPUExecutionProvider"])
    assert libelle_peripherique(PERIPHERIQUE_AUTO) == f"Calcul : {LIBELLE_CPU}"


def test_le_libelle_ne_contient_jamais_de_device_brut(monkeypatch):
    """Un nom de provider à l'écran serait du jargon."""
    _simuler(monkeypatch, ["DmlExecutionProvider", "CPUExecutionProvider"])
    assert "DmlExecutionProvider" not in libelle_peripherique(PERIPHERIQUE_AUTO)
    assert "cuda:0" not in libelle_peripherique(PERIPHERIQUE_AUTO)
