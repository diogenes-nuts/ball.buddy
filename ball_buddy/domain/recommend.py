"""Need-aware pool recommender (M2.3 fallback + P6 market/fit scoring).

Two modes:

- **M2.3 fallback** (``recommend``): pure top-N pool ranking. Ranks pool
  rows by ``rank`` (ascending = market rank), breaking rank ties by
  ``value`` (descending), and drops anything in the excluded name set
  (drafted + kept players, both entered and pool-bridged — computed by
  the caller, see ``ui/views/board.py::_excluded_names``). Rows with a
  blank or unparseable ``rank`` sort after all ranked rows (stable by row
  order) and carry ``rank=None`` so the UI shows "—" instead of a display
  rank that could collide with a real pool rank. A blank ``value``
  displays as "".
- **P6 need-aware** (``recommend_need_aware``): orders candidates with
  ``scorer.score_pool`` — the market / hole-covered fit / REACH-VALUE tag
  composite on the pool's own ``rank`` and signed ``z_*`` columns (see
  ``ball_buddy.domain.scorer``) — for MY current pick, then appends the
  P2 reason bits per candidate: (a) the league-relative CATEGORY gaps of
  MY team that the candidate actually fills (the 9 H2H categories,
  projected via the same engine ``engine.project_roster`` /
  ``engine.project_player`` as matchup projections, so any systematic
  bias in the pool's stats cancels) and (b) C1 positional scarcity: the
  remaining (undrafted, unkept) pool count for the candidate's primary
  position vs the median across positions. Facts, not prediction. Every
  suggestion carries a human-readable ``reason`` string for the board
  panel.

The fill bits are CATEGORY-level, not position-level: this is a
9-category H2H game, and the question is per category — is my category
strength competitive, is my weakness salvageable? For each cat:
``gap = median_across_teams − mine`` in the better direction (``to`` is
lower-is-better, per ``engine.DIRECTIONS``), normalized by the league
``spread = max − min`` (0 → treated as 1). A candidate's fill for a cat
is its own season value normalized the same way (for ``to``: quality is
low turnovers, so fill = ``1 − player/spread``). Per-cat filled amount is
``max(0, min(gap_norm, fill_norm))``; the reason names the top-2
categories by filled amount. Fill and scarcity bits are reasons only —
the ordering comes from the P6 composite score. Fallback applies when
``teams`` is empty, ``my_team`` is blank, or the set my-team name is not
a known team — the recommender degrades to the M2.3 ranking instead of
crashing. Exclusions are identical in both modes (drafted + active
keepers; opted-out keepers stay draftable). All secured players count in
a team's projection (draft picks + active keepers — no starter/bench
distinction). Pure and stdlib-only (plus the domain engine + scorer).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from statistics import median

from ball_buddy.domain.engine import (
    CATS,
    DIRECTIONS,
    PlayerProjection,
    project_player,
    project_roster,
)


@dataclass(frozen=True)
class Suggestion:
    """One suggested pool player; ``value`` is the raw display string.

    ``rank`` is ``None`` for rows with a blank/unparseable rank cell.
    ``reason`` explains the score (P6 composite + P2 bits) — empty only in
    the M2.3 fallback, which the UI treats as "plain pool ranking".
    """

    name: str
    pos: str
    value: str
    rank: int | None
    reason: str = ""


def _parse_rank(text: str) -> int | None:
    try:
        rank = int(str(text).strip())
        return rank if rank > 0 else None
    except ValueError:
        return None


def _parse_value(text: str) -> float | None:
    try:
        return float(str(text).strip())
    except ValueError:
        return None


def _fmt(number: float) -> str:
    """Compact number: 12.0 -> "12", 12.5 -> "12.5"."""
    text = f"{number:g}"
    return text


def _primary_pos(pos: str) -> str:
    """Primary (first-listed) position; "PG/SG" -> "PG"."""
    return (pos or "").split("/")[0].strip() or "?"


def recommend(
    rows: list[dict[str, str]],
    excluded: set[str],
    top_n: int = 5,
) -> list[Suggestion]:
    """Top-``top_n`` pool players, ranked, minus the excluded names (M2.3).

    Pure and stdlib-only; tolerant of blank/unparseable ``rank``/``value``
    cells (blank rank sorts last, blank value displays as "").
    """
    items: list[tuple[int, str, dict[str, str], int | None, float | None]] = []
    for index, row in enumerate(rows):
        name = (row.get("name") or "").strip()
        if not name or name in excluded:
            continue
        rank = _parse_rank(row.get("rank", ""))
        value = _parse_value(row.get("value", ""))
        items.append((index, name, row, rank, value))

    def sort_key(item: tuple[int, str, dict[str, str], int | None, float | None]):
        index, _name, _row, rank, value = item
        if rank is None:
            # unranked rows: after ranked ones, stable by row order
            return (1, 0, index)
        # rank asc, then value desc (blank value sorts last within its rank)
        return (0, rank, -(value if value is not None else float("-inf")), index)

    ordered = sorted(items, key=sort_key)
    return [
        Suggestion(
            name=name,
            pos=(row.get("pos", "") or "").strip(),
            value=(row.get("value", "") or "").strip(),
            rank=rank,
        )
        for _index, name, row, rank, _value in ordered[:top_n]
    ]


def _fallback(rows: list[dict[str, str]], excluded: set[str], top_n: int) -> list[Suggestion]:
    """M2.3 ranking with a reason string attached to each row."""
    return [
        replace(
            suggestion,
            reason=(
                f"pool rank {suggestion.rank}"
                if suggestion.rank is not None
                else "unranked (top pool order)"
            ),
        )
        for suggestion in recommend(rows, excluded, top_n)
    ]


def category_gaps(
    my_projection, all_projections: dict[str, object]
) -> tuple[dict[str, float], dict[str, float]]:
    """Per-cat normalized gap and spread across all teams.

    ``gap[c]``: how far MY team sits BELOW the league-median team in the
    better direction (``to`` is lower-is-better), divided by the league
    spread (max − min across teams; 0 → 1). Positive = I'm behind.
    ``spread[c]``: the raw league spread used to normalize candidate
    fills (0 → 1).
    """
    gaps: dict[str, float] = {}
    spreads: dict[str, float] = {}
    for cat in CATS:
        values = [proj.cat_values[cat] for proj in all_projections.values()]
        league_median = median(values)
        mine = my_projection.cat_values[cat]
        gap = (
            mine - league_median
            if DIRECTIONS[cat] == "lower"
            else league_median - mine
        )
        spread = max(values) - min(values)
        if spread <= 0:
            spread = 1.0
        gaps[cat] = max(0.0, gap) / spread
        spreads[cat] = spread
    # Note: teams with no secured players project to all zeros (engine
    # behaviour), which inflates every category's spread — most visibly the
    # pct categories (0 vs ~0.48) — so the fill-bit signal is diluted
    # pre-draft, when most rosters are still empty. Intentional (empty
    # teams still count toward the league median); it recovers as picks
    # are entered.
    return gaps, spreads


def cat_fill(cat: str, player_value: float, spread: float) -> float:
    """Candidate's normalized fill for one cat, in [0.0, 1.0].

    Higher-is-better cats: ``player/spread`` (a candidate who beats the
    league max clamps to 1.0; ``min(gap, fill)`` would cap it anyway).
    ``to``: quality is low turnovers, so ``1 − player/spread``.
    """
    if DIRECTIONS[cat] == "lower":
        fill = 1.0 - player_value / spread
    else:
        fill = player_value / spread
    return max(0.0, min(1.0, fill))


def recommend_need_aware(
    rows: list[dict[str, str]],
    excluded: set[str],
    teams: dict[str, list[dict[str, str]]] | None,
    my_team: str = "",
    top_n: int = 5,
    overall: int = 0,
    team_count: int = 0,
) -> list[Suggestion]:
    """P6: market/fit/tag scoring for MY current pick, with reason strings.

    ``rows`` is the whole pool; ``excluded`` the drafted + active-keeper
    names (caller-computed). ``teams`` maps every team name to the pool
    rows of its SECURED players (draft picks + active keepers — all count;
    no starter/bench). ``my_team`` is ``settings["my_team"]``.
    ``overall`` is the current pick's 1-based snake index and
    ``team_count`` the start-order length (both feed the scorer's tag
    boundaries and value-gap threshold; 0 = no draft context, where the
    tag adjustment is a flat offset — harmless to ordering — and the gap
    floor is unadjusted).

    Ordering is ``scorer.score_pool`` (market + hole/covered fit on
    signed pool z + REACH/VALUE tag composite). The P2 bits are appended
    to each reason, never scored: the top-2 category gaps the candidate
    fills (gap_c: median team vs my team, better direction, / spread;
    f_c: candidate / spread; for ``to``: 1 − candidate / spread) and the
    C1 scarcity bit (remaining pool count at the candidate's primary
    position below the position median).

    Efficient: each team's secured rows are projected once per call; each
    candidate is projected once (cached by name) for the fill bits.

    Falls back to the M2.3 ranking (with reasons) when ``teams`` is
    empty, ``my_team`` is blank, or unknown — never crashes.
    """
    if not teams or not my_team or my_team not in teams:
        return _fallback(rows, excluded, top_n)

    from ball_buddy.domain import scorer  # local: scorer imports Suggestion here

    candidate_rows = [
        row
        for row in rows
        if (row.get("name") or "").strip() and (row.get("name") or "").strip() not in excluded
    ]
    base = scorer.score_pool(
        candidate_rows, teams[my_team], overall, team_count, top_n=top_n
    )
    if not base:
        return []

    projections = {
        team: project_roster(team_rows, team) for team, team_rows in teams.items()
    }
    gaps, spreads = category_gaps(projections[my_team], projections)

    # C1: remaining (undrafted, unkept) pool count per primary position.
    remaining: dict[str, int] = {}
    for row in candidate_rows:
        pos = _primary_pos(row.get("pos", ""))
        remaining[pos] = remaining.get(pos, 0) + 1
    counts_median = median(remaining.values()) if remaining else 0.0

    name_to_row: dict[str, dict[str, str]] = {}
    for row in candidate_rows:
        name_to_row.setdefault((row.get("name") or "").strip(), row)

    player_cache: dict[str, PlayerProjection] = {}
    out: list[Suggestion] = []
    for suggestion in base:
        row = name_to_row.get(suggestion.name)
        if row is None:
            out.append(suggestion)
            continue
        player = player_cache.setdefault(suggestion.name, project_player(row))
        filled = {
            cat: max(0.0, min(gaps[cat], cat_fill(cat, player.values[cat], spreads[cat])))
            for cat in CATS
        }
        bits: list[str] = []
        filling = [cat for cat in CATS if filled[cat] > 0]
        if filling:
            top_cats = sorted(filling, key=lambda c: filled[c], reverse=True)[:2]
            bits.append("fills " + " & ".join(top_cats) + " gaps")
        pos = _primary_pos(row.get("pos", ""))
        scarcity = max(0.0, counts_median - remaining.get(pos, 0))
        if scarcity > 0:
            bits.append(
                f"only {remaining.get(pos, 0)} {pos} left (median "
                f"{_fmt(counts_median)} per position)"
            )
        if bits:
            suggestion = replace(
                suggestion, reason=suggestion.reason + " · " + " · ".join(bits)
            )
        out.append(suggestion)
    return out


__all__ = [
    "Suggestion",
    "recommend",
    "recommend_need_aware",
    "category_gaps",
    "cat_fill",
]
