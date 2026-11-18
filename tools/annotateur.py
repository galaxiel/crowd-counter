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

from PySide6.QtCore import Qt, QTimer, QUrl  # noqa: E402
from PySide6.QtGui import QDesktopServices  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QCheckBox,
    QComboBox,
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

from compteur.config import Config  # noqa: E402
from interface.widgets_video import WidgetVideo  # noqa: E402
from tools import verite_terrain as banc  # noqa: E402

#: Vitesses de lecture proposées. 0,5× par défaut : 15 i/s effectives, assez
#: lent pour voir le franchissement, assez rapide pour parcourir le segment.
VITESSES = [("0,15×", 0.15), ("0,25×", 0.25), ("0,5×", 0.5), ("1×", 1.0)]

#: Longueur du premier segment et du pas « Segment suivant », en frames. 900
#: = la longueur du créneau de référence validé (3600-4500) ; l'opérateur reste
#: libre de la changer dans les champs début/fin, sans recompiler.
LONGUEUR_SEGMENT_DEFAUT = 900

#: Fenêtre (en frames) autour du frame courant où l'on redessine TES clics déjà
#: posés : un repère vert évite de re-cliquer la même personne qui vient de
#: franchir la ligne. N'affiche JAMAIS le moteur — la vérité terrain reste
#: humaine et non contaminée.
PORTEE_REPERE = 15


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
        self.chemin = str(chemin)
        self._cap = cv2.VideoCapture(self.chemin)
        if not self._cap.isOpened():
            raise FileNotFoundError(f"vidéo illisible : {chemin}")
        self.nb_frames = int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT))
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


class SourceVide:
    """Source de secours quand aucune vidéo n'est ouverte.

    Sans elle, une vidéo de référence absente empêcherait la fenêtre de
    s'ouvrir — et le bouton « Ouvrir une vidéo… » resterait inatteignable.
    Elle rend une image noire, ne navigue pas, et n'a d'autre rôle que de
    laisser l'outil démarrer en attendant un vrai fichier.
    """

    def __init__(self, debut: int = 0, fin: int = 1) -> None:
        self.debut, self.fin = debut, max(debut + 1, fin)
        self.index = debut
        self.fps = 30.0
        self.nb_frames = self.fin - self.debut
        self.chemin = ""

    def _image(self):
        import numpy as np

        return np.zeros((720, 1280, 3), dtype=np.uint8)

    def suivante(self):
        return None

    def precedente(self):
        return None

    def aller_a(self, index: int):
        self.index = index
        return self._image()

    def fermer(self) -> None:
        pass


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
        chemin: str | pathlib.Path | None = None,
        nb_frames: int | None = None,
        dossier_lignes: str | pathlib.Path | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.debut, self.fin = debut, fin
        self.chemin = str(chemin) if chemin is not None else banc.VIDEO_REF
        self.nb_frames = int(nb_frames) if nb_frames is not None else max(fin, 1)
        self.longueur_segment = max(1, fin - debut)
        self._sans_video = False
        if source is None:
            try:
                source = SourceVideo(debut, fin, self.chemin)
            except Exception:
                source = SourceVide(debut, fin)
                self._sans_video = True
        self.source = source
        self.sortie = (
            pathlib.Path(sortie)
            if sortie is not None
            else self._nom_sortie(debut, fin)
        )
        # Reprise : un fichier existant est rechargé, jamais écrasé en silence.
        # Une heure de clics perdue au redémarrage est une heure de banc en moins.
        self.session = SessionAnnotation()
        if self.sortie.exists():
            self.session = SessionAnnotation.depuis_texte(
                self.sortie.read_text(encoding="utf-8")
            )
        self.en_cours = False
        # Ligne de comptage : mémorisée PAR VIDÉO (verite_terrain/lignes.json)
        # pour que `comparer` réutilise la même frontière, même quand on fait une
        # batterie de tests en changeant les paramètres. Sans mémoire : référence.
        self._mode_ligne = False
        self._points_ligne: list[tuple[int, int]] = []
        self.dossier_lignes = (
            pathlib.Path(dossier_lignes)
            if dossier_lignes is not None
            else banc.DOSSIER_BANC
        )
        self._fichier_lignes = self.dossier_lignes / "lignes.json"
        self.ligne, self.sens = self._ligne_initiale()
        self._reconstruire_ligne()

        self._maj_titre()
        self.video = WidgetVideo()
        self.video.clic.connect(self._sur_clic)

        # Rangée HAUT : choisir la vidéo et le segment à annoter. Changer de
        # vidéo recharge la source et repart au premier segment ; les champs
        # début/fin permettent d'ajuster un créneau précis ; « Segment suivant »
        # enchaîne sans revenir au début (une fois un segment fini).
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
        self.bouton_segment_suivant = QPushButton("Segment suivant ▶")
        self.bouton_segment_suivant.clicked.connect(self._segment_suivant)
        self.bouton_ligne = QPushButton("Tracer la ligne")
        self.bouton_ligne.clicked.connect(self._demarrer_tracage_ligne)
        self.bouton_sens = QPushButton("Inverser le sens")
        self.bouton_sens.clicked.connect(self._inverser_sens)
        rangee_haut = QHBoxLayout()
        rangee_haut.addWidget(self.bouton_ouvrir_video)
        rangee_haut.addWidget(self.case_tout)
        rangee_haut.addWidget(QLabel("de"))
        rangee_haut.addWidget(self.champ_debut)
        rangee_haut.addWidget(QLabel("à"))
        rangee_haut.addWidget(self.champ_fin)
        rangee_haut.addWidget(self.bouton_segment_suivant)
        rangee_haut.addWidget(self.bouton_ligne)
        rangee_haut.addWidget(self.bouton_sens)
        rangee_haut.addStretch(1)

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
        self.combo_vitesse.setCurrentIndex(2)  # 0,5× par défaut (indice de VITESSES)
        self.label_frame = QLabel()
        self.bouton_arriere.clicked.connect(self._pas_arriere)
        self.bouton_lecture.clicked.connect(self._basculer_lecture)
        self.bouton_avant.clicked.connect(self._pas_avant)
        self.combo_vitesse.currentIndexChanged.connect(self._sur_vitesse)

        self.label_compte = QLabel()
        self.liste = QListWidget()
        self.bouton_annuler = QPushButton("Annuler le dernier")
        self.bouton_supprimer = QPushButton("Supprimer la plus récente")
        self.bouton_enregistrer = QPushButton("Enregistrer")
        self.bouton_dossier = QPushButton("Ouvrir le dossier")
        self.label_etat = QLabel(
            "Clic sur une tête SUR la ligne verte = 1 franchissement.\n"
            "« Tracer la ligne » : place la frontière (2 clics) ; "
            "« Inverser le sens » règle le côté compté.\n"
            "Espace : lecture/pause · ←/→ : frame par frame."
        )
        self.label_etat.setWordWrap(True)
        self.bouton_annuler.clicked.connect(self._annuler)
        self.bouton_supprimer.clicked.connect(self._supprimer)
        self.bouton_enregistrer.clicked.connect(self._enregistrer)
        self.bouton_dossier.clicked.connect(self._ouvrir_dossier)

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
            self.bouton_dossier,
        ):
            colonne_boutons.addWidget(b)
        colonne_boutons.addWidget(self.label_etat)
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
        self._maj_liste()
        if self._sans_video:
            self.label_etat.setText(
                "Aucune vidéo ouverte. Clique sur « Ouvrir une vidéo… » pour "
                "commencer — toute la vidéo, ou un segment via début/fin."
            )

    # -- Affichage ---------------------------------------------------------

    def _afficher(self, img) -> None:
        cadre = self._ligne.dessiner(img)
        banc._ecrire_frame_number(cadre, self.source.index)
        # Repères de TES clics récents (jamais ceux du moteur) : vert vif au
        # frame courant, vert sombre autour — pour ne pas cliquer deux fois.
        import cv2

        for frame_repere, x, y in self._clics_proches(self.source.index):
            couleur = (0, 255, 0) if frame_repere == self.source.index else (0, 150, 0)
            cv2.circle(cadre, (int(x), int(y)), 9, couleur, 2)
        # Points déjà posés d'une ligne en cours de tracé.
        for px, py in self._points_ligne:
            cv2.circle(cadre, (int(px), int(py)), 10, (255, 160, 0), 2)
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

    def _clics_proches(self, index: int) -> list[tuple[int, int, int]]:
        """Clics posés à ±PORTEE_REPERE frames, avec leur position cliquée."""
        return [
            (f, x, y)
            for f, x, y in self.session.entrees
            if x is not None and y is not None and abs(f - index) <= PORTEE_REPERE
        ]

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
        if self._mode_ligne:
            self._points_ligne.append((int(x), int(y)))
            if len(self._points_ligne) == 1:
                self.bouton_ligne.setText("Tracer la ligne… (2/2)")
                self.label_etat.setText(
                    "Premier point posé. Clique la deuxième extrémité de la ligne."
                )
                self._redessiner_courant()
                return
            (x1, y1), (x2, y2) = self._points_ligne
            if abs(x1 - x2) < 5 and abs(y1 - y2) < 5:
                # Deux clics au même endroit : ligne dégénérée, on garde le 1er.
                self._points_ligne = [(x1, y1)]
                self.label_etat.setText(
                    "Ligne trop courte : clique un deuxième point plus éloigné."
                )
                self._redessiner_courant()
                return
            self.ligne = (float(x1), float(y1), float(x2), float(y2))
            self._mode_ligne = False
            self._points_ligne = []
            self.bouton_ligne.setText("Tracer la ligne")
            self._reconstruire_ligne()
            self._enregistrer_ligne()
            self.label_etat.setText(
                "Ligne tracée et mémorisée pour cette vidéo. "
                "« Inverser le sens » si le sens compté est l'autre."
            )
            self._redessiner_courant()
            return
        self.session.ajouter(self.source.index, x, y)
        self._maj_liste()
        self._redessiner_courant()  # affiche tout de suite le repère du clic

    # -- Ligne de comptage -------------------------------------------------

    def _ligne_initiale(
        self,
    ) -> tuple[tuple[float, float, float, float], int]:
        if not self._sans_video:
            stockee = banc.charger_ligne(self.chemin, self._fichier_lignes)
            if stockee is not None:
                return stockee
        return banc.LIGNE_REF, -1

    def _reconstruire_ligne(self) -> None:
        self._ligne = banc._ligne_de_reference(
            Config(ligne=self.ligne, sens=self.sens)
        )

    def _enregistrer_ligne(self) -> None:
        if self._sans_video:
            return
        banc.enregistrer_ligne(
            self.chemin, self.ligne, self.sens, self._fichier_lignes
        )

    def _redessiner_courant(self) -> None:
        img = self.source.aller_a(self.source.index)
        if img is not None:
            self._afficher(img)

    def _demarrer_tracage_ligne(self) -> None:
        self._pause()
        self._mode_ligne = True
        self._points_ligne = []
        self.bouton_ligne.setText("Tracer la ligne… (1/2)")
        self.label_etat.setText(
            "Trace la ligne : clique les DEUX extrémités sur l'image "
            "(le sens se règle ensuite avec « Inverser le sens »)."
        )

    def _inverser_sens(self) -> None:
        self.sens = -1 if self.sens == 1 else 1
        self._reconstruire_ligne()
        self._enregistrer_ligne()
        self._redessiner_courant()

    def _annuler(self) -> None:
        self.session.annuler()
        self._maj_liste()

    def _supprimer(self) -> None:
        ligne = self.liste.currentRow()
        if ligne < 0 and len(self.session):
            # Rien de sélectionné : retire la PLUS RÉCENTE (comme l'outil boîtes).
            ligne = len(self.session) - 1
        if ligne >= 0:
            self.session.supprimer(ligne)
            self._maj_liste()
            self._redessiner_courant()

    def _enregistrer(self) -> None:
        self.sortie.parent.mkdir(parents=True, exist_ok=True)
        self.sortie.write_text(self.session.vers_texte(), encoding="utf-8")
        # Le chemin est affiché DANS la fenêtre : le lanceur .bat (pythonw)
        # n'a pas de console, le print ci-dessous serait invisible.
        self.label_etat.setText(
            f"Enregistré : {len(self.session)} franchissements.\n"
            f"Fichier : {self.sortie}"
        )
        print(f"annotation : {self.sortie} ({len(self.session)} franchissements)")
        commande = f"python tools/verite_terrain.py comparer {self.sortie.as_posix()}"
        if str(self.chemin) != str(banc.VIDEO_REF):
            commande += f' --video "{self.chemin}"'
        print(f"comparer   : {commande}")

    def _ouvrir_dossier(self) -> None:
        dossier = self.sortie.parent
        dossier.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(dossier)))

    # -- Vidéo / segment ---------------------------------------------------

    def _nom_sortie(self, debut: int, fin: int) -> pathlib.Path:
        """Nom du fichier d'annotations pour ce segment.

        La vidéo de RÉFÉRENCE garde le nom historique `segment_…` (les clics
        déjà posés restent liés) ; une AUTRE vidéo porte son nom, pour ne pas
        mélanger deux vérités terrain.
        """
        if str(self.chemin) == str(banc.VIDEO_REF):
            nom = f"segment_{debut}-{fin}_operateur.txt"
        else:
            nom = f"{pathlib.Path(self.chemin).stem}_segment_{debut}-{fin}_operateur.txt"
        return banc.DOSSIER_BANC / nom

    def _maj_titre(self) -> None:
        nom = pathlib.Path(self.chemin).name
        self.setWindowTitle(
            f"Annotateur — vérité terrain ({self.debut}–{self.fin}) · {nom}"
        )

    def _recharger_session(self) -> None:
        self.session = SessionAnnotation()
        if self.sortie.exists():
            self.session = SessionAnnotation.depuis_texte(
                self.sortie.read_text(encoding="utf-8")
            )
        self._maj_liste()

    def _configurer_plage(self, debut: int, fin: int) -> None:
        """Applique une nouvelle plage [debut, fin) : piste, champs, fichier."""
        debut = max(0, int(debut))
        fin = max(debut + 1, int(fin))
        self.debut, self.fin = debut, fin
        # Bornes de la source = plage courante : la navigation s'arrête à fin.
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
        self.sortie = self._nom_sortie(debut, fin)
        self._recharger_session()
        self._maj_titre()
        img = self.source.aller_a(debut)
        if img is not None:
            self._afficher(img)

    def _sur_case_tout(self, coche: bool) -> None:
        self.champ_debut.setEnabled(not coche)
        self.champ_fin.setEnabled(not coche)
        self.bouton_segment_suivant.setEnabled(not coche)
        if coche:
            self._configurer_plage(0, self.nb_frames)
        else:
            self._configurer_plage(0, min(self.longueur_segment, self.nb_frames))

    def _sur_champs(self) -> None:
        debut = self.champ_debut.value()
        fin = self.champ_fin.value()
        if fin <= debut:
            fin = min(debut + 1, self.nb_frames)
            if fin <= debut:
                debut = max(0, fin - 1)
        self.longueur_segment = max(1, fin - debut)
        self._configurer_plage(debut, fin)

    def _segment_suivant(self) -> None:
        if self.case_tout.isChecked() or self.fin >= self.nb_frames:
            return
        debut = self.fin
        fin = min(debut + self.longueur_segment, self.nb_frames)
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
        """Charge une nouvelle vidéo et repart au premier segment.

        `source`/`nb_frames` sont injectables pour les tests (pas de vraie
        vidéo) ; en production, la source est construite ici.
        """
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
        self.champ_debut.blockSignals(True)
        self.champ_debut.setRange(0, max(0, self.nb_frames - 1))
        self.champ_debut.blockSignals(False)
        self.champ_fin.blockSignals(True)
        self.champ_fin.setRange(1, self.nb_frames)
        self.champ_fin.blockSignals(False)
        self.longueur_segment = min(LONGUEUR_SEGMENT_DEFAUT, self.nb_frames)
        self.case_tout.blockSignals(True)
        self.case_tout.setChecked(False)
        self.case_tout.blockSignals(False)
        self.champ_debut.setEnabled(True)
        self.champ_fin.setEnabled(True)
        self.bouton_segment_suivant.setEnabled(True)
        # Ligne mémorisée pour CETTE vidéo (ou référence) ; tracé remis à zéro.
        stockee = banc.charger_ligne(self.chemin, self._fichier_lignes)
        self.ligne, self.sens = stockee if stockee else (banc.LIGNE_REF, -1)
        self._reconstruire_ligne()
        self._mode_ligne = False
        self._points_ligne = []
        self.bouton_ligne.setText("Tracer la ligne")
        self._configurer_plage(0, min(self.longueur_segment, self.nb_frames))

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
    nb_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) if cap.isOpened() else None
    cap.release()
    if len(argv) == 2:
        debut, fin = int(argv[0]), int(argv[1])
    elif argv:
        raise SystemExit("usage : python tools/annotateur.py [debut fin]")
    else:
        # Démarre sur le PREMIER segment ; « Toute la vidéo » ou les champs
        # début/fin permettent de changer d'étendue dans la fenêtre.
        debut = 0
        fin = min(LONGUEUR_SEGMENT_DEFAUT, nb_frames or banc.FIN_REF)
    app = QApplication.instance() or QApplication(sys.argv[:1])
    fenetre = FenetreAnnotation(debut=debut, fin=fin, nb_frames=nb_frames)
    fenetre.resize(1280, 800)
    fenetre.show()
    raise SystemExit(app.exec())


if __name__ == "__main__":
    main()