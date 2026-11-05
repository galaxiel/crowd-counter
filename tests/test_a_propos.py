"""Le dialogue « À propos » : version, vérification MANUELLE de mise à jour.

Demande opérateur (05/11/2026) : le bouton vert n'apparaît que QUAND une
mise à jour existe — il manquait l'inverse, « ai-je la dernière version ? »
sans redémarrer. La vérification réutilise le worker et le thread du
démarrage (le closeEvent les attend déjà, borné).
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402

import compteur  # noqa: E402
from interface.app import FenetrePrincipale  # noqa: E402


@pytest.fixture
def application():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def fenetre(application):
    f = FenetrePrincipale()
    yield f
    f.close()


def test_le_bouton_a_propos_existe_dans_la_barre(fenetre):
    assert fenetre.btn_a_propos.text() == "À propos"
    # Toujours actionnable : le dialogue ne dépend ni de la vidéo ni du
    # moteur (fenêtre sans vidéo chargée comprise).
    assert fenetre.btn_a_propos.isEnabled()


def test_le_dialogue_dit_la_version_et_propose_la_verification(fenetre):
    dialogue = fenetre._construire_a_propos()
    try:
        textes = [l.text() for l in dialogue.findChildren(QLabel)]
        assert any(compteur.VERSION in texte for texte in textes)
        assert fenetre._btn_verifier_maj.text() == "Vérifier les mises à jour"
    finally:
        dialogue.deleteLater()


def test_verification_hors_exe_repond_honnetement(fenetre):
    """Hors exécutable gelé, `dossier_application` est None : le garde
    `frozen` rend la vérification silencieuse — le dialogue doit le DIRE
    au lieu de rester muet sur un clic."""
    fenetre._construire_a_propos()
    retour = fenetre._retour_a_propos
    fenetre._verifier_mise_a_jour(retour=retour)
    assert "installée" in retour.text()


def test_le_resultat_est_annonce_dans_le_dialogue(fenetre):
    fenetre._construire_a_propos()
    retour = fenetre._retour_a_propos
    # Pas de mise à jour / réseau injoignable : message honnête.
    fenetre._retour_verification = retour
    fenetre._annoncer_resultat_verification(None)
    assert "Aucune nouvelle version" in retour.text()
    # Une version trouvée : elle est nommée, le bouton vert fait le reste.
    fenetre._retour_verification = retour
    fenetre._annoncer_resultat_verification({"version": "99.0.0", "sha256": "x"})
    assert "99.0.0" in retour.text()


def test_resultat_sans_dialogue_est_ignore_sans_plantage(fenetre):
    """La vérification du DÉMARRAGE (sans `retour`) ne doit rien casser :
    le slot d'annonce sort proprement quand aucun dialogue ne l'attend."""
    fenetre._retour_verification = None
    fenetre._annoncer_resultat_verification(None)
