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

from pathlib import Path

from ball_buddy.domain import keepers as keepers_mod
from ball_buddy.domain import picks as picks_mod
from ball_buddy.domain.keepers import KeeperEntry
from ball_buddy.domain.players import PlayerPool
from ball_buddy.services.sync import SyncService

# (pool, keepers, picks, aliases) quad, keyed on (data_dir, file mtimes).
# Views re-resolve rosters on every render/click; the quad is stable
# until one of the four files changes, so cache it module-wide (R5.2).
_QUAD_CACHE: dict[tuple[str, int | None, int | None, int | None, int | None],
                 tuple[PlayerPool, list[KeeperEntry], list[picks_mod.DraftPick],
                       dict[str, str]]] = {}


def _quad_paths(service: SyncService) -> tuple[Path, Path, Path, Path]:
    """The four files behind the quad, in key order (players, keepers,
    picks, aliases) — same paths the direct loads below use."""
    return (
        service.pool_path,
        service.data_dir / keepers_mod.KEEPERS_FILE,
        service.data_dir / picks_mod.PICKS_FILE,
        service.aliases_path,
    )


def _quad(
    service: SyncService,
) -> tuple[PlayerPool, list[KeeperEntry], list[picks_mod.DraftPick], dict[str, str]]:
    """The cached (pool, keepers, picks, aliases) quad for ``service``.

    Keyed on the data dir plus each file's ``st_mtime_ns`` (None when the
    file is absent); ANY mtime or existence change reloads all four.
    """
    key = (str(service.data_dir), *(
        path.stat().st_mtime_ns if path.exists() else None
        for path in _quad_paths(service)
    ))
    cached = _QUAD_CACHE.get(key)
    if cached is not None:
        return cached
    quad = (
        PlayerPool.load(service.pool_path),
        keepers_mod.load(service.data_dir / keepers_mod.KEEPERS_FILE),
        picks_mod.load(service.data_dir / picks_mod.PICKS_FILE),
        service.load_aliases(),
    )
    _QUAD_CACHE.clear()  # one active data dir at a time; drop stale entries
    _QUAD_CACHE[key] = quad
    return quad


def clear_cache() -> None:
    """Drop the quad cache (test seam)."""
    _QUAD_CACHE.clear()


def _resolve_pool_names(
    service: SyncService, team_name: str
) -> tuple[list[str], list[str]]:
    """(resolved pool names, unresolvable names) in keeper-then-pick order,
    deduped. One ``keepers.resolve`` pass."""
    pool, keepers, picks, aliases = _quad(service)
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
    pool, _keepers, _picks, _aliases = _quad(service)  # same cached pool
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


__all__ = ["clear_cache", "team_roster_names", "team_roster_rows"]
