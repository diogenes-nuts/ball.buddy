"""MatchupView tests (offscreen Qt): fixture roster rendering, MC run.

Reuses the M3.1 engine fixture rows (P1-P4, gp=40) as players.csv and
keepers.json (Red keeps P1/P2, Blue keeps P3/P4) over the fixture
snapshot (teams Red/Blue). Expected numbers from
``tests/domain/test_engine.py`` / ``agents/004_engine/_smoke.py``:
gaps +520/+360/-80/+32/+36/+20/+60, fg +0.03187135, ft +0.00577778,
cat_wins 7-2, winner Red, MC(seed 42, 10000) = 0.9763.
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
from ball_buddy.ui.views.matchup import MatchupView

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
def view(tmp_path: Path, qapp: QApplication) -> MatchupView:
    service = SyncService(tmp_path, client=YahooClient(FakeQuery(), "k", "s"))
    doc = to_snapshot(
        load_results(),
        "1234",
    )
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
    return MatchupView(service)


def test_headline_winner_and_cat_wins(view: MatchupView) -> None:
    view.pick_teams("Red", "Blue")
    assert "Red wins" in view.headline_label.text()
    assert "7-2" in view.headline_label.text()
    assert "No lineups yet" in view.banner.text()
    # W/L column per cat (CATS order: pts reb ast stl blk to three fg ft)
    wl = [view.cat_table.item(i, 4).text() for i in range(9)]
    assert wl == ["A", "A", "B", "A", "A", "B", "A", "A", "A"]


def test_gap_cells_match_m31_fixture(view: MatchupView) -> None:
    view.pick_teams("Red", "Blue")
    gaps = [view.cat_table.item(i, 1).text() for i in range(9)]
    assert gaps == [
        "+520", "+360", "-80", "+32", "+36", "+20", "+60",
        "+0.03187135", "+0.00577778",
    ]
    assert view.gap_bars.gaps["pts"] == pytest.approx(520)
    assert view.gap_bars.gaps["fg_pct"] == pytest.approx(18.1 / 38 - 12 / 27, abs=1e-9)


def test_marginal_table_order_and_signs(view: MatchupView) -> None:
    view.pick_teams("Red", "Blue")
    assert view.marginal_table.rowCount() == 4
    names = [view.marginal_table.item(i, 0).text() for i in range(4)]
    sides = [view.marginal_table.item(i, 1).text() for i in range(4)]
    assert names == ["P1", "P2", "P3", "P4"]
    assert sides == ["A", "A", "B", "B"]
    # P1 pts contribution +800; P3 pts contribution -600; pct cols are "–"
    assert view.marginal_table.item(0, 2).text() == "+800.0"
    assert view.marginal_table.item(2, 2).text() == "-600.0"
    assert view.marginal_table.item(0, 9).text() == "–"
    assert view.marginal_table.item(0, 10).text() == "–"


def test_week_combo_from_schedule(view: MatchupView) -> None:
    assert [view.week_combo.itemText(i) for i in range(view.week_combo.count())] == [
        "1", "2",
    ]
    assert "unused pre-draft" in view.week_note.text()


def test_run_mc_seeded(view: MatchupView) -> None:
    view.pick_teams("Red", "Blue")
    view.seed_spin.setValue(42)
    view.trials_spin.setValue(10_000)
    view.mc_button.click()
    assert "0.9763" in view.mc_label.text()
    assert "seed 42" in view.mc_label.text()
    assert "10000 trials" in view.mc_label.text()


def test_tie_break_persisted_to_settings(view: MatchupView) -> None:
    assert view.service.settings().get("matchup_tie_break") is None
    view.tie_break_combo.setCurrentText("h2h")
    assert view.service.settings()["matchup_tie_break"] == "h2h"


def test_h2h_tie_break_uses_snapshot_standings(qapp, tmp_path: Path) -> None:
    """W1: on a true cat-tie the view must consult snapshot standings.

    Red and Blue both keep only P1 -> identical rosters -> 4-4 cat-tie.
    Standings say Blue 5-0 vs Red 0-5 -> h2h mode picks Blue; with no
    standings evidence it stays a push.
    """
    service = SyncService(tmp_path, client=YahooClient(FakeQuery(), "k", "s"))
    doc = to_snapshot(load_results(), "1234")
    doc["standings"] = [
        {"team_key": "1234-1", "name": "Red", "rank": 2,
         "wins": 0, "losses": 5, "ties": 0},
        {"team_key": "1234-2", "name": "Blue", "rank": 1,
         "wins": 5, "losses": 0, "ties": 0},
    ]
    save_snapshot(doc, service.snapshot_path)
    write_csv([P1], service.pool_path)
    save_keepers(
        [
            KeeperEntry(team="Red", player="P1", cost_round=1),
            KeeperEntry(team="Blue", player="P1", cost_round=1),
        ],
        service.data_dir / "keepers.json",
    )
    v = MatchupView(service)
    v.pick_teams("Red", "Blue")
    assert "Push" in v.headline_label.text()  # cat-tie; yahoo_default has no catwins
    v.tie_break_combo.setCurrentText("h2h")
    assert "Blue wins" in v.headline_label.text()


def test_empty_rosters_do_not_crash(qapp, tmp_path: Path) -> None:
    service = SyncService(tmp_path, client=YahooClient(FakeQuery(), "k", "s"))
    doc = to_snapshot(
        load_results(),
        "1234",
    )
    save_snapshot(doc, service.snapshot_path)
    write_csv([P1], service.pool_path)  # pool exists, but no keepers/picks
    v = MatchupView(service)
    v.pick_teams("Red", "Blue")
    assert "No snapshot" not in v.headline_label.text()
    assert "Empty roster" in v.week_note.text()


# -- offline manual team list -------------------------------------------------


def test_manual_teams_populate_combos(qapp, tmp_path):
    service = SyncService(tmp_path, client=YahooClient(FakeQuery(), "k", "s"))
    settings = service.settings()
    settings["manual_teams"] = ["Alpha", "Beta"]
    service.save_settings(settings)
    write_csv([P1, P2, P3, P4], service.pool_path)
    save_keepers(
        [
            KeeperEntry(team="Alpha", player="P1", cost_round=1),
            KeeperEntry(team="Beta", player="P3", cost_round=1),
        ],
        service.data_dir / "keepers.json",
    )
    view = MatchupView(service)
    assert not view.offline_banner.isHidden()
    assert "manual team list" in view.offline_banner.text()
    names = [view.team_a_combo.itemText(i) for i in range(view.team_a_combo.count())]
    assert names == ["Alpha", "Beta"]
    # pre-draft rosters resolve from the manual team's keepers
    view.pick_teams("Alpha", "Beta")
    assert view.marginal_table.rowCount() == 2
