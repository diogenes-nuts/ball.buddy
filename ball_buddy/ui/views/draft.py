"""Draft page (M2.1): keeper entry.

Two pre-allocated rows per team (structural 2/team cap — no team picker),
player free-text with a QCompleter over the local pool, cost round 1..13,
opt-out checkbox. Names are bridged live via the naming bridge; unmatched
names are flagged (Status + banner-alert) but still save. Only
``keepers.validate`` errors block Save.

All colors come from existing theme tokens (``panel``/``banner``/
``banner-alert``/tables). No emoji; sentence-case labels.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QCompleter,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ball_buddy.domain import keepers as keepers_mod
from ball_buddy.domain.keepers import KeeperEntry
from ball_buddy.domain.naming import bridge
from ball_buddy.domain.players import PlayerPool
from ball_buddy.io.state import StateError
from ball_buddy.services.sync import SyncService
from ball_buddy.ui.views import _offline
from ball_buddy.ui.views.board import DraftBoard

COLUMNS = ("Team", "Player", "Cost round", "Opt out", "Status")


class DraftView(QWidget):
    """Keeper entry page; saves to data/keepers.json."""

    def __init__(self, service: SyncService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.service = service
        self.keepers_path = service.data_dir / keepers_mod.KEEPERS_FILE
        self.teams: list[str] = []
        self.board: DraftBoard | None = None
        self._rows: list[dict] = []
        self._dropped_msg: str = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        header = QVBoxLayout()
        title = QLabel("draft — keeper entry")
        title.setObjectName("title")
        header.addWidget(title)
        note = QLabel(
            "Up to 2 keepers per team. Cost round is the draft round the "
            "keeper consumes (1-13); opt-out means the player stays but "
            "costs no pick. Unmatched names are flagged but still saved."
        )
        note.setObjectName("secondary")
        note.setWordWrap(True)
        header.addWidget(note)
        root.addLayout(header)

        self.offline_banner = QLabel("")
        self.offline_banner.setObjectName("banner")
        self.offline_banner.setWordWrap(True)
        self.offline_banner.setVisible(False)
        root.addWidget(self.offline_banner)

        self.status_banner = QLabel("")
        self.status_banner.setObjectName("banner")
        self.status_banner.setWordWrap(True)
        root.addWidget(self.status_banner)
        self.alert_banner = QLabel("")
        self.alert_banner.setObjectName("banner-alert")
        self.alert_banner.setWordWrap(True)
        self.alert_banner.setVisible(False)
        root.addWidget(self.alert_banner)

        panel = QWidget()
        panel.setObjectName("panel")
        root.addWidget(panel, 1)
        inner = QVBoxLayout(panel)
        inner.setContentsMargins(8, 8, 8, 8)
        inner.setSpacing(8)

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.table.setAlternatingRowColors(True)
        inner.addWidget(self.table, 1)

        self.save_button = QPushButton("Save keepers")
        self.save_button.setProperty("ink", "true")
        self.save_button.setEnabled(False)
        self.save_button.clicked.connect(self._save)
        button_row = QVBoxLayout()
        button_row.addStretch(1)
        button_row.addWidget(self.save_button, 0, Qt.AlignmentFlag.AlignRight)
        inner.addLayout(button_row)

        self.board_title = QLabel("Draft board")
        self.board_title.setObjectName("title")
        root.addWidget(self.board_title)

        self.refresh()

    # -- data loading ----------------------------------------------------------

    def refresh(self) -> None:
        """Rebuild the grid from the effective snapshot + saved keepers.json.

        The effective snapshot is the last Yahoo snapshot when one exists,
        else the manual team list from Settings (offline mode) — keepers and
        the embedded board both work from team names alone.
        """
        self._rows = []
        snapshot = self.service.effective_snapshot()
        if snapshot is None:
            self.teams = []
            self.table.setRowCount(0)
            self.save_button.setEnabled(False)
            _offline.hide_banner(self.offline_banner)
            self._set_banner(
                self.alert_banner, "banner-alert", "Sync the league first (League → Sync now)"
            )
            self._set_banner(self.status_banner, "banner", "")
            self._rebuild_board([])
            return

        self._set_banner(self.alert_banner, "banner-alert", "")
        if _offline.is_manual(snapshot):
            _offline.show_banner(self.offline_banner)
        else:
            _offline.hide_banner(self.offline_banner)
        self.teams = [team["name"] for team in snapshot.get("teams", [])]
        self.table.setRowCount(2 * len(self.teams))
        pool = PlayerPool.load(self.service.pool_path)  # once, shared by all rows
        for i, team in enumerate(self.teams):
            for slot in (0, 1):
                row = 2 * i + slot
                self._add_row(row, team, pool)

        saved: list[KeeperEntry] = []
        try:
            saved = keepers_mod.load(self.keepers_path)
        except StateError as exc:
            self._set_banner(self.alert_banner, "banner-alert", f"keepers.json: {exc}")
        dropped: list[KeeperEntry] = []
        for entry in saved:
            if not self._apply_entry(entry):
                dropped.append(entry)
        self._dropped_msg = (
            ""
            if not dropped
            else "keepers.json exceeds 2 per team — not shown (re-saving deletes them): "
            + ", ".join(f"{e.player} ({e.team})" for e in dropped)
        )
        self.save_button.setEnabled(True)
        self._set_banner(self.status_banner, "banner", "")
        self.update_statuses()
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
        layout = self.layout()  # type: ignore[union-attr]
        if layout is not None:
            layout.addWidget(self.board)

    def _add_row(self, row: int, team: str, pool: PlayerPool) -> None:
        team_item = QTableWidgetItem(team)
        team_item.setFlags(Qt.ItemFlag.ItemIsEnabled)  # plain text, not editable
        self.table.setItem(row, 0, team_item)

        edit = QLineEdit()
        edit.setPlaceholderText("player name")
        edit.setCompleter(QCompleter(pool.names()))
        self.table.setCellWidget(row, 1, edit)

        spin = QSpinBox()
        spin.setRange(1, keepers_mod.MAX_COST_ROUND)
        spin.setValue(1)
        self.table.setCellWidget(row, 2, spin)

        check = QCheckBox()
        self.table.setCellWidget(row, 3, check)

        self.table.setItem(row, 4, QTableWidgetItem(""))
        self._rows.append(
            {"row": row, "team": team, "player": edit, "round": spin, "opted": check}
        )
        edit.textChanged.connect(lambda _text, r=row: self._row_changed(r))
        check.toggled.connect(lambda _on, r=row: self._row_changed(r))
        spin.valueChanged.connect(lambda _v, r=row: self._row_changed(r))

    def _apply_entry(self, entry: KeeperEntry) -> bool:
        """Place a saved keeper into an empty slot; False if no slot is free."""
        for row in self._rows:
            if row["team"] != entry.team:
                continue
            if row["player"].text():
                continue  # this team's slot is already filled
            row["player"].setText(entry.player)
            row["round"].setValue(entry.cost_round)
            row["opted"].setChecked(entry.opted_out)
            return True
        return False

    # -- status / resolution -----------------------------------------------------

    def _row_changed(self, row: int) -> None:
        self.update_statuses()

    def _entries_from_grid(self) -> list[KeeperEntry]:
        entries: list[KeeperEntry] = []
        for row in self._rows:
            player = row["player"].text().strip()
            if not player:
                continue  # empty rows are ignored on save
            entries.append(
                KeeperEntry(
                    team=row["team"],
                    player=player,
                    cost_round=row["round"].value(),
                    opted_out=row["opted"].isChecked(),
                )
            )
        return entries

    def _resolved(self, entries: list[KeeperEntry]) -> dict[str, str | None]:
        pool = PlayerPool.load(self.service.pool_path)
        return keepers_mod.resolve(entries, pool.names(), self.service.load_aliases())

    def update_statuses(self) -> None:
        """Recompute per-row Status + the unmatched/validate alert banner."""
        if not self.teams:
            return
        entries = self._entries_from_grid()
        if not entries:
            for row in self._rows:
                self.table.item(row["row"], 4).setText("")
            self._set_banner(self.alert_banner, "banner-alert", "")
            return
        report = bridge(
            [entry.player for entry in entries],
            PlayerPool.load(self.service.pool_path).names(),
            self.service.load_aliases(),
        )
        resolved = {name: report.matched.get(name) for name in {e.player for e in entries}}
        suggestions: dict[str, str] = {}
        for roster, candidates in report.unmatched:
            suggestions[roster] = candidates[0] if candidates else ""

        for row in self._rows:
            player = row["player"].text().strip()
            item = self.table.item(row["row"], 4)
            if not player:
                item.setText("")
                continue
            pool_name = resolved.get(player)
            if pool_name:
                item.setText(pool_name)
            else:
                suggestion = suggestions.get(player, "")
                item.setText(f"UNMATCHED (try {suggestion})" if suggestion else "UNMATCHED")
        self._update_alert(entries, resolved)

    def _update_alert(self, entries: list[KeeperEntry], resolved: dict) -> None:
        problems: list[str] = []
        errors = keepers_mod.validate(entries, self.teams, resolved)
        problems.extend(errors)
        unmatched = [
            entry.player for entry in entries if resolved.get(entry.player) is None
        ]
        if unmatched:
            problems.append(
                f"{len(unmatched)} keeper name(s) unmatched — fix spelling or "
                "add data/aliases.json entries"
            )
        if self._dropped_msg:
            problems.append(self._dropped_msg)
        self._set_banner(
            self.alert_banner, "banner-alert", "; ".join(problems)
        )

    @staticmethod
    def _set_banner(label: QLabel, object_name: str, text: str) -> None:
        if label.objectName() != object_name:
            label.setObjectName(object_name)
            label.style().unpolish(label)
            label.style().polish(label)
        label.setText(text)
        label.setVisible(bool(text))

    # -- save --------------------------------------------------------------------

    def _save(self) -> None:
        entries = self._entries_from_grid()
        resolved = self._resolved(entries)
        errors = keepers_mod.validate(entries, self.teams, resolved)
        if errors:
            self._set_banner(self.alert_banner, "banner-alert", "; ".join(errors))
            self._set_banner(self.status_banner, "banner", "Not saved — fix the errors above.")
            return
        keepers_mod.save(entries, self.keepers_path)
        self._set_banner(
            self.status_banner,
            "banner",
            f"Saved {len(entries)} keepers to keepers.json.",
        )
        self.update_statuses()


__all__ = ["DraftView"]
