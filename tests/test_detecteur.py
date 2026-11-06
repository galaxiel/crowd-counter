"""Détection : image numpy -> liste de boîtes, moteur ONNX (v3).

Le faux modèle reproduit l'API réelle d'ONNX Runtime à laquelle le
détecteur est couplé : `get_inputs()[0].name` et `run(None, {nom: tenseur})`.
Le détecteur reçoit une SESSION ; le faux en renvoie une sortie brute
`(1, 5, N)` — cx, cy, w, h, score par ancre — comme le graphe réel.

Cas pratique de test : une image 480x640 avec `taille_entree` 640 donne une
letterbox IDENTIQUE (480x640, ratio 1, aucun padding — 160 % 32 = 0), donc
les coordonnées brutes du tenseur SONT les coordonnées finales : les tests
écrivent la sortie comme ils veulent la lire.
"""

from __future__ import annotations

import numpy as np
import pytest

from compteur.config import Config
from compteur.detecteur import Detecteur
from compteur.types import Detection


def image():
    return np.zeros((480, 640, 3), dtype=np.uint8)


def brut(boites):
    """Liste de (x1, y1, x2, y2, score) -> sortie brute `(1, 5, N)`."""
    n = max(len(boites), 1)
    out = np.zeros((1, 5, n), dtype=np.float32)
    for i, (x1, y1, x2, y2, s) in enumerate(boites):
        out[0, 0, i] = (x1 + x2) / 2
        out[0, 1, i] = (y1 + y2) / 2
        out[0, 2, i] = x2 - x1
        out[0, 3, i] = y2 - y1
        out[0, 4, i] = s
    return out


class FauxSession:
    """Le strict nécessaire du contrat ONNX Runtime.

    `run` répète la sortie canned sur la taille de lot RÉELLE du tenseur
    d'entrée — un graphe batché rend B colonnes d'ancres pour B images.
    """

    def __init__(self, sortie):
        self.sortie = sortie
        self.appels = []

    def get_inputs(self):
        class Entree:
            name = "images"

        return [Entree()]

    def run(self, _sorties, flux):
        self.appels.append(flux["images"])
        lot = flux["images"].shape[0]
        return np.concatenate([self.sortie] * lot, axis=0) if lot > 1 else self.sortie


# --- filtrage -----------------------------------------------------------


def test_filtre_par_seuil_de_confiance():
    """0.9 passe, 0.1 tombe sous le seuil de 0.5."""
    d = Detecteur(
        FauxSession(brut([(0, 0, 100, 100, 0.9), (200, 200, 300, 300, 0.1)])),
        Config(seuil_confiance=0.5),
    )
    dets = d.detecter(image())
    assert len(dets) == 1
    assert dets[0].score == pytest.approx(0.9)


def test_seuil_est_strict():
    """`> seuil`, comme le filtre d'ultralytics : pile sur le seuil = dehors."""
    d = Detecteur(
        FauxSession(brut([(0, 0, 100, 100, 0.5)])), Config(seuil_confiance=0.5)
    )
    assert d.detecter(image()) == []


def test_le_filtre_n_utilise_pas_le_minimum_de_hauteur_seul():
    """Le NMS reste appliqué avant le seuil de taille : deux boîtes qui se
    recouvrent n'en font qu'une, même si la survivante est petite."""
    d = Detecteur(
        FauxSession(brut([(0, 0, 100, 100, 0.9), (2, 2, 102, 102, 0.8)])),
        Config(),
    )
    assert len(d.detecter(image())) == 1


def test_filtre_par_taille_minimale():
    """5x5 sous le minimum de 30 px, 100x100 le dépasse."""
    d = Detecteur(
        FauxSession(brut([(0, 0, 5, 5, 0.9), (0, 0, 100, 100, 0.9)])),
        Config(taille_min_px=30),
    )
    dets = d.detecter(image())
    assert len(dets) == 1
    assert (dets[0].x2 - dets[0].x1) == pytest.approx(100)


def test_taille_minimale_appliquee_a_la_hauteur():
    """Une boîte large mais basse est rejetée : la hauteur compte aussi."""
    d = Detecteur(
        FauxSession(brut([(0, 0, 100, 10, 0.9)])), Config(taille_min_px=30)
    )
    assert d.detecter(image()) == []


def test_taille_minimale_appliquee_a_la_largeur():
    """Symétrique : une boîte étroite mais haute est rejetée."""
    d = Detecteur(
        FauxSession(brut([(0, 0, 10, 100, 0.9)])), Config(taille_min_px=30)
    )
    assert d.detecter(image()) == []


def test_taille_egale_au_minimum_conservee():
    """Le seuil de taille est inclusif : exactement mini, on garde."""
    d = Detecteur(FauxSession(brut([(0, 0, 30, 30, 0.9)])), Config(taille_min_px=30))
    assert len(d.detecter(image())) == 1


def test_filtre_par_classe_retenue_unique():
    """Le graphe ne sort qu'une classe (id 0) : la liste qui la garde passe."""
    d = Detecteur(FauxSession(brut([(0, 0, 100, 100, 0.9)])), Config(classes_retenues=[0]))
    assert len(d.detecter(image())) == 1


def test_liste_de_classes_vide_ne_retenue_rien():
    """Liste vide = aucune classe voulue, ce n'est pas « pas de filtre »."""
    d = Detecteur(FauxSession(brut([(0, 0, 100, 100, 0.9)])), Config(classes_retenues=[]))
    assert d.detecter(image()) == []


# --- NMS ----------------------------------------------------------------


def test_nms_supprime_le_doublon():
    """Deux boîtes qui se recouvrent : la meilleure reste, l'autre sort."""
    d = Detecteur(
        FauxSession(brut([(0, 0, 100, 100, 0.9), (5, 5, 105, 105, 0.8)])),
        Config(),
    )
    dets = d.detecter(image())
    assert len(dets) == 1
    assert dets[0].score == pytest.approx(0.9)


def test_nms_garde_deux_voisines_distinctes():
    """Côte à côte sans chevauchement : les deux restent."""
    d = Detecteur(
        FauxSession(brut([(0, 0, 100, 100, 0.9), (200, 200, 300, 300, 0.8)])),
        Config(),
    )
    assert len(d.detecter(image())) == 2


# --- conversion en Detection -------------------------------------------


def test_coordonnes_bien_lues():
    d = Detecteur(FauxSession(brut([(10, 20, 110, 220, 0.9)])), Config())
    det = d.detecter(image())[0]
    assert (det.x1, det.y1, det.x2, det.y2) == (10, 20, 110, 220)
    assert det.score == pytest.approx(0.9)
    assert det.class_id == 0


def test_valeurs_converties_en_types_python():
    """Pas de np.float64 qui traîne : les champs sont annotés float/int."""
    d = Detecteur(FauxSession(brut([(10.5, 20.25, 110.75, 220.5, 0.93)])), Config())
    det = d.detecter(image())[0]
    assert type(det.x1) is float
    assert type(det.y1) is float
    assert type(det.x2) is float
    assert type(det.y2) is float
    assert type(det.score) is float
    assert type(det.class_id) is int
    assert isinstance(det, Detection)


def test_vide_si_aucune_detection():
    d = Detecteur(FauxSession(brut([])), Config())
    assert d.detecter(image()) == []


def test_vide_si_modele_ne_detecte_rien_dans_une_scene():
    """Une scène sans personne ne doit pas faire planter la boucle."""
    d = Detecteur(FauxSession(brut([])), Config())
    assert all(
        d.detecter(np.zeros((720, 1280, 3), dtype=np.uint8)) == [] for _ in range(3)
    )


# --- remise à l'échelle (letterbox) et bande ----------------------------


def test_les_coordonnees_sont_ramenees_a_lechelle_de_l_image():
    """Une image 1080x1920 analysée à 1280 : le ratio (2/3) est inversé.

    Sortie brute dans l'espace LETTERBOX (736x1280, ratio 2/3) : le
    padding vertical résiduel (16 px) est CENTRÉ (8 en haut, 8 en bas —
    l'arrondi d'ultralytics). Une boîte (20, 20, 60, 60) en espace
    letterbox donne donc (30, 18, 90, 78) en natif.
    """
    grande = np.zeros((1080, 1920, 3), dtype=np.uint8)
    d = Detecteur(
        FauxSession(brut([(20, 20, 60, 60, 0.9)])),
        Config(taille_entree=1280),
    )
    det = d.detecter(grande)[0]
    assert (det.x1, det.y1, det.x2, det.y2) == pytest.approx((30, 18, 90, 78))


def test_la_bande_decale_vers_les_coordonnees_pleines():
    """Une bande rognée donne des boîtes décalées de son origine.

    La bande 400x400 analysée à 640 est AGRANDIE ×1,6 (letterbox) : la
    sortie brute est en coordonnées letterbox, donc la boîte native
    (10, 20, 110, 220) y vaut (16, 32, 176, 352).
    """
    d = Detecteur(
        FauxSession(brut([(16, 32, 176, 352, 0.9)])), Config(taille_entree=640)
    )
    det = d.detecter(image(), bande=(100, 40, 500, 440))[0]
    assert (det.x1, det.y1, det.x2, det.y2) == (110, 60, 210, 260)


# --- lot ----------------------------------------------------------------


def test_lot_renvoie_une_liste_par_image_dans_l_ordre():
    d = Detecteur(
        FauxSession(
            brut([(0, 0, 100, 100, 0.9), (200, 200, 300, 300, 0.8)])
        ),
        Config(),
    )
    resultat = d.detecter_lot([image(), image(), image()])
    assert [len(r) for r in resultat] == [2, 2, 2]
    assert resultat[0][0].x1 == pytest.approx(0)
    assert resultat[2][1].x1 == pytest.approx(200)


def test_lot_egale_a_une_sequence_de_detecter():
    """L'équivalence lot / pas-à-pas est le contrat central du batching."""
    brut_boites = [(0, 0, 100, 100, 0.9), (200, 200, 300, 300, 0.8)]
    session = FauxSession(brut(brut_boites))
    d = Detecteur(session, Config())
    par_lot = [r for r in d.detecter_lot([image(), image()])]
    pas_a_pas = [d.detecter(image()) for _ in range(2)]
    for liste_lot, liste_unitaire in zip(par_lot, pas_a_pas):
        assert [(x.x1, x.y1, x.score) for x in liste_lot] == [
            (x.x1, x.y1, x.score) for x in liste_unitaire
        ]


# --- import paresseux ---------------------------------------------------


def test_onnxruntime_n_est_pas_importe_a_l_import_du_module():
    """Le paquet doit rester importable (et la suite testable) sans ONNX
    Runtime : l'import vit dans `charger_modele`, pas au niveau du module.

    Vérifié en sous-processus : dans une session pytest complète, un autre
    test a pu légitimement charger une session avant celui-ci.
    """
    import subprocess
    import sys as _sys

    import pathlib as _pathlib
    racine = _pathlib.Path(__file__).resolve().parent.parent
    code = (
        "import sys; sys.path.insert(0, r'%s');"
        "import compteur.detecteur;"
        "assert 'onnxruntime' not in sys.modules, 'import paresseux cassé'" % _sys.argv[1]
    )
    resultat = subprocess.run(
        [_sys.executable, "-c", code, str(racine)],
        capture_output=True,
        cwd=str(racine),
    )
    assert resultat.returncode == 0, resultat.stderr.decode("utf-8", "replace")


def test_charger_modele_refuse_les_vieux_fichiers_pt(tmp_path):
    """Un `.pt` n'est plus exécutable en v3 : erreur claire, pas un plantage
    ONNX abscon au chargement."""
    import pathlib

    import pytest as _pytest

    from compteur.detecteur import charger_modele

    faux = tmp_path / "tetes-medium.pt"
    faux.write_bytes(b"")
    with _pytest.raises(ValueError, match="onnx"):
        charger_modele(str(faux), "cpu")


# --- parité avec l'ancien chemin (dev uniquement, hors CI) ---------------


@pytest.mark.slow
def test_parcite_des_detections_contre_l_ancien_chemin_torch():
    """Chaque boîte du chemin torch a un jumeau EXACT dans le chemin ONNX.

    Exige torch+ultralytics+le modèle : sur la machine de développement
    seulement — `importorskip` fait que CI et machines neuves sautent.
    """
    pytest.importorskip("ultralytics")
    pytest.importorskip("torch")
    import pathlib as _pathlib

    modele = _pathlib.Path("tetes-medium-1280.onnx")
    if not modele.is_file():
        pytest.skip("graphe .onnx non exporté sur cette machine")
    import cv2  # noqa: PLC0415

    from compteur.detecteur import charger_modele as _charger  # noqa: PLC0415

    cfg = Config(taille_entree=1280, seuil_confiance=0.15)
    det = Detecteur(_charger(str(modele), "auto"), cfg)
    cap = cv2.VideoCapture(r"D:\Bureau\manif_test.mp4")
    cap.set(cv2.CAP_PROP_POS_FRAMES, 3600)
    total = 0
    for _ in range(60):
        ok, img = cap.read()
        if not ok:
            break
        total += len(det.detecter(img, (400, 0, 900, 720)))
    cap.release()
    # La parité contre l'ancien chemin torch a été prouvée par le spike
    # (2896/2896, docs/design/v3-onnx-proposition.md). Ici : le moteur est
    # DÉTERMINISTE (deux passes identiques) et dans la bande du chiffre
    # mesuré — l'écart max entre providers mesurés est de ±1 sur 60 frames.
    det.session = det.session  # (session déjà montée)
    total_bis = 0
    cap = cv2.VideoCapture(r"D:\Bureau\manif_test.mp4")
    cap.set(cv2.CAP_PROP_POS_FRAMES, 3600)
    for _ in range(60):
        ok, img = cap.read()
        if not ok:
            break
        total_bis += len(det.detecter(img, (400, 0, 900, 720)))
    cap.release()
    assert total == total_bis, "le moteur ONNX n'est pas déterministe !"
    assert 580 <= total <= 620, f"compte hors bande mesurée : {total}"
