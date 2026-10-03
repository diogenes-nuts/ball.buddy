"""Tests for the headless projection engine (M3.1)."""

from __future__ import annotations

import pytest

from ball_buddy.domain.engine import (
    CATS,
    MatchupResult,
    matchup,
    project_player,
    project_roster,
    win_prob,
)


def _row(name: str, **stats: str) -> dict[str, str]:
    row = {column: "" for column in (
        "name", "gp", "pts_pg", "reb_pg", "ast_pg", "stl_pg", "blk_pg",
        "to_pg", "fg_pct", "fga_pg", "ft_pct", "fta_pg", "three_pg",
    )}
    row["name"] = name
    row["gp"] = "40"
    row.update(stats)
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


@pytest.fixture()
def rosters() -> tuple[object, object]:
    return (
        project_roster([P1, P2], "A"),
        project_roster([P3, P4], "B"),
    )


def test_roster_values_exact(rosters) -> None:
    a, b = rosters
    expected_a = {
        "pts": 1520, "reb": 720, "ast": 360, "stl": 100, "blk": 88, "to": 180,
        "three": 200, "fg_pct": 18.1 / 38, "ft_pct": 7.9 / 9,
    }
    expected_b = {
        "pts": 1000, "reb": 360, "ast": 440, "stl": 68, "blk": 52, "to": 160,
        "three": 140, "fg_pct": 12 / 27, "ft_pct": 4.36 / 5,
    }
    for roster, expected in ((a, expected_a), (b, expected_b)):
        assert set(roster.cat_values) == set(CATS)
        for cat, value in expected.items():
            assert roster.cat_values[cat] == pytest.approx(value, abs=1e-9)
    assert a.warnings == []
    assert b.warnings == []


def test_deterministic_gaps_and_winner(rosters) -> None:
    a, b = rosters
    result = matchup(a, b)
    expected_gaps = {
        "pts": 520, "reb": 360, "ast": -80, "stl": 32, "blk": 36, "to": 20,
        "three": 60,
        "fg_pct": 18.1 / 38 - 12 / 27,  # ~ +0.03187135
        "ft_pct": 7.9 / 9 - 0.872,  # ~ +0.00577778
    }
    for cat, value in expected_gaps.items():
        assert result.gaps[cat] == pytest.approx(value, abs=1e-9)
    by_cat = dict(zip(CATS, result.cat_outcomes))
    assert by_cat["to"] == ("loss", "win")  # A's TO gap is positive -> B wins TO
    assert by_cat["ast"] == ("loss", "win")
    assert result.cat_wins == (7, 2)
    assert result.winner == "A"
    assert result.p_win is None


def test_identical_projections_tie_and_tie_breaks() -> None:
    a = project_roster([P1, P2], "A")
    b = project_roster([P1, P2], "B")  # identical projections, named B
    result = matchup(a, b)
    assert all(out == ("tie", "tie") for out in result.cat_outcomes)
    assert result.winner is None  # no tie-break data -> push

    result = matchup(a, b, catwins={"A": 6, "B": 5})  # yahoo_default
    assert result.winner == "A"

    result = matchup(a, b, tie_break="h2h", h2h={"A": (1, 3), "B": (3, 1)})
    assert result.winner == "B"


def test_tie_break_missing_data_is_push() -> None:
    a = project_roster([P1], "A")
    b = project_roster([P1], "B")
    result = matchup(a, b, catwins={"A": 6})
    assert result.winner is None  # B missing from evidence -> push
    result = matchup(a, b, tie_break="h2h", h2h={"A": (1, 3)})
    assert result.winner is None  # B missing from evidence -> push


def test_mc_seeded_plausible_and_reproducible(rosters) -> None:
    a, b = rosters
    first = matchup(a, b, mc=True, seed=42)
    assert isinstance(first, MatchupResult)
    assert first.p_win is not None
    assert 0.5 < first.p_win < 1.0
    assert first.p_win == win_prob(a, b, seed=42)  # wrapper agrees
    assert 0.0 <= first.p_win <= 1.0
    again = matchup(a, b, mc=True, seed=42)
    assert again.p_win == first.p_win  # bit-identical under the same seed
    reversed_prob = matchup(b, a, mc=True, seed=42).p_win
    assert reversed_prob is not None and reversed_prob < 0.5  # P(B) < 0.5


def test_mc_different_seed_may_differ() -> None:
    roster = project_roster([P1, P2], "A")
    other = project_roster([P3, P4], "B")
    p1 = matchup(roster, other, mc=True, seed=1, trials=1000).p_win
    p2 = matchup(roster, other, mc=True, seed=2, trials=1000).p_win
    assert p1 is not None and p2 is not None
    assert 0.0 <= p1 <= 1.0 and 0.0 <= p2 <= 1.0


def test_missing_cells_warn_and_contribute_zero() -> None:
    row = _row("Ghost", pts_pg="20", reb_pg="", ast_pg="oops")
    proj = project_player(row)
    assert proj.values["reb"] == 0.0
    assert proj.values["ast"] == 0.0
    assert any("reb_pg" in w for w in proj.warnings)
    assert any("ast_pg" in w for w in proj.warnings)


def test_zero_attempts_pool_is_zero_with_warning() -> None:
    row = _row("NoShots", pts_pg="5", fg_pct=".55", fga_pg="", ft_pct=".9", fta_pg="")
    roster = project_roster([row], "Loners")
    assert roster.cat_values["fg_pct"] == 0.0
    assert roster.cat_values["ft_pct"] == 0.0
    assert any("no FG attempts" in w for w in roster.warnings)
    assert any("no FT attempts" in w for w in roster.warnings)
