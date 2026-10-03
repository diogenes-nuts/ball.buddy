"""Domain layer must be pure Python — importing it must not pull in Qt.

pytest imports every test module (including test_shell.py, which loads
PySide6) before running any test, so this test scrubs PySide6 and
ball_buddy.domain from sys.modules and re-imports domain from scratch.
"""

import importlib
import sys


def _purge(prefixes: tuple[str, ...]) -> None:
    for name in [m for m in sys.modules if any(m == p or m.startswith(p + ".") for p in prefixes)]:
        del sys.modules[name]


def test_categories_has_nine_entries() -> None:
    _purge(("PySide6", "ball_buddy.domain"))
    domain = importlib.import_module("ball_buddy.domain")
    assert len(domain.CATEGORIES) == 9
    assert len(set(domain.CATEGORIES)) == 9


def test_import_does_not_load_pyside6() -> None:
    _purge(("PySide6", "ball_buddy.domain"))
    importlib.import_module("ball_buddy.domain")
    assert not any(m == "PySide6" or m.startswith("PySide6.") for m in sys.modules)
