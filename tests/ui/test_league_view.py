"""LeagueView tests (offscreen Qt): fixture snapshot rendering, banners."""

import os
import sys
import time
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"  # must be set before any PySide6 import

import pytest
from PySide6.QtWidgets import QApplication

from ball_buddy.io.yahoo.client import YahooClient
from ball_buddy.io.yahoo.snapshot import save_snapshot, to_snapshot
from ball_buddy.services.sync import SyncService
from ball_buddy.ui.views.league import LeagueView

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tests.io.test_yahoo_client import FakeQuery  # noqa: E402

FIXTURE = Path("tests/fixtures/snapshot_results.json")


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    return QApplication.instance() or QApplication([])


def make_snapshot(tmp_path: Path, results_raw: dict | None = None) -> dict:
    from tests.io.test_snapshot import load_results

    results = load_results()
    doc = to_snapshot(results, "1234")
    save_snapshot(doc, tmp_path / "snapshot.json")
    return doc


def make_view(tmp_path: Path, qapp: QApplication) -> LeagueView:
    service = SyncService(tmp_path, client=YahooClient(FakeQuery(), "k", "s"))
    service.save_settings({"league_id": "1234"})
    view = LeagueView(service)
    return view


def test_renders_team_rows(qapp, tmp_path):
    view = make_view(tmp_path, qapp)
    service = view.service
    save_snapshot(to_snapshot_from_fixture(), service.snapshot_path)
    view.apply_result(service.load_last())
    assert view.snapshot is not None
    assert view.teams_table.rowCount() == 2
    assert view.teams_table.item(0, 0).text() == "Red"
    assert view.teams_table.item(0, 1).text() == "mgr_red"
    assert view.teams_table.item(0, 2).text() == "2"  # roster size
    assert view.teams_table.item(1, 3).text() == "1"  # Blue has 1 IR player
    assert view.league_label.text() == "Fake League"


def to_snapshot_from_fixture() -> dict:
    from tests.io.test_snapshot import load_results

    return to_snapshot(load_results(), "1234")


def test_unmatched_banner_shows_when_report_has_unmatched(qapp, tmp_path):
    view = make_view(tmp_path, qapp)
    service = view.service
    save_snapshot(to_snapshot_from_fixture(), service.snapshot_path)
    # small pool: nobody matches the fixture roster -> all unmatched
    from ball_buddy.io.pool.importer import FIELDNAMES, write_csv

    rows = [{f: "" for f in FIELDNAMES} for _ in range(2)]
    rows[0]["name"] = "Zed Zederson"
    rows[1]["name"] = "Ann Annerson"
    write_csv(rows, service.pool_path)
    result = service.load_last()
    assert result.report is not None
    assert len(result.report.unmatched) == 4  # 2 players x 2 teams
    view.apply_result(result)
    assert not view.unmatched_banner.isHidden()
    assert "4 roster players unmatched" in view.unmatched_banner.text()
    assert view.unmatched_banner.objectName() == "banner-danger"


def test_no_unmatched_banner_when_all_matched(qapp, tmp_path):
    view = make_view(tmp_path, qapp)
    service = view.service
    save_snapshot(to_snapshot_from_fixture(), service.snapshot_path)
    from ball_buddy.io.pool.importer import FIELDNAMES, write_csv

    names = ["Nikola Jokic", "Ghost Player", "Shaquille O'Neal", "Jokic"]
    rows = []
    for name in names:
        row = {f: "" for f in FIELDNAMES}
        row["name"] = name
        rows.append(row)
    write_csv(rows, service.pool_path)
    result = service.load_last()
    view.apply_result(result)
    # every roster name has an exact pool match -> banner hidden
    assert result.report is not None
    assert result.report.problem_count == 0
    assert len(result.report.matched) == 4
    assert view.unmatched_banner.isHidden()

    # make one roster player unmatched (pool lacks O'Neal) -> banner shows;
    # then resolve it with an alias entry
    rows = [row for row in rows if row["name"] != "Ghost Player"]
    write_csv(rows, service.pool_path)
    result = service.load_last()
    view.apply_result(result)
    assert [name for name, _ in result.report.unmatched] == ["Ghost Player"]
    assert not view.unmatched_banner.isHidden()
    service.save_aliases({"Ghost Player": "Shaquille O'Neal"})
    result = service.load_last()
    view.apply_result(result)
    assert result.report.problem_count == 0
    assert result.report.matched["Ghost Player"] == "Shaquille O'Neal"
    assert view.unmatched_banner.isHidden()


def test_stale_banner_offline(qapp, tmp_path):
    view = make_view(tmp_path, qapp)
    result = view.service.load_last()
    assert result.snapshot is None  # never synced
    view.apply_result(result)
    assert "No snapshot yet" in view.status_banner.text()
    save_snapshot(to_snapshot_from_fixture(), view.service.snapshot_path)
    view.apply_result(view.service.load_last())
    text = view.status_banner.text().lower()
    assert "last synced" in text or "showing last snapshot" in text


def test_schedule_and_draft_tables(qapp, tmp_path):
    view = make_view(tmp_path, qapp)
    save_snapshot(to_snapshot_from_fixture(), view.service.snapshot_path)
    view.apply_result(view.service.load_last())
    # schedule from Red's perspective: week1 vs Blue, week2 bye
    assert view.schedule_table.rowCount() == 2
    assert view.schedule_table.item(0, 0).text() == "1"
    assert view.schedule_table.item(1, 1).text() == "BYE"
    # draft order from live draft_position (Red 1st, Blue 2nd), 14 rounds
    assert view.draft_table.rowCount() == 28
    assert view.draft_table.item(0, 2).text() == "Red"
    assert view.draft_table.item(1, 2).text() == "Blue"
    assert view.draft_table.item(2, 2).text() == "Blue"  # round 2 snakes


def test_settings_dialog_saves_credentials(qapp, tmp_path):
    from ball_buddy.ui.views.league import SettingsDialog

    view = make_view(tmp_path, qapp)
    dialog = SettingsDialog(view.service, view)
    dialog.league_id_edit.setText("98765")
    dialog.consumer_key_edit.setText("dummKey")
    dialog.consumer_secret_edit.setText("dummSecret")
    dialog._save()
    saved = view.service.settings()
    assert saved["version"] == 1
    assert saved["league_id"] == "98765"
    assert saved["consumer_key"] == "dummKey"
    assert saved["consumer_secret"] == "dummSecret"
    assert view.settings_button is not None


def test_settings_dialog_has_reset_button(qapp, tmp_path):
    from ball_buddy.ui.views.league import SettingsDialog

    view = make_view(tmp_path, qapp)
    dialog = SettingsDialog(view.service, view)
    assert dialog.reset_button is not None
    assert dialog.reset_button.text() == "Reset all data…"


def test_settings_reset_yes_wipes_data(qapp, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from ball_buddy.ui.views.league import SettingsDialog

    view = make_view(tmp_path, qapp)
    view.service.save_settings({"league_id": "1234"})
    (tmp_path / "yahoo_tokens.json").write_text("{}", encoding="utf-8")
    assert view.service.data_dir.exists()

    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes),
    )
    dialog = SettingsDialog(view.service, view)
    dialog._reset()
    assert not view.service.data_dir.exists()  # wiped: settings + tokens gone
    assert "Reset complete" in dialog.reset_status.text()


def test_settings_reset_no_keeps_data(qapp, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from ball_buddy.ui.views.league import SettingsDialog

    view = make_view(tmp_path, qapp)
    view.service.save_settings({"league_id": "1234"})

    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.No),
    )
    dialog = SettingsDialog(view.service, view)
    dialog._reset()
    assert view.service.data_dir.exists()
    assert view.service.settings()["league_id"] == "1234"
    assert dialog.reset_status.text() == ""


def _spin_until(predicate, timeout: float = 10.0) -> None:
    """Pump the Qt event loop until predicate() is true. The sync worker runs
    on a QThread; its signals (worker.finished -> thread.quit, then
    thread.finished) are delivered on the main loop, so we must pump here.
    A blocking wait() inside a queued slot would deadlock this pump."""
    deadline = time.monotonic() + timeout
    app = QApplication.instance()
    while not predicate():
        if time.monotonic() > deadline:
            raise AssertionError("timed out waiting for sync thread to finish")
        app.processEvents()
        time.sleep(0.02)


def test_sync_now_thread_round_trip(qapp, tmp_path):
    """Regression for the "Sync now crashes the app" deadlock.

    The old _on_sync_done called thread.wait() inside the queued finished
    slot, which blocked the main loop so thread.quit() (queued behind it)
    could never run -> the app wedged. The fix stores the result first and
    drives the UI from thread.finished. This drives the REAL _sync_now thread
    path and requires it to come back (thread torn down, banner updated);
    the old code hangs here until the timeout."""
    view = make_view(tmp_path, qapp)
    view.sync_button.setEnabled(True)
    view.import_button.setEnabled(True)
    assert view._thread is None
    view._sync_now()
    assert view._thread is not None  # the worker thread is up
    _spin_until(lambda: view._thread is None and view._worker is None)
    # the injected FakeQuery client returns a good result -> clean "Synced"
    assert "Syncing\u2026" not in view.status_banner.text()
    assert view.sync_button.isEnabled()
    assert view.import_button.isEnabled()


def test_manual_order_applied_when_no_live_order(qapp, tmp_path):
    view = make_view(tmp_path, qapp)
    service = view.service
    doc = to_snapshot_from_fixture()
    doc["draft"]["order"] = None  # simulate pre-draft: Yahoo gives no order
    save_snapshot(doc, service.snapshot_path)
    service.save_settings({"league_id": "1234", "manual_draft_order": ["Blue", "Red"]})
    view.apply_result(service.load_last())
    assert view.draft_table.item(0, 2).text() == "Blue"
    assert view.draft_table.item(1, 2).text() == "Red"
    # stale/unknown names are dropped, new teams appended in snapshot order
    service.save_settings({"league_id": "1234", "manual_draft_order": ["Blue", "Gone"]})
    assert view._manual_order_for(["Red", "Blue", "Green"]) == ["Blue", "Red", "Green"]


# -- offline manual team list -------------------------------------------------


def test_manual_mode_renders_teams_and_order(qapp, tmp_path):
    service = SyncService(tmp_path, client=YahooClient(FakeQuery(), "k", "s"))
    settings = service.settings()
    settings["manual_teams"] = ["Alpha", "Beta"]
    service.save_settings(settings)
    view = LeagueView(service)
    assert view.snapshot is not None
    assert view.snapshot["source"] == "manual"
    assert view.league_label.text() == "Manual team list (offline)"
    assert not view.offline_banner.isHidden()
    assert "manual team list" in view.offline_banner.text()
    assert view.teams_table.rowCount() == 2
    assert view.teams_table.item(0, 0).text() == "Alpha"
    assert "manual team list" in view.status_banner.text().lower()
    # order editable offline: 14-round snake, buttons live, no live order
    assert view.draft_table.rowCount() == 14 * 2
    assert view.save_order_button.isEnabled()
    assert view.schedule_empty.isHidden() is False


def test_manual_order_saved_offline(qapp, tmp_path):
    service = SyncService(tmp_path, client=YahooClient(FakeQuery(), "k", "s"))
    settings = service.settings()
    settings["manual_teams"] = ["Alpha", "Beta"]
    service.save_settings(settings)
    view = LeagueView(service)
    view.draft_table.setCurrentCell(0, 0)  # swap rows 0/1 in the round-1 block
    view._move_selected(1)
    # move persists immediately (re-render would otherwise drop the swap)
    assert view.service.settings()["manual_draft_order"] == ["Beta", "Alpha"]
    assert view.draft_table.item(0, 2).text() == "Beta"
    assert view.draft_table.item(1, 2).text() == "Alpha"
