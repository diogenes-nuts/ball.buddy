"""Tests for trade scoring (M6.1)."""

from __future__ import annotations

import pytest

from ball_buddy.domain.players import PlayerPool
from ball_buddy.domain.trade import Trade, analyze_trade

TRIALS = 50  # low for speed; seeds make results reproducible
SEED = 11


def _row(name: str, **stats: str) -> dict[str, str]:
    row = {column: "" for column in (
        "name", "gp", "pts_pg", "reb_pg", "ast_pg", "stl_pg", "blk_pg",
        "to_pg", "fg_pct", "fga_pg", "ft_pct", "fta_pg", "three_pg",
    )}
    row["name"] = name
    row["gp"] = "40"
    row.update(stats)
    return row


# My roster: 2 strong (S1 best, S2) + 2 weak (W1, W2; W2 weakest).
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

# Their roster: O1 solid mid, O2/O3 middling (O2 their worst on pts).
O1 = _row("O1", pts_pg="14", reb_pg="4", ast_pg="4", stl_pg="1.0",
          blk_pg=".7", to_pg="2.2", three_pg="1.8", fg_pct=".46",
          fga_pg="13", ft_pct=".84", fta_pg="3")
O2 = _row("O2", pts_pg="13", reb_pg="5", ast_pg="3", stl_pg=".9",
          blk_pg=".8", to_pg="2.4", three_pg="1.5", fg_pct=".45",
          fga_pg="12", ft_pct=".82", fta_pg="3")
O3 = _row("O3", pts_pg="15", reb_pg="3", ast_pg="4", stl_pg="1.1",
          blk_pg=".6", to_pg="2.0", three_pg="2.2", fg_pct=".47",
          fga_pg="14", ft_pct=".86", fta_pg="3")

POOL = PlayerPool([S1, S2, W1, W2, O1, O2, O3])
MY_ROSTER = ["S1", "S2", "W1", "W2"]
THEIR_ROSTER = ["O1", "O2", "O3"]


def test_good_one_for_one() -> None:
    # Give W1 (mine, weak) for O1 (theirs, solid): clearly positive for me.
    result = analyze_trade(
        Trade(my_give=("W1",), their_give=("O1",)),
        MY_ROSTER, THEIR_ROSTER, POOL,
        trials=TRIALS, seed=SEED,
    )
    assert result.my_delta_p > 0
    assert result.their_delta_p < 0
    assert result.fairness_flag is False
    assert result.my_names_after == ("S1", "S2", "W2", "O1")
    assert result.their_names_after == ("O2", "O3", "W1")
    assert result.summary.startswith("you +")


def test_bad_trade_flags_fairness() -> None:
    # Give my best (S1) for their worst (O2): loses P(win) for me.
    result = analyze_trade(
        Trade(my_give=("S1",), their_give=("O2",)),
        MY_ROSTER, THEIR_ROSTER, POOL,
        trials=TRIALS, seed=SEED,
    )
    assert result.my_delta_p < 0
    assert result.their_delta_p > 0
    assert result.fairness_flag is True


def test_name_not_on_my_roster() -> None:
    with pytest.raises(ValueError, match="Ghost"):
        analyze_trade(
            Trade(my_give=("Ghost",), their_give=("O1",)),
            MY_ROSTER, THEIR_ROSTER, POOL,
            trials=TRIALS, seed=SEED,
        )


def test_name_not_in_pool() -> None:
    # "O1" is on their roster but a give from my side must be on MINE.
    with pytest.raises(ValueError, match="O1"):
        analyze_trade(
            Trade(my_give=("O1",), their_give=("O2",)),
            MY_ROSTER, THEIR_ROSTER, POOL,
            trials=TRIALS, seed=SEED,
        )


def test_roster_name_missing_from_pool() -> None:
    # A roster (non-give) name the pool can't resolve must raise the same
    # loud ValueError, not crash inside project_roster with a TypeError.
    with pytest.raises(ValueError, match="GHOST"):
        analyze_trade(
            Trade(my_give=("W1",), their_give=("O1",)),
            ["S1", "S2", "W1", "GHOST"], THEIR_ROSTER, POOL,
            trials=TRIALS, seed=SEED,
        )


def test_two_for_two() -> None:
    result = analyze_trade(
        Trade(my_give=("W1", "W2"), their_give=("O1", "O2")),
        MY_ROSTER, THEIR_ROSTER, POOL,
        trials=TRIALS, seed=SEED,
    )
    assert result.my_names_after == ("S1", "S2", "O1", "O2")
    assert result.their_names_after == ("O3", "W1", "W2")


def test_summary_format() -> None:
    result = analyze_trade(
        Trade(my_give=("W1",), their_give=("O1",)),
        MY_ROSTER, THEIR_ROSTER, POOL,
        trials=TRIALS, seed=SEED,
    )
    mirror = f"you {result.my_delta_p:+.2f}, them {result.their_delta_p:+.2f}"
    assert result.summary.startswith(mirror)
    assert result.summary.endswith((" likely a bad deal", " looks fair"))


def test_both_sides_empty_rejected() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        analyze_trade(
            Trade(my_give=(), their_give=()),
            MY_ROSTER, THEIR_ROSTER, POOL,
            trials=TRIALS, seed=SEED,
        )


def test_determinism() -> None:
    trade = Trade(my_give=("W1",), their_give=("O1",))
    first = analyze_trade(
        trade, MY_ROSTER, THEIR_ROSTER, POOL, trials=TRIALS, seed=SEED
    )
    second = analyze_trade(
        trade, MY_ROSTER, THEIR_ROSTER, POOL, trials=TRIALS, seed=SEED
    )
    assert first.my_delta_p == second.my_delta_p
    assert first.their_delta_p == second.their_delta_p
    assert first.my_gaps_after == second.my_gaps_after


def test_symmetry_roles_swapped() -> None:
    trade = Trade(my_give=("W1",), their_give=("O1",))
    # More trials here: the two role-swapped calls draw different MC
    # streams (A/B order), so the sign-mirror only holds up to MC noise;
    # 2000 trials keeps that well inside the 0.05 tolerance.
    mine = analyze_trade(
        trade, MY_ROSTER, THEIR_ROSTER, POOL, trials=2000, seed=SEED
    )
    theirs = analyze_trade(
        Trade(my_give=("O1",), their_give=("W1",)),
        THEIR_ROSTER, MY_ROSTER, POOL, trials=2000, seed=SEED,
    )
    # Each side's "my_delta" from their seat mirrors my "my_delta".
    assert abs(theirs.my_delta_p - (-mine.my_delta_p)) < 0.05
    assert abs(theirs.their_delta_p - (-mine.their_delta_p)) < 0.05


def test_gaps_after_hand_computed() -> None:
    # Give W1 (12 pts/pg) for O1 (14 pts/pg): my pts +2/pg (+80 season)
    # AND their pts -2/pg (-80 season), so the gap (me - them) rises by
    # exactly +160 (deterministic mode, hand-computed).
    result = analyze_trade(
        Trade(my_give=("W1",), their_give=("O1",)),
        MY_ROSTER, THEIR_ROSTER, POOL,
        trials=TRIALS, seed=SEED,
    )
    assert result.my_gaps_after["pts"] == result.my_gaps_before["pts"] + 160.0
    # Theirs is the sign-flip of mine.
    assert result.their_gaps_before["pts"] == -result.my_gaps_before["pts"]
    assert result.their_gaps_after["pts"] == -result.my_gaps_after["pts"]
