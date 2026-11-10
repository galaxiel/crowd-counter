"""Export optionnel du bilan (lot 6 / section 4 de l'audit).

Depuis le retrait de l'export en v3, le résultat n'existait qu'en RAM :
fenêtre fermée, chiffre perdu. L'opérateur le recopiait à la main. Ces
helpers reconstruisent un export OPTIONNEL depuis `statistiques` et les
événements — même source que le récapitulatif, donc même vérité. Purs,
sans Qt : ils ne décident rien, ils formatent ce qui est déjà calculé.
"""

from __future__ import annotations

import json

from compteur.rapport import csv_evenements, json_bilan, statistiques, texte_bilan
from compteur.types import Evenement, Resultat


def _resultat() -> Resultat:
    return Resultat(
        total=2,
        evenements=[
            Evenement(frame=3, timestamp_s=0.12, x=10.0, y=20.0, track_id=1),
            Evenement(frame=7, timestamp_s=0.28, x=11.5, y=21.0, track_id=2),
        ],
        modele="tetes-medium.onnx",
        nb_frames=900,
        presents_max=3,
        duree_video_s=150.0,
        secondes=12.0,
    )


def test_texte_bilan_contient_total_et_modele():
    texte = texte_bilan(_resultat())
    assert "2" in texte
    assert "tetes-medium.onnx" in texte
    assert "personnes" in texte.lower()


def test_texte_bilan_publie_les_avertissements():
    """Un bilan copié doit porter les mêmes avertissements que le récap."""
    r = Resultat(total=0, nb_frames=900, presents_max=40, duree_video_s=150.0)
    texte = texte_bilan(r)
    stats = statistiques(r)
    for avertissement in stats["fiabilite"]["avertissements"]:
        assert avertissement in texte


def test_csv_evenements_une_ligne_par_comptage():
    lignes = csv_evenements(_resultat()).strip().splitlines()
    assert len(lignes) == 3  # en-tête + 2 franchissements
    assert "track_id" in lignes[0]
    assert "timestamp_s" in lignes[0]
    assert "0.12" in lignes[1]
    assert "1" in lignes[1]


def test_csv_evenements_vide_garde_l_en_tete():
    """Aucun comptage : un CSV avec en-tête seul, pas un fichier vide."""
    lignes = csv_evenements(Resultat(total=0)).strip().splitlines()
    assert len(lignes) == 1
    assert "track_id" in lignes[0]


def test_json_bilan_est_statistiques():
    r = _resultat()
    assert json.loads(json_bilan(r)) == statistiques(r)