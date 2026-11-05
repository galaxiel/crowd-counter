"""Les boutons de barre nés du retour opérateur du 05/11/2026.

- « Sens : … » : inversion du sens compté d'un clic, à la place de l'option
  du panneau de réglages (le panneau ne fait plus que PORTER la valeur).
- « Recommencer » : relance l'analyse du DÉBUT sans recharger la vidéo —
  `lancer()` rembobinait déjà tout seul, mais en fin d'analyse le nom ne
  le disait pas et l'opérateur se croyait obligé de recharger.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from interface.app import FenetrePrincipale  # noqa: E402


@pytest.fixture
def application():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def fenetre(application):
    f = FenetrePrincipale()
    yield f
    f.close()


def test_le_bouton_sens_affiche_le_sens_courant(fenetre):
    assert fenetre.btn_sens.text().startswith("Sens : ")
    # Sans ligne tracée, l'orientation supposée est la verticale : le défaut
    # `sens=+1` se lit « Gauche → droite ».
    assert "Gauche → droite" in fenetre.btn_sens.text()


def test_sans_video_les_boutons_sont_inactifs(fenetre):
    assert not fenetre.btn_sens.isEnabled()
    assert not fenetre.btn_recommencer.isEnabled()


def test_linversion_change_config_panneau_et_libelle(fenetre):
    fenetre.config.sens = 1
    fenetre.btn_sens.setEnabled(True)  # normalement offert avec une vidéo
    fenetre._on_inverser_sens()
    assert fenetre.config.sens == -1
    # Le panneau PORTE la valeur : le prochain `lancer()` la relira.
    assert fenetre.panneau.lire().sens == -1
    assert "Droite → gauche" in fenetre.btn_sens.text()
    # Double inversion : retour au point de départ.
    fenetre._on_inverser_sens()
    assert fenetre.config.sens == 1
    assert "Gauche → droite" in fenetre.btn_sens.text()


def test_recommencer_exige_une_analyse_deja_faite(fenetre):
    """« Recommencer » n'a de sens qu'APRÈS un premier essai : avant, il
    serait un second « Lancer » sans rien dire de plus."""
    class FauxCapture:
        def release(self):
            pass

    from compteur.ligne import Ligne

    fenetre.cap = FauxCapture()
    fenetre.ligne = Ligne((0.0, 0.0), (100.0, 100.0))
    fenetre._une_analyse_faite = False
    fenetre._maj_boutons()
    assert not fenetre.btn_recommencer.isEnabled()
    fenetre._une_analyse_faite = True
    fenetre._maj_boutons()
    assert fenetre.btn_recommencer.isEnabled()
