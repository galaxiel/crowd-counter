# Changelog

Toutes les évolutions notables de ce projet sont documentées ici. Le format
s'inspire de [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/) ; les
notes de release détaillées (anglais) accompagnent chaque version sur la
[page des releases GitHub](https://github.com/galaxiel/crowd-counter/releases).

Les poids `.pt` ne sont pas dans les archives : les modèles `tetes-*.pt`
doivent être posés dans `modeles/` (voir le README).

## [Non publié]

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
  depuis la 2.6.4, l'échange est automatique pour de bon.
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
