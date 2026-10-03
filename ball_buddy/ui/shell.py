"""Main window: fixed left sidebar nav + QStackedWidget pages."""

from pathlib import Path

from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ball_buddy.services.sync import SyncService
from ball_buddy.ui.views.draft import DraftView
from ball_buddy.ui.views.league import LeagueView
from ball_buddy.ui.views.placeholders import PlaceholderView

# Sentence-case labels, no emoji; Draft selected by default.
NAV_ITEMS: tuple[str, ...] = ("League", "Matchup", "Waivers", "Lineups", "Trades", "Draft")


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ball.buddy")
        self.resize(1000, 640)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # Left sidebar first (layout order = visual order). Draft is checked
        # only after the stack exists, since nav toggle callbacks read self.stack.
        layout.addWidget(self._build_sidebar())
        layout.addWidget(self._build_stack(), 1)
        self.nav_buttons[NAV_ITEMS.index("Draft")].setChecked(True)

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setFixedWidth(200)
        v = QVBoxLayout(sidebar)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons: list[QPushButton] = []
        for index, label in enumerate(NAV_ITEMS):
            button = QPushButton(label)
            button.setObjectName("nav")
            button.setCheckable(True)
            button.setFixedHeight(32)
            button.toggled.connect(
                lambda checked, i=index: checked and self.stack.setCurrentIndex(i)
            )
            v.addWidget(button)
            self.nav_group.addButton(button, index)  # explicit id: objectName "nav" collides
            self.nav_buttons.append(button)

        v.addStretch(1)
        return sidebar

    def _build_stack(self) -> QStackedWidget:
        # data/ at the repo root (gitignored local state: settings, tokens,
        # players.csv, aliases.json, snapshot.json).
        self.data_dir = Path(__file__).resolve().parents[2] / "data"
        self.sync_service = SyncService(self.data_dir)
        stack = QStackedWidget()
        for label in NAV_ITEMS:
            if label == "League":
                stack.addWidget(LeagueView(self.sync_service))
            elif label == "Draft":
                stack.addWidget(DraftView(self.sync_service))
            else:
                stack.addWidget(PlaceholderView(label.lower() + " — coming soon"))
        stack.setCurrentIndex(NAV_ITEMS.index("Draft"))
        self.stack = stack
        return stack


__all__ = ["MainWindow", "NAV_ITEMS"]
