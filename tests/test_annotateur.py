"""Tests de l'annotateur au clic (tools/annotateur.py).

Deux étages : la session d'annotation (pure, sans Qt) et la fenêtre
(offscreen, source vidéo factice). Le fichier produit doit se relire par
`tools.verite_terrain.lire_annotations` : c'est le contrat du banc.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

import numpy as np  # noqa: E402
from PySide6.QtCore import QEvent, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QMouseEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from tools.annotateur import FenetreAnnotation, SessionAnnotation  # noqa: E402
from tools.verite_terrain import lire_annotations  # noqa: E402


def test_ajouter_range_le_frame_et_la_position():
    s = SessionAnnotation()
    s.ajouter(3732, 640, 300)
    assert s.entrees == [(3732, 640, 300)]
    assert len(s) == 1


def test_annuler_retire_le_dernier_clic():
    s = SessionAnnotation()
    s.ajouter(3732, 640, 300)
    s.ajouter(3800)
    s.annuler()
    assert s.entrees == [(3732, 640, 300)]


def test_annuler_sur_session_vide_ne_plante_pas():
    s = SessionAnnotation()
    s.annuler()
    assert len(s) == 0


def test_supprimer_retire_la_ligne_demandee():
    s = SessionAnnotation()
    s.ajouter(3732)
    s.ajouter(3800)
    s.ajouter(3900)
    s.supprimer(1)
    assert [f for f, _, _ in s.entrees] == [3732, 3900]


def test_vers_texte_se_relit_par_le_banc(tmp_path):
    s = SessionAnnotation()
    s.ajouter(3800)
    s.ajouter(3732, 640, 300)
    chemin = tmp_path / "ann.txt"
    chemin.write_text(s.vers_texte(), encoding="utf-8")
    assert lire_annotations(chemin) == [3732, 3800]


def test_aller_retour_texte_garde_les_positions():
    s = SessionAnnotation()
    s.ajouter(3732, 640, 300)
    s.ajouter(3800)
    reprise = SessionAnnotation.depuis_texte(s.vers_texte())
    assert reprise.entrees == s.entrees


def test_depuis_texte_accepte_un_fichier_sans_commentaires():
    s = SessionAnnotation.depuis_texte("# tête\n3732\n3800  # hésitation\n")
    assert s.entrees == [(3732, None, None), (3800, None, None)]


# -- Fenêtre (offscreen, source vidéo factice) ------------------------------


class FausseSource:
    """Une image unie par frame, identifiable à sa valeur : pas de vidéo réelle."""

    fps = 30.0

    def __init__(self, debut: int, fin: int) -> None:
        self.debut = debut
        self.fin = fin
        self.index = debut

    def _image(self) -> np.ndarray:
        return np.full((720, 1280, 3), self.index % 256, dtype=np.uint8)

    def suivante(self):
        if self.index + 1 >= self.fin:
            return None
        self.index += 1
        return self._image()

    def precedente(self):
        if self.index - 1 < self.debut:
            return None
        self.index -= 1
        return self._image()

    def aller_a(self, index: int):
        self.index = index
        return self._image()

    def fermer(self) -> None:
        pass


@pytest.fixture
def application():
    return QApplication.instance() or QApplication([])


def construire(application, tmp_path, debut=3600, fin=3700, sortie=None):
    source = FausseSource(debut, fin)
    f = FenetreAnnotation(
        source=source,
        sortie=sortie if sortie is not None else tmp_path / "ann.txt",
        debut=debut,
        fin=fin,
        dossier_lignes=tmp_path,
    )
    f.resize(1200, 800)
    f.show()
    application.processEvents()
    return f


def cliquer_video(f, application):
    """Un vrai clic gauche au centre de la zone vidéo, comme l'opérateur."""
    w = f.video
    centre = w.rect().center()
    evenement = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(centre.x(), centre.y()),
        QPointF(centre.x(), centre.y()),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    w.mousePressEvent(evenement)
    application.processEvents()


def test_un_clic_enregistre_le_frame_affiche(application, tmp_path):
    f = construire(application, tmp_path)
    cliquer_video(f, application)
    assert [e[0] for e in f.session.entrees] == [3600]
    assert f.liste.count() == 1


def test_un_clic_met_la_lecture_en_pause(application, tmp_path):
    f = construire(application, tmp_path)
    f.bouton_lecture.click()
    assert f.en_cours is True
    cliquer_video(f, application)
    assert f.en_cours is False


def test_pas_avant_et_arriere_changent_le_frame_affiche(application, tmp_path):
    f = construire(application, tmp_path)
    f.bouton_avant.click()
    assert f.source.index == 3601
    f.bouton_arriere.click()
    assert f.source.index == 3600


def test_enregistrer_ecrit_un_fichier_relu_par_le_banc(application, tmp_path):
    sortie = tmp_path / "ann.txt"
    f = construire(application, tmp_path, sortie=sortie)
    cliquer_video(f, application)
    f.bouton_avant.click()
    cliquer_video(f, application)
    f.bouton_enregistrer.click()
    assert lire_annotations(sortie) == [3600, 3601]


def test_une_session_reprise_recharge_le_fichier_existant(application, tmp_path):
    sortie = tmp_path / "ann.txt"
    sortie.write_text("3732\n3800\n", encoding="utf-8")
    f = construire(application, tmp_path, sortie=sortie)
    assert len(f.session) == 2
    assert f.liste.count() == 2


def test_annuler_et_supprimer_mettent_la_liste_a_jour(application, tmp_path):
    f = construire(application, tmp_path)
    cliquer_video(f, application)
    f.bouton_avant.click()
    cliquer_video(f, application)
    f.bouton_annuler.click()
    assert f.liste.count() == 1
    f.liste.setCurrentRow(0)
    f.bouton_supprimer.click()
    assert f.liste.count() == 0
    assert len(f.session) == 0


# -- Sélecteur de vidéo + segments -----------------------------------------


def construire_plage(
    application,
    tmp_path,
    debut=0,
    fin=900,
    nb_frames=7399,
    chemin="D:/x/manif_test.mp4",
    sortie=None,
):
    source = FausseSource(debut, fin)
    f = FenetreAnnotation(
        source=source,
        sortie=sortie if sortie is not None else tmp_path / "ann.txt",
        debut=debut,
        fin=fin,
        chemin=chemin,
        nb_frames=nb_frames,
        dossier_lignes=tmp_path,
    )
    f.resize(1200, 800)
    f.show()
    application.processEvents()
    return f


def test_demarre_sur_le_premier_segment(application, tmp_path):
    f = construire_plage(application, tmp_path)
    assert (f.debut, f.fin) == (0, 900)
    assert f.champ_debut.value() == 0
    assert f.champ_fin.value() == 900
    assert f.case_tout.isChecked() is False
    assert f.bouton_segment_suivant.isEnabled() is True


def test_segment_suivant_enchaine_sans_revenir_au_debut(application, tmp_path):
    f = construire_plage(application, tmp_path)
    f.bouton_segment_suivant.click()
    assert (f.debut, f.fin) == (900, 1800)
    assert (f.source.debut, f.source.fin) == (900, 1800)
    assert f.champ_debut.value() == 900
    assert f.champ_fin.value() == 1800


def test_segment_suivant_s_arrete_a_la_fin(application, tmp_path):
    f = construire_plage(application, tmp_path, debut=7000, fin=7399, nb_frames=7399)
    f.bouton_segment_suivant.click()
    assert (f.debut, f.fin) == (7000, 7399)


def test_case_toute_la_video_regle_la_plage(application, tmp_path):
    f = construire_plage(application, tmp_path)
    f.case_tout.setChecked(True)
    assert (f.debut, f.fin) == (0, 7399)
    assert f.champ_debut.isEnabled() is False
    assert f.champ_fin.isEnabled() is False
    assert f.bouton_segment_suivant.isEnabled() is False


def test_champs_reglent_la_plage(application, tmp_path):
    f = construire_plage(application, tmp_path)
    f.champ_debut.setValue(3600)
    f.champ_fin.setValue(4500)
    assert (f.debut, f.fin) == (3600, 4500)


def test_charger_video_repart_au_premier_segment(application, tmp_path):
    f = construire_plage(application, tmp_path)
    f.charger_video("D:/x/test57.mp4", source=FausseSource(0, 5000), nb_frames=5000)
    assert (f.debut, f.fin) == (0, 900)
    assert f.nb_frames == 5000
    assert "test57" in f.sortie.name


def test_nom_sortie_video_hors_reference_porte_le_nom(application, tmp_path):
    f = FenetreAnnotation(
        source=FausseSource(0, 900),
        debut=0,
        fin=900,
        chemin="D:/x/test57.mp4",
        nb_frames=7399,
    )
    f.show()
    application.processEvents()
    assert "test57" in f.sortie.name
    assert f.sortie.name.endswith("_operateur.txt")


def test_nom_sortie_reference_garde_le_nom_historique(application, tmp_path):
    from tools import verite_terrain as banc

    f = FenetreAnnotation(
        source=FausseSource(3600, 4500),
        debut=3600,
        fin=4500,
        chemin=banc.VIDEO_REF,
        nb_frames=7399,
    )
    f.show()
    application.processEvents()
    assert f.sortie.name == "segment_3600-4500_operateur.txt"


def test_sans_video_reference_la_fenetre_s_ouvre_quand_meme(application, tmp_path):
    # Vidéo de référence absente : la fenêtre doit s'ouvrir (source vide) pour
    # que le bouton « Ouvrir une vidéo… » reste atteignable.
    f = FenetreAnnotation(
        chemin="D:/nexistepas.mp4", debut=0, fin=900, nb_frames=1000
    )
    f.show()
    application.processEvents()
    assert f._sans_video is True
    assert f.video is not None


def test_les_reperes_ne_montrent_que_les_clics_proches(application, tmp_path):
    f = construire(application, tmp_path)
    f.session.ajouter(3600, 100, 100)
    f.session.ajouter(3605, 200, 150)
    f.session.ajouter(3700, 300, 300)  # trop loin du frame 3605
    f.session.ajouter(3601)  # sans position : pas de repère
    proches = f._clics_proches(3605)
    frames = [p[0] for p in proches]
    assert 3600 in frames
    assert 3605 in frames
    assert 3700 not in frames
    assert 3601 not in frames


# -- Ligne de comptage (tracé + mémorisation) ------------------------------


def test_tracer_la_ligne_deux_clics_memorise(application, tmp_path):
    from tools import verite_terrain as banc

    f = construire(application, tmp_path)
    assert f.ligne == banc.LIGNE_REF
    f.bouton_ligne.click()
    assert f._mode_ligne is True
    f._sur_clic(100, 120)
    f._sur_clic(600, 120)
    assert f._mode_ligne is False
    assert f.ligne == (100.0, 120.0, 600.0, 120.0)
    relu = banc.charger_ligne(f.chemin, tmp_path / "lignes.json")
    assert relu == ((100.0, 120.0, 600.0, 120.0), -1)


def test_inverser_le_sens_memorise(application, tmp_path):
    from tools import verite_terrain as banc

    f = construire(application, tmp_path)
    assert f.sens == -1
    f.bouton_sens.click()
    assert f.sens == 1
    relu = banc.charger_ligne(f.chemin, tmp_path / "lignes.json")
    assert relu is not None and relu[1] == 1


def test_ligne_memorisee_rechargee_a_l_ouverture(application, tmp_path):
    import json

    from tools import verite_terrain as banc

    (tmp_path / "lignes.json").write_text(
        json.dumps(
            {banc._cle_video(banc.VIDEO_REF): {"ligne": [10, 20, 30, 40], "sens": 1}}
        ),
        encoding="utf-8",
    )
    f = construire(application, tmp_path)
    assert f.ligne == (10.0, 20.0, 30.0, 40.0)
    assert f.sens == 1


def test_supprimer_sans_selection_retire_la_plus_recente(application, tmp_path):
    f = construire(application, tmp_path)
    cliquer_video(f, application)  # frame 3600
    f.bouton_avant.click()
    cliquer_video(f, application)  # frame 3601
    assert len(f.session) == 2
    f.bouton_supprimer.click()  # aucune ligne sélectionnée -> retire la plus récente
    assert len(f.session) == 1
    assert f.session.entrees[0][0] == 3600


def test_enregistrer_affiche_le_chemin_dans_la_fenetre(application, tmp_path):
    sortie = tmp_path / "ann.txt"
    f = construire(application, tmp_path, sortie=sortie)
    cliquer_video(f, application)
    f.bouton_enregistrer.click()
    assert str(sortie) in f.label_etat.text()