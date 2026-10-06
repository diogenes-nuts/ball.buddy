"""DraftView tests: embedded board, Setup pointer, offline banner.

Keeper entry now lives in SetupDialog (tests/ui/test_setup_dialog.py); this
view only hosts the board + banners.
"""

import os
import sys
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"  # must be set before any PySide6 import

import pytest
from PySide6.QtWidgets import QApplication

from ball_buddy.domain import keepers as keepers_mod
from ball_buddy.io.yahoo.client import YahooClient
from ball_buddy.io.yahoo.snapshot import save_snapshot, to_snapshot
from ball_buddy.services.sync import SyncService
from ball_buddy.ui.views.board import DraftBoard
from ball_buddy.ui.views.draft import DraftView

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tests.io.test_snapshot import load_results  # noqa: E402
from tests.io.test_yahoo_client import FakeQuery  # noqa: E402


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    return QApplication.instance() or QApplication([])


def make_view(tmp_path: Path) -> DraftView:
    service = SyncService(tmp_path, client=YahooClient(FakeQuery(), "k", "s"))
    service.save_settings({"league_id": "1234"})
    return DraftView(service)


def save_fixture_snapshot(service: SyncService) -> None:
    save_snapshot(to_snapshot(load_results(), "1234"), service.snapshot_path)


def test_view_embeds_board_and_setup_button(qapp, tmp_path):
    view = make_view(tmp_path)
    save_fixture_snapshot(view.service)
    view.refresh()
    assert isinstance(view.board, DraftBoard)
    assert view.board.grid.rowCount() == 13
    assert view.board.grid.columnCount() == 2
    assert view.board.setup_button.text() == "Setup…"
    # re-rendering with the same teams + keepers reuses the board
    same_board = view.board
    view.refresh()
    assert view.board is same_board
    # no-snapshot path also shows the board (alert banner only)
    view.service.snapshot_path.unlink()
    view.refresh()
    assert "Sync the league first" in view.board.alert_banner.text()


def test_no_snapshot_shows_banner(qapp, tmp_path):
    view = make_view(tmp_path)
    assert "Sync the league first" in view.alert_banner.text()
    assert view.alert_banner.objectName() == "banner-danger"
    assert not view.alert_banner.isHidden()


def test_saved_keepers_flow_into_board(qapp, tmp_path):
    view = make_view(tmp_path)
    save_fixture_snapshot(view.service)
    keepers_mod.save(
        [keepers_mod.KeeperEntry("Red", "Big Keeper", 1)], view.keepers_path
    )
    view.refresh()
    assert view.board.keepers == [keepers_mod.KeeperEntry("Red", "Big Keeper", 1)]
    assert view.board.grid.item(0, 0).text() == "Keeper: Big Keeper"


def test_over_cap_keeper_dropped_from_board(qapp, tmp_path):
    view = make_view(tmp_path)
    save_fixture_snapshot(view.service)
    keepers_mod.save(
        [
            keepers_mod.KeeperEntry("Red", "One", 1),
            keepers_mod.KeeperEntry("Red", "Two", 2),
            keepers_mod.KeeperEntry("Red", "Three", 3),
        ],
        view.keepers_path,
    )
    view.refresh()
    assert [e.player for e in view.board.keepers] == ["One", "Two"]
    assert "exceeds 2 per team" in view.alert_banner.text()
    assert "Three (Red)" in view.alert_banner.text()


# -- offline manual team list -------------------------------------------------


def make_manual_view(tmp_path: Path) -> DraftView:
    service = SyncService(tmp_path, client=YahooClient(FakeQuery(), "k", "s"))
    settings = service.settings()
    settings["manual_teams"] = ["Alpha", "Beta"]
    service.save_settings(settings)
    return DraftView(service)


def test_manual_teams_render_offline_board(qapp, tmp_path):
    view = make_manual_view(tmp_path)
    assert view.teams == ["Alpha", "Beta"]
    assert not view.offline_banner.isHidden()
    assert "manual team list" in view.offline_banner.text()
    assert view.board is not None
    assert view.board.start_order == ["Alpha", "Beta"]
