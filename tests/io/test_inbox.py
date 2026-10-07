"""Tests for the data/inbox drop-folder auto-import (P4, headless)."""

from __future__ import annotations

import shutil
from pathlib import Path

from ball_buddy.io.pool import inbox
from ball_buddy.io.pool.importer import load_players

FIXTURE = Path("tests/fixtures/hashtag_sample.html")
SEED_CSV = "name,pos,team\nOLD PLAYER,X,NOP\n"


def _seed(data_dir: Path, old_csv: bool = True) -> None:
    """Create an inbox dir; optionally seed a pre-existing players.csv."""
    inbox.inbox_dir(data_dir)
    if old_csv:
        (data_dir / "players.csv").write_text(SEED_CSV, encoding="utf-8")


def _drop(data_dir: Path, name: str = "sample.html") -> Path:
    target = inbox.inbox_dir(data_dir) / name
    shutil.copyfile(FIXTURE, target)
    return target


# -- scan behavior ------------------------------------------------------------


def test_first_scan_imports_and_keeps_prev(tmp_path: Path) -> None:
    _seed(tmp_path)
    _drop(tmp_path)
    outcome = inbox.scan_inbox(tmp_path)

    assert len(outcome.imported) == 1
    assert outcome.imported[0].file == "sample.html"
    assert outcome.imported[0].players == 3
    assert outcome.errors == []
    assert outcome.unchanged == []

    # csv written with the parsed rows; previous csv preserved for undo
    rows = load_players(tmp_path / "players.csv")
    assert len(rows) == 3
    assert rows[0]["name"] == "Nikola Jokic"
    assert (tmp_path / "players.prev.csv").read_text(encoding="utf-8") == SEED_CSV

    state = inbox.load_state(tmp_path)
    entry = state["files"]["sample.html"]
    assert entry["sha256"] == inbox.sha256_file(tmp_path / "inbox/sample.html")
    assert entry["players"] == 3
    assert entry["imported_at"]


def test_second_scan_same_sha_unchanged(tmp_path: Path) -> None:
    _seed(tmp_path)
    _drop(tmp_path)
    inbox.scan_inbox(tmp_path)
    before = (tmp_path / "players.csv").read_text(encoding="utf-8")

    outcome = inbox.scan_inbox(tmp_path)
    assert outcome.imported == []
    assert outcome.errors == []
    assert outcome.unchanged == ["sample.html"]
    assert (tmp_path / "players.csv").read_text(encoding="utf-8") == before


def test_modified_file_reimports(tmp_path: Path) -> None:
    _seed(tmp_path)
    _drop(tmp_path)
    inbox.scan_inbox(tmp_path)

    path = _drop(tmp_path)
    path.write_text(
        path.read_text(encoding="utf-8") + "<!-- touched -->", encoding="utf-8"
    )
    outcome = inbox.scan_inbox(tmp_path)
    assert [e.file for e in outcome.imported] == ["sample.html"]
    assert outcome.unchanged == []


def test_garbage_html_reports_error_and_keeps_csv(tmp_path: Path) -> None:
    _seed(tmp_path)
    (inbox.inbox_dir(tmp_path) / "bad.html").write_text(
        "<html><body>no grid here</body></html>", encoding="utf-8"
    )
    before = (tmp_path / "players.csv").read_text(encoding="utf-8")

    outcome = inbox.scan_inbox(tmp_path)
    assert outcome.imported == []
    assert outcome.unchanged == []
    assert len(outcome.errors) == 1
    assert outcome.errors[0].file == "bad.html"
    assert (tmp_path / "players.csv").read_text(encoding="utf-8") == before
    # the file stays in the inbox for inspection
    assert (inbox.inbox_dir(tmp_path) / "bad.html").exists()


def test_multiple_files_imported_in_sort_order(tmp_path: Path) -> None:
    _seed(tmp_path)
    shutil.copyfile(FIXTURE, inbox.inbox_dir(tmp_path) / "b.html")
    shutil.copyfile(FIXTURE, inbox.inbox_dir(tmp_path) / "a.html")
    outcome = inbox.scan_inbox(tmp_path)
    assert [e.file for e in outcome.imported] == ["a.html", "b.html"]
    # one prev per scan: undo reverts to the pre-import pool, not
    # just-before-the-last-file
    assert (tmp_path / "players.prev.csv").read_text(encoding="utf-8") == SEED_CSV
    assert inbox.restore_prev_pool(tmp_path) is True
    assert (tmp_path / "players.csv").read_text(encoding="utf-8") == SEED_CSV


def test_empty_inbox_noop(tmp_path: Path) -> None:
    _seed(tmp_path, old_csv=False)
    outcome = inbox.scan_inbox(tmp_path)
    assert (outcome.imported, outcome.errors, outcome.unchanged) == ([], [], [])
    assert not (tmp_path / "players.csv").exists()


# -- undo / restore ------------------------------------------------------------


def test_restore_prev_pool(tmp_path: Path) -> None:
    _seed(tmp_path)
    _drop(tmp_path)
    inbox.scan_inbox(tmp_path)

    assert inbox.restore_prev_pool(tmp_path) is True
    assert (tmp_path / "players.csv").read_text(encoding="utf-8") == SEED_CSV
    assert not (tmp_path / "players.prev.csv").exists()


def test_restore_prev_pool_without_prev(tmp_path: Path) -> None:
    _seed(tmp_path, old_csv=False)
    assert inbox.restore_prev_pool(tmp_path) is False


# -- state / dedupe -------------------------------------------------------------


def test_record_import_dedupes_manual_inbox_import(tmp_path: Path) -> None:
    _seed(tmp_path)
    path = _drop(tmp_path)
    assert inbox.record_import(tmp_path, path, players=3) is True

    # a scan now sees the manual import as current, not new
    outcome = inbox.scan_inbox(tmp_path)
    assert outcome.imported == []
    assert outcome.unchanged == ["sample.html"]


def test_record_import_ignores_non_inbox(tmp_path: Path) -> None:
    _seed(tmp_path, old_csv=False)
    outside = tmp_path / "elsewhere.html"
    shutil.copyfile(FIXTURE, outside)
    assert inbox.record_import(tmp_path, outside) is False
    assert inbox.load_state(tmp_path) == {}


def test_in_inbox_path_forms(tmp_path: Path, monkeypatch) -> None:
    inbox.inbox_dir(tmp_path)
    inside = inbox.inbox_dir(tmp_path) / "sample.html"
    shutil.copyfile(FIXTURE, inside)
    # absolute, relative (cwd-based), and redundant forms all compare inside
    assert inbox.in_inbox(tmp_path, inside) is True
    monkeypatch.chdir(tmp_path)
    assert inbox.in_inbox(tmp_path, "inbox/sample.html") is True
    assert inbox.in_inbox(tmp_path, inside.parent / ".." / "inbox" / "sample.html") is True
    assert inbox.in_inbox(tmp_path, tmp_path / "elsewhere.html") is False


def test_corrupt_state_recovers(tmp_path: Path) -> None:
    _seed(tmp_path)
    inbox.state_path(tmp_path).write_text("{not json", encoding="utf-8")
    _drop(tmp_path)
    outcome = inbox.scan_inbox(tmp_path)  # must not raise
    assert len(outcome.imported) == 1


def test_inbox_dir_created_on_demand(tmp_path: Path) -> None:
    path = inbox.inbox_dir(tmp_path)
    assert path == tmp_path / "inbox"
    assert path.is_dir()
