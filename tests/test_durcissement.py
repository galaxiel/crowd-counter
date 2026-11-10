"""Durcissement de la périphérie (lot 5 de l'audit).

Des défauts de robustesse sans effet sur le compte, mais dont la
conséquence est disproportionnée : un filtre zip-slip qui laisse passer un
dossier frère partageant le préfixe, une erreur « espace disque » qui
lève `TypeError` au lieu de parler à l'opérateur, un nettoyage qui efface
tout dossier `*.ancienne` du parent (un « photos.ancienne » personnel y
passerait), un journal muet en exe windowed. Chaque point a un test sans
réseau ni caméra.
"""

from __future__ import annotations

import logging
import os
import zipfile

import pytest

from compteur import mise_a_jour
from compteur.erreurs import ErreurDisque


# -- Zip-slip : le séparateur manquant ------------------------------------


def test_zip_slip_frere_partageant_le_prefixe_est_refuse(tmp_path):
    """`startswith` sans séparateur laisse passer un dossier frère.

    Extraction dans `…/foo` : un membre résolvant vers `…/foobar` commence
    bien par `…/foo` — l'ancien filtre l'acceptait, il écrit HORS du dossier.
    """
    extraction = tmp_path / "foo"
    extraction.mkdir()
    membre = zipfile.ZipInfo(filename="../foobar/pwn.txt")
    assert mise_a_jour._membre_sur(extraction, membre) is False


def test_zip_slip_frere_refuse_a_l_extraction(tmp_path):
    """Le même cas au niveau d'`extraire` : l'archive est refusée, rien d'écrit."""
    archive = tmp_path / "mechant.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("../foobar/pwn.txt", b"x")
    from compteur.erreurs import ErreurReseau

    with pytest.raises(ErreurReseau, match="hors dossier"):
        mise_a_jour.extraire(archive, tmp_path / "foo")
    assert not (tmp_path / "foobar").exists()


def test_membre_dans_le_dossier_est_accepte(tmp_path):
    """Le filtre ne doit pas rejeter un membre légitime sous le dossier."""
    extraction = tmp_path / "foo"
    extraction.mkdir()
    membre = zipfile.ZipInfo(filename="foo/sous/fichier.txt")
    assert mise_a_jour._membre_sur(extraction, membre) is True


# -- ErreurDisque : des octets, pas une chaîne ----------------------------


def test_erreur_disque_formate_des_octets():
    """Le constructeur attend un entier d'octets et l'affiche en Go."""
    exc = ErreurDisque(2 * 1024 ** 3)
    assert "2.0 Go" in str(exc)
    assert "insuffisant" in str(exc).lower()


def test_verifier_disque_leve_une_erreur_lisible(tmp_path, monkeypatch):
    """Disque trop plein : `ErreurDisque` parlante, pas un `TypeError`.

    `verifier_disque` passait une chaîne au constructeur qui attend des
    octets : `manque / (1024**3)` levait `TypeError`, le message « espace
    disque » ne pouvait pas exister.
    """
    monkeypatch.setattr(mise_a_jour, "taille_libre", lambda d: 10 * 1024 * 1024)
    with pytest.raises(ErreurDisque) as exc:
        mise_a_jour.verifier_disque(tmp_path, taille_zip=100 * 1024 * 1024)
    assert "insuffisant" in str(exc.value).lower()


def test_verifier_disque_silencieux_si_la_place_est_la(tmp_path, monkeypatch):
    """Assez de place : aucune erreur (le repli 0 de taille_libre ne gêne pas)."""
    monkeypatch.setattr(mise_a_jour, "taille_libre", lambda d: 10 * 1024 ** 3)
    mise_a_jour.verifier_disque(tmp_path, taille_zip=100 * 1024 * 1024)


# -- Nettoyage : le nom exact de sauvegarde -------------------------------


def test_nettoyage_epargne_une_sauvegarde_voisine(tmp_path):
    """Un dossier personnel « photos.ancienne » voisin doit SURVIVRE.

    L'ancien filtre `endswith('.ancienne')` effaçait tout dossier ainsi
    suffixé dans le parent de l'installation — sur le Bureau, un dossier
    personnel y passait au démarrage.
    """
    (tmp_path / "CompteurManifestation.ancienne").mkdir()
    (tmp_path / "photos.ancienne").mkdir()
    (tmp_path / ".maj-2.6.0").mkdir()

    supprimes = mise_a_jour.nettoyer_anciennes(tmp_path)

    assert "CompteurManifestation.ancienne" in supprimes
    assert ".maj-2.6.0" in supprimes
    assert (tmp_path / "photos.ancienne").exists(), "sauvegarde voisine effacée"
    assert "photos.ancienne" not in supprimes


# -- Journal fichier (exe windowed : stderr muet) -------------------------


def test_journal_fichier_sous_localappdata(tmp_path, monkeypatch):
    """Le journal part dans %LOCALAPPDATA%, et un message y atterrit."""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    import main as module_main

    racine = logging.getLogger()
    avant = list(racine.handlers)
    niveau = racine.level
    racine.setLevel(logging.INFO)  # comme main() après basicConfig(level=INFO)
    chemin = module_main.installer_journal_fichier()
    ajoutes = [h for h in racine.handlers if h not in avant]
    try:
        assert chemin is not None
        assert chemin == tmp_path / "local" / "CompteurManifestation" / "journal.log"
        assert chemin.is_file()
        logging.getLogger("test.journal").info("bonjour le journal")
        for h in ajoutes:
            h.flush()
        assert "bonjour le journal" in chemin.read_text(encoding="utf-8")
    finally:
        for h in ajoutes:
            racine.removeHandler(h)
            h.close()
        racine.setLevel(niveau)


def test_journal_fichier_echec_est_silencieux(monkeypatch):
    """Dossier impossible à créer : le logiciel démarre quand même (None)."""
    import compteur.erreurs as erreurs
    import main as module_main

    def explosif():
        raise OSError("volume inaccessible")

    monkeypatch.setattr(erreurs, "dossier_cache", explosif)
    assert module_main.installer_journal_fichier() is None


# -- Le worker vérifie le disque AVANT de télécharger ---------------------


def test_installation_verifie_le_disque_avant_telecharger(tmp_path, monkeypatch):
    """Disque insuffisant : `echouee` parle, `telecharger` n'est pas appelé."""
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])
    from interface.app import _InstallationMaj

    appele = {"telecharger": False}

    def faux_verifier(dossier, taille):
        raise ErreurDisque(5 * 1024 ** 3)

    def faux_telecharger(*a, **k):
        appele["telecharger"] = True

    monkeypatch.setattr(mise_a_jour, "verifier_disque", faux_verifier)
    monkeypatch.setattr(mise_a_jour, "telecharger", faux_telecharger)
    info = {
        "version": "9.9.9",
        "url_zip": "https://x/z.zip",
        "taille_zip": 100,
        "sha256": "abc",
    }
    worker = _InstallationMaj(info, tmp_path / "app")
    messages = []
    worker.echouee.connect(messages.append)
    worker.run()
    assert appele["telecharger"] is False, "téléchargement lancé malgré le disque plein"
    assert messages and "insuffisant" in messages[0].lower()