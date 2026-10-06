"""Shell construction and nav behavior (offscreen Qt)."""

import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"  # must be set before any PySide6 import

import pytest
from PySide6.QtWidgets import QApplication

from ball_buddy.pathing import resolve_data_dir
from ball_buddy.ui.shell import NAV_ITEMS, MainWindow


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_nav_labels_in_order(qapp: QApplication) -> None:
    window = MainWindow()
    assert [b.text() for b in window.nav_group.buttons()] == list(NAV_ITEMS)
    assert len(NAV_ITEMS) == 6


def test_draft_selected_by_default(qapp: QApplication) -> None:
    window = MainWindow()
    assert window.stack.currentIndex() == NAV_ITEMS.index("Draft")
    draft_button = window.nav_group.button(NAV_ITEMS.index("Draft"))
    assert draft_button is not None and draft_button.isChecked()


def test_data_dir_and_window_icon(qapp: QApplication) -> None:
    window = MainWindow()
    assert window.data_dir == resolve_data_dir()
    assert not window.windowIcon().pixmap(16, 16).isNull()


def test_click_league_switches_stack(qapp: QApplication) -> None:
    window = MainWindow()
    league_button = window.nav_group.button(NAV_ITEMS.index("League"))
    assert league_button is not None
    league_button.click()
    assert window.stack.currentIndex() == NAV_ITEMS.index("League")


def test_dark_toggle_applies_and_persists_theme(qapp, tmp_path, monkeypatch) -> None:
    import ball_buddy.ui.shell as shell

    # Never touch the real data dir: point the shell at a sandbox.
    monkeypatch.setattr(shell, "resolve_data_dir", lambda: tmp_path)
    window = MainWindow()
    assert window.theme_toggle.isChecked() is False
    window.theme_toggle.setChecked(True)
    assert "#1B1913" in qapp.styleSheet()  # dark canvas
    assert window.sync_service.settings()["dark_mode"] is True
    # back to light
    window.theme_toggle.setChecked(False)
    assert "#F5EFE0" in qapp.styleSheet()
    assert window.sync_service.settings()["dark_mode"] is False


def test_theme_built_from_both_palettes() -> None:
    from ball_buddy.ui import theme

    for name in ("light", "dark"):
        style = theme._style(theme.THEMES[name])
        assert "banner-danger" in style
        assert theme.THEMES[name]["outline"] in style


def test_clicking_every_nav_item_switches_stack(qapp: QApplication) -> None:
    window = MainWindow()
    for index, _label in enumerate(NAV_ITEMS):
        button = window.nav_group.button(index)
        assert button is not None
        button.click()
        assert window.stack.currentIndex() == index
