"""DraftView (keeper entry) tests: offscreen Qt, fixture snapshot."""

import os
import sys
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"  # must be set before any PySide6 import

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QCheckBox, QLineEdit, QSpinBox

from ball_buddy.domain import keepers as keepers_mod
from ball_buddy.io.pool.importer import FIELDNAMES, write_csv
from ball_buddy.io.yahoo.client import YahooClient
from ball_buddy.io.yahoo.snapshot import save_snapshot, to_snapshot
from ball_buddy.services.sync import SyncService
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


def write_pool(service: SyncService, names: list[str]) -> None:
    rows = [{f: "" for f in FIELDNAMES} for _ in names]
    for row, name in zip(rows, names):
        row["name"] = name
    write_csv(rows, service.pool_path)


def player_edit(view: DraftView, row: int) -> QLineEdit:
    widget = view.table.cellWidget(row, 1)
    assert isinstance(widget, QLineEdit)
    return widget


def round_spin(view: DraftView, row: int) -> QSpinBox:
    widget = view.table.cellWidget(row, 2)
    assert isinstance(widget, QSpinBox)
    return widget


def opt_check(view: DraftView, row: int) -> QCheckBox:
    widget = view.table.cellWidget(row, 3)
    assert isinstance(widget, QCheckBox)
    return widget


def test_renders_two_rows_per_team(qapp, tmp_path):
    view = make_view(tmp_path)
    save_fixture_snapshot(view.service)
    view.refresh()
    # fixture snapshot has 2 teams (Red, Blue) -> 4 grid rows
    assert view.table.rowCount() == 2 * 2
    assert view.table.item(0, 0).text() == "Red"
    assert view.table.item(1, 0).text() == "Red"
    assert view.table.item(2, 0).text() == "Blue"
    assert view.table.item(3, 0).text() == "Blue"
    assert view.save_button.isEnabled()
    spin = round_spin(view, 0)
    assert spin.minimum() == 1 and spin.maximum() == 13
    # team cell is plain text, not editable; player cell has a pool completer
    assert not (view.table.item(0, 0).flags() & Qt.ItemFlag.ItemIsEditable)
    assert player_edit(view, 0).completer() is not None


def test_no_snapshot_disables_save_and_shows_banner(qapp, tmp_path):
    view = make_view(tmp_path)
    assert view.save_button.isEnabled() is False
    assert "Sync the league first" in view.alert_banner.text()
    assert view.alert_banner.objectName() == "banner-alert"
    assert not view.alert_banner.isHidden()
    assert view.table.rowCount() == 0


def test_fill_row_save_writes_keepers_json(qapp, tmp_path):
    view = make_view(tmp_path)
    save_fixture_snapshot(view.service)
    write_pool(view.service, ["Nikola Jokic", "Ghost Player"])
    view.refresh()
    player_edit(view, 0).setText("Nikola Jokic")
    round_spin(view, 0).setValue(3)
    view.update_statuses()
    # Status shows the resolved pool name
    assert view.table.item(0, 4).text() == "Nikola Jokic"
    view._save()
    saved = keepers_mod.load(view.keepers_path)
    assert saved == [
        keepers_mod.KeeperEntry(team="Red", player="Nikola Jokic", cost_round=3, opted_out=False)
    ]
    assert "Saved 1 keepers" in view.status_banner.text()
    # reload round-trips the entry back into the grid
    view2 = make_view(tmp_path)
    view2.teams = ["Red", "Blue"]
    view2.refresh()
    assert player_edit(view2, 0).text() == "Nikola Jokic"
    assert round_spin(view2, 0).value() == 3


def test_unmatched_name_flagged_but_saves(qapp, tmp_path):
    view = make_view(tmp_path)
    save_fixture_snapshot(view.service)
    write_pool(view.service, ["Nikola Jokic"])
    view.refresh()
    player_edit(view, 0).setText("Zed Zederson")
    view.update_statuses()
    assert view.table.item(0, 4).text().startswith("UNMATCHED")
    assert not view.alert_banner.isHidden()
    assert "1 keeper name(s) unmatched" in view.alert_banner.text()
    # unmatched keepers still save (flagged, not blocked)
    view._save()
    saved = keepers_mod.load(view.keepers_path)
    assert [e.player for e in saved] == ["Zed Zederson"]


def test_validate_errors_block_save(qapp, tmp_path):
    view = make_view(tmp_path)
    save_fixture_snapshot(view.service)
    write_pool(view.service, ["Nikola Jokic"])
    view.refresh()
    # two keepers for Red in the same round -> validate error blocks Save
    player_edit(view, 0).setText("Nikola Jokic")
    round_spin(view, 0).setValue(1)
    player_edit(view, 1).setText("Nikola Jokic")
    round_spin(view, 1).setValue(1)
    view._save()
    assert view.keepers_path.exists() is False
    assert "fix the errors" in view.status_banner.text()
    # hand-built entries also reach validate (3rd keeper per team)
    errors = keepers_mod.validate(
        [
            keepers_mod.KeeperEntry("Red", "A", 1),
            keepers_mod.KeeperEntry("Red", "B", 2),
            keepers_mod.KeeperEntry("Red", "C", 3),
        ],
        view.teams,
    )
    assert any("max 2" in err for err in errors)


def test_opted_out_saves_flag(qapp, tmp_path):
    view = make_view(tmp_path)
    save_fixture_snapshot(view.service)
    write_pool(view.service, ["Nikola Jokic"])
    view.refresh()
    player_edit(view, 0).setText("Nikola Jokic")
    opt_check(view, 0).setChecked(True)
    view._save()
    saved = keepers_mod.load(view.keepers_path)
    assert saved[0].opted_out is True


# -- offline manual team list -------------------------------------------------


def make_manual_view(tmp_path: Path) -> DraftView:
    service = SyncService(tmp_path, client=YahooClient(FakeQuery(), "k", "s"))
    settings = service.settings()
    settings["manual_teams"] = ["Alpha", "Beta"]
    service.save_settings(settings)
    return DraftView(service)


def test_manual_teams_render_keeper_grid(qapp, tmp_path):
    view = make_manual_view(tmp_path)
    assert view.teams == ["Alpha", "Beta"]
    assert view.table.rowCount() == 4  # 2 keeper slots per team
    assert not view.offline_banner.isHidden()
    assert "manual team list" in view.offline_banner.text()
    assert view.save_button.isEnabled()
    assert view.board is not None
    assert view.board.start_order == ["Alpha", "Beta"]


def test_manual_teams_save_keepers(qapp, tmp_path):
    view = make_manual_view(tmp_path)
    player_edit(view, 0).setText("Big Keeper")
    view.save_button.click()
    saved = keepers_mod.load(view.keepers_path)
    assert saved == [keepers_mod.KeeperEntry("Alpha", "Big Keeper", 1)]
    assert "Saved 1 keepers" in view.status_banner.text()
