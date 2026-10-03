"""DraftBoard (M2.2) tests: offscreen Qt, 2-team fixture (Red, Blue)."""

import os
import sys
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"  # must be set before any PySide6 import

import pytest
from PySide6.QtWidgets import QApplication

from ball_buddy.domain import picks as picks_mod
from ball_buddy.domain.keepers import KeeperEntry
from ball_buddy.io.pool.importer import FIELDNAMES, write_csv
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


def make_service(tmp_path: Path) -> SyncService:
    service = SyncService(tmp_path, client=YahooClient(FakeQuery(), "k", "s"))
    service.save_settings({"league_id": "1234"})
    return service


def save_fixture_snapshot(service: SyncService) -> None:
    # fixture teams: (100, Red), (200, Blue) with live order [100, 200]
    save_snapshot(to_snapshot(load_results(), "1234"), service.snapshot_path)


def write_pool(service: SyncService, rows: list[dict[str, str]]) -> None:
    records = [{f: "" for f in FIELDNAMES} for _ in rows]
    for record, values in zip(records, rows):
        record.update(values)
    write_csv(records, service.pool_path)


def make_board(tmp_path: Path, keepers: list[KeeperEntry]) -> DraftBoard:
    service = make_service(tmp_path)
    save_fixture_snapshot(service)
    return DraftBoard(service, keepers)


def test_grid_shape_and_keeper_forfeit(qapp, tmp_path):
    board = make_board(tmp_path, [KeeperEntry("Red", "Big Keeper", 1)])
    assert board.grid.rowCount() == 13
    assert board.grid.columnCount() == 2
    assert board.start_order == ["Red", "Blue"]
    # round 1: col 0 = Red (forfeited), col 1 = Blue (current)
    assert board.grid.item(0, 0).text() == "Keeper: Big Keeper"
    assert board.grid.item(0, 1).text() == ""
    assert (board.grid.currentRow(), board.grid.currentColumn()) == (0, 1)
    assert "pick 2 of 2" in board.current_label.text()
    assert board.current_label.text().startswith("Round 1,")
    assert board.current_label.text().endswith("overall 2/26")
    assert board.name_edit.completer() is not None
    assert board.grid.item(1, 0).text() == ""  # round 2 snakes right-to-left


def test_even_round_keeper_forfeit_shows_keeper_name(qapp, tmp_path):
    # keeper on Red at cost round 2 (even): snake order is reversed, so Red
    # is order 2 (col 1), not order 1 — the cell must show the keeper name.
    board = make_board(tmp_path, [KeeperEntry("Red", "Even Keeper", 2)])
    assert board.grid.item(1, 1).text() == "Keeper: Even Keeper"
    # commit round 1, then the forfeited pick (R2 order 2, overall 3) is
    # skipped: current is round 2 order 1 (Blue, col 0), overall 3/26
    board.name_edit.setText("Some Player")
    board.commit_button.click()
    board.name_edit.setText("Other Player")
    board.commit_button.click()
    assert (board.grid.currentRow(), board.grid.currentColumn()) == (1, 0)
    assert "overall 3/26" in board.current_label.text()


def test_opted_out_keeper_leaves_even_round_pick_open(qapp, tmp_path):
    board = make_board(
        tmp_path, [KeeperEntry("Red", "Out Keeper", 2, opted_out=True)]
    )
    assert board.grid.item(1, 1).text() == ""
    assert board._keeper_cells == {}


def test_commit_writes_file_and_advances(qapp, tmp_path):
    board = make_board(tmp_path, [KeeperEntry("Red", "Big Keeper", 1)])
    write_pool(board.service, [{"name": "Nikola Jokic"}, {"name": "Ghost Player"}])
    board.refresh()
    board.name_edit.setText("Nikola Jokic")
    board.commit_button.click()
    # persisted
    saved = picks_mod.load(board.picks_path)
    assert saved == [picks_mod.DraftPick(1, 2, "Blue", "Nikola Jokic")]
    # cell shows the name; current advanced to round 2 pick 1 (overall 3)
    assert board.grid.item(0, 1).text() == "Nikola Jokic"
    assert (board.grid.currentRow(), board.grid.currentColumn()) == (1, 0)
    assert "Round 2, pick 1 of 2" in board.current_label.text()
    assert "overall 3/26" in board.current_label.text()
    assert board.name_edit.text() == ""


def test_commit_rejects_empty_and_already_picked(qapp, tmp_path):
    board = make_board(tmp_path, [])
    board.name_edit.setText("")
    board.commit_button.click()
    assert board.picks == []
    assert "Enter a player name" in board.alert_banner.text()
    board.name_edit.setText("Some Player")
    board.commit_button.click()
    board.name_edit.setText("Some Player")
    board.commit_button.click()
    assert len(board.picks) == 1
    assert "already drafted" in board.alert_banner.text()


def test_undo_drops_last_pick(qapp, tmp_path):
    board = make_board(tmp_path, [])
    write_pool(board.service, [{"name": "Nikola Jokic"}])
    board.refresh()
    board.name_edit.setText("Nikola Jokic")
    board.commit_button.click()
    assert picks_mod.load(board.picks_path)
    board.undo_button.click()
    saved = picks_mod.load(board.picks_path)
    assert saved == []
    assert board.grid.item(0, 0).text() == ""
    assert (board.grid.currentRow(), board.grid.currentColumn()) == (0, 0)
    board.undo_button.click()  # no-op on empty picks, no crash


def test_picked_cell_shows_pool_value(qapp, tmp_path):
    board = make_board(tmp_path, [])
    write_pool(
        board.service,
        [
            {"name": "Nikola Jokic", "value": "82.5"},
            {"name": "Ghost Player"},
        ],
    )
    board.refresh()
    board.name_edit.setText("Jokic")  # containment-bridges to pool name
    board.commit_button.click()
    # cell shows the entered name plus the bridged pool value
    assert board.grid.item(0, 0).text() == "Jokic (82.5)"
    # unbridged pick without a value shows the raw name only
    board.name_edit.setText("Zed Zederson")
    board.commit_button.click()
    assert board.grid.item(0, 1).text() == "Zed Zederson"
    assert "did not match the pool" in board.alert_banner.text()


def test_no_snapshot_shows_alert(qapp, tmp_path):
    service = make_service(tmp_path)
    board = DraftBoard(service, [])
    assert board.grid.rowCount() == 0
    assert "Sync the league first" in board.alert_banner.text()
    assert not board.alert_banner.isHidden()
    assert not board.commit_button.isEnabled()


def test_draft_view_embeds_board(qapp, tmp_path):
    view = DraftView(make_service(tmp_path))
    save_fixture_snapshot(view.service)
    view.refresh()
    assert isinstance(view.board, DraftBoard)
    assert view.board.grid.rowCount() == 13
    assert view.board.grid.columnCount() == 2
    # re-rendering with the same teams + keepers reuses the board
    same_board = view.board
    view.refresh()
    assert view.board is same_board
    # no-snapshot path also shows the board (alert banner only)
    view.service.snapshot_path.unlink()
    view.refresh()
    assert "Sync the league first" in view.board.alert_banner.text()


def test_board_keeps_loaded_picks_when_file_corrupt(qapp, tmp_path):
    board = make_board(tmp_path, [])
    write_pool(board.service, [{"name": "Nikola Jokic"}])
    board.refresh()
    board.name_edit.setText("Nikola Jokic")
    board.commit_button.click()
    board.picks_path.write_text("not json", encoding="utf-8")
    board.refresh()
    # falls back to the last loaded picks, banner explains why
    assert [p.player for p in board.picks] == ["Nikola Jokic"]
    assert "draft_picks.json" in board.alert_banner.text()
