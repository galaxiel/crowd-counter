"""Les profils de réglages livrés : valides, et copiés avec le build.

Les fichiers `config/profils/*.json` du dépôt partent avec chaque
installation (`tools/copier_modeles.py`). Trois contrats :

1. chaque fichier se relit en `Config` — un JSON écrit à la main qui
   dérailerait fermerait le panneau des profils à la première relecture ;
2. la liste livrée n'est pas vide (sinon l'étape de copie devient
   silencieusement inutile) ;
3. `profils_livres` trie et ne voit que les `.json`.
"""

from __future__ import annotations

import pathlib

from compteur.config import Config
from tools.copier_modeles import PROFILS_DOSSIER, copier, profils_livres


def test_les_profils_livres_se_relisent_en_config():
    profils = profils_livres()
    assert profils, "aucun profil livré dans config/profils/"
    for p in profils:
        config = Config.depuis_fichier(p)
        assert config.sens in (1, -1), p
        assert config.modele.endswith(".pt"), p


def test_profils_livres_tries_et_json_seulement(tmp_path: pathlib.Path):
    (tmp_path / "b.json").write_text("{}", encoding="utf-8")
    (tmp_path / "a.json").write_text("{}", encoding="utf-8")
    (tmp_path / "note.txt").write_text("x", encoding="utf-8")
    (tmp_path / "sous").mkdir()
    trouves = profils_livres(tmp_path)
    assert [p.name for p in trouves] == ["a.json", "b.json"]


def test_dossier_absent_n_est_pas_une_erreur(tmp_path: pathlib.Path):
    assert profils_livres(tmp_path / "inexistant") == []


def test_la_copie_ecrase_sauf_demande(tmp_path: pathlib.Path):
    source = PROFILS_DOSSIER / "manif-plongee.json"
    dest = tmp_path / "config" / "profils"
    copies, _ = copier([source], dest)
    assert [c.name for c in copies] == ["manif-plongee.json"]
    (dest / "manif-plongee.json").write_text("{}", encoding="utf-8")
    copies, ignores = copier([source], dest, ecraser=False)
    assert copies == []
    assert [i.name for i in ignores] == ["manif-plongee.json"]
