"""Tests du système de mise à jour automatique (moteur, sans réseau).

La règle du module : **un échec ne touche jamais une installation qui
marche**. Les tests vérifient donc les garde-fous un par un — empreinte
obligatoire, extraction refusant le zip-slip, migration des données de
l'opérateur, sauvegarde par renommage (jamais une suppression), nettoyage
qui ne touche que ses propres motifs. Tout se joue avec des faux réseau
(`fetch`/`ouvrir` injectés) et de vrais zips bâtis dans `tmp_path` : la
suite reste sans réseau et sans écriture hors du temporaire.
"""

import io
import json
import pathlib
import sys
import zipfile

import pytest

from compteur import mise_a_jour
from compteur.telechargement import Annulation, ErreurReseau

EXE = mise_a_jour.EXE_NOM


# -- Versions ------------------------------------------------------------


def test_analyser_version_tolere_le_v():
    assert mise_a_jour.analyser_version("v2.6.0") == (2, 6, 0)
    assert mise_a_jour.analyser_version("2.6") == (2, 6)
    assert mise_a_jour.analyser_version("pas une version") is None
    assert mise_a_jour.analyser_version("2.6.0-rc1") is None


def test_comparer_versions():
    assert mise_a_jour.comparer_versions("v2.6.0", "2.5.0") > 0
    assert mise_a_jour.comparer_versions("2.5.0", "2.6") < 0
    assert mise_a_jour.comparer_versions("2.6.0", "v2.6.0") == 0
    # Une version incompréhensible côté serveur trie APRÈS : elle sera
    # proposée plutôt que masquée.
    assert mise_a_jour.comparer_versions("demain", "2.5.0") < 0


# -- Recherche de release -------------------------------------------------


def _api(tag="v2.6.0", avec_sha=True, url_zip="https://x/archive.zip", taille=10):
    assets = [{"name": "CompteurManifestationV2-v2.6.0-win64.zip",
               "browser_download_url": url_zip, "size": taille}]
    if avec_sha:
        assets.append({"name": "CompteurManifestationV2-v2.6.0-win64.zip.sha256",
                       "browser_download_url": "https://x/sum"})
    return {"tag_name": tag, "assets": assets, "html_url": "https://page"}


def test_chercher_release_trouve_une_version_plus_recente():
    reponses = [json.dumps(_api()).encode(), b"abcdef  archive.zip\n"]

    def fetch(url, *_a):
        return reponses.pop(0)

    info = mise_a_jour.chercher_release("2.5.0", fetch=fetch)
    assert info == {
        "version": "2.6.0",
        "url_zip": "https://x/archive.zip",
        "taille_zip": 10,
        "sha256": "abcdef",
        "url_page": "https://page",
    }


def test_chercher_release_rien_de_plus_recent():
    assert mise_a_jour.chercher_release("2.6.0", fetch=lambda u: json.dumps(_api()).encode()) is None
    assert mise_a_jour.chercher_release("2.7.0", fetch=lambda u: json.dumps(_api()).encode()) is None


def test_chercher_release_reseau_mort_rend_none():
    def fetch(url):
        raise OSError("hors ligne")

    assert mise_a_jour.chercher_release("2.5.0", fetch=fetch) is None


def test_chercher_release_sans_zip_rend_none():
    data = {"tag_name": "v2.6.0", "assets": [], "html_url": "https://page"}
    assert mise_a_jour.chercher_release("2.5.0", fetch=lambda u: json.dumps(data).encode()) is None


def test_chercher_release_sans_empreinte_le_dit():
    """Pas d'asset .sha256 : `sha256=None` — l'UI doit retomber au niveau 1."""
    info = mise_a_jour.chercher_release(
        "2.5.0", fetch=lambda u: json.dumps(_api(avec_sha=False)).encode()
    )
    assert info is not None
    assert info["sha256"] is None


# -- Téléchargement -------------------------------------------------------


class _ReponseFausse:
    """Ce que `urlopen` aurait rendu : lecture par blocs + en-têtes."""

    def __init__(self, donnees: bytes, en_tetes: dict) -> None:
        self._donnees = donnees
        self.en_tetes = en_tetes
        self.status = 206 if "Range" in en_tetes else 200
        self.headers = {"Content-Length": str(len(donnees))}

    def read(self, n=-1):
        bout, self._pos = self._pos, min(len(self._donnees), self._pos + n)
        return self._donnees[bout:self._pos]

    _pos = 0

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_telecharger_complet(tmp_path):
    demandes = []

    def ouvrir(url, en_tetes):
        demandes.append(dict(en_tetes))
        return _ReponseFausse(b"contenu complet", en_tetes)

    cible = tmp_path / "archive.zip"
    mise_a_jour.telecharger("https://x", cible, ouvrir=ouvrir)
    assert cible.read_bytes() == b"contenu complet"
    assert not cible.with_suffix(".zip.part").exists()
    assert "Range" not in demandes[0]


def test_telecharger_reprend_ou_il_en_etait(tmp_path):
    cible = tmp_path / "archive.zip"
    partiel = cible.with_suffix(".zip.part")
    partiel.write_bytes(b"conte")
    vus = []

    def ouvrir(url, en_tetes):
        vus.append(dict(en_tetes))
        return _ReponseFausse(b"nu complet", en_tetes)

    mise_a_jour.telecharger("https://x", cible, ouvrir=ouvrir)
    assert vus[0]["Range"] == "bytes=5-"
    assert cible.read_bytes() == b"contenu complet"


def test_telecharger_serveur_ignore_la_reprise(tmp_path):
    """Réponse 200 sur un partiel : repartir de zéro, sinon contenu corrompu."""
    cible = tmp_path / "archive.zip"
    cible.with_suffix(".zip.part").write_bytes(b"vieux reste")

    class ServeurSourd(_ReponseFausse):
        def __init__(self, donnees, en_tetes):
            super().__init__(donnees, en_tetes)
            self.status = 200

    mise_a_jour.telecharger(
        "https://x", cible, ouvrir=lambda u, t: ServeurSourd(b"frais", t)
    )
    assert cible.read_bytes() == b"frais"


def test_telecharger_taille_faussée_est_refusee(tmp_path):
    cible = tmp_path / "archive.zip"
    with pytest.raises(ErreurReseau, match="attendue"):
        mise_a_jour.telecharger(
            "https://x", cible, taille_attendue=100,
            ouvrir=lambda u, t: _ReponseFausse(b"court", t),
        )
    assert not cible.exists()
    assert not cible.with_suffix(".zip.part").exists()


def test_telecharger_annulation_ne_touch_pas_la_destination(tmp_path):
    cible = tmp_path / "archive.zip"

    def ouvrir(url, en_tetes):
        return _ReponseFausse(b"x" * 10, en_tetes)

    with pytest.raises(Annulation):
        mise_a_jour.telecharger(
            "https://x", cible, ouvrir=ouvrir, annule=lambda: True
        )
    assert not cible.exists()


# -- Extraction et préparation --------------------------------------------


def _zip_install(dossier: pathlib.Path, extra: dict[str, bytes] | None = None) -> pathlib.Path:
    archive = dossier / "archive.zip"
    contenu = {
        f"CompteurManifestation/{EXE}": b"exe",
        "CompteurManifestation/modeles/tetes-medium.pt": b"poids livres",
        **(extra or {}),
    }
    with zipfile.ZipFile(archive, "w") as z:
        for nom, donnees in contenu.items():
            z.writestr(nom, donnees)
    return archive


def _installation_ancienne(dossier: pathlib.Path) -> pathlib.Path:
    """Une installation d'origine, avec les données de l'opérateur dedans."""
    app = dossier / "CompteurManifestation"
    (app / "config").mkdir(parents=True)
    (app / "config" / "local_theme.json").write_text('{"mode": "marine"}', encoding="utf-8")
    (app / "config" / "profils").mkdir()
    (app / "config" / "profils" / "dimanche.json").write_text("{}", encoding="utf-8")
    (app / "modeles").mkdir()
    (app / "modeles" / "tetes-medium.pt").write_bytes(b"anciens poids")
    (app / "modeles" / "a-moi.pt").write_bytes(b"mon modele")
    return app


def test_extraire_et_migrer(tmp_path):
    app = _installation_ancienne(tmp_path)
    staging = tmp_path / ".maj-2.6.0"
    mise_a_jour.extraire(_zip_install(tmp_path), staging)
    nouveau = staging / "CompteurManifestation"
    copies = mise_a_jour.migrer_donnees(app, nouveau)
    assert (nouveau / "config" / "local_theme.json").read_text(encoding="utf-8") == '{"mode": "marine"}'
    assert (nouveau / "config" / "profils" / "dimanche.json").exists()
    # Le modèle déposé suit ; celui livré par la release n'est PAS écrasé.
    assert (nouveau / "modeles" / "a-moi.pt").read_bytes() == b"mon modele"
    assert (nouveau / "modeles" / "tetes-medium.pt").read_bytes() == b"poids livres"
    assert any("a-moi.pt" in c for c in copies)


def test_extraire_refuse_le_zip_slip(tmp_path):
    """Un membre `..\\...` doit être refusé, jamais écrit hors du dossier."""
    archive = tmp_path / "mechant.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("../echappe.txt", b"x")
    with pytest.raises(ErreurReseau, match="hors dossier"):
        mise_a_jour.extraire(archive, tmp_path / "sortie")
    assert not (tmp_path / "echappe.txt").exists()


def test_preparer_staging_ecrit_le_script_et_migre(tmp_path):
    app = _installation_ancienne(tmp_path)
    bat = mise_a_jour.preparer_staging(
        _zip_install(tmp_path), app, "2.6.0"
    )
    assert bat.exists() and bat.name == "mise-a-jour.bat"
    texte = bat.read_text(encoding="cp1252")
    assert "tasklist" in texte
    assert "CompteurManifestation.ancienne" in texte
    assert "CompteurManifestation\\CompteurManifestation.exe" in texte
    # Les données ont suivi dans l'étape.
    nouveau = bat.parent / "CompteurManifestation"
    assert (nouveau / "config" / "local_theme.json").exists()
    assert (nouveau / modeles_rel()).exists()


def modeles_rel() -> str:
    return "modeles/a-moi.pt"


def test_preparer_staging_refuse_une_archive_sans_exe(tmp_path):
    app = _installation_ancienne(tmp_path)
    archive = tmp_path / "vide.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("CompteurManifestation/lisez-moi.txt", b"?")
    with pytest.raises(ErreurReseau, match="absent"):
        mise_a_jour.preparer_staging(archive, app, "2.6.0")


# -- Nettoyage ------------------------------------------------------------


def test_nettoyer_anciennes_ne_touche_que_ses_motifs(tmp_path):
    (tmp_path / ".maj-2.6.0").mkdir()
    (tmp_path / ".maj-2.6.0.zip").write_bytes(b"z")
    (tmp_path / "CompteurManifestation.ancienne").mkdir()
    (tmp_path / "CompteurManifestation").mkdir()
    (tmp_path / "mes documents").mkdir()
    (tmp_path / "generation.anciennete").write_bytes(b"x")

    supprimes = mise_a_jour.nettoyer_anciennes(tmp_path)

    assert sorted(supprimes) == [".maj-2.6.0", ".maj-2.6.0.zip", "CompteurManifestation.ancienne"]
    assert (tmp_path / "CompteurManifestation").exists()
    assert (tmp_path / "mes documents").exists()
    assert (tmp_path / "generation.anciennete").exists()


def test_nettoyer_dossier_absent_est_silencieux(tmp_path):
    assert mise_a_jour.nettoyer_anciennes(tmp_path / "rien-ici") == []


# -- Garde « exécutable gelé » ---------------------------------------------


def test_hors_exe_rien_a_mettre_a_jour():
    """Depuis les sources, l'updater doit être muet — jamais toucher le dépôt."""
    assert getattr(sys, "frozen", False) is False
    assert mise_a_jour.dossier_application() is None


def test_exe_gele_renvoie_son_dossier(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "app" / EXE))
    assert mise_a_jour.dossier_application() == tmp_path / "app"


# -- Le script d'échange en lui-même ---------------------------------------


def test_script_echange_renomme_sans_supprimer():
    texte = mise_a_jour.texte_script_echange(".maj-2.6.0")
    # La sauvegarde est un RENOMMAGE — jamais une suppression avant le
    # démarrage réussi de la nouvelle version.
    assert "move /Y \"CompteurManifestation\" \"CompteurManifestation.ancienne\"" in texte
    assert "rd " not in texte and "rmdir" not in texte
    # Retour arrière si la nouvelle version est incomplète : les sauts vers
    # :retour/:echec sont sur le chemin normal, AVANT la sortie heureuse.
    assert ":retour" in texte and ":echec" in texte
    sortie_heureuse = texte.index("exit /b 0")
    assert texte.index("goto retour") < sortie_heureuse
    assert texte.index("goto echec") < sortie_heureuse
