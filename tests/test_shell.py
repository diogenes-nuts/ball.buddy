"""Shell construction and nav behavior (offscreen Qt)."""

import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"  # must be set before any PySide6 import

import pytest
from PySide6.QtWidgets import QApplication

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


def test_click_league_switches_stack(qapp: QApplication) -> None:
    window = MainWindow()
    league_button = window.nav_group.button(NAV_ITEMS.index("League"))
    assert league_button is not None
    league_button.click()
    assert window.stack.currentIndex() == NAV_ITEMS.index("League")
