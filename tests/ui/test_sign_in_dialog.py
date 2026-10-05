"""SignInDialog tests (offscreen Qt): auto capture + manual paste fallback."""

import os
import sys
import time
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"  # must be set before any PySide6 import

import pytest
import requests
from PySide6.QtWidgets import QApplication

from ball_buddy.io.yahoo import oauth
from ball_buddy.services.sync import SyncService
from ball_buddy.ui.views.league import SignInDialog

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

FAKE_TOKENS = {
    "access_token": "tok",
    "guid": "987654321",
    "refresh_token": "ref",
    "token_time": time.time(),
    "token_type": "bearer",
    "consumer_key": "k",
    "consumer_secret": "s",
}


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    return QApplication.instance() or QApplication([])


def _service(tmp_path: Path) -> SyncService:
    service = SyncService(tmp_path, client=None)
    service.save_settings(
        {"league_id": "847", "consumer_key": "k", "consumer_secret": "s"}
    )
    return service


def _spin_until(predicate, timeout: float = 10.0) -> None:
    """Pump the Qt event loop until predicate() is true (worker threads emit
    signals that are delivered here)."""
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() > deadline:
            raise AssertionError("timed out waiting for dialog state")
        app = QApplication.instance()
        app.processEvents()
        time.sleep(0.05)


class _FakeServer:
    """LocalCallbackServer stand-in: real bound server, no browser open."""

    def __init__(self, captured: list) -> None:
        self._real = oauth.LocalCallbackServer()
        self._real.start()
        self.captured = captured

    @property
    def callback_uri(self) -> str:
        return self._real.callback_uri

    @property
    def code_verifier(self):
        return self._real.code_verifier

    def wait(self, timeout=None):
        return self._real.wait(timeout)

    def stop(self) -> None:
        self._real.stop()


def _patch_sign_in(monkeypatch, captured: list) -> None:
    monkeypatch.setattr(
        oauth, "begin_sign_in", lambda *a, **kw: (_FakeServer(captured), "")
    )
    monkeypatch.setattr(oauth, "complete_exchange", lambda *a, **kw: dict(FAKE_TOKENS))


def test_auto_capture_path(qapp, tmp_path, monkeypatch):
    captured: list = []
    _patch_sign_in(monkeypatch, captured)
    service = _service(tmp_path)
    dialog = SignInDialog(service)
    try:
        # Simulate Yahoo's redirect hitting the local callback.
        requests.get(f"{dialog._server.callback_uri}?code=abc123", timeout=5)
        _spin_until(lambda: (tmp_path / "yahoo_tokens.json").exists())
        assert dialog.result() == 1  # accepted
    finally:
        dialog.close()
    tokens = (tmp_path / "yahoo_tokens.json").read_text(encoding="utf-8")
    assert '"tok"' in tokens


def test_manual_paste_path(qapp, tmp_path, monkeypatch):
    captured: list = []
    _patch_sign_in(monkeypatch, captured)
    service = _service(tmp_path)
    dialog = SignInDialog(service)
    try:
        dialog._timer.stop()
        dialog._show_paste()
        assert dialog.paste_widget.isVisible() is False  # not shown until exec
        dialog.paste_edit.setText(
            "http://127.0.0.1:8480/callback?code=pasted123&x=1"
        )
        dialog._paste_and_go()
        _spin_until(lambda: (tmp_path / "yahoo_tokens.json").exists())
        assert dialog.result() == 1
    finally:
        dialog.close()


def test_bad_paste_shows_error(qapp, tmp_path, monkeypatch):
    captured: list = []
    _patch_sign_in(monkeypatch, captured)
    service = _service(tmp_path)
    dialog = SignInDialog(service)
    try:
        dialog._timer.stop()
        dialog._show_paste()
        dialog.paste_edit.setText("   ")
        dialog._paste_and_go()
        assert "empty" in dialog.status_label.text()
    finally:
        dialog.close()


def test_exchange_failure_keeps_dialog_open(qapp, tmp_path, monkeypatch):
    captured: list = []
    monkeypatch.setattr(
        oauth, "begin_sign_in", lambda *a, **kw: (_FakeServer(captured), "")
    )
    monkeypatch.setattr(
        oauth,
        "complete_exchange",
        lambda *a, **kw: (_ for _ in ()).throw(oauth.OAuthError("bad code")),
    )
    service = _service(tmp_path)
    dialog = SignInDialog(service)
    try:
        dialog._timer.stop()
        dialog._show_paste()
        dialog.paste_edit.setText("somecode")
        dialog._paste_and_go()
        _spin_until(lambda: "Sign-in failed" in dialog.status_label.text())
        assert dialog.result() == 0  # still open (no accept)
        assert not (tmp_path / "yahoo_tokens.json").exists()
    finally:
        dialog.close()
