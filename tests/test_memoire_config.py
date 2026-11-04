"""Tests de la mémoire des derniers réglages (config/local_config.json).

Le contrat : reprendre ses réglages est un CONFORT (toute illisibilité rend
les défauts, jamais une erreur), la ligne tracée n'y figure JAMAIS (elle
appartient à la vidéo — la recharger ailleurs tracerait une ligne invisible
au mauvais endroit), et la suite de tests ne laisse rien dans le dépôt
(conftest : `memoire_config_isolee`).
"""

import json

import pytest

pytest.importorskip("PySide6")

import interface.app as app_mod  # noqa: E402
from compteur.config import Config  # noqa: E402
from interface.app import ecrire_derniere_config, lire_derniere_config  # noqa: E402


@pytest.fixture
def application():
    """Une QApplication unique pour toute la session (Qt n'aime pas deux fois)."""
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def fichier_config(tmp_path, monkeypatch):
    cible = tmp_path / "config" / "local_config.json"
    monkeypatch.setattr(app_mod, "FICHIER_MEMOIRE_CONFIG", cible)
    return cible


def test_absent_rend_les_defauts(fichier_config):
    assert not fichier_config.exists()
    assert lire_derniere_config() == Config.defauts()


def test_aller_retour_des_reglages(fichier_config):
    fichier_config.parent.mkdir(parents=True)
    c = Config.defauts()
    c.seuil_confiance = 0.42
    c.modele = "tetes-medium-1280.pt"
    c.frames_confirmation = 1
    ecrire_derniere_config(c)
    relue = lire_derniere_config()
    assert relue.seuil_confiance == 0.42
    assert relue.modele == "tetes-medium-1280.pt"
    assert relue.frames_confirmation == 1


def test_la_ligne_n_est_jamais_memorisee(fichier_config):
    """Recharger une ligne tracée sur une AUTRE vidéo = ligne invisible au
    mauvais endroit : le défaut exact que la mémoire ne doit pas créer."""
    fichier_config.parent.mkdir(parents=True)
    c = Config.defauts()
    c.ligne = (960.0, 0.0, 960.0, 720.0)
    ecrire_derniere_config(c)
    ecrit = json.loads(fichier_config.read_text(encoding="utf-8"))
    assert ecrit["ligne"] is None
    assert lire_derniere_config().ligne is None


def test_fichier_corrompu_rend_les_defauts(fichier_config):
    fichier_config.parent.mkdir(parents=True)
    fichier_config.write_text("{pas du json", encoding="utf-8")
    assert lire_derniere_config() == Config.defauts()


def test_champs_inconnus_d_une_version_passee_rendent_les_defauts(fichier_config):
    """Un fichier écrit par une version future/past ne bloque pas le lancement."""
    fichier_config.parent.mkdir(parents=True)
    fichier_config.write_text('{"seuil_confiance": 0.3, "champ_futur": 12}', encoding="utf-8")
    relue = lire_derniere_config()
    # Le champ connu est repris, l'inconnu ignoré — ou tout aux défauts :
    # dans les deux cas on obtient une Config valide avec une ligne vide.
    assert relue.ligne is None
    assert relue.seuil_confiance in (0.3, Config.defauts().seuil_confiance)


def test_ecriture_impossible_est_silencieuse(fichier_config):
    """Un disque plein ne doit pas empêcher de fermer l'application."""
    import os
    import stat

    fichier_config.parent.mkdir(parents=True)
    fichier_config.write_bytes(b"ancien contenu")
    os.chmod(fichier_config, stat.S_IREAD)  # lecture seule
    try:
        ecrire_derniere_config(Config.defauts())  # ne lève pas
    finally:
        os.chmod(fichier_config, stat.S_IWRITE | stat.S_IREAD)


# -- Branchement dans la fenêtre ------------------------------------------


def test_la_fenetre_dmarre_avec_les_derniers_reglages(application, fichier_config):
    from interface.app import FenetrePrincipale

    fichier_config.parent.mkdir(parents=True)
    depart = Config.defauts()
    depart.seuil_confiance = 0.42
    depart.modele = "tetes-nano.pt"
    ecrire_derniere_config(depart)

    fenetre = FenetrePrincipale()
    try:
        assert fenetre.config.seuil_confiance == 0.42
        assert fenetre.config.modele == "tetes-nano.pt"
        assert fenetre.config.ligne is None
    finally:
        fenetre.close()


def test_la_fermeture_memorise_les_reglages_courants(
    application, fichier_config, monkeypatch
):
    from interface.app import FenetrePrincipale

    fenetre = FenetrePrincipale()
    try:
        fenetre.config.seuil_confiance = 0.37
        fenetre.close()
        relue = json.loads(fichier_config.read_text(encoding="utf-8"))
        assert relue["seuil_confiance"] == 0.37
        assert relue["ligne"] is None
    finally:
        fenetre.close()
