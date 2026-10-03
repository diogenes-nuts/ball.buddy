"""Keeper entries (M2.1): model, validation, keepers.json persistence, resolution.

A keeper entry stores the player name **as entered**; resolution against the
local pool is computed on demand via the naming bridge (``domain/naming.py``)
and never persisted. Rules mirror SPEC §1.1 and ``league.py::_validate_keepers``:

- max 2 keepers per team (opted-out keepers still count toward the cap);
- cost round 1..13 (13-round snake per SPEC §1.1);
- at most one active (non-opted-out) keeper per (team, cost round) — an
  opted-out keeper consumes no pick;
- a player may not be kept by two teams (dedupe on the resolved pool name
  when resolvable, else the normalized entered name).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ball_buddy.domain.naming import bridge, normalize
from ball_buddy.io.state import StateError, load_json, save_json

KEEPERS_VERSION = 1
MAX_COST_ROUND = 13  # SPEC §1.1: 13-round snake
MAX_KEEPERS_PER_TEAM = 2
KEEPERS_FILE = "keepers.json"


@dataclass(frozen=True)
class KeeperEntry:
    """One keeper line; ``player`` is the name exactly as the user entered it."""

    team: str
    player: str
    cost_round: int
    opted_out: bool = False


def resolve(
    entries: list[KeeperEntry],
    pool_names: list[str],
    aliases: dict[str, str] | None = None,
) -> dict[str, str | None]:
    """Map each entered player name to its resolved pool name (None = unresolved).

    Reuses :func:`ball_buddy.domain.naming.bridge` over the entered names;
    ambiguous names are not auto-picked and resolve to None.
    """
    report = bridge([entry.player for entry in entries], list(pool_names), aliases)
    return {
        name: report.matched.get(name)
        for name in {entry.player for entry in entries}
    }


def validate(
    entries: list[KeeperEntry],
    teams: list[str] | tuple[str, ...],
    resolved: dict[str, str | None] | None = None,
) -> list[str]:
    """Return human-readable errors (empty list = valid).

    ``resolved`` (from :func:`resolve`) lets the cross-team duplicate check
    treat alias/containment-equivalent names (e.g. "Jokic" vs "Nikola Jokic"
    both bridging to pool "Jokic") as the same player.
    """
    resolved = resolved or {}
    team_set = set(teams)
    errors: list[str] = []
    per_team: dict[str, int] = {}
    dedupe: dict[str, str] = {}  # player key -> first team that kept it
    team_rounds: dict[str, set[int]] = {}
    for entry in entries:
        if entry.team not in team_set:
            errors.append(f"unknown team {entry.team!r}")
            continue
        per_team[entry.team] = per_team.get(entry.team, 0) + 1
        if not 1 <= entry.cost_round <= MAX_COST_ROUND:
            errors.append(
                f"{entry.team!r}: cost_round {entry.cost_round} "
                f"must be in 1..{MAX_COST_ROUND}"
            )
        if not entry.opted_out:
            rounds = team_rounds.setdefault(entry.team, set())
            if entry.cost_round in rounds:
                errors.append(
                    f"{entry.team!r} keeps two players costing round "
                    f"{entry.cost_round} — only one pick per round"
                )
            rounds.add(entry.cost_round)
        key = resolved.get(entry.player) or normalize(entry.player)
        first_team = dedupe.get(key)
        if first_team is not None and first_team != entry.team:
            errors.append(
                f"player {entry.player!r} is kept by both {first_team!r} and {entry.team!r}"
            )
        else:
            dedupe.setdefault(key, entry.team)
    for team, count in per_team.items():
        if count > MAX_KEEPERS_PER_TEAM:
            errors.append(
                f"{team!r} has {count} keepers (max {MAX_KEEPERS_PER_TEAM})"
            )
    return errors


def load(path: str | Path) -> list[KeeperEntry]:
    """Read keepers.json; empty list if the file does not exist yet.

    Raises :class:`StateError` on a corrupt file or a version mismatch
    (same contract as the other io/state.py documents).
    """
    document = load_json(path, KEEPERS_VERSION)
    if document is None:
        return []
    result: list[KeeperEntry] = []
    for raw in document.get("keepers", []):
        if not isinstance(raw, dict):
            raise StateError(f"{path}: keeper entries must be objects")
        result.append(
            KeeperEntry(
                team=str(raw["team"]),
                player=str(raw["player"]),
                cost_round=int(raw["cost_round"]),
                opted_out=bool(raw.get("opted_out", False)),
            )
        )
    return result


def save(entries: list[KeeperEntry], path: str | Path) -> None:
    """Atomically persist entries to keepers.json (``io/state.py``)."""
    save_json(
        {
            "keepers": [
                {
                    "team": entry.team,
                    "player": entry.player,
                    "cost_round": entry.cost_round,
                    "opted_out": entry.opted_out,
                }
                for entry in entries
            ]
        },
        path,
        KEEPERS_VERSION,
    )


__all__ = [
    "KEEPERS_FILE",
    "KEEPERS_VERSION",
    "MAX_COST_ROUND",
    "MAX_KEEPERS_PER_TEAM",
    "KeeperEntry",
    "load",
    "resolve",
    "save",
    "validate",
]
