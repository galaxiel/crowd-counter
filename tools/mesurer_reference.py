"""Harnais de mesure : décompte sur le segment de RÉFÉRENCE de la vidéo de test.

C'est l'outil de non-régression du moteur. Il tourne le VRAI chemin de
production (`Compteur.traiter_lot`, groupé par `TAILLE_LOT_DETECTION`) sur un
segment borné de `D:\\Bureau\\manif_test.mp4`, avec la ligne verticale x=640 et
`sens=-1` — la seule combinaison qui compte (AGENTS.md : `sens=+1` ne compte
RIEN sur cette vidéo, tous les diagnostics faits avec `+1` sont faux).

Chaque modification du moteur se mesure ICI avant/après, jamais à l'aveugle.

Usage :
    /c/Python311/python tools/mesurer_reference.py            # segment par défaut
    /c/Python311/python tools/mesurer_reference.py 0 3000     # segment libre
    /c/Python311/python tools/mesurer_reference.py 3600 4500 --modele tetes-nano.pt
"""

from __future__ import annotations

import argparse
import pathlib
import sys
import time

# Le script est lancé depuis `tools/` : le dépôt doit être dans le chemin pour
# que `compteur` soit importable.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import cv2  #: noqa: E402

from compteur.compteur import TAILLE_LOT_DETECTION, Compteur  #: noqa: E402
from compteur.config import (  #: noqa: E402
    BANDE_APRES_PX,
    BANDE_AVANT_PX,
    Config,
)
from compteur.detecteur import Detecteur, charger_modele  #: noqa: E402
from compteur.ligne import Ligne  #: noqa: E402
from compteur.tracker import Tracker  #: noqa: E402

VIDEO_REF = r"D:\Bureau\manif_test.mp4"
LIGNE_REF = (640.0, 0.0, 640.0, 720.0)  #: verticale au milieu de l'image
#: Segment de référence (AGENTS.md) : frames 3600-4500, soit 2:00 -> 2:30 à 30 fps.
DEBUT_REF, FIN_REF = 3600, 4500


def mesurer(
    chemin: str,
    debut: int,
    fin: int,
    modele: str | None = None,
    fenetre_lissage: int = 1,
    verbose: bool = True,
) -> dict:
    """Décompte `fin - debut` frames par le chemin groupé, et chronomètre.

    Retourne un dict avec le compte, le nombre de frames réellement traitées,
    le temps écoulé et le débit. ``modele``/``fenetre_lissage`` permettent de
    tester une variable à la fois sans toucher au reste des défauts.
    """
    kwargs = {}
    if modele is not None:
        kwargs["modele"] = modele
    if fenetre_lissage != 1:
        kwargs["fenetre_lissage"] = fenetre_lissage
    config = Config(ligne=LIGNE_REF, sens=-1, **kwargs)

    detecteur = Detecteur(charger_modele(config.modele, config.peripherique), config)
    compteur = Compteur(config, detecteur, Tracker(config))
    compteur.ajuster_ligne(
        Ligne(
            (LIGNE_REF[0], LIGNE_REF[1]),
            (LIGNE_REF[2], LIGNE_REF[3]),
            epaisseur=config.epaisseur_bande,
            sens=config.sens,
            hysteresis=config.frames_hysteresis,
            bande_avant_px=BANDE_AVANT_PX,
            bande_apres_px=BANDE_APRES_PX,
        )
    )

    cap = cv2.VideoCapture(chemin)
    if not cap.isOpened():
        raise FileNotFoundError(f"vidéo illisible : {chemin}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    # Saut jusqu'au début du segment : on ne décode pas les frames d'avant.
    if debut > 0:
        cap.set(cv2.CAP_PROP_POS_FRAMES, debut)

    debut_t = time.time()
    index = debut
    while index < fin:
        lot = []
        while len(lot) < TAILLE_LOT_DETECTION and index < fin:
            ok, img = cap.read()
            if not ok:
                break
            lot.append((img, index, index / fps))
            index += 1
        if not lot:
            break
        compteur.traiter_lot(lot)
    ecoule = time.time() - debut_t
    cap.release()

    traitees = index - debut
    return {
        "total": compteur.total,
        "frames": traitees,
        "secondes": ecoule,
        "ips": traitees / ecoule if ecoule > 0 else 0.0,
        "presents_max": compteur.presents_max,
        "modele": config.modele,
        "segment": (debut, index),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("debut", nargs="?", type=int, default=DEBUT_REF)
    parser.add_argument("fin", nargs="?", type=int, default=FIN_REF)
    parser.add_argument("--modele", default=None)
    parser.add_argument("--lissage", type=int, default=1)
    args = parser.parse_args()

    r = mesurer(VIDEO_REF, args.debut, args.fin, args.modele, args.lissage)
    duree_video = r["frames"] / 30.0
    print(
        f"segment {r['segment'][0]}-{r['segment'][1]} "
        f"({r['frames']} frames, {duree_video:.1f} s de vidéo)"
    )
    print(f"modèle   : {r['modele']}")
    print(f"lissage  : K={args.lissage}")
    print(f"COMPTÉ   : {r['total']} personnes")
    print(f"presents max : {r['presents_max']}")
    print(f"temps    : {r['secondes']:.1f} s  ({r['ips']:.1f} frames/s)")


if __name__ == "__main__":
    main()
