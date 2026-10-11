"""Shared view display constants (single definitions for the view layer)."""

from __future__ import annotations

from ball_buddy.domain import engine

CAT_LABELS: dict[str, str] = {
    "fg_pct": "FG%", "ft_pct": "FT%", "three": "3P", "pts": "Pts",
    "reb": "Reb", "ast": "Ast", "stl": "Stl", "blk": "Blk", "to": "To",
}


def _fmt_gap(cat: str, value: float) -> str:
    if cat in engine.COUNT_CATS:
        return f"{value:+.0f}"
    return f"{value:+.8f}"


__all__ = ["CAT_LABELS", "_fmt_gap"]
