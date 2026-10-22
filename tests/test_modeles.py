"""Où le logiciel cherche ses modèles, et comment il les trouve.

Le contrat tient en une phrase : **la liste et le chargement balaient les
mêmes dossiers, dans le même ordre.** Sans lui, l'interface propose un nom
que le chargement refuse (« modèle introuvable ») — c'est le défaut qu'a
corrigé la v2.3.0, et c'est ce que ces tests verrouillent.

Aucun torch, aucun cv2 ici : `resoudre_modele` et `charger_modele` (branche
d'erreur) sont du pur chemin de fichiers.
"""

from __future__ import annotations

import pathlib

import pytest

from compteur.config import (
    DOSSIER_MODELES_NOM,
    dossier_modeles_utilisateur,
    dossiers_modeles,
    resoudre_modele,
)


@pytest.fixture
def bac_a_sable(monkeypatch, tmp_path):
    """Racine isolée : dossier courant ET `%LOCALAPPDATA%` dans `tmp_path`.

    Sans cela, la vraie machine entre dans le test : le dossier personnel de
    l'utilisateur pourrait contenir un `medium.pt` et masquer un défaut.
    """
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_ordre_des_dossiers_est_un_contrat(bac_a_sable):
    """L'ordre est énuméré tel quel : c'est lui qui départage deux homonymes."""
    dossiers = dossiers_modeles()
    assert dossiers[0] == pathlib.Path(".")
    assert dossiers[1] == pathlib.Path(DOSSIER_MODELES_NOM)
    assert dossiers[2] == bac_a_sable / "local" / "CompteurManifestation" / DOSSIER_MODELES_NOM


def test_dossier_personnel_partage_la_racine_du_cache(bac_a_sable):
    """Le dossier personnel doit vivre sous le MÊME parent que le cache v2.

    Deux noms qui divergent, et les modèles de l'opérateur atterrissent dans
    un dossier que plus personne ne balaie.
    """
    from compteur.telechargement import dossier_cache

    assert dossier_modeles_utilisateur().parent == dossier_cache()


def test_resout_dans_le_dossier_modeles(bac_a_sable):
    """Le point de la v2.3.0 : un nom de `modeles/` doit se CHARGER."""
    (bac_a_sable / DOSSIER_MODELES_NOM).mkdir()
    (bac_a_sable / DOSSIER_MODELES_NOM / "medium.pt").write_bytes(b"poids")

    trouve = resoudre_modele("medium.pt")
    assert trouve is not None
    assert trouve == pathlib.Path(DOSSIER_MODELES_NOM) / "medium.pt"
    assert trouve.is_file()


def test_resout_dans_le_dossier_personnel(bac_a_sable):
    """Un modèle rangé dans le dossier personnel survit aux mises à jour."""
    perso = bac_a_sable / "local" / "CompteurManifestation" / DOSSIER_MODELES_NOM
    perso.mkdir(parents=True)
    (perso / "maison.pt").write_bytes(b"poids")

    trouve = resoudre_modele("maison.pt")
    assert trouve is not None
    assert trouve.is_file()
    assert trouve.parent == perso


def test_le_dossier_courant_garde_la_priorite(bac_a_sable):
    """Deux homonymes : le dossier courant d'abord, comme la liste l'affiche."""
    (bac_a_sable / "medium.pt").write_bytes(b"courant")
    (bac_a_sable / DOSSIER_MODELES_NOM).mkdir()
    (bac_a_sable / DOSSIER_MODELES_NOM / "medium.pt").write_bytes(b"modeles")

    assert resoudre_modele("medium.pt") == pathlib.Path("medium.pt")


def test_chemin_absolu_pris_tel_quel(bac_a_sable):
    ailleurs = bac_a_sable / "ailleurs"
    ailleurs.mkdir()
    cible = ailleurs / "modele.pt"
    cible.write_bytes(b"poids")

    assert resoudre_modele(str(cible)) == cible


def test_introuvable_rend_none(bac_a_sable):
    assert resoudre_modele("fantome.pt") is None


def test_chemin_vide_rend_none(bac_a_sable):
    """`Config.modele` vide ne doit pas lever, seulement ne rien trouver."""
    assert resoudre_modele("") is None


def test_charger_modele_dit_ou_il_a_cherche(bac_a_sable):
    """L'erreur doit nommer les dossiers balayés, sinon on cherche au hasard."""
    from compteur.detecteur import charger_modele

    with pytest.raises(FileNotFoundError) as exc:
        charger_modele("fantome.pt")

    message = str(exc.value)
    assert "fantome.pt" in message
    assert DOSSIER_MODELES_NOM in message
    assert "CompteurManifestation" in message
