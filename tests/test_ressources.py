"""Tests des ressources embarquées (icône) et de leur résolution de chemin.

Le contrat : l'icône existe dans le dépôt, se charge en `QIcon` non vide
(un 404 silencieux donnerait une fenêtre sans icône), et `chemin_ressource`
résout correctement les deux contextes — sources (relatif à ce fichier) et
exécutable gelé (`sys._MEIPASS`, injecté ici par monkeypatch).
"""

import sys

import pytest

pytest.importorskip("PySide6")

from interface.ressources import (  # noqa: E402
    NOM_ICONE,
    appliquer_icone_classe,
    chemin_icone,
    chemin_ressource,
)


@pytest.fixture
def application():
    """Une QApplication unique pour toute la session (Qt n'aime pas deux fois)."""
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


def test_l_icone_existe_dans_le_depot():
    chemin = chemin_icone()
    assert chemin.is_file(), f"icône absente : {chemin}"
    assert chemin.stat().st_size > 1000


def test_la_resolution_depuis_les_sources_est_independante_du_cwd(
    monkeypatch, tmp_path
):
    monkeypatch.chdir(tmp_path)
    assert chemin_ressource(NOM_ICONE).is_file()


def test_la_resolution_gelee_passe_par_meipass(monkeypatch, tmp_path):
    faux = tmp_path / "resources" / "crowd-counter.ico"
    faux.parent.mkdir(parents=True)
    faux.write_bytes(b"ico")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert chemin_ressource(NOM_ICONE) == faux


def test_l_icone_se_charge_en_qicon(application):
    from PySide6.QtGui import QIcon

    icone = QIcon(str(chemin_icone()))
    assert not icone.isNull()
    # Plusieurs tailles doivent être disponibles (16 px de barre de titre
    # comme 256 px d'Explorateur).
    assert not icone.pixmap(16, 16).isNull()
    assert not icone.pixmap(64, 64).isNull()


def test_la_fenetre_porte_l_icone(application):
    from interface.app import FenetrePrincipale

    fenetre = FenetrePrincipale()
    try:
        icone = fenetre.windowIcon()
        assert not icone.isNull()
        assert not icone.pixmap(32, 32).isNull()
    finally:
        fenetre.close()


# -- Icône de CLASSE (correctif barre des tâches, 05/11) ------------------


def test_appliquer_icone_classe_ne_leve_jamais():
    """Cosmétique Windows : même avec un handle bidon, jamais d'exception.

    Le handle 0 n'est pas une fenêtre : les API échouent en silence — ce qui
    est exactement le contrat (un échec ne doit pas empêcher l'app de
    démarrer)."""
    assert appliquer_icone_classe(0) in (True, False)


def test_appliquer_icone_classe_hors_windows(monkeypatch):
    """Hors Windows : ne fait rien, rend False (la suite tourne sur Linux en CI)."""
    import interface.ressources as ressources

    monkeypatch.setattr(ressources.sys, "platform", "linux")
    assert appliquer_icone_classe(123) is False


def test_la_fenetre_applique_le_correctif_de_classe(application, monkeypatch):
    """`FenetrePrincipale` pose l'icône de classe avec le handle natif, dès la
    construction — AVANT `show()` : le shell lit l'icône quand la fenêtre
    apparaît, la poser après serait trop tard (bug réel du 05/11, la barre
    des tâches affichait l'icône par défaut de Qt)."""
    appels: list[int] = []

    def faux(hwnd):
        appels.append(hwnd)
        return True

    monkeypatch.setattr("interface.app.appliquer_icone_classe", faux)
    from interface.app import FenetrePrincipale

    fenetre = FenetrePrincipale()
    try:
        assert appels, "le correctif d'icône de classe n'est pas appelé"
        assert appels[0] != 0, "le handle natif doit être réel"
    finally:
        fenetre.close()
