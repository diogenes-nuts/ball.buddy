"""Domain layer must be pure Python — importing it must not pull in Qt.

The shell tests load PySide6 in the same process, and mid-process purging of
loaded Qt C-extensions corrupts shiboken (segfault), so instead of nuking
PySide6 from sys.modules we record which PySide6 modules are present and
assert that re-importing ``ball_buddy.domain`` adds none of them.
"""

import importlib
import sys


def _pyside6_modules() -> set[str]:
    return {m for m in sys.modules if m == "PySide6" or m.startswith("PySide6.")}


def _purge_domain() -> None:
    prefix = "ball_buddy.domain"
    for name in [m for m in sys.modules if m == prefix or m.startswith(prefix + ".")]:
        del sys.modules[name]


def test_categories_has_nine_entries() -> None:
    _purge_domain()
    domain = importlib.import_module("ball_buddy.domain")
    assert len(domain.CATEGORIES) == 9
    assert len(set(domain.CATEGORIES)) == 9


def test_import_does_not_load_pyside6() -> None:
    before = _pyside6_modules()
    _purge_domain()
    importlib.import_module("ball_buddy.domain")
    added = _pyside6_modules() - before
    assert not added, f"importing domain pulled in Qt: {sorted(added)}"
