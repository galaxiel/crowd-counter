# Roadmap

État des lots livrés et candidats à venir. `AGENTS.md` reste la référence pour
les conventions de travail, l'interpréteur et les pistes mortes — ce fichier ne
les répète pas, il les complète.

Règle du dépôt : **un candidat n'est retenu qu'après mesure ou validation
explicite**, jamais parce qu'il « a l'air bon ». Chaque item ci-dessous dit
donc comment le trancher.

## v2.5 — LIVRÉE (30/10/2026)

Dix commits locaux (`0ade293` → `37a1382`), puis deux correctifs le jour même.
Suite complète : **592 tests verts, 0 échec** (les 62 tests `slow` compris).

| Commit  | Apport |
|---|---|
| `0ade293` | verrou anti-rebond du lancement d'analyse |
| `9254c08` | rapport `tracks_presents_*` (trajectoires observées, diagnostics) |
| `5cc7710` | suppression des doublons de tests de téléchargement |
| `9b6f4af` | nettoyage général (code mort, commentaires périmés) |
| `5ccca6c` | raccourcis clavier (Esc arrête l'analyse — Qt sérialise `"Esc"`) |
| `e6b617f` | retour visible des profils de détection appliqués |
| `ee3a92d` | validation du modèle avant d'accepter une vidéo |
| `c3a36f0` | mémoire du dernier dossier vidéo ouvert |
| `157cb79` | débit (i/s) et temps restant sous la barre de progression |
| `37a1382` | **chargement du modèle en arrière-plan** — la fenêtre ne gèle plus |

Correctifs du 30/10 :

- **encodage des sous-processus de test** — les cinq tests `slow` de
  `tests/test_peripherique.py` échouaient sur une machine francophone : le
  sous-processus écrit ses accents (« ÉCHEC ») via la console Windows en
  CP1252, le parent décodait en UTF-8 strict. `PYTHONIOENCODING=utf-8` chez
  l'enfant (helper `_dry_run`) — le producteur est mis en cause, pas le
  décodeur.
- **purge des `__pycache__` périmés** — 31 `.pyc` portaient encore les chemins
  de l'ancien nom de dossier (`crowd-counter-v2`), ce qui affichait de faux
  chemins dans les tracebacks.

## v2.6 — CANDIDATS (rien n'est commencé)

Chaque item : ce qu'il apporte, ce qu'il coûte, et la preuve qui décidera.
Effort : `S` < 1 h, `M` 1-4 h, `L` une journée ou plus.

### 1. Banc de vérité terrain annoté — effort `M`

**Ce que c'est.** Annoter à la main les franchissements du segment de
référence (frames 3600-4500) et versionner le résultat
(`tests/verite_terrain/` + outil de comparaison).

**Pourquoi c'est le premier.** C'est le manque signalé depuis le début dans
`ETAT_PROJET.md` (« le seul qui manque ») : aujourd'hui toute mesure se
résume à un total agrégé (« 32 sur le segment »). Un total ne dit pas si le
logiciel rate 3 personnes et en compte 3 autres par-dessus — les erreurs
compensées passent invisibles. Avec un banc annoté, chaque candidat
d'optimisation de cette liste se tranche sur un écart en personnes, pas sur
une impression.

**Preuve attendue.** Un fichier de vérité terrain versionné et un écart
mesuré entre le logiciel et la main levée sur le segment de référence.

### 2. Intégration continue (GitHub Actions) — effort `S`

**Ce que c'est.** Aucun workflow n'existe (vérifié : rien sous `.github/`).
Un job public sur `ubuntu-latest`, Python 3.11, dépendances CPU, qui lance
`pytest -m "not slow"` à chaque push.

**Détails qui décident.**
- Qt tourne sans serveur d'affichage via `QT_QPA_PLATFORM=offscreen` ;
  `cv2` et `torch` CPU suffisent (la suite ne fait aucune inférence).
- `torch` CPU pèse ~800 Mo : un `actions/cache` sur le pip cache est
  nécessaire, sinon chaque run retélécharge.
- Les tests `slow` (sous-processus `installer.py`) détectent le matériel de la
  machine : ils restent hors CI.

**Preuve attendue.** Un workflow vert sur un push, et un push volontairement
cassé qui tourne en rouge.

### 3. `opencv-python` → `opencv-python-headless` — effort `S`

**Ce que c'est.** Aucun composant GUI d'OpenCV n'est utilisé (vérifié : pas de
`imshow`, `namedWindow`, `waitKey` — seul `VideoWriter`, inclus dans le build
headless). Le build embarqué gagnerait la place des DLL d'affichage Qt
d'OpenCV, qui font double emploi avec PySide6.

**Preuve attendue.** Poids du dossier `dist/` avant/après, mesuré après
reconstruction — et lancement de l'exécutable vérifié (un `.exe` qui démarre
sans fenêtre ne prouve rien, règle déjà écrite dans `AGENTS.md`).

### 4. `imgsz` calé sur la bande rognée — effort `M`

**L'analyse.** `detecter()` rogne la bande (250 px avant / 250 après la ligne,
soit 500×720 sur la vidéo de référence) **puis** passe la bande au modèle avec
`imgsz=1280` — la valeur calculée pour l'image **entière**
(`taille_entree_automatique` plafonne à 1280). Ultralytics redimensionne donc
une bande de 500 px de large à 1280 : un agrandissement ×2,56 qui n'invente
aucun détail mais coûte du calcul GPU sur chaque frame.

**Ce qu'il faudrait.** Calculer `imgsz` depuis la bande rognée, pas depuis la
source. La bande fait 720 de haut → `imgsz` ~704-736 au lieu de 1280 : moins
de pixels à inférer, donc potentiellement plus de débit.

**Pourquoi c'est un pari et pas un gain annoncé.** Réduire `imgsz` ramène les
têtes de 51-74 px à leur taille native (20-29 px) dans l'entrée du modèle —
c'est exactement ce que font varier les mesures déjà au comptoir de
`config.py` (+11 % de personnes entre 640 et 1280). La vitesse montera
peut-être, les comptes bougeront sûrement.

**Preuve attendue.** Mesure aller-retour sur le segment de référence
(frames 3600-4500, `sens=-1`, `tetes-medium.pt`) : débit et écart de comptes
contre la valeur actuelle. Si les comptes perdent plus que le temps gagné ne
vaut, la piste est classée morte dans `AGENTS.md`.

### 5. Double sens en une passe — effort `L`

**Ce que c'est.** Le moteur compte aujourd'hui dans **un** sens
(`config.sens`). Pour les flux bidirectionnels (départs et retours sur la même
voie), l'opérateur doit lancer deux analyses séparées. Le moteur pourrait
franchir dans les deux sens et exposer deux totaux.

**Ce qui coûte.** Contrat public du moteur modifié (`compteur/resultat`),
interface (deux totaux, deux flèches), rapport, récapitulatif, et une
nouvelle mesure de référence à établir.

**Décision qui appartient à l'opérateur, pas au chronomètre.** Le besoin est
réel si et seulement si les manifestations filmées ont ce flux-là. À valider
avant toute ligne de code.

### 6. Reprise au scrub / recalcul par segment — effort `L`

**Ce que c'est.** Relancer l'analyse à un point de la vidéo (ou sur un segment
seul) après un changement de réglage, sans repasser par le début.

**Ce qui coûte.** Un cache des détections/trajectoires par segment, une UI de
reprise, et un point délicat : le tracker a une mémoire ; reprendre à mi-parcours
sans ses états antérieurs produirait des comptes différents de l'analyse en
continu. Soit on rejoue les états, soit on documente l'écart.

**Preuve attendue.** Que la reprise au scrub donne EXACTEMENT le même total
qu'une analyse continue — sinon la fonction est un piège silencieux.

### 7. Pipeline décodage ‖ inférence — effort `M-L`

**Ce que c'est.** Dans le worker d'analyse, le décodage (cv2) et l'inférence
(GPU) s'exécutent en séquence. Un couple producteur/consommateur masquerait
la latence de décodage derrière le calcul GPU.

**Pourquoi mesurer d'abord.** Si le décodage ne pèse que 10 % du temps total,
le gain plafonne à 10 % — et le thread supplémentaire ajoute un plan de
concurrence (annulation, arrêt, exceptions) sur lequel la v2.5 a déjà écrit
beaucoup de précautions.

**Preuve attendue.** Un profil honnête du temps total (part décodage /
inférence / tracker) sur le segment de référence. Décodage > 25 % : ça vaut
le chantier. Sinon : ne pas commencer.

## Hors périmètre assumé

ByteTrack, bande native, saut de frame, FP16, densimétrie : pistes mesurées et
mortes, liste dans `AGENTS.md`. Ne pas les rouvrir sans donnée nouvelle.
