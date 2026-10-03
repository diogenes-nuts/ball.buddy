"""Data-dir resolution: repo checkout vs frozen PyInstaller build.

A frozen onedir exe lives in dist/ball.buddy/_internal/, so `__file__`-relative
paths would land inside the bundle. Frozen: data/ sits next to the exe.
All savers mkdir(parents=True), so a missing data dir is a clean state.
"""

import sys
from pathlib import Path


def resolve_data_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "data"
    # ball_buddy/pathing.py -> parents[1] is the repo root (same dir the old
    # shell.py expression produced: shell.py was one level deeper).
    return Path(__file__).resolve().parents[1] / "data"


__all__ = ["resolve_data_dir"]
