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
