"""Setup dialog (P1, 006_board): draft order, team names, keepers, MY team.

Edits the same stores the draft board already reads, so ``board.py`` works
unchanged: ``settings["manual_teams"]`` / ``settings["manual_draft_order"]``
/ ``settings["my_team"]`` (data/settings.json) and data/keepers.json. Team
row order IS the draft start order (manual mode keeps ``draft.order`` empty,
so the board falls back to ``manual_draft_order``; with a live Yahoo order
the edit only affects the fallback). ``keepers_mod.validate`` errors block
Save; empty and duplicate team names also block Save (the board indexes
picks by team name). Unmatched/ambiguous player names are flagged in the
Status column (with "try ..." suggestions) but still saved. All colors come
from existing theme tokens (``panel``/``banner-danger``/tables). No emoji;
sentence-case labels.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QCompleter,
    QDialog,
    QDialogButtonBox,
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
from ball_buddy.domain import naming
from ball_buddy.domain.keepers import KeeperEntry
from ball_buddy.domain.players import PlayerPool
from ball_buddy.services.sync import SyncService

KEEPER_COLUMNS = ("Team", "Player", "Cost round", "Opt out", "Status")


class SetupDialog(QDialog):
    """Edit the draft start order, team names, keepers, and MY team."""

    def __init__(self, service: SyncService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.service = service
        self.setWindowTitle("Setup — draft order, teams, keepers")
        self.setMinimumWidth(560)

        settings = service.settings()
        teams = list(settings.get("manual_teams") or [])
        if not teams:
            # live mode: no manual list yet — seed from the effective snapshot
            snapshot = service.effective_snapshot()
            if snapshot:
                teams = [t["name"] for t in snapshot.get("teams", [])]
        my_team = settings.get("my_team", "")
        self._load_error = ""
        keepers: list[KeeperEntry] = []
        try:
            keepers = keepers_mod.load(service.data_dir / keepers_mod.KEEPERS_FILE)
        except Exception as exc:  # corrupt keepers.json: refuse to overwrite
            self._load_error = f"keepers.json: {exc} — fix or delete it before saving."
        self._pool = PlayerPool.load(service.pool_path)

        root = QVBoxLayout(self)
        root.setSpacing(8)

        self.alert_banner = QLabel("")
        self.alert_banner.setObjectName("banner-danger")
        self.alert_banner.setWordWrap(True)
        self.alert_banner.setVisible(False)
        root.addWidget(self.alert_banner)

        # --- teams & draft order --------------------------------------------
        teams_panel = QWidget()
        teams_panel.setObjectName("panel")
        root.addWidget(teams_panel)
        teams_inner = QVBoxLayout(teams_panel)
        teams_inner.setContentsMargins(8, 8, 8, 8)
        teams_inner.setSpacing(4)
        teams_title = QLabel("Teams & draft order")
        teams_title.setObjectName("title")
        teams_inner.addWidget(teams_title)
        teams_note = QLabel(
            "Row order is the draft start order. Check the box to mark your "
            "own team."
        )
        teams_note.setObjectName("secondary")
        teams_note.setWordWrap(True)
        teams_inner.addWidget(teams_note)
        self.teams_table = QTableWidget(0, 2)
        self.teams_table.setHorizontalHeaderLabels(["Team", "My team"])
        self.teams_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.teams_table.verticalHeader().setVisible(False)
        self.teams_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        teams_inner.addWidget(self.teams_table, 1)
        for name in teams:
            self._add_team_row(name, name == my_team)
        team_buttons = QVBoxLayout()
        team_buttons.setSpacing(4)
        self.add_team_button = QPushButton("Add team")
        self.add_team_button.clicked.connect(lambda: self._add_team_row("", False))
        self.remove_team_button = QPushButton("Remove selected")
        self.remove_team_button.clicked.connect(self._remove_team_row)
        self.move_up_button = QPushButton("Move up")
        self.move_up_button.clicked.connect(lambda: self._move_team_row(-1))
        self.move_down_button = QPushButton("Move down")
        self.move_down_button.clicked.connect(lambda: self._move_team_row(1))
        for button in (
            self.add_team_button,
            self.remove_team_button,
            self.move_up_button,
            self.move_down_button,
        ):
            team_buttons.addWidget(button)
        teams_inner.addLayout(team_buttons)

        # --- keepers ----------------------------------------------------------
        keepers_panel = QWidget()
        keepers_panel.setObjectName("panel")
        root.addWidget(keepers_panel)
        keepers_inner = QVBoxLayout(keepers_panel)
        keepers_inner.setContentsMargins(8, 8, 8, 8)
        keepers_inner.setSpacing(4)
        keepers_title = QLabel("Keepers")
        keepers_title.setObjectName("title")
        keepers_inner.addWidget(keepers_title)
        keepers_note = QLabel(
            "Up to 2 per team; cost round is the draft round the keeper "
            "consumes (1-13). Opt-out: the player stays but costs no pick. "
            "Unmatched names are flagged but still saved."
        )
        keepers_note.setObjectName("secondary")
        keepers_note.setWordWrap(True)
        keepers_inner.addWidget(keepers_note)
        self.keepers_table = QTableWidget(0, len(KEEPER_COLUMNS))
        self.keepers_table.setHorizontalHeaderLabels(KEEPER_COLUMNS)
        self.keepers_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.keepers_table.verticalHeader().setVisible(False)
        self.keepers_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        keepers_inner.addWidget(self.keepers_table, 1)
        for entry in keepers:
            self._add_keeper_row(entry)
        self._update_statuses()
        keeper_buttons = QVBoxLayout()
        keeper_buttons.setSpacing(4)
        self.add_keeper_button = QPushButton("Add keeper")
        self.add_keeper_button.clicked.connect(
            lambda: self._add_keeper_row(None)
        )
        self.remove_keeper_button = QPushButton("Remove selected")
        self.remove_keeper_button.clicked.connect(self._remove_keeper_row)
        for button in (self.add_keeper_button, self.remove_keeper_button):
            keeper_buttons.addWidget(button)
        keepers_inner.addLayout(keeper_buttons)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        if self._load_error:
            self._set_alert(self._load_error)

    # -- teams table -------------------------------------------------------------

    def _add_team_row(self, name: str, is_my: bool) -> int:
        row = self.teams_table.rowCount()
        self.teams_table.insertRow(row)
        self.teams_table.setItem(row, 0, QTableWidgetItem(name))
        check = QCheckBox()
        check.setChecked(is_my)
        self.teams_table.setCellWidget(row, 1, check)
        return row

    def _remove_team_row(self) -> None:
        row = self.teams_table.currentRow()
        if row < 0 and self.teams_table.rowCount() > 0:
            row = self.teams_table.rowCount() - 1
        if row >= 0:
            self.teams_table.removeRow(row)

    def _move_team_row(self, delta: int) -> None:
        row = self.teams_table.currentRow()
        target = row + delta
        if row < 0 or not (0 <= target < self.teams_table.rowCount()):
            return
        a_name = self.teams_table.item(row, 0).text()
        b_name = self.teams_table.item(target, 0).text()
        a_check = self.teams_table.cellWidget(row, 1)
        b_check = self.teams_table.cellWidget(target, 1)
        # swap both the text items and the checkbox cell widgets
        self.teams_table.setItem(row, 0, QTableWidgetItem(b_name))
        self.teams_table.setItem(target, 0, QTableWidgetItem(a_name))
        self.teams_table.setCellWidget(row, 1, None)
        self.teams_table.setCellWidget(target, 1, None)
        self.teams_table.setCellWidget(row, 1, b_check)
        self.teams_table.setCellWidget(target, 1, a_check)
        self.teams_table.setCurrentCell(target, 0)

    # -- keepers table -------------------------------------------------------------

    def _add_keeper_row(self, entry: KeeperEntry | None) -> None:
        row = self.keepers_table.rowCount()
        self.keepers_table.insertRow(row)

        combo = QComboBox()
        combo.addItems(self._team_names())
        if entry is not None and entry.team in self._team_names():
            combo.setCurrentText(entry.team)
        self.keepers_table.setCellWidget(row, 0, combo)

        edit = QLineEdit()
        edit.setPlaceholderText("player name")
        edit.setCompleter(QCompleter(self._pool.names()))
        edit.setText(entry.player if entry is not None else "")
        self.keepers_table.setCellWidget(row, 1, edit)

        spin = QSpinBox()
        spin.setRange(1, keepers_mod.MAX_COST_ROUND)
        spin.setValue(entry.cost_round if entry is not None else 1)
        self.keepers_table.setCellWidget(row, 2, spin)

        check = QCheckBox()
        check.setChecked(entry.opted_out if entry is not None else False)
        self.keepers_table.setCellWidget(row, 3, check)

        self.keepers_table.setItem(row, 4, QTableWidgetItem(""))
        edit.textChanged.connect(lambda _text: self._update_statuses())

    def _remove_keeper_row(self) -> None:
        row = self.keepers_table.currentRow()
        if row < 0 and self.keepers_table.rowCount() > 0:
            row = self.keepers_table.rowCount() - 1
        if row >= 0:
            self.keepers_table.removeRow(row)

    def _team_names(self) -> list[str]:
        return [
            self.teams_table.item(row, 0).text().strip()
            for row in range(self.teams_table.rowCount())
            if self.teams_table.item(row, 0).text().strip()
        ]

    def _keeper_entries(self) -> list[KeeperEntry]:
        entries: list[KeeperEntry] = []
        for row in range(self.keepers_table.rowCount()):
            edit = self.keepers_table.cellWidget(row, 1)
            player = edit.text().strip() if isinstance(edit, QLineEdit) else ""
            if not player:
                continue  # empty rows are ignored on save
            combo = self.keepers_table.cellWidget(row, 0)
            spin = self.keepers_table.cellWidget(row, 2)
            check = self.keepers_table.cellWidget(row, 3)
            entries.append(
                KeeperEntry(
                    team=combo.currentText(),
                    player=player,
                    cost_round=spin.value(),
                    opted_out=check.isChecked(),
                )
            )
        return entries

    def _update_statuses(self) -> None:
        """Per-row Status: resolved pool name, "ambiguous: ...", or
        "UNMATCHED — try <suggestions>" (flagged, never blocked)."""
        entries = self._keeper_entries()
        report = (
            naming.bridge(
                [entry.player for entry in entries],
                self._pool.names(),
                self.service.load_aliases(),
            )
            if entries
            else None
        )
        unmatched_suggestions = dict(report.unmatched) if report else {}
        for row in range(self.keepers_table.rowCount()):
            item = self.keepers_table.item(row, 4)
            if item is None:
                continue
            edit = self.keepers_table.cellWidget(row, 1)
            player = edit.text().strip() if isinstance(edit, QLineEdit) else ""
            if not player:
                item.setText("")
                continue
            if not report:
                continue
            if player in report.matched:
                item.setText(report.matched[player])
            elif player in report.ambiguous:
                item.setText("ambiguous: " + ", ".join(report.ambiguous[player]))
            else:
                suggestions = unmatched_suggestions.get(player, [])
                item.setText(
                    "UNMATCHED — try " + ", ".join(suggestions)
                    if suggestions
                    else "UNMATCHED"
                )

    # -- save ------------------------------------------------------------------------

    def _set_alert(self, text: str) -> None:
        self.alert_banner.setText(text)
        self.alert_banner.setVisible(bool(text))

    def _save(self) -> None:
        if self._load_error:
            self._set_alert(self._load_error)
            return
        ordered_names = self._team_names()
        if not ordered_names:
            self._set_alert("Add at least one team.")
            return
        if any(not row.text().strip() for row in self._iter_team_items()):
            self._set_alert("Some team rows are empty — enter a name or remove them.")
            return
        seen: set[str] = set()
        duplicates = [name for name in ordered_names if name in seen or seen.add(name)]
        if duplicates:
            self._set_alert(
                "Duplicate team names: "
                + ", ".join(sorted(duplicates))
                + " — rename them before saving."
            )
            return
        my_team = ""
        for row in range(self.teams_table.rowCount()):
            check = self.teams_table.cellWidget(row, 1)
            if isinstance(check, QCheckBox) and check.isChecked():
                my_team = self.teams_table.item(row, 0).text().strip()
                break
        entries = self._keeper_entries()
        resolved = keepers_mod.resolve(
            entries, self._pool.names(), self.service.load_aliases()
        )
        errors = keepers_mod.validate(entries, ordered_names, resolved)
        if errors:
            self._set_alert("; ".join(errors))
            return  # no accept, nothing persisted
        settings = self.service.settings()
        settings["manual_teams"] = ordered_names
        settings["manual_draft_order"] = ordered_names
        settings["my_team"] = my_team
        self.service.save_settings(settings)
        keepers_mod.save(entries, self.service.data_dir / keepers_mod.KEEPERS_FILE)
        self._set_alert("")
        self.accept()

    def _iter_team_items(self):
        for row in range(self.teams_table.rowCount()):
            yield self.teams_table.item(row, 0)


__all__ = ["SetupDialog"]
