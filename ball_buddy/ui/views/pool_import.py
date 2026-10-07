"""In-app Hashtag pool import dialog (salvaged importer, plan §4).

Flow: pick a saved Hashtag import-v4 HTML page -> ``parse_file`` -> show
warnings -> ``write_csv(data/players.csv)`` -> rebuild the pool -> run the
name bridge against the current snapshot rosters -> show matched /
ambiguous / unmatched tables. All colors from existing theme tokens.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ball_buddy.domain.naming import MatchReport, bridge
from ball_buddy.domain.players import PlayerPool
from ball_buddy.io.pool import inbox
from ball_buddy.io.pool.importer import ImportError, parse_file, validate_rows, write_csv
from ball_buddy.services.sync import SyncService


class PoolImportDialog(QWidget):
    """Modal import flow; parent it on the main window for centering."""

    def __init__(
        self, service: SyncService, snapshot: dict | None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.snapshot = snapshot
        self.last_report: MatchReport | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        header = QLabel("Import player pool (Hashtag export)")
        header.setObjectName("title")
        layout.addWidget(header)

        pick_row = QHBoxLayout()
        self.file_label = QLabel("No file selected.")
        self.file_label.setObjectName("secondary")
        pick_row.addWidget(self.file_label, 1)
        self.pick_button = QPushButton("Choose file")
        self.pick_button.clicked.connect(self._pick_file)
        pick_row.addWidget(self.pick_button)
        layout.addLayout(pick_row)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        self.warnings_label = QLabel("")
        self.warnings_label.setObjectName("secondary")
        self.warnings_label.setWordWrap(True)
        layout.addWidget(self.warnings_label)

        self.tables = QGridLayout()
        self.matched_table = self._table(("Roster name", "Pool name"))
        self.ambiguous_table = self._table(("Roster name", "Pool candidates"))
        self.unmatched_table = self._table(("Roster name", "Suggested pool names"))
        self.tables.addWidget(QLabel("Matched"), 0, 0)
        self.tables.addWidget(self.matched_table, 0, 1)
        self.tables.addWidget(QLabel("Ambiguous (add an alias)"), 1, 0)
        self.tables.addWidget(self.ambiguous_table, 1, 1)
        self.tables.addWidget(QLabel("Unmatched"), 2, 0)
        self.tables.addWidget(self.unmatched_table, 2, 1)
        layout.addLayout(self.tables, 1)

    def _table(self, headers: tuple[str, ...]) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(list(headers))
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        table.verticalHeader().setVisible(False)
        return table

    def _pick_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Hashtag export", "", "HTML (*.html)")
        if path:
            self.import_html(path)

    def _fill_table(self, table: QTableWidget, rows: list[tuple[str, str]]) -> None:
        table.setRowCount(len(rows))
        for i, (left, right) in enumerate(rows):
            table.setItem(i, 0, QTableWidgetItem(left))
            table.setItem(i, 1, QTableWidgetItem(right))

    def _roster_names(self) -> list[str]:
        names: list[str] = []
        for team in (self.snapshot or {}).get("teams", []):
            names.extend(p["name"] for p in team.get("players", []) if p.get("name"))
        return names

    def import_html(self, path: str | Path) -> MatchReport | None:
        """Parse, validate, persist, and bridge. Returns the report or None."""
        try:
            parsed = parse_file(path)
        except ImportError as exc:
            self.status_label.setText(f"Import failed: {exc}")
            return None

        warnings = list(parsed.warnings) + validate_rows(parsed.rows)
        self.file_label.setText(Path(path).name)
        if warnings:
            shown = "; ".join(warnings[:8])
            self.warnings_label.setText(
                f"{len(warnings)} warning(s): {shown}"
                + (" …" if len(warnings) > 8 else "")
            )
        else:
            self.warnings_label.setText("No warnings.")

        written = write_csv(parsed.rows, self.service.pool_path)
        if inbox.in_inbox(self.service.data_dir, Path(path)):
            # Dedupe: an inbox file imported manually is already current,
            # so a later scan reports it unchanged instead of re-importing.
            inbox.record_import(self.service.data_dir, Path(path), players=written)
        pool = PlayerPool.load(self.service.pool_path)
        report = bridge(self._roster_names(), pool.names(), self.service.load_aliases())
        self.last_report = report

        self.status_label.setText(
            f"{written} pool players written; {len(report.matched)} matched, "
            f"{len(report.ambiguous)} ambiguous, {len(report.unmatched)} unmatched."
        )
        self._fill_table(self.matched_table, sorted(report.matched.items()))
        ambiguous_rows = [
            (name, " / ".join(candidates))
            for name, candidates in sorted(report.ambiguous.items())
        ]
        self._fill_table(self.ambiguous_table, ambiguous_rows)
        unmatched_rows = [
            (name, " / ".join(suggestions) if suggestions else "(none)")
            for name, suggestions in report.unmatched
        ]
        self._fill_table(self.unmatched_table, unmatched_rows)
        return report


__all__ = ["PoolImportDialog"]
