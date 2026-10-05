"""resolve_data_dir: repo checkout vs frozen exe."""

import sys
from pathlib import Path

import pytest

from ball_buddy.pathing import resolve_data_dir


def test_default_returns_repo_data_dir() -> None:
    # pathing.py sits in ball_buddy/, so parents[1] is the repo root — the
    # same directory the old shell.py parents[2] expression resolved to.
    expected = Path(__file__).resolve().parents[1] / "data"
    assert resolve_data_dir() == expected


def test_frozen_returns_data_above_exe_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # data/ lives above the exe's own dir (dist/ball.buddy -> dist/data) so a
    # pyinstaller -y rebuild of the onedir output cannot wipe user data.
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "ball.buddy.exe"))
    assert resolve_data_dir() == tmp_path.parent / "data"

