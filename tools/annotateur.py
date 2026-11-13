"""Annotateur au clic pour le banc de vérité terrain.

L'opérateur clique sur une tête au moment où elle est sur la ligne : le frame
courant est enregistré, sans avoir à noter un numéro à la main. La sortie est
le format idiot du banc (un entier par ligne, `#` en commentaire), relue par
`tools.verite_terrain.lire_annotations` puis confrontée au moteur par
`comparer`.

Usage :
    /c/Python311/python tools/annotateur.py
    /c/Python311/python tools/annotateur.py 3600 4500
"""

from __future__ import annotations

import pathlib
import re
import sys

# Le script est lancé depuis `tools/` : le dépôt doit être dans le chemin pour
# que `compteur`, `interface` et `tools` soient importables.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from PySide6.QtCore import Qt, QTimer  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from compteur.config import Config  # noqa: E402
from interface.widgets_video import WidgetVideo  # noqa: E402
from tools import verite_terrain as banc  # noqa: E402

#: Vitesses de lecture proposées. 0,5× par défaut : 15 i/s effectives, assez
#: lent pour voir le franchissement, assez rapide pour parcourir le segment.
VITESSES = [("0,25×", 0.25), ("0,5×", 0.5), ("1×", 1.0)]


class SessionAnnotation:
    """La liste des clics de l'opérateur, pure et testable sans écran."""

    def __init__(self) -> None:
        self.entrees: list[tuple[int, int | None, int | None]] = []

    def ajouter(self, frame: int, x: int | None = None, y: int | None = None) -> None:
        self.entrees.append((int(frame), x, y))

    def annuler(self) -> None:
        if self.entrees:
            self.entrees.pop()

    def supprimer(self, index: int) -> None:
        del self.entrees[index]

    def __len__(self) -> int:
        return len(self.entrees)

    def vers_texte(self) -> str:
        lignes = [
            "# Vérité terrain — annotateur au clic (tools/annotateur.py).",
            "# Un numéro de frame par ligne : clic sur la tête au moment où",
            "# elle est SUR la ligne verte. La position du clic est en",
            "# commentaire pour relecture ; `comparer` ne lit que le numéro.",
        ]
        for frame, x, y in self.entrees:
            if x is None or y is None:
                lignes.append(str(frame))
            else:
                lignes.append(f"{frame}  # clic ({x}, {y})")
        return "\n".join(lignes) + "\n"

    @classmethod
    def depuis_texte(cls, texte: str) -> "SessionAnnotation":
        s = cls()
        for numero, ligne in enumerate(texte.splitlines(), start=1):
            brut, _, commentaire = ligne.partition("#")
            brut = brut.strip()
            if not brut:
                continue
            try:
                frame = int(brut)
            except ValueError:
                raise ValueError(
                    f"ligne {numero} : {brut!r} n'est pas un numéro de frame "
                    "(un entier seul par ligne)."
                ) from None
            x = y = None
            pose = re.search(r"clic \((-?\d+), (-?\d+)\)", commentaire)
            if pose:
                x, y = int(pose.group(1)), int(pose.group(2))
            s.entrees.append((frame, x, y))
        return s


class SourceVideo:
    """Décode la vidéo de référence, bornée au segment [debut, fin).

    Même contrat que la source factice des tests : `suivante`/`precedente`
    renvoient None aux bords du segment, `aller_a` saute à une frame absolue.
    Le décodage est séquentiel vers l'avant ; un pas arrière repose le curseur
    de décodage (coût d'un seek, acceptable pour un geste humain).
    """

    def __init__(
        self, debut: int, fin: int, chemin: str | pathlib.Path = banc.VIDEO_REF
    ) -> None:
        import cv2

        self.debut, self.fin = debut, fin
        self._cap = cv2.VideoCapture(str(chemin))
        if not self._cap.isOpened():
            raise FileNotFoundError(f"vidéo illisible : {chemin}")
        self.fps = self._cap.get(cv2.CAP_PROP_FPS) or 30.0
        self.index = debut
        if debut > 0:
            self._cap.set(cv2.CAP_PROP_POS_FRAMES, debut)

    def _lire(self):
        ok, img = self._cap.read()
        return img if ok else None

    def suivante(self):
        if self.index + 1 >= self.fin:
            return None
        img = self._lire()
        if img is None:
            return None
        self.index += 1
        return img

    def precedente(self):
        import cv2

        if self.index - 1 < self.debut:
            return None
        self.index -= 1
        self._cap.set(cv2.CAP_PROP_POS_FRAMES, self.index)
        return self._lire()

    def aller_a(self, index: int):
        import cv2

        self.index = index
        self._cap.set(cv2.CAP_PROP_POS_FRAMES, index)
        return self._lire()

    def fermer(self) -> None:
        self._cap.release()


class FenetreAnnotation(QWidget):
    """L'outil de l'opérateur : cliquer une tête SUR la ligne, frame enregistrée.

    La ligne verte et le numéro de frame sont dessinés par les MÊMES briques
    que le banc (`verite_terrain`) : ce que l'opérateur voit est exactement ce
    que `comparer` confrontera au moteur. Le clic vient de `WidgetVideo`, déjà
    testé : il arrive en coordonnées pixel de l'image source, sans conversion
    à réécrire ici.
    """

    def __init__(
        self,
        source=None,
        sortie: str | pathlib.Path | None = None,
        debut: int = banc.DEBUT_REF,
        fin: int = banc.FIN_REF,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.debut, self.fin = debut, fin
        self.source = source if source is not None else SourceVideo(debut, fin)
        self.sortie = (
            pathlib.Path(sortie)
            if sortie is not None
            else banc.DOSSIER_BANC / f"segment_{debut}-{fin}_operateur.txt"
        )
        # Reprise : un fichier existant est rechargé, jamais écrasé en silence.
        # Une heure de clics perdue au redémarrage est une heure de banc en moins.
        self.session = SessionAnnotation()
        if self.sortie.exists():
            self.session = SessionAnnotation.depuis_texte(
                self.sortie.read_text(encoding="utf-8")
            )
        self.en_cours = False
        self._ligne = banc._ligne_de_reference(Config(ligne=banc.LIGNE_REF, sens=-1))

        self.setWindowTitle(f"Annotateur — vérité terrain ({debut}–{fin})")
        self.video = WidgetVideo()
        self.video.clic.connect(self._sur_clic)

        self.curseur = QSlider(Qt.Orientation.Horizontal)
        self.curseur.setRange(debut, fin - 1)
        self.curseur.setValue(debut)
        self.curseur.valueChanged.connect(self._sur_curseur)

        self.bouton_arriere = QPushButton("Précédente")
        self.bouton_lecture = QPushButton("Lecture")
        self.bouton_avant = QPushButton("Suivante")
        self.combo_vitesse = QComboBox()
        for texte, _ in VITESSES:
            self.combo_vitesse.addItem(texte)
        self.combo_vitesse.setCurrentIndex(1)
        self.label_frame = QLabel()
        self.bouton_arriere.clicked.connect(self._pas_arriere)
        self.bouton_lecture.clicked.connect(self._basculer_lecture)
        self.bouton_avant.clicked.connect(self._pas_avant)
        self.combo_vitesse.currentIndexChanged.connect(self._sur_vitesse)

        self.label_compte = QLabel()
        self.liste = QListWidget()
        self.bouton_annuler = QPushButton("Annuler le dernier")
        self.bouton_supprimer = QPushButton("Supprimer la sélection")
        self.bouton_enregistrer = QPushButton("Enregistrer")
        self.label_etat = QLabel(
            "Clic sur une tête SUR la ligne verte = 1 franchissement.\n"
            "Espace : lecture/pause · ←/→ : frame par frame."
        )
        self.label_etat.setWordWrap(True)
        self.bouton_annuler.clicked.connect(self._annuler)
        self.bouton_supprimer.clicked.connect(self._supprimer)
        self.bouton_enregistrer.clicked.connect(self._enregistrer)

        rangee = QHBoxLayout()
        for w in (
            self.bouton_arriere,
            self.bouton_lecture,
            self.bouton_avant,
            self.combo_vitesse,
        ):
            rangee.addWidget(w)
        rangee.addWidget(self.label_frame, stretch=1)

        colonne_liste = QVBoxLayout()
        colonne_liste.addWidget(self.label_compte)
        colonne_liste.addWidget(self.liste, stretch=1)
        colonne_boutons = QVBoxLayout()
        for b in (
            self.bouton_annuler,
            self.bouton_supprimer,
            self.bouton_enregistrer,
        ):
            colonne_boutons.addWidget(b)
        colonne_boutons.addWidget(self.label_etat)
        colonne_boutons.addStretch(1)
        bas = QHBoxLayout()
        bas.addLayout(colonne_liste, stretch=1)
        bas.addLayout(colonne_boutons)

        racine = QVBoxLayout(self)
        racine.addWidget(self.video, stretch=1)
        racine.addWidget(self.curseur)
        racine.addLayout(rangee)
        racine.addLayout(bas)

        self._minuteur = QTimer(self)
        self._minuteur.timeout.connect(self._tick)

        img = self.source.aller_a(debut)
        if img is not None:
            self._afficher(img)
        self._maj_liste()

    # -- Affichage ---------------------------------------------------------

    def _afficher(self, img) -> None:
        cadre = self._ligne.dessiner(img)
        banc._ecrire_frame_number(cadre, self.source.index)
        self.video.definir_image(cadre)
        self.curseur.blockSignals(True)
        self.curseur.setValue(self.source.index)
        self.curseur.blockSignals(False)
        self.label_frame.setText(f"frame {self.source.index} / {self.fin - 1}")

    def _maj_liste(self) -> None:
        self.liste.clear()
        for frame, x, y in self.session.entrees:
            if x is None or y is None:
                self.liste.addItem(str(frame))
            else:
                self.liste.addItem(f"{frame}  ({x}, {y})")
        self.label_compte.setText(f"Franchissements : {len(self.session)}")

    # -- Lecture -----------------------------------------------------------

    def _intervalle(self) -> int:
        vitesse = VITESSES[self.combo_vitesse.currentIndex()][1]
        return max(1, int(1000 / (self.source.fps * vitesse)))

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
        self._minuteur.start(self._intervalle())

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

    def _sur_vitesse(self) -> None:
        if self.en_cours:
            self._minuteur.start(self._intervalle())

    def _sur_curseur(self, valeur: int) -> None:
        self._pause()
        img = self.source.aller_a(valeur)
        if img is not None:
            self._afficher(img)

    # -- Annotation --------------------------------------------------------

    def _sur_clic(self, x: int, y: int) -> None:
        # Le clic FIGE la lecture : l'opérateur vient de dire « c'est ici »,
        # la frame affichée ne doit pas défiler sous son clic.
        self._pause()
        self.session.ajouter(self.source.index, x, y)
        self._maj_liste()

    def _annuler(self) -> None:
        self.session.annuler()
        self._maj_liste()

    def _supprimer(self) -> None:
        ligne = self.liste.currentRow()
        if ligne >= 0:
            self.session.supprimer(ligne)
            self._maj_liste()

    def _enregistrer(self) -> None:
        self.sortie.parent.mkdir(parents=True, exist_ok=True)
        self.sortie.write_text(self.session.vers_texte(), encoding="utf-8")
        self.label_etat.setText(f"Enregistré : {len(self.session)} franchissements.")
        print(f"annotation : {self.sortie} ({len(self.session)} franchissements)")
        print(
            "comparer   : python tools/verite_terrain.py comparer "
            f"{self.sortie.as_posix()}"
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
    argv = sys.argv[1:] if argv is None else argv
    debut, fin = banc.DEBUT_REF, banc.FIN_REF
    if len(argv) == 2:
        debut, fin = int(argv[0]), int(argv[1])
    elif argv:
        raise SystemExit("usage : python tools/annotateur.py [debut fin]")
    app = QApplication.instance() or QApplication(sys.argv[:1])
    fenetre = FenetreAnnotation(debut=debut, fin=fin)
    fenetre.resize(1280, 800)
    fenetre.show()
    raise SystemExit(app.exec())


if __name__ == "__main__":
    main()