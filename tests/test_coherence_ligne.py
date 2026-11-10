"""Cohérence moteur ↔ écran pendant une session ouverte (lot 1 de l'audit).

Une session vit de « Lancer » à « Stop »/fin de vidéo, PAUSE COMPRISE.
Pendant cet intervalle, l'écran et le moteur doivent raconter la MÊME
histoire : même ligne, même sens, même verrou. Les bugs audités :

- le sens pouvait être inversé en pause : la flèche verte pivotait à
  l'écran, le moteur gardait l'ancien sens ;
- tout changement de réglage reconstruisait la ligne DÉVERROUILLÉE :
  elle redevenait déplaçable en pause, et le moteur n'était pas prévenu ;
- le panneau restait actif pendant l'analyse : un seuil changé à chaud
  produisait un total hybride, moitié ancien réglage, moitié nouveau.

La règle testée ici : session ouverte = sens/ligne/réglages FIGÉS ;
toute reconstruction malgré tout préserve le verrou et resynchronise
le moteur (`compteur.ajuster_ligne`).
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from dataclasses import replace  # noqa: E402

import cv2  # noqa: E402
import numpy as np  # noqa: E402
import pytest  # noqa: E402

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from compteur.types import FrameResult  # noqa: E402
from interface.app import FenetrePrincipale  # noqa: E402


@pytest.fixture
def application():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def fenetre(application):
    f = FenetrePrincipale()
    yield f
    f.close()


class FauxCapture:
    """Une capture qui ne lit rien : seuls son existence comptent ici."""

    def get(self, prop):
        return 0.0

    def read(self):
        return False, None

    def set(self, prop, value):
        pass

    def release(self):
        pass


class FauxMoteur:
    """Moteur qui retient la ligne qu'on lui confie, pour vérifier le suivi."""

    def __init__(self):
        self.ligne = None

    def ajuster_ligne(self, ligne):
        self.ligne = ligne


class FauxCompteurFrames:
    """Compte une frame par appel, comme la vidéo synthétique de 5 frames."""

    def __init__(self):
        self.ligne = None

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
        from compteur.types import Resultat

        return Resultat(
            total=nb_frames,
            evenements=[],
            modele=modele,
            nb_frames=nb_frames,
            presents_max=0,
            secondes=secondes,
            duree_video_s=duree_video_s,
        )


@pytest.fixture
def video_synthetique(tmp_path):
    chemin = tmp_path / "coherence.mp4"
    auteur = cv2.VideoWriter(
        str(chemin), cv2.VideoWriter_fourcc(*"mp4v"), 25.0, (64, 48)
    )
    assert auteur.isOpened()
    for i in range(5):
        auteur.write(np.full((48, 64, 3), 20 + i * 10, dtype=np.uint8))
    auteur.release()
    return chemin


def avancer(fenetre, n=1):
    for _ in range(n):
        fenetre._tick()
        fenetre._afficher()


def test_sens_refuse_pendant_la_pause(fenetre):
    """En pause, la session est ouverte : inverser le sens ne doit RIEN faire.

    Sinon la flèche verte pivoterait à l'écran pendant que le moteur
    continuerait de compter dans l'ancien sens à la reprise.
    """
    f = fenetre
    f.definir_ligne((300.0, 20.0), (300.0, 460.0))
    f._ouvrir_session()
    f._basculer_pause()
    assert f._en_analyse is False and f._session_ouverte is True
    f._on_inverser_sens()
    assert f.config.sens == 1
    assert f.ligne.sens == 1


def test_boutons_sens_et_ligne_bloques_des_la_session_ouverte(fenetre):
    """« Sens » et « Tracer » sont grisés en analyse ET en pause."""
    f = fenetre
    f.cap = FauxCapture()
    f.definir_ligne((300.0, 20.0), (300.0, 460.0))
    f._ouvrir_session()
    f._maj_boutons()
    assert not f.btn_sens.isEnabled()
    assert not f.btn_ligne.isEnabled()
    f._basculer_pause()  # la pause ne rend pas la main sur la ligne
    assert not f.btn_sens.isEnabled()
    assert not f.btn_ligne.isEnabled()
    f.arreter()
    assert f.btn_sens.isEnabled()
    assert f.btn_ligne.isEnabled()


def test_reconstruction_en_session_garde_verrou_et_synchronise_moteur(fenetre):
    """Si la ligne est reconstruite session ouverte, le verrou survit et le
    moteur reçoit la NOUVELLE ligne — pas une copie écran orpheline."""
    f = fenetre
    f.definir_ligne((300.0, 20.0), (300.0, 460.0))
    f.compteur = FauxMoteur()
    f._ouvrir_session()
    f.ligne.verrouiller()
    f.compteur.ajuster_ligne(f.ligne)
    f._reconstruire_ligne_depuis_config()
    assert f.ligne.verrouillee
    assert f.compteur.ligne is f.ligne


def test_sur_config_en_session_garde_verrou_et_synchronise_moteur(fenetre):
    """Même contrat par le chemin large : un réglage propagé par `_sur_config`."""
    f = fenetre
    f.definir_ligne((300.0, 20.0), (300.0, 460.0))
    f.compteur = FauxMoteur()
    f._ouvrir_session()
    f.ligne.verrouiller()
    f.compteur.ajuster_ligne(f.ligne)
    f._sur_config(replace(f.config, epaisseur_bande=96))
    assert f.ligne.epaisseur == 96
    assert f.ligne.verrouillee
    assert f.compteur.ligne is f.ligne


def test_panneau_gele_pendant_la_session_meme_en_pause(fenetre):
    """Un seuil changé à chaud ferait un total hybride : le panneau est gelé
    tant que la session n'est pas close."""
    f = fenetre
    f._ouvrir_session()
    f._maj_boutons()
    assert not f.panneau.isEnabled()
    f._basculer_pause()
    assert not f.panneau.isEnabled()
    f.arreter()
    assert f.panneau.isEnabled()


def test_zone_deplacement_absente_en_pause_meme_apres_reglage(fenetre):
    """Le piège audités : réglage en pause → ligne reconstruite déverrouillée
    → bande re-déplaçable sous une session encore ouverte."""
    f = fenetre
    f.video.definir_image(np.zeros((240, 320, 3), dtype=np.uint8))
    f.definir_ligne((160.0, 20.0), (160.0, 220.0))
    f._ouvrir_session()
    f._basculer_pause()
    f._sur_config(replace(f.config, epaisseur_bande=96))
    assert f._zone_deplacement() is None


def test_glissement_inerte_en_pause_meme_apres_reglage(fenetre):
    f = fenetre
    f.video.definir_image(np.zeros((240, 320, 3), dtype=np.uint8))
    f.definir_ligne((160.0, 20.0), (160.0, 220.0))
    f._ouvrir_session()
    f._basculer_pause()
    f._sur_config(replace(f.config, epaisseur_bande=96))
    f._on_deplacement_video(10, 0)
    assert f.ligne.p1 == (160.0, 20.0)
    assert f.ligne.p2 == (160.0, 220.0)


def test_pause_sens_reprise_meme_total_et_meme_ligne(fenetre, video_synthetique):
    """Le scénario opérateur complet : pause, tentative d'inversion, reprise.

    Le total doit être celui d'un lancement direct (5 frames = 5), et
    l'écran et le moteur doivent désigner la MÊME ligne au même sens.
    """
    f = fenetre
    f.charger_video(str(video_synthetique))
    f.definir_ligne((32.0, 4.0), (32.0, 44.0))
    f.compteur = FauxCompteurFrames()
    f._ouvrir_session()
    f.compteur.ajuster_ligne(f.ligne)
    avancer(f, 1)  # premier lot : 4 frames
    f._basculer_pause()
    f._on_inverser_sens()  # tentative : doit être refusée
    f._basculer_pause()
    avancer(f, 2)  # fin de vidéo
    assert f.compteur_total == 5
    assert f.config.sens == 1
    assert f.ligne is f.compteur.ligne
    assert f.ligne.sens == f.config.sens