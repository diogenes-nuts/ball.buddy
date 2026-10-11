"""Shared pre-draft roster resolver (keepers + drafted picks -> pool).

One implementation of the name-resolution core used by the matchup,
lineups, trades, and waivers views: for a team, the keeper entries
(``keepers.json`` via ``domain/keepers.resolve`` + ``aliases.json``) union
the entered ``DraftPick`` players (``draft_picks.json``), each resolved
against ``players.csv`` (deduped, keeper-then-pick order kept). Names that
do not resolve into the pool are returned separately — surfaced as warnings
by the views, never a crash.
"""

from __future__ import annotations

from ball_buddy.domain import keepers as keepers_mod
from ball_buddy.domain import picks as picks_mod
from ball_buddy.domain.keepers import KeeperEntry
from ball_buddy.domain.players import PlayerPool
from ball_buddy.services.sync import SyncService


def _resolve_pool_names(
    service: SyncService, team_name: str
) -> tuple[list[str], list[str]]:
    """(resolved pool names, unresolvable names) in keeper-then-pick order,
    deduped. One ``keepers.resolve`` pass."""
    pool = PlayerPool.load(service.pool_path)
    aliases = service.load_aliases()
    keepers = keepers_mod.load(service.data_dir / keepers_mod.KEEPERS_FILE)
    picks = picks_mod.load(service.data_dir / picks_mod.PICKS_FILE)
    if not team_name:
        return [], []
    names = [entry.player for entry in keepers if entry.team == team_name] + [
        pick.player for pick in picks if pick.team == team_name
    ]
    # keepers.resolve only needs the player names; cost_round/team are unused
    resolved = keepers_mod.resolve(
        [KeeperEntry(team=team_name, player=name, cost_round=1) for name in names],
        pool.names(),
        aliases,
    )
    pool_names: list[str] = []
    missing: list[str] = []
    for name in names:
        pool_name = resolved.get(name)
        if pool_name is None:
            if name not in missing:
                missing.append(name)
        elif pool_name not in pool_names:
            pool_names.append(pool_name)
    return pool_names, missing


def team_roster_rows(
    service: SyncService, team_name: str
) -> tuple[list[dict[str, str]], list[str]]:
    """Pool rows (kept players resolved + entered picks, deduped, order
    kept), plus the kept/picked names that did not resolve into the pool
    (surfaced as warnings, never a crash)."""
    pool = PlayerPool.load(service.pool_path)
    pool_names, missing = _resolve_pool_names(service, team_name)
    rows: list[dict[str, str]] = []
    for pool_name in pool_names:
        row = pool.get(pool_name)
        if row is not None:
            rows.append(row)
    return rows, missing


def team_roster_names(
    service: SyncService, team_name: str
) -> tuple[list[str], list[str]]:
    """(resolved pool names, unresolvable names) in keeper-then-pick order,
    deduped — see :func:`_resolve_pool_names`."""
    return _resolve_pool_names(service, team_name)


__all__ = ["team_roster_names", "team_roster_rows"]
