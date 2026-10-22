"""Copier les poids `.pt` dans `modeles/`, à côté de l'exécutable construit.

Pourquoi une copie et pas un embarquement dans l'exécutable :

- les poids font 50 Mo chacun (`medium.pt` : 50 Mo, `yolov8n-head.pt` :
  50 Mo, `nano.pt` : 6 Mo) et sont **volontairement hors du dépôt**
  (`.gitignore` : `*.pt`) ;
- le modèle est un **paramètre**, pas une dépendance : changer de détecteur,
  en ajouter un, ou essayer un modèle entraîné localement doit se faire en
  déposant un fichier, sans reconstruire l'exécutable ;
- l'archive onefile est ré-écrite en entier à chaque construction : y mettre
  les poids allonge le build sans rien apporter.

Le logiciel balaie le dossier courant, `modeles/` et le dossier personnel
(`compteur.config.dossiers_modeles`) — les MÊMES dossiers, dans le même
ordre, que le chargement du modèle. Un double-clic sur l'exécutable donne
pour dossier courant le dossier de l'exécutable : les poids copiés dans son
sous-dossier `modeles/` apparaissent donc dans la liste, et se chargent.

Usage :

    python tools/copier_modeles.py            # medium.pt, nano.pt, yolov8n-head.pt
    python tools/copier_modeles.py --dest /tmp/ailleurs
    python tools/copier_modeles.py --propre   # ne recopie que ce qui manque
"""

from __future__ import annotations

import argparse
import pathlib
import shutil
import sys

RACINE = pathlib.Path(__file__).resolve().parent.parent
# `compteur` doit être importable quel que soit le dossier de lancement : on
# ancre la racine du dépôt sur `sys.path`, comme les autres outils.
sys.path.insert(0, str(RACINE))

from compteur.config import DOSSIER_MODELES_NOM  # noqa: E402

#: Sorties de build acceptées, dans l'ordre de préférence. Le `.spec` produit
#: un DOSSIER (`dist/CompteurManifestationV2/`) et non un `.exe` isolé ; les
#: poids vont dans son sous-dossier `modeles/`, celui que le logiciel balaie.
#: Si un build onefile a été produit, ils vont dans `dist/modeles/`.
BUILDS_CIBLES = (
    RACINE / "dist" / "CompteurManifestationV2",
    RACINE / "dist",
)

#: Poids livrés avec le projet, dans l'ordre de préférence pour l'utilisateur.
MODELES_DEFAUT = ("medium.pt", "nano.pt", "yolov8n-head.pt")

#: Note déposée dans le dossier `modeles/` de l'installation : elle explique à
#: l'opérateur ce que ce dossier fait, sans qu'il ait à lire le dépôt.
NOTE_NOM = "LISEZ-MOI.txt"
NOTE_DOSSIER = (
    "Dépose ici tes fichiers de modèle (.pt ou .onnx).\n"
    "\n"
    "Ils apparaîtront dans la liste « Modèle » des réglages. Le bouton\n"
    "« Parcourir… » de ces réglages prend aussi un fichier rangé ailleurs\n"
    "sur l'ordinateur, sans le déplacer.\n"
    "\n"
    "Ce dossier est remplacé si tu extrais une nouvelle version du logiciel\n"
    "dans un dossier neuf. Pour un modèle personnel, préfère :\n"
    "%LOCALAPPDATA%\\CompteurManifestation\\modeles — il survit aux mises à\n"
    "jour et le logiciel le balaie aussi.\n"
)

#: Extension acceptée, alignée sur `compteur.detecteur.FORMATS_MODELES`.
SUFFIXES = (".pt", ".onnx")


def modeles_trouves(dossier: pathlib.Path = RACINE) -> list[pathlib.Path]:
    """Poids présents à la racine du dépôt, triés par taille décroissante.

    Trier par taille n'est pas cosmétique : `nano.pt` (6 Mo) est le seul
    modèle assez léger pour être ouvert sur une machine sans GPU rapide, et
    l'utilisateur doit le voir en premier.
    """
    trouves = [
        p
        for p in dossier.iterdir()
        if p.is_file() and p.suffix.lower() in SUFFIXES
    ]
    return sorted(trouves, key=lambda p: p.stat().st_size)


def copier(
    sources: list[pathlib.Path],
    dest: pathlib.Path,
    ecraser: bool = True,
) -> tuple[list[pathlib.Path], list[pathlib.Path]]:
    """Copie ``sources`` dans ``dest``. Retourne (copiés, ignorés)."""
    dest.mkdir(parents=True, exist_ok=True)
    copies: list[pathlib.Path] = []
    ignores: list[pathlib.Path] = []
    for src in sources:
        cible = dest / src.name
        if cible.exists() and not ecraser:
            ignores.append(cible)
            continue
        shutil.copy2(src, cible)
        copies.append(cible)
    return copies, ignores


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    p.add_argument(
        "--dest",
        default=None,
        help="dossier cible (défaut : le premier dossier de build qui existe)",
    )
    p.add_argument(
        "--propre",
        action="store_true",
        help="ne recopie que les poids manquants",
    )
    args = p.parse_args(argv)

    # La note n'est écrite QUE dans le dossier de l'installation : un `--dest`
    # explicite pointe souvent vers un dossier de l'opérateur, où déposer un
    # fichier de plus serait une intrusion.
    deposer_note = False
    if args.dest:
        # `--dest` désigne le dossier EXACT (aucun sous-dossier ajouté) : qui
        # le donne sait où il veut ses fichiers.
        dest = pathlib.Path(args.dest)
        if not dest.is_dir():
            print(f"ERREUR : {dest} n'existe pas.", file=sys.stderr)
            return 1
    else:
        build = next((b for b in BUILDS_CIBLES if b.is_dir()), None)
        if build is None:
            print(
                f"ERREUR : aucun dossier de build trouvé ({BUILDS_CIBLES[0]}).\n"
                "Construis d'abord l'exécutable :\n"
                "    python -m PyInstaller --clean --workpath build/v2 crowd-counter-v2.spec",
                file=sys.stderr,
            )
            return 1
        # Le sous-dossier `modeles/` est créé par `copier` : c'est la première
        # copie des poids qui l'installe, pas le build.
        dest = build / DOSSIER_MODELES_NOM
        deposer_note = True

    trouves = modeles_trouves()
    if not trouves:
        print(
            "Aucun poids .pt / .onnx à la racine du dépôt.\n"
            "Dépose-les à côté de main.py, puis relance ce script.\n"
            f"Dossier attendu : {RACINE}",
            file=sys.stderr,
        )
        return 1

    copies, ignores = copier(trouves, dest, ecraser=not args.propre)

    for c in copies:
        print(f"copié  {c.name}  ({c.stat().st_size / 1024 / 1024:.1f} Mo)")
    for i in ignores:
        print(f"déjà là {i.name} (inchangé)")
    if deposer_note:
        (dest / NOTE_NOM).write_text(NOTE_DOSSIER, encoding="utf-8")
        print(f"note   {NOTE_NOM}")
    print(f"\n{dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())