# Roadmap

État des lots livrés et candidats à venir. `AGENTS.md` reste la référence pour
les conventions de travail et l'interpréteur — ce fichier ne les répète pas,
il les complète.

## v2.10 — CANDIDATS (propositions opérateur, 05/11/2026)

Règle du dépôt inchangée : un candidat ne part qu'après validation explicite.

### 1. Version anglaise de l'interface — effort `L` (pas simple aujourd'hui)

**L'état des lieux (vérifié dans le code).** Toutes les chaînes visibles —
boutons, messages de statut, boîtes de dialogue, info-bulles, et surtout le
dictionnaire `AIDE` des réglages (11 textes longs, structurés, avec des
mesures) — sont en français **en dur** dans `interface/`. Qt n'est utilisé
avec aucun mécanisme de traduction (`tr()`, `QTranslator`) : il n'y a pas de
catalogue de chaînes, rien qu'à activer.

**Ce que ça coûterait.** Une passe d'extraction de toutes les chaînes vers
un catalogue (des centaines de chaînes), puis la traduction — les textes
d'aide sont longs et portent des mesures chiffrées qu'il faut traduire sans
les dénaturer. Effort honnête : une journée ou plus pour une couverture
complète ; une demi-journée pour une version partielle (boutons et messages
seulement, sans les aides) qui donnerait une interface moitié anglaise
moitié française — déconseillé.

**Quand le faire.** Quand l'interface sera stabilisée (chaque chaîne
ajoutée ensuite devrait être traduite deux fois). Si un public anglais
devient réel, commencer par `tr()` sur les nouveaux ajouts.

### 2. Bouton « À propos » avec vérification manuelle des mises à jour — effort `S`

**Ce que c'est.** Un petit dialogue « À propos » : version en cours, bouton
**« Vérifier les mises à jour »** (qui réutilise la recherche déjà codée —
elle tourne au démarrage mais n'est pas déclenchable à la main), et le lien
vers la page des releases. Le bouton vert existant reste inchangé : il
apparait quand une mise à jour EST disponible ; l'À propos répond au besoin
inverse — « ai-je la dernière version ? » sans attendre le prochain
démarrage.

**Pourquoi c'est simple.** Toute la mécanique existe
(`mise_a_jour.chercher_release`, worker `_VerificationMaj`, bouton vert) :
il s'agit d'un dialogue avec un bouton qui relance le worker existant.
Demi-heure à une heure, tests compris.

## v2.9 — L'INTERFACE AU SERVICE DU TERRAIN (05/11/2026, LIVRÉE)

Lot piloté par le retour d'usage de l'opérateur sur les vidéos de la manif du
05/11. 701 tests verts.

| Apport | Détail |
|---|---|
| Bouton « Sens : … » dans la barre | Le sens de comptage s'inverse d'un clic, libellé explicite selon la ligne, flèche verte qui pivote. L'option quitte le panneau de réglages (qui ne fait plus que PORTER la valeur — les profils continuent de l'appliquer). |
| Bouton « Recommencer » | `lancer()` rembobinait DÉJÀ la vidéo à zéro (rembobinage, compteur, récap) — l'opérateur se croyait obligé de recharger. Le bouton rend le geste explicite ; offert seulement après un premier essai. |
| Magnétisme du tracé à 5° | Une ligne tracée à moins de 5° de l'horizontale/verticale se colle exactement droite (le réglage a été essayé à 3° puis élargi à la demande de l'opérateur). Une diagonale volontaire n'est pas déplacée. |
| Zone de détection fidèle au dessin | Le rognage est un rectangle droit englobant : sur une ligne inclinée ses coins dépassaient de la bande réelle, et le voile restait droit. Désormais les détections hors de la bande oblique sont écartées ET le voile suit l'inclinaison. Zéro changement pour une ligne H/V (mesuré : rectangle = bande). |
| Aides des réglages : audit complet | 6 entrées sur 11 étaient fausses ou périmées : `seuil_confiance` (logique INVERSÉE), `fenetre_lissage` (décrivait un bug corrigé), `resolution_analyse` (se contredisait ; le test qui imposait la phrase fausse réécrit), `modele`, `frames_confirmation`, `seuil_matching` (silencieuses sur les verdicts terrain). Toutes citent maintenant les mesures (profil livré = valeur conseillée quand le terrain a tranché). |
| Épaisseur de bande : mesurée | 5 px = 37, 30 px = 32 (référence), 100 px = 24 — influence forte (zone neutre de confirmation du côté de départ). Aide réécrite d'après la mesure, pas de 5 en 5, bornes 5-100. |

## v2.8.0 — LISIBLE ET FIDÈLE (05/11/2026, LIVRÉE)

| Apport | Détail |
|---|---|
| Flèches visibles sur les listes | Le style des listes faisait disparaître la flèche native de Qt ; une image livrée (`resources/fleche-bas.png`) est posée en QSS dans les 3 thèmes. |
| Thème marine par défaut | C'est un thème sombre lui-même — lisibilité extérieure conservée. |
| Ligne plus lisible | Flèche de sens doublée, croix de placement doublées, trait plus épais. |
| Profils livrés | Deux profils validés terrain copiés dans chaque installation par l'étape post-build. |

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
| 5. Reprise au scrub | gardée, sans mémoire | à rouvrir sur besoin réel |
| 6. Pipeline décodage ‖ GPU | au chaud | seulement si profil > 25 % décodage |

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

### 5. Reprise au scrub / recalcul par segment — effort `L` — **idée conservée, sans mémoire**

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
comparer`, qui accepte un segment libre et une tolérance) : rouvrir l'item 5
uniquement si un vrai besoin d'analyse interactive apparaît.

### 6. Pipeline décodage ‖ inférence — effort `M-L` — **au chaud**

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

## v2.8 — FOULE DENSE ET PASSAGES RAPIDES (candidats, 31/10/2026 — requalifiés v2.8 le 04/11)

Deux items issus du rapport d'améliorations initial (28/10) qui n'avaient
pas été repris dans le lot v2.6. Même règle que partout : ils ne
s'exécutent qu'après annotation du segment de référence (v2.6 item 1) et
décision explicite. L'opérateur les a requalifiés « v2.8 » le 04/11 en
faveur de la mise à jour automatique (devenue v2.7).

| Item | Ce qu'il améliore | Effort | État |
|---|---|---|---|
| 1. NMS en foule dense | sous-comptage quand les têtes se chevauchent | `M` | **MESURÉ ET JETÉ (05/11, branche `essai/v2.8-nms`)** — voir le verdict plus bas |
| 2. Avertissement passant rapide | signal honnête quand un passage rapide n'est pas compté | `S` | **LIVRÉ sur la branche `essai/v2.8-nms`** (fusion à décider) |

### 1. NMS en foule dense — effort `M`

**Le mécanisme, en détail.** Le modèle YOLO ne sait pas « compter des
personnes » : il dessine des **boîtes** autour de chaque tête qu'il voit, avec
un score de confiance. En foule serrée, une seule tête produit souvent
plusieurs boîtes légèrement décalées qui se chevauchent. Sans filtre, la même
personne serait comptée trois fois. C'est le rôle du **NMS** (*Non-Maximum
Suppression*, « suppression des non-maxima ») : parmi un groupe de boîtes qui
se chevauchent, il **garde la meilleure et supprime toutes les autres** —
celles dont le chevauchement (IoU, *Intersection over Union* : proportion de
l'aire commune entre deux boîtes) dépasse un seuil.

**Le défaut qu'on cherche à corriger.** Le NMS ne sait pas distinguer
« trois boîtes sur la même tête » de « deux vraies têtes collées ». Deux
personnes côte à côte dans une masse compacte peuvent produire deux boîtes de
vraies personnes différentes qui se chevauchent au-delà du seuil : le NMS
**supprime la seconde comme si c'était un doublon**. La personne disparaît de
la détection, le tracker ne la voit jamais, elle **n'est pas comptée** — et
silencieusement. Le biais est donc toujours dans le même sens : **la foule
densément serrée est sous-comptée**, exactement le cas d'usage du logiciel.
À l'inverse, un NMS trop permissif garde des doublons et **sur-compte** —
d'où l'obligation de mesurer, jamais de deviner.

**L'état actuel (vérifié dans le code).** L'application n'appelle le modèle
qu'avec `conf` et `imgsz` (`detecteur.py:232-236`) : le seuil IoU du NMS est
celui d'ultralytics par défaut et **n'est nulle part réglable** aujourd'hui.
Aucun compteur n'enregistre combien de boîtes le NMS jette par frame — on
observe seulement le total final.

**VERDICT MESURÉ (05/11/2026, branche `essai/v2.8-nms`) — candidat JETÉ.**
Le diagnostic et le balayage ont été faits sur les vidéos de vérité terrain
de l'opérateur (test57 = 57 personnes, test124 = 124 — scène à banderoles),
avec le profil gagnant de la batterie :

- **Diagnostic** : le NMS jette 76-79 % des détections brutes (41 frames
  échantillonnées par vidéo). Grosse proportion, mais normale — l'essentiel
  des boîtes jetées sont des doublons de la même tête ;
- **Balayage du seuil IoU** (0,70 = défaut / 0,85 / 0,95) :
  test57 → 54 / 52 / **60** ; test124 → 107 / 99 / **143**. Monter le seuil
  **bascule du sous-comptage au sur-comptage** : à 0,95, des pistes
  fantômes nées sur la ligne font comptées des personnes deux fois
  (+19 sur test124), et le compteur de passages rapides explose en
  conséquence (8 → 69) ;
- **Aucune valeur ne convient aux deux scènes** : le déficit de test124
  n'est PAS un problème de NMS — ce sont des têtes jamais détectées
  (cachées derrière les banderoles) et des passages rapides. Le knob
  `iou_nms` essayé sur la branche a été **retiré** ; le défaut
  ultralytics (0,7) reste la référence.

Ne pas rouvrir sans donnée nouvelle (par exemple un vrai couloir dense
filmé en surplomb, qui n'a rien à voir avec ces places ouvertes).

### 2. Avertissement « passage rapide non compté » — effort `S` — **LIVRÉ sur la branche `essai/v2.8-nms`** (fusion à décider)

**Le défaut.** Une piste n'est acceptée par le tracker qu'après
`frames_confirmation` frames d'affilée (`config.py`), et le comptage
exige de connaître le côté « avant » du franchissement (`cote_avant`). Un
passant rapide traverse la ligne en 2-3 frames : quand sa piste est enfin
confirmée, il a déjà franchi, le côté avant n'a jamais été enregistré →
**rejet silencieux, personne non comptée, aucun indice pour l'opérateur**.

**Décision de l'opérateur (31/10) : palier sûr uniquement.** Le moteur
**détecte** le cas (côté avant inconnu au franchissement → rejet) et le
**compte à part** — jamais ajouté au total. Le palier ambitieux — **deviner
le côté de départ à partir de la vitesse de la piste** pour compter quand
même — est **écarté** : deviner peut inventer des franchissements, et un
faux avertissement est bon marché quand un faux compte coûte cher.

**CE QUE LE CHIFFRE EST — ET N'EST PAS** (explication demandée par
l'opérateur le 05/11, à relire avant toute utilisation) :

- ✅ **Une borne d'incertitude par le bas, et un indicateur de fiabilité.**
  Le vrai chiffre est quelque part entre `total` et `total + passages
  rapides` (moins les artefacts), jamais en dessous du total. Un compteur
  bas (1 sur test57) dit « ce total est fiable » ; un compteur élevé dit
  « méfiance, et corrige la CAUSE » (ligne trop loin du point d'apparition,
  confirmation trop stricte, caméra trop basse) ;
- ❌ **PAS un correctif du total.** Ne JAMAIS l'additionner au chiffre
  global : la case mélange de vrais passages manqués ET des **pistes
  fantômes** (artefacts de détection nés sur la ligne qui « franchissent »
  instantanément, sans être des personnes). Preuve mesurée : lever le seuil
  IoU fait exploser le compteur (1 → 27 sur test57, 8 → 69 sur test124)
  exactement quand les doublons apparaissent ;
- La vraie lecture sur les vidéos de l'opérateur : test57 → 54 comptés +
  1 rapide = le vrai est probablement 54-55 ; test124 → 107 + 8 = entre
  107 et ~115 — le reste de l'écart avec le compte humain (124) est
  derrière les banderoles, invisible pour tout le monde, et le compte
  humain lui-même y a été difficile (déclaré par l'opérateur).

**Implémentation (branche `essai/v2.8-nms`).** Moteur : `Compteur.
passages_rapides` incrémenté UNIQUEMENT quand `cote_avant is None` (un
contre-marcheur, `cote_avant <= 0`, est un rejet voulu et n'y figure
jamais) ; exposé dans `Resultat.passages_rapides` ; récap : ligne ambre
« N passage(s) rapide(s) possible(s) non compté(s) » (objet
`#avertissement`, déjà thémé), masquée quand le compteur est à zéro.
**Mesuré en conditions réelles** : 1 sur test57, 8 sur test124 — les
avertissements tombent sur de vrais franchissements, le déclencheur est
juste. 682 tests verts sur la branche.

## v2.7 — THÈME ET MISE À JOUR (décisions du 04/11/2026)

Deux items issus de l'analyse « une interface moderne à la GestyLoc ? ».
Verdict de l'analyse, écrit ici pour ne pas la refaire : le look de GestyLoc
vient de son DESIGN (palette Tailwind, bleu primaire `#2563eb`, cartes
arrondies, espacement), pas de sa stack Electron/React. Il se transpose donc
en QSS dans l'interface Qt existante. La réécriture complète en
Electron+React+sidecar Python est ÉCARTÉE : 2-4 semaines estimées pour un
décompte inchangé, un plan de concurrence vidéo à refaire, et le seul gain
fonctionnel (l'auto-update) est traité par l'item 2 ci-dessous.

### 1. Quatre modes de thème — effort `S` — LIVRÉ (04/11, validé par l'opérateur, release v2.5.0)

**Ce que c'est.** L'interface reste sombre par défaut (raison de lisibilité
extérieure documentée dans `interface/style.py`), avec trois modes ajoutés :
clair, bleu marine (demande opérateur du jour même), et « suivre le système »
(thème Windows, suivi en direct via `QStyleHints.colorSchemeChanged`).

**Choix de l'opérateur (04/11).** Les modes à choisir dans l'interface,
l'emplacement laissé à l'agent : liste déroulante « Thème » en bout de barre
de boutons. Le défaut reste SOMBRE (pas « système ») : un défaut « système »
ferait passer silencieusement les utilisateurs existants en clair.

**Implémentation.** `interface/style.py` : `STYLE_SOMBRE`/`STYLE_CLAIR`
(mêmes sélecteurs, contrastes recalés — compteur `#15803d` sur fond clair),
`mode_reel()` (résout « systeme », repli propre si Qt est muet), persistance
`config/local_theme.json` (même contrat que `local_dossier_video.json` :
préférence d'un poste, sous `.gitignore`, toute illisibilité rend le défaut).
`interface/app.py` : le sélecteur applique à chaud, persiste, arme/désarme le
suivi de l'OS ; le mode stocké est lu dans la VALEUR du choix, jamais dans
l'indice. `main.py` : le thème est relu avant la première fenêtre (écran
d'installation compris). Le thème n'est PAS un champ de `Config` : le panneau
de réglages produit une config du MOTEUR, et le thème n'a rien à y faire.

**Passe graphique (04/11, sur demande explicite : « tout sauf le layout »).**
La première version des thèmes laissait le sombre presque inchangé — l'app
était déjà sombre au bleu primaire — et l'opérateur l'a relevé. Ajouté aux
DEUX thèmes, sans toucher au layout ni à la géométrie des clics : groupes de
réglages en CARTES (fond détaché, coins 10 px, air intérieur), boutons
hiérarchisés (« Lancer » plus gros et gras, aide en bouton PLAT), champs
habillés (combos, spinboxes, liste déroulante, focus au bleu), info-bulles et
barres de défilement dans le thème, compteur posé sur une tuile arrondie.
Piège rencontré : la règle `QWidget` peignait les libellés d'un rectangle de
fond de fenêtre, visible en bande sombre sur les cartes — corrigé par
`QLabel { background: transparent; }`.

**Preuve.** 14 tests (`tests/test_theme.py`) : persistance corrompue → défaut,
résolution « systeme » avec faux QStyleHints, sélecteur de bout en bout,
sélecteurs partagés (champs/tooltips/scrollbars présents dans les deux
feuilles). Suite complète : **629 verts**. Captures des deux thèmes
présentées à l'opérateur — le commit part après validation visuelle.

### 2. Mise à jour automatique, niveau 2 — effort `M` — LIVRÉ (04/11, demande opérateur)

**Ce que c'est.** L'application, à chaque démarrage (exe gelé seulement),
cherche la dernière release sur l'API GitHub. Plus récente ? Un bouton vert
apparait dans la barre de boutons — pas de dialogue imposé. Au clic,
confirmation, puis : téléchargement avec **reprise sur interruption**
(`Range`), **vérification sha256** publiée en asset de la release,
extraction dans un dossier d'étape `.maj-<version>` du dossier parent,
**migration des données de l'opérateur** (`config/local_*.json`,
`config/profils/`, les `.pt` déposés dans `modeles/` non livrés par la
release), et un script d'échange détaché qui — après la sortie de l'app —
**RENOMME** l'installation courante en `*.ancienne` (sauvegarde, jamais une
suppression), met la nouvelle à sa place et la relance. La nouvelle
version, en démarrant, efface les restes (`nettoyer_anciennes`) : un
`*.ancienne` encore présent au démarrage suivant prouve que la nouvelle
version N'A JAMAIS démarré, et la sauvegarde contient l'installation qui
marchait.

**Garde-fous (tous bloquants).** Pas d'asset `.sha256` dans la release →
repli niveau 1 (bouton qui ouvre la page). Archive sans le bon sha →
effacée, rien d'installé. Espace disque insuffisant → refus avant de
télécharger. Archive suspecte (zip-slip) → refusée. Hors exe gelé
(développement, tests) → module muet, jamais de réseau. Un serveur qui
ignore la reprise `Range` → redémarrage du téléchargement à zéro au lieu
d'un fichier corrompu.

**Implémentation.** `compteur/mise_a_jour.py` (moteur, sans Qt — 21 tests
`tests/test_mise_a_jour.py`, réseau injecté, zips réels dans tmp) ;
`interface/app.py` : `_VerificationMaj` / `_InstallationMaj` (pattern
worker/thread du chargement de modèle), bouton `#maj_disponible` dans les
trois thèmes, `QProgressDialog` modal avec annulation bornée ;
`closeEvent` attend le thread de mise à jour de façon bornée.

**Reste, avant de compter dessus en conditions réelles** : un test complet
du remplacement sur une installation réelle (PC de l'opérateur) au moment
de la release qui la portera — c'est le seul item du projet capable de
rendre une app non démarrable s'il rate, et le renommage-sauvegarde est
précisément ce qui rend l'échec récupérable à la main. Les releases
futures doivent publier l'asset `.zip.sha256` à côté du zip.
