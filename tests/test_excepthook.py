"""main.py error UX: the excepthook appends a traceback to <data_dir>/app.log."""

import os
import sys
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"  # must be set before any PySide6 import

import pytest
from PySide6.QtCore import qInstallMessageHandler
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ball_buddy import main as main_mod  # noqa: E402
from ball_buddy import pathing  # noqa: E402


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_excepthook_writes_app_log(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(pathing, "resolve_data_dir", lambda: tmp_path)
    monkeypatch.setattr("PySide6.QtWidgets.QMessageBox.critical", lambda *a, **k: None)

    original_hook = sys.excepthook
    main_mod._install_error_hooks()
    try:
        try:
            raise ValueError("boom for the log test")
        except ValueError as exc:
            try:
                raise exc
            except ValueError:
                sys.excepthook(*sys.exc_info())

        log = tmp_path / "app.log"
        assert log.exists()
        text = log.read_text(encoding="utf-8")
        assert "Traceback" in text
        assert "ValueError: boom for the log test" in text
    finally:
        qInstallMessageHandler(None)  # don't leak the Qt message handler
        sys.excepthook = original_hook  # don't leak the test hook to other tests


def test_excepthook_dialog_and_reraise(qapp, tmp_path, monkeypatch):
    """The crash dialog uses a None parent (a str parent raises TypeError,
    which used to be swallowed so the dialog never showed)."""
    monkeypatch.setattr(pathing, "resolve_data_dir", lambda: tmp_path)
    calls: list = []
    monkeypatch.setattr(
        "PySide6.QtWidgets.QMessageBox.critical",
        lambda *args: calls.append(args),
    )

    original_hook = sys.excepthook
    main_mod._install_error_hooks()
    try:
        try:
            raise RuntimeError("boom for the dialog test")
        except RuntimeError as exc:
            try:
                raise exc
            except RuntimeError:
                sys.excepthook(*sys.exc_info())

        assert len(calls) == 1
        parent, text = calls[0]
        assert parent is None  # str parent -> swallowed TypeError, dialog never showed
        assert isinstance(text, str)
        assert "RuntimeError" in text
    finally:
        qInstallMessageHandler(None)
        sys.excepthook = original_hook


def test_excepthook_still_calls_default_hook(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(pathing, "resolve_data_dir", lambda: tmp_path)
    monkeypatch.setattr("PySide6.QtWidgets.QMessageBox.critical", lambda *a, **k: None)
    seen: list = []

    original_hook = sys.excepthook
    sys.excepthook = lambda t, v, tb: seen.append((t, v, tb))  # stand-in default hook
    main_mod._install_error_hooks()
    try:
        try:
            raise ValueError("boom for the re-raise test")
        except ValueError as exc:
            try:
                raise exc
            except ValueError:
                sys.excepthook(*sys.exc_info())
        assert len(seen) == 1
        assert seen[0][0] is ValueError
        assert str(seen[0][1]) == "boom for the re-raise test"
    finally:
        qInstallMessageHandler(None)
        sys.excepthook = original_hook
