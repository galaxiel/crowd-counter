"""Tests des thèmes d'interface (sombre / clair / suivre le système).

Trois propriétés : la persistance est un CONFORT (toute illisibilité rend le
défaut, jamais une erreur au démarrage), « systeme » se résout en un thème
réel via les QStyleHints (avec repli propre quand Qt est muet), et l'application
à chaud remplace bien la feuille de style. Le sélecteur de la fenêtre est
testé de bout en bout : changement de menu → fichier écrit + style appliqué.

Le fichier de mémoire est toujours déplacé hors du dépôt (`tmp_path`) : les
tests ne doivent pas laisser une préférence de poste derrière eux.
"""

import json

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402

import interface.style as style  # noqa: E402
from interface.style import (  # noqa: E402
    MODES,
    MODE_DEFAUT,
    STYLES,
    appliquer_style,
    ecrire_modele_theme,
    lire_modele_theme,
    mode_reel,
)


@pytest.fixture
def application():
    """Une QApplication unique pour toute la session (Qt n'aime pas deux fois)."""
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def fichier_theme(tmp_path, monkeypatch):
    """Le fichier de mémoire du thème, déplacé hors du dépôt."""
    cible = tmp_path / "config" / "local_theme.json"
    monkeypatch.setattr(style, "FICHIER_MEMOIRE_THEME", cible)
    return cible


# -- Persistance ---------------------------------------------------------


def test_theme_absent_rend_le_defaut(fichier_theme):
    assert not fichier_theme.exists()
    assert lire_modele_theme() == MODE_DEFAUT


def test_aller_retour_du_mode(fichier_theme):
    fichier_theme.parent.mkdir(parents=True)
    ecrire_modele_theme("clair")
    assert lire_modele_theme() == "clair"
    ecrire_modele_theme("systeme")
    assert lire_modele_theme() == "systeme"
    ecrire_modele_theme("sombre")
    assert lire_modele_theme() == "sombre"


def test_fichier_corrompu_rend_le_defaut(fichier_theme):
    fichier_theme.parent.mkdir(parents=True)
    fichier_theme.write_text("{pas du json", encoding="utf-8")
    assert lire_modele_theme() == MODE_DEFAUT


def test_mode_inconnu_rend_le_defaut(fichier_theme):
    """Un fichier écrit à la main (ou un retour arrière de version) ne bloque pas."""
    fichier_theme.parent.mkdir(parents=True)
    fichier_theme.write_text('{"mode": "arc-en-ciel"}', encoding="utf-8")
    assert lire_modele_theme() == MODE_DEFAUT


def test_mode_invalide_n_est_pas_ecrit(fichier_theme):
    ecrire_modele_theme("arc-en-ciel")
    assert not fichier_theme.exists()


def test_modes_sans_accent():
    """Les identifiants voyagent dans un JSON : pas d'accent, pas d'espace."""
    for mode in MODES:
        assert mode == mode.strip()
        assert mode.isascii()


# -- Résolution « système » ----------------------------------------------


class _FauxHints:
    """QStyleHints de test : renvoie le schéma imposé."""

    def __init__(self, schema) -> None:
        self._schema = schema

    def colorScheme(self):  # noqa: N802 — API Qt
        return self._schema


def test_modes_fixes_passent_tels_quels():
    assert mode_reel("sombre") == "sombre"
    assert mode_reel("clair") == "clair"
    assert mode_reel("marine") == "marine"


def test_systeme_suit_le_schema_de_l_os():
    assert mode_reel("systeme", _FauxHints(Qt.ColorScheme.Light)) == "clair"
    assert mode_reel("systeme", _FauxHints(Qt.ColorScheme.Dark)) == "sombre"


def test_systeme_sans_infos_rend_le_defaut():
    """Qt muet ou schéma inconnu : repli sur le défaut, jamais une erreur."""

    class HintsMuets:
        def colorScheme(self):  # noqa: N802 — API Qt
            raise RuntimeError("plateforme muette")

    assert mode_reel("systeme", HintsMuets()) == MODE_DEFAUT


def test_mode_inconnu_rend_le_defaut():
    assert mode_reel("arc-en-ciel") == MODE_DEFAUT


# -- Feuilles de style ----------------------------------------------------


def test_chaque_mode_reel_a_sa_feuille():
    assert set(STYLES) == {"sombre", "clair", "marine"}
    assert len({STYLES[m] for m in STYLES}) == len(STYLES)


def test_selecteurs_partages():
    """Les deux thèmes habillent les mêmes objets — sinon un widget change
    d'aspect selon le thème, ce qui n'est pas un « thème » mais un autre écran.
    Les champs, info-bulles et barres de défilement sont inclus : c'est
    exactement ce que la passe graphique du 04/11 a ajouté."""
    for feuille in STYLES.values():
        assert "#compteur" in feuille
        assert "#primaire" in feuille
        assert "#avertissement" in feuille
        assert "QProgressBar::chunk" in feuille
        assert "QGroupBox::title" in feuille
        assert "QComboBox" in feuille
        assert "QSpinBox" in feuille
        assert "QToolTip" in feuille
        assert "QScrollBar::handle" in feuille
        assert "#bouton_aide" in feuille


def test_appliquer_style(application, fichier_theme):
    appliquer_style(application, "sombre")
    assert application.styleSheet() == STYLES["sombre"]
    appliquer_style(application, "clair")
    assert application.styleSheet() == STYLES["clair"]
    # Idempotence promise par la docstring.
    appliquer_style(application, "clair")
    assert application.styleSheet() == STYLES["clair"]
    # Le mode « systeme » se résout en l'une des deux feuilles, jamais autre chose.
    appliquer_style(application, "systeme")
    assert application.styleSheet() in STYLES.values()
    # Restaurer le sombre (thème par défaut) pour les autres sessions de tests.
    appliquer_style(application, "sombre")


# -- Sélecteur de la fenêtre ----------------------------------------------


def test_le_menu_change_le_style_et_memorise(application, fichier_theme):
    from interface.app import FenetrePrincipale

    fenetre = FenetrePrincipale()
    try:
        assert fenetre.choix_theme.count() == len(MODES)
        fenetre.choix_theme.setCurrentIndex(1)  # « Clair »
        assert application.styleSheet() == STYLES["clair"]
        assert json.loads(fichier_theme.read_text(encoding="utf-8"))["mode"] == "clair"
        fenetre.choix_theme.setCurrentIndex(0)  # « Sombre »
        assert application.styleSheet() == STYLES["sombre"]
        assert json.loads(fichier_theme.read_text(encoding="utf-8"))["mode"] == "sombre"
    finally:
        fenetre.close()


def test_mode_systeme_armer_le_suivi_des_l_ouverture(application, fichier_theme):
    """Le suivi de l'OS est branché dès la construction, pas au premier clic."""
    from interface.app import FenetrePrincipale

    fichier_theme.parent.mkdir(parents=True)
    fichier_theme.write_text('{"mode": "systeme"}', encoding="utf-8")
    fenetre = FenetrePrincipale()
    try:
        assert fenetre.choix_theme.currentIndex() == MODES.index("systeme")
        assert fenetre._connexion_schema is not None
        # Un changement de schéma de l'OS réapplique le thème sans erreur.
        fenetre._on_schema_systeme()
        # Quitter le mode débranche le suivi : un choix manuel ensuite reste
        # un choix manuel.
        fenetre.choix_theme.setCurrentIndex(MODES.index("clair"))
        assert fenetre._connexion_schema is None
        assert application.styleSheet() == STYLES["clair"]
    finally:
        fenetre.close()
