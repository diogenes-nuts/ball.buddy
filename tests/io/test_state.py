"""Tests for atomic JSON persistence (salvaged from autodraft state tests)."""

import json
from datetime import datetime
from pathlib import Path

import pytest

from ball_buddy.io.state import StateError, load_json, save_json


def test_save_load_round_trip(tmp_path: Path):
    path = tmp_path / "doc.json"
    save_json({"payload": [1, 2, 3]}, path, version=1)
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["version"] == 1
    assert raw["payload"] == [1, 2, 3]
    datetime.fromisoformat(raw["updated_at"])  # valid ISO timestamp
    loaded = load_json(path, expected_version=1)
    assert loaded == raw


def test_save_is_atomic_no_leftover_tmp(tmp_path: Path):
    path = tmp_path / "doc.json"
    save_json({"a": 1}, path, version=1)
    save_json({"a": 2}, path, version=1)
    assert [p.name for p in tmp_path.iterdir()] == ["doc.json"]
    assert not any(p.name.endswith(".tmp") for p in tmp_path.iterdir())


def test_payload_precedence(tmp_path: Path):
    path = tmp_path / "doc.json"
    save_json({"updated_at": "custom"}, path, version=1)
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["updated_at"] == "custom"


def test_creates_parent_dirs(tmp_path: Path):
    path = tmp_path / "nested" / "deep" / "doc.json"
    save_json({"a": 1}, path, version=1)
    assert load_json(path, 1) is not None


def test_load_missing_file_returns_none(tmp_path: Path):
    assert load_json(tmp_path / "nope.json", 1) is None


def test_version_mismatch_raises(tmp_path: Path):
    path = tmp_path / "doc.json"
    save_json({"a": 1}, path, version=1)
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["version"] = 99
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(StateError, match="version"):
        load_json(path, 1)


def test_invalid_json_raises(tmp_path: Path):
    path = tmp_path / "doc.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(StateError, match="not valid JSON"):
        load_json(path, 1)


def test_non_object_raises(tmp_path: Path):
    path = tmp_path / "doc.json"
    path.write_text("[1, 2]", encoding="utf-8")
    with pytest.raises(StateError, match="JSON object"):
        load_json(path, 1)
