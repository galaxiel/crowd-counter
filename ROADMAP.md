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

## v2.6 — EN COURS (décision « on fait tout », 30/10/2026)

Chaque item : ce qu'il apporte, ce qu'il coûte, et la preuve qui décidera.
Effort : `S` < 1 h, `M` 1-4 h, `L` une journée ou plus.

| Item | État au 30/10 | Suite |
|---|---|---|
| 1. Banc de vérité terrain | outillage committé, vidéo lente produite, gabarit versionné | **annotation humaine** puis `comparer` |
| 2. CI GitHub Actions | **prouvé** : 1er run rouge (teardown Qt), correctif, 2 runs verts | surveiller les prochains pushes |
| 3. opencv-headless | bascule faite + mesurée : gain réel **0,5 Mo** (plus de Qt dans la wheel 5.x) | bascule maintenue (bon paquet), pas pour le poids |
| 4. imgsz sur la bande | **mesuré** (32 à 640/704, 36 à 1280) | décision après vérité terrain |
| 5. Double sens | **rejeté** par l'opérateur | — |
| 6. Reprise au scrub | gardée, sans mémoire | à rouvrir sur besoin réel |
| 7. Pipeline décodage ‖ GPU | au chaud | seulement si profil > 25 % décodage |

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

**État (30/10).** Outillage committé (`1e6d8e0`) : `tools/verite_terrain.py`
(`extraire` produit une vidéo lente ×3 avec frame number gravé, ligne et
bande ; `comparer` tourne le moteur en résolution automatique et apparie les
franchissements humains aux événements moteur, tolérance 30 frames,
appariement aux couples les plus serrés d'abord), 23 tests dédiés verts,
`mesurer_reference.mesurer` étendu (`--imgsz`, retourne les frames
d'événements). Vidéo lente de 90 s produite :
`verite_terrain/segment_3600-4500_lent.mp4`.

**Reste — travail humain, non automatisable.** Regarder la vidéo lente, noter
une frame par franchissement (le numéro gravé en jaune), remplir
`verite_terrain/segment_3600-4500.txt`, puis :

```bash
python tools/verite_terrain.py comparer verite_terrain/segment_3600-4500.txt
```

C'est ce résultat qui tranchera l'item 4 (32 ou 36 : lequel est juste ?).

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

**État (30/10).** Workflow committé (`dc19866`) :
`.github/workflows/tests.yml` — Ubuntu, Python 3.11, torch CPU (index
dédié, même index pour torchvision), cache pip clé sur `requirements.txt`,
`QT_QPA_PLATFORM=offscreen` avec les libs système, purge opencv identique à
`docs/BUILDING.md`, `pytest -m "not slow"`. **Preuve faite : premier push
vert… après un rouge.** Le tout premier run a échoué (exit 139) alors que
les 553 tests étaient tous passés : un segfault de **teardown PySide6** à
la fermeture du processus (Linux offscreen, « shared QObject was deleted
directly ») — le GC détruit les objets Qt dans un ordre arbitraire à la
sortie de l'interpréteur. Correctif racine (`7a29bb5`) : fixture de
session dans `tests/conftest.py` qui ferme et supprime les top-level
widgets et vide la file `DeferredDelete` **pendant** la session. Deux
exécutions vertes consécutives ensuite (`7a29bb5`, `6c230df`).

### 3. `opencv-python` → `opencv-python-headless` — effort `S`

**Ce que c'est.** Aucun composant GUI d'OpenCV n'est utilisé (vérifié : pas de
`imshow`, `namedWindow`, `waitKey` — seul `VideoWriter`, inclus dans le build
headless). Le build embarqué gagnerait la place des DLL d'affichage Qt
d'OpenCV, qui font double emploi avec PySide6.

**État (30/10).** Bascule faite (`db43c4a`) dans `requirements.txt`,
`installer.py`, `docs/BUILDING.md` (étape 3bis) et la CI. Le piège central :
`ultralytics` déclare `opencv-python` en dépendance (vérifié dans son
METADATA) — pip installe la variante complète **en plus** de la headless, et
les deux paquets écrivent dans le même dossier `cv2/`. D'où la séquence
déterministe, écrite à trois endroits : installer tout, purger les DEUX
paquets, réinstaller la headless seule.

**Mesure faite (`fb4e506`+reconstruction, 30/10) — et elle réfute l'estimation
initiale.** Le gain n'est PAS de ~80 Mo mais de **~0,5 Mo** : `dist` passe de
293,7 Mo à 293,2 Mo (sans les modèles), `cv2` embarquée de 111,8 à 111,3 Mo.
La raison : l'estimation venait d'OpenCV **4.x**, dont la wheel Windows
embarquait ses DLL Qt. OpenCV **5.0.0.93** ne les embarque plus (wheel
complète 44,0 Mo vs headless 43,8 Mo ; la licence du paquet ne mentionne Qt
que pour les wheels **Linux**). La bascule est maintenue parce que c'est le
bon paquet pour un logiciel qui n'affiche rien avec OpenCV — pas à cause du
poids.

### 4. `imgsz` calé sur la bande rognée — effort `M`

**L'analyse.** `detecter()` rogne la bande (250 px avant / 250 après la ligne,
soit 500×720 sur la vidéo de référence) **puis** passe la bande au modèle avec
`imgsz=1280` — la valeur calculée pour l'image **entière**
(`taille_entree_automatique` plafonne à 1280). Ultralytics redimensionne donc
une bande de 500 px de large à 1280 : un agrandissement ×2,56 qui n'invente
aucun détail mais coûte du calcul GPU sur chaque frame.

**Mesures (30/10, 3 passes répétables, frames 3600-4500, `sens=-1`,
`tetes-medium.pt`, RTX 4070 SUPER) :**

| imgsz | Compté | Débit |
|---|---|---|
| 640 (réglage du harnais) | 32 | 45-59 i/s |
| 704 (taille réelle de la bande) | 32 | 51-61 i/s |
| **1280 (réglage auto de l'app)** | **36** | **30-33 i/s** |

**Découverte majeure.** Le harnais `mesurer_reference` mesure à `imgsz=640`
(fixé en dur dans sa config) alors que l'application, en résolution
automatique, analyse cette vidéo à **1280**. Les deux ne donnent PAS le même
compte (32 contre 36) : le « 32 personnes » de référence n'est pas ce que voit
un utilisateur du logiciel. Savoir si le 1280 détecte 4 personnes de plus ou
bien 4 faux comptes ne se tranche qu'avec le banc de vérité terrain (item 1).

**Décision.** Différée à l'item 1 : sans vérité terrain, réduire `imgsz`
gagnerait du débit mais pourrait perdre de vrais manifestants — ou en
retirer de faux, impossible à le dire avec un seul total.

### 5. Double sens en une passe — effort `L` — **REJETÉ (30/10)**

**Ce que c'est.** Le moteur compte aujourd'hui dans **un** sens
(`config.sens`). Pour les flux bidirectionnels (départs et retours sur la même
voie), l'opérateur doit lancer deux analyses séparées. Le moteur pourrait
franchir dans les deux sens et exposer deux totaux.

**Décision de l'opérateur (30/10) : rejeté.** Les personnes qui vont dans
l'autre sens sont des **passants**, pas des manifestants — ne pas les compter
est le comportement voulu. Le fonctionnement actuel (`sens=-1` ne compte que
le sens du cortège, l'autre est ignoré par conception) est déjà exactement
celui demandé. Ne pas rouvrir sans changement de besoin réel.

### 6. Reprise au scrub / recalcul par segment — effort `L` — **idée conservée, sans mémoire**

**Ce que c'est.** Relancer l'analyse à un point de la vidéo (ou sur un segment
seul) après un changement de réglage, sans repasser par le début.

**Ce qui coûte.** Un cache des détections/trajectoires par segment, une UI de
reprise, et un point délicat : le tracker a une mémoire ; reprendre à mi-parcours
sans ses états antérieurs produirait des comptes différents de l'analyse en
continu. Soit on rejoue les états, soit on documente l'écart.

**Décision de l'opérateur (30/10).** L'idée est conservée **sans mémoire du
tracker** : le cas d'usage visé est d'analyser une fenêtre calme de la vidéo
(où les personnes sont plus espacées, les erreurs moindres, le comptage
humain plus simple) pour **comparer à un comptage à la main**. Une reprise à
froid ne doit donc PAS prétendre reproduire le total d'une analyse continue —
elle sert de banc de comparaison, pas de raccourci de calcul. La comparaison
moteur vs humain est déjà fournie par l'item 1 (`tools/verite_terrain.py
comparer`, qui accepte un segment libre et une tolérance) : rouvrir l'item 6
uniquement si un vrai besoin d'analyse interactive apparaît.

### 7. Pipeline décodage ‖ inférence — effort `M-L` — **au chaud**

**Ce que c'est.** Dans le worker d'analyse, le décodage (cv2) et l'inférence
(GPU) s'exécutent en séquence. Un couple producteur/consommateur masquerait
la latence de décodage derrière le calcul GPU.

**Pourquoi mesurer d'abord.** Si le décodage ne pèse que 10 % du temps total,
le gain plafonne à 10 % — et le thread supplémentaire ajoute un plan de
concurrence (annulation, arrêt, exceptions) sur lequel la v2.5 a déjà écrit
beaucoup de précautions.

**Décision de l'opérateur (30/10).** L'idée reste dans la roadmap. À ouvrir
uniquement si un profil honnête du temps total (part décodage / inférence /
tracker) sur le segment de référence montre un décodage **> 25 %**. Sinon :
ne pas commencer.

## Hors périmètre assumé

ByteTrack, bande native, saut de frame, FP16, densimétrie : pistes mesurées et
mortes, liste dans `AGENTS.md`. Ne pas les rouvrir sans donnée nouvelle.
