"""WaiverView tests (offscreen Qt): fixture ranking, FAAB budget, errors.

Reuses the M3.1 engine fixture rows (P1-P4, gp=40) as players.csv and
keepers.json (Red keeps P1/P2, Blue keeps P3/P4) over the fixture
snapshot (teams Red/Blue). Red vs Blue: adding P3 (cost 5) or P4 (cost 0)
to Red's 2-man roster must rank P3 above P4 (P3 is the better player),
both with a non-empty best drop. Budget 4 flags P3 over budget. An
unresolvable candidate name surfaces as a banner error, no exception.
"""

import os
import sys
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"  # must be set before any PySide6 import

import pytest
from PySide6.QtWidgets import QApplication

from ball_buddy.domain.keepers import KeeperEntry
from ball_buddy.domain.keepers import save as save_keepers
from ball_buddy.io.pool.importer import FIELDNAMES, write_csv
from ball_buddy.io.yahoo.client import YahooClient
from ball_buddy.io.yahoo.snapshot import save_snapshot, to_snapshot
from ball_buddy.services.sync import SyncService
from ball_buddy.ui.views.waivers import WaiverView

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


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def view(tmp_path: Path, qapp: QApplication) -> WaiverView:
    service = SyncService(tmp_path, client=YahooClient(FakeQuery(), "k", "s"))
    doc = to_snapshot(load_results(), "1234")
    save_snapshot(doc, service.snapshot_path)
    write_csv([P1, P2, P3, P4], service.pool_path)
    save_keepers(
        [
            KeeperEntry(team="Red", player="P1", cost_round=1),
            KeeperEntry(team="Red", player="P2", cost_round=2),
            KeeperEntry(team="Blue", player="P3", cost_round=1),
            KeeperEntry(team="Blue", player="P4", cost_round=2),
        ],
        service.data_dir / "keepers.json",
    )
    return WaiverView(service)


def test_rank_two_candidates(view: WaiverView) -> None:
    view.pick_teams("Red", "Blue")
    view.add_candidate("P3", cost=5)
    view.add_candidate("P4", cost=0)
    view.rank()
    assert view.result_table.rowCount() == 2
    assert view.result_table.item(0, 1).text() == "P3"
    assert view.result_table.item(1, 1).text() == "P4"
    delta_p3 = float(view.result_table.item(0, 2).text())
    delta_p4 = float(view.result_table.item(1, 2).text())
    assert delta_p3 > delta_p4
    # roster is non-empty (P1, P2) so both rows have a best drop
    for i in range(2):
        assert view.result_table.item(i, 3).text() != ""
    assert "No lineups yet" in view.banner.text()
    assert view.result_table.item(0, 6).text() == ""  # budget 100, no over-budget


def test_low_budget_flags_over_budget(view: WaiverView) -> None:
    view.pick_teams("Red", "Blue")
    view.add_candidate("P3", cost=5)
    view.budget_spin.setValue(4)
    view.rank()
    assert view.result_table.rowCount() == 1
    assert view.result_table.item(0, 6).text() == "YES"


def test_unresolved_candidate_surfaces_error(view: WaiverView) -> None:
    view.pick_teams("Red", "Blue")
    view.add_candidate("P3", cost=5)
    view.add_candidate("Ghost")
    view.rank()  # must not raise
    assert "unresolved" in view.banner.text()
    assert "Ghost" in view.banner.text()
    assert view.result_table.rowCount() == 0


def test_empty_entry_banner(view: WaiverView) -> None:
    view.pick_teams("Red", "Blue")
    view.add_candidate("", cost=0)  # blank rows are skipped, not an error
    view.rank()
    assert view.banner.text() == "Add at least one candidate."
    assert view.result_table.rowCount() == 0


def test_budget_persisted_to_settings(view: WaiverView) -> None:
    assert view.budget_spin.value() == 100  # default until first save
    view.budget_spin.setValue(4)
    assert view.service.settings()["waiver_faab_budget"] == 4
