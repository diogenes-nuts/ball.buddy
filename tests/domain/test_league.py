"""League model tests (salvaged from autodraft; import paths + fixture only)."""

import copy
import json
from dataclasses import replace
from pathlib import Path

import pytest

from ball_buddy.domain.league import (
    Keeper,
    LeagueConfig,
    LeagueConfigError,
    forfeited_picks,
    keeper_players,
    load_league,
    remaining_picks,
    snake_order,
)

SAMPLE = Path("tests/fixtures/league.sample.json")


def standard_categories() -> list[dict]:
    return [
        {"key": "fg_pct", "label": "FG%", "direction": "higher"},
        {"key": "ft_pct", "label": "FT%", "direction": "higher"},
        {"key": "three_pg", "label": "3PTM", "direction": "higher"},
        {"key": "pts_pg", "label": "PTS", "direction": "higher"},
        {"key": "reb_pg", "label": "REB", "direction": "higher"},
        {"key": "ast_pg", "label": "AST", "direction": "higher"},
        {"key": "stl_pg", "label": "STL", "direction": "higher"},
        {"key": "blk_pg", "label": "BLK", "direction": "higher"},
        {"key": "to_pg", "label": "TO", "direction": "lower"},
    ]


def base_config() -> dict:
    return {
        "teams": ["A", "B", "C"],
        "start_order": ["A", "B", "C"],
        "rounds": 3,
        "games_per_week": 3.5,
        "roster": {
            "slots": [
                {"slot": "PG", "count": 1, "eligible": ["PG"]},
                {"slot": "C", "count": 1, "eligible": ["C"]},
                {"slot": "UTIL", "count": 1, "eligible": ["PG", "SG", "SF", "PF", "C"]},
            ]
        },
        "categories": standard_categories(),
        "weights": {cat["key"]: 1.0 for cat in standard_categories()},
        "keepers": [],
    }


def write_league(tmp_path: Path, config: dict, name: str = "league.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(config), encoding="utf-8")
    return path


def test_sample_config_loads():
    league = load_league(SAMPLE)
    assert league.warnings == ()
    assert len(league.teams) == 12
    assert league.start_order == league.teams
    assert league.rounds == 13
    assert league.games_per_week == 3.5
    assert len(league.slots) == 9
    assert league.roster_size() == 13
    assert [c.key for c in league.categories][:3] == ["fg_pct", "ft_pct", "three_pg"]
    by_key = {c.key: c for c in league.categories}
    assert by_key["to_pg"].direction == "lower"
    assert all(c.direction == "higher" for k, c in by_key.items() if k != "to_pg")
    assert league.weights == {k: 1.0 for k in by_key}
    assert league.keepers == ()


def test_snake_two_teams_four_rounds(tmp_path):
    config = base_config()
    config["teams"] = ["A", "B"]
    config["start_order"] = ["A", "B"]
    config["rounds"] = 4
    league = load_league(write_league(tmp_path, config))
    assert [p.team for p in snake_order(league)] == ["A", "B", "B", "A", "A", "B", "B", "A"]


def test_snake_12_team_13_round_anchors():
    league = load_league(SAMPLE)
    picks = snake_order(league)
    assert len(picks) == 156
    assert [p.overall for p in picks] == list(range(1, 157))
    first = [p.overall for p in picks if p.team == "Team 1"]
    assert first == [1, 24, 25, 48, 49, 72, 73, 96, 97, 120, 121, 144, 145]
    last = [p.overall for p in picks if p.team == "Team 12"]
    assert last == [12, 13, 36, 37, 60, 61, 84, 85, 108, 109, 132, 133, 156]


def test_snake_round_parity(tmp_path):
    league = load_league(write_league(tmp_path, base_config()))
    picks = snake_order(league)
    for rnd in (1, 3):
        assert [p.team for p in picks if p.round == rnd] == ["A", "B", "C"]
    assert [p.team for p in picks if p.round == 2] == ["C", "B", "A"]


def make_keeper_league(league: LeagueConfig) -> LeagueConfig:
    return replace(
        league,
        keepers=(
            Keeper(team="Team 2", player="Player A", cost_round=3),
            Keeper(team="Team 2", player="Player B", cost_round=7),
        ),
    )


def test_keeper_forfeits_flag_specific_picks():
    league = make_keeper_league(load_league(SAMPLE))
    picks = snake_order(league)
    assert len(picks) == 156  # the snake is not shortened by keepers
    forfeited = [p for p in picks if p.forfeited]
    assert [(p.team, p.round) for p in forfeited] == [("Team 2", 3), ("Team 2", 7)]
    assert forfeited_picks(league) == {("Team 2", 3), ("Team 2", 7)}


def test_keeper_remaining_picks():
    league = make_keeper_league(load_league(SAMPLE))
    remaining = remaining_picks(league, "Team 2")
    assert len(remaining) == 11
    assert {p.round for p in remaining} == {1, 2, 4, 5, 6, 8, 9, 10, 11, 12, 13}
    assert all(not p.forfeited for p in remaining)
    for team in league.teams:
        if team != "Team 2":
            assert len(remaining_picks(league, team)) == 13


def test_keeper_players_for_pool_removal():
    league = make_keeper_league(load_league(SAMPLE))
    assert keeper_players(league) == {"Player A", "Player B"}


# --- validation hard errors -------------------------------------------------


def expect_error(tmp_path, mutator):
    config = base_config()
    mutator(config)
    with pytest.raises(LeagueConfigError):
        load_league(write_league(tmp_path, config))


def test_duplicate_team(tmp_path):
    expect_error(tmp_path, lambda c: c["teams"].append("A"))


def test_start_order_wrong_length(tmp_path):
    expect_error(tmp_path, lambda c: c["start_order"].append("A"))


def test_start_order_unknown_team(tmp_path):
    expect_error(tmp_path, lambda c: c["start_order"].__setitem__(2, "Z"))


def test_start_order_duplicate(tmp_path):
    expect_error(tmp_path, lambda c: c["start_order"].__setitem__(2, "A"))


def test_rounds_too_small(tmp_path):
    expect_error(tmp_path, lambda c: c.update(rounds=0))


def test_games_per_week_too_small(tmp_path):
    expect_error(tmp_path, lambda c: c.update(games_per_week=0.5))


def test_slot_count_zero_is_allowed(tmp_path):
    config = base_config()
    config["roster"]["slots"][0].update(count=0)
    league = load_league(write_league(tmp_path, config))
    assert league.slots[0].count == 0
    assert league.roster_size() == 2


def test_slot_count_negative(tmp_path):
    expect_error(tmp_path, lambda c: c["roster"]["slots"][0].update(count=-1))


def test_roster_without_slots(tmp_path):
    expect_error(tmp_path, lambda c: c["roster"].__setitem__("slots", []))


def test_slot_unknown_position(tmp_path):
    expect_error(tmp_path, lambda c: c["roster"]["slots"][0].update(eligible=["X"]))


def test_slot_empty_eligible(tmp_path):
    expect_error(tmp_path, lambda c: c["roster"]["slots"][0].update(eligible=[]))


def test_unknown_category_key(tmp_path):
    entry = {"key": "dunk", "label": "DUNK", "direction": "higher"}
    expect_error(tmp_path, lambda c: c["categories"].append(entry))


def test_duplicate_category_key(tmp_path):
    expect_error(tmp_path, lambda c: c["categories"].append(copy.deepcopy(c["categories"][0])))


def test_bad_direction(tmp_path):
    expect_error(tmp_path, lambda c: c["categories"][0].update(direction="best"))


def test_weight_unknown_key(tmp_path):
    expect_error(tmp_path, lambda c: c["weights"].update({"dunk": 1.0}))


def test_negative_weight(tmp_path):
    expect_error(tmp_path, lambda c: c["weights"].update({"to_pg": -1.0}))


def test_keeper_unknown_team(tmp_path):
    c = {"team": "Z", "player": "P", "cost_round": 1}
    expect_error(tmp_path, lambda cfg: cfg["keepers"].append(c))


def test_keeper_cost_round_out_of_range(tmp_path):
    keeper = {"team": "A", "player": "P", "cost_round": 4}
    expect_error(tmp_path, lambda c: c["keepers"].append(keeper))


def test_keeper_negative_cost_round(tmp_path):
    keeper = {"team": "A", "player": "P", "cost_round": 0}
    expect_error(tmp_path, lambda c: c["keepers"].append(keeper))


def test_two_keepers_same_round_same_team(tmp_path):
    expect_error(
        tmp_path,
        lambda c: c["keepers"].extend(
            [
                {"team": "A", "player": "P1", "cost_round": 2},
                {"team": "A", "player": "P2", "cost_round": 2},
            ]
        ),
    )


def test_duplicate_keeper_player(tmp_path):
    expect_error(
        tmp_path,
        lambda c: c["keepers"].extend(
            [
                {"team": "A", "player": "P", "cost_round": 1},
                {"team": "B", "player": "P", "cost_round": 2},
            ]
        ),
    )


def test_missing_file(tmp_path):
    with pytest.raises(LeagueConfigError, match="not found"):
        load_league(tmp_path / "nope.json")


def test_invalid_json(tmp_path):
    path = write_league(tmp_path, base_config())
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(LeagueConfigError, match="not valid JSON"):
        load_league(path)


# --- validation soft warnings -----------------------------------------------


def test_roster_size_mismatch_warns(tmp_path):
    config = base_config()
    config["rounds"] = 4  # roster still totals 3
    league = load_league(write_league(tmp_path, config))
    assert any("roster size 3 != rounds 4" in w for w in league.warnings)


def test_nonstandard_categories_warn(tmp_path):
    config = base_config()
    config["categories"] = config["categories"][:-1]  # drop TO
    del config["weights"]["to_pg"]  # a weight for an undefined category is a hard error
    league = load_league(write_league(tmp_path, config))
    assert any("non-standard category set" in w for w in league.warnings)
    assert league.weights == {cat["key"]: 1.0 for cat in config["categories"]}


def test_clean_config_has_no_warnings(tmp_path):
    league = load_league(write_league(tmp_path, base_config()))
    assert league.warnings == ()
