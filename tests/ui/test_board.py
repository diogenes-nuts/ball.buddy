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
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QHeaderView, QSizePolicy

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
    # players table: ALL columns Interactive and fitted to content once per
    # pool change via font-metric widths (persistent ResizeToContents
    # re-measured every row on each app restyle/theme toggle; Stretch on Name
    # would balloon it on wide windows — user decision: longest-name width,
    # leftover space stays empty).
    hdr = board.player_view.horizontalHeader()
    for ci in range(board._player_model.columnCount()):
        assert hdr.sectionResizeMode(ci) == QHeaderView.ResizeMode.Interactive
    assert board.player_view.columnWidth(0) > 0
    assert board.player_view.columnWidth(1) > 0
    # fixed row height (per-row sizeHintForRow was re-derived on scroll)
    assert board.player_view.verticalHeader().defaultSectionSize() == 22
    # text cells must not leak into CheckStateRole (digit cells would render
    # checkbox indicators)
    rank_idx = board._player_model.index(0, 3)
    assert board._player_model.data(rank_idx, Qt.ItemDataRole.CheckStateRole) is None
    # recs rail: 5 columns, top-n spin default 10, range 1-20
    assert board.recs_grid.columnCount() == 5
    assert board.top_n_spin.value() == 10
    assert (board.top_n_spin.minimum(), board.top_n_spin.maximum()) == (1, 20)
    assert board.commit_button.text() == "Commit pick"
    # single pick path: no separate "Log selected" button (user decision)
    assert not hasattr(board, "log_button")


def test_strip_format(qapp, tmp_path):
    board = make_board(tmp_path, [KeeperEntry("Red", "Big Keeper", 1)])
    # Red forfeits R1 order 1 -> current is R1, overall 2/26, Blue
    assert board.current_label.text() == "R1 \u00b7 pick 2/26 \u00b7 Blue"
    assert board.search_popup.model() is board._search_filter
    assert board.commit_button.isEnabled()


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


def test_double_click_logs_selected_row(qapp, tmp_path):
    board = make_board(tmp_path, [])
    write_pool(board.service, POOL)
    board.refresh()
    # no selection: alert, nothing logged
    board.log_selected()
    assert board.picks == []
    assert "Select a player" in board.alert_banner.text()
    # select the first row, log via double-click
    board.player_view.selectRow(0)
    board.player_view.doubleClicked.emit(board._player_model.index(0, 0))
    assert [p.player for p in board.picks] == ["One Aardvark"]
    # double-click logs the next selected row
    board.player_view.selectRow(0)  # model shrank: now Two Bumble
    board.player_view.doubleClicked.emit(board._player_model.index(0, 0))
    assert [p.player for p in board.picks] == ["One Aardvark", "Two Bumble"]


def test_search_dropdown_partial_match(qapp, tmp_path):
    board = make_board(tmp_path, [])
    write_pool(board.service, POOL)
    board.refresh()
    # typing populates the dropdown with PARTIAL (substring) matches, not
    # just prefixes — "jok"-style mid-word queries are the point
    board.name_edit.setText("chee")
    names = board._search_filter
    matched = [
        names.data(names.index(r, 0)) for r in range(names.rowCount())
    ]
    assert matched == ["Three Cheetah"]
    # "ee" matches several mid-word, and the edit's completer is the proxy
    # filter (so the popup shows exactly these rows)
    board.name_edit.setText("ee")
    matched = [
        board._search_filter.data(board._search_filter.index(r, 0))
        for r in range(board._search_filter.rowCount())
    ]
    assert "Three Cheetah" in matched
    assert "Four Deer" in matched
    assert "One Aardvark" not in matched
    # the search popup is the proxy filter — so it shows exactly the
    # filtered rows, and activating one autofills the edit.
    assert board.search_popup.model() is board._search_filter
    board.search_popup.activated.emit(board._search_filter.index(0, 0))
    assert board.name_edit.text() == matched[0]
    # the dropdown source is excluded-aware (rebuilt on render)
    board2 = make_board(tmp_path, [KeeperEntry("Red", "One Aardvark", 1)])
    write_pool(board2.service, POOL)
    board2.refresh()
    board2.name_edit.setText("one")
    assert board2._search_filter.rowCount() == 0  # keeper excluded


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
    assert board.recs_grid.item(0, 4).text() == "\u2014"  # no cats in fallback
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
    # need cats human-labeled via CAT_LABELS (overhaul 3: was raw "pts")
    assert board.recs_grid.item(0, 4).text() == "Pts"  # fixture: z_pts only
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
    # Display order: col 3 = pts, col 4 = reb (fg/ft/3P are cols 0-2).
    # pts: Alpha is best (12.0 vs 1.0 per game) -> BUILD, neg gap
    assert grid.item(0, 3).text() == "12.00"  # My team row, per game
    assert grid.item(2, 3).text().startswith("-")  # Gap row: ahead
    assert grid.item(3, 3).text() == "BUILD"
    # reb: Alpha is worst -> PUNT, positive gap (behind)
    assert grid.item(3, 4).text() == "PUNT"
    assert grid.item(2, 4).text().startswith("+")
    # gap row stat-coloring: pts ahead -> greenish, reb behind -> reddish
    pts_bg = grid.item(2, 3).background()
    reb_bg = grid.item(2, 4).background()
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


# -- overhaul 4: two-column layout + sortable pool table ----------------------


SORT_POOL = [
    {"name": "Alpha", "pos": "PG", "rank": "1", "value": "10", "z_pts": "1.1"},
    {"name": "Beta", "pos": "SG", "rank": "2", "value": "9", "z_pts": "0.4"},
    {"name": "Gamma", "pos": "SF", "rank": "3", "value": "8", "z_pts": "9.9"},
    {"name": "Delta", "pos": "PF", "rank": "4", "value": "7", "z_pts": ""},
    {"name": "Epsilon", "pos": "C", "rank": "5", "value": "6", "z_pts": "2.0"},
]


def test_pool_table_sortable_by_parsed_z(qapp, tmp_path):
    from ball_buddy.domain.scorer import CAT_Z_COLUMN

    board = make_board(tmp_path, [])
    write_pool(board.service, SORT_POOL)
    board.refresh()
    model = board._player_model
    pts_col = 4 + tuple(CAT_Z_COLUMN).index("pts")
    assert board.player_view.isSortingEnabled()
    # Default order = pool order (Alpha first).
    assert model.name_at(0) == "Alpha"

    model.sort(pts_col, Qt.SortOrder.AscendingOrder)
    # Numeric, not text: "+0.4" < "+1.1" < "+2.0" < "+9.9"; missing last.
    assert _players_names(board) == ["Beta", "Alpha", "Epsilon", "Gamma", "Delta"]

    model.sort(pts_col, Qt.SortOrder.DescendingOrder)
    # Missing stays LAST in both directions (sentinel, not reverse).
    assert _players_names(board) == ["Gamma", "Epsilon", "Alpha", "Beta", "Delta"]

    # Rank sorts numerically too ("10" < "2" would fail on text sort).
    model.sort(3, Qt.SortOrder.AscendingOrder)
    assert _players_names(board) == ["Alpha", "Beta", "Gamma", "Delta", "Epsilon"]

    # POS filter resets the sort (pool order of the filtered subset).
    board.pos_combo.setCurrentText("PG")
    assert _players_names(board) == ["Alpha"]


def test_two_column_layout_right_rail_scroll(qapp, tmp_path):
    from PySide6.QtWidgets import QScrollArea

    board = make_board(tmp_path, [])
    write_pool(board.service, POOL)
    board.refresh()
    rail = board.right_rail
    assert isinstance(rail, QScrollArea)
    assert rail.widgetResizable()
    # Both columns are content-sized (no dead space, no greedy stretch):
    # the rail is exactly its widest panel's content width.
    max_panel = max(
        p.sizeHint().width()
        for p in (board.recs_panel, board.relative_panel, board.roster_panel)
    )
    assert rail.width() == max_panel
    # The left panel stretches (the pool table keeps all leftover window
    # width as empty table background) — it is NOT content-fitted.
    assert (
        board.left_panel.sizePolicy().horizontalPolicy()
        == QSizePolicy.Policy.Expanding
    )
    right_col = rail.widget()
    # Recs, Comparison, Roster in that order, each a panel.
    assert right_col.layout().itemAt(0).widget() is board.recs_panel
    assert right_col.layout().itemAt(1).widget() is board.relative_panel
    assert right_col.layout().itemAt(2).widget() is board.roster_panel
    for panel in (board.recs_panel, board.relative_panel, board.roster_panel):
        assert panel.objectName() == "panel"
        assert panel.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Maximum
    # Recs grid stays as tall as its rows (no collapse in the rail).
    assert board.recs_grid.minimumHeight() > 0
    # Recs Reason column is content-sized (not a greedy Stretch).
    assert (
        board.recs_grid.horizontalHeader().sectionResizeMode(4)
        != QHeaderView.ResizeMode.Stretch
    )


def test_search_dropdown_narrows_and_closes_on_blur(qapp, tmp_path):
    from PySide6.QtCore import QEvent
    from PySide6.QtGui import QFocusEvent

    board = make_board(tmp_path, [])
    write_pool(board.service, POOL)
    board.refresh()
    model = board.search_popup.model()
    full = model.rowCount()
    assert full == len(POOL)
    # Typing a substring narrows the dropdown (only the dropdown — the pool
    # table itself is never filtered) and the popup actually appears (the
    # old Qt.Popup flag stole focus on show() and the focus-out filter
    # killed it before it was ever visible).
    board.refresh()
    board.resize(1400, 900)
    board.show()
    board.name_edit.setText("one")
    qapp.processEvents()
    assert board.search_popup.isVisible()
    narrowed = [
        str(model.data(model.index(r, 0))) for r in range(model.rowCount())
    ]
    assert model.rowCount() < full
    assert all("one" in n.lower() for n in narrowed)
    assert "One Aardvark" in narrowed
    # Clearing restores the full list.
    board.name_edit.clear()
    assert model.rowCount() == full
    # Losing focus closes the popup (routed through the event filter, as Qt
    # dispatches it).
    board.name_edit.setText("one")
    qapp.processEvents()
    assert board.search_popup.isVisible()
    qapp.sendEvent(board.name_edit, QFocusEvent(QEvent.Type.FocusOut))
    assert not board.search_popup.isVisible()
