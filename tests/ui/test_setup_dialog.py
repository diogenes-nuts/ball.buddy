"""SetupDialog (P1, 006_board) tests: offscreen Qt, manual-mode service."""

import os
import sys
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"  # must be set before any PySide6 import

import pytest
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QLineEdit,
    QSpinBox,
)

from ball_buddy.domain import keepers as keepers_mod
from ball_buddy.io.pool.importer import FIELDNAMES, write_csv
from ball_buddy.io.yahoo.client import YahooClient
from ball_buddy.services.sync import SyncService
from ball_buddy.ui.views.board import DraftBoard
from ball_buddy.ui.views.setup_dialog import SetupDialog

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tests.io.test_yahoo_client import FakeQuery  # noqa: E402


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    return QApplication.instance() or QApplication([])


def make_service(tmp_path: Path, teams: list[str] | None = None) -> SyncService:
    service = SyncService(tmp_path, client=YahooClient(FakeQuery(), "k", "s"))
    settings = {"league_id": "1234"}
    if teams is not None:
        settings["manual_teams"] = teams
    service.save_settings(settings)
    return service


def write_pool(service: SyncService, names: list[str]) -> None:
    rows = [{f: "" for f in FIELDNAMES} for _ in names]
    for row, name in zip(rows, names):
        row["name"] = name
    write_csv(rows, service.pool_path)


def team_check(dialog: SetupDialog, row: int) -> QCheckBox:
    widget = dialog.teams_table.cellWidget(row, 1)
    assert isinstance(widget, QCheckBox)
    return widget


def keeper_widgets(
    dialog: SetupDialog, row: int
) -> tuple[QComboBox, QLineEdit, QSpinBox, QCheckBox]:
    combo = dialog.keepers_table.cellWidget(row, 0)
    edit = dialog.keepers_table.cellWidget(row, 1)
    spin = dialog.keepers_table.cellWidget(row, 2)
    check = dialog.keepers_table.cellWidget(row, 3)
    assert isinstance(combo, QComboBox)
    assert isinstance(edit, QLineEdit)
    assert isinstance(spin, QSpinBox)
    assert isinstance(check, QCheckBox)
    return combo, edit, spin, check


# -- teams / draft order ------------------------------------------------------


def test_reorder_rename_and_my_team_save(qapp, tmp_path):
    service = make_service(tmp_path, ["Alpha", "Beta"])
    dialog = SetupDialog(service)
    assert dialog.teams_table.rowCount() == 2
    # rename Alpha and move it below Beta
    dialog.teams_table.item(0, 0).setText("Zulu")
    dialog.teams_table.setCurrentCell(0, 0)
    dialog.move_down_button.click()
    assert dialog.teams_table.item(0, 0).text() == "Beta"
    assert dialog.teams_table.item(1, 0).text() == "Zulu"
    # mark Zulu as my team
    team_check(dialog, 1).setChecked(True)
    dialog._save()
    saved = service.settings()
    assert saved["manual_teams"] == ["Beta", "Zulu"]
    assert saved["manual_draft_order"] == ["Beta", "Zulu"]
    assert saved["my_team"] == "Zulu"
    # the board's start order follows the saved order (offline manual mode)
    board = DraftBoard(service, [])
    assert board.start_order == ["Beta", "Zulu"]


def test_no_my_team_clears_setting(qapp, tmp_path):
    service = make_service(tmp_path, ["Alpha", "Beta"])
    service.save_settings({**service.settings(), "my_team": "Alpha"})
    dialog = SetupDialog(service)
    assert team_check(dialog, 0).isChecked()
    team_check(dialog, 0).setChecked(False)
    dialog._save()
    assert service.settings()["my_team"] == ""


def test_duplicate_team_names_block_save(qapp, tmp_path):
    service = make_service(tmp_path, ["Alpha", "Beta"])
    dialog = SetupDialog(service)
    dialog.teams_table.item(1, 0).setText("Alpha")  # duplicate
    dialog._save()
    assert not dialog.alert_banner.isHidden()
    assert "Duplicate team names" in dialog.alert_banner.text()
    # nothing persisted
    assert service.settings()["manual_teams"] == ["Alpha", "Beta"]
    # rename resolves it
    dialog.teams_table.item(1, 0).setText("Gamma")
    dialog._save()
    assert service.settings()["manual_teams"] == ["Alpha", "Gamma"]


def test_empty_team_row_blocks_save(qapp, tmp_path):
    service = make_service(tmp_path, ["Alpha"])
    dialog = SetupDialog(service)
    dialog.add_team_button.click()  # blank row
    dialog._save()
    assert not dialog.alert_banner.isHidden()
    assert "empty" in dialog.alert_banner.text()
    assert service.settings()["manual_teams"] == ["Alpha"]


def test_add_and_remove_team(qapp, tmp_path):
    service = make_service(tmp_path, ["Alpha"])
    dialog = SetupDialog(service)
    dialog.add_team_button.click()
    dialog.teams_table.item(1, 0).setText("Beta")
    dialog._save()
    assert service.settings()["manual_teams"] == ["Alpha", "Beta"]
    dialog2 = SetupDialog(service)
    dialog2.teams_table.setCurrentCell(1, 0)
    dialog2.remove_team_button.click()
    dialog2._save()
    assert service.settings()["manual_teams"] == ["Alpha"]


# -- keepers -------------------------------------------------------------------


def test_add_keeper_save_flows_to_board(qapp, tmp_path):
    service = make_service(tmp_path, ["Alpha", "Beta"])
    write_pool(service, ["Nikola Jokic"])
    dialog = SetupDialog(service)
    dialog.add_keeper_button.click()
    combo, edit, spin, _check = keeper_widgets(dialog, 0)
    combo.setCurrentText("Alpha")
    edit.setText("Nikola Jokic")
    spin.setValue(3)
    dialog._save()
    saved = keepers_mod.load(service.data_dir / keepers_mod.KEEPERS_FILE)
    assert saved == [
        keepers_mod.KeeperEntry("Alpha", "Nikola Jokic", 3, opted_out=False)
    ]
    # board forfeits the cost-round pick and shows the keeper name
    board = DraftBoard(service, saved)
    assert "Keeper: Nikola Jokic" in board.grid.item(2, 0).text()
    # Status column resolved the name against the pool
    assert dialog.keepers_table.item(0, 4).text() == "Nikola Jokic"
    # reopening the dialog round-trips the entry
    dialog2 = SetupDialog(service)
    assert dialog2.keepers_table.rowCount() == 1
    combo2, edit2, spin2, _check2 = keeper_widgets(dialog2, 0)
    assert combo2.currentText() == "Alpha"
    assert edit2.text() == "Nikola Jokic"
    assert spin2.value() == 3


def test_remove_keeper_saves_empty(qapp, tmp_path):
    service = make_service(tmp_path, ["Alpha", "Beta"])
    keepers_mod.save(
        [keepers_mod.KeeperEntry("Alpha", "Big Keeper", 1)],
        service.data_dir / keepers_mod.KEEPERS_FILE,
    )
    dialog = SetupDialog(service)
    assert dialog.keepers_table.rowCount() == 1
    dialog.keepers_table.setCurrentCell(0, 0)
    dialog.remove_keeper_button.click()
    assert dialog.keepers_table.rowCount() == 0
    dialog._save()
    assert keepers_mod.load(service.data_dir / keepers_mod.KEEPERS_FILE) == []


def test_status_column_flags_unmatched_with_suggestions(qapp, tmp_path):
    service = make_service(tmp_path, ["Alpha"])
    write_pool(service, ["Nikola Jokic"])
    dialog = SetupDialog(service)
    dialog.add_keeper_button.click()
    _combo, edit, _spin, _check = keeper_widgets(dialog, 0)
    edit.setText("Jokic")  # resolves via containment
    assert dialog.keepers_table.item(0, 4).text() == "Nikola Jokic"
    edit.setText("Ghost Jokic")  # unmatched, last-name suggestion
    assert "UNMATCHED" in dialog.keepers_table.item(0, 4).text()
    assert "Nikola Jokic" in dialog.keepers_table.item(0, 4).text()
    # unmatched is flagged but still saved
    dialog._save()
    saved = keepers_mod.load(service.data_dir / keepers_mod.KEEPERS_FILE)
    assert [e.player for e in saved] == ["Ghost Jokic"]


def test_opted_out_keeper_not_forfeited(qapp, tmp_path):
    service = make_service(tmp_path, ["Alpha", "Beta"])
    dialog = SetupDialog(service)
    dialog.add_keeper_button.click()
    combo, edit, spin, check = keeper_widgets(dialog, 0)
    combo.setCurrentText("Alpha")
    edit.setText("Big Keeper")
    check.setChecked(True)  # opt out
    dialog._save()
    saved = keepers_mod.load(service.data_dir / keepers_mod.KEEPERS_FILE)
    assert saved[0].opted_out is True
    board = DraftBoard(service, saved)
    assert board.grid.item(0, 0).text() == ""  # pick stays open
    assert board._keeper_cells == {}


# -- validation ------------------------------------------------------------------


def test_same_round_keepers_block_save(qapp, tmp_path):
    service = make_service(tmp_path, ["Alpha", "Beta"])
    write_pool(service, ["Nikola Jokic", "Ghost Player"])
    dialog = SetupDialog(service)
    dialog.add_keeper_button.click()
    combo, edit, spin, _check = keeper_widgets(dialog, 0)
    combo.setCurrentText("Alpha")
    edit.setText("Nikola Jokic")
    spin.setValue(1)
    dialog.add_keeper_button.click()
    combo2, edit2, spin2, _check2 = keeper_widgets(dialog, 1)
    combo2.setCurrentText("Alpha")
    edit2.setText("Ghost Player")
    spin2.setValue(1)  # same cost round, both active -> validate error
    dialog._save()
    # alert shown, nothing persisted, dialog not accepted
    assert not dialog.alert_banner.isHidden()
    assert "costing round 1" in dialog.alert_banner.text()
    assert not (service.data_dir / keepers_mod.KEEPERS_FILE).exists()
    assert service.settings().get("manual_teams") == ["Alpha", "Beta"]


def test_over_two_keepers_block_save(qapp, tmp_path):
    service = make_service(tmp_path, ["Alpha", "Beta"])
    dialog = SetupDialog(service)
    for i, name in enumerate(("One", "Two", "Three")):
        dialog.add_keeper_button.click()
        combo, edit, spin, _check = keeper_widgets(dialog, i)
        combo.setCurrentText("Alpha")
        edit.setText(name)
        spin.setValue(i + 1)
    dialog._save()
    assert not dialog.alert_banner.isHidden()
    assert "max 2" in dialog.alert_banner.text()
    assert not (service.data_dir / keepers_mod.KEEPERS_FILE).exists()


def test_corrupt_keepers_file_refuses_save(qapp, tmp_path):
    service = make_service(tmp_path, ["Alpha", "Beta"])
    (service.data_dir / keepers_mod.KEEPERS_FILE).write_text("not json", encoding="utf-8")
    dialog = SetupDialog(service)
    assert "keepers.json" in dialog.alert_banner.text()
    dialog._save()
    assert (service.data_dir / keepers_mod.KEEPERS_FILE).read_text(encoding="utf-8") == "not json"


# -- live-mode seeding ------------------------------------------------------------


def test_live_mode_seeds_teams_from_snapshot(qapp, tmp_path):
    from ball_buddy.io.yahoo.snapshot import save_snapshot, to_snapshot
    from tests.io.test_snapshot import load_results

    service = make_service(tmp_path)  # no manual teams
    save_snapshot(to_snapshot(load_results(), "1234"), service.snapshot_path)
    dialog = SetupDialog(service)
    assert [
        dialog.teams_table.item(r, 0).text() for r in range(dialog.teams_table.rowCount())
    ] == ["Red", "Blue"]
    dialog._save()
    saved = service.settings()
    assert saved["manual_teams"] == ["Red", "Blue"]
    assert saved["manual_draft_order"] == ["Red", "Blue"]
