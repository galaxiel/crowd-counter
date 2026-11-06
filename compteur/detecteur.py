"""Détection : image numpy -> liste de boîtes, via ONNX Runtime (moteur v3).

CHANGEMENT DE CONTRAT DE LA v3 : plus de torch, plus d'ultralytics, plus
de téléchargement de 2,4 Go. Le modèle est un graphe `.onnx` appliqué par
ONNX Runtime ; le prétraitement et le NMS — qui étaient le travail
d'ultralytics — sont vendores ICI, en numpy pur. Leur exactitude est
prouvée par parité contre l'ancien chemin : 2 896/2 896 détections jumelées
sur 60 frames de référence, et des comptes identiques à ±1 sur les quatre
vidéos terrain (voir `docs/design/v3-onnx-proposition.md`).

Deux règles structurantes :

- `onnxruntime` n'est importé qu'à l'intérieur de :func:`charger_modele`.
  L'importer au niveau du module ferait échouer toute la suite de tests
  sur une machine sans ce paquet ;
- les ops vendues ci-dessous (`_letterbox`, `_echelle_boites`, `_nms`)
  répliquent le comportement d'ultralytics au pixel près — un écart de
  détection limite change le décompte, elles sont donc verrouillées par
  les tests de parité (tests/test_detecteur.py).
"""

from __future__ import annotations

import logging
from typing import NamedTuple

import numpy as np

from .config import (
    PERIPHERIQUE_AUTO,
    PERIPHERIQUE_CPU,
    PERIPHERIQUE_CUDA,
    Config,
    dossiers_modeles,
    mode_peripherique,
    resoudre_modele,
)
from .types import Detection

log = logging.getLogger(__name__)

FORMATS_MODELES = (".onnx",)

#: Libellé affiché quand aucun accélérateur GPU n'est utilisé.
LIBELLE_CPU = "CPU uniquement"

#: Providers par réglage, du préféré au repli. DirectML couvre TOUTES les
#: cartes (NVIDIA, AMD, Intel) sous Windows ; le paquet installé décide de
#: ce qui est réellement disponible (`onnxruntime-directml` ne propose pas
#: CUDA, `onnxruntime-gpu` ne propose pas DML — un seul est installé).
PROVIDERS = {
    "auto": ["DmlExecutionProvider", "CUDAExecutionProvider", "CPUExecutionProvider"],
    "dml": ["DmlExecutionProvider", "CPUExecutionProvider"],
    # « cuda » (GPU exigé) accepte DirectML : c'est la couche GPU de
    # Windows, elle pilote les NVIDIA aussi — et le libellé affiché
    # reste honnête quel que soit le provider retenu.
    "cuda": ["DmlExecutionProvider", "CUDAExecutionProvider", "CPUExecutionProvider"],
    "cpu": ["CPUExecutionProvider"],
}


class ChoixPeripherique(NamedTuple):
    """Ce qui sera réellement utilisé, et pourquoi.

    `avertissement` est `None` quand tout va bien. Il n'est pas vide quand
    l'opérateur a demandé quelque chose que la machine ne peut pas faire : le
    texte est fait pour être affiché tel quel dans la barre de statut.
    """

    device: str
    libelle: str
    cuda: bool
    avertissement: str | None = None


def _session_onnxruntime():
    """Import paresseux d'ONNX Runtime (jamais au niveau du module)."""
    import onnxruntime  # noqa: PLC0415

    return onnxruntime


def providers_disponibles() -> list[str]:
    """Les providers réellement actifs dans le paquet installé."""
    return list(_session_onnxruntime().get_available_providers())


def choix_peripherique(peripherique: str = PERIPHERIQUE_AUTO) -> ChoixPeripherique:
    """Traduit le réglage en provider concret, repli CPU documenté.

    `auto` : premier provider GPU disponible (DirectML puis CUDA), CPU
    sinon — sans avertissement, c'est le comportement attendu. Un réglage
    explicite indisponible (`cuda` sur une machine dont le paquet ne le
    propose pas) tombe sur le CPU AVEC un avertissement : un crash sur le
    terrain coûte plus cher qu'une analyse lente qu'on peut au moins
    regarder, parce que l'opérateur voit la cause affichée et peut décider.
    """
    disponibles = providers_disponibles()
    preferes = PROVIDERS.get(peripherique)
    if preferes is None:
        return ChoixPeripherique(
            device="CPUExecutionProvider",
            libelle=LIBELLE_CPU,
            cuda=False,
            avertissement=f"périphérique inconnu : {peripherique} — CPU utilisé.",
        )
    for fournisseur in preferes:
        if fournisseur in disponibles:
            gpu = fournisseur != "CPUExecutionProvider"
            libelle = {
                "DmlExecutionProvider": "GPU (DirectML)",
                "CUDAExecutionProvider": "GPU (CUDA)",
                "CPUExecutionProvider": LIBELLE_CPU,
            }[fournisseur]
            avertissement = (
                "Aucun GPU accessible : l'analyse continue sur le CPU."
                if peripherique == PERIPHERIQUE_CUDA and not gpu
                else None
            )
            return ChoixPeripherique(
                device=fournisseur, libelle=libelle, cuda=gpu,
                avertissement=avertissement,
            )
    return ChoixPeripherique(
        device="CPUExecutionProvider",
        libelle=LIBELLE_CPU,
        cuda=False,
        avertissement=(
            f"Réglage « {peripherique} » indisponible (paquet installé : "
            f"{', '.join(disponibles)}) — analyse sur le CPU."
        ),
    )


def peripherique_effectif(choisi: str = PERIPHERIQUE_AUTO) -> ChoixPeripherique:
    """Nom historique de :func:`choix_peripherique` (l'UI et les outils l'appellent)."""
    return choix_peripherique(choisi)


def cuda_disponible() -> bool:
    """Un accélérateur GPU est-il utilisable ? (nom historique conservé.)"""
    return choix_peripherique(PERIPHERIQUE_AUTO).cuda


def nom_cuda() -> str:
    """Le libellé de l'accélération effective. (Nom historique conservé.)"""
    return choix_peripherique(PERIPHERIQUE_AUTO).libelle


def libelle_peripherique(choisi: str = PERIPHERIQUE_AUTO) -> str:
    """La ligne d'indicateur de la barre de statut : « Calcul : … »."""
    return f"Calcul : {choix_peripherique(choisi).libelle}"


def message_modele_absent(chemin: str) -> str:
    """Le message complet quand un modèle est introuvable sur le disque."""
    cherches = "\n".join(str(d) for d in dossiers_modeles())
    return (
        f"Modèle introuvable : {chemin}\n"
        f"Cherché tel quel, puis dans :\n{cherches}\n"
        "Dépose le fichier .onnx dans « modeles/ », ou choisis-le avec le "
        "bouton « Parcourir… » des réglages."
    )


def charger_modele(chemin: str, peripherique: str = PERIPHERIQUE_AUTO):
    """Charge un graphe `.onnx` via ONNX Runtime, provider demandé.

    Le chemin est résolu *avant* tout import lourd : sur une machine sans
    `onnxruntime`, l'erreur promise par l'API (`FileNotFoundError`) reste
    celle que l'appelant reçoit, pas un `ModuleNotFoundError`.

    Le fichier est cherché tel quel, puis dans les dossiers de
    `config.dossiers_modeles()` (dossier courant, `modeles/`, dossier
    personnel) — les mêmes que la liste déroulante des réglages, dans le
    même ordre.
    """
    p = resoudre_modele(chemin)
    if p is None:
        raise FileNotFoundError(message_modele_absent(chemin))
    if p.suffix.lower() not in FORMATS_MODELES:
        raise ValueError(
            f"format de modèle non supporté : {p.suffix} "
            f"(attendu : {', '.join(FORMATS_MODELES)}) — un graphe .onnx se "
            f"génère depuis un .pt par export ultralytics."
        )

    ort = _session_onnxruntime()
    choix = choix_peripherique(peripherique)
    if choix.avertissement:
        log.warning("%s", choix.avertissement)
    # PIÈGE mesuré le 06/11 : `get_available_providers()` liste un provider
    # même quand ses DLL manquent, et `InferenceSession` retombe ALORS
    # silencieusement sur le CPU. Le provider réellement actif se lit sur
    # la session CRÉÉE — on le vérifie, et on le dit si ce n'est pas celui
    # demandé.
    session = ort.InferenceSession(str(p), providers=[choix.device])
    actif = session.get_providers()[0]
    if actif != choix.device:
        log.warning(
            "provider %s demandé mais %s actif — analyse sur le repli.",
            choix.device, actif,
        )
    else:
        log.info("périphérique de détection : %s", actif)
    return session


# -- Ops vendues (l'ex-travail d'ultralytics, en numpy pur) --------------


def _letterbox(
    img: np.ndarray, taille: int
) -> tuple[np.ndarray, float, tuple[int, int]]:
    """Redimensionne et pad l'image pour l'inférence, comme ultralytics.

    Ratio = taille / plus long côté ; le résultat est porté au multiple de
    32 supérieur (stride du modèle) avec le padding MINIMAL restant
    (auto=True), CENTRÉ avec l'arrondi asymétrique d'ultralytics
    (`round(x - 0.1)` à gauche/haut, `round(x + 0.1)` à droite/bas),
    couleur 114, interpolation INTER_LINEAR. Retour : (image, ratio,
    (pad_gauche, pad_haut)).
    """
    import cv2  # noqa: PLC0415

    h, w = img.shape[:2]
    r = min(taille / h, taille / w)
    nh, nw = round(h * r), round(w * r)
    dw, dh = (taille - nw) % 32, (taille - nh) % 32
    dw, dh = dw / 2, dh / 2
    gauche, droite = round(dw - 0.1), round(dw + 0.1)
    haut, bas = round(dh - 0.1), round(dh + 0.1)
    encadre = np.full(
        (nh + haut + bas, nw + gauche + droite, 3), 114, dtype=np.uint8
    )
    if (w, h) != (nw, nh):
        img = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR)
    encadre[haut : haut + nh, gauche : gauche + nw] = img
    return encadre, r, (gauche, haut)


def _vers_tenseur(encadre: np.ndarray) -> np.ndarray:
    """Letterbox -> tenseur (1, 3, H, W) float32 : BGR->RGB, /255, CHW.

    La conversion BGR->RGB est OBLIGATOIRE : le graphe est issu d'un
    modèle entraîné en RGB, et ultralytics la fait avant l'inférence.
    Trouvé par la mesure (05/11) : en BGR, 42 détections contre 49 au
    même pixel.
    """
    x = encadre[..., ::-1].astype(np.float32) / 255.0
    return np.ascontiguousarray(x.transpose(2, 0, 1))[None]


def _nms(boites: np.ndarray, scores: np.ndarray, iou: float) -> list[int]:
    """NMS glouton, sémantique de torchvision.ops.nms : tri par score
    décroissant (stable — les égalités gardent l'ordre d'origine), on
    écarte toute boîte qui chevauche STRICTEMENT plus que `iou` une boîte
    déjà gardée."""
    x1, y1, x2, y2 = boites[:, 0], boites[:, 1], boites[:, 2], boites[:, 3]
    aires = (x2 - x1) * (y2 - y1)
    ordre = np.argsort(-scores, kind="stable")
    garde: list[int] = []
    while ordre.size:
        i = int(ordre[0])
        garde.append(i)
        xx1 = np.maximum(x1[i], x1[ordre[1:]])
        yy1 = np.maximum(y1[i], y1[ordre[1:]])
        xx2 = np.minimum(x2[i], x2[ordre[1:]])
        yy2 = np.minimum(y2[i], y2[ordre[1:]])
        inter = np.maximum(0, xx2 - xx1) * np.maximum(0, yy2 - yy1)
        union = aires[i] + aires[ordre[1:]] - inter
        # Restent en course : celles qui ne chevauchent PAS trop la boîte
        # gardée (strictement plus que `iou` = supprimée).
        ordre = ordre[1:][(inter / union) <= iou]
    return garde


def _echelle_boites(
    boites: np.ndarray, forme_letterbox: tuple, forme_origine: tuple
) -> np.ndarray:
    """Letterbox -> image d'origine : padding centré retiré, ratio inversé,
    borné à l'image — la formule exacte de `ultralytics.ops.scale_boxes`."""
    h_orig, w_orig = forme_origine
    h_enc, w_enc = forme_letterbox
    gain = min(h_enc / h_orig, w_enc / w_orig)
    pad_x = round((w_enc - w_orig * gain) / 2 - 0.1)
    pad_y = round((h_enc - h_orig * gain) / 2 - 0.1)
    b = boites.copy()
    b[:, [0, 2]] -= pad_x
    b[:, [1, 3]] -= pad_y
    b /= gain
    b[:, [0, 2]] = b[:, [0, 2]].clip(0, w_orig)
    b[:, [1, 3]] = b[:, [1, 3]].clip(0, h_orig)
    return b


class Detecteur:
    """Boîtes d'une image via une session ONNX Runtime.

    `modele` est ce que renvoie :func:`charger_modele` (une session déjà
    configurée sur le bon provider). L'API `detecter`/`detecter_lot` est
    celle de la v2 : les faux détecteurs des tests et les outils
    (mesurer_reference, verite_terrain) ne changent pas.
    """

    def __init__(self, modele, config: Config):
        self.session = modele
        self.config = config
        self.input_name = modele.get_inputs()[0].name

    # -- Prétraitement ----------------------------------------------------

    def _preparer(self, img: np.ndarray) -> tuple[np.ndarray, tuple]:
        """Image -> (tenseur, forme letterbox)."""
        encadre, _r, _pad = _letterbox(img, self.config.taille_entree)
        return _vers_tenseur(encadre), encadre.shape[:2]

    def _sortie_vers_detections(
        self, sortie: np.ndarray, forme_letterbox: tuple, forme_bande: tuple,
        decalage: tuple[int, int],
    ) -> list[Detection]:
        """Sortie brute `(1|B, 5, N)` -> `Detection` en coordonnées PLEINES.

        `sortie` : cx, cy, w, h, score (une classe) par ancre. Filtre de
        confiance STRICT (`> seuil`, comme ultralytics), NMS IoU 0,7
        (défaut historique — mesuré le 05/11 : toute autre valeur déplace
        le décompte), max_det 300, remise à l'échelle vers l'image de la
        bande puis décalage vers l'image PLEINE.
        """
        seuil = self.config.seuil_confiance
        # `run(...)[0]` donne (5, N) en passage UNITAIRE et (B, 5, N) en
        # lot : on remet l'axe de lot pour une seule boucle partout.
        if sortie.ndim == 2:
            # Passage unitaire : run()[0] donne (5, N) — on remet l'axe
            # de lot pour que la boucle soit la même partout.
            sortie = sortie[None]
        detections: list[Detection] = []
        for i in range(sortie.shape[0]):
            s = sortie[i]
            garde = s[4] > seuil
            sc = s[4][garde]
            if not sc.size:
                continue
            cx, cy = s[0][garde], s[1][garde]
            wl, hl = s[2][garde] / 2, s[3][garde] / 2
            boites = np.stack([cx - wl, cy - hl, cx + wl, cy + hl], axis=1)
            garder = _nms(boites, sc.astype(np.float32), 0.7)[:300]
            boites = boites[garder]
            boites = _echelle_boites(
                boites, forme_letterbox, (forme_bande[0], forme_bande[1])
            )
            for b, score in zip(boites.tolist(), sc[garder].tolist()):
                # Filtrage de la Config appliqué ICI, même si le graphe est
                # déjà paramétré : c'est la seule garantie que la valeur de
                # `Config` fait autorité, quel que soit le modèle fourni.
                largeur, hauteur = b[2] - b[0], b[3] - b[1]
                if (
                    largeur < self.config.taille_min_px
                    or hauteur < self.config.taille_min_px
                ):
                    continue
                if (
                    self.config.classes_retenues is not None
                    and 0 not in self.config.classes_retenues
                ):
                    continue
                detections.append(
                    Detection(
                        x1=b[0] + decalage[0],
                        y1=b[1] + decalage[1],
                        x2=b[2] + decalage[0],
                        y2=b[3] + decalage[1],
                        score=score,
                        class_id=0,
                    )
                )
        return detections

    # -- API publique ------------------------------------------------------

    def detecter(
        self, img: np.ndarray, bande: tuple[int, int, int, int] | None = None
    ) -> list[Detection]:
        """Boîtes de `img`, éventuellement restreintes à `bande`.

        `bande` est un rectangle ``(x1, y1, x2, y2)`` en pixels de l'image
        NATIVE, ou `None` pour analyser l'image entière. Les coordonnées
        renvoyées sont toujours dans le repère de l'image pleine.
        """
        decalage_x = decalage_y = 0
        if bande is not None:
            x1, y1, x2, y2 = (int(v) for v in bande)
            img = np.ascontiguousarray(img[y1:y2, x1:x2])
            decalage_x, decalage_y = x1, y1
        entree, forme_letterbox = self._preparer(img)
        sortie = self.session.run(None, {self.input_name: entree})[0]
        return self._sortie_vers_detections(
            sortie, forme_letterbox, img.shape[:2], (decalage_x, decalage_y)
        )

    def detecter_lot(
        self, imgs: list[np.ndarray], bande: tuple[int, int, int, int] | None = None
    ) -> list[list[Detection]]:
        """Détecte PLUSIEURS images en un appel modèle, sans changer le résultat.

        `bande` est le MÊME rectangle pour tout le lot : la ligne est
        verrouillée pendant une analyse, donc le décalage aussi. Même
        contrat de sortie que `detecter`, par image : une liste de listes
        de `Detection` en coordonnées de l'image pleine.
        """
        if len(imgs) == 1:
            return [self.detecter(imgs[0], bande)]
        decalage_x = decalage_y = 0
        if bande is not None:
            x1, y1, x2, y2 = (int(v) for v in bande)
            imgs = [np.ascontiguousarray(i[y1:y2, x1:x2]) for i in imgs]
            decalage_x, decalage_y = x1, y1
        entrees = [self._preparer(i) for i in imgs]
        entree = np.concatenate([e[0] for e in entrees])
        forme_letterbox = entrees[0][1]
        # `run` renvoie une LISTE de sorties (une par sortie du graphe) :
        # on prend la première AVANT de trancher par image — un slice de
        # liste donnerait des sous-listes, pas des tenseurs (bug 06/11).
        sortie = self.session.run(None, {self.input_name: entree})[0]
        return [
            self._sortie_vers_detections(
                sortie[i : i + 1], forme_letterbox, imgs[i].shape[:2],
                (decalage_x, decalage_y),
            )
            for i in range(len(imgs))
        ]
