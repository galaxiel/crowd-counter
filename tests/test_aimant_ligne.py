"""Le magnétisme du tracé de ligne (interface.app.aimanter_second_point).

Demande opérateur (05/11/2026) : une ligne tracée à la main qui frôle
l'horizontale ou la verticale restait penchée de 1-2°, et la zone de
détection (rectangle droit) divergeait du dessin. À moins de 3°, le second
point se recale exactement ; au-delà, le tracé libre est respecté.
"""

from __future__ import annotations

import math

from interface.app import TOLERANCE_AIMANT_DEGRES, aimanter_second_point


def test_quasi_horizontal_se_recale():
    p2 = aimanter_second_point((100.0, 200.0), (600.0, 206.0))
    assert p2 == (600.0, 200.0)  # dy annulé : ligne exactement horizontale


def test_quasi_vertical_se_recale():
    p2 = aimanter_second_point((500.0, 100.0), (507.0, 600.0))
    assert p2 == (500.0, 600.0)  # dx annulé : ligne exactement verticale


def test_diagonale_volontaire_est_respectee():
    # ~26.6° : ni horizontal ni vertical, aucun recadrage.
    p2 = aimanter_second_point((0.0, 0.0), (600.0, 300.0))
    assert p2 == (600.0, 300.0)


def test_limite_de_tolerance_est_la_bonne():
    # Un tracé EXACTEMENT à la tolérance (3°) se recale encore.
    dy = 600.0 * math.tan(math.radians(TOLERANCE_AIMANT_DEGRES))
    p2 = aimanter_second_point((0.0, 0.0), (600.0, dy))
    assert p2[1] == 0.0
    # Juste au-delà, non.
    dy_beyond = 600.0 * math.tan(math.radians(TOLERANCE_AIMANT_DEGRES + 1.0))
    p3 = aimanter_second_point((0.0, 0.0), (600.0, dy_beyond))
    assert p3 == (600.0, dy_beyond)


def test_deja_aligne_ne_bouge_pas():
    assert aimanter_second_point((10.0, 10.0), (400.0, 10.0)) == (400.0, 10.0)
    assert aimanter_second_point((10.0, 10.0), (10.0, 400.0)) == (10.0, 400.0)
