# Refonte v3.2.0 — audit du 10/11/2026 + interface

*Compte rendu de la refonte engagée sur décision opérateur « fait tout, y compris
l'UI » (10/11/2026). À lire avec l'audit d'origine
(`D:\Bureau\Hermes_doc\audits\crowd-counter.md`, lecture seule, version 3.1.0) dont
il reprend les numéros de bugs. Les `fichier:ligne` cités sous « constat » sont
ceux de l'audit, **avant correction** — ils documentent le défaut, pas l'état actuel.*

## Cadre

- **Point de départ** : v3.1.0, moteur ONNX Runtime sain (l'audit le confirme :
  ID de tracks jamais recyclés, franchissement interpolé, anti-recomptage non
  purgé par conception). Le fil rouge des défauts : **un résultat faux présenté
  comme juste** — l'écran et le moteur peuvent diverger, un arrêt de lecture est
  annoncé « Terminé », le résultat n'existe plus qu'en RAM.
- **Périmètre livré** : les 5 chantiers de l'audit (12 bugs + robustesse) **et**
  toute la section 4 « interface », en 6 lots.
- **Méthode** : TDD strict (test rouge d'abord, vu échouer pour la bonne raison,
  code minimal, vert, refactor). Passe rapide `pytest -m "not slow"` après chaque
  lot ; suite complète en finale. Aucun commit sans demande explicite (la
  demande de publication est intervenue après la livraison des 6 lots).
- **Verrou majeur respecté** : le **moteur de comptage ne change pas de
  comportement**. Le matching IoU n'est pas touché (un essai de repli a déjà été
  rejeté le 06/11 pour vol d'identités en foule dense). La refonte porte sur
  l'exactitude **écran↔moteur**, l'honnêteté du bilan, le cycle de vie Qt, les
  modèles ONNX et l'interface — pas sur l'algorithme de comptage. La batterie de
  référence n'a donc pas à être rejouée (aucun candidat tracker ouvert).

## Lot 1 — Cohérence moteur ↔ écran (bugs 1, 2, 3)

**Constats (audit).**
- Bug 1 (Élevée) — `interface/app.py:2162-2167`, `2015-2029`, `2052-2061` : sens
  inversé en pause sans effet moteur. La garde ne testait que `_en_analyse` ; le
  clic passait, la flèche pivotait à l'écran, mais ni `verrouiller()` ni
  `compteur.ajuster_ligne()` n'étaient rappelés. Sur la vidéo de référence :
  **315 contre ~1** — compte faux, invisible.
- Bug 2 (Élevée) — `interface/app.py:1740-1750`, `1558`, `1587-1592` : toute
  modification de réglage reconstruisait la ligne d'affichage **déverrouillée**,
  sans réappliquer au moteur. En pause, la ligne redevenait déplaçable ; un
  glissement de 100 px puis reprise : le moteur comptait sur la ligne d'origine.
- Bug 3 (Élevée) — `interface/app.py:1756-1791` : réglages modifiables et
  appliqués à chaud en pleine analyse (panneau jamais désactivé) → total
  mi-figue mi-raisin, non reproductible.

**Correctif.** État de session à **deux drapeaux** : `_en_analyse` (le timer
tourne) et `_session_ouverte` (analyse engagée, non terminée, **pause comprise**).
La pause ne lève que le premier. Tant que `_session_ouverte` :
- le panneau de réglages est **gelé** (`setEnabled(False)`), avec la mention
  « s'appliquent au prochain lancement » ;
- ligne et sens sont **verrouillés** ; toute reconstruction de ligne re-verrouille
  et rappelle `compteur.ajuster_ligne` pour que l'écran et le moteur décrivent la
  même ligne ;
- la zone de déplacement et le glissement sont inertes, même après un réglage.

**Tests** : `tests/test_coherence_ligne.py` (8), `tests/test_verrou_session.py` (6).
**Critère de validation** : « pause → sens → reprise donne le même total qu'un
lancement direct au bon sens » → `test_pause_sens_reprise_meme_total_et_meme_ligne` ;
« aucun widget de réglage actif pendant l'analyse » →
`test_panneau_gele_pendant_la_session_meme_en_pause`.

## Lot 2 — Bilan honnête (bugs 4, 7, 8)

**Constats (audit).**
- Bug 4 (Élevée) — `interface/app.py:2223-2232`, `2502-2507` : une frame illisible
  en milieu de vidéo produisait un lot vide → `arreter()` + « Terminé — N
  personnes ». Aucune distinction fin de fichier / erreur de décodage. Une vidéo
  de 60 min endommagée à la minute 2 publiait « Terminé — 48 personnes ».
- Bug 7 (Moyenne) — `interface/app.py:2113-2115`, `2497-2499` ;
  `compteur/compteur.py:422-455` : l'IHM passait `frames/fps` (durée vidéo) dans
  `secondes` (temps de calcul). L'avertissement « analyse plus lente que le temps
  réel » (`rapport.py:235-243`, seuil 5 i/s) ne pouvait **jamais** se déclencher
  depuis l'IHM ; une analyse CPU de 3 h passait sans alerte.
- Bug 8 (Moyenne) — `compteur/rapport.py:188-249` ; `interface/recap.py:320-339` :
  les avertissements de cohérence de `statistiques()` (« total ≠ événements »,
  « track_id répétés », « 0 compté avec foule présente ») étaient calculés mais
  jamais affichés.

**Correctif.**
- Distinction **fin de fichier** / **erreur de décodage** : une lecture
  interrompue avant la fin annonce « analyse incomplète » (bandeau), jamais
  « Terminé » seul.
- Le vrai **temps de calcul** part dans `secondes`, la **durée vidéo** dans
  `duree_video_s` ; la pause est déduite du temps de calcul. La fenêtre de pic
  se calcule sur la durée vidéo, pas le temps de calcul.
- Le récap **affiche les avertissements** de `statistiques()` (fiabilité), et les
  masque quand tout est cohérent.

**Tests** : `tests/test_bilan_honnete.py` (6), `tests/test_export_bilan.py` (5),
`tests/test_rapport.py` (étendu).
**Critère** : « une vidéo tronquée volontairement n'affiche jamais Terminé sans
bandeau » → `test_lecture_interrompue_annonce_analyse_incomplete` ;
« l'avertissement analyse lente se déclenche sur une analyse CPU forcée » →
couvert par les tests de fiabilité (`test_recap_affiche_les_avertissements_de_fiabilite`,
`test_secondes_et_duree_video_distinctes_au_bilan`).

## Lot 3 — Cycle de vie Qt & boutons (bugs 5, 6, 9)

**Constats (audit).**
- Bug 5 (Moyenne) — `interface/app.py:985-999`, `1015-1038` : thread d'installation
  jamais arrêté (aucun `quit` connecté). Annulation/échec → le thread reste dans
  sa boucle ; réessayer écrase `self._thread_maj` → l'ancien `QThread` est détruit
  en marche → **crash Qt** (« QThread: Destroyed while thread is still running »).
- Bug 6 (Moyenne) — `interface/app.py:460`, `2194-2199` : `_une_analyse_faite`
  n'était écrit à `True` nulle part → « Recommencer » restait grisé pour toujours.
- Bug 9 (Basse) — `interface/app.py:949-953` : chaque vérification positive créait
  un nouveau bouton MAJ sans retirer le précédent → deux boutons verts empilés.

**Correctif.**
- `quit` du thread d'installation sur **échec / annulation / succès** ; une
  vérification reste possible après un échec ; une installation est refusée si un
  thread tourne déjà.
- **Un seul bouton MAJ** réutilisé, même après deux vérifications.
- `_une_analyse_faite` écrit à l'**arrêt d'une analyse engagée** → « Recommencer »
  s'active et repart de zéro avec une nouvelle vidéo.

**Tests** : `tests/test_threads_boutons.py` (6), `tests/test_maj_ui.py` (étendu),
`tests/test_etats_boutons.py` (6).
**Critère** : « annuler puis réessayer une installation ne ferme pas l'application »
→ `test_le_thread_d_installation_quitte_apres_un_echec` +
`test_verification_possible_apres_un_echec_installation` ; « Recommencer s'active
après la première analyse » → `test_recommencer_actif_apres_un_arret`.

## Lot 4 — Modèles & profils ONNX (bugs 10, 11 + robustesse ONNX)

**Constats (audit).**
- Bug 10 (Basse) — `interface/app.py:1301-1310` ; `interface/panneau_reglages.py:142`,
  `521`, `773` : `_etat_du_modele` globbait `*.pt` et conseillait « dépose un
  fichier .pt dans modeles/ » alors que le moteur v3 ne charge que des `.onnx` →
  l'opérateur suivait le conseil et recevait « format de modèle non supporté ».
- Bug 11 (Basse) — `interface/panneau_reglages.py:909-914`, `929` : nom de profil
  non assaini (« manif/été » → OSError ; « ../../x » → écrit hors du dossier).
- Robustesse ONNX — `compteur/detecteur.py:306-309`, `419-424`, `340` : aucune
  validation de forme à la construction. Un graphe à **batch statique** fait
  échouer `detecter_lot` à chaque tick (exception non capturée dans le slot
  QTimer → analyse figée, stderr muet en exe windowed) ; une **sortie multi-classe**
  est comptée silencieusement sur la mauvaise classe.

**Correctif.**
- **Validation des formes entrée/sortie au chargement** (`get_inputs()` /
  `get_outputs()`) : batch statique, sortie multi-classe, canaux non RGB refusés
  avec un **message d'export lisible**, au chargement — pas au premier tick.
- Textes et glob **`.onnx`** partout côté opérateur ; le message d'absence conseille
  « Dépose le fichier .onnx dans modeles/ » ; déposer un `.pt` produit un refus
  clair qui explique l'export ultralytics, plus un conseil menant à l'échec.
- **Nom de profil assaini** (pas de traversée, pas de séparateur).

**Tests** : `tests/test_formes_onnx.py` (5), `tests/test_modeles_ui.py` (7),
`tests/test_modeles.py` / `tests/test_detecteur.py` (étendus),
`tests/test_copier_profils.py`.
**Critère** : « un .onnx à batch statique est refusé au chargement avec un message
lisible, pas au premier tick » → `test_batch_statique_refuse` +
`test_charger_modele_applique_la_validation` ; « déposer un .pt ne produit plus un
conseil qui mène à l'échec » → message `.onnx` vérifié (`detecteur.py:161`).

## Lot 5 — Durcissement de la périphérie

**Constats (audit, §2 Robustesse).** `compteur/mise_a_jour.py` : filtre zip-slip
insuffisant (un frère partageant le préfixe passait) ; `nettoyer_anciennes`
(`489-515`) effaçait **tout** dossier `*.ancienne` du parent de l'installation
(un « photos.ancienne » voisin y serait supprimé au démarrage) ; `ErreurDisque`
mal formée / `verifier_disque` non appelé avant téléchargement ; pas de journal
fichier ; garde NaN absente sur le fps.

**Correctif.**
- **Zip-slip** : filtre à séparateur (un frère partageant le préfixe est refusé,
  un membre dans le dossier est accepté).
- **`verifier_disque` appelé avant de télécharger** ; `ErreurDisque` formate des
  octets lisibles ; silencieux si la place est là.
- **Journal fichier** sous `%LOCALAPPDATA%` ; un échec de journal reste silencieux
  (ne bloque pas l'installation).
- **Garde NaN** dans `analyser_video` : un fps non fini replie sur 25.
- **`nettoyer_anciennes` limité au nom exact** `CompteurManifestation.ancienne` :
  une sauvegarde voisine survit au démarrage.

**Tests** : `tests/test_durcissement.py` (10), `tests/test_mise_a_jour.py` (étendu),
`tests/test_compteur.py::test_analyser_video_fps_nan_replie_sur_25`.
**Critère** : « chaque point a un test unitaire sans réseau ni caméra ; un dossier
photos.ancienne voisin survit au démarrage » → `test_nettoyage_epargne_une_sauvegarde_voisine`,
`test_zip_slip_frere_refuse_a_l_extraction`, `test_verifier_disque_leve_une_erreur_lisible`,
`test_journal_fichier_sous_localappdata`, `test_analyser_video_fps_nan_replie_sur_25`.

## Lot 6 — Interface (section 4 de l'audit), écran par écran

La section 4 de l'audit proposait une interface « au service du terrain ». Tout
est livré, sans changer la géométrie de clic ni le moteur.

1. **Accueil.** Deux pastilles près de « Lancer » : **modèle** (trouvé/absent,
   cliquable vers le champ Modèle des réglages) et **périphérique effectif**.
   « Lancer » reste le bouton primaire ; le statut modèle remplace l'ancien
   texte `.pt`. (`interface/app.py`, `tests/test_badges_ui.py`.)
2. **Analyse en cours.** Réglages **grisés** avec mention « s'appliquent au
   prochain lancement » (corrige le bug 3 par le geste) ; barre d'état unique ;
   seuls Pause et Stop actifs ; un **cadenas discret** sur la vidéo dit que la
   ligne est figée (`QLabel#verrou`, `tests/test_verrou_session.py`).
3. **Pause.** Statut « En pause — ligne et sens verrouillés » ; « Reprendre »
   primaire ; « Lancer » grisé. (`tests/test_etats_boutons.py`.)
4. **Fin.** Les 4 chiffres + la courbe sont gardés ; **bandeau « analyse
   incomplète »** si la lecture a été interrompue ; avertissements de fiabilité ;
   boutons **« Copier le bilan » / « Enregistrer… »** (JSON + CSV) ; « Recommencer »
   réparé et primaire. (`interface/recap.py`, `tests/test_recap_export.py`.)
5. **Réglages.** Les six cartes passent en **accordéon** (`QToolBox`, une section
   ouverte à la fois), **profils en tête**, aide dépliable section par section,
   textes `.onnx` partout. Le panneau ne décide rien — règle actuelle conservée.
   (`interface/panneau_reglages.py`, `tests/test_accordeon.py`.)
6. **Mise à jour.** Traitée par les lots 3 et 5 (thread, bouton unique, durcissement).

**Bouton primaire contextuel** (`_maj_bouton_primaire`) : « Lancer » au repos,
« Pause »/« Reprendre » pendant la session, « Recommencer » en fin d'analyse.
Changement d'`objectName` suivi de `unpolish`/`polish` pour réappliquer le QSS.

**QSS des trois thèmes** (`interface/style.py`) étendu aux nouveaux widgets :
pastille `#badge_modele` (vert trouvé / ambre absent), `#verrou`, onglets
`QToolBox::tab`, boutons `#bouton_recap`. (`tests/test_theme.py`, 16.)

**Trois tests de l'ancien panneau défilant remplacés honnêtement** : l'accordéon
(section 4.5) supersède le design « panneau qui défile » des tâches 17/18. Les
tests `test_reglages.py` concernés ont été réécrits avec un commentaire expliquant
le changement de design — pas masqués.

## Inventaire des tests

- **12 nouveaux fichiers**, **77 cas** : `test_accordeon` (7), `test_badges_ui` (5),
  `test_bilan_honnete` (6), `test_coherence_ligne` (8), `test_durcissement` (10),
  `test_etats_boutons` (6), `test_export_bilan` (5), `test_formes_onnx` (5),
  `test_modeles_ui` (7), `test_recap_export` (6), `test_threads_boutons` (6),
  `test_verrou_session` (6).
- Fichiers existants étendus : `test_app`, `test_compteur`, `test_mise_a_jour`,
  `test_reglages`, `test_theme`, `test_rapport`, `test_modeles`, `test_detecteur`,
  `test_maj_ui`, `test_copier_profils`.
- **Suite complète : 734 passés, 1 sauté** (`pytest tests/ -q`, ~25 s, vérifié le
  10/11/2026). Le saut est `test_detecteur.py::test_parcite_des_detections_contre_l_ancien_chemin_torch`
  (marqué `slow`, dev uniquement : torch+ultralytics, graphe `tetes-medium-1280.onnx`
  exporté, vidéo de référence) — **ressource absente sur cette machine, pas une
  régression**. Passe rapide : 734 passés, 1 désélectionné.

## Verrous respectés

- `compteur/` n'importe **jamais** PySide6/tkinter/PyQt/wx (`test_isolation_ui.py` vert).
- Matching du tracker **non touché** ; aucun candidat `ROADMAP.md` non demandé ouvert.
- `config/default.json` et la dataclass `Config` synchronisés (test dédié vert).
- Aucun chemin d'OS en dur dans les tests (`tmp_path` + `pathlib`).
- Aucun build ni release avant la demande explicite de l'opérateur (intervenue
  après la livraison des 6 lots) ; aucun commit avant cette même demande.

## Livraison

- Version : **3.2.0** (`compteur.VERSION`, source de vérité unique ; la ressource
  de version de l'exe en est dérivée à chaque build).
- Notes de release : `release-notes-v3.2.0.md` (anglais, SHA-256 en dernière ligne).
- Procédure : `docs/BUILDING.md` §« Publishing a release » — archive **avec** le
  dossier `CompteurManifestation/` à la racine, **deux assets** (zip + `.zip.sha256`),
  hash généré depuis `dist/`.
- État de publication (URL, hash, assets) : voir `ETAT_PROJET.md`, mise à jour du
  10/11/2026.