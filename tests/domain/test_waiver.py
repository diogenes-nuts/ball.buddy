"""Tests for waiver-pick scoring (M4.1)."""

from __future__ import annotations

import pytest

from ball_buddy.domain.players import PlayerPool
from ball_buddy.domain.waiver import WaiverCandidate, rank_candidates

TRIALS = 50  # low for speed; seeds make results reproducible


def _row(name: str, **stats: str) -> dict[str, str]:
    row = {column: "" for column in (
        "name", "gp", "pts_pg", "reb_pg", "ast_pg", "stl_pg", "blk_pg",
        "to_pg", "fg_pct", "fga_pg", "ft_pct", "fta_pg", "three_pg",
    )}
    row["name"] = name
    row["gp"] = "40"
    row.update(stats)
    return row


# Roster: 2 strong (S1 high-PTS, S2 high-AST) + 2 weak (W1, W2; W2 weakest).
S1 = _row("S1", pts_pg="22", reb_pg="5", ast_pg="3", stl_pg="1.0",
          blk_pg=".8", to_pg="2.0", three_pg="3.0", fg_pct=".50",
          fga_pg="20", ft_pct=".85", fta_pg="4")
S2 = _row("S2", pts_pg="15", reb_pg="3", ast_pg="9", stl_pg="1.2",
          blk_pg=".5", to_pg="2.5", three_pg="2.0", fg_pct=".48",
          fga_pg="14", ft_pct=".90", fta_pg="3")
W1 = _row("W1", pts_pg="12", reb_pg="4", ast_pg="2", stl_pg=".6",
          blk_pg=".4", to_pg="1.5", three_pg="1.0", fg_pct=".42",
          fga_pg="10", ft_pct=".75", fta_pg="2")
W2 = _row("W2", pts_pg="7", reb_pg="2", ast_pg="1", stl_pg=".4",
          blk_pg=".2", to_pg="1.8", three_pg=".5", fg_pct=".38",
          fga_pg="7", ft_pct=".70", fta_pg="1")

# Opponent: 3 mid rows.
O1 = _row("O1", pts_pg="14", reb_pg="4", ast_pg="4", stl_pg="1.0",
          blk_pg=".7", to_pg="2.2", three_pg="1.8", fg_pct=".46",
          fga_pg="13", ft_pct=".84", fta_pg="3")
O2 = _row("O2", pts_pg="13", reb_pg="5", ast_pg="3", stl_pg=".9",
          blk_pg=".8", to_pg="2.4", three_pg="1.5", fg_pct=".45",
          fga_pg="12", ft_pct=".82", fta_pg="3")
O3 = _row("O3", pts_pg="15", reb_pg="3", ast_pg="4", stl_pg="1.1",
          blk_pg=".6", to_pg="2.0", three_pg="2.2", fg_pct=".47",
          fga_pg="14", ft_pct=".86", fta_pg="3")

# Candidates: Star (dominant PTS/REB), Point (big AST, near-redundant vs S2),
# Mid (average).
STAR = _row("Star", pts_pg="28", reb_pg="9", ast_pg="2", stl_pg="1.2",
            blk_pg="1.4", to_pg="2.2", three_pg="4.0", fg_pct=".52",
            fga_pg="22", ft_pct=".88", fta_pg="5")
POINT = _row("Point", pts_pg="14", reb_pg="2", ast_pg="11", stl_pg="1.4",
             blk_pg=".3", to_pg="2.8", three_pg="2.0", fg_pct=".46",
             fga_pg="13", ft_pct=".88", fta_pg="2")
MID = _row("Mid", pts_pg="14", reb_pg="4", ast_pg="4", stl_pg="1.0",
           blk_pg=".7", to_pg="2.2", three_pg="1.8", fg_pct=".46",
           fga_pg="13", ft_pct=".84", fta_pg="3")

POOL = PlayerPool([
    S1, S2, W1, W2, O1, O2, O3, STAR, POINT, MID,
])
ROSTER = ["S1", "S2", "W1", "W2"]
OPPONENT = ["O1", "O2", "O3"]
CANDIDATES = [
    WaiverCandidate("Star", faab_cost=30),
    WaiverCandidate("Point"),
    WaiverCandidate("Mid", faab_cost=10),
]


def test_ranking_order() -> None:
    result = rank_candidates(
        CANDIDATES, ROSTER, OPPONENT, POOL,
        trials=TRIALS, seed=7,
    )
    assert [r.candidate.name for r in result] == ["Star", "Point", "Mid"]
    assert result[0].candidate.name == "Star"
    assert result[0].delta_p > result[2].delta_p


def test_best_drop() -> None:
    result = rank_candidates(
        CANDIDATES, ROSTER, OPPONENT, POOL,
        trials=TRIALS, seed=7,
    )
    by_name = {r.candidate.name: r for r in result}
    # Point adds an AST guard: best when the weakest slot (W2) is replaced.
    assert by_name["Point"].best_drop == "W2"
    assert by_name["Star"].best_drop in ROSTER


def test_determinism() -> None:
    first = rank_candidates(
        CANDIDATES, ROSTER, OPPONENT, POOL, trials=TRIALS, seed=7,
    )
    second = rank_candidates(
        CANDIDATES, ROSTER, OPPONENT, POOL, trials=TRIALS, seed=7,
    )
    for a, b in zip(first, second):
        assert a.delta_p == b.delta_p
        assert a.cat_delta == b.cat_delta


def test_budget() -> None:
    result = rank_candidates(
        CANDIDATES, ROSTER, OPPONENT, POOL,
        faab_budget=20, trials=TRIALS, seed=7,
    )
    by_name = {r.candidate.name: r for r in result}
    assert by_name["Star"].over_budget is True  # 30 > 20
    assert by_name["Point"].over_budget is False  # cost None


def test_unmatched_candidate() -> None:
    with pytest.raises(ValueError, match="Not A Player"):
        rank_candidates(
            [WaiverCandidate("Not A Player")], ROSTER, OPPONENT, POOL,
            trials=TRIALS, seed=7,
        )


def test_unmatched_roster_name() -> None:
    with pytest.raises(ValueError, match="Ghost"):
        rank_candidates(
            [WaiverCandidate("Mid")], ["S1", "Ghost"], OPPONENT, POOL,
            trials=TRIALS, seed=7,
        )


def test_negative_faab_cost() -> None:
    with pytest.raises(ValueError, match="faab_cost"):
        rank_candidates(
            [WaiverCandidate("Mid", faab_cost=-1)], ROSTER, OPPONENT, POOL,
            trials=TRIALS, seed=7,
        )


def test_empty_roster() -> None:
    result = rank_candidates(
        CANDIDATES, [], OPPONENT, POOL, trials=TRIALS, seed=7,
    )
    assert len(result) == len(CANDIDATES)
    for r in result:
        assert r.best_drop is None
        assert r.rationale  # non-empty


def test_rationale_mentions_category() -> None:
    result = rank_candidates(
        CANDIDATES, ROSTER, OPPONENT, POOL, trials=TRIALS, seed=7,
    )
    for r in result:
        assert " (was " in r.rationale
        assert r.rationale.endswith(")")
        cat = r.rationale.split(" ")[0]
        assert cat.upper() == cat and cat in (
            "PTS", "REB", "AST", "STL", "BLK", "TO", "THREE", "FG_PCT",
            "FT_PCT",
        )
