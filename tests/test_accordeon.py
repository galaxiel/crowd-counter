"""Accordéon des réglages (lot 6, section 4.5 du rapport).

La colonne de six cartes empilées devient un accordéon : une section
ouverte à la fois, profils en tête. Le panneau ne décide toujours rien —
il lit des widgets et rend une Config — et naviguer entre les sections ne
change aucun réglage. L'aide reste dépliable ; seule la section ouverte
montre ses encarts à l'écran.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QToolBox  # noqa: E402

from compteur.config import Config  # noqa: E402
from interface.panneau_reglages import PanneauReglages  # noqa: E402


@pytest.fixture
def application():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def panneau(application):
    return PanneauReglages(Config())


def test_panneau_a_un_accordeon(panneau):
    assert isinstance(panneau._accordeon, QToolBox)


def test_accordeon_a_six_sections(panneau):
    assert panneau._accordeon.count() == 6


def test_profils_en_tete(panneau):
    assert panneau._accordeon.itemText(0) == "Profils"


def test_sections_portent_les_titres_des_groupes(panneau):
    titres = {
        panneau._accordeon.itemText(i)
        for i in range(panneau._accordeon.count())
    }
    assert titres == {
        "Profils",
        "Détection",
        "Tracker",
        "Ligne de franchissement",
        "Lissage",
        "Périphérique de calcul",
    }


def test_une_seule_section_ouverte_a_la_fois(panneau):
    boite = panneau._accordeon
    boite.setCurrentIndex(2)
    assert boite.currentIndex() == 2
    assert boite.currentWidget() is boite.widget(2)
    boite.setCurrentIndex(4)
    assert boite.currentWidget() is boite.widget(4)


def test_naviguer_ne_change_aucun_reglage(panneau, application):
    avant = panneau.lire()
    emissions = []
    panneau.config_modifiee.connect(lambda c: emissions.append(c))
    for i in range(panneau._accordeon.count()):
        panneau._accordeon.setCurrentIndex(i)
        application.processEvents()
    assert emissions == []
    assert panneau.lire().vers_dict() == avant.vers_dict()


def test_l_accordeon_garde_les_widgets_de_reglage(panneau):
    # Les widgets restent enregistrés : lire() et les profils fonctionnent
    # exactement comme avant, seule la présentation change.
    assert "survie_max" in panneau._widgets
    assert "taille_entree" in panneau._widgets
    assert "peripherique" in panneau._widgets
    panneau._widgets["survie_max"].setValue(120)
    assert panneau.lire().survie_max == 120