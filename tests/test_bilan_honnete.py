"""Bilan honnête (lot 2 de l'audit) : durée, temps de calcul, avertissements.

Trois mensonges audités, trois contrats :

1. Une frame corrompue arrête la lecture comme une fin de vidéo : l'écran
   annonçait « Terminé » sur une analyse tronquée. Une lecture arrêtée
   AVANT le nombre de frames annoncé doit être dite « incomplète ».
2. `secondes` recevait la durée de la VIDÉO : le temps de calcul réel
   (pauses déduites) et la durée vidéo sont deux grandeurs distinctes,
   et l'avertissement « analyse plus lente que le temps réel » ne peut
   vivre qu'avec le vrai temps de calcul.
3. Les avertissements de fiabilité étaient calculés puis jetés : le
   récapitulatif doit les AFFICHER (« ce 0 ne doit pas être publié »).
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import time  # noqa: E402

import cv2  # noqa: E402
import numpy as np  # noqa: E402
import pytest  # noqa: E402

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from compteur.rapport import statistiques  # noqa: E402
from compteur.types import Evenement, FrameResult, Resultat  # noqa: E402
from interface.app import FenetrePrincipale  # noqa: E402
from interface.recap import PanneauRecap  # noqa: E402


@pytest.fixture
def application():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def fenetre(application):
    f = FenetrePrincipale()
    yield f
    f.close()


class CompteurEspion:
    """Retient les durées reçues par `resultat` : c'est là que le mensonge se voit."""

    def __init__(self):
        self.ligne = None
        self.dernier = None

    def ajuster_ligne(self, ligne):
        self.ligne = ligne

    def traiter_frame(self, img, index, ts):
        return FrameResult(
            image=img,
            total=index + 1,
            presents=0,
            frame_index=index,
            timestamp_s=ts,
            evenements=[],
        )

    def resultat(self, modele, nb_frames, secondes, duree_video_s=0.0):
        self.dernier = {"secondes": secondes, "duree_video_s": duree_video_s}
        return Resultat(
            total=nb_frames,
            evenements=[],
            modele=modele,
            nb_frames=nb_frames,
            presents_max=0,
            secondes=secondes,
            duree_video_s=duree_video_s,
        )


class CaptureInterrompue:
    """Délègue à une vraie capture, puis échoue : la frame corrompue du terrain."""

    def __init__(self, cap, lectures_max):
        self.cap = cap
        self.lectures_max = lectures_max
        self.lectures = 0

    def read(self):
        self.lectures += 1
        if self.lectures > self.lectures_max:
            return False, None
        return self.cap.read()

    def get(self, prop):
        return self.cap.get(prop)

    def set(self, prop, valeur):
        return self.cap.set(prop, valeur)

    def release(self):
        self.cap.release()


def ecrire_video(chemin, nb_frames):
    auteur = cv2.VideoWriter(
        str(chemin), cv2.VideoWriter_fourcc(*"mp4v"), 25.0, (64, 48)
    )
    assert auteur.isOpened()
    for i in range(nb_frames):
        auteur.write(np.full((48, 64, 3), 20 + (i % 20) * 10, dtype=np.uint8))
    auteur.release()


def avancer(fenetre, n=1):
    for _ in range(n):
        fenetre._tick()
        fenetre._afficher()


def test_lecture_interrompue_annonce_analyse_incomplete(fenetre, tmp_path):
    """2 frames lues sur 5 annoncées : « Terminé » serait un mensonge."""
    chemin = tmp_path / "coupee.mp4"
    ecrire_video(chemin, 5)
    f = fenetre
    f.charger_video(str(chemin))
    f.definir_ligne((32.0, 4.0), (32.0, 44.0))
    f.compteur = CompteurEspion()
    f.cap = CaptureInterrompue(f.cap, 2)
    f._ouvrir_session()
    avancer(f, 5)
    assert not f._session_ouverte
    assert "incomplète" in f.label_statut.text()
    assert "Terminé" not in f.label_statut.text()
    assert not f.recap.avertissements.isHidden()
    assert "incomplète" in f.recap.avertissements.text()


def test_secondes_et_duree_video_distinctes_au_bilan(fenetre, tmp_path):
    """100 frames à 25 i/s = 4 s de vidéo, traitées en bien moins de 2 s.

    Le débit affiché reste celui de la VIDÉO (100 personnes / 4 s = 1500/min),
    jamais celui du temps de calcul.
    """
    chemin = tmp_path / "longue.mp4"
    ecrire_video(chemin, 100)
    f = fenetre
    f.charger_video(str(chemin))
    f.definir_ligne((32.0, 4.0), (32.0, 44.0))
    f.compteur = CompteurEspion()
    f._ouvrir_session()
    for _ in range(40):
        avancer(f)
        if not f._session_ouverte:
            break
    assert f.frames == 100
    assert f.compteur.dernier["duree_video_s"] == pytest.approx(4.0)
    assert f.compteur.dernier["secondes"] < 2.0
    assert "1500.0/min" in f.label_statut.text()


def test_pause_deduite_du_temps_de_calcul(fenetre):
    """Arrêtée PENDANT la pause : le temps de pause ne compte pas comme calcul."""
    f = fenetre
    f.compteur = CompteurEspion()
    f._ouvrir_session()
    f._debut_analyse = time.monotonic() - 2.0
    f._basculer_pause()  # pause immédiate : ~2 s de calcul, pas plus
    f.arreter()
    assert 1.5 <= f.compteur.dernier["secondes"] <= 2.5


def test_recap_affiche_les_avertissements_de_fiabilite(application):
    """« 0 compté » avec une foule présente : l'avertissement doit être LU."""
    panneau = PanneauRecap()
    resultat = Resultat(
        total=0,
        evenements=[],
        modele="tetes-medium.onnx",
        nb_frames=100,
        presents_max=3,
        presents_moyen=2.5,
        secondes=10.0,
    )
    panneau.afficher(resultat)
    assert not panneau.avertissements.isHidden()
    assert "ne doit pas être publié" in panneau.avertissements.text()
    panneau.effacer()
    assert panneau.avertissements.isHidden()


def test_recap_sans_avertissement_quand_coherent(application):
    """Un bilan cohérent n'affiche aucun bandeau : pas d'alerte décorative."""
    panneau = PanneauRecap()
    resultat = Resultat(
        total=2,
        evenements=[
            Evenement(frame=1, timestamp_s=10.0, x=1.0, y=1.0, track_id=1),
            Evenement(frame=2, timestamp_s=70.0, x=1.0, y=1.0, track_id=2),
        ],
        modele="tetes-medium.onnx",
        nb_frames=3000,
        presents_max=2,
        presents_moyen=1.0,
        secondes=10.0,
        duree_video_s=120.0,
    )
    panneau.afficher(resultat)
    assert panneau.avertissements.isHidden()


def test_fenetre_de_pic_sur_duree_video_pas_temps_calcul():
    """Le pic se mesure sur la durée de la VIDÉO : un GPU rapide ne rétrécit
    pas la fenêtre d'observation au temps de calcul."""
    resultat = Resultat(
        total=2,
        evenements=[
            Evenement(frame=1, timestamp_s=10.0, x=1.0, y=1.0, track_id=1),
            Evenement(frame=2, timestamp_s=70.0, x=1.0, y=1.0, track_id=2),
        ],
        modele="m",
        nb_frames=3000,
        presents_max=2,
        presents_moyen=1.0,
        secondes=0.5,
        duree_video_s=120.0,
    )
    stats = statistiques(resultat)
    assert stats["debit_max_fenetre_s"] == 60.0