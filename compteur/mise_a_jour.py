"""Mise à jour automatique de l'application (niveau 2 : télécharger, installer, relancer).

Conçu pour une distribution ZIP PORTABLE : l'application ne peut PAS se
remplacer pendant qu'elle tourne (son exe et ses DLL sont ouverts). La
séquence est donc étalée dans le temps, et chaque maillon a son repli :

1. **Chercher** la dernière release sur l'API GitHub — jamais bloquant, en
   tâche de fond, `None` au moindre souci réseau ;
2. **Télécharger** le zip DANS le dossier parent de l'installation (même
   volume que l'app : les renommages de l'échange restent atomiques), avec
   reprise sur interruption (requête `Range`) ;
3. **Vérifier** le sha256 publié en asset de la release. SANS cet asset, pas
   d'installation : repli niveau 1 (ouvrir la page de release). Un zip
   corrompu ne doit jamais toucher une installation qui marche ;
4. **Préparer** un dossier d'étape `.maj-<version>` : extraction vérifiée
   (pas de chemin absolu ni de `..` dans l'archive), puis MIGRATION des
   données de l'utilisateur — `config/local_*.json` (thème, mémoire de
   dossier), `config/profils/*.json`, et tout `.pt` déposé dans `modeles/`
   qui ne serait pas déjà dans la nouvelle version. Sans ça, une mise à
   jour effacerait le travail de l'opérateur ;
5. **Échanger** au moyen d'un script `.bat` généré, lancé détaché juste
   avant la sortie de l'app : il attend la fin de l'exe, RENOMME
   l'installation courante en `<nom>.ancienne` (sauvegarde, PAS une
   suppression), met la nouvelle à sa place, la relance. Le dossier
   ancien n'est supprimé que par la nouvelle app AU LANCEMENT SUIVANT
   (`nettoyer_anciennes`) — s'il est encore là, c'est que la nouvelle
   version n'a jamais réussi à démarrer, et il contient l'installation
   qui marchait.

Ce module appartient au moteur (`compteur/`) : pas de Qt, tout est
testable sans écran. Les détails Windows (chemins, `tasklist`, drapeaux de
processus détaché) restent derrière des fonctions que les tests
instrumentent sans exécuter quoi que ce soit.
"""

from __future__ import annotations

import hashlib
import json
import logging
import pathlib
import shutil
import subprocess
import sys
import urllib.request
import zipfile

from .telechargement import Annulation, ErreurDisque, ErreurReseau

log = logging.getLogger(__name__)

#: Dépôt public d'origine. L'API `releases/latest` renvoie la dernière
#: publication non-brouillon ; un tag sans asset zip y est ignoré.
URL_API_RELEASE = "https://api.github.com/repos/galaxiel/crowd-counter/releases/latest"

#: Débit de lecture du téléchargement (1 MiB par aller réseau).
TAILLE_BLOC = 1024 * 1024

#: Espace disque réclamé en plus du zip : l'extraction prend à peu près la
#: taille du zip (marge ×1,2), et le zip lui-même doit tenir.
MARGE_EXTRACTION = 1.2

EXE_NOM = "CompteurManifestation.exe"


# -- Versions ------------------------------------------------------------


def analyser_version(texte: str) -> tuple[int, ...] | None:
    """`"v2.6.0"` → `(2, 6, 0)`. `None` si la forme n'est pas X.Y.Z.

    Les tags GitHub portent un `v` initial ; les comparaisons ne doivent pas
    en dépendre. Toute composante non numérique invalide la version entière
    plutôt que d'être ignorée : comparer « 2.6.0-rc1 » comme 2.6.0 ferait
    proposer une pré-release comme si elle était finie.
    """
    corps = texte.strip().lstrip("vV")
    parties = corps.split(".")
    if not 1 <= len(parties) <= 4:
        return None
    try:
        return tuple(int(p) for p in parties)
    except ValueError:
        return None


def comparer_versions(a: str, b: str) -> int:
    """Compare deux numéros de version. Négatif si a < b, 0 si égaux.

    Les composantes manquantes valent zéro : `2.6` == `2.6.0`. Une version
    non analysable trie APRES toute version valide (elle est considérée
    plus récente et sera proposée — un numéro incompréhensible côté serveur
    ne doit pas masquer une mise à jour réelle).
    """
    va, vb = analyser_version(a), analyser_version(b)
    if va is None and vb is None:
        return 0
    if va is None:
        return -1
    if vb is None:
        return 1
    longueur = max(len(va), len(vb))
    va = va + (0,) * (longueur - len(va))
    vb = vb + (0,) * (longueur - len(vb))
    return (va > vb) - (va < vb)


# -- Recherche de release -------------------------------------------------


def _reseau(url: str, timeout: int = 10) -> bytes:
    """Corps d'une URL, avec l'en-tête User-Agent exigé par l'API GitHub."""
    requete = urllib.request.Request(url, headers={"User-Agent": "crowd-counter"})
    with urllib.request.urlopen(requete, timeout=timeout) as reponse:
        return reponse.read()


def chercher_release(
    version_courante: str, fetch=_reseau, url: str = URL_API_RELEASE
) -> dict | None:
    """Dernière release publiée, ou ``None`` (réseau, JSON, rien de neuf).

    Retour : `{"version", "url_zip", "taille_zip", "sha256", "url_page"}` —
    `sha256` vaut `None` si l'asset `.sha256` n'existe pas : l'appelant doit
    ALORS se contenter du niveau 1 (ouvrir la page), jamais installer sans
    vérification. Toute erreur réseau rend `None` sans lever : la recherche
    est un confort du démarrage, jamais une condition.
    """
    try:
        donnees = json.loads(fetch(url).decode("utf-8"))
    except (OSError, ValueError) as exc:
        log.info("recherche de mise à jour impossible : %s", exc)
        return None
    tag = str(donnees.get("tag_name", ""))
    if analyser_version(tag) is None:
        return None
    if comparer_versions(tag, version_courante) <= 0:
        return None
    assets = donnees.get("assets") or []
    url_zip = ""
    taille_zip = 0
    sha = ""
    for asset in assets:
        nom = str(asset.get("name", ""))
        if nom.endswith(".zip") and not nom.endswith(".zip.sha256"):
            url_zip = str(asset.get("browser_download_url", ""))
            taille_zip = int(asset.get("size", 0))
        elif nom.endswith(".zip.sha256"):
            sha = str(asset.get("browser_download_url", ""))
    if not url_zip:
        return None
    sha256 = None
    if sha:
        try:
            sha256 = fetch(sha).decode("utf-8").split()[0].lower()
        except (OSError, ValueError, IndexError):
            sha256 = None
    return {
        "version": tag.lstrip("vV"),
        "url_zip": url_zip,
        "taille_zip": taille_zip,
        "sha256": sha256,
        "url_page": str(donnees.get("html_url", "")),
    }


# -- Téléchargement -------------------------------------------------------


def taille_libre(dossier: pathlib.Path) -> int:
    """Octets libres sur le volume qui porte ``dossier`` (0 si introuvable)."""
    try:
        return shutil.disk_usage(dossier).free
    except OSError:
        return 0


def verifier_disque(dossier: pathlib.Path, taille_zip: int) -> None:
    """Lève `ErreurDisque` si le volume ne peut pas porter zip + extraction."""
    requis = int(taille_zip * (1 + MARGE_EXTRACTION))
    libre = taille_libre(dossier)
    if libre and libre < requis:
        raise ErreurDisque(
            f"{requis // (1024 * 1024)} Mo nécessaires, {libre // (1024 * 1024)} Mo libres"
        )


def telecharger(
    url: str,
    destination: pathlib.Path,
    taille_attendue: int = 0,
    progression=None,
    annule=None,
    ouvrir=None,
) -> pathlib.Path:
    """Télécharge ``url`` vers ``destination``, avec reprise sur interruption.

    Les octets partent dans ``destination.part`` ; un fichier partiel existe
    déjà ? La reprise repart à l'octet près via une requête `Range` — c'est
    la même promesse que le téléchargement de torch (un téléchargement de
    224 Mo coupé à 90 % ne repart PAS de zéro). Le `.part` est renommé à la
    fin seulement : un `destination` complet prouve un téléchargement fini.
    `progression(faits, total)` et `annule()` sont optionnels ; lever
    `Annulation` entre deux blocs, jamais au milieu d'un octet écrit.
    """
    if ouvrir is None:
        ouvrir = _ouvrir_reseau
    destination.parent.mkdir(parents=True, exist_ok=True)
    partiel = destination.with_suffix(destination.suffix + ".part")
    deja = partiel.stat().st_size if partiel.exists() else 0
    en_tetes = {"User-Agent": "crowd-counter"}
    if deja:
        en_tetes["Range"] = f"bytes={deja}-"
    try:
        reponse = ouvrir(url, en_tetes)
        code = getattr(reponse, "status", None)
        if code is None and hasattr(reponse, "getcode"):
            code = reponse.getcode()
        if deja and code not in (None, 206):
            # Le serveur a ignoré la reprise (réponse complète) : repartir de
            # zéro, sinon on collerait TOUT le contenu derrière un partiel.
            with open(partiel, "wb"):
                pass
            deja = 0
        with reponse, open(partiel, "ab") as sortie:
            total = taille_attendue or _taille_reponse(reponse) + deja
            faits = deja
            while True:
                if annule is not None and annule():
                    raise Annulation("téléchargement de mise à jour annulé")
                bloc = reponse.read(TAILLE_BLOC)
                if not bloc:
                    break
                sortie.write(bloc)
                faits += len(bloc)
                if progression is not None:
                    progression(faits, total or faits)
    except OSError as exc:
        raise ErreurReseau(f"téléchargement interrompu : {exc}") from exc
    if taille_attendue and partiel.stat().st_size != taille_attendue:
        recus = partiel.stat().st_size
        partiel.unlink(missing_ok=True)
        raise ErreurReseau(f"taille reçue {recus} ≠ attendue {taille_attendue}")
    shutil.move(partiel, destination)
    return destination


def _ouvrir_reseau(url: str, en_tetes: dict[str, str]):
    requete = urllib.request.Request(url, headers=en_tetes)
    return urllib.request.urlopen(requete, timeout=30)


def _taille_reponse(reponse) -> int:
    try:
        return int(reponse.headers.get("Content-Length", 0))
    except (TypeError, ValueError):
        return 0


def sha256_fichier(chemin: pathlib.Path) -> str:
    """Empreinte sha256 d'un fichier, par blocs (le zip fait 224 Mo)."""
    h = hashlib.sha256()
    with open(chemin, "rb") as f:
        for bloc in iter(lambda: f.read(TAILLE_BLOC), b""):
            h.update(bloc)
    return h.hexdigest()


# -- Préparation de l'échange ---------------------------------------------


def dossier_application() -> pathlib.Path | None:
    """Dossier de l'application, ou ``None`` hors exécutable gelé.

    En développement (`python main.py`), il n'y a rien à mettre à jour —
    l'updater doit rester silencieux plutôt que proposer d'écraser le dépôt.
    """
    if not getattr(sys, "frozen", False):
        return None
    return pathlib.Path(sys.executable).resolve().parent


def _membre_sur(extraction: pathlib.Path, membre: zipfile.ZipInfo) -> bool:
    """Faux si un membre d'archive tente de sortir du dossier d'extraction."""
    cible = (extraction / membre.filename).resolve()
    return str(cible).startswith(str(extraction.resolve()))


def extraire(zip_path: pathlib.Path, dossier: pathlib.Path, progression=None) -> None:
    """Extrait une archive en refusant tout membre qui sortirait du dossier.

    Un zip de release vient du réseau : ses noms de membres ne sont pas
    dignes de confiance (zip-slip). Les entrées acceptées ne sont que des
    fichiers et dossiers réguliers.
    """
    dossier.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as archive:
        membres = archive.infolist()
        for i, membre in enumerate(membres):
            if membre.is_dir():
                continue
            if not _membre_sur(dossier, membre):
                raise ErreurReseau(
                    f"archive suspecte : entrée hors dossier ({membre.filename})"
                )
            archive.extract(membre, dossier)
            if progression is not None:
                progression(i + 1, len(membres))


def migrer_donnees(ancienne: pathlib.Path, nouvelle: pathlib.Path) -> list[str]:
    """Recopie les données de l'opérateur de l'ancienne installation vers la nouvelle.

    Trois familles, dans cet ordre d'importance :

    - `config/local_*.json` — préférences du poste (thème, dernier dossier) ;
    - `config/profils/*.json` — profils de réglages nommés ;
    - `modeles/*.pt` — les poids que l'opérateur a DÉPOSÉS et qui ne sont
      pas déjà dans la nouvelle version (les poids livrés, eux, viennent de
      la release et ne doivent pas écraser les siens plus récents).

    Retourne la liste des fichiers recopiés (pour le journal). Tout est
    best-effort : un fichier illisible est loggé et sauté, jamais fatal.
    """
    copies: list[str] = []
    # Préférences du poste, à l'identique.
    for motif in ("local_*.json",):
        for source in (ancienne / "config").glob(motif):
            cible = nouvelle / "config" / source.name
            cible.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(source, cible)
                copies.append(str(source.relative_to(ancienne)))
            except OSError as exc:
                log.warning("migration impossible (%s) : %s", source, exc)
    # Profils nommés.
    profils_anciens = ancienne / "config" / "profils"
    if profils_anciens.is_dir():
        for source in profils_anciens.glob("*.json"):
            cible = nouvelle / "config" / "profils" / source.name
            cible.parent.mkdir(parents=True, exist_ok=True)
            if not cible.exists():
                try:
                    shutil.copy2(source, cible)
                    copies.append(str(source.relative_to(ancienne)))
                except OSError as exc:
                    log.warning("migration impossible (%s) : %s", source, exc)
    # Poids déposés par l'opérateur (non livrés par la nouvelle release).
    modeles_anciens = ancienne / "modeles"
    if modeles_anciens.is_dir():
        for source in modeles_anciens.glob("*.pt"):
            cible = nouvelle / "modeles" / source.name
            if not cible.exists():
                try:
                    shutil.copy2(source, cible)
                    copies.append(str(source.relative_to(ancienne)))
                except OSError as exc:
                    log.warning("migration impossible (%s) : %s", source, exc)
    return copies


def texte_script_echange() -> str:
    """Le `.bat` qui échange l'installation APRES la sortie de l'app.

    Généré avec des chemins RELATIFS au dossier parent (`pushd "%~dp0.."`),
    donc indifférent au nom réel du dossier d'installation (que
    l'opérateur a pu renommer) et à son emplacement (Bureau, clé USB).
    **Piège corrigé le 04/11 (réel)** : le chemin de la nouvelle version ne
    doit PAS repartir du nom de l'étape (`%~dp0.maj-X`), car `%~dp0` EST
    déjà le dossier d'étape — le doubler donne un chemin inexistant, le
    `move` échoue en silence (`>nul`) et le repli remet l'ancienne version
    sans jamais relancer. La forme correcte est `%~dp0CompteurManifestation`
    : le bat vit DANS l'étape, l'application extraite est juste à côté de
    lui. Séquence : attendre la sortie de l'exe, RENOMMER l'ancienne
    installation (sauvegarde — jamais supprimée ici), mettre la nouvelle à
    sa place, vérifier que l'exe y est, la relancer. Si un `move` échoue ou
    que l'exe manque : RETOUR ARRIÈRE immédiat, l'installation d'origine
    est intacte. Le nettoyage des dossiers `.maj-*` et `*.ancienne`
    restants appartient à la nouvelle app (`nettoyer_anciennes`), qui seul
    sait que la nouvelle version a démarré. Les commentaires du bat sont
    en ASCII pur : il est écrit en cp1252 et un accent mal décodé ne doit
    jamais faire douter d'une ligne de commande.
    """
    return f"""@echo off
rem Echange de l'installation - genere par CompteurManifestation.
rem Etapes : attendre la sortie de l'exe, renommer l'ancienne installation
rem (sauvegarde), mettre la nouvelle a sa place, la relancer.
setlocal
pushd "%~dp0.."
:attendre
tasklist /FI "IMAGENAME eq {EXE_NOM}" 2>nul | find /I "{EXE_NOM}" >nul && (timeout /t 1 /nobreak >nul & goto attendre)
move /Y "CompteurManifestation" "CompteurManifestation.ancienne" >nul
if errorlevel 1 goto echec
move /Y "%~dp0CompteurManifestation" "CompteurManifestation" >nul
if errorlevel 1 goto retour
if not exist "CompteurManifestation\\{EXE_NOM}" goto retour
start "" "CompteurManifestation\\{EXE_NOM}"
popd
exit /b 0
:retour
move /Y "CompteurManifestation.ancienne" "CompteurManifestation" >nul
:echec
popd
exit /b 1
"""


def preparer_staging(
    zip_path: pathlib.Path,
    dossier_app: pathlib.Path,
    version: str,
    progression=None,
) -> pathlib.Path:
    """Extrait, migre les données, écrit le script d'échange. Renvoie le `.bat`.

    Le dossier d'étape vit dans le PARENT de l'installation : même volume
    obligatoire pour que les `move` du script soient des renommages (pas des
    copies de 224 Mo). Un étage resté d'une tentative précédente est
    reparti de zéro.
    """
    parent = dossier_app.parent
    staging = parent / f".maj-{version}"
    if staging.exists():
        shutil.rmtree(staging, ignore_errors=True)
    extraire(zip_path, staging, progression)
    nouveau = staging / dossier_app.name
    if not (nouveau / EXE_NOM).exists():
        raise ErreurReseau(
            f"archive inattendue : {EXE_NOM} absent de la nouvelle version"
        )
    migrer_donnees(dossier_app, nouveau)
    chemin_bat = staging / "mise-a-jour.bat"
    chemin_bat.write_text(texte_script_echange(), encoding="cp1252")
    return chemin_bat


def lancer_echange(chemin_bat: pathlib.Path) -> None:
    """Lance le script d'échange DÉTACHÉ, puis c'est lui qui prend la main.

    Détaché : l'app qui se ferme ne doit pas tuer le script. Sans fenêtre
    console — l'opérateur ne doit rien voir s'ouvrir.
    """
    drapeaux = 0
    if sys.platform == "win32":
        DETACHED_PROCESS = 0x00000008
        CREATE_NO_WINDOW = 0x08000000
        drapeaux = DETACHED_PROCESS | CREATE_NO_WINDOW
    subprocess.Popen(
        ["cmd", "/c", str(chemin_bat)],
        cwd=str(chemin_bat.parent),
        creationflags=drapeaux,
        close_fds=True,
    )


def nettoyer_anciennes(dossier_parent: pathlib.Path) -> list[str]:
    """Efface les restes d'un échange précédent. Appelé au démarrage de l'app.

    Deux familles : les dossiers d'étape `.maj-*` (tentative interrompue)
    et les sauvegardes `*.ancienne` — leur présence au démarrage de la
    NOUVELLE version prouve que celle-ci démarre, donc que la sauvegarde a
    rempli son rôle. Best-effort : un dossier verrouillé (antivirus,
    explorateur) reste en place et sera retenté au prochain démarrage.
    """
    supprimes: list[str] = []
    if not dossier_parent.is_dir():
        return supprimes
    for element in dossier_parent.iterdir():
        nom = element.name
        if not nom.startswith(".maj-") and not nom.endswith(".ancienne"):
            continue
        try:
            if element.is_dir():
                shutil.rmtree(element, ignore_errors=True)
            else:
                element.unlink()
        except OSError as exc:
            log.info("nettoyage impossible (%s) : %s", nom, exc)
            continue
        if not element.exists():
            supprimes.append(nom)
    return supprimes
