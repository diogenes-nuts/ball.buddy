"""Snapshot model: raw yfpy models -> plain-dict JSON document (plan §3).

The adapter maps each yfpy model onto a small, explicit dict shape (not raw
``_extracted_data`` dumps) so the snapshot stays stable against yfpy model
churn (SPEC R1). ``SNAPSHOT_VERSION`` guards :func:`load_snapshot`.
"""

from __future__ import annotations

from pathlib import Path

from ball_buddy.io.state import StateError, load_json, save_json

SNAPSHOT_VERSION = 1

_TOP_FIELDS = ("updated_at", "user", "league", "teams", "draft", "schedule", "standings", "source")


class SnapshotError(StateError):
    """A snapshot document failed validation."""


def _text(value: object) -> str:
    return "" if value is None else str(value)


def _name_of(name: object) -> str:
    """Full name from a yfpy ``Name`` model (or a bare string)."""
    if isinstance(name, str):
        return name
    full = getattr(name, "full", None)
    if full:
        return full
    first = _text(getattr(name, "first", None))
    last = _text(getattr(name, "last", None))
    return " ".join(part for part in (first, last) if part)


def _player_of(player: object) -> dict:
    positions: list[str] = []
    eligible = (
        getattr(player, "eligible_positions", None) or getattr(player, "positions", None) or []
    )
    for position in eligible:
        label = _text(getattr(position, "position", None) or position)
        if label and label not in positions:
            positions.append(label)
    return {
        "player_key": _text(getattr(player, "player_key", None)),
        "name": _name_of(getattr(player, "name", None)),
        "positions": positions,
        "status": _text(getattr(player, "status", None)),
    }


def _team_of(team: object) -> dict:
    manager = getattr(team, "manager", None)
    players = []
    roster = getattr(team, "roster", None)
    if roster is not None:
        raw_players = getattr(roster, "players", None) or []
    else:
        raw_players = getattr(team, "players", None) or []
    for player in raw_players:
        players.append(_player_of(player))
    return {
        "team_id": _text(getattr(team, "team_id", None) or getattr(team, "team_key", None)),
        "name": _text(getattr(team, "name", None)),
        "manager": _text(getattr(manager, "nickname", None)),
        "manager_guid": _text(getattr(manager, "guid", None)),
        "players": players,
    }


def _matchup_of(matchup: object) -> dict:
    entries = []
    for team in (getattr(matchup, "teams", None) or []):
        entries.append(team.get("team") if isinstance(team, dict) else team)
    a = entries[0] if entries else None
    b = entries[1] if len(entries) > 1 else None

    def _id_of(team: object) -> str:
        return _text(getattr(team, "team_id", None) or getattr(team, "team_key", None))

    return {
        "week": int(getattr(matchup, "week", 0) or 0),
        "team_a": _id_of(a),
        "team_b": _id_of(b) if b is not None else "",
        "bye": b is None,
        "status": _text(getattr(matchup, "status", None)),
    }


def _schedule_from_matchups(matchups: list[object]) -> list[dict]:
    """Dedupe matchups by (week, sorted team pair); keep richest status."""
    seen: dict[tuple, dict] = {}
    for matchup in matchups:
        entry = _matchup_of(matchup)
        week = entry["week"]
        if entry["bye"]:
            key = (week, entry["team_a"], "")
        else:
            pair = tuple(sorted((entry["team_a"], entry["team_b"])))
            entry["team_a"], entry["team_b"] = pair
            key = (week, pair[0], pair[1])
        existing = seen.get(key)
        if existing is None or (not existing["status"] and entry["status"]):
            seen[key] = entry
    return sorted(seen.values(), key=lambda m: (m["week"], m["team_a"], m["team_b"]))


def _draft_results_of(results: object) -> list[dict]:
    out = []
    for result in results or []:
        out.append(
            {
                "round": int(getattr(result, "round", 0) or 0),
                "pick": int(getattr(result, "pick", 0) or 0),
                "team_key": _text(getattr(result, "team_key", None)),
                "player_key": _text(getattr(result, "player_key", None)),
            }
        )
    return out


def _standings_of(standings: object) -> list[dict]:
    out = []
    for team in (getattr(standings, "teams", None) or []):
        out.append(
            {
                "team_key": _text(getattr(team, "team_key", None)),
                "name": _text(getattr(team, "name", None)),
                "rank": int(getattr(team, "rank", 0) or 0),
                "wins": int(getattr(team, "wins", 0) or 0),
                "losses": int(getattr(team, "losses", 0) or 0),
                "ties": int(getattr(team, "ties", 0) or 0),
            }
        )
    return out


def _settings_of(settings: object) -> dict:
    data = getattr(settings, "_extracted_data", None)
    return dict(data) if isinstance(data, dict) else {}


def _live_order(teams: object) -> list[str] | None:
    """Commission start order from each team's draft_position, if complete."""
    positions = [
        (int(getattr(team, "draft_position", 0) or 0), _text(getattr(team, "team_id", None)))
        for team in (teams or [])
    ]
    valid = all(p[0] > 0 for p in positions) and len(positions) == len(set(p[1] for p in positions))
    if not positions or not valid:
        return None
    positions.sort()
    return [key for _, key in positions]


def to_snapshot(
    results: dict,
    league_id: str,
    manual_order: list[str] | None = None,
) -> dict:
    """Map a :meth:`YahooClient.fetch_all` results dict onto the snapshot doc.

    ``results`` keys: user, league, settings, teams, draft_results,
    standings, matchups. ``manual_order`` (team names in commission-start
    order) is the fallback when Yahoo does not expose a live draft order
    (pre-draft).
    """
    league_name = ""
    league_key = ""
    for league in (results.get("league") or []):
        lid = _text(getattr(league, "league_id", None))
        league_name = _text(getattr(league, "name", None) or getattr(league, "display_name", None))
        league_key = _text(getattr(league, "league_key", None))
        if lid == league_id:
            break

    teams = [_team_of(team) for team in (results.get("teams") or [])]

    order = _live_order(results.get("teams"))
    source = "live"
    if order is None and manual_order:
        by_name = {team["name"]: team["team_id"] for team in teams}
        resolved = [by_name[name] for name in manual_order if name in by_name]
        if len(resolved) == len(teams) and teams:
            order = resolved
            source = "manual-order"

    settings = _settings_of(results.get("settings"))
    return {
        "user": {"guid": _text(getattr(results.get("user"), "guid", None))},
        "league": {
            "key": league_key or league_id,
            "name": league_name or league_id,
            "settings": settings,
        },
        "teams": teams,
        "draft": {
            "type": settings.get("draft_type"),
            "pick_time": settings.get("draft_pick_time"),
            "time": settings.get("draft_time"),
            "order": order,
            "results": _draft_results_of(results.get("draft_results")),
        },
        "schedule": _schedule_from_matchups(results.get("matchups") or []),
        "standings": _standings_of(results.get("standings")),
        "source": source,
    }


def manual_snapshot(teams: list[str], league_id: str = "") -> dict:
    """A minimal snapshot doc built from a manual team list (offline).

    Used when there is no Yahoo sync yet (no snapshot.json) but the user
    entered the league's team names in Settings (``manual_teams``). Team ids
    are synthetic (``manual-01``...) so every consumer of the doc (views,
    board, engine) works unchanged. ``draft.order`` stays empty so the
    League view's up/down order editor + ``manual_draft_order`` remain the
    start-order source. Returns an empty dict when ``teams`` is empty.
    """
    names = [name.strip() for name in teams if name.strip()]
    if not names:
        return {}
    return {
        "user": {"guid": ""},
        "league": {
            "key": league_id or "manual",
            "name": "Manual team list (offline)",
            "settings": {},
        },
        "teams": [
            {
                "team_id": f"manual-{index:02d}",
                "name": name,
                "manager": "",
                "manager_guid": "",
                "players": [],
            }
            for index, name in enumerate(names, start=1)
        ],
        "draft": {"type": None, "pick_time": None, "time": None, "order": [], "results": []},
        "schedule": [],
        "standings": [],
        "source": "manual",
    }


def save_snapshot(document: dict, path: str | Path) -> None:
    """Write the snapshot doc (adds version + updated_at) atomically."""
    save_json(document, path, SNAPSHOT_VERSION)


def load_snapshot(path: str | Path) -> dict | None:
    """Load and validate a snapshot doc; ``None`` if the file is missing.

    Validates the top-level shape (SPEC R1) before handing it to the UI.
    Raises :class:`SnapshotError` on malformed or wrong-version documents.
    """
    try:
        raw = load_json(path, SNAPSHOT_VERSION)
    except StateError as exc:
        raise SnapshotError(str(exc)) from exc
    if raw is None:
        return None
    try:
        missing = [field for field in _TOP_FIELDS if field not in raw]
        if missing:
            raise SnapshotError(f"snapshot {path} is missing fields {missing!r}")
        for team in raw["teams"]:
            for key in ("team_id", "name", "players"):
                if key not in team:
                    raise SnapshotError(f"snapshot {path} team is missing {key!r}")
        for week in raw["schedule"]:
            for key in ("week", "team_a", "bye"):
                if key not in week:
                    raise SnapshotError(f"snapshot {path} schedule entry is missing {key!r}")
    except SnapshotError:
        raise
    except Exception as exc:
        raise SnapshotError(f"snapshot {path} failed validation: {exc}") from exc
    return raw
