# Changelog

Toutes les évolutions notables de ce projet sont documentées ici. Le format
s'inspire de [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/) ; les
notes de release détaillées (anglais) accompagnent chaque version sur la
[page des releases GitHub](https://github.com/galaxiel/crowd-counter/releases).

Les modèles livrés sont des graphes `.onnx` **inclus dans l'archive** (depuis la
v3) ; les poids source `.pt` restent sur le poste de dev (export / fine-tuning)
et ne sont pas dans les archives (voir le README).

## [3.3.0] — 2026-11-13

Banc de vérité terrain et annotation au clic : l'opérateur dispose enfin d'un
outil pour poser la vérité terrain sans numéro de frame à recopier, et d'un
outil séparé pour annoter les boîtes d'entraînement. Côté app, une option
annonce les franchissements écartés faute de côté de départ connu. Le moteur
de comptage (appariement IoU) est inchangé.

### Ajouté

- **Option « Avertir des passages rapides non comptés »** (réglages → Tracker,
  activée par défaut) : annonce les franchissements écartés faute de côté de
  départ connu — une borne basse d'incertitude, jamais ajoutée au total. Le
  moteur les mesure toujours ; l'option ne décide que de la phrase. La réserve
  voyage à la source unique (`rapport.indicateurs_fiabilite`) : récap, bilan
  copié et JSON exporté ; le chiffre brut reste exporté option coupée.
  Mesuré segment 3600-4500, sens -1 : 1280 → 36 comptés + 8 signalés ;
  640 → 32 + 6.
- **Annotateur au clic** (`tools/annotateur.py`, outil séparé, hors app) :
  l'opérateur clique sur une tête au moment où elle est SUR la ligne verte ;
  le frame courant est enregistré sans numéro à noter à la main. Lecture
  ralentie (0,25×/0,5×/1×), pas à pas, seek, annuler/supprimer, reprise
  automatique d'une session existante. Ligne et numéro de frame dessinés par
  les mêmes briques que le banc. Sortie au format du banc
  (`verite_terrain/segment_<debut>-<fin>_operateur.txt`), relue par
  `lire_annotations` puis confrontée au moteur par `comparer`. 13 tests TDD.
- **Annotateur de boîtes** (`tools/annotateur_boites.py`, outil séparé du
  précédent) : données d'ENTRAÎNEMENT, pas de validation — glisser une boîte
  sur la tête au moment où elle est visible (pas de ligne), « Proposer »
  laisse le modèle ONNX poser ses boîtes à confirmer/corriger, export dataset
  YOLO (`entrainement/` : images brutes + labels normalisés + `data.yaml`),
  reprise des labels existants. 15 tests TDD.

### Documenté

- **Banc de vérité terrain exécuté le 12/11** sur le segment 3600-4500,
  annotation partielle (premier plan, à réviser par l'opérateur) : 14/15
  appariés à 640 comme à 1280, même manqué (frame 4290). Le banc ne tranche pas
  32 vs 36 (écart dans la foule dense non annotée) ; résolution auto 1280
  conservée. Annotation : `verite_terrain/segment_3600-4500.txt`.
  Comptage opérateur du 13/11 : **45** sur le segment (total, sans numéros de
  frame) ; 36 + 8 = 44 à 1280 contre 32 + 6 = 38 à 640 : l'auto 1280 est
  confirmé et la réserve annoncée est du bon ordre de grandeur. Comparaison
  frame par frame en attente des numéros de frame.

Suite : **783 passés, 1 sauté** (parité dev).

## [3.2.0] — 2026-11-10

Refonte issue de l'audit lecture seule du 10/11 (12 bugs + robustesse) et de sa
section 4 « interface ». Compte rendu détaillé : `docs/refonte-v3.2.0.md`. Le
moteur de comptage est inchangé (matching IoU intact) ; la refonte porte sur
l'exactitude écran↔moteur, l'honnêteté du bilan, le cycle de vie Qt, les modèles
ONNX et l'interface. Suite à la livraison : **734 passés, 1 sauté** (parité dev).

### Ajouté

- **Accordéon des réglages** : les six cartes deviennent un `QToolBox`, une
  section ouverte à la fois, profils en tête, aide dépliable section par section.
  Le panneau ne décide rien (il produit une `Config`).
- **Pastille « modèle : trouvé / absent »** avant « Lancer », cliquable vers le
  champ Modèle des réglages ; l'état remplace l'ancien texte `.pt`.
- **Boutons « Copier le bilan » / « Enregistrer… »** en fin d'analyse : le
  résultat n'existe plus seulement en RAM (presse-papiers, JSON + CSV).
- **Cadenas « ligne verrouillée — réglages au prochain lancement »** sur la vidéo
  pendant toute la session ; statut de pause explicite « ligne et sens verrouillés ».
- **Validation des formes ONNX au chargement** : batch statique, sortie
  multi-classe, canaux non RGB refusés avec un message d'export lisible, pas au
  premier tick.

### Corrigé

- **Sens inversé en pause sans effet moteur** (compte faux invisible) : la
  garde ne testait que le timer ; ligne et sens sont désormais verrouillés dès
  la session ouverte et rappelés au moteur (`ajuster_ligne`) à chaque reconstruction.
- **Réglages appliqués à chaud en pleine analyse** (total non reproductible) :
  panneau gelé pendant toute la session, pause comprise.
- **Frame illisible annoncée « Terminé »** : distinction fin de fichier / erreur
  de décodage, bandeau « analyse incomplète ».
- **« Secondes » = durée vidéo au lieu du temps de calcul** : l'avertissement
  « analyse lente » peut enfin se déclencher ; avertissements de `statistiques()`
  affichés dans le récap.
- **Thread d'installation jamais arrêté** (crash Qt au ré-essai après annulation) :
  `quit` sur échec/annulation/succès ; un seul bouton MAJ réutilisé.
- **« Recommencer » ne se réactivait jamais** : `_une_analyse_faite` écrit à
  l'arrêt d'une analyse engagée.
- **Textes et glob `.pt` périmés** : conseils et liste en `.onnx` ; déposer un
  `.pt` ne mène plus à un échec silencieux.
- **Nom de profil non assaini** (traversée / OSError) ; **zip-slip** (filtre à
  séparateur) ; **`nettoyer_anciennes`** effaçait tout `*.ancienne` voisin
  (limité au nom exact de sauvegarde) ; **garde NaN** sur le fps ; `ErreurDisque`
  lisible et `verifier_disque` appelé avant téléchargement ; journal fichier.

### Modifié

- **Bouton primaire contextuel** : « Lancer » au repos, « Pause »/« Reprendre »
  pendant la session, « Recommencer » en fin d'analyse ; « Lancer » grisé en pause.
- QSS des trois thèmes étendu aux nouveaux widgets (pastille, cadenas, onglets
  d'accordéon, boutons de récap).

## [3.1.0] — 2026-11-06

### Ajouté

- **L'affichage suit les personnes pendant une perte brève du tracker.**
  Sur une marche rapide ou une occultation (drapeau), le tracker peut perdre
  quelqu'un une à trois frames : le point et le carré vert restaient figés à
  l'ancienne place, sur du vide. Ils glissent maintenant dans la dernière
  direction connue, et au-delà de trois frames ils s'effacent au lieu de
  tricher (réapparition au ré-accrochage). Purement de l'affichage : le
  comptage est prouvé inchangé (événements identiques frame par frame sur la
  vidéo plongée de référence).

## [2.8.0] — 2026-11-05

### Ajouté

- **Flèche visible sur toutes les listes déroulantes.** Le style des
  listes faisait disparaitre la flèche native de Qt : rien n'indiquait
  qu'une liste s'ouvrait. Une flèche dessinée (image livrée
  `resources/fleche-bas.png`) est posée sur chaque liste, dans les trois
  thèmes.
- **Le thème bleu marine est le thème par défaut** des nouvelles
  installations (c'est un thème sombre lui-même : la lisibilité extérieure
  est conservée).

## [2.8.0] — 2026-11-05

### Corrigé

- **Sur une ligne inclinée, la zone de détection ne suivait pas le dessin.**
  Le rognage est un rectangle droit englobant : ses coins dépassaient de la
  bande réelle, et le voile affiché restait droit. Désormais les détections
  hors de la bande oblique sont écartées ET le voile suit l'inclinaison —
  l'affiche et le comptage décrivent exactement la même zone. Aucun
  changement pour une ligne horizontale ou verticale (rectangle = bande).

### Modifié

- **Ligne de comptage plus lisible** (demande opérateur) : flèche de sens
  deux fois plus longue et épaisse, croix de placement doublées, trait de
  ligne plus épais.
- **Magnétisme du tracé** : une ligne tracée à moins de 3° de l'horizontale
  ou de la verticale se colle exactement droite (recalage du second point).
  Un tracé franchement diagonal n'est pas déplacé.

## [3.0.1] — 2026-11-06

### Corrigé

- **L'analyse en lot plantait** (`'list' object has no attribute 'ndim'`) :
  `run` d'ONNX Runtime renvoie une LISTE de sorties, et le code de lot
  tranchait la liste au lieu du tenseur — trouvé par l'opérateur sur la
  première analyse réelle, corrigé et prouvé sur sa vidéo (122/122, 50 i/s).

## [3.0.0] — 2026-11-06

### Changed — CHANGEMENT DE CONTRAT D'INSTALLATION (le « majeur » du projet)

- **Le moteur est ONNX Runtime : plus de torch, plus d'ultralytics, plus de
  téléchargement de 2,4 Go au premier lancement.** Les modèles livrés sont
  des graphes `.onnx` ; l'accélération GPU passe par DirectML, qui pilote
  NVIDIA, AMD **et** Intel — la v2 exigeait une carte NVIDIA.
- **Parité prouvée** avant bascule : 2 896/2 896 détections jumelées sur 60
  frames de référence ; comptes identiques à ±1 sur les quatre vidéos
  terrain ; DirectML mesuré à 51,2 i/s sur RTX 4070 (88 % de torch). Détail
  complet et deux pièges trouvés par la mesure (RGB obligatoire, NMS à ne
  pas réimplémenter) dans `docs/design/v3-onnx-proposition.md`.
- `main.py` ne reconstruit plus de venv, plus d'écran d'installation :
  le double-clic ouvre la fenêtre. `compteur/telechargement.py` (1 545
  lignes) et `interface/demarrage.py` supprimés.
- Le poids du zip monte à ~380 Mo (les graphes FP32), contre 213 Mo — mais
  le téléchargement de 2,4 Go disparaît.

### Added

- `compteur/erreurs.py` : exceptions et dossier de données survivant au
  retrait du téléchargement.

## [2.10.0] — 2026-11-05

### Ajouté

- **Dialogue « À propos »** (bouton en bout de barre) : version du
  logiciel, bouton **« Vérifier les mises à jour »** — la même recherche
  que celle du démarrage, déclenchable à la main, résultat annoncé dans
  le dialogue — et lien vers la page des versions. Le bouton vert reste
  le geste d'installation : il n'apparaît que quand une mise à jour
  existe.

## [3.0.1] — 2026-11-06

### Corrigé

- **L'analyse en lot plantait** (`'list' object has no attribute 'ndim'`) :
  `run` d'ONNX Runtime renvoie une LISTE de sorties, et le code de lot
  tranchait la liste au lieu du tenseur — trouvé par l'opérateur sur la
  première analyse réelle, corrigé et prouvé sur sa vidéo (122/122, 50 i/s).

## [3.0.0] — 2026-11-06

### Changed — CHANGEMENT DE CONTRAT D'INSTALLATION (le « majeur » du projet)

- **Le moteur est ONNX Runtime : plus de torch, plus d'ultralytics, plus de
  téléchargement de 2,4 Go au premier lancement.** Les modèles livrés sont
  des graphes `.onnx` ; l'accélération GPU passe par DirectML, qui pilote
  NVIDIA, AMD **et** Intel — la v2 exigeait une carte NVIDIA.
- **Parité prouvée** avant bascule : 2 896/2 896 détections jumelées sur 60
  frames de référence ; comptes identiques à ±1 sur les quatre vidéos
  terrain ; DirectML mesuré à 51,2 i/s sur RTX 4070 (88 % de torch). Détail
  complet et deux pièges trouvés par la mesure (RGB obligatoire, NMS à ne
  pas réimplémenter) dans `docs/design/v3-onnx-proposition.md`.
- `main.py` ne reconstruit plus de venv, plus d'écran d'installation :
  le double-clic ouvre la fenêtre. `compteur/telechargement.py` (1 545
  lignes) et `interface/demarrage.py` supprimés.
- Le poids du zip monte à ~380 Mo (les graphes FP32), contre 213 Mo — mais
  le téléchargement de 2,4 Go disparaît.

### Added

- `compteur/erreurs.py` : exceptions et dossier de données survivant au
  retrait du téléchargement.

## [2.10.0] — 2026-11-05

### Corrigé

- **La molette fait défiler les réglages, elle ne change plus les champs.**
  Survoler un champ (nombre, liste) en descendant le panneau changeait sa
  valeur sans le vouloir (comportement natif de Qt). Un champ ne réagit
  désormais à la molette que s'il a le focus (clic dedans d'abord) ; sinon
  c'est le panneau qui défile.

## [2.10.0] — 2026-11-05

### Ajouté

- **Bouton « Sens : … » dans la barre de boutons** (demande opérateur) :
  le sens de comptage s'inverse d'un clic, avec son libellé explicite et
  la flèche verte qui pivote. L'option « Sens de traversée » quitte le
  panneau de réglages — le panneau ne fait que porter la valeur, les
  profils continuent de l'appliquer.
- **Bouton « Recommencer »** (demande opérateur) : relance l'analyse du
  début sans recharger la vidéo — la vidéo est rembobinée, le compteur
  remis à zéro, le modèle reste chargé. Il n'apparait qu'après un premier
  essai ; c'est le « Lancer » du deuxième essai, avec un nom qui le dit.
- **Magnétisme du tracé porté à 5°** (demande opérateur, réglé par essai).

## [2.7.1] — 2026-11-05

### Corrigé

- **Après une mise à jour automatique, l'application repartait avec un
  dossier courant FAUX** (celui du dossier parent, pas celui de
  l'installation) : la liste des profils était vide, « Charger ce
  profil » ne trouvait rien, et les fichiers mémoire
  (`config/local_*.json`) s'écrivaient dans le dossier parent. Deux
  correctifs : le bat d'échange relance l'application **depuis son
  dossier**, et l'application gelée se réancre elle-même sur le dossier
  de son exe au démarrage (quel que soit le lanceur).

## [2.7.0] — 2026-11-05

### Ajouté

- **Profils de réglages livrés avec le logiciel.** `config/profils/`
  transporte désormais deux profils validés sur le terrain, copiés dans
  chaque installation par `tools/copier_modeles.py` :
  `manif-vue-laterale-haute` (vue de côté, caméra légèrement en hauteur —
  `tetes-medium-1280`, seuil 0,15, confirmation 1) et `manif-vue-plongeante`
  (vue en plongée, flux vertical, têtes rapides — `tetes-medium-1280`,
  seuil 0,05, confirmation 1, matching 0,15, hystérésis 1 ; mesuré à
  l'identique du compte humain sur la vidéo de référence). La ligne se
  trace à la main sur chaque vidéo, comme toujours. Une variante
  personnelle d'un profil livré doit être enregistrée sous un autre nom
  pour survivre aux mises à jour.

## [2.6.6] — 2026-11-05

### Corrigé

- **La mise à jour automatique s'arrêtait au premier tour et ne finissait
  jamais.** Le script qui échange l'installation attendait la fermeture de
  l'application avec un tube (`tasklist | find`) qui se **fige** dans ce
  contexte sans console : le script restait vivant indéfiniment, la nouvelle
  version n'était jamais mise en place et rien ne relançait l'application.
  L'attente passe désormais par une commande PowerShell sans tube, qui rend
  la main dès que l'application a disparu. **Conséquence** : les versions
  ≤ 2.6.5 ne peuvent pas se mettre à jour toutes seules — installez cette
  2.6.6 à la main une dernière fois, puis le bouton vert fera tout le
  travail.
- **L'icône de la barre des tâches affichait un dessin par défaut de Qt**
  (une petite fenêtre blanche/verte) au lieu du logo, alors que l'exécutable,
  l'icône de fenêtre et l'icône vue par l'explorateur étaient toutes
  correctes. Cause : Qt enregistre la classe de fenêtre avec sa propre icône
  par défaut, que le shell utilisait pour le bouton. L'icône de classe est
  désormais posée explicitement sur le logo avant l'affichage de la fenêtre
  (`interface/ressources.py::appliquer_icone_classe`).

## [2.6.5] — 2026-11-05

### Ajouté

- **Texte d'accueil dans la zone vidéo** : tant qu'aucune vidéo n'est
  chargée, le grand cadre noir indique les deux façons de charger une vidéo
  (glisser-déposer, ou bouton *Charger la vidéo*) au lieu de rester muet.
- *(Distribution, invisible dans l'application)* : l'archive de release perd
  le préfixe historique `V2` — `CompteurManifestation-v2.6.5-win64.zip`.
  Même application, même dossier, même exe.

## [2.6.4] — 2026-11-05

### Ajouté

- **Les réglages du dernier lancement sont repris au démarrage** — seuil,
  modèle, confirmation… (la ligne tracée, elle, appartient à chaque vidéo
  et n'est jamais mémorisée). Toute illisibilité rend les défauts.
- **Le récapitulatif de fin rappelle les réglages qui ont produit le
  total** (modèle, seuil, confirmation, résolution) — chaque essai devient
  traçable à ses réglages.
- **Journal écrit par le script d'échange de la mise à jour**
  (`%LOCALAPPDATA%\CompteurManifestation\journal-mise-a-jour.log`) : chaque
  étape et toute erreur sont consignées — un échange qui rate n'est plus
  un silence.

### Corrigé

- **Le script d'échange de la mise à jour ne pouvait jamais réussir** : le
  chemin de la nouvelle version repartait du nom du dossier d'étape ALORS
  QUE `%~dp0` désigne déjà ce dossier — chemin doublé, inexistant, `move`
  en échec silencieux, repli à l'ancienne version sans relance. Trouvé par
  le premier test réel bout-en-bout (l'app tournait depuis le dossier
  d'étape). Toute mise à jour DEPUIS une version ≤ 2.6.3 échoue au même
  endroit, sans danger (compléter à la main depuis le dossier `.maj-X`) ;
  **à partir de cette version, l'échange est automatique pour de bon** —
  installez cette 2.6.4 manuellement une dernière fois, les suivantes se
  mettront à jour toutes seules.
- **Identité de barre des tâches explicite** (AppUserModelID) : sans elle,
  Windows peut afficher l'icône en cache des builds précédents.

## [2.6.3] — 2026-11-04

### Ajouté

- **Icône de l'application** (foule cyan sur fond noir) : barre de titre,
  barre des tâches, écran d'installation et icône du `.exe` lui-même
  (gravée par PyInstaller).
- **Propriétés de version de l'exe** (clic droit → Propriétés → Détails) :
  dérivées de `compteur.VERSION` à chaque build — source de vérité unique,
  l'exe porte automatiquement sa version après chaque mise à jour.

## [2.6.2] — 2026-11-04

### Corrigé

- **L'interface gelait dès le début d'une mise à jour** (fenêtre « ne
  réponds plus » dès le premier bloc téléchargé). Cause : la barre de
  progression était branchée sur une lambda sans objet récepteur, donc
  exécutée dans le thread réseau — `setValue` appelé hors du fil IHM.
  La progression passe maintenant par un slot de la fenêtre, avec un test
  de non-régression qui émet depuis un fil secondaire et vérifie le fil
  d'exécution.

## [2.6.1] — 2026-11-04

### Ajouté

- **Glisser-déposer d'une vidéo** : dépose un fichier vidéo n'importe où sur
  la fenêtre pour la charger. Mêmes règles que le sélecteur de fichier
  (une seule vidéo, mêmes extensions) ; refusé pendant une analyse en
  cours — un dépôt ne doit pas arrêter un comptage.

## [2.6.0] — 2026-11-04

### Ajouté

- **Mise à jour automatique** : au démarrage, l'application vérifie la
  dernière release publiée. Plus récente ? Un bouton vert apparait —
  téléchargement avec reprise, vérification de l'empreinte sha256 publiée
  en asset, remplacement de l'application et relance automatiques. Les
  réglages, profils et modèles déposés sont conservés ; l'ancienne version
  reste en sauvegarde jusqu'au démarrage réussi de la nouvelle. Sans
  empreinte publiée, repli sur l'ouverture de la page de téléchargement.
  Disponible uniquement dans l'exécutable — c'est la première release que
  les versions suivantes pourront installer automatiquement.

## [2.5.0] — 2026-11-04

### Ajouté

- **Quatre modes de thème** — sombre (défaut), clair, bleu marine, suivre le
  système : choix en bas de la fenêtre, application à chaud, suivi en direct
  du thème Windows, mémorisé d'un lancement à l'autre
  (`config/local_theme.json`). Le sombre reste le défaut : le compteur est
  prévu pour être lu dehors, en plein jour.
- **Interface retravaillée** (dans les deux thèmes fixes) : groupes de
  réglages en cartes, boutons hiérarchisés (« Lancer » en bouton principal),
  champs et listes assortis au thème, info-bulles et barres de défilement
  thémées, compteur posé sur une tuile arrondie.
- **Banc de vérité terrain** (`tools/verite_terrain.py`) : extraction d'un
  segment en vidéo lente avec numéro de frame gravé, puis comparaison
  automatique entre les franchissements annotés à la main et les événements
  du moteur (tolérance et appariement paramétrables). Gabarit d'annotation
  fourni.
- **Débit et temps restant** affichés sous la barre de progression.
- **Raccourci Échap** pour arrêter l'analyse.

### Modifié

- **Chargement du modèle en arrière-plan** : la fenêtre ne gèle plus pendant
  le chargement des poids.
- Le modèle est **validé avant d'accepter une vidéo** ; retour visible des
  profils de détection appliqués ; mémoire du dernier dossier vidéo ouvert.
- **Verrou anti-rebond** du lancement d'analyse ; rapport
  `tracks_presents_*` (trajectoires observées, diagnostics).
- `opencv-python-headless` remplace `opencv-python` (aucune fonction
  d'affichage d'OpenCV n'est utilisée).

### Développement

- **Intégration continue** : GitHub Actions lance la suite de tests à chaque
  push (Ubuntu, torch CPU, Qt offscreen).
- Suite de tests portée à **629 tests verts** ; correctifs d'encodage des
  sous-processus de test ; documentation des candidats v2.7 et v2.8.

## [2.4.0] — 2026-10-22

### Modifié

- **Modèles renommés pour que le nom dise ce qu'ils détectent**
  (`cible-poids[-précision].pt`) : `medium.pt` → `tetes-medium.pt` (défaut),
  `nano.pt` → `tetes-nano.pt`, `yolov8n-head.pt` → `tetes-medium-1280.pt` —
  il n'était PAS « nano » : ses métadonnées montrent 25,9 M de paramètres,
  la classe de `tetes-medium.pt`. Les modèles génériques 80 classes deviennent
  `personnes-et-objets-…`.
- Légende de nommage livrée dans `modeles/` (`LISEZ-MOI.txt`).

## [2.3.0] — 2026-10-22

### Ajouté

- **Dossier `modeles/`** livré à côté de l'exécutable et balayé par
  l'application : un `.pt` déposé apparaît dans la liste sans redémarrage.
- **Dossier personnel** `%LOCALAPPDATA%\CompteurManifestation\modeles`, qui
  survit aux mises à jour.
- **Bouton « Parcourir… »** pour choisir un modèle n'importe où sur le
  disque, sans le déplacer.

### Corrigé

- Un modèle listé depuis `modeles/` pouvait refuser de se charger
  (« modèle introuvable ») : la liste et le chargement balaient désormais
  les mêmes dossiers, dans le même ordre — un modèle proposé est un modèle
  qui charge.

## [2.2.0] — 2026-10-22

### Ajouté

- **Barre de progression** sous la vidéo (frames / total, mode « occupé » si
  le conteneur ne déclare pas son nombre de frames).

### Modifié

- **Analyse ~2,6× plus rapide** : la détection passe par des lots de 4 images
  (45 s contre 115 s sur la vidéo de référence, décompte identique vérifié
  frame par frame) — le comptage reste strictement image par image.
- Rendu de l'aperçu allégé (~15 i/s) : l'affichage ne bride plus l'analyse ;
  le FP16 est retiré (décalait le décompte de −2 sans gain de vitesse).

### Corrigé

- Le flash rouge de comptage se déclenche aussi quand un comptage tombe
  entre deux frames affichées (il pouvait passer totalement inaperçu).

## [2.1.0] — 2026-10-05

### Ajouté

- **Déplacement de la ligne à la souris** : la bande suit la ligne, l'ensemble
  est un seul objet déplaçable, verrouillé au lancement de l'analyse.
- Les boîtes vertes des personnes comptées s'estompent après le
  franchissement au lieu de disparaître sur la ligne.
- Bouton de soutien ; la version s'affiche dans le titre de la fenêtre.

### Modifié

- **Bande de détection symétrique** (250 px de chaque côté de la ligne).
- Le sélecteur de vitesse de présentation est retiré : l'analyse va à la
  vitesse maximale de la machine.
- Licence du code : MIT (les poids gardent leurs licences d'origine).

## [2.0.0] — 2026-10-05

### Première version de la v2

- Application de bureau PySide6 : vidéo en direct, ligne à tracer au clic,
  bande de détection, compteur géant lisible de loin, récapitulatif de fin
  (total, durée, débit, pic, courbe).
- Détection de têtes (SCUT-HEAD) + tracker IoU, 100 % local — aucun
  entraînement, aucune donnée envoyée.
- **torch n'est pas dans l'archive** : téléchargé au premier lancement
  (version CUDA figée à celle du build, reprise d'un téléchargement
  interrompu, mode dégradé CPU pour que le démarrage soit toujours possible).
- Compteur de référence : 257 personnes sur les 3000 premières frames de la
  vidéo de référence (`sens=-1`).
