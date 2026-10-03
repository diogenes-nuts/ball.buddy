"""Head-to-head projection engine (M3.1, headless).

Pool rows -> 9-category season projections -> deterministic matchup gaps and
seeded Monte-Carlo win probability, with a configurable 4-4 tie-break
(SPEC section 1.1 open item: ``tie_break="yahoo_default" | "h2h"``).

Design notes:
- Pure domain: no Qt, no third-party deps. Consumes only the 9 stat columns
  plus ``gp`` from the canonical importer row schema (``FIELDNAMES``).
  A later ``ProjectionSource`` seam can feed real box-score rows unchanged.
- Per player: ``season[cat] = rate x gp``. FG%/FT% are pooled at the roster
  level weighted by attempt volume (``fga_pg x gp`` / ``fta_pg x gp``),
  which kills naive pct summing (the 3889.3% bug).
- ``usage_factor`` (default 1.0) is a deliberate single-scalar simplification
  of SPEC's lineup-shape usage adjustment: pre-draft both teams share roster
  shape so it cancels in gaps. It is the usage-adjust seam; kept as a scalar
  on purpose (no redesign later).
- Variance: fixed relative-variance prior (``REL_SIGMA``), pre-draft with no
  history. Count cats: per-player ``N(season, REL_SIGMA x season)`` floored
  at 0, roster = sum. Pct cats: one draw per roster per trial, clamped to
  [0, 1]. Raw ``>`` compares in the MC: ties count for both teams per SPEC.
- The ``week`` parameter is accepted but unused pre-draft (season scale
  cancels in the per-cat compare); the signature is kept for M3.2.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

# The standard 9 categories in fixed display order (league.py keys).
CATS: tuple[str, ...] = (
    "pts", "reb", "ast", "stl", "blk", "to", "three", "fg_pct", "ft_pct"
)
COUNT_CATS: tuple[str, ...] = ("pts", "reb", "ast", "stl", "blk", "to", "three")
PCT_CATS: tuple[str, ...] = ("fg_pct", "ft_pct")

# Engine category key -> canonical players.csv per-game column.
COUNT_COLUMN: dict[str, str] = {
    "pts": "pts_pg", "reb": "reb_pg", "ast": "ast_pg", "stl": "stl_pg",
    "blk": "blk_pg", "to": "to_pg", "three": "three_pg",
}
PCT_COLUMN: dict[str, str] = {"fg_pct": "fg_pct", "ft_pct": "ft_pct"}
ATTEMPT_COLUMN: dict[str, str] = {"fg_pct": "fga_pg", "ft_pct": "fta_pg"}

# Better direction per category (Yahoo standard 9; ``to`` is lower-is-better,
# so a positive TO gap means A is *worse* on turnovers).
DIRECTIONS: dict[str, str] = {
    cat: ("lower" if cat == "to" else "higher") for cat in CATS
}

# Fixed relative-variance prior for pre-draft Monte-Carlo (no history yet).
REL_SIGMA: dict[str, float] = {
    "pts": 0.25, "reb": 0.30, "ast": 0.35, "stl": 0.50, "blk": 0.50,
    "to": 0.40, "three": 0.35, "fg_pct": 0.02, "ft_pct": 0.01,
}

TIE_BREAK_MODES: tuple[str, ...] = ("yahoo_default", "h2h")


def _num(row: dict[str, str], column: str, who: str, warns: list[str]) -> float:
    """Parse one numeric cell; missing/non-numeric -> 0.0 + loud warning."""
    raw = row.get(column, "")
    try:
        return float(raw)
    except (TypeError, ValueError):
        warns.append(f"{who}: {column}={raw!r} missing/non-numeric; projected 0")
        return 0.0


def _clamp01(x: float) -> float:
    return min(1.0, max(0.0, x))


@dataclass
class PlayerProjection:
    """Season projection for one player.

    ``values`` holds the season value for all 9 categories (count cats as
    totals, pct cats as the pooled pct); ``fg_attempts`` / ``ft_attempts``
    are the season attempt volumes used for roster-level pct pooling.
    """

    name: str
    gp: float
    values: dict[str, float]
    fg_attempts: float
    ft_attempts: float
    warnings: list[str] = field(default_factory=list)

    def attempts(self, cat: str) -> float:
        return self.fg_attempts if cat == "fg_pct" else self.ft_attempts


@dataclass
class RosterProjection:
    """Season projection for a whole roster (9 category values + warnings)."""

    name: str
    cat_values: dict[str, float]
    warnings: list[str] = field(default_factory=list)
    players: tuple[PlayerProjection, ...] = ()
    usage_factor: float = 1.0


@dataclass
class MatchupResult:
    """Result of comparing two roster projections.

    ``gaps`` are season-total gaps (A - B) per category. ``cat_outcomes``
    is a 9-tuple of (a, b) outcome strings ("win" / "loss" / "tie") at the
    deterministic season scale. ``cat_wins`` counts wins per side (a tie
    counts for both). ``winner`` is the team name or None (push). ``p_win``
    is the Monte-Carlo probability that A takes the matchup (None when
    ``mc=False``).
    """

    gaps: dict[str, float]
    cat_outcomes: tuple[tuple[str, str], ...]
    cat_wins: tuple[int, int]
    winner: str | None
    p_win: float | None
    warnings: list[str] = field(default_factory=list)


def project_player(row: dict[str, str]) -> PlayerProjection:
    """Project one canonical pool row to season values (``rate x gp``)."""
    name = row.get("name", "")
    warns: list[str] = []
    gp = _num(row, "gp", name, warns)
    values: dict[str, float] = {}
    for cat in COUNT_CATS:
        rate = _num(row, COUNT_COLUMN[cat], name, warns)
        values[cat] = rate * gp
    for cat in PCT_CATS:
        values[cat] = _num(row, PCT_COLUMN[cat], name, warns)
    fg_att = _num(row, "fga_pg", name, warns) * gp
    ft_att = _num(row, "fta_pg", name, warns) * gp
    return PlayerProjection(
        name=name, gp=gp, values=values, fg_attempts=fg_att,
        ft_attempts=ft_att, warnings=warns,
    )


def project_roster(
    rows: list[dict[str, str]], name: str, usage_factor: float = 1.0
) -> RosterProjection:
    """Project a roster: sum player seasons (x usage) for counts, and pool
    FG%/FT% weighted by attempt volume (kills the 3889.3% pct-sum bug)."""
    players = tuple(project_player(row) for row in rows)
    warns: list[str] = [w for p in players for w in p.warnings]
    cat_values: dict[str, float] = {}
    for cat in COUNT_CATS:
        cat_values[cat] = sum(p.values[cat] for p in players) * usage_factor
    for cat in PCT_CATS:
        numerator = sum(p.values[cat] * p.attempts(cat) for p in players)
        denominator = sum(p.attempts(cat) for p in players)
        if denominator <= 0:
            cat_values[cat] = 0.0
            kind = "FG" if cat == "fg_pct" else "FT"
            warns.append(f"{name}: no {kind} attempts; projected 0")
        else:
            cat_values[cat] = numerator / denominator
    return RosterProjection(
        name=name, cat_values=cat_values, warnings=warns,
        players=players, usage_factor=usage_factor,
    )


def _tie_break(
    a_name: str,
    b_name: str,
    tie_break: str,
    catwins: dict[str, int] | None,
    h2h: dict[str, tuple[int, int]] | None,
) -> str | None:
    """Resolve an equal cat-score. Missing data or a true tie -> push (None)."""
    if tie_break == "yahoo_default":
        if catwins and a_name in catwins and b_name in catwins:
            if catwins[a_name] > catwins[b_name]:
                return a_name
            if catwins[b_name] > catwins[a_name]:
                return b_name
        return None
    if tie_break == "h2h":
        if h2h and a_name in h2h and b_name in h2h:
            (_, a_losses), (_, b_losses) = h2h[a_name], h2h[b_name]
            if a_losses < b_losses:
                return a_name
            if b_losses < a_losses:
                return b_name
            a_wins, b_wins = h2h[a_name][0], h2h[b_name][0]
            if a_wins > b_wins:
                return a_name
            if b_wins > a_wins:
                return b_name
        return None
    raise ValueError(
        f"tie_break must be one of {TIE_BREAK_MODES}, got {tie_break!r}"
    )


def _compare(av: float, bv: float, direction: str) -> tuple[float, float]:
    """Return (av, bv) so that higher-is-better, for raw `>` compares."""
    if direction == "lower":
        return -av, -bv
    return av, bv


def _deterministic(
    a: RosterProjection, b: RosterProjection
) -> tuple[dict[str, float], tuple[tuple[str, str], ...], tuple[int, int]]:
    """Season-total gaps + per-cat outcomes + cat wins (ties count both)."""
    gaps: dict[str, float] = {c: a.cat_values[c] - b.cat_values[c] for c in CATS}
    outcomes: list[tuple[str, str]] = []
    awins = 0
    bwins = 0
    for cat in CATS:
        av, bv = _compare(a.cat_values[cat], b.cat_values[cat], DIRECTIONS[cat])
        if av > bv:
            outcomes.append(("win", "loss"))
            awins += 1
        elif av < bv:
            outcomes.append(("loss", "win"))
            bwins += 1
        else:
            outcomes.append(("tie", "tie"))
            awins += 1
            bwins += 1
    return gaps, tuple(outcomes), (awins, bwins)


def matchup(
    a: RosterProjection,
    b: RosterProjection,
    week: int = 1,
    tie_break: str = "yahoo_default",
    catwins: dict[str, int] | None = None,
    h2h: dict[str, tuple[int, int]] | None = None,
    mc: bool = False,
    seed: int | None = None,
    trials: int = 10_000,
) -> MatchupResult:
    """Compare two roster projections (deterministic gaps, or seeded MC).

    ``week`` is accepted but unused pre-draft (kept for M3.2). In MC mode
    each trial draws per-player count samples (floored at 0) and one pooled
    pct draw per roster; a trial with equal cat scores falls through to
    ``tie_break`` (push when no/equal data). ``p_win`` = fraction of trials
    A wins (pushes count for neither side).
    """
    del week  # accepted for signature stability; season scale cancels.
    warnings = [*a.warnings, *b.warnings]
    gaps, outcomes, (awins, bwins) = _deterministic(a, b)

    if not mc:
        winner: str | None = None
        if awins > bwins:
            winner = a.name
        elif bwins > awins:
            winner = b.name
        else:
            winner = _tie_break(a.name, b.name, tie_break, catwins, h2h)
        return MatchupResult(
            gaps=gaps, cat_outcomes=outcomes, cat_wins=(awins, bwins),
            winner=winner, p_win=None, warnings=warnings,
        )

    if trials < 1:
        raise ValueError("trials must be >= 1")
    rng = random.Random(seed)
    a_counts = {
        cat: [
            (p.values[cat] * a.usage_factor,
             REL_SIGMA[cat] * p.values[cat] * a.usage_factor)
            for p in a.players
        ]
        for cat in COUNT_CATS
    }
    b_counts = {
        cat: [
            (p.values[cat] * b.usage_factor,
             REL_SIGMA[cat] * p.values[cat] * b.usage_factor)
            for p in b.players
        ]
        for cat in COUNT_CATS
    }
    a_pct = {
        cat: (a.cat_values[cat], REL_SIGMA[cat] * a.cat_values[cat])
        for cat in PCT_CATS
    }
    b_pct = {
        cat: (b.cat_values[cat], REL_SIGMA[cat] * b.cat_values[cat])
        for cat in PCT_CATS
    }

    a_trial_wins = 0
    for _ in range(trials):
        trial_a = 0
        trial_b = 0
        for cat in CATS:
            if cat in COUNT_CATS:
                av = sum(max(0.0, rng.gauss(mu, sigma)) for mu, sigma in a_counts[cat])
                bv = sum(max(0.0, rng.gauss(mu, sigma)) for mu, sigma in b_counts[cat])
            else:
                av = _clamp01(rng.gauss(*a_pct[cat]))
                bv = _clamp01(rng.gauss(*b_pct[cat]))
            av, bv = _compare(av, bv, DIRECTIONS[cat])
            if av > bv:
                trial_a += 1
            elif av < bv:
                trial_b += 1
            else:
                trial_a += 1  # tie counts for both (SPEC)
                trial_b += 1
        if trial_a > trial_b:
            a_trial_wins += 1
        elif trial_a == trial_b:
            if _tie_break(a.name, b.name, tie_break, catwins, h2h) == a.name:
                a_trial_wins += 1
    p_win = a_trial_wins / trials
    return MatchupResult(
        gaps=gaps, cat_outcomes=outcomes, cat_wins=(awins, bwins),
        winner=None, p_win=p_win, warnings=warnings,
    )


def win_prob(
    a: RosterProjection,
    b: RosterProjection,
    seed: int | None = None,
    trials: int = 10_000,
    tie_break: str = "yahoo_default",
    catwins: dict[str, int] | None = None,
    h2h: dict[str, tuple[int, int]] | None = None,
    week: int = 1,
) -> float:
    """Monte-Carlo probability that ``a`` takes the matchup over ``b``."""
    result = matchup(
        a, b, week=week, tie_break=tie_break, catwins=catwins, h2h=h2h,
        mc=True, seed=seed, trials=trials,
    )
    return 0.0 if result.p_win is None else result.p_win


__all__ = [
    "CATS", "COUNT_CATS", "PCT_CATS", "DIRECTIONS", "REL_SIGMA",
    "PlayerProjection", "RosterProjection", "MatchupResult",
    "project_player", "project_roster", "matchup", "win_prob",
]
