"""L'ancrage du dossier courant sur l'exe (main.ancrer_dossier_courant).

L'app lit des dossiers relatifs à son installation ; le bug du 05/11
(profils vides après une mise à jour automatique) venait d'une relance avec
un dossier courant faux. Le filet : l'app gelée se réancère elle-même.
"""

from __future__ import annotations

import pathlib

import main


def test_gelee_se_reancre_sur_l_exe(tmp_path, monkeypatch):
    faux_exe = tmp_path / "CompteurManifestation" / "CompteurManifestation.exe"
    faux_exe.parent.mkdir()
    faux_exe.write_bytes(b"")
    monkeypatch.setattr(main.sys, "frozen", True, raising=False)
    monkeypatch.setattr(main.sys, "executable", str(faux_exe))
    main.ancrer_dossier_courant()
    assert pathlib.Path.cwd() == faux_exe.parent


def test_hors_gel_aucune_action(tmp_path, monkeypatch):
    monkeypatch.setattr(main.sys, "frozen", False, raising=False)
    avant = pathlib.Path.cwd()
    main.ancrer_dossier_courant()
    assert pathlib.Path.cwd() == avant
