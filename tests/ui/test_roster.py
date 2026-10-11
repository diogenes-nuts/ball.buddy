"""Direct unit tests for the shared roster resolver (ui/views/_roster.py).

Reuses the M3.1 engine fixture rows (P1-P4, gp=40) and fixture snapshot,
same fixture shape as tests/ui/test_matchup_view.py — but exercises the
module function directly, no view construction.
"""

import os
import sys
import time
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"  # must be set before any PySide6 import

import ball_buddy.ui.views._roster as roster_mod
from ball_buddy.domain import picks as picks_mod
from ball_buddy.domain.keepers import KeeperEntry
from ball_buddy.domain.keepers import save as save_keepers
from ball_buddy.domain.players import PlayerPool
from ball_buddy.io.pool.importer import FIELDNAMES, write_csv
from ball_buddy.io.yahoo.client import YahooClient
from ball_buddy.io.yahoo.snapshot import save_snapshot, to_snapshot
from ball_buddy.services.sync import SyncService
from ball_buddy.ui.views._roster import (
    clear_cache,
    team_roster_names,
    team_roster_rows,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tests.io.test_snapshot import load_results  # noqa: E402
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


def _service(tmp_path: Path, pool_rows: list[dict]) -> SyncService:
    service = SyncService(tmp_path, client=YahooClient(FakeQuery(), "k", "s"))
    save_snapshot(to_snapshot(load_results(), "1234"), service.snapshot_path)
    write_csv(pool_rows, service.pool_path)
    return service


def test_rows_dedupe_order_and_missing(tmp_path: Path) -> None:
    """Keeper-then-pick order kept; a pick duplicating a keeper resolves
    once; unresolvable names (no pool row) land in ``missing`` once each."""
    service = _service(tmp_path, [P1, P2])
    save_keepers(
        [
            KeeperEntry(team="Red", player="P1", cost_round=1),
            KeeperEntry(team="Red", player="P2", cost_round=2),
        ],
        service.data_dir / "keepers.json",
    )
    picks_mod.save(
        [
            picks_mod.DraftPick(2, 1, "Red", "P1"),  # duplicate of keeper
            picks_mod.DraftPick(3, 1, "Red", "Nope"),
            picks_mod.DraftPick(4, 1, "Red", "Nope"),
        ],
        service.data_dir / picks_mod.PICKS_FILE,
    )
    rows, missing = team_roster_rows(service, "Red")
    assert [row["name"] for row in rows] == ["P1", "P2"]
    assert missing == ["Nope"]


def test_names_wrapper_matches_rows(tmp_path: Path) -> None:
    service = _service(tmp_path, [P1])
    save_keepers(
        [KeeperEntry(team="Red", player="P1", cost_round=1)],
        service.data_dir / "keepers.json",
    )
    names, missing = team_roster_names(service, "Red")
    assert names == ["P1"]
    assert missing == []


def test_unknown_and_empty_team_name(tmp_path: Path) -> None:
    service = _service(tmp_path, [P1])
    save_keepers(
        [KeeperEntry(team="Red", player="P1", cost_round=1)],
        service.data_dir / "keepers.json",
    )
    assert team_roster_rows(service, "Ghost") == ([], [])
    assert team_roster_rows(service, "") == ([], [])
    assert team_roster_names(service, "Ghost") == ([], [])
    assert team_roster_names(service, "") == ([], [])


def test_missing_only_counts_unresolvable_names(tmp_path: Path) -> None:
    """A name absent from the pool (keeper-only team) is reported in
    ``missing`` but never in the rows."""
    service = _service(tmp_path, [P1, P2])
    save_keepers(
        [
            KeeperEntry(team="Red", player="P1", cost_round=1),
            KeeperEntry(team="Red", player="Absent", cost_round=2),
        ],
        service.data_dir / "keepers.json",
    )
    rows, missing = team_roster_rows(service, "Red")
    assert [row["name"] for row in rows] == ["P1"]
    assert missing == ["Absent"]


def test_quad_cache_hits_and_invalidates(tmp_path: Path, monkeypatch) -> None:
    """R5.2: the (pool, keepers, picks, aliases) quad loads once per data
    dir until a file mtime changes; ``clear_cache()`` forces a reload."""
    service = _service(tmp_path, [P1, P2])
    keepers_path = service.data_dir / "keepers.json"
    save_keepers(
        [KeeperEntry(team="Red", player="P1", cost_round=1)], keepers_path
    )
    # Count pool loads through the module's own PlayerPool reference.
    real_load = PlayerPool.load.__func__
    counts = {"n": 0}

    def counting_load(cls, path):
        counts["n"] += 1
        return real_load(cls, path)

    monkeypatch.setattr(roster_mod.PlayerPool, "load", classmethod(counting_load))
    clear_cache()  # don't rely on other tests' cache state

    rows1, missing1 = team_roster_rows(service, "Red")
    assert [row["name"] for row in rows1] == ["P1"]
    assert counts["n"] == 1
    # Identical state -> cache hit, no reload (team_roster_rows must reuse
    # the cached pool too, not load a second time).
    rows2, missing2 = team_roster_rows(service, "Red")
    assert (rows2, missing2) == (rows1, missing1)
    assert counts["n"] == 1

    # Mtime change on keepers.json -> the whole quad reloads and reflects it.
    # Explicit utime: don't rely on filesystem timestamp resolution.
    save_keepers(
        [
            KeeperEntry(team="Red", player="P1", cost_round=1),
            KeeperEntry(team="Red", player="P2", cost_round=2),
        ],
        keepers_path,
    )
    os.utime(keepers_path, (keepers_path.stat().st_atime, time.time() + 1000))
    rows3, _missing3 = team_roster_rows(service, "Red")
    assert [row["name"] for row in rows3] == ["P1", "P2"]
    assert counts["n"] == 2

    # clear_cache() forces a reload even with unchanged mtimes.
    team_roster_rows(service, "Red")
    assert counts["n"] == 2
    clear_cache()
    team_roster_rows(service, "Red")
    assert counts["n"] == 3
