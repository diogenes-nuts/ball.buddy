"""Tests for the M5.1 lineup optimizer (ball_buddy/domain/lineup.py)."""

from __future__ import annotations

import random

import pytest

from ball_buddy.domain import engine
from ball_buddy.domain.lineup import SLOTS, LineupResult, optimize
from ball_buddy.io.pool.importer import FIELDNAMES

# Fixture spread (14 rows): 2 PG (Aiden, Bram), 2 PG/SG (Cyrus, Zeta),
# 1 SG (Dane), 2 SF (Eli, Gus), 2 PF (Finn, Moe), 1 SF/PF (Ivan),
# 2 C (Jon, Kip), 1 PG/SG/SF (Leo), 1 C/PF (Yankee).
# UTL-eligible (>= 2 pos tokens): Cyrus, Zeta, Ivan, Leo, Yankee (5).
#
# Base stats per player (season = pg x 82 gp):
#   pts 10 (820)  reb 4 (328)  ast 2 (164)  stl 1 (82)  blk 0.5 (41)
#   to 1.5 (123)  three 1.5 (123)  fg .48 @ 12 fga  ft .40 @ 5 fta (410)

BASE = {
    "gp": "82", "mpg": "20", "team": "SMK",
    "pts_pg": "10", "reb_pg": "4", "ast_pg": "2", "stl_pg": "1", "blk_pg": "0.5",
    "to_pg": "1.5", "three_pg": "1.5",
    "fg_pct": "0.48", "fga_pg": "12", "ft_pct": "0.40", "fta_pg": "5",
}


def _row(name: str, pos: str, **overrides: str) -> dict[str, str]:
    row = {field: "" for field in FIELDNAMES}
    row["name"] = name
    row["pos"] = pos
    row.update(BASE)
    row.update(overrides)
    return row


def fixture_rows() -> list[dict[str, str]]:
    return [
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
        _row("Zeta", "PG/SG", pts_pg="6", ft_pct="0.80", fta_pg="6"),
        _row("Yankee", "C/PF", pts_pg="9", ft_pct="0.75", fta_pg="7"),
    ]


def opponent_projection() -> engine.RosterProjection:
    """Opponent ~1.0/pg under us in every count cat except TO (2.0 vs our
    1.5 -> we win the lower-is-better cat), fg% .50 > our .48 (a
    count-style +1.0 offset is not a rate), and ft% .45 > our base pool
    .40 (the swing category)."""
    return engine.RosterProjection(
        name="Rivals",
        cat_values={
            "pts": 9.0 * 10 * 82, "reb": 3.0 * 10 * 82, "ast": 1.0 * 10 * 82,
            "stl": 0.5 * 10 * 82, "blk": 0.25 * 10 * 82, "to": 2.0 * 10 * 82,
            "three": 0.5 * 10 * 82, "fg_pct": 0.50, "ft_pct": 0.45,
        },
    )


def test_greedy_wrong_scenario() -> None:
    """Zeta (6 pts) and Yankee (9 pts) must start despite low scoring.

    Hand arithmetic (10 starters, season = pg x 82):
    - Naive top-pts greedy seats any 10 of the 12 ten-pointers, sitting
      Zeta and Yankee. Its FT pool is the plain base 0.40 (every starter at
      .40) -> loses FT% (0.40 < 0.45) and FG% (0.48 < 0.50): wins 7, loses 2.
    - FT% pool with BOTH Zeta and Yankee starting (8 base @410 attempts/.40,
      Zeta 6x82=492 @.80, Yankee 7x82=574 @.75):
          (8*410*.40 + 492*.80 + 574*.75) / (8*410 + 492 + 574)
        = (1312 + 393.6 + 430.5) / 3348 = 2136.1 / 3348 ~= 0.4915 > 0.45
      Either one alone stays UNDER 0.45 (Zeta only:
      (9*410*.40 + 492*.80)/(9*410 + 492) ~= 0.4471; Yankee only
      ~= 0.4471 too), so BOTH must start to win FT%.
    - Optimum = 8 base ten-pointers + Zeta + Yankee:
        wins  pts  8*820 + 492 + 738 = 7790   vs 9*820 = 7380  -> +410
               (reb/ast/stl/blk/three likewise +1.0 or +0.5 pg per player)
        wins  to   8*123 + 123 + 41 = 1146    vs 1640       -> we win
               (lower is better)
        win   ft   0.4915 vs 0.45  -> +0.0415
        loss  fg   0.48 vs 0.50 (only non-swing loss)
      -> cat_wins (8, 1). The plan's "target ~7-1" assumed two lost cats;
      with this opponent the computed optimum is 8-1, which this test
      asserts. Margin > 0 (sum of direction-adjusted gaps over the 8 won
      cats, all positive in their better direction).
    """
    res = optimize(fixture_rows(), opponent_projection())
    starter_names = [name for _, name in res.starters]
    assert "Zeta" in starter_names
    assert "Yankee" in starter_names
    assert res.cat_wins == (8, 1)
    assert res.cat_wins[0] > res.cat_wins[1]
    assert res.margin > 0
    # The swing is real: FT% gap positive, FG% the only loss.
    assert res.gaps["ft_pct"] > 0
    losses = [cat for cat, (a, _) in
              zip(engine.CATS, res.cat_outcomes) if a != "win"]
    assert losses == ["fg_pct"]


def _slot_tokens_ok(pos: str, slot: str) -> bool:
    tokens = set(t for t in pos.split("/") if t)
    if slot == "UTL":
        return len(tokens) >= 2
    return {
        "PG": "PG" in tokens, "SG": "SG" in tokens,
        "G": bool(tokens & {"PG", "SG"}),
        "SF": "SF" in tokens, "PF": "PF" in tokens,
        "F": bool(tokens & {"SF", "PF"}), "C": "C" in tokens,
    }[slot]


@pytest.mark.parametrize("variant", range(5))
def test_slot_constraint_properties(variant: int) -> None:
    """5 fixture variants: slots disjoint, each starter fits its slot,
    10 starters + 4 sitters = 14 disjoint names."""
    rows = fixture_rows()
    playing: frozenset[str] | None = None
    if variant == 1:  # explicit playing set, rows shuffled
        rng = random.Random(variant)
        rows = rows[:]
        rng.shuffle(rows)
        playing = frozenset(r["name"] for r in rows)
    elif variant == 2:  # TO perturbed on non-SF rows only (SF untouched so
        # the best set keeps its SF; TO sum stays under the opponent's 1640)
        rows = [
            dict(r, to_pg=str(1.0 + i * 0.1))
            if "SF" not in r["pos"] else r
            for i, r in enumerate(rows)
        ]
    elif variant == 3:  # tighter opponent (scales all cat values by 0.98)
        pass
    opponent = (
        engine.RosterProjection(
            name="Tight",
            cat_values={c: v * 0.98
                        for c, v in opponent_projection().cat_values.items()},
        )
        if variant == 3
        else opponent_projection()
    )
    res = optimize(rows, opponent, playing=playing)
    names = [name for _, name in res.starters]
    # exactly one player per slot key
    assert len(names) == len(set(names)) == 10
    by_pos = {r["name"]: r["pos"] for r in rows}
    for slot, name in res.starters:
        assert _slot_tokens_ok(by_pos[name], slot), (slot, name)
    # 10 starters + 4 sitters, disjoint, = all 14
    assert len(res.sits) == 4
    assert set(names).isdisjoint(res.sits)
    assert set(names) | set(res.sits) == set(by_pos)
    assert [slot for slot, _ in res.starters] == list(SLOTS)


def test_deterministic_repeated_calls() -> None:
    opponent = opponent_projection()
    first = optimize(fixture_rows(), opponent)
    assert isinstance(first, LineupResult)
    for _ in range(19):
        assert optimize(fixture_rows(), opponent) == first


def test_valueerror_no_playing_rows() -> None:
    with pytest.raises(ValueError):
        optimize(fixture_rows(), opponent_projection(),
                 playing=frozenset())


def test_valueerror_not_enough_utl() -> None:
    """10 rows with most multi-pos players removed (Cyrus, Zeta, Ivan,
    Leo) leaving only Yankee UTL-eligible -> ValueError naming UTL."""
    drop = {"Cyrus", "Zeta", "Ivan", "Leo"}
    rows = [r for r in fixture_rows() if r["name"] not in drop]
    assert len(rows) == 10
    with pytest.raises(ValueError, match="UTL"):
        optimize(rows, opponent_projection())


def test_mc_trials_seeded_does_not_change_choice() -> None:
    opponent = opponent_projection()
    plain = optimize(fixture_rows(), opponent)
    mc = optimize(fixture_rows(), opponent, mc_trials=1000, seed=42)
    assert mc.p_win is not None
    assert 0.0 <= mc.p_win <= 1.0
    assert mc.starters == plain.starters
    assert mc.sits == plain.sits
