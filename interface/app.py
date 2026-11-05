"""Fenêtre principale : assemble le moteur, la lecture et l'affichage.

Trois décisions structurent ce module, et chacune a un test qui la verrouille.

**1. Deux minuteries, jamais une.** Le traitement d'une frame (détection YOLO
sur GPU, tracking, franchissement) et son affichage ont deux cadences
indépendantes : le traitement est aussi rapide que la machine le permet
(intervalle à 0 ms), l'affichage est cadencé à `CADENCE_AFFICHAGE_IPS`
(15 i/s, fixe). Séparer les deux garantit qu'une affichage plus lent ne
ralentit jamais le COMPTAGE : le décompte ne dépend pas de la vitesse de
présentation. (Un curseur de vitesse d'affichage a existé puis été retiré :
il ne réglait que le timer d'affichage, jamais celui du traitement.)

**2. La ligne se trace à la souris, en coordonnées image.** `WidgetVideo.clic`
émet déjà des pixels de l'image SOURCE ; ce module ne fait que les assembler en
`Ligne`. Toute la conversion écran -> pixel est dans le widget, testée
ailleurs : la dupliquer ici rouvrirait le risque d'une ligne décalée, invisible
à l'écran et qui ne se révèle qu'en comptant faux.

**3. Rien de lourd au démarrage.** CUDA est présent et `tetes-medium.pt` met plusieurs
secondes à monter. Le modèle est chargé sur « Lancer », jamais dans
`__init__` : la fenêtre s'ouvre immédiatement, l'opérateur trace sa ligne
pendant que le GPU se réveille.

Les boîtes de dialogue sont modales **seulement** si la fenêtre est visible.
Sans cette garde, un test qui provoque une erreur resterait bloqué sur un
« OK » que personne ne peut cliquer : le message tombe alors dans le journal et
dans la barre de statut, qui est visible dans les deux cas.
"""

from __future__ import annotations

import json
import logging
import math
import pathlib
import time

import cv2
from PySide6.QtCore import QObject, QThread, QTimer, QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QProgressDialog,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from compteur import VERSION, mise_a_jour
from compteur.compteur import TAILLE_LOT_DETECTION, Compteur
from compteur.config import (
    BANDE_APRES_PX,
    BANDE_AVANT_PX,
    DUREE_BOITE_COMPTEE_FRAMES,
    MODE_MANUEL,
    Config,
    dossiers_modeles,
    mode_peripherique,
    mode_resolution,
    resoudre_modele,
)
from compteur.detecteur import (
    Detecteur,
    charger_modele,
    message_modele_absent,
    peripherique_effectif,
)
from compteur.ligne import LIBELLES_SENS, Ligne
from compteur.tracker import Tracker
from interface.overlay import dessiner
from interface.panneau_reglages import (
    PanneauReglages,
    orientation_par_defaut_sens,
)
from interface.recap import PanneauRecap, formater_duree
from interface.ressources import appliquer_icone_classe, chemin_icone
from interface.style import (  # noqa: F401  (ré-export pour main.py)
    CHOIX_THEME,
    MODE_DEFAUT,
    appliquer_style,
    ecrire_modele_theme,
    lire_modele_theme,
)
from interface.widgets_video import WidgetVideo

log = logging.getLogger(__name__)

#: Cadence de référence quand la vidéo n'annonce pas la sienne (codec exotique,
#: conteneur mal écrit). 25 i/s est le standard des caméras de surveillance.
FPS_REPLI = 25.0

#: Cadence d'affichage pendant une analyse, en images par seconde. Le
#: traitement, lui, n'est PAS limité (timer à intervalle 0) : c'est le rendu
#: CPU par frame affichée qui coûte cher, et l'opérateur n'a pas besoin d'un
#: aperçu fluide pour lire un compteur. Voir le bloc des minuteries.
CADENCE_AFFICHAGE_IPS = 15

#: Lien du bouton de soutien. Le `data-slug` du widget Buy Me a Coffee fourni
#: par l'opérateur est `galaxiel` — le bouton natif ouvre cette page dans le
#: navigateur, ce qui donne le même résultat sans embarqué de JavaScript.
LIEN_SOUTIEN = "https://buymeacoffee.com/galaxiel"

#: Durée du flash rouge de comptage, en frames AFFICHÉES. Le flash sert à
#: repérer d'un coup d'œil l'instant d'un comptage ; le compter en frames
#: traitées le rendrait subliminal dès qu'on ralentit l'affichage.
FLASH_FRAMES = 3

#: Filtres du sélecteur de fichier, par ordre de préférence.
FILTRES_VIDEOS = (
    "Vidéos (*.mp4 *.avi *.mkv *.mov *.m4v *.webm);;Tous les fichiers (*)"
)

#: Extensions acceptées en glisser-déposer — le même ensemble que
#: `FILTRES_VIDEOS`, en minuscules : le dépôt ne doit pas accepter plus (ou
#: moins) que le sélecteur, sinon deux façons de charger diraient deux
#: choses différentes.
EXTENSIONS_VIDEO = frozenset({".mp4", ".avi", ".mkv", ".mov", ".m4v", ".webm"})

#: Mémoire du dernier dossier vidéo ouvert, entre deux lancements.
#:
#: Le dialogue « Charger la vidéo » partait toujours du dossier courant —
#: celui de l'exécutable — ce qui obligeait à remonter l'arborescence à
#: chaque ouverture. Le fichier est relatif au dossier courant, comme les
#: profils, et son nom `local_*.json` tombe sous le `.gitignore` existant
#: (`config/local_*.json`) : c'est une préférence d'un poste, pas du code.
FICHIER_MEMOIRE_VIDEO = pathlib.Path("config") / "local_dossier_video.json"

#: Mémoire des DERNIERS réglages utilisés, entre deux lancements. Même
#: contrat que la mémoire de dossier vidéo : préférence d'un poste, sous le
#: `.gitignore` (`config/local_*.json`), toute illisibilité rend les défauts.
#: La ligne tracée n'y figure PAS (elle appartient à la vidéo, pas au poste).
FICHIER_MEMOIRE_CONFIG = pathlib.Path("config") / "local_config.json"


def lire_derniere_config() -> Config:
    """Les réglages du dernier lancement, ou les défauts si rien de valide.

    Toute illisibilité — fichier absent, JSON cassé, champs inconnus d'une
    version antérieure — rend les défauts, jamais une erreur : reprendre
    ses réglages est un confort, pas une condition au démarrage. La ligne
    tracée est systématiquement vidée : elle appartient à la vidéo.
    """
    try:
        donnees = json.loads(FICHIER_MEMOIRE_CONFIG.read_text(encoding="utf-8"))
        config = Config.depuis_dict(donnees)
        config.ligne = None
        return config
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        if FICHIER_MEMOIRE_CONFIG.exists():
            log.info("réglages précédents illisibles, défauts appliqués : %s", exc)
        return Config.defauts()


def ecrire_derniere_config(config: Config) -> None:
    """Mémorise les réglages pour le prochain lancement. N'échoue jamais.

    La ligne tracée est retirée avant l'écriture : la recharger sur une
    autre vidéo tracerait une ligne au mauvais endroit sans que l'opérateur
    le voie — le défaut exact que la mémoire ne doit pas créer.
    """
    try:
        donnees = config.vers_dict()
        donnees["ligne"] = None
        FICHIER_MEMOIRE_CONFIG.parent.mkdir(parents=True, exist_ok=True)
        FICHIER_MEMOIRE_CONFIG.write_text(
            json.dumps(donnees, ensure_ascii=False), encoding="utf-8"
        )
    except (OSError, ValueError, TypeError) as exc:
        log.warning("réglages non mémorisés : %s", exc)


def lire_dernier_dossier() -> str:
    """Dossier de la dernière vidéo ouverte, ou `""` si mémoire absente.

    Toute illisibilité — fichier absent, JSON cassé, disque enlevé — rend
    `""`, pas une erreur : la mémoire d'un dialogue est un confort, jamais
    une condition au démarrage.
    """
    try:
        donnees = json.loads(FICHIER_MEMOIRE_VIDEO.read_text(encoding="utf-8"))
        return str(donnees.get("dossier", ""))
    except (OSError, ValueError, AttributeError):
        return ""


def ecrire_dernier_dossier(dossier: str) -> None:
    """Mémorise ``dossier`` pour la prochaine ouverture. N'échoue jamais.

    Un souci d'écriture (dossier protégé, disque plein) est loggé et
    ignoré : il ne doit pas empêcher d'ouvrir une vidéo qui, elle, a
    parfaitement réussi à se lire.
    """
    try:
        FICHIER_MEMOIRE_VIDEO.parent.mkdir(parents=True, exist_ok=True)
        FICHIER_MEMOIRE_VIDEO.write_text(
            json.dumps({"dossier": dossier}, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError as exc:
        log.warning("dossier vidéo non mémorisé : %s", exc)

#: TAILLE DE LA LISTE des boîtes vertes affichées après un comptage.
#:
#: La liste est bornée DEUX fois, par deux règles indépendantes, parce que
#: chacune rattrape une défaillance de l'autre :
#:
#: 1. **Une durée** (`DUREE_BOITE_COMPTEE_FRAMES`, 400 frames ≈ 13 s) : c'est
#:    la règle qui décide de la vie réelle d'une boîte verte. 250 px après la
#:    ligne à 0,69 px/frame mesuré (~362 frames) : c'est le temps que la
#:    personne met à sortir de la zone utile. Au-delà, elle n'est plus là,
#:    la garder n'apprend rien.
#: 2. **Un nombre** (cette constante, 200) : c'est le filet de sécurité. Si la
#:    règle de durée venait à ne pas purger — un `frame_index` qui ne
#:    progresse pas, une pause, un test qui fige le compteur — la liste ne peut
#:    pas croître sans fin. 200 boîtes vertes à l'écran seraient absurdes et
#:    illisibles ; en mémoire cela ne fait que ~200 tuples, quelques dizaines de
#:    kilo-octets, donc ce plafond ne coûte rien et garantit qu'aucune fuite
#:    n'est possible.
#:
#: Pourquoi 200 : à 256 personnes sur 3000 frames, il y a en moyenne 0,085
#: comptage par frame. Une durée de 400 frames donne donc ~34 boîtes vivantes
#: en régime normal. 200 est un ordre de grandeur au-dessus : le plafond ne
#: se déclenche jamais sur une analyse réelle, ce qui est exactement ce qu'on
#: veut d'un filet de sécurité — s'il se déclenchait, il masquerait un bug au
#: lieu de l'empêcher.
TAILLE_MAX_BOITES_COMPTES = 200

#: Durée de vidéo ANALYSÉE au-delà de laquelle un compteur resté à zéro doit
#: être signalé. Exprimé en SECONDES DE VIDÉO et non en frames affichées :
#: l'avertissement parle à l'opérateur qui regarde l'écran, or lui voit du
#: temps, pas un compteur d'images. Trois secondes suffisent à voir un groupe
#: arriver et à ne pas le compter, sans attendre la fin de la vidéo.
SEUIL_AVERTISSEMENT_SENS_S = 3.0

#: Le rappel, mot pour mot. Court, et une seule question : le défaut `sens`
#: vaut +1 alors que le cortège de la vidéo de référence marche vers la
#: gauche, et un zéro « rien ne traverse » ne se distingue pas, à l'écran,
#: d'un zéro « tout le monde est compté dans l'autre sens ».
AVERTISSEMENT_SENS = (
    "0 compté — le sens de la flèche correspond-il au sens de marche "
    "du cortège ?"
)


class _ChargementModele(QObject):
    """Charge les poids HORS du fil de l'IHM.

    Monter un modèle medium coûte plusieurs secondes (lecture disque + mise
    en mémoire, GPU compris) : sur le fil de l'IHM, il gelait la fenêtre —
    Stop et fermeture compris. Le motif est celui de `interface.demarrage` :
    un `QObject` déplacé dans un `QThread`, qui émet SON RÉSULTAT OU SON
    EXCEPTION sur `fini` — un échec doit ARRIVER à l'opérateur, pas tuer le
    thread en silence.
    """

    fini = Signal(object)

    def __init__(self, modele: str, peripherique: str) -> None:
        super().__init__()
        self._modele = modele
        self._peripherique = peripherique

    def run(self) -> None:
        try:
            self.fini.emit(charger_modele(self._modele, self._peripherique))
        except BaseException as exc:  # noqa: BLE001 — remonter l'échec est le contrat
            self.fini.emit(exc)


class _VerificationMaj(QObject):
    """Cherche une mise à jour HORS du fil de l'IHM (réseau, jamais bloquant).

    Le même passage PROFITE du démarrage pour effacer les restes d'un
    échange précédent (`.maj-*`, `*.ancienne`) : leur présence à ce moment
    prouve que la nouvelle version a démarré, donc que la sauvegarde a
    rempli son rôle. Tout échec (réseau, JSON) rend `None` — la recherche
    est un confort, jamais une condition au démarrage.
    """

    fini = Signal(object)

    def __init__(self, version: str, dossier: pathlib.Path) -> None:
        super().__init__()
        self._version = version
        self._dossier = dossier

    def run(self) -> None:
        try:
            mise_a_jour.nettoyer_anciennes(self._dossier.parent)
        except OSError as exc:
            log.info("nettoyage des restes de mise à jour : %s", exc)
        try:
            info = mise_a_jour.chercher_release(self._version)
        except Exception as exc:  # noqa: BLE001 — le réseau est hostile
            log.info("vérification de mise à jour ratée : %s", exc)
            info = None
        self.fini.emit(info)


class _InstallationMaj(QObject):
    """Télécharge, vérifie, prépare puis lance l'échange — hors fil de l'IHM.

    Chaque étape est annoncée (`etape`) pour que le dialogue dise où on en
    est. **Un échec n'a RIEN touché** : le zip est vérifié AVANT extraction,
    l'ancienne installation n'est renommée que par le script d'échange, et
    toute erreur arrive sur `echouee` avec un message lisible.
    """

    progression = Signal(int, int)
    etape = Signal(str)
    echouee = Signal(str)
    prete = Signal(str)

    def __init__(self, info: dict, dossier: pathlib.Path) -> None:
        super().__init__()
        self._info = info
        self._dossier = dossier
        self._annule = False

    def annuler(self) -> None:
        self._annule = True

    def run(self) -> None:
        version = self._info["version"]
        try:
            self.etape.emit("Téléchargement de la nouvelle version…")
            zip_cible = self._dossier.parent / f".maj-{version}.zip"

            def _prog(faits: int, total: int) -> None:
                self.progression.emit(faits, total)

            mise_a_jour.telecharger(
                self._info["url_zip"],
                zip_cible,
                taille_attendue=self._info["taille_zip"],
                progression=_prog,
                annule=lambda: self._annule,
            )
            self.etape.emit("Vérification de l'archive…")
            empreinte = mise_a_jour.sha256_fichier(zip_cible)
            if empreinte != str(self._info["sha256"]).lower():
                zip_cible.unlink(missing_ok=True)
                raise mise_a_jour.ErreurReseau(
                    "l'archive téléchargée ne correspond pas à son empreinte "
                    "publiée — elle a été effacée, rien n'a été installé"
                )
            self.etape.emit("Préparation de la nouvelle version…")
            bat = mise_a_jour.preparer_staging(zip_cible, self._dossier, version)
            zip_cible.unlink(missing_ok=True)
            self.etape.emit("Lancement de la nouvelle version…")
            mise_a_jour.lancer_echange(bat)
            self.prete.emit(version)
        except mise_a_jour.Annulation:
            self.echouee.emit("mise à jour annulée")
        except (mise_a_jour.ErreurReseau, mise_a_jour.ErreurDisque) as exc:
            self.echouee.emit(str(exc))
        except Exception as exc:  # noqa: BLE001 — l'opérateur doit savoir
            log.exception("installation de la mise à jour ratée")
            self.echouee.emit(str(exc) or exc.__class__.__name__)


class FenetrePrincipale(QMainWindow):
    """La fenêtre : vidéo à gauche, compteur et réglages à droite."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"Compteur de manifestation — {VERSION}")
        self.resize(1400, 850)
        # Glisser-déposer d'une vidéo : accepté au niveau de la FENÊTRE — les
        # enfants (vue vidéo, panneaux) ne réclament pas de dépôt, les
        # événements remontent donc jusqu'ici.
        self.setAcceptDrops(True)
        # Icône de fenêtre (barre de titre + barre des tâches). Reprise au
        # niveau application par `main.py` pour l'écran d'installation ; la
        # refaire ICI rend la fenêtre correcte même construite hors de
        # `main.py` (tests).
        icone = QIcon(str(chemin_icone()))
        if not icone.isNull():
            self.setWindowIcon(icone)
        # Correctif du 05/11 : Qt laisse une icône de CLASSE par défaut que
        # la barre des tâches affiche à la place de l'icône de fenêtre (voir
        # `ressources.appliquer_icone_classe`). `winId()` force la création
        # native MAINTENANT : le shell lit l'icône quand la fenêtre
        # apparaît, la poser après `show()` serait trop tard.
        appliquer_icone_classe(int(self.winId()))

        # Les réglages du DERNIER lancement, pas les défauts du dépôt : un
        # opérateur qui a tuné son seuil hier ne doit pas le retrouver à
        # zéro ce matin (demande opérateur 05/11). La ligne, elle, part de
        # zéro — elle appartient à la vidéo.
        self.config: Config = lire_derniere_config()
        self.cap = None
        #: Nombre total de frames annoncées par la vidéo chargée (0 si le
        #: conteneur ne le dit pas) : c'est le maximum de la barre de
        #: progression. Un conteneur muet sur ce chiffre bascule la barre en
        #: mode « occupé » plutôt qu'en pourcentage faux.
        self._nb_frames_video = 0
        self.video_finiment: pathlib.Path | None = None
        self.detecteur = None
        self.tracker = None
        self.compteur = None
        self.ligne: Ligne | None = None

        #: Points posés par l'opérateur, en cours de tracé (0, 1 ou 2).
        self._points_ligne: list[tuple[float, float]] = []
        #: Tracé « armé » : le clic suivant pose le premier point. Sans cette
        #: étape, un clic parasite en plein réglage décalerait la ligne du
        #: premier point venu — invisible à l'écran, faux au compteur.
        self._trace_arme = False
        #: Le traitement tourne (minuterie de traitement active).
        self._en_analyse = False
        #: Une analyse a AU MOINS été lancée sur la vidéo chargée — c'est
        #: ce qui distingue « Recommencer » d'un second « Lancer ».
        self._une_analyse_faite = False
        #: Une analyse a été démarrée et n'est pas terminée (pause comprise).
        self._session_ouverte = False
        #: Horloge de départ de l'analyse EN COURS (`time.monotonic`), pour le
        #: débit affiché sous la barre. `None` hors analyse.
        self._debut_analyse: float | None = None
        #: Début de la pause en cours, pour que le temps de pause ne soit PAS
        #: décompté du débit : 10 minutes d'arrêt ne doivent pas afficher un
        #: « 2 i/s » qui décrit l'inactivité de l'opérateur, pas le moteur.
        self._pause_debut: float | None = None
        #: Un chargement de modèle tourne dans son thread. Drapeau
        #: d'unicité : un second « Lancer » pendant ce temps est ignoré,
        #: et l'activation des boutons s'y aligne (Stop reste actif —
        #: c'est par lui qu'on annule le chargement).
        self._chargement_en_cours = False
        #: `(modèle, périphérique)` que le thread en cours est censé livrer.
        #: Un résultat qui ne correspond plus — réglages modifiés en route,
        #: chargement annulé puis relancé sur un autre modèle — est JETÉ,
        #: jamais monté : il compterait avec des poids que l'écran ne
        #: annonce pas.
        self._chargement_demande: tuple[str, str] = ()
        #: Le thread et son worker : le worker doit rester référencé tant
        #: que son thread tourne (sinon Python le détruirait en marche).
        self._thread_modele: QThread | None = None
        self._worker_modele: _ChargementModele | None = None
        #: L'avertissement « 0 compté » a déjà été montré pour CETTE analyse.
        #: Vrai une fois, remis à faux à chaque nouveau comptage.
        self._avertissement_sens_affiche = False
        #: Nom du modèle effectivement chargé dans `self.detecteur`.
        self._modele_charge = ""
        self._flash = 0
        #: Dernier `FrameResult` traité, en attente d'affichage.
        self._resultat_courant = None
        #: Index du dernier résultat déjà affiché, pour ne pas redessiner.
        self._index_affiche = -1
        #: Position du marqueur de premier point, en pixels image.
        self._apercu_point: tuple[int, int] | None = None
        #: Boîtes VERTES des personnes comptées, encore à l'écran.
        #:
        #: Ce n'est PAS du tracking figé : le track continue d'être suivi après
        #: le franchissement (`_purger_franchis` ne touche pas au tracker), donc
        #: on stocke le `track_id` et on cherche sa position COURANTE dans le
        #: résultat — la boîte verte suit la tête au lieu de rester collée à la
        #: ligne. Quand la personne sort de la bande, elle n'est plus détectée,
        #: le track meurt et la boîte disparaît avec lui.
        #:
        #: Liste de tuples `(frame_comptage, track_id)`, bornée en nombre —
        #: voir `TAILLE_MAX_BOITES_COMPTES`.
        self._boites_comptees: list[tuple[int, int]] = []
        #: Nombre d'événements du compteur déjà transformés en boîtes vertes.
        #: L'affichage peut sauter des frames (vitesse lente) : sans ce
        #: marqueur, on relirait sans cesse les mêmes événements et on
        #: re-créerait des boîtes déjà vues. Il progresse d'un cran par
        #: événement consommé, et repart de zéro quand l'historique est vidé
        #: (nouvelle analyse).
        self._dernier_evenement_affiche = 0
        #: Position de la ligne AU DÉBUT du glissement en cours, ou None.
        #: Le décalage émis par le widget est cumulé depuis l'ancrage : il faut
        #: donc repartir de la position de départ à chaque mouvement, sinon la
        #: ligne dériverait au lieu de suivre le curseur.
        self._ligne_avant_glissement: tuple | None = None
        #: Connexion au changement de thème de l'OS (mode « suivre le
        #: système »). Référence conservée pour être débranchée proprement
        #: quand on quitte le mode — sinon un changement d'OS écraserait un
        #: choix manuel fait entre-temps.
        self._connexion_schema = None
        #: Mise à jour : thread, worker et dialogue de progression —
        #: référencés tant qu'ils tournent (un worker non référencé est
        #: collecté en pleine exécution, crash sans message).
        self._thread_maj: QThread | None = None
        self._worker_maj: QObject | None = None
        self._dialogue_maj: QProgressDialog | None = None

        self._construire()
        self._connecter()
        self.compteur_total = 0
        self.presents = 0
        self.frames = 0
        self.maj_compteurs(0, 0, 0)
        self._maj_boutons()
        self._verifier_mise_a_jour()

    # -- Construction ----------------------------------------------------

    def _construire(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        racine = QHBoxLayout(central)
        racine.setContentsMargins(8, 8, 8, 8)
        racine.setSpacing(10)

        # La vidéo ET sa barre de progression forment un bloc : la barre est
        # lisible SOUS l'image, là où l'œil reste pendant l'analyse. La
        # noyer dans la colonne de droite, entre le compteur et les réglages,
        # la rendrait invisible — et l'opérateur repartirait à ne pas savoir
        # où en est le traitement.
        self.video = WidgetVideo()
        self.video.setMinimumWidth(760)
        colonne_video = QVBoxLayout()
        colonne_video.addWidget(self.video, stretch=1)

        self.barre_progression = QProgressBar()
        self.barre_progression.setFormat("%v / %m frames (%p %)")
        self.barre_progression.setVisible(False)
        colonne_video.addWidget(self.barre_progression)

        # Débit réel et temps restant, DIRECTEMENT SOUS la barre : c'est là
        # que l'œil cherche « ça avance, ça mettra combien ? ». Le temps
        # restant est une ESTIMATION (marquée « ≈ ») : elle n'a de sens que
        # pendant l'analyse, d'où un label dédié plutôt que le format de la
        # barre, qui, lui, reste affiché en fin d'analyse.
        self.label_debit = QLabel("")
        self.label_debit.setVisible(False)
        colonne_video.addWidget(self.label_debit)

        racine.addLayout(colonne_video, stretch=3)

        colonne = QVBoxLayout()
        racine.addLayout(colonne, stretch=2)

        self.titre_compteur = QLabel("PERSONNES COMPTÉES")
        self.titre_compteur.setObjectName("compteur_titre")
        self.titre_compteur.setAlignment(Qt.AlignmentFlag.AlignCenter)
        colonne.addWidget(self.titre_compteur)

        self.label_compteur = QLabel("0")
        self.label_compteur.setObjectName("compteur")
        self.label_compteur.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Largeur minimale : sans elle, la colonne se resserre quand le chiffre
        # passe de 1 à 2 chiffres et le nombre se décale sous l'œil de
        # l'opérateur. C'est le seul chiffre lu de loin — il doit rester au
        # même endroit.
        self.label_compteur.setMinimumWidth(280)
        colonne.addWidget(self.label_compteur)

        # Le compteur de « présents » et celui de « frames » ont été retirés
        # de l'affichage : deux chiffres que l'opérateur ne regardait jamais,
        # et qui occupaient la place sous le seul chiffre qui compte. Les
        # VALEURS restent calculées — `maj_compteurs` continue de les
        # mémoriser, et le récapitulatif de fin d'analyse en dépendent. On ne
        # retire que l'étiquette.

        # Le périphérique de calcul est affiché EN PERMANENCE, dans son PROPRE
        # label et non dans `label_statut`.
        #
        # `label_statut` est écrasé à chaque changement d'état (vidéo chargée,
        # analyse en cours, pause, erreur) : un indicateur de calcul mis là
        # disparaîtrait précisément quand l'opérateur en a le plus besoin. Un
        # label dédié n'est jamais réécrit, donc l'information est toujours là.
        # Il est placé SOUS le compteur et au-dessus de la barre de statut, et
        # jamais à côté du chiffre : le compteur reste libre pour le résultat.
        self.label_peripherique = QLabel()
        self.label_peripherique.setObjectName("sous_titre")
        self.label_peripherique.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._maj_peripherique()
        colonne.addWidget(self.label_peripherique)

        # L'etat de TORCH lui-meme (version, GPU reellement utilise, ou
        # « absent ») est un label distinct de `label_peripherique`, et pour
        # une raison differente : `label_peripherique` dit ce que le REGLAGE
        # produit, y compris quand torch manque (« CPU uniquement » parce
        # qu'aucun GPU n'est visible). `label_torch` dit si le moteur de
        # calcul est INSTALLE. Les deux se contredisent dans le cas
        # interessant — une machine avec GPU et sans torch — et c'est
        # justement ce cas qu'il faut voir sans ambiguite.
        self.label_torch = QLabel()
        self.label_torch.setObjectName("sous_titre")
        self.label_torch.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label_torch.setWordWrap(True)
        self._etat_torch = None
        colonne.addWidget(self.label_torch)

        # L'avertissement « 0 compté » vit dans son PROPRE label, comme le
        # périphérique de calcul et pour la même raison : `label_statut` est
        # réécrit à chaque changement d'état (vidéo chargée, pause, erreur,
        # fin de lecture) et l'effacerait au moment précis où l'opérateur en a
        # besoin. Un label dédié, jamais réécrit sauf par cet avertissement
        # lui-même, tient jusqu'à ce que le compteur reparte.
        #
        # Il est SOUS le compteur, dans la colonne de droite, juste au-dessus
        # de la barre de statut : c'est là que l'œil va chercher pourquoi le
        # chiffre ne bouge pas. Il est masqué (et non « vide ») quand il n'a
        # rien à dire — un label vide garde sa place dans la colonne et ferait
        # sauter la mise en page.
        self.label_avertissement = QLabel()
        self.label_avertissement.setObjectName("avertissement")
        self.label_avertissement.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label_avertissement.setWordWrap(True)
        self.label_avertissement.setVisible(False)
        colonne.addWidget(self.label_avertissement)

        self.label_statut = QLabel("Charge une vidéo (ou glisse-la ici) pour commencer.")
        self.label_statut.setObjectName("sous_titre")
        self.label_statut.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label_statut.setWordWrap(True)
        self.label_statut.setMinimumHeight(56)
        colonne.addWidget(self.label_statut)

        # Le récapitulatif de fin d'analyse est une SECTION de la colonne de
        # droite, pas un onglet. La fenêtre n'a pas d'organisation par onglets
        # — elle a une colonne d'affichage et une colonne de réglages — et un
        # QTabWidget aurait imposé de choisir à chaque instant entre la vidéo
        # et son bilan : l'opérateur ne verrait plus la scène en lisant le
        # décompte. Une section masquée jusqu'à la fin de l'analyse garde les
        # deux visibles en même temps, et ne coûte aucune place avant qu'il y
        # ait quelque chose à montrer.
        self.recap = PanneauRecap()
        self.recap.setVisible(False)
        colonne.addWidget(self.recap, stretch=1)

        self.panneau = PanneauReglages(self.config)
        # Le panneau est dans une zone défilante, et la zone reste nécessaire
        # même aide repliée. Mesuré : panneau à 984 px aide masquée, 2138 px
        # aide dépliée, pour 618 px disponibles dans une fenêtre de 850 — la
        # vidéo, le compteur et la barre de boutons mangent déjà 232 px. Sans
        # zone, Qt comprimerait le panneau et le bouton « Lancer » deviendrait
        # inatteignable : l'analyse ne serait plus lançable du tout.
        #
        # Ce que la tâche 18 a changé n'est donc pas la zone mais son contenu :
        # les encarts d'aide sont repliés derrière le bouton « Aide » du panneau.
        # On a gagné 1154 px de défilement sans retirer un mot d'explication —
        # elles sont toutes là, à deux endroits : au survol du champ, et d'un clic
        # dans le panneau quand on veut les lire.
        zone = QScrollArea()
        zone.setWidget(self.panneau)
        zone.setWidgetResizable(True)
        zone.setFrameShape(QScrollArea.Shape.NoFrame)
        colonne.addWidget(zone, stretch=1)

        barre = QHBoxLayout()
        self.btn_video = QPushButton("Charger la vidéo")
        self.btn_ligne = QPushButton("Tracer la ligne")
        self.btn_ligne.setToolTip(
            "Clique ensuite deux points sur l'image, aux deux extrémités de "
            "la limite que tu veux compter.\n"
            "Le sens se règle ensuite d'un clic sur le bouton « Sens : … » "
            "de cette barre — son libellé dit exactement ce qui est compté."
        )
        # Le sens de comptage vit ICI, pas dans le panneau (demande
        # opérateur du 05/11/2026) : c'est un geste de la vidéo, pas un
        # réglage du moteur — on l'inverse d'un clic, la flèche verte le
        # montre tout de suite.
        self.btn_sens = QPushButton("")
        self.btn_sens.setToolTip(
            "Inverse le sens de comptage (la flèche verte montre le sens "
            "compté)."
        )
        self.btn_sens.clicked.connect(self._on_inverser_sens)
        self.btn_lancer = QPushButton("Lancer")
        self.btn_lancer.setObjectName("primaire")
        self.btn_pause = QPushButton("Pause")
        self.btn_stop = QPushButton("Stop")
        # « Recommencer » est le LANCER du deuxième essai : même action
        # (rembobinage, compteur à zéro, modèle conservé), nom explicite —
        # en fin d'analyse, « Lancer » tout seul ne disait pas qu'un essai
        # repartait de zéro sans recharger la vidéo (constat opérateur).
        self.btn_recommencer = QPushButton("Recommencer")
        self.btn_recommencer.setToolTip(
            "Relance l'analyse du DÉBUT : la vidéo est rembobinée, le "
            "compteur remis à zéro. Le modèle reste chargé — ça repart "
            "tout de suite."
        )
        self.btn_recommencer.clicked.connect(self.lancer)
        for b in (
            self.btn_video,
            self.btn_ligne,
            self.btn_sens,
            self.btn_lancer,
            self.btn_pause,
            self.btn_stop,
            self.btn_recommencer,
        ):
            barre.addWidget(b)

        # Choix du thème (sombre / clair / suivre le système), en bout de
        # barre de boutons. Ce n'est PAS un réglage du panneau : le panneau
        # produit une Config du MOTEUR, et le thème n'a rien à y faire — ni
        # dans les profils, ni dans la config par défaut. Le mode est
        # persisté à chaque changement (`interface.style`) et relu au
        # prochain démarrage par `main.py`, avant que cette fenêtre existe.
        self.choix_theme = QComboBox()
        for libelle, _mode in CHOIX_THEME:
            self.choix_theme.addItem(libelle)
        self.choix_theme.setCurrentIndex(
            max(0, [m for _, m in CHOIX_THEME].index(lire_modele_theme()))
        )
        self.choix_theme.setToolTip(
            "Thème de l'interface. « Sombre » reste le défaut recommandé : "
            "le compteur est prévu pour être lu dehors, en plein jour. "
            "« Suivre le système » adopte le thème clair ou sombre de "
            "Windows, et le suit quand il change."
        )
        etiquette_theme = QLabel("Thème")
        etiquette_theme.setObjectName("libelle_reglage")
        barre.addWidget(etiquette_theme)
        barre.addWidget(self.choix_theme)
        # « À propos » : version, vérification MANUELLE de mise à jour
        # (le bouton vert, lui, n'apparaît que QUAND une mise à jour
        # existe) et lien vers les versions. Demande opérateur du
        # 05/11/2026 — candidat v2.10 item 2, validé à l'oral.
        self.btn_a_propos = QPushButton("À propos")
        self.btn_a_propos.setToolTip(
            "Version du logiciel, vérification manuelle de mise à jour, "
            "page des versions."
        )
        self.btn_a_propos.clicked.connect(self._ouvrir_a_propos)
        barre.addWidget(self.btn_a_propos)
        self._barre_boutons = barre
        colonne.addLayout(barre)

        # Bouton de soutien, discret, tout en bas sous la barre de boutons.
        # Ce n'est pas un réglage : il ouvre simplement la page de don dans le
        # navigateur. Pas de JS, pas de widget web — un lien natif, qui marche
        # hors ligne et ne ralentit rien.
        self.btn_soutenir = QPushButton("☕ Buy me a coffee")
        self.btn_soutenir.setObjectName("soutenir")
        self.btn_soutenir.setToolTip(
            "Soutenir le développement du compteur — ouvre la page de don "
            "dans ton navigateur."
        )
        colonne.addWidget(self.btn_soutenir, alignment=Qt.AlignmentFlag.AlignHCenter)

        # Traitement : intervalle 0, donc « aussi vite que possible ». C'est
        # le GPU qui fixe la cadence de cette minuterie, jamais un réglage
        # utilisateur : l'analyse va aussi vite que la machine le permet.
        self._timer_traitement = QTimer(self)
        self._timer_traitement.setInterval(0)
        # Affichage : ~15 i/s, PAS la cadence de traitement. Rendre la frame
        # (voile, boîtes, conversion Qt, mise à l'échelle) coûte en CPU autant
        # que l'inférence en GPU, et les deux tournent sur le même thread :
        # afficher chaque frame traitée plafonnerait le débit de comptage.
        # L'opérateur lit un compteur, pas un film — 15 i/s suffisent largement.
        # Le rattrapage des événements sautés est déjà prévu (voir
        # `_dernier_evenement_affiche`, écrit pour des frames non affichées),
        # et le comptage, lui, reste à la cadence du timer de traitement.
        self._timer_affichage = QTimer(self)
        self._timer_affichage.setInterval(1000 // CADENCE_AFFICHAGE_IPS)

    def _connecter(self) -> None:
        self.btn_video.clicked.connect(self._on_charger_video)
        self.btn_ligne.clicked.connect(self._on_tracer_ligne)
        self.btn_lancer.clicked.connect(self.lancer)
        self.btn_pause.clicked.connect(self._basculer_pause)
        self.btn_stop.clicked.connect(self.arreter)
        self.btn_soutenir.clicked.connect(self._on_soutenir)
        self.choix_theme.currentIndexChanged.connect(self._on_changement_theme)
        # Si le mode mémorisé est « suivre le système », le suivi doit être
        # armé dès l'ouverture — pas seulement au prochain changement de
        # thème dans le menu.
        self._suivre_systeme(lire_modele_theme() == "systeme")
        self._installer_raccourcis()
        self.video.clic.connect(self._on_clic_video)
        self.video.deplacement.connect(self._on_deplacement_video)
        self.video.deplacement_fini.connect(self._on_deplacement_fini)
        self.panneau.config_modifiee.connect(self._sur_config)
        self._timer_traitement.timeout.connect(self._tick)
        self._timer_affichage.timeout.connect(self._afficher)

        # Etat de torch initial, AVANT tout affichage. `preparer()` (v2)
        # rappelle `definir_etat_torch` juste apres la construction ; depuis
        # les sources, ou dans un test, c'est cette ligne qui donne un
        # indicateur honnete au lieu d'un label vide.
        self.definir_etat_torch(None)

    # -- Thème ------------------------------------------------------------

    def _on_changement_theme(self, _index: int) -> None:
        """Applique le thème choisi à chaud, le mémorise pour la prochaine fois.

        Le mode stocké est lu dans la VALEUR du choix, jamais dans l'indice :
        réordonner `CHOIX_THEME` ne peut pas retourner silencieusement un
        autre thème que celui affiché — même règle que pour le sens et le
        périphérique dans le panneau de réglages.
        """
        modes = [m for _, m in CHOIX_THEME]
        index = self.choix_theme.currentIndex()
        mode = modes[index] if 0 <= index < len(modes) else MODE_DEFAUT
        ecrire_modele_theme(mode)
        self._suivre_systeme(mode == "systeme")
        appliquer_style(QApplication.instance(), mode)
        log.info("thème appliqué : %s", mode)

    def _suivre_systeme(self, suivre: bool) -> None:
        """Branche (ou débranche) le suivi du thème de l'OS.

        En mode « suivre le système », un changement de thème Windows doit se
        répercuter sans redémarrage. Le branchement vit sur les `QStyleHints`
        de l'application ; le débranchement est systématique avant chaque
        rebranchement, pour que quitter le mode laisse un choix manuel intact.
        """
        if self._connexion_schema is not None:
            try:
                QApplication.instance().styleHints().colorSchemeChanged.disconnect(
                    self._connexion_schema
                )
            except (RuntimeError, TypeError):
                pass  # connexion déjà morte (fenêtre en fermeture)
            self._connexion_schema = None
        if suivre:
            self._connexion_schema = (
                QApplication.instance().styleHints().colorSchemeChanged.connect(
                    self._on_schema_systeme
                )
            )

    def _on_schema_systeme(self, *_args) -> None:
        """Réapplique le thème quand l'OS change de mode.

        Idempotent si le mode courant est sombre ou clair : `mode_reel` ne
        réagit au système QUE pour « systeme », donc rebrancher puis réappliquer
        ne peut pas écraser un choix manuel.
        """
        modes = [m for _, m in CHOIX_THEME]
        index = self.choix_theme.currentIndex()
        mode = modes[index] if 0 <= index < len(modes) else MODE_DEFAUT
        appliquer_style(QApplication.instance(), mode)

    # -- Mise à jour ------------------------------------------------------

    def _verifier_mise_a_jour(self, retour=None) -> bool:
        """Cherche une mise à jour en tâche de fond — EXÉCUTABLE GELÉ SEULEMENT.

        En développement (`python main.py`) il n'y a rien à mettre à jour,
        et les tests ne doivent pas toucher le réseau : le garde `frozen`
        rend toute la fonction silencieuse hors exe. La vérification part
        une fois, au démarrage ; un échec n'est signalé nulle part.

        `retour` (un QLabel) sert à la vérification MANUELLE du dialogue
        « À propos » : le résultat y est annoncé, au-delà du bouton vert.
        Le thread est le MÊME que celui du démarrage (`self._thread_maj`) :
        le `closeEvent` l'attend de façon bornée, vérification manuelle
        comprise.
        """
        dossier = mise_a_jour.dossier_application()
        if dossier is None:
            if retour is not None:
                retour.setText(
                    "Vérification possible dans l'application installée "
                    "seulement."
                )
            return False
        if self._thread_maj is not None and self._thread_maj.isRunning():
            if retour is not None:
                retour.setText("Une vérification est déjà en cours…")
            return False
        self._thread_maj = QThread()
        self._worker_maj = _VerificationMaj(VERSION, dossier)
        self._worker_maj.moveToThread(self._thread_maj)
        self._thread_maj.started.connect(self._worker_maj.run)
        self._worker_maj.fini.connect(self._maj_trouvee)
        self._worker_maj.fini.connect(self._thread_maj.quit)
        self._retour_verification = retour
        if retour is not None:
            # Slot de CET objet (récepteur) : le résultat du worker,
            # émis hors du fil IHM, arrive sur le fil de l'interface —
            # jamais de lambda nue (leçon du 04/11).
            self._worker_maj.fini.connect(self._annoncer_resultat_verification)
            retour.setText("Vérification en cours…")
        self._thread_maj.start()
        return True

    def _maj_trouvee(self, info) -> None:
        """Une version plus récente existe : un bouton vert le dit.

        Pas de dialogue imposé — le bouton n'apparaît que si une mise à
        jour existe, et l'opérateur décide. `sha256` absent : le niveau 2
        est refusé par conception (installer sans vérification n'est pas
        une option), le bouton ouvre simplement la page de release — le
        niveau 1, qui ne peut rien casser.
        """
        if info is None:
            return
        if info.get("sha256"):
            texte = f"Nouvelle version {info['version']} — installer"
            pourpointe = f"Mettre à jour vers {info['version']}"
            action = lambda _=False: self._installer_maj(info)  # noqa: E731
        else:
            texte = f"Nouvelle version {info['version']} — voir la page"
            pourpointe = (
                "L'archive de cette version n'est pas accompagnée de son "
                "empreinte : par prudence, l'installation automatique est "
                "refusée — le bouton ouvre la page de téléchargement."
            )
            url = info.get("url_page", "")
            action = lambda _=False: QDesktopServices.openUrl(QUrl(url))  # noqa: E731
        self.btn_maj = QPushButton(texte)
        self.btn_maj.setObjectName("maj_disponible")
        self.btn_maj.setToolTip(pourpointe)
        self.btn_maj.clicked.connect(action)
        self._barre_boutons.addWidget(self.btn_maj)

    def _installer_maj(self, info: dict) -> None:
        """Confirme, puis pilote l'installation (thread + dialogue modal).

        Modal : pendant le téléchargement, la fenêtre principale est
        intouchable — pas de fermeture qui tuerait le thread en pleine
        écriture. L'annulation est bornée (entre deux blocs réseau) et un
        téléchargement interrompu reprendra où il en était.
        """
        dossier = mise_a_jour.dossier_application()
        if dossier is None:
            return
        taille_mo = max(1, self._info_mo(info))
        reponse = QMessageBox.question(
            self,
            "Installer la mise à jour",
            f"Passer à la version {info['version']} ?\n\n"
            f"L'application télécharge l'archive (~{taille_mo} Mo), vérifie "
            "son empreinte, puis se ferme et se relance toute seule.\n\n"
            "Réglages, profils et modèles déposés sont conservés ; "
            "l'ancienne version reste en sauvegarde jusqu'au prochain "
            "démarrage.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reponse != QMessageBox.StandardButton.Yes:
            return
        dialogue = QProgressDialog("Préparation…", "Annuler", 0, 100, self)
        dialogue.setWindowTitle("Mise à jour")
        dialogue.setWindowModality(Qt.WindowModality.WindowModal)
        dialogue.setMinimumDuration(0)
        self._dialogue_maj = dialogue
        self._thread_maj = QThread()
        self._worker_maj = _InstallationMaj(info, dossier)
        self._worker_maj.moveToThread(self._thread_maj)
        self._thread_maj.started.connect(self._worker_maj.run)
        # La progression passe par un SLOT DE LA FENÊTRE, pas par une lambda :
        # une connexion sans objet récepteur s'exécute dans le thread ÉMETTEUR
        # (le thread réseau), et toucher un widget Qt depuis là gèle
        # l'interface — mesuré en conditions réelles le 04/11 (fenêtre
        # « ne réponds plus » dès le premier bloc de téléchargement).
        self._worker_maj.progression.connect(self._maj_progression)
        self._worker_maj.etape.connect(dialogue.setLabelText)
        self._worker_maj.echouee.connect(self._maj_echouee)
        self._worker_maj.prete.connect(self._maj_prete)
        dialogue.canceled.connect(self._worker_maj.annuler)
        self._thread_maj.start()

    def _maj_progression(self, faits: int, total: int) -> None:
        """Progression du téléchargement — REÇUE sur le fil de l'IHM.

        Slot de la fenêtre exprès : c'est lui qui donne à la connexion un
        objet récepteur, donc le bon fil d'exécution (voir le commentaire
        du branchement dans `_installer_maj`).
        """
        if self._dialogue_maj is not None:
            self._dialogue_maj.setValue(int(faits * 100 / max(1, total)))

    @staticmethod
    def _info_mo(info: dict) -> int:
        return int(info.get("taille_zip", 0)) // (1024 * 1024)

    def _maj_echouee(self, message: str) -> None:
        """Échec d'installation : dit-le, sans paniquer l'écran."""
        if self._dialogue_maj is not None:
            self._dialogue_maj.reset()
            self._dialogue_maj = None
        if message != "mise à jour annulée":
            self._signaler(
                "Mise à jour non installée",
                f"L'installation n'a pas abouti — rien n'a été modifié.\n\n{message}",
                grave=True,
            )

    def _maj_prete(self, _version: str) -> None:
        """Échange armé : l'app se ferme, le script prend le relais.

        L'ordre importe : le thread d'installation est déjà en fin de course
        (le script détaché attend la sortie de l'exe), la fermeture passe par
        `closeEvent`, qui attend les threads de façon bornée.
        """
        if self._dialogue_maj is not None:
            self._dialogue_maj.reset()
            self._dialogue_maj = None
        self.arreter()
        self.close()

    def _maj_peripherique(self, config: Config | None = None) -> None:
        """Recalcule et affiche « Calcul : CUDA — … » ou « Calcul : CPU … ».

        L'opérateur a cherché à confirmer le GPU avec le gestionnaire de
        performances sans y arriver ; la réponse doit donc être à l'écran, en
        permanence, et nommer la carte quand elle existe.

        L'avertissement éventuel (GPU demandé mais absent, CPU forcé avec un
        GPU présent) part dans le JOURNAL et non dans le label : un encart de
        deux lignes ici remplacerait le compteur, et l'opérateur n'a rien à
        faire de l'information une fois qu'il l'a lue — sauf changer le
        réglage, ce que le menu « Périphérique de calcul » permet déjà.
        """
        config = config or getattr(self, "config", None) or Config.defauts()
        mode = mode_peripherique(getattr(config, "peripherique", "auto"))
        choix = peripherique_effectif(mode)
        if choix.avertissement:
            log.warning("%s", choix.avertissement)
        self.label_peripherique.setText(f"Calcul : {choix.libelle}")
        self._peripherique_effectif = choix

    def definir_etat_torch(self, etat) -> None:
        """Enregistre l'etat de torch et met l'indicateur a jour.

        Appele par `main.py` avec le retour de `interface.demarrage.preparer`.
        Un argument absent ou faux reste acceptable : la fenetre doit pouvoir
        etre construite seule, comme le font les 481 tests existants, et dans
        ce cas l'indicateur retombe sur une detection directe de torch.

        `label_torch` est un label DEDIE, pas une ligne de plus dans
        `label_statut`. La meme raison que pour `label_peripherique` :
        `label_statut` est reecrit a chaque changement d'etat (video chargee,
        analyse, pause, erreur) et effacerait precisement l'information que
        l'operateur cherche au moment ou il la cherche. Un label jamais
        reecrit tient jusqu'a la fin de session.
        """
        from interface.demarrage import EtatTorch, texte_indicateur

        if etat is None:
            # Fenetre construite seule (tests, ou appel sans `preparer`) :
            # on deduit l'etat de ce qui est reellement importable.
            version = ""
            try:
                import torch

                version = str(getattr(torch, "__version__", ""))
            except ImportError:
                pass
            from interface.demarrage import _cuda_reelle

            etat = EtatTorch(version=version, cuda=_cuda_reelle(), gpu="")
        self._etat_torch = etat
        self.label_torch.setText(texte_indicateur(etat))
        if etat.probleme:
            log.warning("%s", etat.probleme)

    def etat_torch(self):
        """Etat de torch affiche, pour les tests et le recapitulatif."""
        return getattr(self, "_etat_torch", None)

    def device_effectif(self) -> str:
        """Périphérique réellement utilisé, au format attendu par torch.

        Exposé pour que les tests vérifient leTexte affiché ET la valeur qui
        part dans `charger_modele` : les deux doivent parler du même matériel.
        """
        return self._peripherique_effectif.device

    # -- Boîtes de dialogue ----------------------------------------------

    def _signaler(self, titre: str, message: str, grave: bool = False) -> None:
        """Signale un problème à l'opérateur, sans jamais bloquer un test.

        Le message va toujours dans la barre de statut et le journal. La boîte
        modale n'apparaît QUE si la fenêtre est visible : sous `offscreen`, ou
        dans une fenêtre jamais affichée, un « OK » modal serait un blocage
        définitif.
        """
        (log.error if grave else log.warning)("%s : %s", titre, message)
        self.label_statut.setText(f"{titre} — {message}")
        if not self.isVisible():
            return
        boite = QMessageBox.critical if grave else QMessageBox.warning
        boite(self, titre, message)

    def _annoncer_resultat_verification(self, info) -> None:
        """Annonce le résultat de la vérification MANUELLE dans le dialogue.

        `info is None` est ambigu PAR CONCEPTION (échec réseau ou pas de
        mise à jour) : le message le dit honnêtement au lieu de promettre.
        Si une version existe, `_maj_trouvee` a déjà posé le bouton vert.
        """
        retour = self._retour_verification
        self._retour_verification = None
        if retour is None:
            return
        if info is None:
            retour.setText(
                "Aucune nouvelle version trouvée — tu es à jour (ou le "
                "réseau était injoignable : réessaie plus tard)."
            )
        else:
            retour.setText(
                f"Nouvelle version {info.get('version', '?')} disponible "
                "— le bouton vert de la barre l'installe."
            )

    def _construire_a_propos(self) -> QDialog:
        """Le dialogue « À propos » : version, vérification, lien.

        Construit ici, montré par `_ouvrir_a_propos` — la construction est
        séparable pour être testable sans boucle d'événements.
        """
        dialogue = QDialog(self)
        dialogue.setWindowTitle("À propos — Compteur de manifestation")
        v = QVBoxLayout(dialogue)
        titre = QLabel("<b>Compteur de manifestation</b>")
        v.addWidget(titre)
        v.addWidget(QLabel(f"Version {VERSION}"))
        retour = QLabel("")
        retour.setWordWrap(True)
        v.addWidget(retour)
        self._btn_verifier_maj = QPushButton("Vérifier les mises à jour")
        self._btn_verifier_maj.clicked.connect(
            self._demander_verification
        )
        v.addWidget(self._btn_verifier_maj)
        lien = QLabel(
            '<a href="https://github.com/galaxiel/crowd-counter/releases">'
            "Toutes les versions (GitHub)</a>"
        )
        lien.setOpenExternalLinks(True)
        v.addWidget(lien)
        self._retour_a_propos = retour
        return dialogue

    def _demander_verification(self) -> None:
        self._verifier_mise_a_jour(retour=self._retour_a_propos)

    def _ouvrir_a_propos(self) -> None:
        """Montre le dialogue « À propos » (modale, un seul geste utile)."""
        self._construire_a_propos().exec()

    def _on_soutenir(self) -> None:
        """Ouvre la page de don dans le navigateur par défaut.

        L'échec d'ouverture (navigateur absent, aucune application liée au
        protocole http) n'est pas une erreur grave : il est journalisé et
        signalé dans la barre de statut, sans boîte modale qui interromprait
        l'analyse.
        """
        if QDesktopServices.openUrl(QUrl(LIEN_SOUTIEN)):
            self.label_statut.setText(
                "Ouverture de la page de soutien dans le navigateur…"
            )
        else:
            log.warning("impossible d'ouvrir le navigateur vers %s", LIEN_SOUTIEN)
            self.label_statut.setText(
                "Impossible d'ouvrir le navigateur — copie le lien : "
                f"{LIEN_SOUTIEN}"
            )

    # -- Actions : la vidéo ----------------------------------------------

    def _on_charger_video(self) -> None:
        chemin, _ = QFileDialog.getOpenFileName(
            self, "Choisir une vidéo", self._depart_video(), FILTRES_VIDEOS
        )
        if chemin:
            self.charger_video(chemin)

    def _depart_video(self) -> str:
        """Dossier de départ du dialogue : le dernier ouvert, s'il existe.

        S'il a été supprimé depuis (disque externe débranché, dossier
        renommé), on retombe sur `""` — Qt ouvrira son propre dossier —
        plutôt que de demander à l'explorateur un chemin mort.
        """
        dossier = lire_dernier_dossier()
        if dossier and pathlib.Path(dossier).is_dir():
            return dossier
        return ""

    # -- Glisser-déposer ---------------------------------------------------

    def _chemin_de_la_depose(self, mime_data) -> str | None:
        """Chemin de la vidéo déposée, ou ``None`` si le dépôt est refusé.

        Les mêmes règles que le sélecteur de fichier : UNE seule url, une
        extension vidéo (`EXTENSIONS_VIDEO`), et pas d'analyse en cours —
        un fichier lâché pendant un comptage ne doit pas l'arrêter en
        silence, c'est exactement l'accident que le dépôt ne doit pas
        permettre. La validation par EXTENSION (pas par contenu) est
        délibérée : le chargement, lui, vérifie réellement le fichier et
        affiche l'erreur s'il est illisible.
        """
        if self._en_analyse:
            return None
        urls = mime_data.urls() if mime_data.hasUrls() else []
        if len(urls) != 1:
            return None
        chemin = urls[0].toLocalFile()
        if not chemin or pathlib.Path(chemin).suffix.lower() not in EXTENSIONS_VIDEO:
            return None
        return chemin

    def dragEnterEvent(self, event) -> None:  # noqa: N802 (API Qt)
        chemin = self._chemin_de_la_depose(event.mimeData())
        if chemin is None:
            event.ignore()
            return
        event.acceptProposedAction()

    def dragMoveEvent(self, event) -> None:  # noqa: N802 (API Qt)
        # Sans acceptation du move, le drop n'arrive jamais par-dessus les
        # enfants (la vue vidéo occupe presque tout l'écran).
        if self._chemin_de_la_depose(event.mimeData()) is not None:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:  # noqa: N802 (API Qt)
        chemin = self._chemin_de_la_depose(event.mimeData())
        if chemin is None:
            event.ignore()
            return
        event.acceptProposedAction()
        # `charger_video` affiche lui-même l'erreur si le fichier est
        # illisible — le dépôt ne duplique aucun contrôle.
        self.charger_video(chemin)

    def charger_video(self, chemin: str) -> bool:
        """Ouvre ``chemin`` et affiche sa première frame. Faux si illisible."""
        p = pathlib.Path(chemin)
        if not p.exists():
            self._signaler("Vidéo introuvable", f"Fichier absent :\n{chemin}")
            return False

        cap = cv2.VideoCapture(str(p))
        if not cap.isOpened():
            cap.release()
            self._signaler("Vidéo illisible", f"Impossible d'ouvrir :\n{chemin}")
            return False

        self.arreter()
        self._liberer_capture()
        self.cap = cap
        self.video_finiment = p
        # Mémorisé ICI, après la seule étape qui peut échouer (ouvrir le
        # fichier) : on n'oublie que les vidéos réellement ouvertes.
        ecrire_dernier_dossier(str(p.parent))
        self._reset_analyse()
        self._afficher_premiere_frame()

        nb_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        fps = self._fps()
        # La barre de progression est calée sur le total ANNONCÉ par le
        # conteneur. Total inconnu (0) : plage vide (min == max), le mode
        # « occupé » de QProgressBar — mieux qu'un pourcentage faux.
        self._nb_frames_video = nb_frames
        if nb_frames > 0:
            self.barre_progression.setRange(0, nb_frames)
        else:
            self.barre_progression.setRange(0, 0)
        self.barre_progression.setValue(0)
        analyse = self._resolution_analyse_pour(cap)
        largeur = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        hauteur = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        self.label_statut.setText(
            f"{p.name} — {largeur}×{hauteur}, {nb_frames} frames à {fps:.0f} i/s.\n"
            f"Analysée à {analyse} px. Trace la ligne, puis lance."
            + self._etat_du_modele()
        )
        self._maj_boutons()
        return True

    def _etat_du_modele(self) -> str:
        """Ligne ajoutée au statut : le modèle choisi est-il déjà sur le disque ?

        Le contrôle a lieu AU CHARGEMENT DE LA VIDÉO et non au lancement :
        sans lui, un `.pt` absent ne se révélait qu'après que l'opérateur a
        ouvert la vidéo, tracé la ligne et cliqué « Lancer » — pour se voir
        refuser le décompte, en conservant certes la vidéo et la ligne, mais
        après tout le travail de préparation.

        Trois états, et un seul est bon : trouvé ; introuvable alors que des
        poids existent (un nom tapé à la main, un fichier déplacé) ; aucun
        poids sur tout le poste — le cas d'une installation neuve, où le
        dépôt ne contient pas les `.pt` et où rien n'indiquait jusque-là où
        les déposer.
        """
        modele = self.config.modele
        if not modele:
            return "\nAucun modèle choisi — ouvre les réglages pour en choisir un."
        if resoudre_modele(modele) is not None:
            return f"\nModèle {modele} — trouvé, prêt pour le lancement."
        poids = [
            p.name
            for dossier in dossiers_modeles()
            if dossier.is_dir()
            for p in sorted(dossier.glob("*.pt"))
        ]
        if not poids:
            return (
                "\nAucun modèle sur ce poste : dépose un fichier .pt dans le "
                "dossier « modeles/ », puis choisis-le dans les réglages."
            )
        ou = "un modèle" if len(poids) == 1 else f"{len(poids)} modèles"
        return (
            f"\nModèle « {modele} » introuvable — {ou} disponible(s) sur ce "
            "poste : choisis-le dans les réglages (champ « Modèle »)."
        )

    def _resolution_analyse_pour(self, cap) -> int:
        """Résolution d'analyse retenue pour la vidéo ouverte, et appliquée.

        La résolution est LUE sur la `VideoCapture`
        (`CAP_PROP_FRAME_WIDTH`/`HEIGHT`) — c'est ce que le conteneur déclare,
        et cela ne coûte rien. Décoder une frame pour la mesurer serait plus
        lent d'un facteur cent et donnerait le même chiffre.

        Le réglage Manuel court-circuite tout : l'opérateur a dit qu'il savait
        ce qu'il faisait, et son choix n'a pas à être corrigé par la source.
        """
        largeur = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        hauteur = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        if mode_resolution(self.config.resolution_analyse) == MODE_MANUEL:
            return self.config.taille_entree
        taille = self.panneau.definir_resolution_video(largeur, hauteur)
        # Le panneau a recalculé pour son affichage ; `self.config` doit porter
        # la MÊME valeur, sinon la fenêtre annoncerait une résolution et le
        # détecteur en utiliserait une autre.
        self.config = self.panneau.lire()
        log.info(
            "vidéo %dx%d analysée à %d px (mode %s)",
            largeur,
            hauteur,
            taille,
            mode_resolution(self.config.resolution_analyse),
        )
        return taille

    def _reset_analyse(self) -> None:
        """Repart d'un état neuf pour une nouvelle vidéo.

        La ligne tracée est EFFACÉE : ses deux extrémités sont des pixels de
        l'image qui vient d'être remplacée. La conserver donnerait une ligne
        numériquement identique et géométriquement fausse sur la nouvelle
        scène — un défaut qu'aucune fenêtre ne permet de voir.
        """
        self.config = self.panneau.lire()
        self.detecteur = None
        self.tracker = None
        self.compteur = None
        self._modele_charge = ""
        self.ligne = None
        self._points_ligne = []
        self._trace_arme = False
        self._apercu_point = None
        self._resultat_courant = None
        self._index_affiche = -1
        self._flash = 0
        # Les boîtes vertes de l'analyse précédente appartiennent à la vidéo
        # précédente : les laisser afficher sur la nouvelle donnerait à
        # l'opérateur des personnes qui n'existent pas dans cette scène.
        self._boites_comptees.clear()
        # Le marqueur d'événements consommés repart avec : l'historique du
        # compteur est celui de la vidéo précédente, et il sera vidé avec elle.
        self._dernier_evenement_affiche = 0
        # Nouvelle vidéo : l'ancienne ligne appartenait à l'image qui vient
        # d'être remplacée et a déjà été mise à `None` plus haut — rien à
        # déverrouiller, la référence n'existe plus.
        self.video.definir_zone_deplacement(None)
        # Le récapitulatif concernait l'analyse précédente : il n'a plus de
        # rapport avec cette vidéo-ci et disparaît avec elle.
        self.recap.effacer()
        self.recap.setVisible(False)
        # La barre de progression appartient à la vidéo précédente : elle est
        # masquée et repartira de zéro au prochain « Lancer ». Idem pour le
        # débit : ni son horloge ni son estimation ne survivent au changement
        # de vidéo.
        self.barre_progression.setValue(0)
        self.barre_progression.setVisible(False)
        self._debut_analyse = None
        self._pause_debut = None
        self.label_debit.clear()
        self.label_debit.setVisible(False)
        self._nb_frames_video = 0
        self.maj_compteurs(0, 0, 0)

    def _afficher_premiere_frame(self) -> None:
        """Affiche la première frame sans la traiter.

        L'opérateur doit voir la scène avant de poser sa ligne ; le compteur,
        lui, reste à zéro.
        """
        if self.cap is None:
            return
        ok, img = self.cap.read()
        if not ok:
            self._signaler("Vidéo vide", "Aucune image lisible dans ce fichier.")
            return
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        self.video.definir_image(img)

    def _fps(self) -> float:
        """Cadence annoncée par la vidéo, avec repli si elle est aberrante.

        Un `CAP_PROP_FPS` à 0 ou négatif — conteneur mal écrit, certains codecs
        d'observation — donnerait une division par zéro dans le calcul du
        timestamp, et donc un bilan faux ou un plantage.
        """
        if self.cap is None:
            return FPS_REPLI
        fps = float(self.cap.get(cv2.CAP_PROP_FPS) or 0.0)
        if not (1.0 <= fps <= 240.0):
            return FPS_REPLI
        return fps

    # -- Actions : la ligne ----------------------------------------------

    def _installer_raccourcis(self) -> None:
        """Branche les raccourcis clavier de la fenêtre.

        Un opérateur de terrain travaille au gant, parfois sans souris
        précise : Espace pour la pause, Entrée pour lancer, Échap pour
        annuler un tracé raté, → pour avancer frame par frame en pause. Chaque
        raccourci appelle le MÊME slot que le bouton correspondant — il n'y a
        qu'une logique d'action, pas deux.

        → n'est branché qu'à la pause : en analyse, le flux avance tout seul.
        Le recul (←) n'existe pas — le compteur est séquentiel et étatique,
        on ne peut pas « dé-compter » une frame déjà traitée.
        """
        raccourcis = [
            (QKeySequence(Qt.Key.Key_Space), self._basculer_pause),
            (QKeySequence(Qt.Key.Key_Return), self.lancer),
            (QKeySequence(Qt.Key.Key_Enter), self.lancer),
            (QKeySequence(Qt.Key.Key_Escape), self._annuler_trace),
            (QKeySequence("Ctrl+O"), self._on_charger_video),
            (QKeySequence(Qt.Key.Key_S), self.arreter),
        ]
        for touche, action in raccourcis:
            raccourci = QShortcut(touche, self)
            # `WidgetWithChildrenShortcut` : la touche fonctionne même quand
            # le focus est sur un champ de réglage — sinon il faudrait
            # cliquer ailleurs avant chaque raccourci.
            raccourci.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            raccourci.activated.connect(action)
        pas = QShortcut(QKeySequence(Qt.Key.Key_Right), self)
        pas.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        pas.activated.connect(self._pas_de_frame)

    def _annuler_trace(self) -> None:
        """Annule un tracé de ligne en cours (Échap).

        Réinitialise l'état du tracé comme s'il n'avait jamais commencé :
        sans cela, un premier point posé au mauvais endroit laissait
        l'opérateur bloqué, la seule issue étant de re-cliquer « Tracer la
        ligne ».
        """
        if self._en_analyse:
            return
        self._points_ligne = []
        self._apercu_point = None
        self._trace_arme = False
        self._rafraichir_affichage()
        self._maj_boutons()
        if self.ligne is not None:
            self.label_statut.setText(
                "Ligne conservée. « Tracer la ligne » pour en redessiner une."
            )
        else:
            self.label_statut.setText(
                "Tracé annulé. Clique « Tracer la ligne » pour recommencer."
            )

    def _pas_de_frame(self) -> None:
        """ traite et affiche UNE frame de plus, à la pause (→).

        Le comptage normal est groupé par `TAILLE_LOT_DETECTION`, mais un
        pas manuel n'a de sens que frame par frame : on lise et traite une
        seule frame via `traiter_frame`, dont la logique est EXACTEMENT
        celle de `traiter_lot` (même `_integrer`). Ne fait RIEN si l'analyse
        tourne : le flux avance déjà tout seul.
        """
        if self._en_analyse or not self._session_ouverte:
            return
        if self.cap is None or self.compteur is None:
            return
        ok, img = self.cap.read()
        if not ok:
            # Fin de vidéo : même comportement que le flux normal.
            self.arreter()
            self._afficher_bilan()
            return
        index = self.frames
        ts = index / self._fps()
        self.frames += 1
        if hasattr(self.compteur, "traiter_frame"):
            resultat = self.compteur.traiter_frame(img, index, ts)
        else:
            resultat = self.compteur.traiter_lot([(img, index, ts)])[0]
        self._resultat_courant = resultat
        self._afficher()

    def _on_tracer_ligne(self) -> None:
        """Arme le tracé : le prochain clic pose le premier point."""
        self._points_ligne = []
        self.ligne = None
        self._trace_arme = True
        self._apercu_point = None
        self._rafraichir_affichage()
        self._maj_boutons()
        self.label_statut.setText(
            "Clique deux points sur l'image, en haut et en bas de la ligne "
            "que tu veux compter."
        )

    def _on_clic_video(self, x: int, y: int) -> None:
        """Un clic de l'opérateur, EN COORDONNÉES IMAGE (déjà converties).

        Rien n'est fait si le tracé n'est pas armé : c'est ce qui distingue un
        clic volontaire d'un clicRaté en plein réglage.
        """
        if not self._trace_arme or self._en_analyse:
            return

        if not self._points_ligne:
            self._points_ligne.append((float(x), float(y)))
            self._apercu_point = (x, y)
            self._rafraichir_affichage()
            self.label_statut.setText(
                f"Premier point en ({x}, {y}). Clique le second."
            )
            return

        second = aimanter_second_point(
            self._points_ligne[0], (float(x), float(y))
        )
        self._points_ligne.append(second)
        self._apercu_point = None
        self._trace_arme = False
        self.definir_ligne(*self._points_ligne)

    def _zone_deplacement(self) -> "tuple[int, int, int, int] | None":
        """Rectangle de la bande, en pixels image, si le glissement a lieu.

        `None` — donc pas de zone déplaçable — pendant une analyse : la ligne
        est verrouillée, `Ligne.deplacer` refuserait le déplacement, et le
        glisser doit être INOPÉRANT, pas planté. `None` aussi sans ligne.
        """
        if self.ligne is None or self._en_analyse or self.ligne.verrouillee:
            return None
        # Les dimensions sont celles de l'image AFFICHÉE, pas d'une lecture
        # vidéo : c'est elle que l'opérateur clique, donc elle seule donne un
        # rectangle dans lequel le clic tombera vraiment.
        dimensions = self.video.dimensions_image()
        if dimensions is None:
            return None
        largeur, hauteur = dimensions
        return self.ligne.rect_bande_detection(largeur, hauteur)

    def _rafraichir_zone_deplacement(self) -> None:
        """Redonne au widget la zone déplaçable courante.

        Appelée après chaque déplacement et après chaque changement de ligne :
        la zone est DÉRIVÉE de la ligne, elle doit donc suivre le déplacement
        au lieu de rester figée sur la bande d'origine.
        """
        self.video.definir_zone_deplacement(self._zone_deplacement())

    def _on_deplacement_video(self, dx: int, dy: int) -> None:
        """Un glissement : la ligne ET sa bande bougent de (dx, dy) pixels.

        Le décalage est appliqué à `p1` et `p2` PAR LA MÊME valeur : la bande
        n'est pas une coordonnée stockée mais une grandeur dérivée
        (`Ligne.rect_bande_detection`), donc elle suit la ligne sans qu'aucun
        second état puisse diverger. C'est aussi pourquoi on n'arme pas de
        copie de bande ici : il n'y en a pas.
        """
        if self.ligne is None or self._en_analyse or self.ligne.verrouillee:
            return
        if self._ligne_avant_glissement is None:
            self._ligne_avant_glissement = (self.ligne.p1, self.ligne.p2)
        (ax, ay), (bx, by) = self._ligne_avant_glissement
        self.ligne.deplacer((ax + dx, ay + dy), (bx + dx, by + dy))
        self.config.ligne = (
            self.ligne.p1[0],
            self.ligne.p1[1],
            self.ligne.p2[0],
            self.ligne.p2[1],
        )
        self.panneau.definir_ligne(self.config.ligne)
        self._rafraichir_affichage()
        self._rafraichir_zone_deplacement()

    def _on_deplacement_fini(self) -> None:
        """Fin du glissement : l'ancrage est oublié, la zone est rafraîchie."""
        self._ligne_avant_glissement = None
        self._maj_boutons()
        self._rafraichir_zone_deplacement()

    def definir_ligne(self, p1, p2) -> bool:
        """Fixe la ligne de comptage à partir de deux points image.

        `Ligne` valide : points confondus, `sens` hors {+1, -1}, épaisseur
        nulle. Chaque cas est un réglage que l'opérateur peut se tromper, donc
        un message — pas une exception qui ferme la fenêtre au milieu d'une
        manifestation.
        """
        try:
            self.ligne = Ligne(
                p1,
                p2,
                epaisseur=self.config.epaisseur_bande,
                sens=self.config.sens,
                hysteresis=self.config.frames_hysteresis,
                bande_avant_px=BANDE_AVANT_PX,
                bande_apres_px=BANDE_APRES_PX,
            )
        except ValueError as exc:
            self._points_ligne = []
            self._apercu_point = None
            self._maj_boutons()
            self._signaler("Ligne invalide", str(exc))
            return False

        # La ligne tracée est pushed dans la Config : c'est elle que
        # `analyser_video` relira pour une analyse hors interface.
        self.config.ligne = (
            self.ligne.p1[0],
            self.ligne.p1[1],
            self.ligne.p2[0],
            self.ligne.p2[1],
        )
        self.panneau.definir_ligne(self.config.ligne)
        self._rafraichir_affichage()
        self._maj_boutons()
        # La bande devient immédiatement déplaçable : l'opérateur vient de la
        # poser et veut souvent l'ajuster d'un cheveu avant de lancer.
        self._rafraichir_zone_deplacement()
        # Le sens compté est écrit EN CLAIR dans la barre de statut, et pas
        # seulement dessiné par la flèche verte. L'opérateur voit ainsi, avant
        # de lancer, dans quel sens la vidéo va être comptée — c'était
        # exactement l'information manquante qui lui coûtait de tester les
        # deux sens à chaque fois.
        self.label_statut.setText(
            f"Ligne {self.ligne.orientation} posée de "
            f"({self.ligne.p1[0]:.0f}, {self.ligne.p1[1]:.0f}) à "
            f"({self.ligne.p2[0]:.0f}, {self.ligne.p2[1]:.0f}).\n"
            f"Sens compté : {self._sens_en_clair()}. "
            "Si ton cortège va dans l'autre sens, change-le dans les réglages "
            "avant de lancer."
        )
        return True

    def _sens_en_clair(self) -> str:
        """Le sens compté, nommé à l'écran, d'après la ligne posée.

        Délègue à `Ligne.libelle_sens` : la barre de statut et la flèche verte
        ne peuvent donc pas nommer deux choses différentes.
        """
        if self.ligne is None:
            return LIBELLES_SENS[orientation_par_defaut_sens()][
                0 if self.config.sens == 1 else 1
            ]
        return self.ligne.libelle_sens(self.ligne.sens)

    def _rafraichir_affichage(self) -> None:
        """Redessine la frame courante avec l'aperçu de la ligne en cours.

        Sans cela, l'opérateur clique deux points à l'aveugle et ne voit sa
        ligne qu'en lançant le comptage — c'est-à-dire trop tard pour la
        corriger.
        """
        img = self._image_courante()
        if img is None:
            return
        sortie = img
        if self.ligne is not None:
            # Le voile passe ici aussi, et AVANT la ligne : l'opérateur doit voir
            # la colonne qu'il est en train de placer, pas seulement une fois
            # l'analyse lancée. C'est le seul moment où il peut encore corriger
            # son geste.
            sortie = self.ligne.voiler(sortie)
            sortie = self.ligne.dessiner(sortie)
        if self._apercu_point is not None:
            sortie = _marquer_point(sortie, self._apercu_point)
        self.video.definir_image(sortie)

    def _image_courante(self) -> "np.ndarray | None":  # noqa: F821
        """Dernière frame traitée, ou la première frame lue au chargement."""
        if self._resultat_courant is not None:
            return self._resultat_courant.image
        if self.cap is None:
            return None
        position = self.cap.get(cv2.CAP_PROP_POS_FRAMES)
        ok, img = self.cap.read()
        if not ok:
            return None
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, position)
        return img

    # -- Actions : les réglages ------------------------------------------

    def _sur_config(self, config: Config) -> None:
        """Le panneau a changé : on propage sans jamais casser la fenêtre.

        Deux cas distincts :

        - un réglage ordinaire (seuil, bande, hystérésis) se répercute tel quel
          sur le détecteur, le tracker et la ligne déjà tracée, qui garde ses
          DEUX POINTS — c'est la géométrie que l'opérateur a posée qu'il ne
          faut pas perdre ;
        - un MODÈLE différent, lui, rend les poids chargés caducs : le
          détecteur est lâché. Le conserver compterait avec l'ancien modèle
          pendant que l'écran annonce le nouveau.
        """
        # Le périphérique se met à jour AVANT l'affectation de `self.config` :
        # la comparaison ci-dessous porte sur l'ANCIEN réglage, donc elle doit
        # être faite avant que la référence ne soit écrasée. Écraser d'abord
        # rendrait tout changement invisible — et l'indicateur afficherait le
        # périphérique précédent, ce qui est le mensonge exact que cet
        # indicateur sert à éviter.
        peripherique_change = (
            mode_peripherique(getattr(config, "peripherique", "auto"))
            != mode_peripherique(getattr(self.config, "peripherique", "auto"))
        )
        if peripherique_change:
            log.info("périphérique de calcul : %s", getattr(config, "peripherique", "auto"))
            self._maj_peripherique(config)

        self.config = config
        if self.ligne is not None:
            try:
                self.ligne = Ligne(
                    self.ligne.p1,
                    self.ligne.p2,
                    epaisseur=config.epaisseur_bande,
                    sens=config.sens,
                    hysteresis=config.frames_hysteresis,
                    bande_avant_px=BANDE_AVANT_PX,
                bande_apres_px=BANDE_APRES_PX,
                )
            except ValueError as exc:
                # Réglage devenu impossible (épaisseur 0, sens nul) : on garde
                # l'ancienne ligne plutôt que de laisser le moteur sans ligne,
                # qui ne compterait plus personne.
                log.warning("réglage de ligne refusé : %s", exc)
        if self.compteur is not None:
            self.compteur.config = config
        # Un changement de périphérique lâche le détecteur comme un changement
        # de modèle : le device entre dans `charger_modele`.
        if self.detecteur is not None:
            if config.modele and config.modele != self._modele_charge:
                log.info("modèle changé (%s -> %s)", self._modele_charge, config.modele)
                self.detecteur = None
                self.tracker = None
                self._modele_charge = ""
                if self._en_analyse:
                    self.label_statut.setText(
                        "Modèle changé : l'analyse en cours va s'arrêter. "
                        "Relance pour l'appliquer."
                    )
                    self.arreter()
            elif peripherique_change:
                # Un modèle déjà monté reste sur son périphérique d'origine :
                # `Detecteur` ne déplace pas le modèle à chaud. Le lâcher est
                # donc obligatoire, sinon l'écran annoncerait « CPU » pendant
                # que l'analyse tourne encore sur le GPU — l'inverse exact du
                # problème que cet indicateur sert à résoudre.
                log.info("périphérique changé : rechargement du modèle nécessaire.")
                self.detecteur = None
                self.tracker = None
                self._modele_charge = ""
                if self._en_analyse:
                    self.label_statut.setText(
                        "Périphérique de calcul changé : l'analyse en cours va "
                        "s'arrêter. Relance pour l'appliquer."
                    )
                    self.arreter()
            else:
                self.detecteur.config = config
        if self.tracker is not None:
            self.tracker.config = config

    # -- Actions : la lecture --------------------------------------------

    def lancer(self) -> None:
        """Démarre l'analyse. Ne charge le modèle qu'ici, jamais au démarrage.

        Le chargement des poids — plusieurs secondes — part dans un THREAD :
        fait sur le fil de l'IHM, il figerait la fenêtre, Stop et fermeture
        compris. Seule sa VALIDATION (une lecture de disque, une microseconde)
        reste synchrone, pour qu'un modèle absent soit dit sans dépendre de
        la livraison d'un résultat asynchrone.
        """
        if self.cap is None or self.ligne is None or self._en_analyse:
            return
        if self._chargement_en_cours:
            # Double-clic ou Entrée maintenue : un seul chargement à la fois.
            return

        # Un réglage peut avoir bougé depuis le dernier « Lancer » : on
        # repart de l'état du panneau, jamais d'une copie périmée.
        self.config = self.panneau.lire()
        self.config.ligne = self._ligne_en_tuple()
        self._reconstruire_ligne_depuis_config()

        if self.detecteur is None:
            self._demarrer_chargement()
            return
        self._demarrer_analyse()

    def _demarrer_chargement(self) -> None:
        """Valide le modèle, puis le charge dans un thread.

        La validation est la MÊME que celle de `charger_modele`
        (`resoudre_modele`, sans torch ni ultralytics) : un `.pt` absent ou
        un nom tapé à la main est dit tout de suite, en synchrone, avec le
        message exact que le chargement aurait levé. Seul le chargement
        lourd — lecture des poids + mise en mémoire torch — part en thread.
        """
        modele, peripherique = self.config.modele, self.config.peripherique
        if resoudre_modele(modele) is None:
            self._signaler(
                "Démarrage impossible",
                message_modele_absent(modele)
                + "\n\nLa vidéo et la ligne sont conservées.",
                grave=True,
            )
            self._maj_boutons()
            return

        demande = (modele, peripherique)
        ancien = self._thread_modele
        if ancien is not None:
            if ancien.isRunning():
                if self._chargement_demande == demande:
                    # Chargement annulé par erreur (Stop) puis relancé à
                    # l'identique : le résultat du thread qui tourne est
                    # EXACTEMENT celui qu'on attend — on le réarmer plutôt
                    # que de monter deux fois les mêmes poids.
                    self._chargement_en_cours = True
                    self.label_statut.setText(f"Chargement du modèle {modele}…")
                    self._maj_boutons()
                    return
                # Un AUTRE modèle est en route : on ne remplace jamais un
                # QThread en fonctionnement, et doubler deux chargements
                # torch sur le même GPU ne ferait que ralentir les deux.
                self._signaler(
                    "Chargement déjà en cours",
                    "Un autre chargement de modèle est en cours — réessaie "
                    "dans une seconde.",
                )
                self._maj_boutons()
                return
            ancien.quit()
            ancien.wait(5000)
            if ancien.isRunning():
                # Quasi impossible (il ne tournait pas) : on ne remplace
                # JAMAIS un QThread vivant — la référence reste en place, le
                # prochain « Lancer » le reverra en cours et réessaiera.
                self._signaler(
                    "Chargement déjà en cours",
                    "Le chargement précédent n'a pas fini — réessaie dans "
                    "une seconde.",
                )
                self._maj_boutons()
                return
            self._thread_modele = None
            self._worker_modele = None

        log.info("chargement du modèle %s (en thread)", modele)
        self._chargement_en_cours = True
        self._chargement_demande = demande
        self.label_statut.setText(
            f"Chargement du modèle {modele}… La fenêtre reste utilisable."
        )
        self._maj_boutons()

        self._thread_modele = QThread()
        self._worker_modele = _ChargementModele(modele, peripherique)
        self._worker_modele.moveToThread(self._thread_modele)
        self._thread_modele.started.connect(self._worker_modele.run)
        self._worker_modele.fini.connect(self._modele_pret)
        self._worker_modele.fini.connect(self._thread_modele.quit)
        self._thread_modele.start()

    def _modele_pret(self, chargement) -> None:
        """Le thread a livré — un modèle, une exception, ou rien d'utile.

        Trois filtres, dans l'ordre de leur probabilité, et seul un modèle
        qui passe tout démarre l'analyse :

        1. le chargement a été ANNULÉ entre-temps (Stop, nouvelle vidéo) :
           le résultat est jeté silencieusement — l'appelant d'annulation
           vient déjà d'écrire le statut, l'écraser le démentirait ;
        2. le chargement a ÉCHOUÉ : signalé « Démarrage impossible », vidéo
           et ligne conservées — exactement comme avant l'asynchrone ;
        3. les réglages ont BOUGÉ en route : monter le modèle livré
           donnerait une analyse pilotée par un réglage que l'écran ne
           montre plus — on demande une relance.
        """
        if not self._chargement_en_cours:
            log.info("chargement de modèle terminé mais annulé : jeté")
            return
        self._chargement_en_cours = False
        if isinstance(chargement, BaseException):
            self._signaler(
                "Démarrage impossible",
                f"{chargement}\n\nLa vidéo et la ligne sont conservées.",
                grave=True,
            )
            self._maj_boutons()
            return
        choix = self.panneau.lire()
        if (choix.modele, choix.peripherique) != self._chargement_demande:
            self.label_statut.setText(
                "Réglages modifiés pendant le chargement — relance pour les "
                "appliquer."
            )
            self._maj_boutons()
            return
        self._demarrer_analyse(chargement)

    def _demarrer_analyse(self, modele_charge=None) -> None:
        """Monte le modèle reçu (s'il en est un), puis démarre les minuteries.

        ``modele_charge`` est le poids fraîchement livré par le thread, ou
        `None` quand le détecteur est déjà monté. Sa construction reste dans
        le MÊME `try` que le reste du montage : un échec — modèle
        incompatible, config refusée — est signalé « Démarrage impossible »
        avec la vidéo et la ligne conservées, comme avant l'asynchrone.
        """
        try:
            if modele_charge is not None:
                self.detecteur = Detecteur(modele_charge, self.config)
                self._modele_charge = self.config.modele
            if self.tracker is None:
                self.tracker = Tracker(self.config)
            self.compteur = Compteur(self.config, self.detecteur, self.tracker)
        except Exception as exc:  # noqa: BLE001 — un échec ici doit rester récupérable
            # Ni la vidéo ni la ligne ne sont touchées : l'opérateur corrige le
            # modèle et relance, sans retracer.
            self._signaler(
                "Démarrage impossible",
                f"{exc}\n\nLa vidéo et la ligne sont conservées.",
                grave=True,
            )
            self._maj_boutons()
            return

        # La ligne et sa bande de détection sont VERROUILLÉES dès le lancement.
        # Pendant l'analyse, ni l'une ni l'autre ne bougent : sinon le
        # décompte afficherait deux zones différentes dans la même vidéo, et
        # l'opérateur verrait sa colonne glisser sous ses yeux sans pouvoir croire
        # le chiffre. Le verrou est levé par `arreter()` et `_reset_analyse`.
        self.ligne.verrouiller()
        # La zone déplaçable est RETIRÉE, pas seulement ignorée : le clic dans
        # la bande redevient inerte au lieu de partir sur un déplacement que
        # `Ligne.deplacer` refuse.
        self._ligne_avant_glissement = None
        self._rafraichir_zone_deplacement()
        self.compteur.ajuster_ligne(self.ligne)
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        self.compteur_total = 0
        self.presents = 0
        self.frames = 0
        self._resultat_courant = None
        self._index_affiche = -1
        self._flash = 0
        self._boites_comptees.clear()
        self._dernier_evenement_affiche = 0
        # « Une fois par analyse » : le compteur repart de zéro ici, donc le
        # rappel doit pouvoir se redéployer. La réouverture de session après
        # une pause NE le réarme pas : sans cela, chaque reprise en pause le
        # ferait clignoter, alors que l'opérateur n'a pas relancé d'analyse.
        self._avertissement_sens_affiche = False
        # Le récapitulatif de l'analyse PRÉCÉDENTE disparaît ici. Le laisser en
        # place pendant qu'un nouveau décompte démarre ferait lire l'ancien
        # total et l'ancienne courbe comme s'ils étaient en cours.
        self.recap.effacer()
        self.recap.setVisible(False)
        self._ouvrir_session()
        # La barre de progression vit de « Lancer » au prochain chargement de
        # vidéo : en fin d'analyse elle reste visible à sa dernière valeur —
        # l'opérateur voit d'un coup d'œil que la scène est allée au bout.
        self.barre_progression.setValue(0)
        self.barre_progression.setVisible(True)
        # Horloge du débit : démarrée ICI, pas au premier `_tick`, pour que
        # le premier lot — souvent le plus lent (montée en charge du GPU) —
        # soit compté comme le reste.
        self._debut_analyse = time.monotonic()
        self._pause_debut = None
        self.label_debit.setText("")
        self.label_debit.setVisible(True)
        self._maj_boutons()
        self.label_statut.setText("Analyse en cours…")
        self._timer_traitement.start()
        self._timer_affichage.start()

    def _ligne_en_tuple(self) -> tuple[float, float, float, float] | None:
        if self.ligne is None:
            return None
        return (self.ligne.p1[0], self.ligne.p1[1], self.ligne.p2[0], self.ligne.p2[1])

    def _reconstruire_ligne_depuis_config(self) -> None:
        """Réapplique les réglages du panneau à la ligne existante."""
        try:
            self.ligne = Ligne(
                self.ligne.p1,
                self.ligne.p2,
                epaisseur=self.config.epaisseur_bande,
                sens=self.config.sens,
                hysteresis=self.config.frames_hysteresis,
                bande_avant_px=BANDE_AVANT_PX,
                bande_apres_px=BANDE_APRES_PX,
            )
        except ValueError as exc:
            self._signaler("Ligne invalide", str(exc), grave=True)
            self.ligne = None

    def _ouvrir_session(self) -> None:
        """Passe en « analyse lancée » : traitement actif, commandes actives.

        Ce passage est isolé parce que l'état de la lecture est à DEUX
        drapeaux — `_en_analyse` (le timer tourne) et `_session_ouverte` (une
        analyse a été démarrée et n'est pas finie). Les laisser se remplir
        séparément à chaque site d'appel est exactement ce qui les fait
        diverger ; ils ne sont donc écrits que d'ici, de `arreter` et de
        `_reset_analyse`.
        """
        self._en_analyse = True
        self._session_ouverte = True
        self.btn_pause.setText("Pause")

    def _basculer_pause(self) -> None:
        if self._en_analyse:
            self._timer_traitement.stop()
            self._en_analyse = False
            self._pause_debut = time.monotonic()
            self.btn_pause.setText("Reprendre")
            self.label_statut.setText("En pause.")
        elif self._session_ouverte and self.compteur is not None:
            if self._debut_analyse is not None and self._pause_debut is not None:
                # La pause est RETIRÉE de l'horloge du débit : en décalant le
                # départ d'autant, `maintenant - début` ne compte plus que le
                # temps réellement passé à traiter.
                self._debut_analyse += time.monotonic() - self._pause_debut
            self._pause_debut = None
            self._timer_traitement.start()
            self._ouvrir_session()
            self.label_statut.setText("Analyse en cours…")
        self._maj_boutons()

    def arreter(self) -> None:
        """Ferme la session d'analyse et rend la main à l'opérateur.

        Le récapitulatif s'affiche ici, et pas seulement en fin de lecture : un
        opérateur qui coupe au bout de trente secondes — parce que la scène a
        changé, ou qu'il a assez de matière — doit retrouver ses chiffres sans
        avoir à laisser la vidéo tourner jusqu'au bout. Il s'affiche donc sur
        TOUT arrêt d'une analyse engagée, qui que soit l'appelant.

        Le drapeau est lu AVANT la remise à zéro : `arreter()` est aussi
        appelé au chargement d'une vidéo et lors d'un changement de réglage,
        cas où aucune analyse n'a eu lieu et où il n'y a rien à résumer.
        """
        analyse_engagee = self._session_ouverte
        # Un chargement de modèle en route s'arrête aussi : plus rien
        # n'attend son résultat (le prochain « Lancer » en relancera un,
        # ou réarmera celui-ci s'il n'est pas fini).
        if self._chargement_en_cours:
            self._chargement_en_cours = False
            self.label_statut.setText("Chargement du modèle annulé.")
        self._timer_traitement.stop()
        self._timer_affichage.stop()
        # Fin d'analyse : la ligne redevient déplaçable, bande comprise.
        if self.ligne is not None:
            self.ligne.deverrouiller()
        self._rafraichir_zone_deplacement()
        self._en_analyse = False
        self._session_ouverte = False
        # L'estimation du temps restant n'a plus de sens une fois l'analyse
        # arrêtée : le label se vide et la horloge s'éteint — un « reste ≈
        # 40 s » laissé affiché après un Stop mentirait.
        self._debut_analyse = None
        self._pause_debut = None
        self.label_debit.clear()
        self.btn_pause.setText("Pause")
        self._maj_boutons()
        if analyse_engagee:
            self._afficher_recap()

    def _afficher_recap(self) -> None:
        """Remplit et DÉVOILE le récapitulatif de fin d'analyse.

        Un `Resultat` impossible à construire ne fait pas tomber la fenêtre :
        un compteur de terrain ne se ferme pas parce qu'un résumé n'a pas pu
        s'écrire. Le panneau reste alors masqué, et le journal dit pourquoi.
        """
        if self.compteur is None:
            return
        try:
            resultat = self.compteur.resultat(
                self.config.modele, self.frames, self.frames / self._fps()
            )
        except TypeError:
            # Un compteur de test peut ne pas accepter la durée vidéo : le
            # récapitulatif est un bonus d'affichage, pas une condition de
            # fonctionnement de la fenêtre.
            log.warning("récapitulatif indisponible : signature inattendue")
            return
        except Exception as exc:  # noqa: BLE001 — l'affichage ne doit rien casser
            log.warning("récapitulatif indisponible : %s", exc)
            return
        self.recap.definir_reglages(
            f"Modèle : {self.config.modele} · Seuil : "
            f"{self.config.seuil_confiance:.2f} · Confirmation : "
            f"{self.config.frames_confirmation} f · Analyse : "
            f"{self.config.taille_entree} px"
        )
        self.recap.afficher(resultat)
        self.recap.setVisible(True)

    def _libelle_sens(self) -> str:
        """Le libellé du sens compté, exprimé selon la ligne tracée.

        Avec ligne : les libellés de la LIGNE (`Ligne.choix_sens`) —
        « Gauche → droite » sur une verticale, « Haut → bas » sur une
        horizontale. Sans ligne : l'orientation supposée, la même que
        celle qu'affichait l'ancien menu du panneau.
        """
        if self.ligne is not None:
            choix = self.ligne.choix_sens()
        else:
            base = LIBELLES_SENS[orientation_par_defaut_sens()]
            choix = [(base[0], 1), (base[1], -1)]
        correspondance = {v: libelle for libelle, v in choix}
        return correspondance.get(int(self.config.sens), "?")

    def _maj_libelle_sens(self) -> None:
        self.btn_sens.setText(f"Sens : {self._libelle_sens()}")

    def _on_inverser_sens(self) -> None:
        """Inverse le sens compté (bouton de la barre, demande opérateur).

        Le sens appartient à la Config moteur ET à la ligne (c'est la
        ligne qui décide quel côté est « départ ») : les deux sont mis à
        jour ensemble, et la vue est redessinée — la flèche verte pivote
        sous les yeux de l'opérateur, aucune ambiguïté possible.
        Interdit pendant l'analyse : la ligne y est verrouillée.
        """
        if self._en_analyse or self._chargement_en_cours:
            return
        self.config.sens = -int(self.config.sens or 1)
        self.panneau.definir_sens(self.config.sens)
        if self.ligne is not None:
            self._reconstruire_ligne_depuis_config()
        self._maj_libelle_sens()
        self._rafraichir_affichage()
        self.label_statut.setText(
            f"Sens de comptage : {self._libelle_sens()}"
        )

    def _maj_boutons(self) -> None:
        """Une seule source de vérité pour l'activation des boutons.

        Passé par des `setEnabled` dispersés, cet état divergeait : le bouton
        « Lancer » restait actif après le chargement d'une vidéo, et « Pause »
        cliquable sans session ouverte.
        """
        video = self.cap is not None
        pret = video and self.ligne is not None
        # Pendant un chargement, les trois gestes qui le rendraient caduc
        # sont verrouillés (ouvrir une vidéo l'annule, tracer une ligne ou
        # relancer le doublerait) ; Stop, lui, reste actif : c'est par lui
        # qu'on annule un chargement.
        chargement = self._chargement_en_cours
        self.btn_video.setEnabled(not self._en_analyse and not chargement)
        self.btn_ligne.setEnabled(video and not self._en_analyse and not chargement)
        self.btn_sens.setEnabled(video and not self._en_analyse and not chargement)
        self.btn_lancer.setEnabled(pret and not self._en_analyse and not chargement)
        # « Recommencer » n'a de sens qu'APRÈS un premier essai : avant,
        # il serait un second « Lancer » sans rien dire de plus.
        self.btn_recommencer.setEnabled(
            pret
            and not self._en_analyse
            and not chargement
            and self._une_analyse_faite
        )
        self.btn_pause.setEnabled(self._session_ouverte)
        self.btn_stop.setEnabled(self._session_ouverte or chargement)
        self._maj_libelle_sens()

    # -- Boucle de lecture ------------------------------------------------

    def _tick(self) -> None:
        """Traite UN LOT de frames : détection groupée, comptage séquentiel.

        La séparation d'avec `_afficher` reste entière — et prend encore plus
        de sens ici : un lot de 4 frames produit 4 résultats, seuls le
        dernier et les compteurs sont poussés à l'écran. Les événements des
        frames intermédiaires ne sont pas perdus : `_dernier_evenement_affiche`
        les rattrape depuis l'historique du compteur, écrit précisément pour
        des frames traitées mais non affichées.
        """
        if self.cap is None or self.compteur is None:
            self._timer_traitement.stop()
            return

        fps = self._fps()
        lot = []
        while len(lot) < TAILLE_LOT_DETECTION:
            ok, img = self.cap.read()
            if not ok:
                break
            lot.append((img, self.frames, self.frames / fps))
            self.frames += 1

        if not lot:
            self.arreter()
            self._afficher_bilan()
            return

        # Repli : un compteur de test n'a pas forcément `traiter_lot` — même
        # logique que le repli côté détecteur dans `Compteur.traiter_lot`.
        if hasattr(self.compteur, "traiter_lot"):
            resultats = self.compteur.traiter_lot(lot)
        else:
            resultats = [
                self.compteur.traiter_frame(img, index, ts) for img, index, ts in lot
            ]
        self._resultat_courant = resultats[-1]

    def _afficher(self) -> None:
        """Pousse la dernière frame traitée vers l'écran et les compteurs.

        Le compteur et l'image sont mis à jour ENSEMBLE : l'opérateur doit voir
        le chiffre correspondant à la scène qu'il regarde, pas un chiffre qui
        a déjà pris deux secondes d'avance.
        """
        resultat = self._resultat_courant
        if resultat is None or resultat.frame_index == self._index_affiche:
            return
        self._index_affiche = resultat.frame_index

        if resultat.evenements:
            self._flash = FLASH_FRAMES
        flash = self._flash > 0
        if self._flash > 0:
            self._flash -= 1

        # La méthode met à jour `self._boites_comptees` (état interne) ET
        # retourne les positions courantes à dessiner. L'état interne reste
        # donc intact ; c'est le retour qui part dans l'overlay.
        boites = self._boites_comptees_a_afficher(resultat)
        self.maj_compteurs(resultat.total, resultat.presents, self.frames)
        self.video.definir_image(
            dessiner(
                resultat.image,
                resultat,
                self.ligne,
                afficher_ids=False,
                flash=flash,
                boites_comptees=boites,
            )
        )

    def _boites_comptees_a_afficher(
        self, resultat
    ) -> list[tuple[int, float, float, float, float]]:
        """Met à jour l'état interne et retourne les boîtes vertes à dessiner.

        **La boîte verte SUIT la personne, elle ne reste pas sur la ligne.**
        L'événement de comptage porte la position du franchissement ; mais le
        track, lui, continue d'être suivi tant que la personne reste dans la
        bande de détection (`_purger_franchis` ne touche pas au tracker). On
        stocke donc le `track_id`, pas une boîte figée, et on cherche sa
        position COURANTE dans `resultat.tracks` à chaque frame : la boîte
        verte colle à la tête qui avance.

        **Quand disparaît-elle ?** Quand la personne sort de la bande après la
        ligne, elle n'est plus détectée : le tracker la lâche après
        `survie_max` frames sans détection, donc elle disparaît de
        `resultat.tracks` et la boîte avec elle. C'est exactement le geste que
        l'opérateur décrit — détecté dans la bande, vert au franchissement,
        plus de boîte à la sortie.

        Deux bornes, chacune rattrape la défaillance de l'autre :
        - **La vie du track** est la règle normale : boîte tant que la personne
          est suivie. C'est elle qui fait suivre la boîte ET qui la fait
          disparaître à la sortie de bande.
        - **La durée** (`DUREE_BOITE_COMPTEE_FRAMES`) est le filet : si une
          personne s'arrête dans la bande après la ligne, son track reste
          vivant — la boîte verte ne doit pas rester affichée indéfiniment.
        - **Le nombre** (`TAILLE_MAX_BOITES_COMPTES`) est le filet absolu : si
          rien ne purge, la liste ne peut pas croître sans fin.
        """
        suivis = {t.track_id: t for t in getattr(resultat, "tracks", None) or []}

        # Rattraper les événements non encore transformés en boîte verte.
        # L'affichage peut sauter des frames (vitesse lente) : un événement
        # produit sur une frame NON affichée ne serait jamais vu si on ne
        # lisait que `resultat.evenements`, qui ne porte que la dernière frame
        # traitée. L'historique du compteur, lui, garde TOUT — on en consomme
        # un cran de plus à chaque affichage.
        if self.compteur is not None:
            historique = getattr(self.compteur, "evenements", None) or []
            if len(historique) < self._dernier_evenement_affiche:
                # Nouvelle analyse : l'historique a été vidé, on repart de zéro
                # au lieu de re-créer des boîtes déjà vues.
                self._dernier_evenement_affiche = 0
            for ev in historique[self._dernier_evenement_affiche :]:
                if ev.track_id is not None:
                    self._boites_comptees.append((ev.frame, ev.track_id))
            if len(historique) > self._dernier_evenement_affiche:
                # Un ou plusieurs comptes NOUVEAUX viennent d'être rattrapés :
                # le flash s'arme même si la frame affichée n'en porte aucun.
                # En analyse par lot, un compte tombe souvent sur une frame
                # intermédiaire jamais affichée — sans cet armement ici, le
                # flash ne s'allumerait plus du tout.
                self._flash = FLASH_FRAMES
            self._dernier_evenement_affiche = len(historique)
        else:
            # Pas de compteur (test, ou fenêtre construite seule) : on retombe
            # sur les événements de la frame affichée.
            for ev in getattr(resultat, "evenements", None) or []:
                if ev.track_id is not None:
                    self._boites_comptees.append((ev.frame, ev.track_id))

        # On filtre par la vie du track, pas en purgeant sur place : la liste
        # retournée est celle que l'overlay dessine, et une liste mutée pendant
        # que l'overlay la parcourt serait une course.
        vivantes: list[tuple[int, int]] = []
        for frame_comptage, track_id in self._boites_comptees:
            if track_id not in suivis:
                continue  # la personne a quitté la bande : le track est mort
            age = resultat.frame_index - frame_comptage
            if age > DUREE_BOITE_COMPTEE_FRAMES:
                continue  # filet de durée : personne arrêtée dans la bande
            vivantes.append((frame_comptage, track_id))

        # La plus récente d'abord : un dépassement du plafond sacrifie alors les
        # plus anciennes, celles que l'opérateur a déjà eu le temps de voir.
        vivantes.sort(key=lambda boite: boite[0], reverse=True)
        self._boites_comptees = vivantes[:TAILLE_MAX_BOITES_COMPTES]

        # Les positions COURANTES, à la frame affichée.
        return [
            (frame, *suivis[track_id].bbox)
            for frame, track_id in self._boites_comptees
        ]

    # -- Compteurs et bilan ----------------------------------------------

    def maj_compteurs(self, total: int, presents: int, frames: int) -> None:
        """Met à jour le gros chiffre et le détail sous le compteur."""
        self.compteur_total = int(total)
        self.presents = int(presents)
        self.frames = int(frames)
        # `str(int)` : le chiffre est lu de loin, un « 42.0 » se lirait mal et
        # une largeur changeante ferait Sauter l'alignement.
        self.label_compteur.setText(str(int(total)))
        # Barre de progression : frames TRAITÉES rapportées au total annoncé.
        # Elle avance à la cadence d'affichage (~15 i/s), pas de traitement —
        # largement suffisant pour lire « où on en est ».
        if self._nb_frames_video > 0:
            self.barre_progression.setValue(min(int(self.frames), self._nb_frames_video))
        # `presents` et `frames` sont enregistrés mais plus affichés : le
        # second alimente encore l'avertissement « 0 compté », qui raisonne en
        # secondes de VIDÉO, et le premier le bilan de fin d'analyse.
        self._maj_avertissement_sens(int(total), int(frames))
        self._maj_debit()

    # -- Débit et temps restant -------------------------------------------

    def _maj_debit(self) -> None:
        """Réécrit le label de débit si une analyse tourne.

        Rien hors analyse (`_debut_analyse` à `None`) : c'est le même
        drapeau que la session, il ne peut pas désaccorder le label de
        l'état réel de la fenêtre.
        """
        if self._debut_analyse is None:
            return
        self.label_debit.setText(
            self._texte_debit(time.monotonic() - self._debut_analyse)
        )

    def _texte_debit(self, ecoule: float) -> str:
        """« 41 i/s — reste ≈ 2 min 55 s » pour ``ecoule`` secondes écoulées.

        Séparé de l'horloge pour être testé sans manipuler le temps réel.

        Trois règles d'honnêteté :
        - **aucun chiffre avant une demi-seconde** : sur les tout premiers
          instants, le débit saute de plusieurs milliers d'i/s, lecture
          absurde qui jette le doute sur tout le reste ;
        - **le temps restant est approximatif** (« ≈ ») : le débit d'une
          scène dépend de la densité de la foule, il n'est pas linéaire ;
        - **pas de temps restant sans total connu** — un conteneur muet
          (`_nb_frames_video == 0`) ne permet aucune division.
        """
        if ecoule < 0.5 or self.frames <= 0:
            return ""
        ips = self.frames / ecoule
        texte = f"{ips:.0f} i/s"
        if self._nb_frames_video > self.frames:
            reste = (self._nb_frames_video - self.frames) / ips
            texte += f" — reste ≈ {formater_duree(reste)}"
        return texte

    # -- Avertissement « 0 compté » --------------------------------------

    def _maj_avertissement_sens(self, total: int, frames: int) -> None:
        """Rappelle de vérifier le sens quand le compteur reste bloqué à zéro.

        C'est le SEUL réglage qui produise un zéro fiable : le sens par défaut
        vaut +1, et la vidéo de référence donne 315 personnes en `sens=-1`
        contre 1 en `sens=+1`. Un opérateur qui laisse le défaut voit une vidéo
        défiler normalement, des boîtes de détection s'afficher, et un zéro
        qui ne bouge pas — rien ne lui dit que le cortège est compté à
        l'envers. D'où le rappel.

        **Déclencheur volontairement simple** : `total == 0` après au moins
        `SEUIL_AVERTISSEMENT_SENS_S` secondes de vidéo ANALYSÉE. La variante
        « et le sens vient d'être changé » a été écartée : le cas le plus
        fréquent est précisément l'opérateur qui n'y touche pas, donc cette
        condition supprimerait l'avertissement dans le cas pour lequel il
        existe. Le seuil de 3 s suffit à écarter le démarrage d'analyse et le
        risque d'alerter sur une scène où, simplement, personne n'est encore
        passé.

        Le rappel est une fois par analyse, jamais par frame : `_afficher` est
        appelé 25 fois par seconde, et un message qui clignote n'est plus un
        message. Il disparaît dès que `total` repart, et à chaque nouvelle
        analyse.
        """
        if not self._session_ouverte or total > 0:
            self._avertissement_sens_affiche = False
            self.label_avertissement.setVisible(False)
            return
        if self._avertissement_sens_affiche:
            return
        # Le seuil est en SECONDES DE VIDÉO, pas en frames affichées : ralentir
        # la présentation ne doit pas retarder ni hâter l'avertissement, qui
        # parle d'un temps vécu par l'opérateur.
        if frames / self._fps() < SEUIL_AVERTISSEMENT_SENS_S:
            return
        self._avertissement_sens_affiche = True
        self.label_avertissement.setText(AVERTISSEMENT_SENS)
        self.label_avertissement.setVisible(True)
        log.info("avertissement « 0 compté » : vérifier le sens de la ligne")

    def _afficher_bilan(self) -> None:
        """Bilan de fin de lecture, dans la barre de statut.

        Les chiffres sont calculés ici à partir du `Resultat`, sans passer par
        `compteur.rapport` : c'est un résumé d'une ligne, pas le récapitulatif
        complet — celui-ci est dessiné par `PanneauRecap`, appelé par
        `arreter()`.

        L'export a été supprimé, donc ce texte ne propose plus rien à
        exporter : il annonce le résultat et s'arrête là.
        """
        if self.compteur is None:
            return
        resultat = self.compteur.resultat(
            self.config.modele, self.frames, self.frames / self._fps()
        )
        minutes = max(1e-9, resultat.secondes / 60.0)
        par_minute = resultat.total / minutes
        self.label_statut.setText(
            f"Terminé — {resultat.total} personnes, "
            f"{par_minute:.1f}/min, "
            f"max {resultat.presents_max} présents, "
            f"{resultat.presents_moyen:.1f} en moyenne."
        )

    # -- Fermeture --------------------------------------------------------

    def _liberer_capture(self) -> None:
        if self.cap is not None:
            self.cap.release()

    def closeEvent(self, event) -> None:  # noqa: N802 (API Qt)
        """Libère la capture en sortant.

        Sous Windows, une `VideoCapture` non libérée garde le fichier ouvert :
        la vidéo ne peut plus être déplacée ni supprimée tant que l'application
        tourne.

        Un chargement de modèle en route est ANNULÉ puis attendu — borné.
        Jamais un QThread détruit en marche (crash Qt garanti) ; jamais non
        plus une attente infinie : un disque bloqué ne doit pas transformer
        la fermeture en gel. La boucle réitère `quit()` parce qu'un `quit`
        émis AVANT l'entrée du thread dans `exec()` est un no-op (détail
        Qt) — et pompe les événements, sans quoi la livraison de `fini`
        (qui commande l'arrêt) n'aurait jamais lieu.
        """
        self._timer_traitement.stop()
        self._timer_affichage.stop()
        self._chargement_en_cours = False
        thread = self._thread_modele
        if thread is not None:
            fin = time.monotonic() + 15.0
            while thread.isRunning() and time.monotonic() < fin:
                thread.quit()
                QApplication.processEvents()
                thread.wait(20)
        # Le thread de mise à jour (vérification OU installation) : même
        # attente bornée. Normalement déjà fini — la fenêtre n'est fermable
        # pendant une installation qu'APRÈS que le script d'échange est armé.
        thread_maj = self._thread_maj
        if thread_maj is not None:
            fin = time.monotonic() + 15.0
            while thread_maj.isRunning() and time.monotonic() < fin:
                thread_maj.quit()
                QApplication.processEvents()
                thread_maj.wait(20)
        self._liberer_capture()
        # Les réglages courants survivent à la fermeture (thème et dossier
        # vidéo suivent le même principe). Best-effort : un échec d'écriture
        # ne doit pas empêcher de fermer.
        ecrire_derniere_config(self.config)
        super().closeEvent(event)


#: Un tracé à moins de cet angle de l'horizontale ou de la verticale se
#: colle exactement droit (magnétisme, demande opérateur du 05/11/2026 :
#: une ligne penchée de 1-2° faisait diverger la zone de détection du
#: dessin). 5° sur SA demande d'essai — la main tremble plus qu'on croit.
TOLERANCE_AIMANT_DEGRES = 5.0


def aimanter_second_point(
    p1: tuple[float, float], p2: tuple[float, float]
) -> tuple[float, float]:
    """Rend ``p2`` exactement aligné sur ``p1`` si le tracé frôle H ou V.

    Le tracé à main levée frôle souvent l'horizontale ou la verticale sans
    y être exactement : la ligne reste penchée de 1-2° et la zone de
    détection (rectangle droit) diverge du dessin. À moins de
    `TOLERANCE_AIMANT_DEGRES` de l'horizontale ou de la verticale, le
    second point est recalé exactement dessus. Entre les deux, le tracé
    libre est respecté — un tracé volontairement diagonal n'est pas
    déplacé.
    """
    dx = float(p2[0]) - float(p1[0])
    dy = float(p2[1]) - float(p1[1])
    if dx == 0.0 or dy == 0.0:
        return p2  # déjà exactement aligné
    limite = math.tan(math.radians(TOLERANCE_AIMANT_DEGRES))
    pente = abs(dy / dx)
    if pente <= limite:
        return (float(p2[0]), float(p1[1]))  # horizontal
    if pente >= 1.0 / limite:
        return (float(p1[0]), float(p2[1]))  # vertical
    return p2


def _marquer_point(img, point: tuple[int, int]):
    """Cercles sur un point en cours de placement (le geste n'est pas fini)."""
    cv2 = _cv2()
    x, y = point
    sortie = img.copy()
    cv2.drawMarker(
        sortie,
        (int(x), int(y)),
        (60, 200, 255),
        cv2.MARKER_CROSS,
        markerSize=60,
        thickness=4,
    )
    return sortie


def _cv2():
    import cv2

    return cv2
