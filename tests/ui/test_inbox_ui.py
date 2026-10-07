"""Offscreen tests for the League-view inbox drop-folder controls (P4)."""

import os
import shutil

os.environ["QT_QPA_PLATFORM"] = "offscreen"  # must be set before any PySide6 import

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

import ball_buddy.ui.shell as shell
from ball_buddy.io.pool import inbox
from ball_buddy.io.yahoo import auth
from ball_buddy.ui.shell import NAV_ITEMS, MainWindow

FIXTURE = Path("tests/fixtures/hashtag_sample.html")
SEED_CSV = "name,pos,team\nOLD PLAYER,X,NOP\n"


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qapp, tmp_path, monkeypatch) -> MainWindow:
    # Never touch the real data dir: point the shell at a sandbox.
    monkeypatch.setattr(shell, "resolve_data_dir", lambda: tmp_path)
    return MainWindow()


def _league(window: MainWindow):
    return window.stack.widget(NAV_ITEMS.index("League"))


def test_launch_scan_banner_and_undo(window: MainWindow, tmp_path) -> None:
    # Rebuild with a seeded old pool + a valid export already in the inbox
    # (the fixture window scanned an empty inbox at launch).
    inbox.inbox_dir(tmp_path)
    (tmp_path / "players.csv").write_text(SEED_CSV, encoding="utf-8")
    shutil.copyfile(FIXTURE, inbox.inbox_dir(tmp_path) / "sample.html")
    league = _league(window)
    league.rescan_inbox()

    # Scan imported the fixture: success banner + undo visible.
    assert not league.inbox_banner.isHidden()
    assert league.inbox_banner.objectName() == "banner-success"
    text = league.inbox_banner.text()
    assert "sample.html" in text and "3 players" in text
    assert not league.inbox_undo_button.isHidden()
    assert (tmp_path / "players.prev.csv").read_text(encoding="utf-8") == SEED_CSV

    # Undo restores the previous pool and hides the banner.
    league.inbox_undo_button.click()
    assert league.inbox_banner.isHidden()
    assert league.inbox_undo_button.isHidden()
    assert (tmp_path / "players.csv").read_text(encoding="utf-8") == SEED_CSV
    assert not (tmp_path / "players.prev.csv").exists()


def test_launch_scan_at_init(qapp, tmp_path, monkeypatch) -> None:
    # Seed before construction so the __init__ launch scan picks it up.
    inbox.inbox_dir(tmp_path)
    (tmp_path / "players.csv").write_text(SEED_CSV, encoding="utf-8")
    shutil.copyfile(FIXTURE, inbox.inbox_dir(tmp_path) / "sample.html")
    monkeypatch.setattr(shell, "resolve_data_dir", lambda: tmp_path)
    window = MainWindow()
    league = _league(window)

    assert not league.inbox_banner.isHidden()
    assert league.inbox_banner.objectName() == "banner-success"
    assert "sample.html" in league.inbox_banner.text()
    assert not league.inbox_undo_button.isHidden()
    # draft board was not built during __init__'s launch scan, but its pool
    # (built right after) already reflects the imported players
    draft = window.stack.widget(NAV_ITEMS.index("Draft"))
    assert draft.board is not None
    assert "Nikola Jokic" in draft.board._pool.names()


def test_mid_session_rescan_invalidates_draft_board_pool(
    qapp, tmp_path, monkeypatch
) -> None:
    # A manual team list (seeded before construction) gives the board an
    # effective snapshot, so its refresh() proceeds as far as the pool
    # reload (board.py:210).
    inbox.inbox_dir(tmp_path)
    auth.save_settings(tmp_path, {"manual_teams": ["Team A", "Team B"]})
    monkeypatch.setattr(shell, "resolve_data_dir", lambda: tmp_path)
    window = MainWindow()
    league = _league(window)
    assert league.inbox_banner.isHidden()

    draft = window.stack.widget(NAV_ITEMS.index("Draft"))
    board = draft.board
    assert board is not None
    assert "Nikola Jokic" not in board._pool.names()

    # Drop a valid export, then hit Rescan.
    shutil.copyfile(FIXTURE, inbox.inbox_dir(tmp_path) / "sample.html")
    league.rescan_button.click()

    assert not league.inbox_banner.isHidden()
    assert league.inbox_banner.objectName() == "banner-success"
    # pool_changed -> draft.refresh() reloaded the board's cached pool
    # (same teams/keepers key: the existing board refreshes in place)
    assert draft.board is board
    assert "Nikola Jokic" in draft.board._pool.names()


def test_unparseable_export_shows_danger_banner(window: MainWindow, tmp_path) -> None:
    league = _league(window)
    (inbox.inbox_dir(tmp_path) / "bad.html").write_text(
        "<html><body>no grid here</body></html>", encoding="utf-8"
    )

    outcome = league.rescan_inbox()
    assert [e.file for e in outcome.errors] == ["bad.html"]
    assert not league.inbox_banner.isHidden()
    assert league.inbox_banner.objectName() == "banner-danger"
    assert "bad.html" in league.inbox_banner.text()
    assert league.inbox_undo_button.isHidden()
