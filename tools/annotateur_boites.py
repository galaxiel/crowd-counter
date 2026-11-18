"""Annotateur de boîtes pour entraîner un détecteur de têtes (outil SÉPARÉ).

Frère de `tools/annotateur.py`, mais autre contrat : l'annotateur au clic
valide le COMPTAGE (un frame par franchissement de la ligne) ; celui-ci
produit des données d'ENTRAÎNEMENT (des boîtes de têtes, au moment où elles
sont visibles — la ligne n'existe pas ici). Un drapeau qui cache la tête au
passage de la ligne ne gêne pas : on annote deux secondes avant, quand la
tête est nette ; le tracker fera le pont à la ligne.

Gestes : glisser une boîte sur la tête (partie visible), « Proposer » laisse
le modèle ONNX poser ses boîtes à confirmer/corriger, supprimer retire une
boîte. Export dataset YOLO : `entrainement/images/frame_XXXXXX.jpg` +
`entrainement/labels/frame_XXXXXX.txt` (0 cx cy w h normalisés) + `data.yaml`.
Les labels existants sont rechargés en naviguant : une session se reprend.

Usage :
    /c/Python311/python tools/annotateur_boites.py
    /c/Python311/python tools/annotateur_boites.py 3600 4500
"""

from __future__ import annotations

import pathlib
import sys

# Le script est lancé depuis `tools/` : le dépôt doit être dans le chemin pour
# que `compteur`, `interface` et `tools` soient importables.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QRect, Qt, QTimer, Signal  # noqa: E402
from PySide6.QtGui import QColor, QPainter  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from compteur.config import Config, resoudre_modele  # noqa: E402
from compteur.detecteur import Detecteur, charger_modele  # noqa: E402
from interface.widgets_video import WidgetVideo  # noqa: E402
from tools import verite_terrain as banc  # noqa: E402
from tools.annotateur import SourceVide, SourceVideo  # noqa: E402

#: Côté minimal d'une boîte, en pixels image : en dessous, le glissé est un
#: clic accidentel, pas une annotation.
MIN_COTE_PX = 4

DOSSIER_DEFAUT = pathlib.Path(__file__).resolve().parent.parent / "entrainement"


class SessionBoites:
    """Boîtes de têtes par frame, en pixels IMAGE, pure et testable sans écran."""

    def __init__(self) -> None:
        self.par_frame: dict[int, list[tuple[int, int, int, int]]] = {}

    def ajouter(self, frame: int, boite: tuple[int, int, int, int]) -> None:
        self.par_frame.setdefault(int(frame), []).append(tuple(boite))

    def supprimer(self, frame: int, index: int) -> None:
        del self.par_frame[frame][index]

    def boites(self, frame: int) -> list[tuple[int, int, int, int]]:
        return self.par_frame.get(frame, [])

    def frames_annotees(self) -> list[int]:
        return sorted(f for f, b in self.par_frame.items() if b)

    def vers_yolo(self, frame: int, largeur: int, hauteur: int) -> str:
        lignes = []
        for x1, y1, x2, y2 in self.boites(frame):
            cx = (x1 + x2) / 2 / largeur
            cy = (y1 + y2) / 2 / hauteur
            w = (x2 - x1) / largeur
            h = (y2 - y1) / hauteur
            lignes.append(f"0 {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")
        return "\n".join(lignes) + "\n" if lignes else ""

    @staticmethod
    def depuis_yolo(
        texte: str, largeur: int, hauteur: int
    ) -> list[tuple[int, int, int, int]]:
        boites = []
        for ligne in texte.splitlines():
            parts = ligne.split()
            if len(parts) != 5:
                continue
            _, cx, cy, w, h = (float(v) for v in parts)
            x1 = round((cx - w / 2) * largeur)
            y1 = round((cy - h / 2) * hauteur)
            x2 = round((cx + w / 2) * largeur)
            y2 = round((cy + h / 2) * hauteur)
            boites.append((x1, y1, x2, y2))
        return boites


def ecrire_dataset(session: SessionBoites, dossier, lire_image) -> pathlib.Path:
    """Écrit images + labels + data.yaml, un fichier par frame annotée.

    `lire_image(frame)` rend la frame BRUTE (sans boîtes dessinées) : les
    images d'entraînement ne doivent porter aucun marquage. Les labels sont
    le précieux (versionnables) ; les images se régénèrent depuis la vidéo.
    """
    import cv2

    dossier = pathlib.Path(dossier)
    (dossier / "images").mkdir(parents=True, exist_ok=True)
    (dossier / "labels").mkdir(parents=True, exist_ok=True)
    for frame in session.frames_annotees():
        img = lire_image(frame)
        if img is None:
            continue
        hauteur, largeur = img.shape[:2]
        nom = f"frame_{frame:06d}"
        cv2.imwrite(str(dossier / "images" / f"{nom}.jpg"), img)
        (dossier / "labels" / f"{nom}.txt").write_text(
            session.vers_yolo(frame, largeur, hauteur), encoding="utf-8"
        )
    (dossier / "data.yaml").write_text(
        f"path: {dossier.resolve().as_posix()}\n"
        "train: images\n"
        "val: images\n"
        "names:\n"
        "  0: tete\n",
        encoding="utf-8",
    )
    return dossier


class WidgetBoites(WidgetVideo):
    """WidgetVideo dont le glissé gauche trace une boîte en pixels image.

    Le clic simple de la classe mère (signal `clic`) n'est pas utilisé ici :
    le geste d'annotation est le RECTANGLE, pas le point. Un feedback visuel
    (rectangle vert) suit le glissé ; la boîte n'est émise qu'au relâchement,
    et seulement si elle dépasse MIN_COTE_PX.
    """

    boite_tracee = Signal(int, int, int, int)
    #: Clic simple (sans glissé) : le point cliqué, en pixels image. La fenêtre
    #: en fait une boîte de taille standard centrée — plus rapide que glisser
    #: pour une tête « normale ».
    clic_boite = Signal(int, int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._ancre_widget: tuple[float, float] | None = None
        self._coin_widget: tuple[float, float] | None = None

    def mousePressEvent(self, event) -> None:  # noqa: N802 (API Qt)
        if event.button() != Qt.MouseButton.LeftButton:
            return
        x, y = event.position().x(), event.position().y()
        if self.vers_pixels(x, y) is None:
            return
        self._ancre_widget = (x, y)
        self._coin_widget = (x, y)
        self.update()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 (API Qt)
        if self._ancre_widget is None:
            return
        self._coin_widget = (event.position().x(), event.position().y())
        self.update()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 (API Qt)
        if self._ancre_widget is None or event.button() != Qt.MouseButton.LeftButton:
            return
        ancre = self._ancre_widget
        self._ancre_widget = None
        self._coin_widget = None
        self.update()
        a = self.vers_pixels(ancre[0], ancre[1])
        b = self.vers_pixels(event.position().x(), event.position().y())
        if a is None or b is None:
            return
        x1, x2 = sorted((a[0], b[0]))
        y1, y2 = sorted((a[1], b[1]))
        if x2 - x1 < MIN_COTE_PX or y2 - y1 < MIN_COTE_PX:
            # Trop petit pour être un vrai glissé : c'est un CLIC. On émet le
            # point, la fenêtre posera une boîte de taille standard.
            self.clic_boite.emit(*a)
            return
        self.boite_tracee.emit(x1, y1, x2, y2)

    def paintEvent(self, event) -> None:  # noqa: N802 (API Qt)
        super().paintEvent(event)
        if self._ancre_widget is None or self._coin_widget is None:
            return
        ax, ay = self._ancre_widget
        bx, by = self._coin_widget
        peintre = QPainter(self)
        peintre.setPen(QColor(0, 255, 0))
        peintre.drawRect(
            QRect(
                int(min(ax, bx)),
                int(min(ay, by)),
                int(abs(ax - bx)),
                int(abs(ay - by)),
            )
        )
        peintre.end()


class FenetreBoites(QWidget):
    """Navigation libre SANS ligne, boîtes au moment visible, export YOLO.

    Même coque de navigation que l'annotateur au clic (source, timer, pas à
    pas, seek) — mais l'affichage ne dessine NI ligne NI numéro gravé : les
    images exportées doivent rester brutes, et la ligne est un artefact de
    comptage qui n'a pas de sens pour l'entraînement.
    """

    def __init__(
        self,
        source=None,
        detecteur=None,
        dossier=None,
        debut: int = 0,
        fin: int = banc.FIN_REF,
        chemin: str | pathlib.Path | None = None,
        nb_frames: int | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.debut, self.fin = debut, fin
        self.chemin = str(chemin) if chemin is not None else banc.VIDEO_REF
        self.nb_frames = int(nb_frames) if nb_frames is not None else max(fin, 1)
        self._sans_video = False
        if source is None:
            try:
                source = SourceVideo(debut, fin, self.chemin)
            except Exception:
                source = SourceVide(debut, fin)
                self._sans_video = True
        self.source = source
        self.detecteur = detecteur
        self.dossier = (
            pathlib.Path(dossier)
            if dossier is not None
            else self._nom_dossier(self.chemin)
        )
        self.session = SessionBoites()
        self.en_cours = False
        self._image_brute = None

        self._maj_titre()
        self.video = WidgetBoites()
        self.video.boite_tracee.connect(self._sur_boite)
        self.video.clic_boite.connect(self._sur_clic_boite)

        # Rangée HAUT : choisir la vidéo et l'étendue (toute la vidéo ou un
        # segment). Une autre vidéo exporte son dataset dans son propre
        # sous-dossier (entrainement/<nom_video>/) pour ne pas mélanger les
        # frames de deux vidéos.
        self.bouton_ouvrir_video = QPushButton("Ouvrir une vidéo…")
        self.bouton_ouvrir_video.clicked.connect(self._choisir_video)
        self.case_tout = QCheckBox("Toute la vidéo")
        self.case_tout.toggled.connect(self._sur_case_tout)
        self.champ_debut = QSpinBox()
        self.champ_debut.setRange(0, max(0, self.nb_frames - 1))
        self.champ_debut.setValue(debut)
        self.champ_debut.valueChanged.connect(self._sur_champs)
        self.champ_fin = QSpinBox()
        self.champ_fin.setRange(1, self.nb_frames)
        self.champ_fin.setValue(fin)
        self.champ_fin.valueChanged.connect(self._sur_champs)
        rangee_haut = QHBoxLayout()
        rangee_haut.addWidget(self.bouton_ouvrir_video)
        rangee_haut.addWidget(self.case_tout)
        rangee_haut.addWidget(QLabel("de"))
        rangee_haut.addWidget(self.champ_debut)
        rangee_haut.addWidget(QLabel("à"))
        rangee_haut.addWidget(self.champ_fin)
        rangee_haut.addStretch(1)

        self.curseur = QSlider(Qt.Orientation.Horizontal)
        self.curseur.setRange(debut, fin - 1)
        self.curseur.setValue(debut)
        self.curseur.valueChanged.connect(self._sur_curseur)

        self.bouton_arriere = QPushButton("Précédente")
        self.bouton_lecture = QPushButton("Lecture")
        self.bouton_avant = QPushButton("Suivante")
        self.label_frame = QLabel()
        self.bouton_arriere.clicked.connect(self._pas_arriere)
        self.bouton_lecture.clicked.connect(self._basculer_lecture)
        self.bouton_avant.clicked.connect(self._pas_avant)

        self.label_compte = QLabel()
        self.liste = QListWidget()
        self.bouton_supprimer = QPushButton("Supprimer la sélection")
        self.bouton_proposer = QPushButton("Proposer (modèle)")
        self.bouton_enregistrer = QPushButton("Enregistrer le dataset")
        self.label_aide = QLabel(
            "CLIC sur une tête = boîte de taille standard (la plus rapide).\n"
            "GLISSE = boîte sur mesure. Boîte déjà posée : le clic est ignoré.\n"
            "Pour supprimer : sélectionne dans la liste (à droite) puis Supprimer."
        )
        self.label_aide.setWordWrap(True)
        self.bouton_supprimer.clicked.connect(self._supprimer)
        self.bouton_proposer.clicked.connect(self._proposer)
        self.bouton_enregistrer.clicked.connect(self._enregistrer)
        if self.detecteur is None:
            self.bouton_proposer.setEnabled(False)
            self.bouton_proposer.setToolTip("Modèle .onnx introuvable — boîtes à la main.")

        rangee = QHBoxLayout()
        for w in (self.bouton_arriere, self.bouton_lecture, self.bouton_avant):
            rangee.addWidget(w)
        rangee.addWidget(self.label_frame, stretch=1)

        colonne_liste = QVBoxLayout()
        colonne_liste.addWidget(self.label_compte)
        colonne_liste.addWidget(self.liste, stretch=1)
        colonne_boutons = QVBoxLayout()
        for b in (self.bouton_proposer, self.bouton_supprimer, self.bouton_enregistrer):
            colonne_boutons.addWidget(b)
        colonne_boutons.addWidget(self.label_aide)
        colonne_boutons.addStretch(1)
        bas = QHBoxLayout()
        bas.addLayout(colonne_liste, stretch=1)
        bas.addLayout(colonne_boutons)

        racine = QVBoxLayout(self)
        racine.addLayout(rangee_haut)
        racine.addWidget(self.video, stretch=1)
        racine.addWidget(self.curseur)
        racine.addLayout(rangee)
        racine.addLayout(bas)

        self._minuteur = QTimer(self)
        self._minuteur.timeout.connect(self._tick)

        img = self.source.aller_a(debut)
        if img is not None:
            self._afficher(img)
        if self._sans_video:
            self.label_aide.setText(
                "Aucune vidéo ouverte. Clique sur « Ouvrir une vidéo… » pour "
                "commencer — puis glisse des boîtes sur les têtes visibles."
            )

    # -- Vidéo / étendue ---------------------------------------------------

    def _nom_dossier(self, chemin: str | pathlib.Path) -> pathlib.Path:
        """Dossier d'export du dataset : séparé par vidéo (hors référence).

        Mélanger les frames de deux vidéos dans le même dossier ferait écraser
        des `frame_XXXXXX.jpg` homonymes — chaque vidéo a donc son sous-dossier.
        """
        if str(chemin) == str(banc.VIDEO_REF):
            return DOSSIER_DEFAUT
        return DOSSIER_DEFAUT / pathlib.Path(chemin).stem

    def _maj_titre(self) -> None:
        nom = pathlib.Path(self.chemin).name
        self.setWindowTitle(
            f"Annotateur de boîtes — entraînement ({self.debut}–{self.fin}) · {nom}"
        )

    def _configurer_plage(self, debut: int, fin: int) -> None:
        debut = max(0, int(debut))
        fin = max(debut + 1, int(fin))
        self.debut, self.fin = debut, fin
        self.source.debut = debut
        self.source.fin = fin
        for champ, valeur in ((self.champ_debut, debut), (self.champ_fin, fin)):
            champ.blockSignals(True)
            champ.setValue(valeur)
            champ.blockSignals(False)
        self.curseur.blockSignals(True)
        self.curseur.setRange(debut, max(debut, fin - 1))
        self.curseur.setValue(debut)
        self.curseur.blockSignals(False)
        self._maj_titre()
        img = self.source.aller_a(debut)
        if img is not None:
            self._afficher(img)

    def _sur_case_tout(self, coche: bool) -> None:
        self.champ_debut.setEnabled(not coche)
        self.champ_fin.setEnabled(not coche)
        if coche:
            self._configurer_plage(0, self.nb_frames)
        else:
            self._configurer_plage(0, min(900, self.nb_frames))

    def _sur_champs(self) -> None:
        debut = self.champ_debut.value()
        fin = self.champ_fin.value()
        if fin <= debut:
            fin = min(debut + 1, self.nb_frames)
            if fin <= debut:
                debut = max(0, fin - 1)
        self._configurer_plage(debut, fin)

    def _choisir_video(self) -> None:
        chemin, _ = QFileDialog.getOpenFileName(
            self,
            "Choisir une vidéo",
            str(pathlib.Path(self.chemin).parent),
            "Vidéos (*.mp4 *.avi *.mov *.mkv);;Tous les fichiers (*)",
        )
        if chemin:
            self.charger_video(chemin)

    def charger_video(
        self,
        chemin: str | pathlib.Path,
        source=None,
        nb_frames: int | None = None,
    ) -> None:
        """Charge une nouvelle vidéo : nouveau dossier d'export, session vierge."""
        if source is None:
            import cv2

            cap = cv2.VideoCapture(str(chemin))
            if not cap.isOpened():
                raise FileNotFoundError(f"vidéo illisible : {chemin}")
            nb = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            cap.release()
            source = SourceVideo(0, nb, chemin)
            nb_frames = nb
        if nb_frames is None:
            nb_frames = max(1, self.fin)
        self._pause()
        try:
            self.source.fermer()
        except Exception:
            pass
        self.source = source
        self._sans_video = False
        self.chemin = str(chemin)
        self.nb_frames = max(1, int(nb_frames))
        self.dossier = self._nom_dossier(self.chemin)
        self.session = SessionBoites()
        self.champ_debut.blockSignals(True)
        self.champ_debut.setRange(0, max(0, self.nb_frames - 1))
        self.champ_debut.blockSignals(False)
        self.champ_fin.blockSignals(True)
        self.champ_fin.setRange(1, self.nb_frames)
        self.champ_fin.blockSignals(False)
        self.case_tout.blockSignals(True)
        self.case_tout.setChecked(False)
        self.case_tout.blockSignals(False)
        self.champ_debut.setEnabled(True)
        self.champ_fin.setEnabled(True)
        self._configurer_plage(0, min(900, self.nb_frames))

    # -- Affichage ---------------------------------------------------------

    def _afficher(self, img) -> None:
        import cv2

        self._image_brute = img
        index = self.source.index
        # Reprise : un label existant se recharge à la navigation, jamais
        # écrasé en silence — comme l'annotateur au clic recharge son fichier.
        if index not in self.session.par_frame:
            chemin = self.dossier / "labels" / f"frame_{index:06d}.txt"
            if chemin.exists():
                hauteur, largeur = img.shape[:2]
                self.session.par_frame[index] = SessionBoites.depuis_yolo(
                    chemin.read_text(encoding="utf-8"), largeur, hauteur
                )
        cadre = img.copy()
        for x1, y1, x2, y2 in self.session.boites(index):
            cv2.rectangle(cadre, (x1, y1), (x2, y2), (0, 255, 0), 2)
        self.video.definir_image(cadre)
        self.curseur.blockSignals(True)
        self.curseur.setValue(index)
        self.curseur.blockSignals(False)
        self.label_frame.setText(f"frame {index} / {self.fin - 1}")
        self._maj_liste()

    def _maj_liste(self) -> None:
        self.liste.clear()
        for i, (x1, y1, x2, y2) in enumerate(self.session.boites(self.source.index)):
            self.liste.addItem(f"{i + 1}. ({x1}, {y1}, {x2}, {y2})")
        self.label_compte.setText(
            f"Frame {self.source.index} : {self.liste.count()} boîtes · "
            f"{len(self.session.frames_annotees())} frames annotées"
        )

    def _redessiner(self) -> None:
        if self._image_brute is not None:
            self._afficher(self._image_brute)

    # -- Lecture -----------------------------------------------------------

    def _pause(self) -> None:
        self.en_cours = False
        self._minuteur.stop()
        self.bouton_lecture.setText("Lecture")

    def _basculer_lecture(self) -> None:
        if self.en_cours:
            self._pause()
            return
        self.en_cours = True
        self.bouton_lecture.setText("Pause")
        self._minuteur.start(max(1, int(1000 / (self.source.fps * 0.5))))

    def _tick(self) -> None:
        img = self.source.suivante()
        if img is None:
            self._pause()
            return
        self._afficher(img)

    def _pas_avant(self) -> None:
        self._pause()
        img = self.source.suivante()
        if img is not None:
            self._afficher(img)

    def _pas_arriere(self) -> None:
        self._pause()
        img = self.source.precedente()
        if img is not None:
            self._afficher(img)

    def _sur_curseur(self, valeur: int) -> None:
        self._pause()
        img = self.source.aller_a(valeur)
        if img is not None:
            self._afficher(img)

    # -- Annotation --------------------------------------------------------

    def _boite_existe(self, frame: int, boite: tuple[int, int, int, int]) -> bool:
        """Vrai si le centre de `boite` tombe dans une boîte déjà posée."""
        cx = (boite[0] + boite[2]) / 2
        cy = (boite[1] + boite[3]) / 2
        for x1, y1, x2, y2 in self.session.boites(frame):
            if x1 <= cx <= x2 and y1 <= cy <= y2:
                return True
        return False

    def _ajouter(self, boite: tuple[int, int, int, int]) -> None:
        """Ajoute une boîte au frame courant (sans doublon) et la sélectionne."""
        if self._boite_existe(self.source.index, boite):
            return
        self.session.ajouter(self.source.index, boite)
        self._redessiner()
        # Sélectionne la boîte neuve : « Supprimer la sélection » l'enlève
        # aussitôt, sans avoir à cliquer dans la liste.
        self.liste.setCurrentRow(self.liste.count() - 1)

    def _sur_boite(self, x1: int, y1: int, x2: int, y2: int) -> None:
        self._pause()
        self._ajouter((x1, y1, x2, y2))

    def _sur_clic_boite(self, x: int, y: int) -> None:
        """Clic simple = boîte de taille standard, centrée sur le point."""
        self._pause()
        if self._image_brute is None:
            return
        hauteur, largeur = self._image_brute.shape[:2]
        w = max(16, round(largeur * 0.034))
        h = max(20, round(hauteur * 0.075))
        x1 = max(0, min(largeur - w, x - w // 2))
        y1 = max(0, min(hauteur - h, y - h // 2))
        self._ajouter((x1, y1, x1 + w, y1 + h))

    def _supprimer(self) -> None:
        ligne = self.liste.currentRow()
        if ligne < 0:
            self.label_aide.setText(
                "Sélectionne d'abord une boîte dans la liste (à droite), "
                "puis « Supprimer la sélection »."
            )
            return
        self.session.supprimer(self.source.index, ligne)
        self._redessiner()

    def _proposer(self) -> None:
        if self.detecteur is None or self._image_brute is None:
            return
        self._pause()
        frame = self.source.index
        for d in self.detecteur.detecter(self._image_brute):
            boite = (int(d.x1), int(d.y1), int(d.x2), int(d.y2))
            if not self._boite_existe(frame, boite):
                self.session.ajouter(frame, boite)
        self._redessiner()

    def _enregistrer(self) -> None:
        courant = self.source.index
        ecrire_dataset(self.session, self.dossier, self.source.aller_a)
        img = self.source.aller_a(courant)
        if img is not None:
            self._afficher(img)
        print(
            f"dataset : {self.dossier} "
            f"({len(self.session.frames_annotees())} frames annotées)"
        )

    # -- Événements Qt ------------------------------------------------------

    def keyPressEvent(self, event) -> None:  # noqa: N802 (API Qt)
        touche = event.key()
        if touche == Qt.Key.Key_Space:
            self._basculer_lecture()
        elif touche == Qt.Key.Key_Right:
            self._pas_avant()
        elif touche == Qt.Key.Key_Left:
            self._pas_arriere()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event) -> None:  # noqa: N802 (API Qt)
        self._minuteur.stop()
        self.source.fermer()
        super().closeEvent(event)


def main(argv: list[str] | None = None) -> None:
    import cv2

    argv = sys.argv[1:] if argv is None else argv
    cap = cv2.VideoCapture(banc.VIDEO_REF)
    nb_frames = (
        int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) if cap.isOpened() else banc.FIN_REF
    )
    cap.release()
    debut, fin = 0, nb_frames
    if len(argv) == 2:
        debut, fin = int(argv[0]), int(argv[1])
    elif argv:
        raise SystemExit("usage : python tools/annotateur_boites.py [debut fin]")

    detecteur = None
    chemin_modele = resoudre_modele(Config().modele)
    if chemin_modele is not None:
        detecteur = Detecteur(charger_modele(str(chemin_modele)), Config())
    else:
        print("modèle .onnx introuvable : « Proposer » désactivé, boîtes à la main.")

    app = QApplication.instance() or QApplication(sys.argv[:1])
    fenetre = FenetreBoites(
        debut=debut,
        fin=fin,
        detecteur=detecteur,
        chemin=banc.VIDEO_REF,
        nb_frames=nb_frames,
    )
    fenetre.resize(1280, 800)
    fenetre.show()
    raise SystemExit(app.exec())


if __name__ == "__main__":
    main()