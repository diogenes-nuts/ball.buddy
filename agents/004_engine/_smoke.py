"""M3.1 engine smoke (run: .venv/Scripts/python agents/004_engine/_smoke.py).

Reproduces the M3.1 report numbers from the test fixture (tests/domain/
test_engine.py: P1-P4, gp=40, rosters A=[P1,P2], B=[P3,P4]):
  gaps: pts +520, reb +360, ast -80, stl +32, blk +36, to +20, three +60,
        fg_pct +0.03187135, ft_pct +0.00577778
  cat_wins 7-2, deterministic winner A, P(A) seed=42 = 0.9763 (reproducible),
  identical rosters -> all-9-cat tie, push (no tie-break data).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ball_buddy.domain.engine import matchup, project_roster  # noqa: E402


def _row(name: str, **stats: str) -> dict[str, str]:
    row = {c: "" for c in (
        "name", "gp", "pts_pg", "reb_pg", "ast_pg", "stl_pg", "blk_pg",
        "to_pg", "fg_pct", "fga_pg", "ft_pct", "fta_pg", "three_pg",
    )}
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


def main() -> None:
    a, b = project_roster([P1, P2], "A"), project_roster([P3, P4], "B")
    det = matchup(a, b)
    print("gaps:", {k: round(v, 8) for k, v in det.gaps.items()})
    print("cat_wins:", det.cat_wins, "winner:", det.winner)
    p1 = matchup(a, b, mc=True, seed=42).p_win
    p2 = matchup(a, b, mc=True, seed=42).p_win
    print(f"P(A) seed42: {p1:.4f}  reproducible={p1 == p2}")
    twin = matchup(a, project_roster([P1, P2], "B"))
    print("tie winner (expect None):", twin.winner)


if __name__ == "__main__":
    main()
