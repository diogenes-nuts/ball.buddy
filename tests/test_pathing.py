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


def test_frozen_returns_data_next_to_exe(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "ball.buddy.exe"))
    assert resolve_data_dir() == tmp_path / "data"

