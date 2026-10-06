"""Per-category BUILD/COAST/PUNT tags: my team vs the league (P3 relative panel).

An independent decision concept from the need-aware recommender: the
recommender answers "which pool player fills MY gaps now"; the tags answer
"which of my categories should I invest in, ignore, or abandon at all?".
The gap math is shared — ``recommend.category_gaps`` (median-vs-mine,
better direction, ÷ league spread; ``to`` lower-is-better, per
``engine.DIRECTIONS``) and ``recommend.cat_fill`` for candidate fills —
but the tag thresholds live here.

Per category (n = number of teams):
- rank: 1-based position across teams sorted best-first by
  ``engine.DIRECTIONS`` (ties: team name ascending — deterministic).
- gap: signed, positive = I'm behind (better direction), the same
  median-vs-mine math as ``recommend.category_gaps`` but kept signed.
- gap_norm = max(0, gap) / spread (spread 0 → 1).
- best_fill_norm: max ``recommend.cat_fill`` over the non-excluded pool
  (0.0 when the pool offers nothing).

Tag rules (draft-day tunables as keyword defaults):
- spread collapsed to its 0 → 1 guard (all teams equal — pre-draft) →
  COAST: no signal. Tags are only meaningful once picks exist; this guard
  absorbs the zero-inflation caveat of ``recommend.category_gaps``.
- rank <= top_n (default 3) → BUILD: strong enough to compete/extend.
- rank >= n − bottom_n + 1 (default 3) AND best_fill_norm <
  punt_close × gap_norm (default 0.25) → PUNT: bottom and the remaining
  pool can't close ~25% of the gap → unsalvageable.
- else → COAST.

Pure and stdlib-only (plus the domain engine + recommend gap helpers).
``None`` when ``teams`` is empty or ``my_team`` is blank/unknown — the
same fallback semantics as ``recommend.recommend_need_aware`` (the panel
hides itself instead of rendering).
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median

from ball_buddy.domain.engine import (
    CATS,
    DIRECTIONS,
    project_player,
    project_roster,
)
from ball_buddy.domain.recommend import cat_fill, category_gaps

BUILD = "BUILD"
COAST = "COAST"
PUNT = "PUNT"


@dataclass(frozen=True)
class CatTag:
    """One category's relative standing of MY team vs the league."""

    cat: str
    mine: float
    median: float
    gap: float  # signed; positive = behind, in the better direction
    gap_norm: float
    rank: int
    best_fill_norm: float
    tag: str  # BUILD / COAST / PUNT


def category_tags(
    teams: dict[str, list[dict[str, str]]],
    my_team: str,
    pool_rows: list[dict[str, str]],
    excluded: set[str],
    top_n: int = 3,
    bottom_n: int = 3,
    punt_close: float = 0.25,
) -> list[CatTag] | None:
    """BUILD/COAST/PUNT tag per category for ``my_team`` vs the league.

    ``teams`` maps every team name to the pool rows of its secured players
    (draft picks + active keepers); empty rosters project to zeros (engine
    behaviour) and still count. ``pool_rows`` is the whole pool;
    ``excluded`` the drafted/kept names to keep out of the fill search.

    Returns ``None`` when ``teams`` is empty or ``my_team`` is blank or
    unknown (panel hides), else one ``CatTag`` per ``engine.CATS`` entry.
    """
    if not teams or not my_team or my_team not in teams:
        return None

    projections = {
        team: project_roster(team_rows, team) for team, team_rows in teams.items()
    }
    my_proj = projections[my_team]
    _gaps, spreads = category_gaps(my_proj, projections)

    n = len(projections)
    player_cache: dict[int, object] = {}
    tags: list[CatTag] = []
    for cat in CATS:
        values = [proj.cat_values[cat] for proj in projections.values()]
        spread = spreads[cat]
        # rank: best-first by DIRECTIONS (to: lower is better), ties
        # broken by team name ascending for deterministic tags.
        def better(team: str) -> float:
            value = projections[team].cat_values[cat]
            return -value if DIRECTIONS[cat] == "lower" else value

        ordered = sorted(projections, key=lambda team: (-better(team), team))
        rank = ordered.index(my_team) + 1
        mine = my_proj.cat_values[cat]
        league_median = median(values)
        # signed gap, better direction (positive = behind)
        gap = (
            mine - league_median
            if DIRECTIONS[cat] == "lower"
            else league_median - mine
        )
        gap_norm = max(0.0, gap) / spread
        # best pool fill for this cat, non-excluded rows only
        best_fill = 0.0
        for index, row in enumerate(pool_rows):
            name = (row.get("name") or "").strip()
            if not name or name in excluded:
                continue
            player = player_cache.setdefault(index, project_player(row))
            best_fill = max(best_fill, cat_fill(cat, player.values[cat], spread))

        if max(values) == min(values):
            # raw league spread is 0 (all teams equal, e.g. pre-draft):
            # category_gaps collapsed it to its 0 -> 1 guard, so there is
            # no signal — tags are only meaningful once picks exist
            tag = COAST
        elif rank <= top_n:
            tag = BUILD
        elif rank >= n - bottom_n + 1 and best_fill < punt_close * gap_norm:
            tag = PUNT
        else:
            tag = COAST
        tags.append(
            CatTag(
                cat=cat,
                mine=mine,
                median=league_median,
                gap=gap,
                gap_norm=gap_norm,
                rank=rank,
                best_fill_norm=best_fill,
                tag=tag,
            )
        )
    return tags


__all__ = ["CatTag", "category_tags", "BUILD", "COAST", "PUNT"]
