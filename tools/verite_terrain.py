"""Banc de vérité terrain : annoter les franchissements à la main, puis comparER.

## Pourquoi ce fichier existe

Jusqu'ici, toute mesure se résume à un total agrégé (« 32 sur le segment »).
Un total ne dit PAS si le logiciel rate 3 personnes et en compte 3 autres
par-dessus : les erreurs compensées passent invisibles. Ce n'est pas une
théorie — c'est la raison pour laquelle `compteur/rapport.py` refuse
d'afficher un taux d'erreur : sans vérité terrain, il n'y en a pas.

Ce module apporte la vérité terrain en deux temps :

1. `extraire` produit une vidéo RALENTIE du segment de référence, avec la
   ligne de comptage et le NUMÉRO DE FRAME affichés en gros. L'opérateur la
   regarde, note les frames où une personne est sur la ligne, et les écrit
   dans un fichier texte — un chiffre par ligne.
2. `comparer` tourne le VRAI chemin de production sur le même segment,
   apparie les franchissements humains aux franchissements moteur (avec une
   tolérance, car l'humain et le moteur ne datent jamais le franchissement
   exactement pareil), et rend un diagnostic : ce qui a été vu des deux côtés,
   ce que le moteur a MANQUÉ, ce qu'il a compté en TROP.

## Pourquoi une vidéo ralentie et pas des images

900 images à feuilleter, c'est un supplice et l'œil se perd. Trois frames
écrites pour une (30 i/s → 10 i/s effectives) donnent le temps de voir le
franchissement, et le numéro de frame brûlé dans l'image supprime toute
ambiguïté sur « à quelle frame ». Un lecteur vidéo permet en plus d'avancer
frame par frame sur une image figée : le numéro affiché EST la frame à noter.

## Tolérance d'appariement

L'humain note la frame où la personne est SUR la ligne ; le moteur date
l'événement là où le suivi lisse franchit. L'écart est de quelques frames, et
il n'y a aucune raison de le faire disparaître : on apparie avec une tolérance
(par défaut 30 frames = 1 s) et on affiche les deux chiffres. Une tolérance à
zéro fabriquerait des « manquants » qui ne sont que des décalages d'horloge.

Usage :
    /c/Python311/python tools/verite_terrain.py extraire
    /c/Python311/python tools/verite_terrain.py extraire 3600 4500
    /c/Python311/python tools/verite_terrain.py comparer verite_terrain/segment_3600-4500.txt
    /c/Python311/python tools/verite_terrain.py comparer ... --tolerance 45
    /c/Python311/python tools/verite_terrain.py comparer ... --imgsz 640
"""

from __future__ import annotations

import argparse
import pathlib
import sys

# Le script est lancé depuis `tools/` : le dépôt doit être dans le chemin pour
# que `compteur` soit importable, et `tools/` lui-même pour que l'import
# paresseux de `mesurer_reference` fonctionne aussi depuis les tests.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from compteur.config import (  #: noqa: E402
    BANDE_APRES_PX,
    BANDE_AVANT_PX,
    Config,
    taille_entree_automatique,
)
from compteur.ligne import Ligne  #: noqa: E402

#: Vidéo et géométrie de référence — alignées sur `tools/mesurer_reference.py`
#: et sur AGENTS.md. Leur divergence MUTERAIT le banc : la même valeur doit
#: être lue au même endroit partout.
VIDEO_REF = r"D:\Bureau\manif_test.mp4"
LIGNE_REF = (640.0, 0.0, 640.0, 720.0)  #: verticale au milieu de l'image
DEBUT_REF, FIN_REF = 3600, 4500

#: Dossier du banc : annotations versionnées (le précieux) et vidéos lentes
#: non versionnées (`.mp4` déjà ignorés par le .gitignore).
DOSSIER_BANC = pathlib.Path(__file__).resolve().parent.parent / "verite_terrain"

#: Tolérance d'appariement par défaut, en frames. 30 frames = 1 s à 30 i/s :
#: assez grand pour absorber la différence de datage humain/moteur, assez
#: petit pour ne pas apparier deux franchissements distincts d'une même
#: seconde.
TOLERANCE_DEFAUT = 30


# -- Annotations (pur, testé sans vidéo) -----------------------------------


def lire_annotations(chemin: str | pathlib.Path) -> list[int]:
    """Frames annotées à la main, une par ligne.

    Format volontairement idiot : un entier par ligne, `#` pour un commentaire,
    lignes vides ignorées. Un fichier qu'on peut remplir dans n'importe quel
    éditeur, sans tableau, sans colonne, sans format à se tromper.

    Le fichier est TRIÉ et dédoublonné à la lecture : l'ordre d'écriture d'un
    humain qui remonte en arrière pour ne rien rater n'a aucune signification,
    et le même chiffre noté deux fois est une hésitation, pas deux personnes.

    Une ligne illisible lève `ValueError` avec son numéro : une annotation
    fausse fausse tout le diagnostic, mieux vaut refuser le fichier que de
    deviner.
    """
    frames: list[int] = []
    texte = pathlib.Path(chemin).read_text(encoding="utf-8")
    for numero, ligne in enumerate(texte.splitlines(), start=1):
        brut = ligne.split("#", 1)[0].strip()
        if not brut:
            continue
        try:
            frame = int(brut)
        except ValueError:
            raise ValueError(
                f"{chemin}, ligne {numero} : {brut!r} n'est pas un numéro de "
                "frame (un entier seul par ligne)."
            ) from None
        if frame < 0:
            raise ValueError(
                f"{chemin}, ligne {numero} : {frame} est négatif, une frame "
                "ne l'est jamais."
            )
        frames.append(frame)
    # Dédoublonnage après tri : le même chiffre noté deux fois est un humain
    # hésitant, pas deux personnes. Sans ça, un simple doublet ferait
    # apparaître un « en trop » du moteur qui n'existe pas.
    frames.sort()
    return [f for i, f in enumerate(frames) if i == 0 or f != frames[i - 1]]


def apparier(
    humain: list[int], moteur: list[int], tolerance: int = TOLERANCE_DEFAUT
) -> dict:
    """Associe chaque franchissement humain au moteur le plus proche.

    Retourne ``{"apparies": [(h, m)], "manques": [h], "en_trop": [m]}`` :

    - ``apparies`` : un franchissement vu par l'humain ET par le moteur ;
    - ``manques`` : frames humaines SANS franchissement moteur à moins de
      ``tolerance`` — le moteur a laissé passer quelqu'un ;
    - ``en_trop`` : frames moteur SANS humain voisin — le moteur a compté
      quelqu'un que l'humain n'a pas vu (faux positif, ou humain fatigué).

    **Les couples les plus serrés s'apparient en premier.** Traiter les
    humains dans l'ordre laisserait un humain voler l'événement moteur d'un
    autre humain plus proche — le diagnostic signalerait un manquant qui
    n'existe que dans l'algorithme. On liste donc toutes les paires dans la
    tolérance, on les trie par écart croissant, et on prend les plus serrées
    d'abord. Un événement moteur ne sert qu'une fois, de toute façon.

    Les deux listes peuvent être non triées : le tri est fait ici, une fois,
    pour que l'appelant n'ait pas à y penser.
    """
    if tolerance < 0:
        raise ValueError(f"tolérance négative ({tolerance}) : sans sens.")

    candidats: list[tuple[int, int, int]] = []  # (écart, frame humaine, index moteur)
    for h in sorted(humain):
        for i, m in enumerate(sorted(moteur)):
            if abs(m - h) <= tolerance:
                candidats.append((abs(m - h), h, i))
    # Tri stable sur l'écart : à égalité, l'humain le plus petit d'abord, ce
    # qui rend le résultat indépendant de l'ordre d'entrée (les frames
    # ascendantes du comptage l'assurent déjà, mais rien ne le garantit).
    candidats.sort()

    m_tries = sorted(moteur)
    humains_vus: set[int] = set()
    moteurs_vus: set[int] = set()
    apparies: list[tuple[int, int]] = []

    for _, h, i in candidats:
        if h in humains_vus or i in moteurs_vus:
            continue
        humains_vus.add(h)
        moteurs_vus.add(i)
        apparies.append((h, m_tries[i]))

    apparies.sort()
    manques = [h for h in sorted(humain) if h not in humains_vus]
    en_trop = [m for i, m in enumerate(m_tries) if i not in moteurs_vus]
    return {"apparies": apparies, "manques": manques, "en_trop": en_trop}


# -- Extraction de la vidéo lente -------------------------------------------


def _ligne_de_reference(config: Config) -> Ligne:
    """Ligne de comptage telle que l'application la construit.

    Même appel que `analyser_video` et `mesurer_reference` : une divergence
    ici montrerait à l'opérateur une zone que le moteur ne compte pas.
    """
    assert config.ligne is not None
    return Ligne(
        (config.ligne[0], config.ligne[1]),
        (config.ligne[2], config.ligne[3]),
        epaisseur=config.epaisseur_bande,
        sens=config.sens,
        hysteresis=config.frames_hysteresis,
        bande_avant_px=BANDE_AVANT_PX,
        bande_apres_px=BANDE_APRES_PX,
    )


def extraire(
    debut: int = DEBUT_REF,
    fin: int = FIN_REF,
    sortie: str | pathlib.Path | None = None,
    modele: str | None = None,
) -> pathlib.Path:
    """Écrit la vidéo lente du segment, avec ligne et numéro de frame.

    Chaque frame source est écrite trois fois : 30 i/s deviennent 10 i/s
    effectives, et le numéro de frame (le NUMÉRO SOURCE, pas la position dans
    la vidéo lente) reste affiché pendant les trois copies — l'opérateur peut
    figer n'importe où et lire la frame à noter.

    Retourne le chemin écrit. Le modèle sert uniquement à respecter le réglage
    de référence (le banc compare au moteur avec SES réglages) ; il n'est pas
    chargé ici — l'extraction ne fait que du décodage et du dessin.
    """
    import cv2

    config = Config(ligne=LIGNE_REF, sens=-1, modele=modele or Config().modele)
    ligne = _ligne_de_reference(config)

    if sortie is None:
        sortie = DOSSIER_BANC / f"segment_{debut}-{fin}_lent.mp4"
    sortie = pathlib.Path(sortie)
    sortie.parent.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(VIDEO_REF)
    if not cap.isOpened():
        raise FileNotFoundError(f"vidéo illisible : {VIDEO_REF}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    largeur = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    hauteur = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if debut > 0:
        cap.set(cv2.CAP_PROP_POS_FRAMES, debut)

    ecrivain = cv2.VideoWriter(
        str(sortie), cv2.VideoWriter_fourcc(*"mp4v"), fps, (largeur, hauteur)
    )
    if not ecrivain.isOpened():
        raise RuntimeError(f"vidéo d'export illisible : {sortie}")

    index = debut
    while index < fin:
        ok, img = cap.read()
        if not ok:
            break
        cadre = ligne.dessiner(img)
        _ecrire_frame_number(cadre, index)
        for _ in range(3):
            ecrivain.write(cadre)
        index += 1
    cap.release()
    ecrivain.release()

    modele_txt = config.modele
    print(f"vidéo lente : {sortie}")
    print(f"segment     : {debut}-{index} ({index - debut} frames, ×3 lentes)")
    print(f"modèle      : {modele_txt} (non chargé pour l'extraction)")
    print(f"lent à lire : {(index - debut) / (fps / 3.0):.0f} s")
    return sortie


def _ecrire_frame_number(img, frame: int) -> None:
    """Grave le numéro de frame en haut à gauche, lisible sur toute image.

    Double pass (contour noir épais puis remplissage jaune) : un chiffre seul
    disparaît sur un ciel blanc comme sur une foule sombre, et l'opérateur qui
    ne lit pas le numéro note la mauvaise frame — l'erreur la plus facile à
    commettre et la plus difficile à détecter ensuite.
    """
    import cv2

    texte = str(frame)
    origine = (24, 64)
    police = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(img, texte, origine, police, 2.0, (0, 0, 0), 7, cv2.LINE_AA)
    cv2.putText(img, texte, origine, police, 2.0, (60, 220, 255), 3, cv2.LINE_AA)


def ecrire_modele_annotation(chemin: str | pathlib.Path) -> pathlib.Path:
    """Crée le fichier d'annotation vierge (s'il n'existe pas encore).

    Un modèle de commentaire en tête plutôt qu'une doc séparée : le fichier
    qui voyage avec l'opérateur est aussi celui qui lui dit comment le
    remplir. Un fichier EXISTANT n'est jamais écrasé — une heure d'annotation
    perdue est une heure de banc en moins.
    """
    chemin = pathlib.Path(chemin)
    if chemin.exists():
        return chemin
    chemin.parent.mkdir(parents=True, exist_ok=True)
    modele = (
        "# Vérité terrain — franchissements vus à la main.\n"
        "# Un numéro de frame par ligne : celui affiché en jaune sur la vidéo\n"
        "# lente, au moment où la personne est SUR la ligne verte.\n"
        "# `#` pour un commentaire, lignes vides acceptées.\n"
        "#\n"
        "# Compléter PUIS lancer :\n"
        "#   python tools/verite_terrain.py comparer "
        f"{chemin.as_posix()}\n"
    )
    chemin.write_text(modele, encoding="utf-8")
    return chemin


# -- Comparaison -------------------------------------------------------------


def comparer(
    annotations: str | pathlib.Path,
    debut: int = DEBUT_REF,
    fin: int = FIN_REF,
    tolerance: int = TOLERANCE_DEFAUT,
    imgsz: int | None = None,
    modele: str | None = None,
) -> dict:
    """Tourne le moteur sur le segment et le compare à l'annotation humaine.

    Le moteur tourne par `tools/mesurer_reference.mesurer` — le chemin groupé
    de production, pas une réécriture : une divergence entre le banc et l'app
    rendrait le diagnostic faux sur l'application qu'on cherche à améliorer.

    `imgsz=None` reproduit le choix de l'APPLICATION (résolution automatique
    depuis la source), ce qui n'est PAS le réglage par défaut du harnais de
    mesure (640 en dur). Les deux ne donnent pas le même compte sur la vidéo
    de référence — voir AGENTS.md, section « Résolution d'analyse ».
    """
    from mesurer_reference import mesurer  # import paresseux : cv2 au-dessus

    humain = lire_annotations(annotations)

    if imgsz is None:
        # Résolution automatique, comme au chargement d'une vidéo dans l'app.
        import cv2

        cap = cv2.VideoCapture(VIDEO_REF)
        if not cap.isOpened():
            raise FileNotFoundError(f"vidéo illisible : {VIDEO_REF}")
        largeur = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        hauteur = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()
        imgsz = taille_entree_automatique(largeur, hauteur)

    resultat = mesurer(
        VIDEO_REF, debut, fin, modele=modele, imgsz=imgsz, verbose=True
    )
    moteur = list(resultat["evenements"])
    rapprochement = apparier(humain, moteur, tolerance)

    return {
        "segment": resultat["segment"],
        "imgsz": resultat["imgsz"],
        "modele": resultat["modele"],
        "ips": resultat["ips"],
        "temps_s": resultat["secondes"],
        "total_humain": len(humain),
        "total_moteur": resultat["total"],
        "tolerance": tolerance,
        **rapprochement,
    }


def _afficher(r: dict) -> None:
    """Le diagnostic, en entier : les trois listes comptent plus que les totaux."""
    debut, fin = r["segment"]
    print(f"segment    : {debut}-{fin}")
    print(f"imgsz      : {r['imgsz']} (réglage de l'application)")
    print(f"modèle     : {r['modele']}")
    print(f"tolérance  : {r['tolerance']} frames")
    print()
    print(f"compté à la main   : {r['total_humain']}")
    print(f"compté par le moteur : {r['total_moteur']}")
    ecart = r["total_moteur"] - r["total_humain"]
    signe = "+" if ecart > 0 else ""
    print(f"écart             : {signe}{ecart}")
    print()
    print(f"appariés    : {len(r['apparies'])}")
    for h, m in r["apparies"]:
        print(f"    humain {h} ~ moteur {m}  (écart {m - h:+d})")
    if r["manques"]:
        print(f"MANQUÉS par le moteur : {len(r['manques'])}")
        print(f"    frames humaines sans événement moteur : {r['manques']}")
        print("    → regarder ces frames sur la vidéo lente, une à une.")
    if r["en_trop"]:
        print(f"COMPTÉS en trop par le moteur : {len(r['en_trop'])}")
        print(f"    frames moteur sans humain voisin : {r['en_trop']}")
        print("    → soit un faux positif du moteur, soit un oubli humain.")
    if not r["manques"] and not r["en_trop"]:
        print("ÉCART ZÉRO : chaque franchissement est vu des deux côtés.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sous = parser.add_subparsers(dest="commande", required=True)

    p_ext = sous.add_parser(
        "extraire", help="vidéo lente + modèle d'annotation du segment"
    )
    p_ext.add_argument("debut", nargs="?", type=int, default=DEBUT_REF)
    p_ext.add_argument("fin", nargs="?", type=int, default=FIN_REF)
    p_ext.add_argument("--sortie", default=None)

    p_cmp = sous.add_parser("comparer", help="moteur vs annotation humaine")
    p_cmp.add_argument("annotations")
    p_cmp.add_argument("debut", nargs="?", type=int, default=DEBUT_REF)
    p_cmp.add_argument("fin", nargs="?", type=int, default=FIN_REF)
    p_cmp.add_argument("--tolerance", type=int, default=TOLERANCE_DEFAUT)
    p_cmp.add_argument(
        "--imgsz",
        type=int,
        default=None,
        help="par défaut : la résolution automatique de l'application",
    )
    p_cmp.add_argument("--modele", default=None)

    args = parser.parse_args()

    if args.commande == "extraire":
        chemin = extraire(args.debut, args.fin, args.sortie)
        modele = DOSSIER_BANC / f"segment_{args.debut}-{args.fin}.txt"
        ecrire_modele_annotation(modele)
        print(f"annotation : {modele} (à compléter à la main)")
        return

    modele_txt = ecrire_modele_annotation(args.annotations)
    print(f"annotation : {modele_txt}")
    resultat = comparer(
        modele_txt,
        args.debut,
        args.fin,
        tolerance=args.tolerance,
        imgsz=args.imgsz,
        modele=args.modele,
    )
    print()
    _afficher(resultat)
    # Code de sortie non nul en cas d'écart : le banc s'utilise aussi dans un
    # script, et un diagnostic silencieusement défaillant ne vaut rien.
    sys.exit(0 if not resultat["manques"] and not resultat["en_trop"] else 1)


if __name__ == "__main__":
    main()
