"""theme.stat_color unit tests (no app needed beyond a QGuiApplication)."""

import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"  # must be set before any PySide6 import

from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from ball_buddy.ui.theme import stat_color  # noqa: E402

app = QApplication.instance() or QGuiApplication([])


def _rgb(color) -> tuple[int, int, int]:
    return (color.red(), color.green(), color.blue())


def test_neutral_band_is_transparent():
    # z within roughly [-0.13, 0.13] -> 45-55th percentile -> uncolored
    for z in (-0.1, 0.0, 0.1, 0.12):
        color = stat_color(z)
        assert color.alpha() == 0, z
        assert stat_color(z, theme="dark").alpha() == 0


def test_extremes_hit_endpoints():
    best = stat_color(3.0)  # ~99.87th percentile -> full light endpoint
    assert _rgb(best) == (0x14, 0x59, 0x00)
    worst = stat_color(-3.0)  # ~0.13th percentile -> full light endpoint
    assert _rgb(worst) == (0x50, 0x00, 0x00)
    # dark endpoints are the lighter #4ade80-class pair
    best_dark = stat_color(3.0, theme="dark")
    assert _rgb(best_dark) == (0x4A, 0xDE, 0x80)
    worst_dark = stat_color(-3.0, theme="dark")
    assert _rgb(worst_dark) == (0xF8, 0x71, 0x71)


def test_moderate_values_sit_between_endpoint_and_pale():
    mid = stat_color(1.5)  # ~93rd percentile
    assert mid.alpha() != 0
    r, g, b = _rgb(mid)
    assert g > r and g > b
    # reddish side: r > g
    low = stat_color(-1.5)
    r2, g2, b2 = _rgb(low)
    assert r2 > g2


def test_lower_is_better_flips_direction():
    # low turnovers = good: raw z_to is NOT sign-corrected, so negative
    # raw z (low TO) with the flip must read green, positive reads red.
    good = stat_color(-1.5, lower_is_better=True)
    assert good.green() > good.red()
    bad = stat_color(1.5, lower_is_better=True)
    assert bad.red() > bad.green()
    # and neutral still transparent under the flip
    assert stat_color(0.0, lower_is_better=True).alpha() == 0


def test_band_boundaries_color_just_outside():
    assert stat_color(0.13).alpha() != 0
    assert stat_color(-0.13).alpha() != 0
