"""Snapshot adapter tests: fixture results -> document -> file round-trip."""

import json
from pathlib import Path

import pytest

from ball_buddy.io.state import StateError
from ball_buddy.io.yahoo.snapshot import (
    SNAPSHOT_VERSION,
    SnapshotError,
    load_snapshot,
    manual_snapshot,
    save_snapshot,
    to_snapshot,
)

FIXTURE = Path("tests/fixtures/snapshot_results.json")
LEAGUE_ID = "1234"


class M:
    """Minimal stand-in for yfpy models: attribute access, _extracted_data."""

    def __init__(self, data: dict) -> None:
        for key, value in data.items():
            setattr(self, key, value)
        if isinstance(data.get("players"), list):
            self.players = [M(p) for p in data["players"]]
        if isinstance(data.get("teams"), list):
            self.teams = [
                {"team": M(t["team"])} if isinstance(t, dict) and "team" in t else M(t)
                for t in data["teams"]
            ]
        self._extracted_data = data

    def __getattr__(self, name):
        return None


def load_results() -> dict:
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    teams = []
    for team in raw["teams"]:
        team = dict(team)
        team["manager"] = M(team["manager"])
        teams.append(M(team))
    return {
        "user": M(raw["user"]),
        "league": [M(league) for league in raw["league"]],
        "settings": M(raw["settings"]),
        "teams": teams,
        "draft_results": [],
        "standings": M(raw["standings"]),
        "matchups": [M(m) for m in raw["matchups"]],
    }


def test_to_snapshot_sections():
    doc = to_snapshot(load_results(), LEAGUE_ID)
    assert doc["user"]["guid"] == "987654321"
    assert doc["league"]["name"] == "Fake League"
    assert doc["league"]["key"] == "nba.fake.1234"
    assert doc["league"]["settings"]["draft_type"] == "standard"
    assert [t["name"] for t in doc["teams"]] == ["Red", "Blue"]
    red = doc["teams"][0]
    assert red["team_id"] == "100"
    assert red["manager"] == "mgr_red"
    assert red["players"][0] == {
        "player_key": "pid_jokic",
        "name": "Nikola Jokic",
        "positions": ["C"],
        "status": "ACTIVE",
    }
    assert doc["draft"]["order"] == ["100", "200"]  # from draft_position
    assert doc["draft"]["results"] == []
    assert doc["source"] == "live"
    # the duplicate week-1 matchup is deduped to one entry; the bye kept
    weeks = [m["week"] for m in doc["schedule"]]
    assert weeks == [1, 2]
    week1 = [m for m in doc["schedule"] if m["week"] == 1]
    assert len(week1) == 1
    assert week1[0]["team_a"] == "100" and week1[0]["team_b"] == "200"
    assert week1[0]["status"] == "SCHEDULED"  # richest status wins the dedupe
    bye = [m for m in doc["schedule"] if m["bye"]]
    assert len(bye) == 1 and bye[0]["week"] == 2
    assert doc["standings"] == []


def test_manual_order_fallback():
    results = load_results()
    for team in results["teams"]:
        team.draft_position = None  # pre-draft: no live order
    doc = to_snapshot(results, LEAGUE_ID, manual_order=["Blue", "Red"])
    assert doc["draft"]["order"] == ["200", "100"]
    assert doc["source"] == "manual-order"


def test_no_order_pre_draft():
    results = load_results()
    for team in results["teams"]:
        team.draft_position = None
    doc = to_snapshot(results, LEAGUE_ID)
    assert doc["draft"]["order"] is None
    assert doc["source"] == "live"


def test_round_trip(tmp_path):
    doc = to_snapshot(load_results(), LEAGUE_ID)
    save_snapshot(doc, tmp_path / "snapshot.json")
    raw = json.loads((tmp_path / "snapshot.json").read_text(encoding="utf-8"))
    assert raw["version"] == SNAPSHOT_VERSION
    datetime_ok = bool(raw["updated_at"])
    assert datetime_ok
    loaded = load_snapshot(tmp_path / "snapshot.json")
    assert loaded is not None
    for key in ("user", "league", "teams", "draft", "schedule", "standings", "source"):
        assert loaded[key] == doc[key]


def test_load_missing_returns_none(tmp_path):
    assert load_snapshot(tmp_path / "nope.json") is None


def test_version_mismatch_raises(tmp_path):
    path = tmp_path / "snapshot.json"
    save_snapshot(to_snapshot(load_results(), LEAGUE_ID), path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["version"] = 99
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(SnapshotError, match="version"):
        load_snapshot(path)


def test_corrupt_json_raises(tmp_path):
    path = tmp_path / "snapshot.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(StateError, match="not valid JSON"):
        load_snapshot(path)


def test_missing_top_field_raises(tmp_path):
    path = tmp_path / "snapshot.json"
    save_snapshot(to_snapshot(load_results(), LEAGUE_ID), path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    del raw["schedule"]
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(SnapshotError, match="missing fields"):
        load_snapshot(path)


def test_manual_snapshot_shape():
    doc = manual_snapshot(["Alpha", "  Beta ", "", "Gamma"], league_id="847")
    assert [team["name"] for team in doc["teams"]] == ["Alpha", "Beta", "Gamma"]
    assert [team["team_id"] for team in doc["teams"]] == [
        "manual-01",
        "manual-02",
        "manual-03",
    ]
    assert all(team["players"] == [] and team["manager"] == "" for team in doc["teams"])
    assert doc["source"] == "manual"
    assert doc["league"]["key"] == "847"
    # start order must stay editable via the League view's manual order
    assert doc["draft"]["order"] == []
    assert doc["schedule"] == []
    assert doc["standings"] == []


def test_manual_snapshot_empty_input_returns_empty_dict():
    assert manual_snapshot([]) == {}
    assert manual_snapshot(["", "  "]) == {}


def test_manual_snapshot_round_trip(tmp_path):
    path = tmp_path / "snapshot.json"
    save_snapshot(manual_snapshot(["Alpha", "Beta"]), path)
    loaded = load_snapshot(path)
    assert loaded is not None
    assert loaded["source"] == "manual"
    assert [team["name"] for team in loaded["teams"]] == ["Alpha", "Beta"]


def test_bad_team_raises(tmp_path):
    path = tmp_path / "snapshot.json"
    save_snapshot(to_snapshot(load_results(), LEAGUE_ID), path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    del raw["teams"][0]["manager"]
    del raw["teams"][0]["players"]
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(SnapshotError, match="missing"):
        load_snapshot(path)
