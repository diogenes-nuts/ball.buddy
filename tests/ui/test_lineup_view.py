"""LineupView tests (offscreen Qt): fixture optimize render, toggles, errors.

Pool rows are the 14-player M5.1 fixture (2 PG, 2 PG/SG, 1 SG, 2 SF, 2 PF,
1 SF/PF, 2 C, 1 PG/SG/SF, 1 C/PF — 5 UTL-eligible), all kept by Red; Blue
keeps 10 of them as the opponent roster. Optimizer math itself is covered by
tests/domain/test_lineup.py (M5.1) — here we only check the UI seams:
slot-ordered starter table, sitters + rationale, 9-cat outcomes, play
toggles, and error banners (no exceptions).
"""

import os
import sys
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"  # must be set before any PySide6 import

import pytest
from PySide6.QtWidgets import QApplication

from ball_buddy.domain.keepers import KeeperEntry
from ball_buddy.domain.keepers import save as save_keepers
from ball_buddy.domain.lineup import SLOTS
from ball_buddy.io.pool.importer import FIELDNAMES, write_csv
from ball_buddy.io.yahoo.client import YahooClient
from ball_buddy.io.yahoo.snapshot import save_snapshot, to_snapshot
from ball_buddy.services.sync import SyncService
from ball_buddy.ui.views.lineups import LineupView

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tests.io.test_snapshot import load_results
from tests.io.test_yahoo_client import FakeQuery  # noqa: E402


def _row(name: str, pos: str, **overrides: str) -> dict[str, str]:
    row = {field: "" for field in FIELDNAMES}
    row.update(
        name=name, pos=pos, gp="40",
        pts_pg="10", reb_pg="4", ast_pg="2", stl_pg="1", blk_pg="0.5",
        to_pg="1.5", three_pg="1.5", fg_pct=".48", fga_pg="12",
        ft_pct=".40", fta_pg="5",
    )
    row.update(overrides)
    return row


ROWS = [
    _row("Aiden", "PG"),
    _row("Bram", "PG"),
    _row("Cyrus", "PG/SG"),
    _row("Dane", "SG"),
    _row("Eli", "SF"),
    _row("Gus", "SF"),
    _row("Finn", "PF"),
    _row("Moe", "PF"),
    _row("Ivan", "SF/PF"),
    _row("Jon", "C"),
    _row("Kip", "C"),
    _row("Leo", "PG/SG/SF"),
    _row("Zeta", "PG/SG", pts_pg="6", ft_pct=".80", fta_pg="6"),
    _row("Yankee", "C/PF", pts_pg="9", ft_pct=".75", fta_pg="7"),
]
NAMES = [row["name"] for row in ROWS]


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def view(tmp_path: Path, qapp: QApplication) -> LineupView:
    service = SyncService(tmp_path, client=YahooClient(FakeQuery(), "k", "s"))
    doc = to_snapshot(load_results(), "1234")
    save_snapshot(doc, service.snapshot_path)
    write_csv(ROWS, service.pool_path)
    save_keepers(
        [KeeperEntry(team="Red", player=name, cost_round=1) for name in NAMES]
        + [KeeperEntry(team="Blue", player=name, cost_round=1)
           for name in NAMES[:10]],
        service.data_dir / "keepers.json",
    )
    return LineupView(service)


def _optimize(view: LineupView) -> None:
    view.pick_teams("Red", "Blue")
    view.optimize()


def test_optimize_renders_starters_sits_cats(view: LineupView) -> None:
    _optimize(view)
    # 10 starter rows in fixed SLOTS order, pts cells numeric
    assert view.starters_table.rowCount() == 10
    for i, slot in enumerate(SLOTS):
        assert view.starters_table.item(i, 0).text() == slot
        float(view.starters_table.item(i, 2).text())
    starter_names = [view.starters_table.item(i, 1).text() for i in range(10)]
    assert len(set(starter_names)) == 10
    # 4 sitters, each with a non-empty rationale
    assert view.sits_table.rowCount() == 4
    for i in range(4):
        assert view.sits_table.item(i, 0).text() in NAMES
        assert view.sits_table.item(i, 1).text()
    # 9-cat outlook: gaps + outcome in {win, tie, lose}
    assert view.cat_table.rowCount() == 9
    for i in range(9):
        assert view.cat_table.item(i, 2).text() in {"win", "tie", "lose"}
    # summary line: cat wins + margin
    assert "cats" in view.summary_label.text()
    assert "margin" in view.summary_label.text()
    # no MC by default -> no P(win)
    assert "P(win)" not in view.summary_label.text()
    # pre-draft: everyone checked -> optimize notes the all-play assumption
    assert "no schedule: assuming all play" in view.banner.text()


def test_uncheck_one_player_still_10_4(view: LineupView) -> None:
    _optimize(view)
    # Kip is a base-set sitter, so the optimum stays slot-able when he sits
    # (a few starter exclusions hit the documented M5.1 gap where the best
    # SET is unslot-able -> ValueError, covered by the banner test below).
    view.set_checked("Kip", False)
    assert view._playing() == frozenset(NAMES) - {"Kip"}
    view.optimize()
    assert view.starters_table.rowCount() == 10
    # 3 optimizer sitters + Kip (toggled off, display-only sit row)
    assert view.sits_table.rowCount() == 4
    sit_names = [view.sits_table.item(i, 0).text() for i in range(4)]
    assert sit_names.count("Kip") == 1
    for i in range(4):
        assert view.sits_table.item(i, 1).text()
    assert "assuming all play" not in view.banner.text()


def test_fewer_than_ten_playable_banners_slot(view: LineupView) -> None:
    _optimize(view)
    for name in NAMES[:5]:  # 9 playable left
        view.set_checked(name, False)
    view.optimize()  # must not raise
    assert "only 9 playable row(s)" in view.banner.text()
    assert "PG" in view.banner.text()
    assert view.starters_table.rowCount() == 0
    assert view.sits_table.rowCount() == 0
    assert view.cat_table.rowCount() == 0
    assert view.summary_label.text() == ""


def test_mc_trials_adds_pwin_display(view: LineupView) -> None:
    _optimize(view)
    view.mc_spin.setValue(1_000)
    view.seed_spin.setValue(42)
    view.optimize()
    assert "P(win)=" in view.summary_label.text()
    assert "seed 42" in view.summary_label.text()


def test_empty_pool_banners(qapp, tmp_path: Path) -> None:
    service = SyncService(tmp_path, client=YahooClient(FakeQuery(), "k", "s"))
    doc = to_snapshot(load_results(), "1234")
    save_snapshot(doc, service.snapshot_path)
    write_csv(ROWS, service.pool_path)
    # keepers exist, but the pool names do not resolve (ghost names)
    save_keepers(
        [
            KeeperEntry(team="Red", player="Ghost A", cost_round=1),
            KeeperEntry(team="Blue", player="Ghost B", cost_round=1),
        ],
        service.data_dir / "keepers.json",
    )
    v = LineupView(service)
    v.pick_teams("Red", "Blue")
    v.optimize()  # must not raise
    assert "Empty roster" in v.banner.text()
    assert "Ghost A" in v.banner.text()
    assert v.starters_table.rowCount() == 0
