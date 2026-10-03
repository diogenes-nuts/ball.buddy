"""Waiver-pick scoring (M4.1, headless).

Ranks waiver candidates by Delta P(win) against a single opponent, reusing
the M3.1 projection engine (``ball_buddy.domain.engine``) unchanged:

- Baseline: ``win_prob(project_roster(roster), project_roster(opp))``.
- Per candidate: evaluate ALL current roster players as drop candidates
  (bench-first not worth the complexity at ~14x14 roster sizes) and keep
  the drop with the highest Delta P(win); empty roster -> no drop.
- ``cat_delta`` is the deterministic (``mc=False``) matchup gap difference
  of the best counterfactual vs the baseline.
- ``rationale`` names the category with the largest direction-adjusted
  improvement; displayed deltas are direction-adjusted so positive always
  means "improves" (``to`` is lower-is-better per ``engine.DIRECTIONS``).

Pure domain: no Qt, no third-party deps. Candidate/roster/opponent names
resolve through ``PlayerPool.get`` (the naming bridge); ANY unresolved name
raises ``ValueError`` listing every miss (loud, never silent).

Runtime: each Delta P(win) is one seeded Monte-Carlo matchup. With the
default ``trials=200`` and ~14-man rosters that is ~14x14x200 trial draws
per candidate — a few seconds for a short candidate list. The engine
re-seeds its own RNG per call, so counterfactuals and the baseline share
the seed and are deterministic per call.
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
class WaiverCandidate:
    """One waiver candidate (``faab_cost=None`` means free/no cost)."""

    name: str
    faab_cost: int | None = None


@dataclass(frozen=True)
class WaiverRanking:
    """Ranked waiver option.

    ``cat_delta[cat]`` is the raw A-B season gap of the best counterfactual
    minus the baseline (positive = team improves); ``best_drop=None`` only
    when the roster is empty.
    """

    candidate: WaiverCandidate
    pool_name: str
    best_drop: str | None
    baseline_p: float
    delta_p: float
    cat_delta: dict[str, float]
    over_budget: bool
    rationale: str


def _resolve(
    pool: PlayerPool, names: list[str], kind: str
) -> list[dict[str, str]]:
    """Resolve display names to pool rows; raise listing ALL unresolved."""
    rows: list[dict[str, str]] = []
    missing: list[str] = []
    for name in names:
        row = pool.get(name)
        if row is None:
            missing.append(name)
        else:
            rows.append(row)
    if missing:
        raise ValueError(
            f"unresolved {kind} name(s) not in pool: "
            + ", ".join(repr(m) for m in missing)
        )
    return rows


def rank_candidates(
    candidates: list[WaiverCandidate],
    roster_names: list[str],
    opponent_names: list[str],
    pool: PlayerPool,
    faab_budget: int | None = None,
    trials: int = 200,
    seed: int | None = None,
    tie_break: str = "yahoo_default",
) -> list[WaiverRanking]:
    """Rank waiver candidates by Delta P(win) over a single opponent.

    See the module docstring for the algorithm. ``roster_names`` /
    ``opponent_names`` are pool (display) names, already bridged upstream.
    Any unresolved name (candidate, roster, or opponent) or a negative
    ``faab_cost`` raises ``ValueError``.
    """
    for cand in candidates:
        if cand.faab_cost is not None and cand.faab_cost < 0:
            raise ValueError(f"faab_cost must be None or >= 0, got {cand.faab_cost}")

    cand_rows = _resolve(pool, [c.name for c in candidates], "candidate")
    roster_rows = _resolve(pool, roster_names, "roster")
    opp_rows = _resolve(pool, opponent_names, "opponent")

    base = project_roster(roster_rows, "Team")
    opp = project_roster(opp_rows, "Opp")
    baseline_p = win_prob(
        base, opp, seed=seed, trials=trials, tie_break=tie_break
    )
    base_gaps = matchup(base, opp, mc=False).gaps

    rankings: list[WaiverRanking] = []
    for cand, cand_row in zip(candidates, cand_rows):
        if roster_rows:
            best_i, best_proj, best_delta = 0, None, float("-inf")
            for i in range(len(roster_rows)):
                rows = roster_rows[:i] + roster_rows[i + 1:] + [cand_row]
                proj = project_roster(rows, "Team")
                delta = (
                    win_prob(proj, opp, seed=seed, trials=trials, tie_break=tie_break)
                    - baseline_p
                )
                if delta > best_delta:
                    best_i, best_proj, best_delta = i, proj, delta
            best_drop = roster_rows[best_i]["name"]
            delta_p = best_delta
        else:
            best_proj = project_roster([cand_row], "Team")
            best_drop = None
            delta_p = (
                win_prob(best_proj, opp, seed=seed, trials=trials, tie_break=tie_break)
                - baseline_p
            )

        cat_delta = {
            cat: matchup(best_proj, opp, mc=False).gaps[cat] - base_gaps[cat]
            for cat in CATS
        }
        scored = {
            cat: cat_delta[cat] * (-1.0 if cat == "to" else 1.0) for cat in CATS
        }
        best_cat = max(CATS, key=lambda c: scored[c])
        # Display the direction-adjusted delta so positive always reads as
        # "improves" (TO is lower-is-better); ``was`` stays the raw gap.
        shown = cat_delta[best_cat] * (-1.0 if best_cat == "to" else 1.0)
        rationale = f"{best_cat.upper()} {shown:+.0f} (was {base_gaps[best_cat]:+.0f})"
        over_budget = (
            faab_budget is not None
            and cand.faab_cost is not None
            and cand.faab_cost > faab_budget
        )
        rankings.append(
            WaiverRanking(
                candidate=cand,
                pool_name=cand_row["name"],
                best_drop=best_drop,
                baseline_p=baseline_p,
                delta_p=delta_p,
                cat_delta=cat_delta,
                over_budget=over_budget,
                rationale=rationale,
            )
        )

    rankings.sort(
        key=lambda r: (
            -r.delta_p,
            r.candidate.faab_cost if r.candidate.faab_cost is not None else 0,
            r.candidate.name,
        )
    )
    return rankings


__all__ = ["WaiverCandidate", "WaiverRanking", "rank_candidates"]
