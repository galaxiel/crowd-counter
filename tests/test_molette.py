"""La molette fait DÉFILER le panneau, elle ne change pas les champs.

Constat opérateur (05/11/2026) : en descendant les réglages à la molette,
chaque champ survolé changeait de valeur (comportement natif de Qt) — un
réglage faussé sans le vouloir. Désormais un champ ne réagit à la molette
que s'il a le focus ; sinon l'événement est transmis à la zone défilante.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QWheelEvent  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QComboBox,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from interface.app import _MoletteChamps  # noqa: E402


@pytest.fixture
def application():
    return QApplication.instance() or QApplication([])


def _molette(delta_y: int) -> QWheelEvent:
    return QWheelEvent(
        QPointF(5.0, 5.0),
        QPointF(5.0, 5.0),
        QPoint(0, 0),
        QPoint(0, delta_y),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )


@pytest.fixture
def panneau_defilant(application):
    """Une zone défilante avec du contenu assez haut pour défiler."""
    zone = QScrollArea()
    contenu = QWidget()
    v = QVBoxLayout(contenu)
    v.addSpacing(600)
    spin = QSpinBox()
    spin.setRange(0, 1000)
    v.addWidget(spin)
    combo = QComboBox()
    combo.addItems(["a", "b", "c"])
    v.addWidget(combo)
    v.addSpacing(600)
    zone.setWidget(contenu)
    zone.setWidgetResizable(True)
    zone.resize(300, 400)
    filtre = _MoletteChamps(zone)
    for champ in (spin, combo):
        champ.installEventFilter(filtre)
    zone.show()
    application.processEvents()
    yield zone, spin, combo
    zone.close()


def test_molette_sans_focus_fait_defiler_le_panneau(application, panneau_defilant):
    zone, spin, _combo = panneau_defilant
    spin.clearFocus()
    application.processEvents()
    assert not spin.hasFocus()
    valeur_avant = spin.value()
    barre_avant = zone.verticalScrollBar().value()

    QApplication.sendEvent(spin, _molette(-120))

    assert spin.value() == valeur_avant, "la molette a changé le champ !"
    assert zone.verticalScrollBar().value() > barre_avant, "le panneau n'a pas défilé"


def test_molette_sur_un_champ_actif_change_sa_valeur(application, panneau_defilant):
    """Champ AYANT le focus (l'opérateur a cliqué dedans) : la molette règle
    le champ, comportement natif conservé là où elle a du sens."""
    zone, spin, _combo = panneau_defilant
    spin.setValue(500)
    spin.setFocus()
    application.processEvents()
    valeur_avant = spin.value()

    QApplication.sendEvent(spin, _molette(-120))

    assert spin.value() != valeur_avant


def test_molette_sur_une_liste_sans_focus_ne_la_change_pas(
    application, panneau_defilant
):
    zone, _spin, combo = panneau_defilant
    index_avant = combo.currentIndex()

    QApplication.sendEvent(combo, _molette(-120))

    assert combo.currentIndex() == index_avant
