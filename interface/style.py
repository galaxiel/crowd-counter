"""Thèmes de l'interface : sombre (défaut), clair, suivre le système.

**Pourquoi le sombre par défaut.** L'interface est vue dehors, souvent en
plein jour, parfois sur l'écran d'un portable posé sur un trotoir. Un thème
sombre n'est pas choisi pour l'esthétique, mais parce qu'il est le seul moyen
d'obtenir un chiffre LISIBLE à trois mètres. Sur fond clair, un gros chiffre
noir en plein soleil est illisible (le noir se confond avec le bitume, et
l'œil accommode mal entre une zone claire et une zone sombre voisine) ;
inversé — chiffres clairs sur fond sombre — le contraste reste lisible quelle
que soit la lumière ambiante.

**Depuis le 04/11/2026, les trois modes coexistent** (demande de l'opérateur)
: sombre, clair, et « suivre le système » (le thème Windows). Le défaut reste
`sombre` — la raison de lisibilité ci-dessus n'a pas changé, et un défaut
« système » ferait passer silencieusement les utilisateurs existants en clair
au premier lancement.

**Passe graphique du 04/11 (même mise en page, aucun changement de layout ni
de géométrie de clic).** Trois décisions, appliquées aux deux thèmes :

- **Hiérarchie des boutons.** « Lancer » (#primaire) est le seul bouton à
  pleine intensité, plus grand et plus gras ; les autres sont des boutons
  secondaires ; l'aide (`#bouton_aide`) devient un bouton plat, sans bordure,
  parce que déplier la documentation n'est pas l'action principale de l'écran.
- **Les groupes de réglages sont des cartes** : fond légèrement détaché du
  fond de fenêtre, coins arrondis, air intérieur. Le titre porte le fond de
  fenêtre pour « couper » le trait de bordure qu'il chevauche.
- **Le thème ne s'arrête pas au bord des widgets.** Champs (combos,
  spinboxes), liste déroulante, info-bulles, barres de défilement : tout ce
  qui était rendu « natif » (donc clair sur fond sombre) est habillé. C'est
  le changement le plus visible du thème sombre.

Dans chaque feuille, le compteur `QLabel#compteur` reste le seul chiffre lu
de loin : très grand (76 px), gras, posé sur une tuile qui le détache du
reste. La couleur du compteur change avec le thème : le vert clair (#4ade80)
garde ~13:1 de contraste sur le fond sombre mais ~1,6:1 sur fond clair — le
thème clair utilise donc un vert foncé (#15803d). Même règle pour
l'avertissement : ambre clair sur sombre, ambre foncé sur clair.

**Ce module n'importe volontairement pas PySide6 au chargement.** Il est
consommé par `main.py` AVANT que `interface.app` (qui importe cv2 puis numpy)
soit importable dans l'exécutable gelé — l'import de PySide6 ne se fait que
dans les fonctions, à la demande. `appliquer_style` reste idempotent :
l'appeler deux fois avec le même mode donne le même résultat.

**Persistance.** Le mode choisi vit dans `config/local_theme.json` — même
contrat que `local_dossier_video.json` : une préférence d'un POSTE, pas du
code, donc sous le `.gitignore` existant (`config/local_*.json`).
"""

from __future__ import annotations

import json
import logging
import pathlib

log = logging.getLogger(__name__)

#: Modes de thème acceptés. Un identifiant SANS ACCENT : c'est lui qui voyage
#: dans le fichier de préférence, pas le libellé affiché. « marine » est un
#: thème fixe ajouté à la demande de l'opérateur (04/11) : bleu marine profond,
#: même structure que « sombre ».
MODES: tuple[str, ...] = ("sombre", "clair", "marine", "systeme")

#: Mode appliqué quand rien n'est encore choisi (voir la raison de l'en-tête).
MODE_DEFAUT = "sombre"

#: Choix proposés dans la barre de boutons, `(libellé affiché, mode stocké)`.
#: Même contrat que `CHOIX_RESOLUTION_ANALYSE` dans le panneau de réglages.
CHOIX_THEME: tuple[tuple[str, str], ...] = (
    ("Sombre", "sombre"),
    ("Clair", "clair"),
    ("Bleu marine", "marine"),
    ("Suivre le système", "systeme"),
)

#: Mémoire du mode de thème, entre deux lancements. Relatif au dossier
#: courant, comme les profils et la mémoire de dossier vidéo.
FICHIER_MEMOIRE_THEME = pathlib.Path("config") / "local_theme.json"

# Feuilles de style Qt. Ce sont des quasi-CSS : les sélecteurs s'appliquent
# par nom de classe Qt (`QPushButton`) ou par `objectName` (`#compteur`), que
# l'IHM fixe via `setObjectName`.
#
# Les couleurs sont en RVB, comme le reste du projet (OpenCV travaille en BGR,
# mais Qt n'a rien à voir avec la frame).
STYLE_SOMBRE = """
QWidget { background-color: #14161a; color: #e6e6e6; font-size: 13px; }
/* Les libellés laissent voir la carte qui les porte : la règle QWidget
   ci-dessus peint un rectangle de fond de fenêtre, qui devenait une bande
   plus sombre sur les cartes dès qu'elles ont eu leur propre fond. */
QLabel { background-color: transparent; }
/* Boutons : coins marqués, air. « Lancer » (#primaire) est le seul bouton à
   pleine intensité — plus grand, plus gras ; les autres sont secondaires. */
QPushButton {
    background-color: #262a31; border: 1px solid #3a4048; border-radius: 8px;
    padding: 8px 16px;
}
QPushButton:hover { background-color: #31363f; border-color: #454c56; }
QPushButton:disabled { color: #6b7280; border-color: #2a2e35; background-color: #1e2127; }
QPushButton#primaire {
    background-color: #2563eb; border-color: #2563eb; color: #ffffff;
    font-size: 14px; font-weight: 600; padding: 9px 26px;
}
QPushButton#primaire:hover { background-color: #1d4ed8; border-color: #1d4ed8; }
QPushButton#primaire:disabled { background-color: #1e3a8a; border-color: #1e3a8a; color: #8fa3d0; }
/* Groupes de réglages en cartes : fond détaché, coins, air intérieur. Le
   titre porte le fond de fenêtre pour couper la bordure qu'il chevauche. */
QGroupBox {
    background-color: #1b1f26; border: 1px solid #2b3038; border-radius: 10px;
    margin-top: 18px; padding: 14px 12px 12px;
}
QGroupBox::title {
    subcontrol-origin: margin; left: 12px; padding: 0 6px;
    color: #9aa3af; font-weight: 600; background-color: #14161a;
}
/* Champs : même traitement que les cartes, focus au bleu primaire. */
QComboBox, QSpinBox, QDoubleSpinBox {
    background-color: #1b1f26; color: #e6e6e6;
    border: 1px solid #2b3038; border-radius: 6px; padding: 5px 8px;
}
QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover { border-color: #454c56; }
QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus { border-color: #2563eb; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView {
    background-color: #1b1f26; color: #e6e6e6; border: 1px solid #3a4048;
    selection-background-color: #2563eb; selection-color: #ffffff; outline: none;
}
/* Info-bulles et barres de défilement : le thème sombre ne s'arrête pas au
   bord des widgets. */
QToolTip {
    background-color: #1e2127; color: #e6e6e6; border: 1px solid #3a4048; padding: 5px;
}
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #333a44; border-radius: 5px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #454c56; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: #333a44; border-radius: 5px; min-width: 30px; }
QScrollBar::handle:horizontal:hover { background: #454c56; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: none; }
QSlider::groove:horizontal { height: 5px; background: #2b3038; border-radius: 2px; }
QSlider::handle:horizontal {
    background: #2563eb; width: 15px; margin: -6px 0; border-radius: 7px;
}
/* Le compteur : le seul chiffre lu de loin. Très grand, gras, sur une tuile
   qui le détache du reste de la colonne. */
QLabel#compteur {
    font-size: 76px; font-weight: 700; color: #4ade80;
    background-color: #1b1f26; border: 1px solid #2b3038; border-radius: 14px;
    padding: 2px 20px;
}
QLabel#compteur_titre {
    font-size: 13px; color: #9aa3af; letter-spacing: 3px; font-weight: 600;
}
QLabel#sous_titre { color: #9ca3af; }
/* Rappel « 0 compté : vérifie le sens ». Ambre, pas rouge : c'est un
   conseil, pas une erreur, et du rouge concurrencerait le flash de comptage
   et le bouton primaire. Gras pour sauter aux yeux sans être une alerte. */
QLabel#avertissement {
    color: #fbbf24; font-weight: 600; padding-top: 4px;
}
/* Aide sous un réglage : volontairement en petit et gris. Elle est lue de
   près, jamais de loin — le seul chiffre lu de loin reste le compteur. Elle
   n'est visible que lorsque le bouton « Aide » est actionné (tâche 18). */
QLabel#aide_reglage {
    color: #8b929c; font-size: 11px; padding-bottom: 4px;
}
/* Le bouton « Aide » : un bouton PLAT, sans bordure ni fond — déplier la
   documentation n'est pas l'action principale de l'écran, « Lancer » garde
   cette place. */
QPushButton#bouton_aide {
    color: #9ca3af; text-align: left; padding: 4px 6px;
    border: none; background: transparent;
}
QPushButton#bouton_aide:hover { color: #e5e7eb; }
QPushButton#bouton_aide:checked { color: #e5e7eb; }
/* Titre d'un réglage situé HORS du panneau (la vitesse de présentation, sous
   la barre de boutons). Même aspect que les autres titres, pour que le
   curseur ne paraisse pas étranger. */
QLabel#libelle_reglage { color: #9aa3af; }
/* Récapitulatif de fin d'analyse : titre neutre, valeurs en clair. Le titre
   reste dans le gris des titres de section — « Analyse terminée » est un
   constat, pas une annonce, et ne doit pas attirer plus l'œil que le total
   qu'il introduit. */
QLabel#recap_titre { font-size: 14px; color: #9aa3af; letter-spacing: 1px; }
QLabel#recap_libelle { color: #9ca3af; }
QLabel#recap_valeur { color: #e6e6e6; }
QProgressBar {
    border: 1px solid #2b3038; border-radius: 6px; text-align: center; height: 20px;
}
QProgressBar::chunk { background-color: #2563eb; border-radius: 5px; }
"""

# Thème clair : mêmes sélecteurs, mêmes espacements, palette inversée. Les
# gris sont calés sur la palette Tailwind (gray-50 pour le fond, gray-700/800
# pour le texte) ; l'accent bleu et le vert du compteur sont ajustés pour
# garder un contraste WCAG AA sur fond clair (voir l'en-tête du module).
STYLE_CLAIR = """
QWidget { background-color: #f5f6f8; color: #1f2430; font-size: 13px; }
QLabel { background-color: transparent; }
QPushButton {
    background-color: #ffffff; border: 1px solid #d3d7de; border-radius: 8px;
    padding: 8px 16px;
}
QPushButton:hover { background-color: #eceff3; border-color: #b9bfc9; }
QPushButton:disabled { color: #9aa1ab; border-color: #e3e6ea; background-color: #f0f2f5; }
QPushButton#primaire {
    background-color: #2563eb; border-color: #2563eb; color: #ffffff;
    font-size: 14px; font-weight: 600; padding: 9px 26px;
}
QPushButton#primaire:hover { background-color: #1d4ed8; border-color: #1d4ed8; }
QPushButton#primaire:disabled { background-color: #a8c3f5; border-color: #a8c3f5; color: #ffffff; }
QGroupBox {
    background-color: #ffffff; border: 1px solid #e3e7ec; border-radius: 10px;
    margin-top: 18px; padding: 14px 12px 12px;
}
QGroupBox::title {
    subcontrol-origin: margin; left: 12px; padding: 0 6px;
    color: #5b6472; font-weight: 600; background-color: #f5f6f8;
}
QComboBox, QSpinBox, QDoubleSpinBox {
    background-color: #ffffff; color: #1f2430;
    border: 1px solid #d3d7de; border-radius: 6px; padding: 5px 8px;
}
QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover { border-color: #b9bfc9; }
QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus { border-color: #2563eb; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView {
    background-color: #ffffff; color: #1f2430; border: 1px solid #d3d7de;
    selection-background-color: #2563eb; selection-color: #ffffff; outline: none;
}
QToolTip {
    background-color: #ffffff; color: #1f2430; border: 1px solid #d3d7de; padding: 5px;
}
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #c9ced6; border-radius: 5px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #b3bac4; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: #c9ced6; border-radius: 5px; min-width: 30px; }
QScrollBar::handle:horizontal:hover { background: #b3bac4; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: none; }
QSlider::groove:horizontal { height: 5px; background: #dfe3e8; border-radius: 2px; }
QSlider::handle:horizontal {
    background: #2563eb; width: 15px; margin: -6px 0; border-radius: 7px;
}
QLabel#compteur {
    font-size: 76px; font-weight: 700; color: #15803d;
    background-color: #ffffff; border: 1px solid #e3e7ec; border-radius: 14px;
    padding: 2px 20px;
}
QLabel#compteur_titre {
    font-size: 13px; color: #5b6472; letter-spacing: 3px; font-weight: 600;
}
QLabel#sous_titre { color: #5f6673; }
QLabel#avertissement {
    color: #b45309; font-weight: 600; padding-top: 4px;
}
QLabel#aide_reglage {
    color: #6b7280; font-size: 11px; padding-bottom: 4px;
}
QPushButton#bouton_aide {
    color: #5b6472; text-align: left; padding: 4px 6px;
    border: none; background: transparent;
}
QPushButton#bouton_aide:hover { color: #1f2430; }
QPushButton#bouton_aide:checked { color: #1f2430; }
QLabel#libelle_reglage { color: #5b6472; }
QLabel#recap_titre { font-size: 14px; color: #5b6472; letter-spacing: 1px; }
QLabel#recap_libelle { color: #5f6673; }
QLabel#recap_valeur { color: #1f2430; }
QProgressBar {
    border: 1px solid #e3e7ec; border-radius: 6px; text-align: center; height: 20px;
}
QProgressBar::chunk { background-color: #2563eb; border-radius: 5px; }
"""

# Thème bleu marine (demande opérateur, 04/11) : même structure que le sombre,
# palette calée sur les bleus profonds (Tailwind slate/blue). Le vert du
# compteur (#4ade80) garde ~9:1 de contraste sur le marine ; le bleu primaire
# est éclairci (#3b82f6) pour se détacher du fond qui est déjà bleu.
STYLE_MARINE = """
QWidget { background-color: #0f172a; color: #e2e8f0; font-size: 13px; }
QLabel { background-color: transparent; }
QPushButton {
    background-color: #1e293b; border: 1px solid #334155; border-radius: 8px;
    padding: 8px 16px;
}
QPushButton:hover { background-color: #273449; border-color: #475569; }
QPushButton:disabled { color: #64748b; border-color: #26334a; background-color: #172136; }
QPushButton#primaire {
    background-color: #3b82f6; border-color: #3b82f6; color: #ffffff;
    font-size: 14px; font-weight: 600; padding: 9px 26px;
}
QPushButton#primaire:hover { background-color: #2563eb; border-color: #2563eb; }
QPushButton#primaire:disabled { background-color: #1e3a8a; border-color: #1e3a8a; color: #93a6d9; }
QGroupBox {
    background-color: #16213a; border: 1px solid #2c3a52; border-radius: 10px;
    margin-top: 18px; padding: 14px 12px 12px;
}
QGroupBox::title {
    subcontrol-origin: margin; left: 12px; padding: 0 6px;
    color: #94a3b8; font-weight: 600; background-color: #0f172a;
}
QComboBox, QSpinBox, QDoubleSpinBox {
    background-color: #16213a; color: #e2e8f0;
    border: 1px solid #2c3a52; border-radius: 6px; padding: 5px 8px;
}
QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover { border-color: #475569; }
QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus { border-color: #3b82f6; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView {
    background-color: #16213a; color: #e2e8f0; border: 1px solid #334155;
    selection-background-color: #3b82f6; selection-color: #ffffff; outline: none;
}
QToolTip {
    background-color: #1e293b; color: #e2e8f0; border: 1px solid #334155; padding: 5px;
}
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #334155; border-radius: 5px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #475569; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: #334155; border-radius: 5px; min-width: 30px; }
QScrollBar::handle:horizontal:hover { background: #475569; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: none; }
QSlider::groove:horizontal { height: 5px; background: #2c3a52; border-radius: 2px; }
QSlider::handle:horizontal {
    background: #3b82f6; width: 15px; margin: -6px 0; border-radius: 7px;
}
QLabel#compteur {
    font-size: 76px; font-weight: 700; color: #4ade80;
    background-color: #16213a; border: 1px solid #2c3a52; border-radius: 14px;
    padding: 2px 20px;
}
QLabel#compteur_titre {
    font-size: 13px; color: #94a3b8; letter-spacing: 3px; font-weight: 600;
}
QLabel#sous_titre { color: #94a3b8; }
QLabel#avertissement {
    color: #fbbf24; font-weight: 600; padding-top: 4px;
}
QLabel#aide_reglage {
    color: #7d8aa0; font-size: 11px; padding-bottom: 4px;
}
QPushButton#bouton_aide {
    color: #94a3b8; text-align: left; padding: 4px 6px;
    border: none; background: transparent;
}
QPushButton#bouton_aide:hover { color: #e2e8f0; }
QPushButton#bouton_aide:checked { color: #e2e8f0; }
QLabel#libelle_reglage { color: #94a3b8; }
QLabel#recap_titre { font-size: 14px; color: #94a3b8; letter-spacing: 1px; }
QLabel#recap_libelle { color: #94a3b8; }
QLabel#recap_valeur { color: #e2e8f0; }
QProgressBar {
    border: 1px solid #2c3a52; border-radius: 6px; text-align: center; height: 20px;
}
QProgressBar::chunk { background-color: #3b82f6; border-radius: 5px; }
"""

#: Styles par mode RÉEL — la clé « systeme » n'existe pas ici : elle est
#: résolue en sombre ou clair par `mode_reel` avant toute application.
STYLES: dict[str, str] = {
    "sombre": STYLE_SOMBRE,
    "clair": STYLE_CLAIR,
    "marine": STYLE_MARINE,
}


def lire_modele_theme() -> str:
    """Mode de thème mémorisé, ou `MODE_DEFAUT` si rien de valide.

    Toute illisibilité — fichier absent, JSON cassé, mode inconnu — rend le
    défaut, pas une erreur : le choix d'un thème est un confort, jamais une
    condition au démarrage. Un mode inconnu (fichier écrit à la main, retour
    arrière de version) retombe silencieusement sur le défaut plutôt que de
    bloquer le lancement.
    """
    try:
        donnees = json.loads(FICHIER_MEMOIRE_THEME.read_text(encoding="utf-8"))
        mode = str(donnees.get("mode", ""))
        return mode if mode in MODES else MODE_DEFAUT
    except (OSError, ValueError, AttributeError):
        return MODE_DEFAUT


def ecrire_modele_theme(mode: str) -> None:
    """Mémorise ``mode`` pour le prochain lancement. N'échoue jamais.

    Un mode hors `MODES` est ignoré (loggé) plutôt qu'écrit : le fichier est
    relu à chaque démarrage, y écrire un invalide c'est planter le prochain
    lancement de façon différée. Un souci d'écriture (dossier protégé, disque
    plein) est loggé et ignoré — comme pour la mémoire de dossier vidéo.
    """
    if mode not in MODES:
        log.warning("mode de thème invalide ignoré : %r", mode)
        return
    try:
        FICHIER_MEMOIRE_THEME.parent.mkdir(parents=True, exist_ok=True)
        FICHIER_MEMOIRE_THEME.write_text(
            json.dumps({"mode": mode}, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError as exc:
        log.warning("thème non mémorisé : %s", exc)


def mode_reel(mode: str, hints=None) -> str:
    """Résout ``mode`` en un thème réellement appliquable.

    « sombre » et « clair » passent tels quels. « systeme » interroge les
    `QStyleHints` de Qt (thème Windows) et retombe sur `MODE_DEFAUT` si
    l'information n'est pas disponible — `hints` permet d'injecter un faux
    dans les tests, sans QApplication réelle.
    """
    if mode == "clair":
        return "clair"
    if mode == "marine":
        return "marine"
    if mode == "sombre":
        return "sombre"
    if mode == "systeme":
        if hints is None:
            try:
                from PySide6.QtWidgets import QApplication

                app = QApplication.instance()
                if app is None:
                    return MODE_DEFAUT
                hints = app.styleHints()
            except Exception as exc:  # noqa: BLE001 — Qt peut être absent ou cassé
                log.warning("thème système indéterminable : %s", exc)
                return MODE_DEFAUT
        try:
            from PySide6.QtCore import Qt

            if hints.colorScheme() == Qt.ColorScheme.Light:
                return "clair"
        except Exception as exc:  # noqa: BLE001 — Qt < 6.5 ou plateforme muette
            log.warning("thème système non lu : %s", exc)
            return MODE_DEFAUT
        return "sombre"
    log.warning("mode de thème inconnu : %r — défaut appliqué", mode)
    return MODE_DEFAUT


def appliquer_style(app, mode: str = MODE_DEFAUT) -> None:
    """Applique le thème ``mode`` à l'application Qt.

    À appeler après la création de la QApplication et avant la construction
    des widgets — puis à chaque changement de mode dans la barre de boutons
    (`interface.app` le refait alors à chaud). Le paramètre ``app`` est laissé
    non typé : ce module n'importe PySide6 qu'à la demande.
    """
    app.setStyleSheet(STYLES[mode_reel(mode)])
