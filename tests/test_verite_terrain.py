"""Tests du banc de vérité terrain (`tools/verite_terrain.py`).

Seules les fonctions PURES sont testées ici : lecture d'annotation et
appariement. Elles décident de la qualité du diagnostic — un appariement qui
apparie n'importe quoi fabrique un « écart zéro » qui ne veut rien dire, pire
qu'un écart visible.

L'extraction vidéo et le moteur ne sont PAS testés : l'une est du décodage
cv2 (couvert par `tests/test_resolution_auto.py`), l'autre est
`tools/mesurer_reference.py` lui-même, dont le contrat est la mesure.
"""

import importlib.util
import pathlib

import pytest

RACINE = pathlib.Path(__file__).resolve().parent.parent


def _charger_module():
    """Importe `tools/verite_terrain.py` par son chemin.

    `tools/` n'est pas un paquet (pas d'`__init__.py`) : l'import par nom
    échouerait. Le chargement par `spec_from_file_location` est la manière
    standard de tester un script autonome sans le promouvoir à un paquet.
    """
    spec = importlib.util.spec_from_file_location(
        "verite_terrain", RACINE / "tools" / "verite_terrain.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


vt = _charger_module()


# -- Lecture d'annotations ---------------------------------------------------


def test_une_seule_frame(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("3700\n", encoding="utf-8")
    assert vt.lire_annotations(f) == [3700]


def test_les_lignes_vides_et_commentaires_sont_ignores(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("# en-tête\n\n3700\n   \n3800\n", encoding="utf-8")
    assert vt.lire_annotations(f) == [3700, 3800]


def test_un_commentaire_en_fin_de_ligne_est_coupé(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("3700  # la deuxième du groupe\n", encoding="utf-8")
    assert vt.lire_annotations(f) == [3700]


def test_l_ordonne_d_ecriture_est_sans_effet(tmp_path):
    """Un humain qui remonte pour ne rien rater ne doit rien casser."""
    f = tmp_path / "a.txt"
    f.write_text("3900\n3700\n3800\n", encoding="utf-8")
    assert vt.lire_annotations(f) == [3700, 3800, 3900]


def test_une_frame_en_double_est_dédoublonnée(tmp_path):
    """Le même chiffre noté deux fois est un humain hésitant, pas deux gens."""
    f = tmp_path / "a.txt"
    f.write_text("3700\n3700\n", encoding="utf-8")
    assert vt.lire_annotations(f) == [3700]


def test_un_fichier_vide_ne_valait_rien_mais_ne_casse_rien(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("# rien de rempli\n", encoding="utf-8")
    assert vt.lire_annotations(f) == []


def test_une_ligne_illisible_nomme_son_numero(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("3700\ndeux mille\n", encoding="utf-8")
    with pytest.raises(ValueError, match="ligne 2"):
        vt.lire_annotations(f)


def test_une_frame_negative_est_refusee(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("-5\n", encoding="utf-8")
    with pytest.raises(ValueError, match="négatif"):
        vt.lire_annotations(f)


def test_le_fichier_debutant_est_ecrit_et_relu(tmp_path):
    """Le modèle doit être LISIBLE par `lire_annotations` — un en-tête qui
    casserait la lecture ferait échouer la comparaison avant de commencer."""
    chemin = vt.ecrire_modele_annotation(tmp_path / "segment_3600-4500.txt")
    assert chemin.exists()
    assert vt.lire_annotations(chemin) == []
    # Un second appel ne réécrit pas (une heure d'annotation n'est pas perdue).
    chemin.write_text("3700\n", encoding="utf-8")
    vt.ecrire_modele_annotation(chemin)
    assert vt.lire_annotations(chemin) == [3700]


# -- Appariement -------------------------------------------------------------


def test_une_correspondance_exacte():
    r = vt.apparier([3700], [3700])
    assert r["apparies"] == [(3700, 3700)]
    assert r["manques"] == []
    assert r["en_trop"] == []


def test_un_ecart_de_deux_frames_apparie_encore():
    """L'humain date la frame où la personne EST SUR la ligne ; le moteur
    date son franchissement lissé. Quelques frames d'écart sont normales."""
    r = vt.apparier([3700], [3702])
    assert r["apparies"] == [(3700, 3702)]
    assert r["manques"] == [] and r["en_trop"] == []


def test_un_ecart_trop_grand_n_apparie_pas():
    r = vt.apparier([3700], [3700 + vt.TOLERANCE_DEFAUT + 1])
    assert r["apparies"] == []
    assert r["manques"] == [3700]
    assert r["en_trop"] == [3700 + vt.TOLERANCE_DEFAUT + 1]


def test_la_tolerance_est_inclusive():
    r = vt.apparier([3700], [3700 + vt.TOLERANCE_DEFAUT], tolerance=vt.TOLERANCE_DEFAUT)
    assert len(r["apparies"]) == 1


def test_on_apparie_au_plus_proche():
    """Deux humains encadrent le même événement moteur : le plus proche gagne,
    l'autre est un manquant — apparier au hasard masquerait l'écart réel."""
    r = vt.apparier([3700, 3701], [3702])
    assert r["apparies"] == [(3701, 3702)]
    assert r["manques"] == [3700]


def test_un_evenement_moteur_ne_sert_que_une_fois():
    r = vt.apparier([3700, 3701], [3700])
    assert r["apparies"] == [(3700, 3700)]
    assert r["manques"] == [3701]


def test_le_moteur_manque_quelqu_un():
    r = vt.apparier([3700, 3800, 3900], [3700, 3900])
    assert r["manques"] == [3800]
    assert len(r["apparies"]) == 2


def test_le_moteur_compte_un_faux_positif():
    r = vt.apparier([3700], [3700, 3800])
    assert r["en_trop"] == [3800]
    assert len(r["apparies"]) == 1


def test_deux_franchissements_rapproches_ne_se_volent_pas():
    """Deux gens qui franchissent à 10 frames d'écart sont DEUX gens."""
    r = vt.apparier([3700, 3710], [3701, 3711])
    assert r["apparies"] == [(3700, 3701), (3710, 3711)]
    assert r["manques"] == [] and r["en_trop"] == []


def test_l_ordre_des_entrees_est_sans_effet():
    """Le moteur renvoie ses événements dans l'ordre du compteur, l'humain
    dans l'ordre de sa relecture : ni l'un ni l'autre n'est garanti trié."""
    r = vt.apparier([3900, 3700], [3898, 3699])
    assert r["apparies"] == [(3700, 3699), (3900, 3898)]


def test_des_listes_vides():
    assert vt.apparier([], []) == {"apparies": [], "manques": [], "en_trop": []}
    assert vt.apparier([3700], [])["manques"] == [3700]
    assert vt.apparier([], [3700])["en_trop"] == [3700]


def test_une_scene_dense_typique():
    """32 humains contre 36 moteur (mesure réelle du 30/10/2026) : 32 appariés,
    4 en trop. Le diagnostic doit isoler les 4 suspects, pas noyer le tout."""
    humain = [3600 + 28 * i for i in range(32)]
    moteur = sorted(humain + [3605, 3750, 3900, 4100])
    r = vt.apparier(humain, moteur)
    assert len(r["apparies"]) == 32
    assert r["manques"] == []
    assert r["en_trop"] == [3605, 3750, 3900, 4100]


def test_une_tolerance_negative_est_refusee():
    with pytest.raises(ValueError, match="négative"):
        vt.apparier([3700], [3700], tolerance=-1)


def test_un_ecart_negatif_absolu_sapparie_quand_meme():
    """Le sens de l'écart n'a pas d'importance : le moteur peut devancer
    l'humain comme l'inverse."""
    r = vt.apparier([3700], [3695])
    assert r["apparies"] == [(3700, 3695)]
