"""Entry point: QApplication -> ui.shell.MainWindow -> exec."""

import sys


def main() -> int:
    from PySide6.QtWidgets import QApplication

    from ball_buddy.ui.shell import MainWindow
    from ball_buddy.ui.theme import apply_theme

    app = QApplication(sys.argv)
    apply_theme(app)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
