"""League model: config loader/validator + snake draft order (salvage).

Salvaged from autodraft ``config.py`` + ``league.py`` (merged; code kept
verbatim, only the cross-import was folded into one module). Stdlib only.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

VALID_POSITIONS: frozenset[str] = frozenset({"PG", "SG", "SF", "PF", "C"})

# The standard 9 categories; keys map to players.csv per-game fields.
STANDARD_CATEGORY_KEYS: frozenset[str] = frozenset(
    {"fg_pct", "ft_pct", "three_pg", "pts_pg", "reb_pg", "ast_pg", "stl_pg", "blk_pg", "to_pg"}
)

VALID_DIRECTIONS: frozenset[str] = frozenset({"higher", "lower"})

DEFAULT_WEIGHT = 1.0


class LeagueConfigError(ValueError):
    """The league.json config is missing, unreadable, or invalid."""


@dataclass(frozen=True)
class RosterSlot:
    """One roster line, e.g. G (1, PG|SG)."""

    slot: str
    count: int
    eligible: tuple[str, ...]


@dataclass(frozen=True)
class LeagueCategory:
    """One head-to-head category and its better direction."""

    key: str
    label: str
    direction: str  # "higher" or "lower"


@dataclass(frozen=True)
class Keeper:
    """A kept player and the draft round his keeper consumes."""

    team: str
    player: str
    cost_round: int


@dataclass(frozen=True)
class LeagueConfig:
    """A fully validated league definition."""

    teams: tuple[str, ...]
    start_order: tuple[str, ...]
    rounds: int
    games_per_week: float
    slots: tuple[RosterSlot, ...]
    categories: tuple[LeagueCategory, ...]
    weights: dict[str, float]  # full map: every category key -> weight
    keepers: tuple[Keeper, ...]
    warnings: tuple[str, ...] = field(default=())

    def roster_size(self) -> int:
        """Total roster slots across all slot lines."""
        return sum(s.count for s in self.slots)


def _require_list(raw: object, name: str) -> list[object]:
    if not isinstance(raw, list):
        raise LeagueConfigError(f"'{name}' must be a list")
    return raw


def _validate_teams(raw: object) -> tuple[str, ...]:
    teams = _require_list(raw, "teams")
    result: list[str] = []
    for team in teams:
        if not isinstance(team, str) or not team.strip():
            raise LeagueConfigError(f"'teams' entries must be non-empty strings, got {team!r}")
        if team in result:
            raise LeagueConfigError(f"duplicate team name: {team!r}")
        result.append(team)
    if not result:
        raise LeagueConfigError("'teams' must not be empty")
    return tuple(result)


def _validate_start_order(raw: object, teams: tuple[str, ...]) -> tuple[str, ...]:
    order = _require_list(raw, "start_order")
    if len(order) != len(teams):
        raise LeagueConfigError(
            f"'start_order' must have {len(teams)} entries (one per team), got {len(order)}"
        )
    result: list[str] = []
    for team in order:
        if not isinstance(team, str) or team not in teams:
            raise LeagueConfigError(f"'start_order' contains unknown team {team!r}")
        if team in result:
            raise LeagueConfigError(f"'start_order' lists {team!r} more than once")
        result.append(team)
    return tuple(result)


def _validate_int(raw: object, name: str, minimum: int) -> int:
    if isinstance(raw, bool) or not isinstance(raw, (int, float)) or not float(raw).is_integer():
        raise LeagueConfigError(f"'{name}' must be an integer, got {raw!r}")
    value = int(raw)
    if value < minimum:
        raise LeagueConfigError(f"'{name}' must be >= {minimum}, got {value}")
    return value


def _validate_games_per_week(raw: object) -> float:
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise LeagueConfigError(f"'games_per_week' must be a number, got {raw!r}")
    value = float(raw)
    if value < 1:
        raise LeagueConfigError(f"'games_per_week' must be >= 1, got {value}")
    return value


def _validate_slots(raw: object) -> tuple[RosterSlot, ...]:
    roster = raw
    if not isinstance(roster, dict) or not isinstance(roster.get("slots"), list):
        raise LeagueConfigError("'roster' must be an object with a 'slots' list")
    slots: list[RosterSlot] = []
    seen: set[str] = set()
    for entry in roster["slots"]:
        if not isinstance(entry, dict):
            raise LeagueConfigError(f"roster slot entries must be objects, got {entry!r}")
        slot = entry.get("slot")
        if not isinstance(slot, str) or not slot.strip():
            raise LeagueConfigError(f"roster slot 'slot' must be a non-empty string, got {slot!r}")
        if slot in seen:
            raise LeagueConfigError(f"duplicate roster slot name: {slot!r}")
        seen.add(slot)
        count = entry.get("count")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise LeagueConfigError(
                f"roster slot {slot!r} 'count' must be an integer >= 0, got {count!r}"
            )
        eligible_raw = entry.get("eligible")
        if not isinstance(eligible_raw, list) or not eligible_raw:
            raise LeagueConfigError(f"roster slot {slot!r} 'eligible' must be a non-empty list")
        for pos in eligible_raw:
            if pos not in VALID_POSITIONS:
                raise LeagueConfigError(
                    f"roster slot {slot!r} has unknown position {pos!r} "
                    f"(valid: {sorted(VALID_POSITIONS)})"
                )
        if len(set(eligible_raw)) != len(eligible_raw):
            raise LeagueConfigError(f"roster slot {slot!r} 'eligible' lists a position twice")
        slots.append(RosterSlot(slot=slot, count=count, eligible=tuple(eligible_raw)))
    if not slots:
        raise LeagueConfigError("'roster' must have at least one slot")
    return tuple(slots)


def _validate_categories(raw: object) -> tuple[LeagueCategory, ...]:
    categories = _require_list(raw, "categories")
    result: list[LeagueCategory] = []
    keys: set[str] = set()
    for entry in categories:
        if not isinstance(entry, dict):
            raise LeagueConfigError(f"'categories' entries must be objects, got {entry!r}")
        key = entry.get("key")
        if not isinstance(key, str) or not key.strip():
            raise LeagueConfigError(f"category 'key' must be a non-empty string, got {key!r}")
        if key in keys:
            raise LeagueConfigError(f"duplicate category key: {key!r}")
        keys.add(key)
        if key not in STANDARD_CATEGORY_KEYS:
            raise LeagueConfigError(
                f"unknown category key {key!r} (valid: {sorted(STANDARD_CATEGORY_KEYS)})"
            )
        label = entry.get("label")
        if not isinstance(label, str) or not label.strip():
            raise LeagueConfigError(f"category {key!r} 'label' must be a non-empty string")
        direction = entry.get("direction")
        if direction not in VALID_DIRECTIONS:
            raise LeagueConfigError(
                f"category {key!r} 'direction' must be 'higher' or 'lower', got {direction!r}"
            )
        result.append(LeagueCategory(key=key, label=label, direction=direction))
    if not result:
        raise LeagueConfigError("'categories' must not be empty")
    return tuple(result)


def _validate_weights(raw: object, categories: tuple[LeagueCategory, ...]) -> dict[str, float]:
    if not isinstance(raw, dict):
        raise LeagueConfigError("'weights' must be an object mapping category key -> number")
    weights: dict[str, float] = {}
    for key in raw:
        if key not in {c.key for c in categories}:
            raise LeagueConfigError(f"'weights' has key {key!r} which is not a defined category")
        value = raw[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise LeagueConfigError(f"'weights[{key!r}]' must be a number, got {value!r}")
        if float(value) < 0:
            raise LeagueConfigError(f"'weights[{key!r}]' must be >= 0, got {value!r}")
        weights[key] = float(value)
    for category in categories:
        weights.setdefault(category.key, DEFAULT_WEIGHT)
    return weights


def _validate_keepers(raw: object, teams: tuple[str, ...], rounds: int) -> tuple[Keeper, ...]:
    keepers = _require_list(raw, "keepers")
    result: list[Keeper] = []
    seen_players: set[str] = set()
    team_rounds: set[tuple[str, int]] = set()
    for entry in keepers:
        if not isinstance(entry, dict):
            raise LeagueConfigError(f"'keepers' entries must be objects, got {entry!r}")
        team = entry.get("team")
        if team not in teams:
            raise LeagueConfigError(f"keeper references unknown team {team!r}")
        player = entry.get("player")
        if not isinstance(player, str) or not player.strip():
            raise LeagueConfigError(f"keeper for {team!r} must name a 'player'")
        if player in seen_players:
            raise LeagueConfigError(f"keeper player {player!r} is kept by more than one team")
        seen_players.add(player)
        cost_round = entry.get("cost_round")
        if (
            isinstance(cost_round, bool)
            or not isinstance(cost_round, int)
            or not 1 <= cost_round <= rounds
        ):
            raise LeagueConfigError(
                f"keeper {player!r} 'cost_round' must be in 1..{rounds}, got {cost_round!r}"
            )
        pair = (team, cost_round)
        if pair in team_rounds:
            raise LeagueConfigError(
                f"{team!r} keeps two players costing round {cost_round} — only one pick per round"
            )
        team_rounds.add(pair)
        result.append(Keeper(team=team, player=player, cost_round=cost_round))
    return tuple(result)


def _soft_warnings(
    slots: tuple[RosterSlot, ...],
    categories: tuple[LeagueCategory, ...],
    rounds: int,
) -> list[str]:
    warnings: list[str] = []
    total = sum(s.count for s in slots)
    if total != rounds:
        warnings.append(
            f"roster size {total} != rounds {rounds}; draft will not fill every roster slot"
        )
    if {c.key for c in categories} != STANDARD_CATEGORY_KEYS:
        missing = sorted(STANDARD_CATEGORY_KEYS - {c.key for c in categories})
        warnings.append(f"non-standard category set; missing: {missing}")
    return warnings


def load_league(path: str | Path) -> LeagueConfig:
    """Load and validate a league.json file into a :class:`LeagueConfig`."""
    file_path = Path(path)
    try:
        raw = json.loads(file_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise LeagueConfigError(f"league config not found: {file_path}") from None
    except json.JSONDecodeError as exc:
        raise LeagueConfigError(f"league config {file_path} is not valid JSON: {exc}") from exc
    return validate_league(raw)


def validate_league(raw: object) -> LeagueConfig:
    """Validate a parsed league.json object into a :class:`LeagueConfig`.

    The single source of validation truth: `load_league` reads the file and
    delegates here, and the API's config save validates edited JSON here too.
    """
    if not isinstance(raw, dict):
        raise LeagueConfigError(
            f"league config must be a JSON object, got {type(raw).__name__}"
        )

    teams = _validate_teams(raw.get("teams"))
    start_order = _validate_start_order(raw.get("start_order"), teams)
    rounds = _validate_int(raw.get("rounds"), "rounds", minimum=1)
    games_per_week = _validate_games_per_week(raw.get("games_per_week"))
    slots = _validate_slots(raw.get("roster"))
    categories = _validate_categories(raw.get("categories"))
    weights = _validate_weights(raw.get("weights"), categories)
    keepers = _validate_keepers(raw.get("keepers"), teams, rounds)
    warnings = _soft_warnings(slots, categories, rounds)

    return LeagueConfig(
        teams=teams,
        start_order=start_order,
        rounds=rounds,
        games_per_week=games_per_week,
        slots=slots,
        categories=categories,
        weights=weights,
        keepers=keepers,
        warnings=tuple(warnings),
    )


"""Snake-draft order generation and the keeper/forfeit model.

The snake order includes every team in every round (odd rounds follow
``start_order``, even rounds reverse it). A keeper with a round cost does not
shorten the snake — it only marks that team's pick in the cost round as
``forfeited`` (see agents/SPEC.md sections 7 and 10).
"""


@dataclass(frozen=True)
class Pick:
    """One slot in the snake draft order."""

    round: int
    order: int  # 1-based position within the round
    team: str
    overall: int  # 1-based position in the full snake sequence
    forfeited: bool  # consumed by a keeper, no player drafted here


def snake_order(league: LeagueConfig) -> list[Pick]:
    """Full snake order for every round, with keeper-forfeited picks flagged."""
    forfeits = forfeited_picks(league)
    picks: list[Pick] = []
    for rnd in range(1, league.rounds + 1):
        seq = league.start_order if rnd % 2 == 1 else tuple(reversed(league.start_order))
        for order, team in enumerate(seq, start=1):
            picks.append(
                Pick(
                    round=rnd,
                    order=order,
                    team=team,
                    overall=len(picks) + 1,
                    forfeited=(team, rnd) in forfeits,
                )
            )
    return picks


def forfeited_picks(league: LeagueConfig) -> set[tuple[str, int]]:
    """Set of (team, round) pairs consumed by keeper costs."""
    return {(keeper.team, keeper.cost_round) for keeper in league.keepers}


def keeper_players(league: LeagueConfig) -> set[str]:
    """Names of kept players, to be removed from the draft-eligible pool."""
    return {keeper.player for keeper in league.keepers}


def remaining_picks(league: LeagueConfig, team: str) -> list[Pick]:
    """A team's live (non-forfeited) picks in full draft order."""
    return [pick for pick in snake_order(league) if pick.team == team and not pick.forfeited]
