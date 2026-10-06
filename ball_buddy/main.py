"""Entry point: QApplication -> ui.shell.MainWindow -> exec.

Also installs the friend-facing error UX (M7.2): an app-wide excepthook and
Qt message handler that append to ``<data_dir>/app.log`` and point the user
at that file instead of a bare traceback.
"""

import sys
from datetime import datetime


def _install_error_hooks() -> None:
    """Log unhandled exceptions and Qt warnings/errors to <data_dir>/app.log."""
    from PySide6.QtCore import QtMsgType, qInstallMessageHandler
    from PySide6.QtWidgets import QMessageBox

    from ball_buddy.pathing import resolve_data_dir

    def _log(line: str) -> None:
        # Resolve fresh each call so tests that repoint the data dir after
        # install still land in the right place; never raise from a hook.
        data_dir = resolve_data_dir()
        data_dir.mkdir(parents=True, exist_ok=True)
        with (data_dir / "app.log").open("a", encoding="utf-8") as f:
            f.write(f"\n[{datetime.now().isoformat(timespec='seconds')}] {line}\n")

    def _qt_handler(mode: QtMsgType, context, message: str) -> None:
        try:
            if mode >= QtMsgType.WarningMsg:
                _log(f"Qt {mode.name}: {message}")
        except Exception:
            pass

    default_hook = sys.excepthook

    def _hook(exc_type, exc_value, exc_tb) -> None:
        import traceback

        log_path = None
        try:
            log_path = resolve_data_dir() / "app.log"
            _log(
                "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
            )
        except Exception:
            pass  # path resolution or logging must never skip the re-raise
        try:
            location = log_path if log_path else "the app log"
            QMessageBox.critical(
                "ball.buddy",
                f"{exc_type.__name__}: {exc_value}\n"
                f"Full details in {location}\nSend that file to the developer.",
            )
        except Exception:
            pass  # never mask the original failure with dialog problems
        default_hook(exc_type, exc_value, exc_tb)

    sys.excepthook = _hook
    qInstallMessageHandler(_qt_handler)


def main() -> int:
    from PySide6.QtWidgets import QApplication

    from ball_buddy.ui.shell import MainWindow
    from ball_buddy.ui.theme import apply_theme

    app = QApplication(sys.argv)
    _install_error_hooks()
    window = MainWindow()
    # Apply the persisted theme before first show (no light flash on a
    # dark-mode install); the sidebar toggle keeps it in sync afterwards.
    apply_theme(app, "dark" if window.sync_service.settings().get("dark_mode") else "light")
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
