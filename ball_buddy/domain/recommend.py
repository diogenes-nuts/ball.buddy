"""Pool value recommender (M2.3): pure top-N pool ranking.

Ranks pool rows by ``rank`` (ascending = market rank), breaking rank ties
by ``value`` (descending), and drops anything in the excluded name set
(drafted + kept players, both entered and pool-bridged — computed by the
caller, see ``ui/views/board.py::_excluded_names``). Rows with a blank or
unparseable ``rank`` sort after all ranked rows (stable by row order)
and carry ``rank=None`` so the UI shows "—" instead of a display rank
that could collide with a real pool rank. A blank ``value`` displays
as "". No
z-scores, no invented math — position is display-only.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Suggestion:
    """One suggested pool player; ``value`` is the raw display string.

    ``rank`` is ``None`` for rows with a blank/unparseable rank cell.
    """

    name: str
    pos: str
    value: str
    rank: int | None


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


def recommend(
    rows: list[dict[str, str]],
    excluded: set[str],
    top_n: int = 5,
) -> list[Suggestion]:
    """Top-``top_n`` pool players, ranked, minus the excluded names.

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


__all__ = ["Suggestion", "recommend"]
