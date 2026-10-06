"""Draft page (M2.1/P1): the draft board plus a pointer to the Setup dialog.

Keeper entry moved out of this page into ``SetupDialog``
(``ui/views/setup_dialog.py``), which edits the same stores this view and
the board read: data/keepers.json and settings.json (manual teams /
start order / my team). This view keeps the offline banner, the keeper
cap-drop alert (``keepers.json`` exceeding 2/team), and the embedded
board; ``refresh()`` re-loads the snapshot + keepers.json and re-builds the
board when teams or saved keepers changed. All colors come from existing
theme tokens (``panel``/``banner``/``banner-success``/``banner-danger``).
No emoji; sentence-case labels.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ball_buddy.domain import keepers as keepers_mod
from ball_buddy.domain.keepers import KeeperEntry
from ball_buddy.io.state import StateError
from ball_buddy.services.sync import SyncService
from ball_buddy.ui.views import _offline
from ball_buddy.ui.views.board import DraftBoard
from ball_buddy.ui.views.setup_dialog import SetupDialog


class DraftView(QWidget):
    """Draft page: embedded board + Setup (keeper entry lives in the dialog)."""

    def __init__(self, service: SyncService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.service = service
        self.keepers_path = service.data_dir / keepers_mod.KEEPERS_FILE
        self.teams: list[str] = []
        self.board: DraftBoard | None = None
        self._dropped_msg: str = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        header = QVBoxLayout()
        title = QLabel("draft")
        title.setObjectName("title")
        header.addWidget(title)
        note = QLabel(
            "Draft order, team names, keepers, and your own team: use "
            "Setup on the draft board below."
        )
        note.setObjectName("secondary")
        note.setWordWrap(True)
        header.addWidget(note)
        root.addLayout(header)

        self.offline_banner = QLabel("")
        self.offline_banner.setObjectName("banner-info")
        self.offline_banner.setWordWrap(True)
        self.offline_banner.setVisible(False)
        root.addWidget(self.offline_banner)

        self.status_banner = QLabel("")
        self.status_banner.setObjectName("banner-info")
        self.status_banner.setWordWrap(True)
        self.status_banner.setVisible(False)
        root.addWidget(self.status_banner)
        self.alert_banner = QLabel("")
        self.alert_banner.setObjectName("banner-danger")
        self.alert_banner.setWordWrap(True)
        self.alert_banner.setVisible(False)
        root.addWidget(self.alert_banner)

        self.board_title = QLabel("Draft board")
        self.board_title.setObjectName("title")
        root.addWidget(self.board_title)

        self.refresh()

    # -- data loading ----------------------------------------------------------

    def refresh(self) -> None:
        """Rebuild the board from the effective snapshot + saved keepers.json.

        The effective snapshot is the last Yahoo snapshot when one exists,
        else the manual team list from Settings (offline mode) — keepers and
        the embedded board both work from team names alone.
        """
        snapshot = self.service.effective_snapshot()
        if snapshot is None:
            self.teams = []
            _offline.hide_banner(self.offline_banner)
            self._set_banner(
                self.alert_banner, "banner-danger", "Sync the league first (League → Sync now)"
            )
            self._set_banner(self.status_banner, "banner-info", "")
            self._rebuild_board([])
            return

        self._set_banner(self.alert_banner, "banner-danger", "")
        if _offline.is_manual(snapshot):
            _offline.show_banner(self.offline_banner)
        else:
            _offline.hide_banner(self.offline_banner)
        self.teams = [team["name"] for team in snapshot.get("teams", [])]

        all_saved: list[KeeperEntry] = []
        try:
            all_saved = keepers_mod.load(self.keepers_path)
        except StateError as exc:
            self._set_banner(self.alert_banner, "banner-danger", f"keepers.json: {exc}")
        # structural 2/team cap: entries beyond the cap are dropped from the
        # board (the Setup dialog's validate() is the enforcement point)
        per_team: dict[str, int] = {}
        saved: list[KeeperEntry] = []
        dropped: list[KeeperEntry] = []
        for entry in all_saved:
            per_team[entry.team] = per_team.get(entry.team, 0) + 1
            if per_team[entry.team] > keepers_mod.MAX_KEEPERS_PER_TEAM:
                dropped.append(entry)
            else:
                saved.append(entry)
        self._dropped_msg = (
            ""
            if not dropped
            else "keepers.json exceeds 2 per team — not shown: "
            + ", ".join(f"{e.player} ({e.team})" for e in dropped)
        )
        if self._dropped_msg:
            self._set_banner(self.alert_banner, "banner-danger", self._dropped_msg)
        else:
            self._set_banner(self.status_banner, "banner-info", "")
        self._rebuild_board(saved)

    def _rebuild_board(self, saved: list[KeeperEntry]) -> None:
        """Re-create the draft board when teams or saved keepers changed."""
        key = (tuple(self.teams), tuple(saved))
        if self.board is not None and getattr(self, "_board_key", None) == key:
            self.board.refresh()
            return
        if self.board is not None:
            self.board.setParent(None)
        self.board = DraftBoard(self.service, list(saved))
        self._board_key = key
        self.board.setup_requested.connect(self._open_setup)
        layout = self.layout()  # type: ignore[union-attr]
        if layout is not None:
            layout.addWidget(self.board)

    def _open_setup(self) -> None:
        """Open the Setup dialog; refresh the view when the user saved."""
        if SetupDialog(self.service, self).exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    @staticmethod
    def _set_banner(label: QLabel, object_name: str, text: str) -> None:
        if label.objectName() != object_name:
            label.setObjectName(object_name)
            label.style().unpolish(label)
            label.style().polish(label)
        label.setText(text)
        label.setVisible(bool(text))


__all__ = ["DraftView"]
