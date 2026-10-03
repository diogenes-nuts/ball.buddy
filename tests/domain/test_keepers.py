"""Keeper entry model tests: persistence round-trip + validation rules."""

from pathlib import Path

import pytest

from ball_buddy.domain import keepers as keepers_mod
from ball_buddy.domain.keepers import KeeperEntry, load, resolve, save, validate
from ball_buddy.io.state import StateError, load_json, save_json

TEAMS = ("Red", "Blue")
POOL = ["Jokic", "Ghost Player", "Shaquille O'Neal"]


def e(team: str, player: str, cost_round: int, opted_out: bool = False) -> KeeperEntry:
    return KeeperEntry(team=team, player=player, cost_round=cost_round, opted_out=opted_out)


# -- persistence -------------------------------------------------------------


def test_save_load_roundtrip(tmp_path: Path):
    path = tmp_path / "keepers.json"
    entries = [
        e("Red", "Jokic", 1),
        e("Blue", "Ghost Player", 2, opted_out=True),
    ]
    save(entries, path)
    document = load_json(path, keepers_mod.KEEPERS_VERSION)
    assert document is not None
    assert document["keepers"] == [
        {"team": "Red", "player": "Jokic", "cost_round": 1, "opted_out": False},
        {"team": "Blue", "player": "Ghost Player", "cost_round": 2, "opted_out": True},
    ]
    assert load(path) == entries


def test_load_missing_file_returns_empty(tmp_path: Path):
    assert load(tmp_path / "keepers.json") == []


def test_load_wrong_version_raises_state_error(tmp_path: Path):
    path = tmp_path / "keepers.json"
    save_json({"keepers": []}, path, version=99)
    with pytest.raises(StateError, match="version"):
        load(path)


def test_load_corrupt_raises_state_error(tmp_path: Path):
    path = tmp_path / "keepers.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(StateError):
        load(path)


# -- validation ---------------------------------------------------------------


def test_valid_entries_no_errors():
    assert validate([e("Red", "Jokic", 1), e("Red", "Ghost Player", 3)], TEAMS) == []


def test_unknown_team():
    errors = validate([e("Green", "Jokic", 1)], TEAMS)
    assert any("unknown team" in err for err in errors)


def test_third_keeper_per_team_blocked():
    errors = validate(
        [e("Red", "Jokic", 1), e("Red", "Ghost Player", 2), e("Red", "Shaquille O'Neal", 3)],
        TEAMS,
    )
    assert any("max 2" in err for err in errors)


def test_opted_out_counts_toward_team_cap():
    errors = validate(
        [e("Red", "Jokic", 1), e("Red", "Ghost Player", 2, opted_out=True),
         e("Red", "Shaquille O'Neal", 3)],
        TEAMS,
    )
    assert any("max 2" in err for err in errors)


@pytest.mark.parametrize("cost_round", [0, 14])
def test_cost_round_bounds(cost_round: int):
    errors = validate([e("Red", "Jokic", cost_round)], TEAMS)
    assert any("cost_round" in err for err in errors)


def test_cost_round_13_allowed():
    assert validate([e("Red", "Jokic", 13)], TEAMS) == []


def test_cross_team_duplicate_player():
    errors = validate([e("Red", "Jokic", 1), e("Blue", "Jokic", 2)], TEAMS)
    assert any("kept by both" in err for err in errors)


def test_alias_equal_names_duplicate_when_resolved():
    # "Jokic" vs "Nikola Jokic": raw names differ but both bridge to pool
    # "Jokic" (containment) -> duplicate under the resolved dedupe key.
    entries = [e("Red", "Jokic", 1), e("Blue", "Nikola Jokic", 2)]
    resolved = resolve(entries, POOL)
    assert resolved["Jokic"] == "Jokic"
    assert resolved["Nikola Jokic"] == "Jokic"
    errors = validate(entries, TEAMS, resolved)
    assert any("kept by both" in err for err in errors)


def test_normalize_equal_names_duplicate_unresolved():
    # No resolved map: "jokic " normalizes to the same key as "Jokic".
    errors = validate([e("Red", "Jokic", 1), e("Blue", "jokic ", 2)], TEAMS)
    assert any("kept by both" in err for err in errors)


def test_same_team_round_blocked_for_active():
    errors = validate([e("Red", "Jokic", 2), e("Red", "Ghost Player", 2)], TEAMS)
    assert any("only one pick per round" in err for err in errors)


def test_same_team_round_allowed_when_opted_out():
    # The opted-out keeper consumes no pick, so the round is free.
    entries = [e("Red", "Jokic", 2), e("Red", "Ghost Player", 2, opted_out=True)]
    assert validate(entries, TEAMS) == []


# -- resolution ----------------------------------------------------------------


def test_resolve_matched_and_unmatched():
    entries = [e("Red", "Jokic", 1), e("Red", "Nobody Nowhere", 2)]
    resolved = resolve(entries, POOL)
    assert resolved == {"Jokic": "Jokic", "Nobody Nowhere": None}


def test_resolve_uses_alias_table():
    entries = [e("Red", "Ghost", 1)]
    resolved = resolve(entries, POOL, aliases={"Ghost": "Ghost Player"})
    assert resolved == {"Ghost": "Ghost Player"}
