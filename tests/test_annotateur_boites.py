"""Tests de l'annotateur de boîtes (tools/annotateur_boites.py).

Outil SÉPARÉ de l'annotateur au clic : ici on annote des têtes au moment où
elles sont VISIBLES (pas de ligne), par glissé, pour entraîner un détecteur.
Deux étages : la session de boîtes + export YOLO (pur), puis la fenêtre
(offscreen, source factice, détecteur factice).
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

import numpy as np  # noqa: E402
from PySide6.QtCore import QEvent, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QMouseEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from compteur.detecteur import Detection  # noqa: E402
from tools.annotateur_boites import (  # noqa: E402
    FenetreBoites,
    SessionBoites,
    ecrire_dataset,
)


# -- Session pure ----------------------------------------------------------


def test_ajouter_range_par_frame():
    s = SessionBoites()
    s.ajouter(3600, (10, 20, 30, 40))
    s.ajouter(3800, (50, 60, 70, 80))
    assert s.boites(3600) == [(10, 20, 30, 40)]
    assert s.boites(3800) == [(50, 60, 70, 80)]
    assert s.boites(4000) == []


def test_supprimer_retire_la_bonne_boite():
    s = SessionBoites()
    s.ajouter(3600, (10, 20, 30, 40))
    s.ajouter(3600, (50, 60, 70, 80))
    s.supprimer(3600, 0)
    assert s.boites(3600) == [(50, 60, 70, 80)]


def test_vers_yolo_normalise():
    s = SessionBoites()
    s.ajouter(3600, (320, 180, 640, 360))
    assert s.vers_yolo(3600, 1280, 720) == "0 0.375000 0.375000 0.250000 0.250000\n"


def test_aller_retour_yolo_garde_les_boites():
    s = SessionBoites()
    s.ajouter(3600, (100, 120, 220, 260))
    relu = SessionBoites.depuis_yolo(s.vers_yolo(3600, 1280, 720), 1280, 720)
    assert relu == [(100, 120, 220, 260)]


def test_depuis_yolo_ignore_lignes_vides():
    relu = SessionBoites.depuis_yolo("\n0 0.5 0.5 0.25 0.25\n", 1280, 720)
    assert relu == [(480, 270, 800, 450)]


def test_frames_annotees_triees_et_sans_frame_vide():
    s = SessionBoites()
    s.ajouter(3800, (1, 2, 3, 4))
    s.ajouter(3600, (1, 2, 3, 4))
    assert s.frames_annotees() == [3600, 3800]
    s.supprimer(3800, 0)
    assert s.frames_annotees() == [3600]


def test_ecrire_dataset_images_labels_yaml(tmp_path):
    s = SessionBoites()
    s.ajouter(3600, (320, 180, 640, 360))
    dossier = ecrire_dataset(
        s, tmp_path / "ds", lambda frame: np.zeros((720, 1280, 3), dtype=np.uint8)
    )
    assert (dossier / "images" / "frame_003600.jpg").exists()
    label = (dossier / "labels" / "frame_003600.txt").read_text(encoding="utf-8")
    assert label == s.vers_yolo(3600, 1280, 720)
    yaml = (dossier / "data.yaml").read_text(encoding="utf-8")
    assert "0: tete" in yaml


# -- Fenêtre (offscreen, source et détecteur factices) ----------------------


class FausseSource:
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


class FauxDetecteur:
    def detecter(self, img, bande=None):
        return [Detection(x1=100, y1=100, x2=200, y2=200, score=0.9, class_id=0)]


@pytest.fixture
def application():
    return QApplication.instance() or QApplication([])


def construire(application, tmp_path, detecteur=None, debut=3600, fin=3700):
    f = FenetreBoites(
        source=FausseSource(debut, fin),
        detecteur=detecteur,
        dossier=tmp_path / "ds",
        debut=debut,
        fin=fin,
    )
    f.resize(1200, 800)
    f.show()
    application.processEvents()
    return f


def glisser(f, application, p1, p2):
    w = f.video
    for type_, pos in (
        (QEvent.Type.MouseButtonPress, p1),
        (QEvent.Type.MouseMove, p2),
        (QEvent.Type.MouseButtonRelease, p2),
    ):
        ev = QMouseEvent(
            type_,
            QPointF(pos[0], pos[1]),
            QPointF(pos[0], pos[1]),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        if type_ == QEvent.Type.MouseButtonPress:
            w.mousePressEvent(ev)
        elif type_ == QEvent.Type.MouseMove:
            w.mouseMoveEvent(ev)
        else:
            w.mouseReleaseEvent(ev)
    application.processEvents()


def coins(f):
    c = f.video.rect().center()
    return (c.x() - 60, c.y() - 40), (c.x() + 60, c.y() + 40)


def test_glisse_trace_une_boite_en_pixels_image(application, tmp_path):
    f = construire(application, tmp_path)
    p1, p2 = coins(f)
    a = f.video.vers_pixels(p1[0], p1[1])
    b = f.video.vers_pixels(p2[0], p2[1])
    attendu = (min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1]))
    glisser(f, application, p1, p2)
    assert f.session.boites(3600) == [attendu]
    assert f.liste.count() == 1


def test_clic_sans_glisse_ne_cree_pas_de_boite(application, tmp_path):
    f = construire(application, tmp_path)
    c = f.video.rect().center()
    glisser(f, application, (c.x(), c.y()), (c.x(), c.y()))
    assert f.session.boites(3600) == []
    assert f.liste.count() == 0


def test_navigation_change_de_frame_et_la_liste(application, tmp_path):
    f = construire(application, tmp_path)
    glisser(f, application, *coins(f))
    f.bouton_avant.click()
    assert f.source.index == 3601
    assert f.liste.count() == 0
    f.bouton_arriere.click()
    assert f.source.index == 3600
    assert f.liste.count() == 1


def test_supprimer_retire_la_boite_selectionnee(application, tmp_path):
    f = construire(application, tmp_path)
    glisser(f, application, *coins(f))
    f.liste.setCurrentRow(0)
    f.bouton_supprimer.click()
    assert f.session.boites(3600) == []
    assert f.liste.count() == 0


def test_reprise_recharge_le_label_existant(application, tmp_path):
    labels = tmp_path / "ds" / "labels"
    labels.mkdir(parents=True)
    (labels / "frame_003600.txt").write_text("0 0.5 0.5 0.25 0.25\n", encoding="utf-8")
    f = construire(application, tmp_path)
    assert f.session.boites(3600) == [(480, 270, 800, 450)]
    assert f.liste.count() == 1


def test_proposer_ajoute_les_boites_du_detecteur(application, tmp_path):
    f = construire(application, tmp_path, detecteur=FauxDetecteur())
    f.bouton_proposer.click()
    assert f.session.boites(3600) == [(100, 100, 200, 200)]
    assert f.liste.count() == 1


def test_sans_detecteur_le_bouton_proposer_est_desactive(application, tmp_path):
    f = construire(application, tmp_path)
    assert f.bouton_proposer.isEnabled() is False


def test_enregistrer_ecrit_le_dataset(application, tmp_path):
    f = construire(application, tmp_path)
    glisser(f, application, *coins(f))
    f.bouton_enregistrer.click()
    dossier = tmp_path / "ds"
    assert (dossier / "images" / "frame_003600.jpg").exists()
    texte = (dossier / "labels" / "frame_003600.txt").read_text(encoding="utf-8")
    assert SessionBoites.depuis_yolo(texte, 1280, 720) == f.session.boites(3600)