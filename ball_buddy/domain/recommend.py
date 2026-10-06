"""Need-aware pool recommender (P2: B + C1) with the M2.3 top-N fallback.

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
- **P2 need-aware** (``recommend_need_aware``): scores each candidate
  (a) pool value, (b) league-relative CATEGORY need of MY team — the 9
  H2H categories, projected via the same engine
  (``engine.project_roster`` / ``project_player``) as matchup projections,
  so any systematic bias in the pool's stats cancels — and (c) C1
  positional scarcity: the remaining (undrafted, unkept) pool count for
  the candidate's primary position vs the median across positions.
  Facts, not prediction. Every suggestion carries a human-readable
  ``reason`` string for the board panel.

Need is CATEGORY-level, not position-level: this is a 9-category H2H
game, and the question is per category — is my category strength
competitive, is my weakness salvageable? For each cat:
``gap = median_across_teams − mine`` in the better direction (``to`` is
lower-is-better, per ``engine.DIRECTIONS``), normalized by the league
``spread = max − min`` (0 → treated as 1). A candidate's fill for a cat
is its own season value normalized the same way (for ``to``: quality is
low turnovers, so fill = ``1 − player/spread``). Per-cat filled amount is
``max(0, min(gap_norm, fill_norm))``; the candidate's need is the sum
over the 9 cats (in [0, 9]).

Score per candidate = value + ``NEED_WEIGHT`` * need +
``SCARCITY_WEIGHT`` * scarcity (weights are module constants, tunable
draft-day). Fallback applies when ``teams`` is empty, ``my_team`` is
blank, or the set my-team name is not a known team — the recommender
degrades to the M2.3 ranking instead of crashing. Exclusions are
identical in both modes (drafted + active keepers; opted-out keepers
stay draftable). All secured players count in a team's projection (draft
picks + active keepers — no starter/bench distinction). Pure and
stdlib-only (plus the domain engine).
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

# Draft-day tunables: weight of the category-need and C1-scarcity terms
# relative to the pool value term.
NEED_WEIGHT = 1.0
SCARCITY_WEIGHT = 1.0


@dataclass(frozen=True)
class Suggestion:
    """One suggested pool player; ``value`` is the raw display string.

    ``rank`` is ``None`` for rows with a blank/unparseable rank cell.
    ``reason`` explains the score (P2) — empty only in the M2.3
    fallback, which the UI treats as "plain pool ranking".
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
    # pct categories (0 vs ~0.48) — so the need-aware signal is diluted
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
) -> list[Suggestion]:
    """P2: need-aware scoring for MY current pick, with reason strings.

    ``rows`` is the whole pool; ``excluded`` the drafted + active-keeper
    names (caller-computed). ``teams`` maps every team name to the pool
    rows of its SECURED players (draft picks + active keepers — all count;
    no starter/bench). ``my_team`` is ``settings["my_team"]``.

    Score per candidate = pool value + NEED_WEIGHT * need +
    SCARCITY_WEIGHT * scarcity. need = sum over the 9 categories of
    max(0, min(g_c, f_c)) — the league-normalized category gap I'm behind
    in (gap_c: median team vs my team, better direction, / spread) that
    the candidate's own season value actually fills (f_c: candidate /
    spread; for ``to``: 1 − candidate / spread). scarcity = C1:
    max(0, median remaining pool count across positions − remaining
    count at the candidate's primary position). Sorts by score desc,
    then rank asc (unranked last), then row order.

    Efficient: each team's secured rows are projected once per call;
    each candidate row is projected once (cached by row index) and its
    9 cat values reused.

    Falls back to the M2.3 ranking (with reasons) when ``teams`` is
    empty, ``my_team`` is blank, or unknown — never crashes.
    """
    if not teams or not my_team or my_team not in teams:
        return _fallback(rows, excluded, top_n)

    projections = {
        team: project_roster(team_rows, team) for team, team_rows in teams.items()
    }
    gaps, spreads = category_gaps(projections[my_team], projections)

    # C1: remaining (undrafted, unkept) pool count per primary position.
    remaining: dict[str, int] = {}
    for row in rows:
        name = (row.get("name") or "").strip()
        if not name or name in excluded:
            continue
        pos = _primary_pos(row.get("pos", ""))
        remaining[pos] = remaining.get(pos, 0) + 1
    counts_median = median(remaining.values()) if remaining else 0.0

    player_cache: dict[int, PlayerProjection] = {}
    entries: list[tuple] = []
    for index, row in enumerate(rows):
        name = (row.get("name") or "").strip()
        if not name or name in excluded:
            continue
        pos = _primary_pos(row.get("pos", ""))
        raw_value = (row.get("value", "") or "").strip()
        value = _parse_value(raw_value) or 0.0
        rank = _parse_rank(row.get("rank", ""))

        player = player_cache.setdefault(index, project_player(row))
        filled = {
            cat: max(0.0, min(gaps[cat], cat_fill(cat, player.values[cat], spreads[cat])))
            for cat in CATS
        }
        need = sum(filled.values())
        scarcity = max(0.0, counts_median - remaining.get(pos, 0))
        score = value + NEED_WEIGHT * need + SCARCITY_WEIGHT * scarcity

        # blank value cell -> "no pool value"; a real 0.0 shows "value 0"
        bits = [f"value {_fmt(value)}" if raw_value else "no pool value"]
        filling = [cat for cat in CATS if filled[cat] > 0]
        if filling:
            top_cats = sorted(filling, key=lambda c: filled[c], reverse=True)[:2]
            bits.append("fills " + " & ".join(top_cats) + " gaps")
        if scarcity > 0:
            bits.append(
                f"only {remaining.get(pos, 0)} {pos} left (median "
                f"{_fmt(counts_median)} per position)"
            )
        entries.append(
            (
                -score,
                1 if rank is None else 0,
                rank or 0,
                index,
                Suggestion(
                    name=name,
                    pos=(row.get("pos", "") or "").strip(),
                    value=(row.get("value", "") or "").strip(),
                    rank=rank,
                    reason=" · ".join(bits),
                ),
            )
        )

    entries.sort(key=lambda entry: entry[:4])
    return [entry[4] for entry in entries[:top_n]]


__all__ = [
    "Suggestion",
    "NEED_WEIGHT",
    "SCARCITY_WEIGHT",
    "recommend",
    "recommend_need_aware",
    "category_gaps",
    "cat_fill",
]
