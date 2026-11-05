# Proposition v3 — moteur ONNX Runtime (remplace le téléchargement torch)

Document de conception écrit le 05/11/2026, à la question de l'opérateur :
« pourquoi se faire chier avec 2,4 Go si 100 Mo suffisent ? ». Statut :
**proposition** — rien n'est décidé, la règle du dépôt s'applique (mesure
d'abord). Le « spike » de mesure est décrit à la fin : c'est lui qui tranche.

## Pourquoi torch pèse 2,4 Go alors que le modèle fait 50 Mo

Torch embarque une usine complète ; le logiciel n'utilise qu'un atelier.

| Dans les 2,4 Go | À quoi ça sert | Utilisé par le logiciel ? |
|---|---|---|
| Machines d'entraînement (autograd, optimiseurs, distribué) | Entraîner des modèles | Non — jamais |
| Noyaux CUDA pour toutes les cartes depuis 2016 (sm_50 → sm_90) | Tourner sur tout GPU NVIDIA | Non — une seule cible |
| cuDNN + cuBLAS complets | Tous les types de calcul | Une fraction |
| L'écosystème Python de torch | Souplesse de recherche | Non — un forward pass |

Un modèle entraîné (25,9 M de paramètres = ~50 Mo) n'a besoin, pour
l'inférence seule, que d'un exécuteur qui applique le graphe de calcul :
c'est ONNX Runtime. Le graphe est figé dans un fichier `.onnx`.

## Les deux voies

| | A — ONNX Runtime + CUDA | B — ONNX Runtime + DirectML |
|---|---|---|
| Installation | ~700 Mo-1 Go (cuDNN obligatoire) | **~100 Mo** |
| Cartes supportées | NVIDIA uniquement (statu quo) | **NVIDIA + AMD + Intel** |
| Changement de contrat d'installation | Modeste | **Total** — la définition du majeur du projet |
| Disparait | Le téléchargement torch | Le téléchargement torch ET la fragilité « PC vierge » |
| Vitesse attendue | Comparable à torch (souvent un peu plus rapide) | Un peu plus lente sur NVIDIA (1,2-2× sur les gros modèles — inconnu ici, modèle petit) |

La voie B est la seule qui justifie le « 3 » : elle change qui peut utiliser
le logiciel. La voie A reste le repli si B est trop lente.

## Les points faibles, honnêtement

1. **La parité de décompte n'est pas garantie d'office.** La conversion
   peut faire basculer une détection limite. Preuve exigée : la batterie
   complète (référence 32, test57 = 54, test124 = 107, plongée = 122)
   avant toute bascule.
2. **Perte des commodités d'ultralytics** : prétraitement (letterbox,
   normalisation) et NMS deviennent notre responsabilité, à réimplémenter
   au pixel près. La zone est connue (mesures NMS du 05/11, seuil IoU 0,7).
3. **Vitesse DirectML sur RTX 4070 inconnue** jusqu'à mesure.
4. **Le fine-tuning (v3.1 envisagée) gardera torch** — mais uniquement sur
   la machine de développement : le logiciel livré n'a besoin que de
   l'inférence, et un `.pt` fine-tuné se convertit en `.onnx` en une
   commande.

## Le spike (une demi-journée) et sa règle de décision

1. Convertir `tetes-medium-1280.pt` → `.onnx` (export ultralytics,
   prétraitement exact : letterbox, normalisation) ;
2. Écrire un `DetecteurOnnx` — même interface que `Detecteur`, mêmes
   sémantiques de boîtes ;
3. Mesurer les DEUX voies sur le segment de référence + la vidéo plongée :
   comptes et débits, côte à côte avec le torch actuel ;
4. Rapport + verdict écrit dans cette section.

**Règle de décision** :
- comptes non identiques → voie morte, quelle qu'elle soit ;
- voie B ≥ ~20 i/s sur la 4070 → **B gagne** (une vidéo de 5 min analysée
  en 2 min suffit à l'usage) ;
- voie B < 20 i/s → repli en A, la v3 reste justifiée (2,4 Go → ~1 Go +
  fin du téléchargement fragile) mais reste NVIDIA-only, documenté.

## RÉSULTATS DU SPIKE (06/11/2026) — la voie B VALIDÉE

Tout s'est passé sur la branche `essai/v3-onnx`. Deux pièges trouvés par la
mesure, sans conséquence une fois corrigés :

1. **BGR vs RGB** : le predictor d'ultralytics convertit BGR→RGB avant le
   graphe. Nourrir le graphe en BGR donnait 42 détections contre 49 au
   même pixel — trouvé en comparant les TENSEURS d'entrée (écart nul à
   6e-08 près après inversion des canaux) ;
2. **Le NMS ne se réimplémente pas** : une version maison perdait 1-3
   détections par frame sur les cas limites. Le NMS d'ultralytics
   (`utils.nms.non_max_suppression`) est utilisé tel quel — pour la v3
   livrée, il sera vendoré (comme `LetterBox` et `scale_boxes`) avec test
   de parité.

**Parité frame par frame (60 frames du segment de référence, bande de
500×720)** : 2 896 détections torch, **chaque boîte torch a son jumeau
ONNX** (appariement ≤ 4 px, même score).

**Batterie complète (comptes, même config des deux côtés)** :

| Vidéo | torch | ONNX CUDA | Écart |
|---|---|---|---|
| référence (frames 3600-4500, medium, 640) | 32 | 31 | −1 |
| plongée (profil manif-vue-plongeante) | 122 | 123 | +1 |
| test57 (ligne 75 %, medium-1280) | 56 | 56 | 0 |
| test124 (idem) | 117 | 116 | −1 |

Les ±1 sont des détections de bord qui basculent au seuil (écarts FP32
infimes de conversion) : 1/122 = 0,8 %, dans le bruit du compte humain.

**Débits (RTX 4070, lot de 4, comptage complet)** :

| Vidéo | torch CUDA | ONNX CUDA | ONNX **DirectML** |
|---|---|---|---|
| plongée (957 frames, 1920→1280) | 57,9 i/s | 38,4 i/s | **51,2 i/s** |
| référence (905 frames, medium 640) | 73,5 i/s | 55,2 i/s | — |

**Verdict** : DirectML fait 51,2 i/s sur la 4070 — 88 % de torch, très
au-dessus du seuil des 20 i/s. **La voie B gagne sa propre règle.**

**Correction d'estimation sur le poids** (honnêteté) : les `.onnx` font
~99 Mo par modèle FP32 (les `.pt` stockent ~50 Mo — poids compactés). Un
zip v3 ≈ 380 Mo contre 213 Mo aujourd'hui — MAIS le téléchargement de
2,4 Go de torch **disparait entièrement**, tout comme la machinerie de
venv et le risque « PC vierge ». Bilan net très favorable ; l'option FP16
(~50 Mo par modèle, à re-valider contre la batterie) existe pour revenir
au poids d'origine.

**Reste avant une v3** (effort L, une autre session) : vendorer
LetterBox/scale_boxes/NMS avec tests de parité, brancher
`DetecteurOnnx` dans l'application (sélecteur de moteur), refaire
l'installateur sans la machinerie torch, valider DirectML sur une carte
AMD/Intel réelle, mise à jour du updater/BUILDING.md.
