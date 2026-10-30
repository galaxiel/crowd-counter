"""Tests de la fenêtre principale (tâche 10).

Trois choses sont vérifiées ici, par ordre de gravité.

1. **La fenêtre se construit et ne bloque pas.** Aucun modèle n'est chargé à
   l'ouverture : le chargement se fait sur « Lancer », jamais dans
   `__init__`. Un `FenetrePrincipale()` doit donc être instantané même avec
   CUDA actif.

2. **Le tracé de la ligne.** C'est la fonction critique : deux clics posés à la
   souris sur la vidéo deviennent les deux extrémités de la ligne que le moteur
   va comptabiliser. Une erreur ici est INVISIBLE à l'écran — la ligne affichée
   paraît bien posée, c'est le décompte qui est faux. Les tests portent donc sur
   la ligne *source* obtenue, et sur la géométrie qui en découle (verticalité,
   abscisse, côtés de part et d'autre de la bande).

3. **Le découplage traitement / présentation.** Ralentir l'affichage ne doit
   JAMAIS ralentir le traitement : deux minuteries distinctes, et c'est
   vérifié explicitement plutôt que supposé.

Une note sur les boîtes de dialogue : l'interface n'ouvre une `QMessageBox`
MODALE que si la fenêtre est visible et que Qt n'est pas en mode `offscreen`.
Sans cette garde, un test qui provoke une erreur resterait bloqué sur un
« OK » que personne ne peut cliquer.
"""

import os
import time

# Doit précéder la création de QApplication (voir test_widgets_video.py).
# `setdefault` respecte un choix déjà pris dans l'environnement de lancement.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import cv2  # noqa: E402
import numpy as np  # noqa: E402
import pytest  # noqa: E402

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QMouseEvent  # noqa: E402

from compteur.compteur import TAILLE_LOT_DETECTION  # noqa: E402
from compteur.types import Evenement, FrameResult, Track  # noqa: E402
from interface.app import (  # noqa: E402
    AVERTISSEMENT_SENS,
    CADENCE_AFFICHAGE_IPS,
    FenetrePrincipale,
    ecrire_dernier_dossier,
    lire_dernier_dossier,
)
from interface.overlay import dessiner  # noqa: E402

# Le chemin de la mémoire se lit SUR LE MODULE : le conftest le détourne
# vers un `tmp_path`, et une valeur importée « par copie » ne le verrait pas.
import interface.app as module_app  # noqa: E402

# Cadence de la vidéo synthétique : 25 i/s. Les tests d'affichage en dépendent
# (0,25x -> 160 ms entre deux images affichées).
FPS_SYNTHETIQUE = 25.0


@pytest.fixture
def application():
    """Une QApplication unique pour toute la session (Qt n'en autorise qu'une)."""
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def video_synthetique(tmp_path):
    """Une vidéo minuscule (64x48, 5 frames) écrite par OpenCV.

    Vraie vidéo, vraie `VideoCapture` : le test du chargement et de la lecture
    exercise le même chemin de code qu'une vidéo de manifestation, sans
    dépendre d'un fichier de several gigaoctets absent du dépôt.
    """
    chemin = tmp_path / "synthetique.mp4"
    auteur = cv2.VideoWriter(
        str(chemin), cv2.VideoWriter_fourcc(*"mp4v"), FPS_SYNTHETIQUE, (64, 48)
    )
    assert auteur.isOpened(), "OpenCV n'a pas pu écrire la vidéo de test"
    for i in range(5):
        auteur.write(np.full((48, 64, 3), 20 + i * 10, dtype=np.uint8))
    auteur.release()
    return chemin


@pytest.fixture
def fenetre(application):
    return FenetrePrincipale()


def cliquer(widget, x, y):
    """Simule un clic gauche en coordonnées WIDGET."""
    captures = []
    widget.clic.connect(lambda px, py: captures.append((px, py)))
    evenement = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(x, y),
        QPointF(x, y),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    widget.mousePressEvent(evenement)
    return captures


def avancer(fenetre, n=1):
    """Traite puis affiche ``n`` frames.

    Les deux temps sont volontairement distincts dans le code : c'est ce
    découplage que la vitesse de présentation ne doit pas casser. Les tests
    d'affichage les enchaînent donc explicitement, au lieu d'attendre qu'un
    seul appel fasse les deux.
    """
    for _ in range(n):
        fenetre._tick()
        fenetre._afficher()


class FauxCompteur:
    """Compteur de test : aucun modèle, aucun GPU, un événement en frame 2."""

    def __init__(self) -> None:
        self.ligne = None
        self.appels = 0
        self.evenements = []

    def ajuster_ligne(self, ligne) -> None:
        self.ligne = ligne

    def traiter_frame(self, img, index, ts) -> FrameResult:
        self.appels += 1
        nouveaux = []
        if index == 2:
            ev = Evenement(frame=index, timestamp_s=ts, x=1.0, y=1.0, track_id=7)
            nouveaux.append(ev)
            self.evenements.append(ev)
        return FrameResult(
            image=img,
            total=index + 1,
            presents=2,
            frame_index=index,
            timestamp_s=ts,
            evenements=nouveaux,
        )

    def resultat(self, modele, nb_frames, secondes):
        from compteur.types import Resultat

        return Resultat(
            total=nb_frames,
            evenements=list(self.evenements),
            modele=modele,
            nb_frames=nb_frames,
            presents_max=3,
            secondes=secondes,
        )


# -- Construction --------------------------------------------------------


def test_fenetre_se_construit(application):
    f = FenetrePrincipale()
    assert f.compteur_total == 0
    assert f.presents == 0
    assert f.video_finiment is None
    assert f.ligne is None
    assert f.compteur is None


def test_fenetre_a_le_titre_avec_le_numero_de_version(application):
    """Le numéro de version vient du moteur, et le titre l'affiche.

    Le titre de la fenêtre est le SEUL endroit où un utilisateur regarde pour
    savoir quelle version il a. Il est donc construit depuis `compteur.VERSION`
    — jamais depuis un littéral ici : ce test compare le titre à la constante,
    donc une redéfinition divergente échouerait au lieu de passer en silence.
    """
    from compteur import VERSION

    f = FenetrePrincipale()
    assert VERSION in f.windowTitle()
    assert f"Compteur de manifestation — {VERSION}" == f.windowTitle()


def test_aucun_chargement_de_modele_a_l_ouverture(application, monkeypatch):
    """Construire la fenêtre ne doit toucher ni torch ni ultralytics.

    CUDA est actif sur cette machine : un chargement de modèle dans `__init__`
    gellerait l'interface avant même d'afficher quoi que ce soit.
    """

    def exploser(*_args, **_kwargs):
        raise AssertionError("le modèle ne doit pas être chargé au démarrage")

    monkeypatch.setattr("interface.app.charger_modele", exploser)
    monkeypatch.setattr("interface.app.Detecteur", exploser)
    FenetrePrincipale()


def test_fenetre_a_le_compteur_et_le_widget_video(application):
    f = FenetrePrincipale()
    assert f.label_compteur.objectName() == "compteur"
    assert f.label_compteur.text() == "0"
    assert f.video is not None


# -- Chargement de la vidéo ---------------------------------------------


def test_charger_video_absente_signale_une_erreur(application, tmp_path):
    f = FenetrePrincipale()
    assert f.charger_video(str(tmp_path / "inexistant.mp4")) is False
    assert f.video_finiment is None


def test_charger_fichier_non_video_signale_une_erreur(application, tmp_path):
    """Un fichier présent mais illisible doit être refusé aussi."""
    faux = tmp_path / "pas_une_video.mp4"
    faux.write_text("ceci n'est pas une vidéo", encoding="utf-8")
    f = FenetrePrincipale()
    assert f.charger_video(str(faux)) is False


def test_video_finiment_renseigne_apres_chargement(application, fenetre, video_synthetique):
    assert fenetre.charger_video(str(video_synthetique)) is True
    assert fenetre.video_finiment == video_synthetique
    assert fenetre.cap is not None


def test_charger_video_affiche_la_premiere_frame(application, fenetre, video_synthetique):
    """L'opérateur doit voir la scène AVANT de tracer sa ligne."""
    fenetre.charger_video(str(video_synthetique))
    assert fenetre.video._image is not None
    assert fenetre.video._image.shape[:2] == (48, 64)


def test_charger_video_reinitialise_le_compteur(application, fenetre, video_synthetique):
    """Une nouvelle vidéo repart de zéro, même après un comptage partiel."""
    fenetre.charger_video(str(video_synthetique))
    fenetre.maj_compteurs(total=42, presents=7, frames=100)
    fenetre.charger_video(str(video_synthetique))
    assert fenetre.compteur_total == 0
    assert fenetre.presents == 0


def test_charger_video_efface_la_ligne_de_la_video_precedente(
    application, fenetre, video_synthetique
):
    """La ligne est en pixels de l'UNE vidéo : la conserver serait compter faux.

    Une ligne gardée après changement de vidéo traverserait l'image au même
    endroit numérique, donc potentiellement à un autre endroit réel. Le défaut
    ne serait visible d'aucune façon à l'écran.
    """
    fenetre.charger_video(str(video_synthetique))
    fenetre.definir_ligne((10.0, 5.0), (10.0, 40.0))
    fenetre.charger_video(str(video_synthetique))
    assert fenetre.ligne is None
    assert not fenetre.btn_lancer.isEnabled()


# -- Boutons : rien de lancable sans vidéo ET sans ligne ------------------


def test_lancer_desactive_tant_qu_aucune_video_nest_chargee(application, fenetre):
    assert not fenetre.btn_lancer.isEnabled()
    assert not fenetre.btn_ligne.isEnabled()
    assert not fenetre.btn_pause.isEnabled()
    assert not fenetre.btn_stop.isEnabled()


def test_lancer_desactive_tant_que_la_ligne_nest_pas_tracee(
    application, fenetre, video_synthetique
):
    fenetre.charger_video(str(video_synthetique))
    assert fenetre.btn_ligne.isEnabled()
    assert not fenetre.btn_lancer.isEnabled()


def test_lancer_actif_apres_une_vide_et_une_ligne(
    application, fenetre, video_synthetique
):
    fenetre.charger_video(str(video_synthetique))
    fenetre._on_tracer_ligne()
    fenetre._on_clic_video(10, 2)
    fenetre._on_clic_video(10, 40)
    assert fenetre.btn_lancer.isEnabled()


def test_retirer_la_ligne_desactive_a_nouveau_lancer(application, fenetre):
    """« Tracer la ligne » réarme : l'ancien tracé ne doit plus rester actif."""
    fenetre.definir_ligne((10.0, 5.0), (10.0, 40.0))
    assert fenetre.btn_lancer.isEnabled() or fenetre.cap is None
    fenetre._on_tracer_ligne()
    assert fenetre.ligne is None
    assert not fenetre.btn_lancer.isEnabled()


# -- Tracé de la ligne : la fonction critique ----------------------------


def test_ligne_invalide_refusee(application, fenetre):
    assert fenetre.definir_ligne((10.0, 10.0), (10.0, 10.0)) is False
    assert fenetre.ligne is None


def test_sens_invalide_refuse(application, fenetre):
    config = fenetre.panneau.lire()
    config.sens = 0  # hors de {+1, -1} : `Ligne` doit refuser
    fenetre.config = config
    assert fenetre.definir_ligne((10.0, 5.0), (10.0, 40.0)) is False


def test_deux_clics_donnent_une_ligne_verticale_a_la_bonne_abscisse(
    application, fenetre
):
    """Le geste réel de l'opérateur, de bout en bout.

    Géométrie connue par construction, donc aucun Repère circulaire : image
    640x480 dans un widget 640x480, facteur 1, décalage nul — les coordonnées
    du clic ET celles de la ligne source sont les mêmes nombres.

    On vérifie ensuite la LIGNE, pas seulement les points : verticale à
    x=300, et surtout les deux personnes voisines de part et d'autre de la
    bande sont classées de côtés OPPOSÉS. C'est cette propriété que le moteur
    utilise pour compter ; une ligne décalée d'un pixel la ferait échouer.
    """
    f = fenetre
    f.video.setMinimumSize(0, 0)
    f.video.resize(640, 480)
    f.video.definir_image(np.zeros((480, 640, 3), dtype=np.uint8))
    assert f.video.facteur_echelle() == pytest.approx(1.0)
    assert f.video.decalage() == (0, 0)

    f._on_tracer_ligne()
    assert cliquer(f.video, 300, 20) == [(300, 20)]
    assert cliquer(f.video, 300, 460) == [(300, 460)]

    assert f.ligne is not None
    assert f.ligne.p1 == (300.0, 20.0)
    assert f.ligne.p2 == (300.0, 460.0)
    assert f.ligne.p1[0] == f.ligne.p2[0], "la ligne doit être verticale"

    # Le point visé est SUR la ligne, à 0 près.
    assert f.ligne.coordonnee_projetee((300, 240)) == pytest.approx(0.0, abs=1e-6)

    # La bande par défaut fait 30 px, donc ±15 px : à ±10 px on est encore
    # DANS la bande, et `point_du_cote` doit y renvoyer 0. Une personne qui
    # n'est pas encore franche du tout n'est comptée ni dans un sens ni dans
    # l'autre — c'est ce qui empêche les oscillations de déclencher un
    # comptage (voir le verrou anti-rebond de `compteur.compteur`).
    assert f.ligne.epaisseur == 30
    assert f.ligne.point_du_cote((290, 240)) == 0
    assert f.ligne.point_du_cote((310, 240)) == 0

    # Juste dehors, de part et d'autre : les côtés sont OPPOSÉS et non nuls.
    # C'est la propriété dont le moteur se sert pour décider d'un franchissement.
    assert f.ligne.point_du_cote((280, 240)) != 0
    assert f.ligne.point_du_cote((320, 240)) != 0
    assert f.ligne.point_du_cote((280, 240)) != f.ligne.point_du_cote((320, 240))

    # Et le franchissement du bon côté vers l'autre est retenu une fois.
    assert f.ligne.a_traverse((280, 240), (320, 240)) is True


def test_deux_clics_avec_reduction_donnent_la_bonne_ligne_source(
    application, fenetre
):
    """Image 1280x960 réduite de moitié dans un widget 640x480.

    Un clic au quart de la largeur doit viser le pixel source 320, pas 160 :
    c'est le régime où la ligne part le plus facilement à côté.
    """
    f = fenetre
    f.video.setMinimumSize(0, 0)
    f.video.resize(640, 480)
    f.video.definir_image(np.zeros((960, 1280, 3), dtype=np.uint8))
    assert f.video.facteur_echelle() == pytest.approx(0.5)

    f._on_tracer_ligne()
    assert cliquer(f.video, 160, 40) == [(320, 80)]
    assert cliquer(f.video, 160, 440) == [(320, 880)]

    assert f.ligne.p1 == (320.0, 80.0)
    assert f.ligne.p2 == (320.0, 880.0)


def test_clic_sans_arme_ne_pose_aucun_point(application, fenetre, video_synthetique):
    """Un clic parasite ne doit pas commencer un tracé.

    Pendant une manifestation, un clic malencontreux au milieu d'un réglage
    décalerait la ligne du premier point venu : le défaut serait invisible et le
    décompte faux.
    """
    f = fenetre
    f.charger_video(str(video_synthetique))
    f._on_clic_video(10, 2)
    assert f.ligne is None
    assert f._points_ligne == []


def test_premier_point_pose_ne_fait_pas_de_ligne(application, fenetre):
    f = fenetre
    f.video.setMinimumSize(0, 0)
    f.video.resize(320, 240)
    f.video.definir_image(np.zeros((240, 320, 3), dtype=np.uint8))
    f._on_tracer_ligne()
    cliquer(f.video, 100, 20)
    assert f.ligne is None
    assert f._points_ligne == [(100.0, 20.0)]


def test_changer_le_sens_reconstruit_la_ligne_sans_perdre_les_points(
    application, fenetre
):
    """Le réglage du sens doit agir sur la ligne déjà tracée, pas la perdre."""
    f = fenetre
    f.definir_ligne((300.0, 20.0), (300.0, 460.0))
    assert f.ligne.sens == 1
    f.panneau._sens.setCurrentIndex(1)  # « Après → avant »
    assert f.config.sens == -1
    assert f.ligne.sens == -1
    assert f.ligne.p1 == (300.0, 20.0)
    assert f.ligne.p2 == (300.0, 460.0)


def test_changer_l_epaisseur_de_bande_reconstruit_la_ligne(application, fenetre):
    f = fenetre
    f.definir_ligne((300.0, 20.0), (300.0, 460.0))
    f.panneau.definir_epaisseur_bande(80)
    assert f.ligne.epaisseur == 80


# -- Compteurs -----------------------------------------------------------


def test_compteur_se_met_a_jour(application):
    f = FenetrePrincipale()
    f.maj_compteurs(total=42, presents=7, frames=100)
    assert f.compteur_total == 42
    assert f.presents == 7
    assert f.frames == 100
    assert f.label_compteur.text() == "42"
    # Les compteurs de « présents » et de « frames » ne sont PLUS affichés :
    # les valeurs restent enregistrées ci-dessus, seul le libellé a disparu.
    assert not hasattr(f, "label_details")


def test_compteur_affiche_les_chiffres_en_entier(application, fenetre):
    """Le gros chiffre est lu de loin : il ne doit jamais afficher de décimale."""
    fenetre.maj_compteurs(total=1234, presents=0, frames=0)
    assert fenetre.label_compteur.text() == "1234"


# -- Boucle de lecture ----------------------------------------------------


def test_tick_traite_un_lot_et_incremente_le_compteur(
    application, fenetre, video_synthetique
):
    """Un tick = un LOT de `TAILLE_LOT_DETECTION` frames, comptage séquentiel.

    La détection est groupée (un appel modèle par lot) ; l'affichage, lui,
    montre la dernière frame du lot. La vidéo de 5 frames fait donc deux
    lots : 4 frames, puis 1.
    """
    f = fenetre
    f.charger_video(str(video_synthetique))
    f.compteur = FauxCompteur()
    f._ouvrir_session()
    avancer(f, 1)
    assert f.compteur.appels == TAILLE_LOT_DETECTION
    assert f.frames == TAILLE_LOT_DETECTION
    assert f.compteur_total == TAILLE_LOT_DETECTION
    avancer(f, 2)
    assert f.compteur.appels == 5  # la vidéo entière : 4 + 1
    assert f.compteur_total == 5


def test_tick_ne_traite_pas_si_pas_de_video(application, fenetre):
    """Sans capture, `_tick` doit s'arrêter proprement, pas lever."""
    f = fenetre
    f.compteur = FauxCompteur()
    f._ouvrir_session()
    f._tick()
    assert not f._timer_traitement.isActive()


def test_fin_de_video_met_en_pause_et_affiche_le_bilan(
    application, fenetre, video_synthetique
):
    """Une vidéo de 5 frames : au bout, la lecture s'arrête et propose l'export."""
    f = fenetre
    f.charger_video(str(video_synthetique))
    f.compteur = FauxCompteur()
    f._ouvrir_session()
    for _ in range(10):
        avancer(f)
    assert f._en_analyse is False
    assert not f._timer_traitement.isActive()
    assert "Terminé" in f.label_statut.text()


def test_flash_de_comptage_s_allume_puis_s_eteint(application, fenetre, tmp_path):
    """Le flash d'alerte aide l'opérateur à voir le groupe qui passe.

    L'événement tombe en frame 2 : avec l'analyse par LOT, cette frame n'est
    jamais AFFICHÉE (le lot 0-3 est représenté par la frame 3). Le flash doit
    s'armer au rattrapage de l'événement depuis l'historique — sinon il ne
    s'allumerait plus jamais en analyse par lot — puis s'éteindre après
    `FLASH_FRAMES` affichages. Une vidéo de 20 frames laisse la place de
    regarder le flash s'éteindre.
    """
    chemin = tmp_path / "flash.mp4"
    auteur = cv2.VideoWriter(
        str(chemin), cv2.VideoWriter_fourcc(*"mp4v"), FPS_SYNTHETIQUE, (64, 48)
    )
    assert auteur.isOpened(), "OpenCV n'a pas pu écrire la vidéo de test"
    for i in range(20):
        auteur.write(np.full((48, 64, 3), 20 + (i % 10) * 10, dtype=np.uint8))
    auteur.release()

    f = fenetre
    f.charger_video(str(chemin))
    f.compteur = FauxCompteur()
    f._ouvrir_session()
    avancer(f, 1)  # le lot couvre les frames 0-3 : l'événement est rattrapé
    assert f._flash > 0
    avancer(f, 6)  # six affichages plus tard : le flash est éteint
    assert f._flash == 0


def test_pause_et_reprise(application, fenetre, video_synthetique):
    f = fenetre
    f.charger_video(str(video_synthetique))
    f.compteur = FauxCompteur()
    f._ouvrir_session()
    f._timer_traitement.start()
    f._basculer_pause()
    assert f._en_analyse is False
    assert not f._timer_traitement.isActive()
    assert f.btn_pause.text() == "Reprendre"
    f._basculer_pause()
    assert f._en_analyse is True
    assert f._timer_traitement.isActive()
    assert f.btn_pause.text() == "Pause"


def test_arreter_ne_plante_pas_sans_video(application, fenetre):
    fenetre.arreter()
    assert fenetre._en_analyse is False


# -- Raccourcis clavier ------------------------------------------------------
#
# Un opérateur de terrain travaille au gant : la souris n'est pas toujours
# utilisable. Les raccourcis doivent exister et appeler les MÊMES slots que
# les boutons — une seule logique d'action, pas deux.


def _raccourcis(fenetre):
    from PySide6.QtGui import QShortcut

    return {r.key().toString(): r for r in fenetre.findChildren(QShortcut)}


def test_les_raccourcis_clavier_sont_installes(application, fenetre):
    """Espace/Entrée/Échap/S/Ctrl+O/→ sont branchés sur la fenêtre."""
    cles = _raccourcis(fenetre)
    # Qt rend `Key_Escape` sous le nom « Esc » — le raccourci répond bien à
    # la touche Échap, c'est seulement son libellé `toString()` qui diffère.
    attendues = {"Space", "Return", "Enter", "Esc", "S", "Right", "Ctrl+O"}
    assert attendues <= set(cles), f"manquants : {attendues - set(cles)}"


def test_espace_bascule_la_pause_comme_le_bouton(application, fenetre):
    """Le raccourci appelle le slot du bouton, il ne duplique pas sa logique."""
    from PySide6.QtGui import QShortcut

    cles = _raccourcis(fenetre)
    appels = []
    # On intercepte l'activation : on veut prouver le BRANCHEMENT, pas
    # rejouer la logique de pause (celle-ci est couverte ailleurs).
    original = fenetre._basculer_pause
    fenetre._basculer_pause = lambda: appels.append(1)
    try:
        cles["Space"].activated.emit()
    finally:
        fenetre._basculer_pause = original
    assert appels == [1]


def test_echap_annule_un_trace_en_cours(application, fenetre):
    """Un premier point posé au mauvais endroit ne doit pas bloquer l'opérateur."""
    f = fenetre
    f._on_tracer_ligne()
    f._points_ligne = [(10, 10)]
    f._annuler_trace()
    assert f._points_ligne == []
    assert f._trace_arme is False


def test_pas_de_frame_sans_session_ne_fait_rien(application, fenetre):
    """→ hors analyse : rien à lire, et surtout pas de plantage."""
    fenetre._pas_de_frame()
    assert fenetre.frames == 0


def test_pas_de_frame_pendant_l_analyse_ne_derange_pas_le_flux(
    application, fenetre, video_synthetique
):
    """Le flux avance tout seul : un pas manuel ne doit pas s'y substituer."""
    f = fenetre
    f.charger_video(str(video_synthetique))
    f.compteur = FauxCompteur()
    f._ouvrir_session()
    f._timer_traitement.start()
    avant = f.frames
    f._pas_de_frame()
    assert f.frames == avant, "le pas manuel doit être ignoré en analyse"


def test_pas_de_frame_avance_d_une_frame_en_pause(
    application, fenetre, video_synthetique
):
    """À la pause, → lit et traite UNE frame, puis l'affiche."""
    f = fenetre
    f.charger_video(str(video_synthetique))
    f.compteur = FauxCompteur()
    f._ouvrir_session()
    f._basculer_pause()  # ouvre la session en pause (timer non démarré)
    avant = f.frames
    f._pas_de_frame()
    assert f.frames == avant + 1
    assert f._resultat_courant is not None, "la frame lue doit être traitée"


def test_fermer_la_fenetre_libere_la_video(application, fenetre, video_synthetique):
    """Une `VideoCapture` non libérée tient le fichier ouvert sous Windows."""
    f = fenetre
    f.charger_video(str(video_synthetique))
    capture = f.cap
    f.close()
    assert not capture.isOpened()


# -- Vitesse de présentation : retirée, l'analyse va à vitesse maximale -----


def test_traitement_a_vitesse_max_et_affichage_plafonne(
    application, fenetre, video_synthetique
):
    """Le traitement fonce ; l'affichage est plafonné à ~15 i/s.

    Le sélecteur de vitesse a été retiré : il ne contrôlait que la fréquence
    de rafraîchissement, pas la vitesse réelle (plafonnée par le traitement),
    et son effet était contre-intuitif — 0,25× semblait plus rapide que ×4.
    Depuis l'analyse par lot, le rendu d'affichage est en outre le poste lourd
    côté CPU sur le même thread que le traitement : le plafonner à
    `CADENCE_AFFICHAGE_IPS` libère le débit de comptage, qui reste à
    intervalle 0.
    """
    f = fenetre
    f.charger_video(str(video_synthetique))
    assert f._timer_traitement.interval() == 0
    assert f._timer_affichage.interval() == 1000 // CADENCE_AFFICHAGE_IPS


def test_affichage_ne_redessine_pas_la_meme_frame_deux_fois(
    application, fenetre, video_synthetique
):
    """L'affichage ne redessine pas la même frame deux fois.

    Le compteur affiché doit correspondre à l'image affichée : les deux sont
    mis à jour au même moment, sinon l'opérateur voit un chiffre qui avance
    devant la scène qu'il regarde.
    """
    f = fenetre
    f.charger_video(str(video_synthetique))
    f.compteur = FauxCompteur()
    f._ouvrir_session()
    vues = []
    f.video.image_changee.connect(lambda img: vues.append(f.compteur_total))
    for _ in range(3):
        f._tick()
        f._afficher()
    # Un tick affiche la DERNIÈRE frame de son lot : lot de 4 (frames 0-3),
    # puis la frame 4. Le troisième tick tombe sur une vidéo épuisée et
    # n'affiche rien de neuf — pas de doublon pour autant.
    assert vues == [TAILLE_LOT_DETECTION, 5]
    # Un appel d'affichage supplémentaire sans frame neuve ne redessine rien.
    f._afficher()
    assert len(vues) == 2


# -- Réglages -------------------------------------------------------------


def test_changer_le_modele_ne_plante_pas(application, fenetre):
    """Aucun détecteur chargé : le changement de modèle ne doit rien casser."""
    f = fenetre
    f.panneau._modele.setCurrentText("nano.pt")
    assert f.config.modele == "nano.pt"
    f.panneau._modele.setCurrentText("medium.pt")
    assert f.config.modele == "medium.pt"


def test_changer_le_modele_invalide_le_detecteur(application, fenetre, monkeypatch):
    """Un modèle différent = des poids différents : le détecteur est lâché.

    Sans cela, changer de modèle en cours de route continuerait à compter avec
    l'ancien, et l'interface afficherait le nom du nouveau : le résultat serait
    attribué au mauvais modèle.
    """

    class FauxDetecteur:
        def __init__(self, config):
            self.config = config

    f = fenetre
    f.detecteur = FauxDetecteur(f.config)
    f._modele_charge = "medium.pt"
    f.panneau._modele.setCurrentText("nano.pt")
    assert f.detecteur is None
    assert f.tracker is None


def test_changer_un_reglage_met_a_jour_le_detecteur_vivant(
    application, fenetre, monkeypatch
):
    """Tant que le modèle ne change pas, le détecteur reçoit la nouvelle config."""

    class FauxDetecteur:
        def __init__(self, config):
            self.config = config

    f = fenetre
    f.detecteur = FauxDetecteur(f.config)
    f._modele_charge = f.config.modele
    f.panneau.definir_seuil(0.8)
    assert f.detecteur is not None
    assert f.detecteur.config.seuil_confiance == pytest.approx(0.8)


def test_le_lancer_signale_un_modele_absent_sans_vider_la_video(
    application, fenetre, video_synthetique
):
    """Pas de poids sur le disque : l'erreur est signalée, rien ne plante.

    Le cas est réel — les `.pt` ne sont pas versionnés (cf. `.gitignore`). La
    vidéo et la ligne déjà tracées doivent SURVIVRE à l'échec, sinon
    l'opérateur recommence tout pour un simple fichier manquant.
    """
    f = fenetre
    f.charger_video(str(video_synthetique))
    f._on_tracer_ligne()
    f._on_clic_video(10, 2)
    f._on_clic_video(10, 40)
    # Le modèle se règle DANS LE PANNEAU : `lancer` relit les widgets, pas
    # `self.config`. Un `medium.pt` valide se chargerait ici et l'analyse
    # démarrerait pour de bon — le test prendrait dix secondes sur le GPU.
    f.panneau._modele.setCurrentText("fichier_absent_xyz.pt")

    f.lancer()

    assert f._en_analyse is False
    assert not f._timer_traitement.isActive()
    assert f.compteur is None
    assert f.cap is not None
    assert f.ligne is not None
    assert f.btn_lancer.isEnabled()  # on peut réessayer une fois le modèle là


# -- Validation du modèle au CHARGEMENT de la vidéo -------------------------
#
# Avant, l'absence de `.pt` ne se révélait qu'au « Lancer » — après avoir
# ouvert la vidéo et tracé la ligne. Le contrôle est remonté à l'ouverture.


def test_charger_video_confirme_un_modele_present(
    application, fenetre, video_synthetique, tmp_path
):
    """Modèle résoluble : le statut le dit, l'opérateur sait que Lancer marchera."""
    f = fenetre
    poids = tmp_path / "poids-test.pt"
    poids.write_bytes(b"")  # le contrôle ne LIT que le nom, pas les poids
    f.panneau._modele.setCurrentText(str(poids))
    f.charger_video(str(video_synthetique))
    statut = f.label_statut.text()
    assert "poids-test.pt" in statut
    assert "trouv" in statut.lower()
    assert "introuvable" not in statut.lower()


def test_charger_video_signale_un_modele_absent_avant_le_lancer(
    application, fenetre, video_synthetique, tmp_path, monkeypatch
):
    """Le nom n'existe nulle part : dit-le DÈS l'ouverture de la vidéo.

    Les dossiers de modèles sont patchés sur un `tmp_path` contenant un
    `.pt` : le test doit afficher « introuvable » partout, y compris sur une
    machine CI sans aucun poids — sinon le message basculerait vers celui
    d'une installation neuve et le test ne vérifierait plus la même branche.
    """
    import interface.app as module_app

    poids = tmp_path / "modeles"
    poids.mkdir()
    (poids / "present.pt").write_bytes(b"")
    monkeypatch.setattr(module_app, "dossiers_modeles", lambda: (poids,))
    f = fenetre
    f.panneau._modele.setCurrentText("fichier_absent_xyz.pt")
    assert f.charger_video(str(video_synthetique)) is True  # la vidéo s'ouvre
    statut = f.label_statut.text()
    assert "fichier_absent_xyz.pt" in statut
    assert "introuvable" in statut.lower()
    assert f.cap is not None, "la vidéo ne doit pas être refusée pour un modèle"


def test_charger_video_dit_ou_deposer_un_pt_sur_une_installation_neuve(
    application, fenetre, video_synthetique, monkeypatch
):
    """Aucun `.pt` sur tout le poste : le message dit OÙ déposer les poids.

    C'est le cas d'une installation neuve — le dépôt ne versionne pas les
    poids (`.gitignore`), et rien n'indiquait jusque-là où les mettre.
    """
    import interface.app as module_app

    monkeypatch.setattr(module_app, "dossiers_modeles", lambda: ())
    f = fenetre
    f.panneau._modele.setCurrentText("fantome.pt")
    f.charger_video(str(video_synthetique))
    statut = f.label_statut.text()
    assert "aucun modèle" in statut.lower()
    assert "modeles/" in statut


# -- Mémoire du dernier dossier vidéo ---------------------------------------
#
# Le dialogue « Charger la vidéo » partait du dossier de l'exécutable à
# chaque fois : remonter l'arborescence à chaque ouverture d'une session.


def test_la_memoire_du_dossier_survit_au_relaunchement():
    """Écrit puis relu — c'est la persistance entre deux lancements qui compte."""
    ecrire_dernier_dossier(r"D:\images\manif")
    assert lire_dernier_dossier() == r"D:\images\manif"


def test_memoire_absente_ou_illisible_renvoie_vide_sans_planter():
    """Fichier absent, puis JSON cassé : `""` dans les deux cas, jamais une erreur."""
    assert lire_dernier_dossier() == ""
    module_app.FICHIER_MEMOIRE_VIDEO.write_text("{ pas du json", encoding="utf-8")
    assert lire_dernier_dossier() == ""


def test_memoire_impossible_a_ecrire_ne_bloque_rien(monkeypatch, tmp_path):
    """Parent introuvable en écriture : le log suffit, l'ouverture continue."""
    bloque = tmp_path / "bloc"
    bloque.write_text("pas un dossier", encoding="utf-8")
    monkeypatch.setattr(
        module_app, "FICHIER_MEMOIRE_VIDEO", bloque / "memoire.json"
    )
    ecrire_dernier_dossier(str(tmp_path))  # ne doit pas lever


def test_charger_video_memorise_le_dossier_de_la_video(
    application, fenetre, video_synthetique
):
    f = fenetre
    assert f.charger_video(str(video_synthetique)) is True
    assert lire_dernier_dossier() == str(video_synthetique.parent)


def test_une_video_illisible_ne_change_pas_la_memoire(
    application, fenetre, tmp_path
):
    """On ne se souvient QUE des vidéos réellement ouvertes."""
    ecrire_dernier_dossier(str(tmp_path))
    f = fenetre
    assert f.charger_video(str(tmp_path / "inexistant.mp4")) is False
    assert lire_dernier_dossier() == str(tmp_path)


def test_le_dialogue_repart_du_dernier_dossier(application, fenetre, tmp_path):
    ecrire_dernier_dossier(str(tmp_path))
    assert fenetre._depart_video() == str(tmp_path)


def test_le_dialogue_retombe_sur_vide_si_le_dossier_a_disparu(
    application, fenetre, tmp_path
):
    """Disque débranché, dossier renommé : ne pas demander un chemin mort."""
    ecrire_dernier_dossier(str(tmp_path / "plus_la"))
    assert fenetre._depart_video() == ""


# -- Débit et temps restant -------------------------------------------------
#
# « Ça avance ? ça mettra combien ? » — les deux questions que pose un
# opérateur devant une scène de trente minutes, sous la barre de progression.


def test_le_debit_est_invisible_tant_que_aucune_analyse_n_a_lieu(
    application, fenetre
):
    f = fenetre
    assert f.label_debit.isHidden() is True
    assert f.label_debit.text() == ""


def test_aucun_debit_affiche_avant_une_demi_seconde(application, fenetre):
    """Sur les premiers instants, le débit oscille entre 0 et des milliers.

    Un chiffre absurde au démarrage jette le doute sur tout le reste : le
    label reste vide le temps d'une mesure exploitable.
    """
    f = fenetre
    f.frames = 100
    f._nb_frames_video = 500
    assert f._texte_debit(0.2) == ""


def test_aucun_debit_sans_frame_traitee(application, fenetre):
    """Diviser 0 frames par le temps donnerait « 0 i/s », lecture fausse."""
    f = fenetre
    f.frames = 0
    f._nb_frames_video = 500
    assert f._texte_debit(10.0) == ""


def test_debit_et_temps_restant(application, fenetre):
    """100 frames traitées en 10 s, 500 au total : 10 i/s, reste 400 frames."""
    f = fenetre
    f.frames = 100
    f._nb_frames_video = 500
    assert f._texte_debit(10.0) == "10 i/s — reste ≈ 40 s"


def test_pas_de_temps_restant_sans_total_connus(application, fenetre):
    """Conteneur muet (`_nb_frames_video == 0`) : aucune division possible.

    La barre bascule déjà en mode « occupé » dans ce cas ; le débit, lui,
    reste affiché — seule l'estimation disparaît.
    """
    f = fenetre
    f.frames = 100
    f._nb_frames_video = 0
    assert f._texte_debit(10.0) == "10 i/s"


def test_pas_de_temps_restant_quand_tout_est_passe(application, fenetre):
    """Au bout : le débit reste vrai, l'estimation n'a plus d'objet."""
    f = fenetre
    f.frames = 500
    f._nb_frames_video = 500
    assert f._texte_debit(10.0) == "50 i/s"


def test_le_debit_s_affiche_pendant_l_analyse(
    application, fenetre, video_synthetique
):
    """De l'horloge au label, par le chemin normal (`maj_compteurs`)."""
    f = fenetre
    f.charger_video(str(video_synthetique))
    f._nb_frames_video = 500
    f._debut_analyse = time.monotonic() - 10.0
    f.maj_compteurs(10, 5, 100)
    assert "i/s" in f.label_debit.text()
    assert "reste ≈" in f.label_debit.text()


def test_hors_analyse_le_debit_ne_s_maj_plus(application, fenetre):
    """Après l'arrêt, `_debut_analyse` est éteint : le label ne se remplit
    plus jamais tout seul (aucune mise à jour fantôme après un Stop)."""
    f = fenetre
    f._debut_analyse = None
    f.maj_compteurs(10, 5, 100)
    assert f.label_debit.text() == ""


def test_arreter_efface_le_temps_restant(application, fenetre):
    """Un « reste ≈ 40 s » affiché APRÈS un Stop mentirait à l'opérateur."""
    f = fenetre
    f._debut_analyse = time.monotonic()
    f.label_debit.setText("41 i/s — reste ≈ 40 s")
    f.arreter()
    assert f.label_debit.text() == ""
    assert f._debut_analyse is None


def test_la_pause_ne_compte_pas_dans_le_debit(
    application, fenetre, video_synthetique
):
    """Dix minutes d'arrêt ne doivent pas afficher « 2 i/s ».

    Le test simule 10 s de traitement puis 100 s de pause : à la reprise,
    l'horloge doit n'avoir gardé que les 10 s de travail.
    """
    f = fenetre
    f.charger_video(str(video_synthetique))
    f.compteur = FauxCompteur()
    f._ouvrir_session()
    f._debut_analyse = time.monotonic() - 110.0  # 10 s de taf + 100 s de pause
    f._basculer_pause()  # mise en pause
    assert f._pause_debut is not None
    f._pause_debut = time.monotonic() - 100.0  # la pause a duré 100 s
    f._basculer_pause()  # reprise : la pause est retirée de l'horloge
    ecoule = time.monotonic() - f._debut_analyse
    assert 0 <= ecoule < 30, f"la pause est comptée : {ecoule:.0f} s"


def test_le_debit_vit_avec_une_vraie_analyse(
    application, fenetre, video_longue, monkeypatch
):
    """Chemin complet : Lancer montre le label, l'analyse le remplit, l'arrêt l'efface.

    Le faux moteur (les quatre `monkeypatch` ci-dessous) fait tourner la
    vraie boucle minuterie/affichage sans charger de poids — le test
    vérifierait autrement le montage, pas le débit.
    """
    monkeypatch.setattr("interface.app.charger_modele", lambda *a, **k: object())
    monkeypatch.setattr("interface.app.Detecteur", FauxDetecteurMinimal)
    monkeypatch.setattr("interface.app.Tracker", lambda config: object())
    monkeypatch.setattr("interface.app.Compteur", CompteurInvisible)

    f = fenetre
    f.charger_video(str(video_longue))  # 100 frames
    f._on_tracer_ligne()
    f._on_clic_video(10, 2)
    f._on_clic_video(10, 40)
    f.lancer()
    assert f.label_debit.isHidden() is False  # visible dès le lancer

    # 5 s de traitement simulées : au-dessous du seuil d'affichage, le
    # label resterait légitimement vide.
    f._debut_analyse = time.monotonic() - 5.0
    avancer(f, 10)  # 40 frames traitées et affichées
    texte = f.label_debit.text()
    assert "i/s" in texte, texte
    assert "reste ≈" in texte, texte

    f.arreter()
    assert f.label_debit.text() == ""


# -- Avertissement « 0 compté : vérifie le sens » ------------------------
#
# Le cas testé ici est LE piège de l'outil : sur la vidéo de référence,
# `sens=-1` compte 315 personnes et `sens=+1` (le défaut) en compte 1. Un
# opérateur qui laisse le défaut voit la vidéo défiler, les boîtes de
# détection s'afficher, et un zéro qui ne bouge pas. Sans rappel, il n'a
# aucun moyen de distinguer « personne ne traverse » de « tout le monde est
# compté à l'envers ».
#
# Le rappel doit être DISCRET : pas de modale (elle bloquerait un traitement
# en cours), et pas plus d'une fois par analyse (il est rappelé à chaque frame
# affichée, donc 25 fois par seconde).


class CompteurInvisible:
    """Compteur qui ne voit personne : `total` reste à 0 indéfiniment.

    Le constructeur accepte n'importe quoi : ce fake remplace `Compteur` dans
    le test de relance, qui l'instancie avec `(config, detecteur, tracker)`.
    """

    def __init__(self, *args, **kwargs) -> None:
        self.ligne = None

    def ajuster_ligne(self, ligne) -> None:
        self.ligne = ligne

    def traiter_frame(self, img, index, ts) -> FrameResult:
        return FrameResult(
            image=img,
            total=0,
            presents=0,
            frame_index=index,
            timestamp_s=ts,
            evenements=[],
        )

    def resultat(self, modele, nb_frames, secondes):
        from compteur.types import Resultat

        return Resultat(
            total=0,
            evenements=[],
            modele=modele,
            nb_frames=nb_frames,
            presents_max=0,
            secondes=secondes,
        )


def avertissement_visible(fenetre):
    """L'avertissement est-il affiché ?

    On interroge `isHidden()` et non `isVisible()` : sous `offscreen`, et
    pour toute fenêtre jamais `show()`e, `isVisible()` renvoie `False` sur
    TOUS les enfants — y compris un label que l'on vient d'afficher. Le test
    passerait donc toujours, ou échouerait pour la mauvaise raison.
    """
    return fenetre.label_avertissement.isHidden() is False


class FauxDetecteurMinimal:
    """Détecteur sans poids : `lancer` n'a besoin que de l'instancier.

    La signature suit celle du vrai `Detecteur` (d'où le `half`, ajouté avec
    la demi-précision CUDA) : un kwarg inattendu serait capté par le try de
    `lancer` et l'analyse ne démarrerait jamais.
    """

    def __init__(self, modele, config, half: bool = False) -> None:
        self.config = config


@pytest.fixture
def video_longue(tmp_path):
    """100 frames à 25 i/s, soit 4 s de vidéo.

    La vidéo de 5 frames du reste de la suite ne permet pas d'atteindre les
    trois secondes du seuil : l'analyse y finit avant que l'avertissement
    puisse avoir lieu de se déclencher.
    """
    chemin = tmp_path / "longue.mp4"
    auteur = cv2.VideoWriter(
        str(chemin), cv2.VideoWriter_fourcc(*"mp4v"), FPS_SYNTHETIQUE, (64, 48)
    )
    assert auteur.isOpened(), "OpenCV n'a pas pu écrire la vidéo de test"
    for i in range(100):
        auteur.write(np.full((48, 64, 3), 20 + (i % 20) * 10, dtype=np.uint8))
    auteur.release()
    return chemin


def test_avertissement_sens_absent_au_demarrage(application, fenetre):
    """Une fenêtre vide n'affiche aucun rappel : rien n'a encore été compté."""
    f = fenetre
    assert avertissement_visible(f) is False
    assert f.label_avertissement.text() == ""


def test_avertissement_sens_pas_avant_le_seuil_de_trois_secondes(
    application, fenetre, video_longue
):
    """Point 3 : à 2,9 s de vidéo, le rappel n'est pas encore justifié.

    Sans ce délai, l'avertissement apparaîtrait sur les premières secondes de
    n'importe quelle analyse — y compris sur une scène où personne n'est
    encore passé — et deviendrait un bruit que l'opérateur ignore.
    """
    f = fenetre
    f.charger_video(str(video_longue))
    f.compteur = CompteurInvisible()
    f._ouvrir_session()
    avancer(f, 18)  # 18 lots × 4 frames = 72 frames = 2,88 s à 25 i/s
    assert avertissement_visible(f) is False


def test_avertissement_sens_apparait_au_dela_de_trois_secondes(
    application, fenetre, video_longue
):
    """Point 1 : zéro franc après 3 s de vidéo -> le rappel s'affiche."""
    f = fenetre
    f.charger_video(str(video_longue))
    f.compteur = CompteurInvisible()
    f._ouvrir_session()
    avancer(f, 20)  # 20 lots × 4 frames = 80 frames = 3,2 s à 25 i/s
    assert avertissement_visible(f) is True
    assert f.label_avertissement.text() == AVERTISSEMENT_SENS
    assert "sens" in f.label_avertissement.text().lower()


def test_avertissement_sens_disparait_des_que_le_compteur_repart(
    application, fenetre, video_longue
):
    """Point 2 : au premier comptage, le rappel s'efface.

    Un avertissement affiché pendant que le compteur monte serait un mensonge :
    il dirait à l'opérateur que son sens est douteux alors qu'il vient de
    compter quelqu'un.
    """
    f = fenetre
    f.charger_video(str(video_longue))
    f.compteur = CompteurInvisible()
    f._ouvrir_session()
    avancer(f, 20)  # 80 frames = 3,2 s : le seuil est franchi
    assert avertissement_visible(f) is True
    f.maj_compteurs(total=1, presents=1, frames=81)
    assert avertissement_visible(f) is False


class LabelEspion:
    """_proxy du label qui compte les `setText`.

    Ce n'est pas un test cosmétique : `_afficher` est appelé 25 fois par
    seconde, donc un rappel réécrit à chaque frame serait lu comme un
    clignotement — l'opérateur le verrait clignoter et finirait par l'ignorer.
    On compte donc les ÉCRITURES, pas seulement la présence du texte.
    """

    def __init__(self, label) -> None:
        self._label = label
        self.écritures = 0

    def setText(self, texte: str) -> None:
        self.écritures += 1
        self._label.setText(texte)

    def setVisible(self, visible: bool) -> None:
        self._label.setVisible(visible)

    def isHidden(self) -> bool:
        return self._label.isHidden()

    def text(self) -> str:
        return self._label.text()


def test_avertissement_sens_ne_clignote_pas_a_haque_frame(
    application, fenetre, video_longue
):
    """Une seule fois par analyse, jamais une fois par frame.

    `_afficher` tourne 25 fois par seconde : sans ce verrou, le label serait
    réécrit 25 fois par seconde et l'opérateur le lirait comme un clignotement.
    """
    f = fenetre
    f.charger_video(str(video_longue))
    f.compteur = CompteurInvisible()
    f._ouvrir_session()
    f.label_avertissement = LabelEspion(f.label_avertissement)
    avancer(f, 20)  # 80 frames : le seuil (75) est franchi une fois
    écritures_au_declenchement = f.label_avertissement.écritures
    assert écritures_au_declenchement == 1
    avancer(f, 10)  # 40 frames de plus : aucun nouveau setText
    assert f.label_avertissement.écritures == écritures_au_declenchement
    assert f.label_avertissement.text() == AVERTISSEMENT_SENS
    assert avertissement_visible(f) is True


def test_avertissement_sens_reapparait_a_la_relance(
    application, fenetre, video_longue, monkeypatch
):
    """Relancer une nouvelle analyse réarme le rappel.

    Le scénario « mauvais sens » se corrige en changeant le réglage et en
    RELANCANT : si le rappel ne pouvait pas se redéployer, il resterait muet au
    moment précis où l'opérateur vérifie sa correction.

    Le modèle est remplacé par un faux : sans cela, `lancer` chargerait
    `medium.pt` sur le GPU et le test prendrait dix secondes.
    """
    monkeypatch.setattr("interface.app.charger_modele", lambda *a, **k: object())
    monkeypatch.setattr("interface.app.Detecteur", FauxDetecteurMinimal)
    monkeypatch.setattr("interface.app.Tracker", lambda config: object())
    monkeypatch.setattr("interface.app.Compteur", CompteurInvisible)

    f = fenetre
    f.charger_video(str(video_longue))
    f._on_tracer_ligne()
    f._on_clic_video(10, 2)
    f._on_clic_video(10, 40)
    f.lancer()
    assert f._en_analyse is True
    assert f._avertissement_sens_affiche is False

    avancer(f, 20)  # 80 frames = 3,2 s : le rappel se déclenche
    assert avertissement_visible(f) is True

    # L'opérateur corrige le sens et RELANCE : le rappel doit pouvoir se
    # redéployer au lieu de rester muet sur la nouvelle analyse.
    f.arreter()
    f.lancer()
    assert f._avertissement_sens_affiche is False


def test_avertissement_sens_ne_saffiche_pas_hors_analyse(
    application, fenetre, video_longue
):
    """Pas d'analyse ouverte, pas de rappel — même après 100 frames.

    Sans la garde sur la session, charger une vidéo et faire défiler
    l'aperçu suffirait à afficher un avertissement qui n'a aucun sens : rien
    n'a été compté.
    """
    f = fenetre
    f.charger_video(str(video_longue))
    assert f._session_ouverte is False
    f.maj_compteurs(total=0, presents=0, frames=500)
    assert avertissement_visible(f) is False


# -- Export supprimé, boîtes vertes bornées --------------------------------


def test_il_ne_reste_plus_rien_a_exporter(application, fenetre):
    """L'export est SUPPRIMÉ, pas masqué.

    On ne vérifie pas seulement que le bouton a disparu de la barre : un bouton
    caché qui fonctionne encore est un export qui existe. Les trois voies sont
    donc fermées — l'attribut, la méthode de dialogue, et la méthode
    d'écriture — et la compilation du module doit rester possible sans
    `compteur.rapport`, dont plus rien n'est chargé au clic.

    Le récapitulatif, lui, doit SURVIVRE : c'est lui qui affiche les chiffres,
    et il s'appuie sur `rapport.statistiques`. C'est la raison pour laquelle
    `compteur/rapport.py` n'a été amputé que de l'écriture de fichiers.
    """
    import compteur.rapport as rapport

    f = fenetre
    assert not hasattr(f, "btn_export"), "le bouton Exporter doit avoir disparu"
    assert not hasattr(f, "exporter"), "la méthode d'export doit avoir disparu"
    assert not hasattr(f, "_on_exporter")
    # Le module est réduit à la COMPUTATION des chiffres : plus rien n'écrit.
    assert not hasattr(rapport, "ecrire_csv")
    assert not hasattr(rapport, "ecrire_json")
    assert callable(rapport.statistiques), "le récapitulatif en dépend"


def test_la_liste_des_boites_comptees_est_bornee(application, fenetre):
    """La mémoire d'affichage ne peut pas grossir sans borne.

    Les tracks sont lâchés à la sortie de la bande : rien ne viendrait purger
    cette liste à leur place. Sans borne explicite, une analyse de dix mille
    passages laisserait dix mille boîtes à l'écran — illisible, et la seule
    trace d'un défaut de purge.

    On éprouve les DEUX bornes séparément : la durée fait disparaître une boîte
    âgée, et le plafond en nombre résiste même quand rien n'expire (ici, tous
    les comptages sur la même frame).
    """
    from compteur.config import DUREE_BOITE_COMPTEE_FRAMES
    from interface.app import TAILLE_MAX_BOITES_COMPTES

    f = fenetre
    img = np.zeros((240, 320, 3), dtype=np.uint8)

    def frame(index, evenements, tracks=None):
        return FrameResult(
            image=img,
            frame_index=index,
            evenements=evenements,
            tracks=tracks or [],
        )

    def evenement(frame_index):
        return Evenement(
            frame=frame_index,
            timestamp_s=frame_index / 25.0,
            x=100.0,
            y=100.0,
            track_id=frame_index,
            bbox=(90.0, 90.0, 110.0, 110.0),
        )

    def track_pour(i):
        return Track(i, (100.0, 100.0), (90.0, 90.0, 110.0, 110.0), 5, True)

    # Une boîte comptée à la frame 0 est encore là à la frame 1 (track suivi)…
    f._boites_comptees_a_afficher(frame(0, [evenement(0)], [track_pour(0)]))
    assert len(f._boites_comptees) == 1
    # … et a disparu une fois son délai de visibilité dépassé, même si le
    # track est encore suivi (une personne arrêtée dans la bande).
    assert f._boites_comptees_a_afficher(
        frame(DUREE_BOITE_COMPTEE_FRAMES + 1, [], [track_pour(0)])
    ) == []

    # Le plafond en nombre tient même si rien n'expire : 300 comptages sur une
    # seule frame ne peuvent pas produire plus de 200 boîtes à l'écran.
    for i in range(300):
        f._boites_comptees_a_afficher(
            frame(0, [evenement(i)], [track_pour(i)])
        )
    assert len(f._boites_comptees) <= TAILLE_MAX_BOITES_COMPTES


def test_un_evenement_de_frame_sautee_devient_quand_meme_vert(
    application, fenetre
):
    """Une frame sautée à l'affichage ne perd PAS sa boîte verte.

    Quand la vitesse de présentation est lente, le traitement produit plusieurs
    frames entre deux affichages ; seul le dernier `FrameResult` est montré.
    L'événement d'une frame intermédiaire n'est donc JAMAIS dans
    `resultat.evenements` (qui ne porte que la frame affichée) — mais le
    compteur l'a bien enregistré dans son HISTORIQUE. Sans rattrapage, le
    total monte sans que la boîte verte ne soit jamais peinte : le chiffre
    dit « compté », l'écran ne montre rien.
    """
    f = fenetre
    img = np.zeros((240, 320, 3), dtype=np.uint8)

    # Le compteur a déjà compté quelqu'un à la frame 2 (historique complet).
    compteur = FauxCompteur()
    compteur.evenements.append(
        Evenement(
            frame=2,
            timestamp_s=2 / 25.0,
            x=100.0,
            y=100.0,
            track_id=7,
            bbox=(90.0, 90.0, 110.0, 110.0),
        )
    )
    f.compteur = compteur

    # L'affichage saute la frame 2 : il présente la frame 5, SANS événement.
    # Le track compté est encore suivi (dans la bande).
    track = Track(7, (105.0, 100.0), (95.0, 90.0, 115.0, 110.0), 20, True)
    resultat = FrameResult(image=img, frame_index=5, tracks=[track])
    boites = f._boites_comptees_a_afficher(resultat)

    assert len(boites) == 1, (
        "l'événement de la frame sautée doit produire sa boîte verte"
    )
    # Et la boîte est à la position COURANTE du track (la personne avance),
    # pas à la position figée du franchissement.
    assert boites[0][1:5] == (95.0, 90.0, 115.0, 110.0)


def test_la_boite_comptee_suit_la_personne_et_suit_le_glisser(
    application, fenetre
):
    """Les deux demandes de l'opérateur, en un seul geste vérifié.

    **1. La boîte verte SUIT la personne comptée, puis disparaît à la sortie
    de la bande.** Elle n'est pas figée sur la ligne : elle est peinte à la
    position COURANTE du track, qui continue d'être suivi après le
    franchissement. Quand la personne sort de la bande (le track disparaît de
    `resultat.tracks`), la boîte disparaît avec elle — le geste exact que
    l'opérateur décrit : détecté dans la bande, vert au franchissement, plus
    de boîte à la sortie.

    **2. Le glisser-déposer déplace la ligne ET sa bande.** Un clic posé DANS
    la bande, une ligne existant, followed d'un mouvement : c'est un
    déplacement. La bande est vérifiée par son rectangle dérivé après le geste,
    ce qui prouve qu'elle suit sans qu'aucun second état soit synchronisé à la
    main. Un clic HORS bande reste un tracé, et une analyse en cours rend le
    geste inopérant au lieu de le laisser tenter un déplacement refusé.
    """
    from interface.overlay import COULEUR_COMPTEE

    f = fenetre
    f.resize(700, 500)
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    f.video.definir_image(img)

    def frame(index, evenements, tracks=None):
        return FrameResult(
            image=img,
            frame_index=index,
            evenements=evenements,
            tracks=tracks or [],
        )

    def evenement(frame_index):
        return Evenement(
            frame=frame_index,
            timestamp_s=frame_index / 25.0,
            x=100.0,
            y=100.0,
            track_id=frame_index,
            bbox=(90.0, 90.0, 110.0, 110.0),
        )

    # -- 1. La boîte SUIT la personne ---------------------------------------
    # Le track compté à la frame 0 est encore suivi à la frame 10, déplacé de
    # 10 px : la boîte verte doit être peinte à sa position COURANTE, pas à
    # celle du franchissement.
    track = Track(0, (110.0, 100.0), (100.0, 90.0, 120.0, 110.0), 15, True)
    f._boites_comptees_a_afficher(frame(0, [evenement(0)], [track]))
    suivi = f._boites_comptees_a_afficher(frame(10, [], [track]))
    assert len(suivi) == 1, "la boîte doit survivre tant que le track est suivi"
    assert suivi[0][1:5] == (100.0, 90.0, 120.0, 110.0), (
        "la boîte doit être à la position COURANTE du track, pas figée"
    )

    # Quand le track sort de la bande (plus suivi), la boîte disparaît.
    f._boites_comptees_a_afficher(frame(20, []))
    assert f._boites_comptees_a_afficher(frame(30, [])) == [], (
        "le track mort (sorti de la bande) doit emporter sa boîte"
    )

    # La boîte est RÉELLEMENT peinte, remplie, à sa position courante. On lit
    # au CENTRE : la boîte est réduite de 3 px de chaque côté.
    sortie = dessiner(
        img,
        frame(0, []),
        boites_comptees=[(0, 90.0, 90.0, 110.0, 110.0)],
    )
    couleur = sortie[100, 100].astype(int)
    assert np.allclose(couleur, COULEUR_COMPTEE, atol=2), (
        f"la boîte comptée devrait être peinte en vert, lu {tuple(couleur)}"
    )

    # -- 2. Le glisser-déposer ---------------------------------------------
    assert f.definir_ligne((300, 100), (300, 380))
    zone = f._zone_deplacement()
    assert zone is not None, "une ligne posée doit rendre sa bande déplaçable"
    f._rafraichir_zone_deplacement()

    wx, wy = f.video.vers_widget(zone[0] + 5, zone[1] + 5)
    hors_x, hors_y = f.video.vers_widget(2, 2)

    clics = []
    f.video.clic.connect(lambda x, y: clics.append((x, y)))

    # Un clic HORS bande reste un tracé.
    f.video.mousePressEvent(_evenement_souris(hors_x, hors_y))
    f.video.mouseReleaseEvent(_evenement_souris(hors_x, hors_y, relâché=True))
    assert len(clics) == 1, "un clic hors bande doit rester un tracé"

    # Un clic DANS la bande, suivi d'un mouvement, déplace.
    p1_avant, p2_avant = f.ligne.p1, f.ligne.p2
    rect_avant = f.ligne.rect_bande_detection(640, 480)
    f.video.mousePressEvent(_evenement_souris(wx, wy))
    f.video.mouseMoveEvent(_evenement_souris(wx + 60, wy))
    f.video.mouseReleaseEvent(_evenement_souris(wx + 60, wy, relâché=True))

    assert (f.ligne.p1, f.ligne.p2) != (p1_avant, p2_avant), "la ligne n'a pas bougé"
    rect_apres = f.ligne.rect_bande_detection(640, 480)
    assert rect_apres != rect_avant, "la bande n'a PAS suivi la ligne"
    # Le décalage est identique des deux côtés : c'est une translation, pas
    # une rotation ni un redimensionnement.
    dx_ligne = f.ligne.p1[0] - p1_avant[0]
    assert rect_apres[0] - rect_avant[0] == dx_ligne, (
        "la bande a glissé différemment de la ligne"
    )

    # Pendant une analyse, le geste est INOPÉRANT, pas planté.
    f.ligne.verrouiller()
    f._rafraichir_zone_deplacement()
    assert f._zone_deplacement() is None, "une ligne verrouillée ne doit pas être déplaçable"
    p_avant = f.ligne.p1
    f.video.mousePressEvent(_evenement_souris(wx, wy))
    f.video.mouseMoveEvent(_evenement_souris(wx - 80, wy))
    f.video.mouseReleaseEvent(_evenement_souris(wx - 80, wy, relâché=True))
    assert f.ligne.p1 == p_avant, "le glissement a bougé une ligne verrouillée"


# -- Bouton de soutien -----------------------------------------------------


def test_le_bouton_de_soutien_existe_et_ouvre_le_bon_lien(
    application, fenetre, monkeypatch
):
    """Le bouton « Buy me a coffee » ouvre la page de don de l'opérateur.

    Le widget fourni est un script JavaScript pour page web ; dans une
    application de bureau il est remplacé par un bouton natif qui ouvre le
    même lien dans le navigateur par défaut. Le `data-slug` (galaxiel) devient
    la partie du chemin de l'URL.
    """
    from interface.app import LIEN_SOUTIEN

    f = fenetre
    assert f.btn_soutenir.text() == "☕ Buy me a coffee"
    assert LIEN_SOUTIEN == "https://buymeacoffee.com/galaxiel"

    ouverts = []
    monkeypatch.setattr(
        "interface.app.QDesktopServices.openUrl",
        lambda url: (ouverts.append(url.toString()) or True),
    )
    f._on_soutenir()
    assert ouverts == [LIEN_SOUTIEN], "le clic doit ouvrir la page de don"


def _evenement_souris(x, y, relâché: bool = False):
    """Construit un QMouseEvent de presse (ou de relâchement) en coordonnées
    WIDGET, comme le fait Qt pour un vrai geste."""
    from PySide6.QtCore import QEvent, QPointF
    from PySide6.QtGui import QMouseEvent

    typ = (
        QEvent.Type.MouseButtonRelease if relâché else QEvent.Type.MouseButtonPress
    )
    bouton = Qt.MouseButton.NoButton if relâché else Qt.MouseButton.LeftButton
    return QMouseEvent(
        typ,
        QPointF(x, y),
        QPointF(x, y),
        Qt.MouseButton.LeftButton,
        bouton,
        Qt.KeyboardModifier.NoModifier,
    )
