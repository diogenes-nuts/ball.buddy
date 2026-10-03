"""domain/picks.py tests: snake shape, forfeits, current_pick, order, persistence."""

from pathlib import Path

import pytest

from ball_buddy.domain import picks as picks_mod
from ball_buddy.domain.keepers import KeeperEntry
from ball_buddy.io.state import StateError

TWELVE = [f"T{i:02d}" for i in range(1, 13)]


def test_twelve_team_snake_shape():
    snake = picks_mod.build_snake(TWELVE, [])
    assert len(snake) == 156
    # round 1 = start order, round 2 exactly reversed, round 3 = start order
    assert [p.team for p in snake[:12]] == TWELVE
    assert [p.team for p in snake[12:24]] == list(reversed(TWELVE))
    assert [p.team for p in snake[24:36]] == TWELVE
    # overall is sequential 1..156
    assert [p.overall for p in snake] == list(range(1, 157))
    # within-round slot numbers reset per round
    assert [p.order for p in snake[:12]] == list(range(1, 13))
    assert [p.order for p in snake[12:24]] == list(range(1, 13))
    # 13 rounds per SPEC §1.1
    assert {p.round for p in snake} == set(range(1, 14))
    assert all(not p.forfeited for p in snake)


def test_forfeits_from_active_keepers_only():
    entries = [
        KeeperEntry("T01", "Alpha", 3),  # active -> forfeits (T01, 3)
        KeeperEntry("T02", "Beta", 5, opted_out=True),  # opted out -> pick stays open
        KeeperEntry("T03", "Gamma", 2),  # active -> forfeits (T03, 2)
    ]
    snake = picks_mod.build_snake(TWELVE, entries)
    by_slot = {(p.round, p.team): p for p in snake}
    assert by_slot[(3, "T01")].forfeited is True
    assert by_slot[(5, "T02")].forfeited is False
    assert by_slot[(2, "T03")].forfeited is True
    # all other picks open
    forfeited = [(p.round, p.team) for p in snake if p.forfeited]
    assert sorted(forfeited) == [(2, "T03"), (3, "T01")]


def test_keeper_forfeits_helper():
    entries = [
        KeeperEntry("T01", "Alpha", 3),
        KeeperEntry("T01", "Beta", 7, opted_out=True),
    ]
    assert picks_mod.keeper_forfeits(entries) == {("T01", 3)}


def test_current_pick_skips_forfeited_and_entered():
    snake = picks_mod.build_snake(TWELVE, [KeeperEntry("T01", "Alpha", 3)])
    # first live pick: round 1, slot 1
    assert picks_mod.current_pick(snake, []) == snake[0]
    picks = [picks_mod.DraftPick(1, 1, "T01", "P1")]
    current = picks_mod.current_pick(snake, picks)
    assert (current.round, current.order) == (1, 2)
    # fill every pick in round 1 -> round 2 slot 1 (round-3 T01 pick is forfeited)
    picks = [picks_mod.DraftPick(1, i, TWELVE[i - 1], f"P{i}") for i in range(1, 13)]
    current = picks_mod.current_pick(snake, picks)
    assert (current.round, current.order) == (2, 1)


def test_current_pick_none_when_complete():
    snake = picks_mod.build_snake(TWELVE, [KeeperEntry("T01", "Alpha", 3)])
    picks = [
        picks_mod.DraftPick(p.round, p.order, p.team, f"n{p.overall}")
        for p in snake
        if not p.forfeited
    ]
    assert len(picks) == 156 - 1
    assert picks_mod.current_pick(snake, picks) is None


def test_start_order_for_live_order_wins():
    snapshot = {
        "teams": [
            {"team_id": "1", "name": "Red"},
            {"team_id": "2", "name": "Blue"},
        ],
        "draft": {"order": ["2", "1"]},
    }
    settings = {"manual_draft_order": ["Red", "Blue"]}
    assert picks_mod.start_order_for(snapshot, settings) == ["Blue", "Red"]


def test_start_order_for_manual_merges_drops_stale_appends_new():
    snapshot = {
        "teams": [
            {"team_id": "1", "name": "Red"},
            {"team_id": "2", "name": "Blue"},
            {"team_id": "3", "name": "Green"},
        ],
        "draft": {"order": []},
    }
    settings = {"manual_draft_order": ["Blue", "Stale", "Red"]}
    assert picks_mod.start_order_for(snapshot, settings) == ["Blue", "Red", "Green"]


def test_start_order_for_fallback_to_snapshot_team_order():
    snapshot = {
        "teams": [
            {"team_id": "1", "name": "Red"},
            {"team_id": "2", "name": "Blue"},
        ],
        "draft": {"order": None},
    }
    assert picks_mod.start_order_for(snapshot, {}) == ["Red", "Blue"]
    assert picks_mod.start_order_for(None, {}) == []


def test_save_load_round_trip(tmp_path: Path):
    path = tmp_path / picks_mod.PICKS_FILE
    assert picks_mod.load(path) == []  # missing file -> []
    picks = [
        picks_mod.DraftPick(1, 1, "Red", "Nikola Jokic"),
        picks_mod.DraftPick(1, 2, "Blue", "Ghost Player"),
    ]
    picks_mod.save(picks, path)
    assert picks_mod.load(path) == picks
    # version mismatch -> StateError
    document = path.read_text(encoding="utf-8")
    path.write_text(document.replace('"version": 1', '"version": 99'), encoding="utf-8")
    with pytest.raises(StateError):
        picks_mod.load(path)
