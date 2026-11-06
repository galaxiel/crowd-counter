"""Installation de l'environnement de développement (v3).

La v2 avait ici une machine à choisir des wheels torch (index CUDA, purge
opencv après ultralytics...) : TOUTE cette machinerie a disparu avec le
moteur torch. La v3 s'installe en deux lignes bêtes — un `pip install` des
requirements, sans aucun choix d'index, puisque rien ne dépend plus du
modèle de carte graphique :

    python -m pip install -r requirements-dev.txt

Ce script existe encore pour deux raisons : il installe DANS L'ORDRE
décrit par docs/BUILDING.md, et il est idempotent (relançable sans
danger). Les tests `slow` de la v2 qui le lançaient en dry-run ont été
retirés avec la machinerie torch.
"""

from __future__ import annotations

import subprocess
import sys

ETAPES = (
    ("Dépendances d'exécution et de construction", ["-r", "requirements-dev.txt"]),
)


def main() -> int:
    for titre, args in ETAPES:
        print(f"== {titre}")
        resultat = subprocess.run(
            [sys.executable, "-m", "pip", "install", *args],
        )
        if resultat.returncode != 0:
            print(f"ÉCHEC : {titre}", file=sys.stderr)
            return resultat.returncode
    print("\nEnvironnement prêt. Interpréteur de référence : Python 3.11.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
