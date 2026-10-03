"""Main window: fixed left sidebar nav + QStackedWidget pages."""

from PySide6.QtGui import QIcon, QPixmap
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

from ball_buddy.pathing import resolve_data_dir
from ball_buddy.services.sync import SyncService
from ball_buddy.ui.appicon import draw_app_icon
from ball_buddy.ui.views.draft import DraftView
from ball_buddy.ui.views.league import LeagueView
from ball_buddy.ui.views.lineups import LineupView
from ball_buddy.ui.views.matchup import MatchupView
from ball_buddy.ui.views.trades import TradeView
from ball_buddy.ui.views.waivers import WaiverView

# Sentence-case labels, no emoji; Draft selected by default.
NAV_ITEMS: tuple[str, ...] = ("League", "Matchup", "Waivers", "Lineups", "Trades", "Draft")


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ball.buddy")
        self.setWindowIcon(QIcon(QPixmap.fromImage(draw_app_icon(64))))
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
        # players.csv, aliases.json, snapshot.json); next to the exe when frozen.
        self.data_dir = resolve_data_dir()
        self.sync_service = SyncService(self.data_dir)
        stack = QStackedWidget()
        for label in NAV_ITEMS:
            if label == "League":
                stack.addWidget(LeagueView(self.sync_service))
            elif label == "Draft":
                stack.addWidget(DraftView(self.sync_service))
            elif label == "Matchup":
                stack.addWidget(MatchupView(self.sync_service))
            elif label == "Waivers":
                stack.addWidget(WaiverView(self.sync_service))
            elif label == "Lineups":
                stack.addWidget(LineupView(self.sync_service))
            elif label == "Trades":
                stack.addWidget(TradeView(self.sync_service))
            else:
                # Every NAV_ITEMS label has a real view (M6.2); a future label
                # must add a branch here rather than silently missing a page.
                raise AssertionError(f"unhandled NAV_ITEMS label: {label!r}")
        stack.setCurrentIndex(NAV_ITEMS.index("Draft"))
        self.stack = stack
        return stack


__all__ = ["MainWindow", "NAV_ITEMS"]
