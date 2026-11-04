"""Tests du glisser-déposer d'une vidéo sur la fenêtre.

Le contrat : le dépôt accepte EXACTEMENT ce que le sélecteur de fichier
accepte (une seule vidéo, extensions de `FILTRES_VIDEOS`), refuse pendant
une analyse (un fichier lâché ne doit pas tuer un comptage en route), et
délègue le chargement réel à `charger_video` — qui affiche elle-même
l'erreur d'un fichier illisible. Les événements Qt sont simulés par un
bateau simple : le code testé n'utilise que `mimeData()`,
`acceptProposedAction()` et `ignore()`.
"""

import re

import cv2
import numpy as np
import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QMimeData, QUrl  # noqa: E402

from interface.app import (  # noqa: E402
    EXTENSIONS_VIDEO,
    FILTRES_VIDEOS,
    FenetrePrincipale,
)

FPS_SYNTHETIQUE = 25.0


@pytest.fixture
def application():
    """Une QApplication unique pour toute la session (Qt n'aime pas deux fois)."""
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


class _EvenementFaux:
    """Événement de drag/drop minimal — l'interface n'utilise que ces trois-là."""

    def __init__(self, mime: QMimeData) -> None:
        self._mime = mime
        self.accepte = False
        self.refuse = False

    def mimeData(self):
        return self._mime

    def acceptProposedAction(self):
        self.accepte = True

    def ignore(self):
        self.refuse = True


def _mime_avec(*chemins: str) -> QMimeData:
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(c) for c in chemins])
    return mime


# -- Validation du dépôt ---------------------------------------------------


def test_une_video_est_acceptee(application):
    fenetre = FenetrePrincipale()
    try:
        chemin = fenetre._chemin_de_la_depose(_mime_avec("D:/scenes/manif.mp4"))
        assert chemin == "D:/scenes/manif.mp4"
    finally:
        fenetre.close()


def test_extension_majuscule_est_acceptee(application):
    fenetre = FenetrePrincipale()
    try:
        assert fenetre._chemin_de_la_depose(_mime_avec("D://VIDEO.MP4")) is not None
    finally:
        fenetre.close()


def test_fichier_non_video_refuse(application):
    fenetre = FenetrePrincipale()
    try:
        assert fenetre._chemin_de_la_depose(_mime_avec("D:/notes.txt")) is None
        assert fenetre._chemin_de_la_depose(_mime_avec("D:/image.png")) is None
    finally:
        fenetre.close()


def test_plusieurs_fichiers_refuses(application):
    fenetre = FenetrePrincipale()
    try:
        assert fenetre._chemin_de_la_depose(
            _mime_avec("D:/a.mp4", "D:/b.mp4")
        ) is None
    finally:
        fenetre.close()


def test_sans_url_refuse(application):
    fenetre = FenetrePrincipale()
    try:
        assert fenetre._chemin_de_la_depose(QMimeData()) is None
    finally:
        fenetre.close()


def test_pendant_une_analyse_tout_est_refuse(application):
    """Un dépôt ne doit pas arrêter un comptage en route — même une vidéo valide."""
    fenetre = FenetrePrincipale()
    try:
        fenetre._en_analyse = True
        assert fenetre._chemin_de_la_depose(_mime_avec("D:/a.mp4")) is None
    finally:
        fenetre._en_analyse = False
        fenetre.close()


def test_extensions_alignees_sur_le_selecteur():
    """Le dépôt et le sélecteur de fichier doivent dire la même chose."""
    ext_filtre = set(re.findall(r"\*\.(\w+)", FILTRES_VIDEOS))
    ext_depot = {e.lstrip(".") for e in EXTENSIONS_VIDEO}
    assert ext_depot == ext_filtre


# -- Événements ------------------------------------------------------------


def test_drag_enter_accepte_et_refuse(application):
    fenetre = FenetrePrincipale()
    try:
        entre = _EvenementFaux(_mime_avec("D:/a.mp4"))
        fenetre.dragEnterEvent(entre)
        assert entre.accepte and not entre.refuse

        entre = _EvenementFaux(_mime_avec("D:/a.txt"))
        fenetre.dragEnterEvent(entre)
        assert entre.refuse and not entre.accepte
    finally:
        fenetre.close()


def test_drop_charge_la_video(application, tmp_path):
    fenetre = FenetrePrincipale()
    try:
        chemin = tmp_path / "scene.mp4"
        auteur = cv2.VideoWriter(
            str(chemin), cv2.VideoWriter_fourcc(*"mp4v"), FPS_SYNTHETIQUE, (64, 48)
        )
        assert auteur.isOpened()
        for _ in range(10):
            auteur.write(np.zeros((48, 64, 3), dtype=np.uint8))
        auteur.release()

        fenetre.dropEvent(_EvenementFaux(_mime_avec(str(chemin))))
        assert fenetre.video_finiment == chemin
        assert fenetre.cap is not None
    finally:
        fenetre.arreter()
        fenetre.close()


def test_drop_de_fichier_illisible_ne_plante_pas(application, tmp_path):
    fenetre = FenetrePrincipale()
    try:
        faux = tmp_path / "faux.mp4"
        faux.write_bytes(b"ceci n'est pas une video")
        fenetre.dropEvent(_EvenementFaux(_mime_avec(str(faux))))
        assert fenetre.video_finiment is None
    finally:
        fenetre.close()
