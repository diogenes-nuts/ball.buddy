"""League view: sync status, teams, draft order, schedule (plan §6).

3-pane QSplitter; sync runs off the UI thread via a QThread worker that calls
headless :class:`SyncService`. All colors come from existing theme tokens
(``panel``/``banner``/``banner-alert``/tables). No emoji; sentence-case.
"""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ball_buddy.domain.league import LeagueConfig, snake_order
from ball_buddy.services.sync import SyncResult, SyncService
from ball_buddy.ui.views.pool_import import PoolImportDialog

DRAFT_ROUNDS = 14  # SPEC §1.1: 14-slot roster


class SyncWorker(QObject):
    """Runs :meth:`SyncService.run` on a worker thread; emits the result."""

    finished = Signal(object)  # SyncResult

    def __init__(self, service: SyncService) -> None:
        super().__init__()
        self._service = service

    def start_sync(self) -> None:
        try:
            result = self._service.run()
        except Exception as exc:  # never crash the thread, surface in banner
            result = SyncResult(error=f"unexpected sync error: {exc}")
        self.finished.emit(result)


class SettingsDialog(QDialog):
    """Enter/edit the Yahoo consumer key, secret, and league id (data/settings.json).

    The league id is the number in the Yahoo league URL
    (``.../nba/default/league/<id>``). All colors come from theme tokens;
    plain QLineEdit styling is left to the base stylesheet.
    """

    def __init__(self, service: SyncService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.service = service
        self.setWindowTitle("League settings")
        settings = service.settings()
        form = QFormLayout(self)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.league_id_edit = QLineEdit(str(settings.get("league_id", "")))
        self.league_id_edit.setPlaceholderText("from the Yahoo league URL")
        self.consumer_key_edit = QLineEdit(str(settings.get("consumer_key", "")))
        self.consumer_secret_edit = QLineEdit(str(settings.get("consumer_secret", "")))
        self.consumer_secret_edit.setEchoMode(QLineEdit.EchoMode.Password)
        note = QLabel(
            "Get the consumer key/secret from a Yahoo developer app "
            "(https://developer.yahoo.com/apps/). Stored in data/settings.json."
        )
        note.setObjectName("secondary")
        note.setWordWrap(True)
        form.addRow("League id:", self.league_id_edit)
        form.addRow("Consumer key:", self.consumer_key_edit)
        form.addRow("Consumer secret:", self.consumer_secret_edit)
        form.addRow(note)
        self.reset_button = QPushButton("Reset all data…")
        # No "danger" theme token exists; the ink-fill primary style is the
        # strongest available visual weight, so the destructive action reads
        # as the heaviest control in the dialog.
        self.reset_button.setProperty("ink", "true")
        self.reset_button.clicked.connect(self._reset)
        form.addRow(self.reset_button)
        self.reset_status = QLabel("")
        self.reset_status.setObjectName("secondary")
        form.addRow(self.reset_status)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _reset(self) -> None:
        """Wipe the whole data dir (login/tokens AND league data)."""
        answer = QMessageBox.question(
            self,
            "Reset all data",
            "This deletes ALL local data: your Yahoo login and saved tokens, "
            "league settings, imported player pool, snapshot, keepers, and draft "
            "picks. You will have to sign in to Yahoo and import the pool again.\n\n"
            "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.service.reset_all_data()
        self.reset_status.setText(
            "Reset complete — restart the app for a fully clean slate "
            "(the running app keeps its in-memory state)."
        )

    def _save(self) -> None:
        settings = self.service.settings()
        settings["version"] = 1
        settings["league_id"] = self.league_id_edit.text().strip()
        settings["consumer_key"] = self.consumer_key_edit.text().strip()
        settings["consumer_secret"] = self.consumer_secret_edit.text().strip()
        self.service.save_settings(settings)
        self.accept()


class LeagueView(QWidget):
    """League page: header actions + status banners + teams/draft/schedule."""

    def __init__(self, service: SyncService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.service = service
        self.snapshot: dict | None = None
        self.last_report = None
        self._thread: QThread | None = None
        self._worker: SyncWorker | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        # --- header row ------------------------------------------------------
        header = QHBoxLayout()
        self.league_label = QLabel("League")
        self.league_label.setObjectName("title")
        self.synced_label = QLabel("never synced")
        self.synced_label.setObjectName("secondary")
        header.addWidget(self.league_label)
        header.addWidget(self.synced_label, 1)

        self.sign_in_button = QPushButton("Sign in to Yahoo")
        self.sign_in_button.clicked.connect(self._sign_in)
        self.sync_button = QPushButton("Sync now")
        self.sync_button.setProperty("ink", "true")
        self.sync_button.clicked.connect(self._sync_now)
        self.import_button = QPushButton("Import pool")
        self.import_button.clicked.connect(self._import_pool)
        self.settings_button = QPushButton("Settings")
        self.settings_button.clicked.connect(self._edit_settings)
        for button in (
            self.sign_in_button,
            self.sync_button,
            self.import_button,
            self.settings_button,
        ):
            header.addWidget(button)
        root.addLayout(header)

        # --- status banners ---------------------------------------------------
        self.status_banner = QLabel("")
        self.status_banner.setObjectName("banner")
        self.status_banner.setWordWrap(True)
        root.addWidget(self.status_banner)
        self.unmatched_banner = QLabel("")
        self.unmatched_banner.setObjectName("banner-alert")
        self.unmatched_banner.setWordWrap(True)
        self.unmatched_banner.setVisible(False)
        root.addWidget(self.unmatched_banner)

        # --- 3-pane body ------------------------------------------------------
        self.splitter = QSplitter(self)
        self.splitter.addWidget(self._teams_pane())
        self.splitter.addWidget(self._draft_pane())
        self.splitter.addWidget(self._schedule_pane())
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 3)
        self.splitter.setStretchFactor(2, 2)
        root.addWidget(self.splitter, 1)

        last = service.load_last()
        self.apply_result(last)

    # -- panes -----------------------------------------------------------------

    def _panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("panel")
        return panel

    def _teams_pane(self) -> QWidget:
        panel = self._panel()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        title = QLabel("Teams")
        title.setObjectName("title")
        layout.addWidget(title)
        self.teams_table = QTableWidget(0, 4)
        self.teams_table.setHorizontalHeaderLabels(["Team", "Manager", "Roster", "IR"])
        self.teams_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.teams_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.teams_table.verticalHeader().setVisible(False)
        self.teams_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.teams_table)
        return panel

    def _draft_pane(self) -> QWidget:
        panel = self._panel()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        title = QLabel("Draft order")
        title.setObjectName("title")
        layout.addWidget(title)
        self.draft_table = QTableWidget(0, 4)
        self.draft_table.setHorizontalHeaderLabels(["Round", "Overall", "Team", "Status"])
        self.draft_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.draft_table.verticalHeader().setVisible(False)
        self.draft_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.draft_table, 1)

        self.order_note = QLabel("")
        self.order_note.setObjectName("secondary")
        self.order_note.setWordWrap(True)
        layout.addWidget(self.order_note)

        controls = QHBoxLayout()
        self.move_up_button = QPushButton("Move up")
        self.move_up_button.clicked.connect(lambda: self._move_selected(-1))
        self.move_down_button = QPushButton("Move down")
        self.move_down_button.clicked.connect(lambda: self._move_selected(1))
        self.save_order_button = QPushButton("Save order")
        self.save_order_button.setProperty("ink", "true")
        self.save_order_button.clicked.connect(self._save_manual_order)
        for button in (self.move_up_button, self.move_down_button, self.save_order_button):
            button.setEnabled(False)
            controls.addWidget(button)
        root = QHBoxLayout()
        root.addStretch(1)
        root.addLayout(controls)
        layout.addLayout(root)
        return panel

    def _schedule_pane(self) -> QWidget:
        panel = self._panel()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        title = QLabel("Schedule")
        title.setObjectName("title")
        layout.addWidget(title)
        self.schedule_table = QTableWidget(0, 3)
        self.schedule_table.setHorizontalHeaderLabels(["Week", "Opponent", "Status"])
        self.schedule_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.schedule_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.schedule_table.verticalHeader().setVisible(False)
        self.schedule_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.schedule_table, 1)
        self.schedule_empty = QLabel("No schedule yet (pre-draft).")
        self.schedule_empty.setObjectName("secondary")
        self.schedule_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.schedule_empty)
        return panel

    # -- rendering ---------------------------------------------------------------

    @staticmethod
    def _format_age(seconds: float | None) -> str:
        if seconds is None:
            return "never"
        minutes = int(seconds // 60)
        if minutes < 60:
            return f"{minutes}m ago"
        hours = minutes // 60
        if hours < 24:
            return f"{hours}h ago"
        return f"{hours // 24}d ago"

    def apply_result(self, result: SyncResult) -> None:
        """Update banners + all three panes from a SyncResult (any origin)."""
        self.last_report = result.report

        if result.snapshot is not None:
            self.snapshot = result.snapshot
            self.league_label.setText(result.snapshot.get("league", {}).get("name") or "League")
            self._render_tables()

        # status banner
        if result.needs_login:
            self._set_banner(self.status_banner, "banner", f"Sign in required: {result.error}")
        elif result.error:
            self._set_banner(self.status_banner, "banner", f"Sync failed: {result.error}")
        elif result.ok:
            self._set_banner(self.status_banner, "banner", "Synced just now.")
        else:
            stale = self._format_age(result.snapshot_age_seconds)
            self._set_banner(
                self.status_banner,
                "banner",
                f"Offline — showing last snapshot (synced {stale})."
                if result.snapshot is not None
                else "No snapshot yet — sign in and sync.",
            )

        synced_at = (result.snapshot or {}).get("updated_at", "")
        if synced_at:
            try:
                stamp = datetime.fromisoformat(synced_at).astimezone().strftime("%Y-%m-%d %H:%M")
            except ValueError:
                stamp = synced_at
            self.synced_label.setText(f"last synced {stamp}")

        # unmatched banner (loud, R3)
        report = result.report
        if report is not None and report.problem_count > 0:
            self.unmatched_banner.setText(report.banner_text())
            self.unmatched_banner.setVisible(True)
        else:
            self.unmatched_banner.setVisible(False)

        self.sign_in_button.setVisible(not self.service.logged_in)
        self._set_order_controls()

    @staticmethod
    def _set_banner(label: QLabel, object_name: str, text: str) -> None:
        if label.objectName() != object_name:
            label.setObjectName(object_name)
            # Re-polish so the new objectName's stylesheet rules apply.
            label.style().unpolish(label)
            label.style().polish(label)
        label.setText(text)
        label.setVisible(bool(text))

    def _render_tables(self) -> None:
        assert self.snapshot is not None
        teams = self.snapshot.get("teams", [])
        by_id = {team["team_id"]: team["name"] for team in teams}

        # Teams
        self.teams_table.setRowCount(len(teams))
        for i, team in enumerate(teams):
            players = team.get("players", [])
            ir = sum(1 for p in players if "IR" in (p.get("status") or ""))
            for col, value in enumerate(
                (team.get("name", ""), team.get("manager", ""), str(len(players)), str(ir))
            ):
                self.teams_table.setItem(i, col, QTableWidgetItem(value))

        # Draft order
        order = (self.snapshot.get("draft") or {}).get("order") or []
        team_names = [team["name"] for team in teams]
        if order:
            names_in_order = [by_id.get(k, k) for k in order]
        elif self.service.settings().get("manual_draft_order"):
            names_in_order = self._manual_order_for(team_names)
        else:
            names_in_order = team_names
        config = LeagueConfig(
            teams=tuple(names_in_order),
            start_order=tuple(names_in_order),
            rounds=DRAFT_ROUNDS,
            games_per_week=3.5,
            slots=(),
            categories=(),
            weights={},
            keepers=(),
        )
        picks = snake_order(config)
        self.draft_table.setRowCount(len(picks))
        for i, pick in enumerate(picks):
            for col, value in enumerate(
                (
                    str(pick.round),
                    str(pick.overall),
                    pick.team,
                    "FORFEITED" if pick.forfeited else "",
                )
            ):
                self.draft_table.setItem(i, col, QTableWidgetItem(value))
        self.order_note.setText(
            "No live draft order from Yahoo (pre-draft). Edit the start order with the "
            "up/down buttons, then Save order."
            if not order
            else f"Draft order source: {self.snapshot.get('source', 'live')}."
        )
        self._manual_order = names_in_order

        # Schedule (from the first team's perspective when possible)
        schedule = self.snapshot.get("schedule", [])
        first_team = teams[0]["team_id"] if teams else ""
        rows = [
            (
                str(entry["week"]),
                "BYE"
                if (entry.get("bye") or entry.get("team_b") == "")
                else by_id.get(
                    entry.get("team_b") or entry.get("team_a"),
                    entry.get("team_b") or entry.get("team_a") or "?",
                ),
                entry.get("status") or "",
            )
            for entry in schedule
            if first_team in (entry.get("team_a"), entry.get("team_b"))
            or entry.get("bye")
        ]
        self.schedule_table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for col, value in enumerate(row):
                self.schedule_table.setItem(i, col, QTableWidgetItem(value))
        has_schedule = len(rows) > 0
        self.schedule_table.setVisible(has_schedule)
        self.schedule_empty.setVisible(not has_schedule)

        self._set_order_controls()

    # -- manual draft order ---------------------------------------------------

    def _manual_order_for(self, team_names: list[str]) -> list[str]:
        """Apply the saved manual start order (team names) to the current roster.

        Names that no longer exist are dropped; new teams are appended in
        snapshot order so the table always covers every team exactly once.
        """
        saved = list(self.service.settings().get("manual_draft_order") or [])
        return [name for name in saved if name in team_names] + [
            name for name in team_names if name not in saved
        ]

    def _set_order_controls(self) -> None:
        """Order editing is enabled only when Yahoo gave no live order."""
        order = ((self.snapshot or {}).get("draft") or {}).get("order")
        editable = self.snapshot is not None and not order
        self.move_up_button.setEnabled(editable)
        self.move_down_button.setEnabled(editable)
        self.save_order_button.setEnabled(editable)
        mode = (
            QTableWidget.SelectionMode.SingleSelection
            if editable
            else QAbstractItemView.SelectionMode.NoSelection
        )
        self.draft_table.setSelectionMode(mode)

    def _move_selected(self, delta: int) -> None:
        row = self.draft_table.currentRow()
        if row < 0:
            return
        # start order = the first round (rows 0..n-1)
        if row >= DRAFT_ROUNDS or not hasattr(self, "_manual_order"):
            return
        target = row + delta
        if not 0 <= target < DRAFT_ROUNDS:
            return
        order = list(self._manual_order)
        order[row], order[target] = order[target], order[row]
        self._manual_order = order
        self._render_tables()

    def _save_manual_order(self) -> None:
        settings = self.service.settings()
        settings["manual_draft_order"] = list(getattr(self, "_manual_order", []))
        self.service.save_settings(settings)
        self.order_note.setText("Manual start order saved to settings.json.")

    # -- actions -----------------------------------------------------------------

    def _sign_in(self) -> None:
        """Fresh 3-legged OAuth (browser); the next sync picks up the token."""
        self.status_banner.setText(
            "Opening Yahoo sign-in; complete the browser flow, then press Sync now."
        )
        try:
            self.service._client = None  # force re-construction without saved token
            settings = self.service.settings()
            settings.pop("_tokens", None)
            from ball_buddy.io.yahoo import auth
            from ball_buddy.io.yahoo.client import LoginRequiredError, YahooClient

            try:
                client = YahooClient.from_settings(
                    settings, auth.load_tokens(self.service.data_dir)
                )
            except LoginRequiredError as exc:
                self._set_banner(self.status_banner, "banner", str(exc))
                return
            self.service._client = client
        except Exception as exc:
            self._set_banner(self.status_banner, "banner", f"Sign-in failed: {exc}")

    def _sync_now(self) -> None:
        self.sync_button.setEnabled(False)
        self.import_button.setEnabled(False)
        self.status_banner.setText("Syncing…")
        self._worker = SyncWorker(self.service)
        self._thread = QThread(self)
        self._worker.moveToThread(self._thread)
        self._worker.finished.connect(self._on_sync_done)
        self._worker.finished.connect(self._thread.quit)
        self._thread.started.connect(self._worker.start_sync)
        self._thread.start()

    def _on_sync_done(self, result: object) -> None:
        self.sync_button.setEnabled(True)
        self.import_button.setEnabled(True)
        self._thread.wait()
        self._thread = None
        self._worker = None
        if not isinstance(result, SyncResult):
            result = SyncResult(error="bad result")
        self.apply_result(result)

    def _import_pool(self) -> None:
        PoolImportDialog(self.service, self.snapshot, self).exec()
        # re-bridge after import (report changes with the new pool)
        self.apply_result(self.service.load_last())

    def _edit_settings(self) -> None:
        SettingsDialog(self.service, self).exec()

    # -- teardown -------------------------------------------------------------------

    def closeEvent(self, event) -> None:  # pragma: no cover - thread join on close
        if self._thread is not None and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(2000)
        super().closeEvent(event)


__all__ = ["LeagueView", "SyncWorker"]
