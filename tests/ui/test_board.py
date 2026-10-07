"""DraftBoard (autodraft-oriented draft helper) tests: offscreen Qt.

Covers the strip + players table + relative + roster panels, the
recommendations rail, pick persistence/undo, and the no-snapshot /
offline-manual paths. Pick-model fixtures: 2-team live snapshot (Red,
Blue) and a 12-team manual service for league-scale panels.
"""

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
from ball_buddy.ui.views.board import DraftBoard, PlayerTableModel
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


def _recs_names(board: DraftBoard) -> list[str]:
    return [
        board.recs_grid.item(r, 1).text() for r in range(board.recs_grid.rowCount())
    ]


def _players_names(board: DraftBoard) -> list[str]:
    model = board._player_model
    return [model.name_at(r) for r in range(model.rowCount())]


# -- layout -------------------------------------------------------------------


def test_layout_no_grid_widget(qapp, tmp_path):
    board = make_board(tmp_path, [])
    assert not hasattr(board, "grid")
    assert isinstance(board._player_model, PlayerTableModel)
    assert board.player_view.model() is board._player_model
    assert board._player_model.columnCount() == 4 + 9  # base + z columns
    # relative panel: 9 columns x 4 rows
    assert board.relative_grid.columnCount() == 9
    assert board.relative_grid.rowCount() == 4
    # roster panel: Name/Pos/Value/From + 9 z columns
    assert board.roster_grid.columnCount() == 4 + 9
    # recs rail: 5 columns, top-n spin default 10, range 1-20
    assert board.recs_grid.columnCount() == 5
    assert board.top_n_spin.value() == 10
    assert (board.top_n_spin.minimum(), board.top_n_spin.maximum()) == (1, 20)
    assert board.commit_button.text() == "Commit pick"
    assert board.log_button.text() == "Log selected"


def test_strip_format(qapp, tmp_path):
    board = make_board(tmp_path, [KeeperEntry("Red", "Big Keeper", 1)])
    # Red forfeits R1 order 1 -> current is R1, overall 2/26, Blue
    assert board.current_label.text() == "R1 \u00b7 pick 2/26 \u00b7 Blue"
    assert board.name_edit.completer() is not None
    assert board.commit_button.isEnabled()
    assert not board.log_button.isEnabled()  # empty pool -> no rows to log


# -- players table + logging ----------------------------------------------------


POOL = [
    {"name": "One Aardvark", "pos": "PG", "rank": "1", "value": "99"},
    {"name": "Two Bumble", "pos": "SG", "rank": "2", "value": "90"},
    {"name": "Three Cheetah", "pos": "SF", "rank": "3", "value": "80"},
    {"name": "Four Deer", "pos": "PF", "rank": "4", "value": "70"},
    {"name": "Five Eagle", "pos": "C", "rank": "5", "value": "60"},
    {"name": "Six Fox", "pos": "PG", "rank": "6", "value": "50"},
]


def test_players_table_lists_pool_minus_excluded(qapp, tmp_path):
    board = make_board(tmp_path, [KeeperEntry("Red", "One Aardvark", 1)])
    write_pool(board.service, POOL)
    board.refresh()
    names = _players_names(board)
    assert "One Aardvark" not in names  # active keeper excluded
    assert "Two Bumble" in names
    assert len(names) == 5


def test_pos_filter(qapp, tmp_path):
    board = make_board(tmp_path, [])
    write_pool(board.service, POOL)
    board.refresh()
    assert board.pos_combo.itemText(1) == "PG"
    board.pos_combo.setCurrentText("PG")
    assert _players_names(board) == ["One Aardvark", "Six Fox"]
    board.pos_combo.setCurrentText("C")
    assert _players_names(board) == ["Five Eagle"]
    board.pos_combo.setCurrentText("All")
    assert len(_players_names(board)) == 6


def test_commit_writes_file_and_updates_panels(qapp, tmp_path):
    board = make_board(tmp_path, [KeeperEntry("Red", "One Aardvark", 1)])
    write_pool(board.service, POOL)
    board.refresh()
    board.name_edit.setText("Two Bumble")
    board.commit_button.click()
    # persisted
    saved = picks_mod.load(board.picks_path)
    assert saved == [picks_mod.DraftPick(1, 2, "Blue", "Two Bumble")]
    # strip advanced: overall 3 is round 2, reversed order -> Blue first
    assert board.current_label.text() == "R2 \u00b7 pick 3/26 \u00b7 Blue"
    # players table drops the drafted player
    assert "Two Bumble" not in _players_names(board)
    # recs rail drops it too
    assert "Two Bumble" not in _recs_names(board)
    assert board.name_edit.text() == ""


def test_log_selected_button_and_double_click(qapp, tmp_path):
    board = make_board(tmp_path, [])
    write_pool(board.service, POOL)
    board.refresh()
    # no selection: alert, nothing logged
    board.log_button.click()
    assert board.picks == []
    assert "Select a player" in board.alert_banner.text()
    # select the first row, log via the button
    board.player_view.selectRow(0)
    board.log_button.click()
    assert [p.player for p in board.picks] == ["One Aardvark"]
    # double-click logs the next selected row
    board.player_view.selectRow(0)  # model shrank: now Two Bumble
    board.player_view.doubleClicked.emit(board._player_model.index(0, 0))
    assert [p.player for p in board.picks] == ["One Aardvark", "Two Bumble"]


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
    write_pool(board.service, POOL)
    board.refresh()
    board.name_edit.setText("One Aardvark")
    board.commit_button.click()
    assert picks_mod.load(board.picks_path)
    assert "One Aardvark" not in _players_names(board)
    board.undo_button.click()
    assert picks_mod.load(board.picks_path) == []
    assert "One Aardvark" in _players_names(board)
    assert board.current_label.text() == "R1 \u00b7 pick 1/26 \u00b7 Red"
    board.undo_button.click()  # no-op on empty picks, no crash


def test_unbridged_pick_alert_and_no_value(qapp, tmp_path):
    board = make_board(tmp_path, [])
    write_pool(board.service, POOL)
    board.refresh()
    board.name_edit.setText("Jokic")  # nothing bridges
    board.commit_button.click()
    assert "did not match the pool" in board.alert_banner.text()
    assert [p.player for p in board.picks] == ["Jokic"]


# -- recommendations rail ---------------------------------------------------------


def test_recs_rail_fallback_ranking_and_top_n(qapp, tmp_path):
    # no my_team -> M2.3 fallback ranking (rank asc); top_n honored
    board = make_board(tmp_path, [KeeperEntry("Red", "One Aardvark", 1)])
    write_pool(board.service, POOL)
    board.refresh()
    assert _recs_names(board) == [
        "Two Bumble", "Three Cheetah", "Four Deer", "Five Eagle", "Six Fox",
    ]
    assert board.recs_grid.item(0, 0).text() == "1"
    assert board.recs_grid.item(0, 2).text() == "\u2014"  # no tag in fallback
    assert board.recs_grid.item(0, 3).text() == "\u2014"  # no mkt/fit bits
    assert "pool rank 2" in board.recs_grid.item(0, 4).text()
    # top-N: 3 -> only 3 rows, persisted to settings
    board.top_n_spin.setValue(3)
    assert _recs_names(board) == ["Two Bumble", "Three Cheetah", "Four Deer"]
    assert board.service.settings()["rec_top_n"] == 3
    # board built later on the same service reads the saved value
    board2 = DraftBoard(board.service, [KeeperEntry("Red", "One Aardvark", 1)])
    assert board2.top_n_spin.value() == 3
    assert len(_recs_names(board2)) == 3


def make_manual_service_12(tmp_path: Path) -> SyncService:
    service = make_service(tmp_path)
    settings = service.settings()
    settings["manual_teams"] = [
        "Alpha", "Bravo", "Charlie", "Delta", "Echo", "Foxtrot",
        "Golf", "Hotel", "India", "Juliet", "Kilo", "Lima",
    ]
    settings["my_team"] = "Alpha"
    service.save_settings(settings)
    return service


def test_recs_rail_scorer_path(qapp, tmp_path):
    service = make_manual_service_12(tmp_path)
    teams = service.settings()["manual_teams"]
    pool_rows = []
    for i, team in enumerate(teams):
        pool_rows.append(
            {
                "name": f"Player {i:02d}",
                "pos": "PG" if i % 2 == 0 else "SG",
                "rank": str(i + 1),
                "value": str(90 - i),
                "z_pts": f"{2.0 - i * 0.1:.1f}",
                "adp_round": str(i + 2.0),
            }
        )
    write_pool(service, pool_rows)
    board = DraftBoard(service, [])
    # current pick 1 (Alpha first): REACH rows have adp < 0.8, none here
    # (min adp 2.0); VALUE rows have adp > 1.25 (all do) -> VALUE chips
    assert board.recs_grid.rowCount() > 0
    first_tag = board.recs_grid.item(0, 2).text()
    assert "VALUE" in first_tag
    # mkt/fit summary parsed from the reason bits
    mkfit = board.recs_grid.item(0, 3).text()
    assert mkfit.startswith("mkt ") and "/ fit " in mkfit
    assert "mkt " in board.recs_grid.item(0, 4).text()  # verbatim reason kept
    # top_n default 10 caps the rail
    assert board.recs_grid.rowCount() <= 10


def test_recs_rail_clears_when_draft_complete(qapp, tmp_path):
    board = make_board(tmp_path, [])
    write_pool(board.service, POOL)
    board.refresh()
    for i in range(len(board.snake)):
        board.name_edit.setText(f"Filler {i}")
        board.commit_button.click()
    assert board.recs_grid.rowCount() == 0
    assert "draft complete" in board.recs_title.text()
    assert "Draft complete" in board.current_label.text()


# -- relative panel ----------------------------------------------------------------


def relative_fixture_service(tmp_path: Path) -> SyncService:
    service = make_manual_service_12(tmp_path)
    teams = service.settings()["manual_teams"]
    pool_rows = [
        {"name": "KP-Alpha", "gp": "70", "pts_pg": "12.0", "reb_pg": "0.1"}
    ]
    pool_rows += [
        {"name": f"KP-{team}", "gp": "70", "pts_pg": "1.0", "reb_pg": "10.0"}
        for team in teams[1:]
    ]
    pool_rows.append(
        {"name": "Weak Filler", "gp": "70", "pts_pg": "1.0", "reb_pg": "1.0"}
    )
    write_pool(service, pool_rows)
    return service


def test_relative_panel_rows_and_gap_colors(qapp, tmp_path):
    service = relative_fixture_service(tmp_path)
    teams = service.settings()["manual_teams"]
    keepers = [KeeperEntry(team, f"KP-{team}", 1) for team in teams]
    board = DraftBoard(service, keepers)
    assert not board.relative_panel.isHidden()
    grid = board.relative_grid
    assert grid.columnCount() == 9
    assert grid.rowCount() == 4
    # col 0 = pts: Alpha is best (840 vs 70) -> BUILD, negative gap
    assert grid.item(0, 0).text() == "840.0"  # My team row
    assert grid.item(2, 0).text().startswith("-")  # Gap row: ahead
    assert grid.item(3, 0).text() == "BUILD"
    # col 1 = reb: Alpha is worst -> PUNT, positive gap (behind)
    assert grid.item(3, 1).text() == "PUNT"
    assert grid.item(2, 1).text().startswith("+")
    # gap row stat-coloring: pts ahead -> greenish, reb behind -> reddish
    pts_bg = grid.item(2, 0).background()
    reb_bg = grid.item(2, 1).background()
    from PySide6.QtCore import Qt as _Qt

    assert pts_bg.style() == _Qt.BrushStyle.SolidPattern
    assert pts_bg.color().green() > pts_bg.color().red()
    assert reb_bg.style() == _Qt.BrushStyle.SolidPattern
    assert reb_bg.color().red() > reb_bg.color().green()
    # flat cats: neutral gap -> uncolored (default NoBrush)
    assert grid.item(3, 2).text() == "COAST"
    assert grid.item(2, 2).background().style() == _Qt.BrushStyle.NoBrush


def test_relative_panel_hidden_without_my_team(qapp, tmp_path):
    service = make_manual_service_12(tmp_path)
    settings = service.settings()
    settings["my_team"] = ""
    service.save_settings(settings)
    board = DraftBoard(service, [])
    assert board.relative_panel.isHidden()


# -- roster panel -------------------------------------------------------------------


def test_roster_default_my_team_and_flag(qapp, tmp_path):
    board = make_board(tmp_path, [])
    write_pool(board.service, POOL)
    board.refresh()
    # fixture 2-team service has no my_team -> defaults to first team
    assert board.roster_combo.currentText() == "Red"
    assert board.roster_flag.isHidden()
    board.roster_combo.setCurrentText("Blue")
    # no my_team set: flag stays hidden
    assert board.roster_flag.isHidden()

    # 12-team service WITH my_team: switch shows the amber flag
    service = make_manual_service_12(board.service.data_dir / "alt")
    write_pool(service, POOL)
    board2 = DraftBoard(service, [])
    assert board2.roster_combo.currentText() == "Alpha"
    assert board2.roster_flag.isHidden()
    board2.roster_combo.setCurrentText("Bravo")
    assert not board2.roster_flag.isHidden()
    from ball_buddy.ui.theme import THEMES

    assert THEMES["light"]["warning_bg"] in board2.roster_flag.styleSheet()
    board2.roster_combo.setCurrentText("Alpha")
    assert board2.roster_flag.isHidden()


def test_roster_lists_keepers_then_picks_in_round_order(qapp, tmp_path):
    service = make_manual_service_12(tmp_path)
    write_pool(service, POOL)
    board = DraftBoard(service, [KeeperEntry("Alpha", "One Aardvark", 1)])
    # keeper on Alpha forfeits R1 order 1; pick 2 is Bravo
    board.name_edit.setText("Two Bumble")
    board.commit_button.click()
    board.name_edit.setText("Three Cheetah")
    board.commit_button.click()  # R1 order 3 = Charlie? no: Bravo already...
    # Alpha's picks: none yet (Alpha's R1 was forfeited) -> roster = keeper only
    board.roster_combo.setCurrentText("Alpha")
    grid = board.roster_grid
    assert grid.rowCount() == 1
    assert grid.item(0, 0).text() == "One Aardvark"
    assert grid.item(0, 3).text() == "keeper R1"
    assert grid.item(0, 1).text() == "PG"  # bridged pool pos
    assert grid.item(0, 4).text() == ""  # no z in pool -> blank cell
    # Bravo got pick 2 (R1 order 2)
    board.roster_combo.setCurrentText("Bravo")
    assert grid.rowCount() == 1
    assert grid.item(0, 0).text() == "Two Bumble"
    assert grid.item(0, 3).text() == "pick R1"
    # opted-out keeper shows "(opted out)" but the pick stays open
    board3 = DraftBoard(service, [KeeperEntry("Alpha", "One Aardvark", 1, opted_out=True)])
    board3.roster_combo.setCurrentText("Alpha")
    assert board3.roster_grid.item(0, 3).text() == "keeper R1 (opted out)"


# -- no snapshot / manual mode -------------------------------------------------------


def test_no_snapshot_shows_alert(qapp, tmp_path):
    service = make_service(tmp_path)
    board = DraftBoard(service, [])
    assert board._player_model.rowCount() == 0
    assert "Sync the league first" in board.alert_banner.text()
    assert not board.alert_banner.isHidden()
    assert not board.commit_button.isEnabled()
    assert not board.log_button.isEnabled()
    assert not board.relative_panel.isVisible()
    assert not board.roster_panel.isVisible()


def test_manual_teams_render_offline_board(qapp, tmp_path):
    service = make_service(tmp_path)
    settings = service.settings()
    settings["manual_teams"] = ["Alpha", "Beta"]
    service.save_settings(settings)
    board = DraftBoard(service, [])
    assert board.start_order == ["Alpha", "Beta"]
    assert not board.offline_banner.isHidden()
    assert "manual team list" in board.offline_banner.text()
    assert board.commit_button.isEnabled()
    assert board.current_label.text() == "R1 \u00b7 pick 1/26 \u00b7 Alpha"
    assert not board.service.snapshot_path.exists()


def test_real_snapshot_wins_over_manual_teams(qapp, tmp_path):
    service = make_manual_service_12(tmp_path)
    save_fixture_snapshot(service)
    board = DraftBoard(service, [])
    assert board.start_order == ["Red", "Blue"]
    assert board.offline_banner.isHidden()


def test_board_keeps_loaded_picks_when_file_corrupt(qapp, tmp_path):
    board = make_board(tmp_path, [])
    write_pool(board.service, POOL)
    board.refresh()
    board.name_edit.setText("One Aardvark")
    board.commit_button.click()
    board.picks_path.write_text("not json", encoding="utf-8")
    board.refresh()
    assert [p.player for p in board.picks] == ["One Aardvark"]
    assert "draft_picks.json" in board.alert_banner.text()


def test_draft_view_embeds_board(qapp, tmp_path):
    view = DraftView(make_service(tmp_path))
    save_fixture_snapshot(view.service)
    view.refresh()
    assert isinstance(view.board, DraftBoard)
    assert len(view.board.snake) == 26
    same_board = view.board
    view.refresh()
    assert view.board is same_board
    view.service.snapshot_path.unlink()
    view.refresh()
    assert "Sync the league first" in view.board.alert_banner.text()
