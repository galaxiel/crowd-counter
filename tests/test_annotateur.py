"""Tests de l'annotateur au clic (tools/annotateur.py).

Deux étages : la session d'annotation (pure, sans Qt) et la fenêtre
(offscreen, source vidéo factice). Le fichier produit doit se relire par
`tools.verite_terrain.lire_annotations` : c'est le contrat du banc.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

import numpy as np  # noqa: E402
from PySide6.QtCore import QEvent, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QMouseEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from tools.annotateur import FenetreAnnotation, SessionAnnotation  # noqa: E402
from tools.verite_terrain import lire_annotations  # noqa: E402


def test_ajouter_range_le_frame_et_la_position():
    s = SessionAnnotation()
    s.ajouter(3732, 640, 300)
    assert s.entrees == [(3732, 640, 300)]
    assert len(s) == 1


def test_annuler_retire_le_dernier_clic():
    s = SessionAnnotation()
    s.ajouter(3732, 640, 300)
    s.ajouter(3800)
    s.annuler()
    assert s.entrees == [(3732, 640, 300)]


def test_annuler_sur_session_vide_ne_plante_pas():
    s = SessionAnnotation()
    s.annuler()
    assert len(s) == 0


def test_supprimer_retire_la_ligne_demandee():
    s = SessionAnnotation()
    s.ajouter(3732)
    s.ajouter(3800)
    s.ajouter(3900)
    s.supprimer(1)
    assert [f for f, _, _ in s.entrees] == [3732, 3900]


def test_vers_texte_se_relit_par_le_banc(tmp_path):
    s = SessionAnnotation()
    s.ajouter(3800)
    s.ajouter(3732, 640, 300)
    chemin = tmp_path / "ann.txt"
    chemin.write_text(s.vers_texte(), encoding="utf-8")
    assert lire_annotations(chemin) == [3732, 3800]


def test_aller_retour_texte_garde_les_positions():
    s = SessionAnnotation()
    s.ajouter(3732, 640, 300)
    s.ajouter(3800)
    reprise = SessionAnnotation.depuis_texte(s.vers_texte())
    assert reprise.entrees == s.entrees


def test_depuis_texte_accepte_un_fichier_sans_commentaires():
    s = SessionAnnotation.depuis_texte("# tête\n3732\n3800  # hésitation\n")
    assert s.entrees == [(3732, None, None), (3800, None, None)]


# -- Fenêtre (offscreen, source vidéo factice) ------------------------------


class FausseSource:
    """Une image unie par frame, identifiable à sa valeur : pas de vidéo réelle."""

    fps = 30.0

    def __init__(self, debut: int, fin: int) -> None:
        self.debut = debut
        self.fin = fin
        self.index = debut

    def _image(self) -> np.ndarray:
        return np.full((720, 1280, 3), self.index % 256, dtype=np.uint8)

    def suivante(self):
        if self.index + 1 >= self.fin:
            return None
        self.index += 1
        return self._image()

    def precedente(self):
        if self.index - 1 < self.debut:
            return None
        self.index -= 1
        return self._image()

    def aller_a(self, index: int):
        self.index = index
        return self._image()

    def fermer(self) -> None:
        pass


@pytest.fixture
def application():
    return QApplication.instance() or QApplication([])


def construire(application, tmp_path, debut=3600, fin=3700, sortie=None):
    source = FausseSource(debut, fin)
    f = FenetreAnnotation(
        source=source,
        sortie=sortie if sortie is not None else tmp_path / "ann.txt",
        debut=debut,
        fin=fin,
    )
    f.resize(1200, 800)
    f.show()
    application.processEvents()
    return f


def cliquer_video(f, application):
    """Un vrai clic gauche au centre de la zone vidéo, comme l'opérateur."""
    w = f.video
    centre = w.rect().center()
    evenement = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(centre.x(), centre.y()),
        QPointF(centre.x(), centre.y()),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    w.mousePressEvent(evenement)
    application.processEvents()


def test_un_clic_enregistre_le_frame_affiche(application, tmp_path):
    f = construire(application, tmp_path)
    cliquer_video(f, application)
    assert [e[0] for e in f.session.entrees] == [3600]
    assert f.liste.count() == 1


def test_un_clic_met_la_lecture_en_pause(application, tmp_path):
    f = construire(application, tmp_path)
    f.bouton_lecture.click()
    assert f.en_cours is True
    cliquer_video(f, application)
    assert f.en_cours is False


def test_pas_avant_et_arriere_changent_le_frame_affiche(application, tmp_path):
    f = construire(application, tmp_path)
    f.bouton_avant.click()
    assert f.source.index == 3601
    f.bouton_arriere.click()
    assert f.source.index == 3600


def test_enregistrer_ecrit_un_fichier_relu_par_le_banc(application, tmp_path):
    sortie = tmp_path / "ann.txt"
    f = construire(application, tmp_path, sortie=sortie)
    cliquer_video(f, application)
    f.bouton_avant.click()
    cliquer_video(f, application)
    f.bouton_enregistrer.click()
    assert lire_annotations(sortie) == [3600, 3601]


def test_une_session_reprise_recharge_le_fichier_existant(application, tmp_path):
    sortie = tmp_path / "ann.txt"
    sortie.write_text("3732\n3800\n", encoding="utf-8")
    f = construire(application, tmp_path, sortie=sortie)
    assert len(f.session) == 2
    assert f.liste.count() == 2


def test_annuler_et_supprimer_mettent_la_liste_a_jour(application, tmp_path):
    f = construire(application, tmp_path)
    cliquer_video(f, application)
    f.bouton_avant.click()
    cliquer_video(f, application)
    f.bouton_annuler.click()
    assert f.liste.count() == 1
    f.liste.setCurrentRow(0)
    f.bouton_supprimer.click()
    assert f.liste.count() == 0
    assert len(f.session) == 0