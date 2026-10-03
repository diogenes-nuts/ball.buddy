"""Trade scoring (M6.1, headless).

Scores a proposed player-for-player swap by Delta P(win) against a single
opponent, reusing the M3.1 projection engine (``ball_buddy.domain.engine``)
unchanged — the same one-shot seeded Monte-Carlo approach as M4.1 waivers:

- Baseline: ``win_prob(project_roster(my), project_roster(their))``; the
  opponent's baseline is ``1 - my_p`` (one run serves both sides).
- After: same, on the swapped rosters, same ``seed``/``trials``.
- ``gaps`` before/after are the deterministic (``mc=False``) season-total
  A-B gaps from each side's own perspective (the opponent's dict is the
  sign-flip of mine).
- ``fairness_flag`` marks deals that cost us more than
  ``fairness_threshold`` (default 0.10) in P(win) — "likely a bad deal".

Caveat: ``1 - p_win`` treats pushes as losses for both sides (the MC
``p_win`` counts pushes for neither). With the shared seed the same trial
stream drives both matchups, so deltas are comparable; the small push bias
cancels between baseline and after for a given side.

Pure domain: no Qt, no third-party deps. All names are pool (display)
names, already bridged upstream, resolved through ``PlayerPool.get``; ANY
unresolved name, or a give not actually on the named roster, raises one
``ValueError`` listing every miss (loud, never silent).

Note: ``their_delta_p == -my_delta_p`` exactly (the ``1 - p``
construction), so a trade can never make both sides better or worse in
P(win) — the ``fairness_flag`` (my side's cost) is the only trade-quality
signal this score gives.
"""

from __future__ import annotations

from dataclasses import dataclass

from ball_buddy.domain.engine import (
    CATS,
    matchup,
    project_roster,
    win_prob,
)
from ball_buddy.domain.players import PlayerPool


@dataclass(frozen=True)
class Trade:
    """A proposed swap; both sides are pool (display) name tuples."""

    my_give: tuple[str, ...]
    their_give: tuple[str, ...]


@dataclass(frozen=True)
class TradeResult:
    """Scored trade from "my" perspective.

    ``*_gaps_*`` are season-total A-B gaps (per category) from each side's
    own perspective — ``my_*`` = me minus them, ``their_*`` = them minus me
    (the sign-flip of mine). ``fairness_flag`` = the trade costs us more
    than the threshold in P(win).
    """

    my_names_after: tuple[str, ...]
    their_names_after: tuple[str, ...]
    my_baseline_p: float
    my_delta_p: float
    their_baseline_p: float
    their_delta_p: float
    my_gaps_before: dict[str, float]
    my_gaps_after: dict[str, float]
    their_gaps_before: dict[str, float]
    their_gaps_after: dict[str, float]
    fairness_flag: bool
    summary: str


def _validate(
    trade: Trade,
    my_roster_names: list[str],
    their_roster_names: list[str],
    pool: PlayerPool,
) -> list[dict[str, str]]:
    """Validate rosters and gives against the pool.

    Raises one ``ValueError`` listing every miss: names the pool cannot
    resolve (give or roster), and gives not on the named roster. Empty
    gives (buyout) are fine; both sides empty is not.
    """
    if not trade.my_give and not trade.their_give:
        raise ValueError("trade needs at least one side non-empty")

    problems: list[str] = []
    for label, roster in (("my", my_roster_names), ("their", their_roster_names)):
        for name in roster:
            if pool.get(name) is None:
                problems.append(f"{label} roster: {name!r} not in pool")
    for name in trade.my_give:
        if name not in my_roster_names:
            problems.append(f"my_give: {name!r} is not on my roster")
        elif pool.get(name) is None:
            problems.append(f"my_give: {name!r} not in pool")
    for name in trade.their_give:
        if name not in their_roster_names:
            problems.append(
                f"their_give: {name!r} is not on their roster"
            )
        elif pool.get(name) is None:
            problems.append(f"their_give: {name!r} not in pool")
    if problems:
        raise ValueError("; ".join(problems))


def analyze_trade(
    trade: Trade,
    my_roster_names: list[str],
    their_roster_names: list[str],
    pool: PlayerPool,
    *,
    trials: int = 200,
    seed: int | None = None,
    fairness_threshold: float = 0.10,
) -> TradeResult:
    """Score a proposed swap: Delta P(win) per side + deterministic gaps.

    See the module docstring for the algorithm. Rosters are pool (display)
    names, already bridged upstream; any unresolved name raises
    ``ValueError``. The same seeded MC run is used for both the baseline
    and the after matchup, so deltas are comparable per side.
    """
    _validate(trade, my_roster_names, their_roster_names, pool)

    my_give_rows = [pool.get(name) for name in trade.my_give]
    my_give_set = set(trade.my_give)
    their_give_set = set(trade.their_give)

    # All names pool-validated above; pool.get can no longer return None.
    my_rows = [pool.get(n) for n in my_roster_names]
    their_rows = [pool.get(n) for n in their_roster_names]

    my_after_names = (
        tuple(n for n in my_roster_names if n not in my_give_set)
        + trade.their_give
    )
    their_after_names = (
        tuple(n for n in their_roster_names if n not in their_give_set)
        + trade.my_give
    )
    my_after_rows = [
        pool.get(n) for n in my_roster_names if n not in my_give_set
    ] + [pool.get(n) for n in trade.their_give]
    their_after_rows = [
        pool.get(n) for n in their_roster_names if n not in their_give_set
    ] + my_give_rows

    base_my = project_roster(my_rows, "Me")
    base_their = project_roster(their_rows, "Them")
    after_my = project_roster(my_after_rows, "Me")
    after_their = project_roster(their_after_rows, "Them")

    my_baseline_p = win_prob(base_my, base_their, seed=seed, trials=trials)
    after_p = win_prob(after_my, after_their, seed=seed, trials=trials)
    their_baseline_p = 1.0 - my_baseline_p
    their_after_p = 1.0 - after_p

    my_delta_p = after_p - my_baseline_p
    their_delta_p = their_after_p - their_baseline_p

    my_gaps_before = matchup(base_my, base_their, mc=False).gaps
    my_gaps_after = matchup(after_my, after_their, mc=False).gaps
    their_gaps_before = {c: -my_gaps_before[c] for c in CATS}
    their_gaps_after = {c: -my_gaps_after[c] for c in CATS}

    fairness_flag = my_delta_p < -fairness_threshold

    # their_delta_p == -my_delta_p exactly (1-p construction), so the
    # summary is just the two mirror deltas + the fairness verdict.
    fairness = (
        " likely a bad deal" if fairness_flag else " looks fair"
    )
    summary = f"you {my_delta_p:+.2f}, them {their_delta_p:+.2f}{fairness}"

    return TradeResult(
        my_names_after=my_after_names,
        their_names_after=their_after_names,
        my_baseline_p=my_baseline_p,
        my_delta_p=my_delta_p,
        their_baseline_p=their_baseline_p,
        their_delta_p=their_delta_p,
        my_gaps_before=my_gaps_before,
        my_gaps_after=my_gaps_after,
        their_gaps_before=their_gaps_before,
        their_gaps_after=their_gaps_after,
        fairness_flag=fairness_flag,
        summary=summary,
    )


__all__ = ["Trade", "TradeResult", "analyze_trade"]
