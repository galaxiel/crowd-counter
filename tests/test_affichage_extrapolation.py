"""Extrapolation d'affichage des tracks perdues (interface/overlay).

Pendant une perte brève du tracker (mouvement rapide, occultation), la
position exposée par le moteur est la dernière VUE : dessinée telle quelle,
elle fige le carré et le point à l'ancienne place — l'artefact signalé par
l'opérateur. `positions_extrapolees` produit la carte d'affichage : position
réelle, extrapolée (dernière vitesse × frames d'absence), ou masquée au-delà
de `FRAMES_EXTRAPOLATION`. Le comptage ne voit jamais cette carte : ces
tests vérifient la carte, le tracker, et le dessin.
"""

from __future__ import annotations

import numpy as np
import pytest

from compteur.types import Detection, Track
from interface.overlay import FRAMES_EXTRAPOLATION, dessiner, positions_extrapolees


def track(tid: int, bbox: tuple, absent: int = 0) -> Track:
    x1, y1, x2, y2 = bbox
    return Track(
        track_id=tid,
        center=((x1 + x2) / 2, (y1 + y2) / 2),
        bbox=bbox,
        age=5,
        confirmed=True,
        absent=absent,
    )


def detection(bbox: tuple) -> Detection:
    x1, y1, x2, y2 = bbox
    return Detection(x1=x1, y1=y1, x2=x2, y2=y2, score=0.9, class_id=0)


# -- positions_extrapolees -------------------------------------------------


def test_track_vue_cette_frame_est_a_sa_place_reelle():
    memoire: dict = {}
    positions = positions_extrapolees([track(1, (10, 10, 20, 20))], memoire)
    assert positions[1][0] == (10, 10, 20, 20)
    # la mémoire retient la position pour extrapoler les pertes à venir
    assert memoire[1] == ((10, 10, 20, 20), (10, 10, 20, 20))


def test_perte_breve_extrapole_dans_la_derniere_direction():
    memoire: dict = {}
    positions_extrapolees([track(1, (10, 10, 20, 20))], memoire)
    positions_extrapolees([track(1, (30, 10, 40, 20))], memoire)  # vitesse +20 x
    # deux frames sans détection : la position d'affichage continue
    positions = positions_extrapolees([track(1, (30, 10, 40, 20), absent=2)], memoire)
    assert positions[1][0] == (70, 10, 80, 20)


def test_perte_au_dela_de_la_borne_est_masquee():
    memoire: dict = {}
    positions_extrapolees([track(1, (10, 10, 20, 20))], memoire)
    positions_extrapolees([track(1, (30, 10, 40, 20))], memoire)
    positions = positions_extrapolees(
        [track(1, (30, 10, 40, 20), absent=FRAMES_EXTRAPOLATION + 1)], memoire
    )
    assert 1 not in positions


def test_nouvelle_track_perdue_sans_vitesse_est_masquee():
    """Apparue une frame puis perdue : rien à extrapoler, rien à figer."""
    memoire: dict = {}
    positions_extrapolees([track(1, (10, 10, 20, 20))], memoire)
    positions = positions_extrapolees([track(1, (10, 10, 20, 20), absent=1)], memoire)
    assert 1 not in positions


def test_re_acquise_recolle_a_la_vraie_position():
    memoire: dict = {}
    positions_extrapolees([track(1, (10, 10, 20, 20))], memoire)
    positions_extrapolees([track(1, (30, 10, 40, 20))], memoire)
    positions_extrapolees([track(1, (30, 10, 40, 20), absent=2)], memoire)
    positions = positions_extrapolees([track(1, (55, 12, 65, 22))], memoire)
    assert positions[1][0] == (55, 12, 65, 22)
    # la vitesse est de nouveau celle des deux DERNIÈRES vues réelles
    positions = positions_extrapolees([track(1, (55, 12, 65, 22), absent=1)], memoire)
    assert positions[1][0] == (80, 14, 90, 24)


def test_memoire_ne_bouge_pas_pendant_une_perte():
    memoire: dict = {}
    positions_extrapolees([track(1, (10, 10, 20, 20))], memoire)
    positions_extrapolees([track(1, (30, 10, 40, 20))], memoire)
    avant = dict(memoire)
    positions_extrapolees([track(1, (30, 10, 40, 20), absent=1)], memoire)
    assert memoire == avant


# -- le tracker expose bien `absent` ---------------------------------------


def test_le_tracker_compte_les_frames_d_absence():
    from compteur.config import Config
    from compteur.tracker import Tracker

    cfg = Config(seuil_matching=0.15)
    tr = Tracker(cfg)
    # frames_confirmation vaut 3 par défaut : trois vues avant confirmation.
    tr.mettre_a_jour([detection((10, 10, 20, 20))], 0)
    tr.mettre_a_jour([detection((12, 10, 22, 20))], 1)
    tr.mettre_a_jour([detection((14, 10, 24, 20))], 2)
    vides = tr.mettre_a_jour([], 3)
    assert [t.absent for t in vides] == [1]
    vides = tr.mettre_a_jour([], 4)
    assert [t.absent for t in vides] == [2]
    revus = tr.mettre_a_jour([detection((16, 10, 26, 20))], 5)
    assert [t.absent for t in revus] == [0]


# -- dessin ----------------------------------------------------------------


def test_dessiner_masque_une_track_absente_de_la_carte():
    """Sans la track dans `positions`, aucun point n'est peint pour elle."""
    img = np.zeros((60, 60, 3), np.uint8)
    resultat = type("R", (), {"image": img, "detections": [], "tracks": [track(1, (10, 10, 20, 20))]})()
    peinte = dessiner(img, resultat, positions={})
    # COULEUR_TRACK = (200, 200, 80) : rien de tel à l'écran
    assert not np.any(np.all(peinte == (200, 200, 80), axis=-1))
    peinte = dessiner(img, resultat, positions={1: ((10, 10, 20, 20), (15, 15))})
    assert np.any(np.all(peinte == (200, 200, 80), axis=-1))


def test_dessiner_sans_carte_reste_comme_avant():
    """Le paramètre est optionnel : l'appel historique ne change rien."""
    img = np.zeros((60, 60, 3), np.uint8)
    resultat = type("R", (), {"image": img, "detections": [], "tracks": [track(1, (10, 10, 20, 20))]})()
    peinte = dessiner(img, resultat)
    assert np.any(np.all(peinte == (200, 200, 80), axis=-1))


@pytest.mark.parametrize("absent", [1, 2, 3])
def test_le_dessin_extrapole_utilise_le_centre_de_la_carte(absent):
    img = np.zeros((200, 200, 3), np.uint8)
    resultat = type(
        "R", (), {"image": img, "detections": [], "tracks": [track(1, (10, 10, 20, 20), absent=absent)]}
    )()
    memoire: dict = {1: ((10, 10, 20, 20), (20, 10, 30, 20))}
    positions = positions_extrapolees(resultat.tracks, memoire)
    peinte = dessiner(img, resultat, positions=positions)
    cx, cy = int(positions[1][1][0]), int(positions[1][1][1])
    # le point est peint au centre EXTRAPOLÉ, pas au centre réel de la track
    assert tuple(peinte[cy, cx]) == (200, 200, 80)
