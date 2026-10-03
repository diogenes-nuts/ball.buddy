"""TradeView tests (offscreen Qt): happy path, fairness flag, errors.

Reuses the M3.1 engine fixture rows (P1-P4, gp=40) as players.csv and
keepers.json (Red keeps P1/P2, Blue keeps P3/P4) over the fixture
snapshot (teams Red/Blue), like the waiver/lineup view tests. P1 is the
best player (highest pts_pg), so giving P1 away for P4 must trip the
fairness flag ("bad deal"). Domain errors (both sides empty) and
unresolved keepers surface as banner text, never an exception.
"""

import os
import sys
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"  # must be set before any PySide6 import

import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication

from ball_buddy.domain.keepers import KeeperEntry
from ball_buddy.domain.keepers import save as save_keepers
from ball_buddy.io.pool.importer import FIELDNAMES, write_csv
from ball_buddy.io.yahoo.client import YahooClient
from ball_buddy.io.yahoo.snapshot import save_snapshot, to_snapshot
from ball_buddy.services.sync import SyncService
from ball_buddy.ui.views.trades import TradeView

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tests.io.test_snapshot import load_results
from tests.io.test_yahoo_client import FakeQuery  # noqa: E402


def _row(name: str, **stats: str) -> dict[str, str]:
    row = {column: "" for column in FIELDNAMES}
    row.update(name=name, gp="40", **stats)
    return row


P1 = _row("P1", pts_pg="20", reb_pg="8", ast_pg="5", stl_pg="1.5", blk_pg="1.0",
          to_pg="2.0", three_pg="3.0", fg_pct=".50", fga_pg="20",
          ft_pct=".90", fta_pg="5")
P2 = _row("P2", pts_pg="18", reb_pg="10", ast_pg="4", stl_pg="1.0", blk_pg="1.2",
          to_pg="2.5", three_pg="2.0", fg_pct=".45", fga_pg="18",
          ft_pct=".85", fta_pg="4")
P3 = _row("P3", pts_pg="15", reb_pg="5", ast_pg="8", stl_pg="1.2", blk_pg=".8",
          to_pg="3.0", three_pg="2.5", fg_pct=".48", fga_pg="15",
          ft_pct=".92", fta_pg="3")
P4 = _row("P4", pts_pg="10", reb_pg="4", ast_pg="3", stl_pg=".5", blk_pg=".5",
          to_pg="1.0", three_pg="1.0", fg_pct=".40", fga_pg="12",
          ft_pct=".80", fta_pg="2")

KEEPERS = [
    KeeperEntry(team="Red", player="P1", cost_round=1),
    KeeperEntry(team="Red", player="P2", cost_round=2),
    KeeperEntry(team="Blue", player="P3", cost_round=1),
    KeeperEntry(team="Blue", player="P4", cost_round=2),
]


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def service(tmp_path: Path) -> SyncService:
    service = SyncService(tmp_path, client=YahooClient(FakeQuery(), "k", "s"))
    doc = to_snapshot(load_results(), "1234")
    save_snapshot(doc, service.snapshot_path)
    write_csv([P1, P2, P3, P4], service.pool_path)
    save_keepers(KEEPERS, service.data_dir / "keepers.json")
    return service


@pytest.fixture()
def view(service: SyncService, qapp: QApplication) -> TradeView:
    return TradeView(service)


def test_happy_path(view: TradeView) -> None:
    view.pick_teams("Red", "Blue")
    view.add_give("my", "P1")
    view.add_give("their", "P3")
    view.analyze()
    assert "you" in view.banner.text()
    assert "them" in view.banner.text()
    assert view.my_table.rowCount() == 9
    assert view.their_table.rowCount() == 9
    assert view.my_table.item(0, 0).text()  # first cat label rendered
    assert "->" in view.summary_label.text()
    assert "seed 42" in view.summary_label.text()
    assert "200 trials" in view.summary_label.text()


def test_fairness_flag_on_bad_deal(view: TradeView) -> None:
    # P1 is the best player (20 pts_pg); trading it for P4 (10) must be
    # flagged as a bad deal (my delta P(win) < -0.10 with 200 trials, seed 42).
    view.pick_teams("Red", "Blue")
    view.add_give("my", "P1")
    view.add_give("their", "P4")
    view.analyze()
    assert "bad deal" in view.banner.text()
    assert view.my_table.rowCount() == 9


def test_both_sides_empty_raises_valueerror(view: TradeView) -> None:
    view.pick_teams("Red", "Blue")
    view.analyze()  # no gives on either side -> domain ValueError
    assert "at least one side" in view.banner.text()
    assert view.my_table.rowCount() == 0
    assert view.their_table.rowCount() == 0


def test_no_snapshot(view: TradeView, tmp_path: Path, qapp: QApplication) -> None:
    fresh = TradeView(SyncService(tmp_path / "fresh"))
    fresh.analyze()
    assert fresh.banner.text() == "Pick a team and an opponent first."


def test_ghost_keepers_empty_roster(view: TradeView, service: SyncService) -> None:
    save_keepers(
        [KeeperEntry(team="Red", player="Ghost", cost_round=1)] + KEEPERS[2:],
        service.data_dir / "keepers.json",
    )
    view.apply_result(service.load_last())
    view.pick_teams("Red", "Blue")
    view.add_give("my", "P1")
    view.analyze()  # must not raise
    assert "Empty roster" in view.banner.text()
    assert "Ghost" in view.banner.text()
    assert view.my_table.rowCount() == 0


def test_process_events_after_add_keeps_live_gives(
    view: TradeView, qapp: QApplication
) -> None:
    # Regression: _rebuild_give_grid used to deleteLater() every widget it
    # takeAt()'d — including still-live give labels/Remove buttons that were
    # then re-added. Once the event loop ran, those widgets were destroyed
    # and the next text()/click raised RuntimeError. (Deferred deletes are
    # flushed by the event loop's exec(), not plain processEvents() — so we
    # mimic it with sendPostedEvents(w, DeferredDelete), targeted at the
    # live give widgets so leftover deferred deletes from other tests don't
    # leak into this one.)
    view.pick_teams("Red", "Blue")
    first = view.add_give("my", "P1")
    view.add_give("my", "P2")  # 2nd rebuild: 1st give's widgets re-added
    view.add_give("their", "P3")

    def flush() -> None:
        qapp.processEvents()
        for g in view._my_gives + view._their_gives:
            for w in (g["label"], g["remove"]):
                QCoreApplication.sendPostedEvents(w, QEvent.DeferredDelete)

    flush()  # what the real event loop would do between Add clicks
    assert first is not None
    assert first["label"].text() == "P1"  # pre-fix: RuntimeError here
    first["remove"].click()  # pre-fix: RuntimeError here too
    flush()
    assert [g["label"].text() for g in view._my_gives] == ["P2"]
    assert [g["label"].text() for g in view._their_gives] == ["P3"]


def test_trials_spin_reflected_in_summary(view: TradeView) -> None:
    view.pick_teams("Red", "Blue")
    view.add_give("my", "P1")
    view.add_give("their", "P3")
    view.trials_spin.setValue(500)
    view.analyze()
    assert "500 trials" in view.summary_label.text()
