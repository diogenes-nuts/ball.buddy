"""Draft picks (M2.2): entered picks model, snake/forfeit/order computation.

The board persists only **entered** picks (``draft_picks.json``). Forfeited
picks are derived from the keeper entries on every build — the keepers stay
the single source of truth for forfeits. The snake itself is produced by
``league.snake_order`` over a minimal config (no slots/categories), exactly
the way ``ui/views/league.py`` builds one for display.

13 rounds per SPEC §1.1 (``keepers.MAX_COST_ROUND``). Note:
``ui/views/league.py::DRAFT_ROUNDS`` is 14 (roster-size comment) — a
pre-existing discrepancy flagged for a later slice, not fixed here.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ball_buddy.domain import keepers as keepers_mod
from ball_buddy.domain import league
from ball_buddy.domain.keepers import KeeperEntry
from ball_buddy.io.state import StateError, load_json, save_json

PICKS_VERSION = 1
PICKS_FILE = "draft_picks.json"
DRAFT_ROUNDS = keepers_mod.MAX_COST_ROUND  # SPEC §1.1: 13-round snake


@dataclass(frozen=True)
class DraftPick:
    """One entered pick; ``slot`` is the 1-based position within the round."""

    round: int
    slot: int
    team: str
    player: str


def load(path: str | Path) -> list[DraftPick]:
    """Read draft_picks.json; empty list if the file does not exist yet.

    Raises :class:`StateError` on a corrupt file or a version mismatch
    (same contract as the other io/state.py documents).
    """
    document = load_json(path, PICKS_VERSION)
    if document is None:
        return []
    result: list[DraftPick] = []
    for raw in document.get("picks", []):
        if not isinstance(raw, dict):
            raise StateError(f"{path}: pick entries must be objects")
        result.append(
            DraftPick(
                round=int(raw["round"]),
                slot=int(raw["slot"]),
                team=str(raw["team"]),
                player=str(raw["player"]),
            )
        )
    return result


def save(picks: list[DraftPick], path: str | Path) -> None:
    """Atomically persist picks to draft_picks.json (``io/state.py``)."""
    save_json(
        {
            "picks": [
                {
                    "round": pick.round,
                    "slot": pick.slot,
                    "team": pick.team,
                    "player": pick.player,
                }
                for pick in picks
            ]
        },
        path,
        PICKS_VERSION,
    )


def keeper_forfeits(entries: list[KeeperEntry]) -> set[tuple[str, int]]:
    """Set of (team, cost round) pairs consumed by active keeper costs.

    Opted-out keepers keep the player but consume no pick, so they are
    excluded (mirrors ``league.forfeited_picks`` over active keepers only).
    """
    return {
        (entry.team, entry.cost_round) for entry in entries if not entry.opted_out
    }


def build_snake(
    start_order: list[str],
    entries: list[KeeperEntry],
    rounds: int = DRAFT_ROUNDS,
) -> list[league.Pick]:
    """Full snake order with keeper-forfeited picks flagged.

    Builds the same minimal ``LeagueConfig`` the League view uses for
    display (no slots/categories), mapping active keeper entries onto
    ``league.Keeper`` without re-validation (entries were already validated
    by M2.1's keeper entry).
    """
    teams = tuple(start_order)
    config = league.LeagueConfig(
        teams=teams,
        start_order=teams,
        rounds=rounds,
        games_per_week=3.5,
        slots=(),
        categories=(),
        weights={},
        keepers=tuple(
            league.Keeper(entry.team, entry.player, entry.cost_round)
            for entry in entries
            if not entry.opted_out
        ),
    )
    return league.snake_order(config)


def start_order_for(snapshot: dict | None, settings: dict) -> list[str]:
    """Resolve the start order (team names) from snapshot + settings.

    Priority (mirrors ``ui/views/league.py``):
      1. the live/manual order saved in the snapshot (team ids -> names);
      2. ``settings["manual_draft_order"]`` merged against the snapshot team
         names (drop stale names, append new teams in snapshot order);
      3. the snapshot team order.
    """
    if not snapshot:
        return []
    teams = snapshot.get("teams", [])
    team_names = [team["name"] for team in teams]
    by_id = {team["team_id"]: team["name"] for team in teams}
    order = (snapshot.get("draft") or {}).get("order") or []
    if order:
        return [by_id.get(team_id, team_id) for team_id in order]
    saved = list(settings.get("manual_draft_order") or [])
    return [name for name in saved if name in team_names] + [
        name for name in team_names if name not in saved
    ]


def current_pick(
    snake: list[league.Pick], picks: list[DraftPick]
) -> league.Pick | None:
    """The earliest pick that is neither forfeited nor yet entered.

    ``None`` when every live pick has an entered DraftPick (draft complete).
    """
    taken = {(pick.round, pick.slot) for pick in picks}
    for pick in snake:
        if not pick.forfeited and (pick.round, pick.order) not in taken:
            return pick
    return None


__all__ = [
    "DRAFT_ROUNDS",
    "PICKS_FILE",
    "PICKS_VERSION",
    "DraftPick",
    "build_snake",
    "current_pick",
    "keeper_forfeits",
    "load",
    "save",
    "start_order_for",
]
