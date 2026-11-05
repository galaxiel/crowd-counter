"""Détection par ONNX Runtime : même interface que `detecteur.Detecteur`.

SPIKE v3 (branche `essai/v3-onnx`) — voir
`docs/design/v3-onnx-proposition.md`. Objectif : prouver que les comptes
sont identiques au chemin torch, et mesurer les débits des deux voies
(CUDA EP et DirectML). Rien ici n'est utilisé tant que la preuve n'est
pas faite.

Deux raccourcis assumés du spike, à lever avant une v3 :

- le prétraitement réutilise les ops d'ultralytics (`LetterBox`,
  `scale_boxes`) pour éliminer une source d'écart — la v3 livrée devrait
  les vendore (fonction de ~30 lignes) avec un test de parité ;
- le NMS réutilise `torchvision.ops.nms` (celui d'ultralytics) — même
  remarque.
"""

from __future__ import annotations

import logging

import numpy as np

from .types import Detection

log = logging.getLogger(__name__)

#: Providers par chemin d'exécution, du préféré au repli.
PROVIDERS = {
    "cuda": ["CUDAExecutionProvider", "CPUExecutionProvider"],
    "dml": ["DmlExecutionProvider", "CPUExecutionProvider"],
    "cpu": ["CPUExecutionProvider"],
}


class DetecteurOnnx:
    """Boîtes d'une image via un graphe `.onnx`, sémantique de `Detecteur`.

    `peripherique` choisit le provider : "cuda", "dml" ou "cpu". Le
    prétraitement réplique EXACTEMENT celui d'ultralytics pour un modèle
    `.pt` à `imgsz` égal (LetterBox auto, stride 32, /255, CHW) — c'est la
    condition de la parité des décomptes.
    """

    def __init__(self, chemin_onnx: str, config, peripherique: str = "cuda"):
        # torch/torchvision : uniquement pour `ops.nms` (le NMS
        # d'ultralytics) — import paresseux, jamais au niveau module.
        import torchvision  # noqa: PLC0415
        from ultralytics.data.augment import LetterBox  # noqa: PLC0415

        import onnxruntime as ort  # noqa: PLC0415

        self.config = config
        self._nms = torchvision.ops.nms
        providers = PROVIDERS[peripherique]
        self.session = ort.InferenceSession(chemin_onnx, providers=providers)
        self.input_name = self.session.get_inputs()[0].name
        self._letterbox = LetterBox(
            new_shape=(config.taille_entree, config.taille_entree),
            auto=True,
            stride=32,
        )
        log.info(
            "DetecteurOnnx prêt (%s) : providers actifs %s",
            peripherique,
            self.session.get_providers(),
        )

    # -- Prétraitement ----------------------------------------------------

    def _preparer(self, img: np.ndarray) -> np.ndarray:
        """LetterBox (auto, stride 32) + BGR->RGB + /255 + CHW, float32, batch 1.

        Même chaîne que le predictor ultralytics — le convertisseur BGR->RGB
        y est IMPLICITE (bug trouvé par la mesure : nourrir le graphe en BGR
        donnait 42 détections contre 49 au même pixel en RGB).
        """
        encadre = self._letterbox(image=img)
        x = encadre[..., ::-1].astype(np.float32) / 255.0
        return np.ascontiguousarray(x.transpose(2, 0, 1))[None]

    def _vers_detections(
        self, sortie: np.ndarray, forme_letterbox: tuple, forme_bande: tuple,
        decalage: tuple,
    ):
        """Sortie brute `(1, 5, N)` -> `Detection`, exactement comme torch.

        Le NMS est celui d'ULTRALYTICS (`utils.nms.non_max_suppression`)
        appliqué à ma sortie brute : réimplémenter ce filtre donnait des
        écarts de 1-3 détections par frame sur les cas limites. Retour :
        `(M, 6)` xyxy + score + classe, en coordonnées de LETTERBOX —
        remise à l'échelle vers l'image de la bande, puis décalage vers
        l'image PLEINE.
        """
        import torch  # noqa: PLC0415
        from ultralytics.utils.nms import non_max_suppression  # noqa: PLC0415
        from ultralytics.utils.ops import scale_boxes  # noqa: PLC0415

        resultat = non_max_suppression(
            torch.from_numpy(sortie),
            conf_thres=self.config.seuil_confiance,
            iou_thres=0.7,
            max_det=300,
        )[0]
        if resultat.numel():
            boites = scale_boxes(
                forme_letterbox, resultat[:, :4], forme_bande
            ).round()
        else:
            boites = resultat[:, :4]
        detections = [
            Detection(
                x1=float(b[0]) + decalage[0],
                y1=float(b[1]) + decalage[1],
                x2=float(b[2]) + decalage[0],
                y2=float(b[3]) + decalage[1],
                score=float(s),
                class_id=0,
            )
            for b, s in zip(boites.tolist(), resultat[:, 4].tolist())
        ]
        return detections

    # -- Interface de Detecteur -------------------------------------------

    def detecter(
        self, img: np.ndarray, bande: tuple[int, int, int, int] | None = None
    ) -> list[Detection]:
        decalage_x = decalage_y = 0
        if bande is not None:
            x1, y1, x2, y2 = (int(v) for v in bande)
            img = np.ascontiguousarray(img[y1:y2, x1:x2])
            decalage_x, decalage_y = x1, y1
        entree = self._preparer(img)
        sortie = self.session.run(None, {self.input_name: entree})[0]
        return self._vers_detections(
            sortie, entree.shape[2:], img.shape[:2], (decalage_x, decalage_y)
        )

    def detecter_lot(
        self, imgs: list[np.ndarray], bande: tuple[int, int, int, int] | None = None
    ) -> list[list[Detection]]:
        if len(imgs) == 1:
            return [self.detecter(imgs[0], bande)]
        decalage_x = decalage_y = 0
        if bande is not None:
            x1, y1, x2, y2 = (int(v) for v in bande)
            imgs = [np.ascontiguousarray(i[y1:y2, x1:x2]) for i in imgs]
            decalage_x, decalage_y = x1, y1
        entree = np.concatenate([self._preparer(i) for i in imgs])
        sorties = self.session.run(None, {self.input_name: entree})[0]
        forme_letterbox = entree.shape[2:]
        return [
            self._vers_detections(
                sorties[i : i + 1], forme_letterbox, imgs[i].shape[:2],
                (decalage_x, decalage_y),
            )
            for i in range(len(imgs))
        ]
