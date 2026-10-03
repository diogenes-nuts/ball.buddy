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
