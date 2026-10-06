"""Lineups view (M5.2): per-player play toggles, lineup.optimize, 10 slots + sits.

Pick my team / opponent / week, toggle which roster players play (checked =
playing; pre-draft there is no Yahoo lineup state, so the toggles are manual),
then "Optimize" runs ``domain/lineup.optimize`` synchronously (deterministic
gap mode by default — ``mc_trials`` 0; C(14,10) is milliseconds, so no worker
thread, same call as M5.1). Renders the 10 starters in fixed SLOTS order with
a per-starter projected pts (``engine.project_roster`` on the 10 starter
rows), the 4 sitters with their rationale lines, and the 9-category outlook
vs the opponent (gaps + W/L/T + cat-win margin, optional seeded P(win)).

Roster source per team: resolved keeper entries + entered picks, looked up
in ``players.csv`` — the ``MatchupView._load_team_data`` name-resolution
core is a bound method (not importable), so the small core is deliberately
duplicated here as :func:`_team_roster_rows` (waivers precedent, no
matchup.py refactor in this slice). Unresolved names surface as banner
warnings, never a crash; an ``optimize`` ``ValueError`` (unfillable slot)
surfaces in the banner with the tables cleared. The 4 sitters include the
conditional IR slot — the IR choice stays manual (display only, no Yahoo
writes in v1).

All colors come from :mod:`ball_buddy.ui.theme` tokens (no raw hex).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ball_buddy.domain import engine
from ball_buddy.domain import keepers as keepers_mod
from ball_buddy.domain import lineup as lineup_mod
from ball_buddy.domain import picks as picks_mod
from ball_buddy.domain.keepers import KeeperEntry
from ball_buddy.domain.lineup import LineupResult
from ball_buddy.domain.players import PlayerPool
from ball_buddy.services.sync import SyncResult, SyncService
from ball_buddy.ui.views import _offline, _status
from ball_buddy.ui.views.matchup import CAT_LABELS

_BASE_NOTE = (
    "No lineups yet — toggle plays, then Optimize (deterministic gap mode; "
    "mc_trials > 0 adds a seeded P(win) display only)."
)
_DONE_NOTE = (
    "Lineup optimized — best 10 starters in slot order below (deterministic "
    "gap mode; mc_trials > 0 adds a seeded P(win) display only)."
)
_IR_NOTE = (
    "4 sitters include your conditional IR slot — choose the IR yourself "
    "(display only)."
)
_WEEK_NOTE = "Week is accepted but unused pre-draft (season projections compare)."


def _fmt_gap(cat: str, value: float) -> str:
    if cat in engine.COUNT_CATS:
        return f"{value:+.0f}"
    return f"{value:+.8f}"


def _team_roster_rows(
    service: SyncService, team_name: str
) -> tuple[list[dict[str, str]], list[str]]:
    """Pool rows (keepers + picks for ``team_name``, resolved, deduped, order
    kept) plus names that did not resolve into the pool (warnings, never a
    crash). Deliberate ~15-line duplicate of the ``MatchupView._load_team_data``
    name-resolution core — that one is a bound method, not importable.
    """
    pool = PlayerPool.load(service.pool_path)
    aliases = service.load_aliases()
    keepers = keepers_mod.load(service.data_dir / keepers_mod.KEEPERS_FILE)
    picks = picks_mod.load(service.data_dir / picks_mod.PICKS_FILE)
    if not team_name:
        return [], []
    names = [entry.player for entry in keepers if entry.team == team_name] + [
        pick.player for pick in picks if pick.team == team_name
    ]
    resolved = keepers_mod.resolve(
        [KeeperEntry(team=team_name, player=name, cost_round=1) for name in names],
        pool.names(),
        aliases,
    )
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    missing: list[str] = []
    for name in names:
        pool_name = resolved.get(name)
        if pool_name is None:
            if name not in missing:
                missing.append(name)
            continue
        if pool_name in seen:
            continue
        seen.add(pool_name)
        row = pool.get(pool_name)
        if row is not None:
            rows.append(row)
    return rows, missing


def _clear_table(table: QTableWidget) -> None:
    table.setRowCount(0)


class LineupView(QWidget):
    """Lineups page: pickers, play toggles, Optimize, starters/sits/cat tables."""

    def __init__(self, service: SyncService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.service = service
        self.snapshot: dict | None = None
        self.last_result: LineupResult | None = None
        self._rows_by_name: dict[str, dict[str, str]] = {}
        self._boxes: list[QCheckBox] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        self.offline_banner = QLabel("")
        self.offline_banner.setObjectName("banner-info")
        self.offline_banner.setWordWrap(True)
        self.offline_banner.setVisible(False)
        root.addWidget(self.offline_banner)

        # --- header ------------------------------------------------------------
        grid = QGridLayout()
        grid.setSpacing(8)

        self.title_label = QLabel("Lineups")
        self.title_label.setObjectName("title")
        grid.addWidget(self.title_label, 0, 0)

        self.team_combo = QComboBox()
        self.opp_combo = QComboBox()
        self.week_combo = QComboBox()

        grid.addWidget(QLabel("My team:"), 0, 1)
        grid.addWidget(self.team_combo, 0, 2)
        grid.addWidget(QLabel("Opponent:"), 0, 3)
        grid.addWidget(self.opp_combo, 0, 4)
        grid.addWidget(QLabel("Week:"), 0, 5)
        grid.addWidget(self.week_combo, 0, 6)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Seed:"))
        self.seed_spin = QSpinBox()
        self.seed_spin.setRange(0, 2**31 - 1)
        self.seed_spin.setValue(42)
        row2.addWidget(self.seed_spin)
        row2.addWidget(QLabel("MC trials:"))
        self.mc_spin = QSpinBox()
        self.mc_spin.setRange(0, 1_000_000)
        self.mc_spin.setValue(0)  # deterministic gap mode by default
        row2.addWidget(self.mc_spin)
        self.optimize_button = QPushButton("Optimize")
        self.optimize_button.setProperty("ink", "true")
        self.optimize_button.clicked.connect(self.optimize)
        row2.addWidget(self.optimize_button)
        row2.addStretch(1)
        grid.addLayout(row2, 1, 0, 1, 7)
        root.addLayout(grid)

        self.week_note = QLabel(_WEEK_NOTE)
        self.week_note.setObjectName("secondary")
        root.addWidget(self.week_note)

        # --- banner ------------------------------------------------------------
        self.banner = QLabel(_BASE_NOTE)
        self.banner.setObjectName("banner-info")
        self.banner.setWordWrap(True)
        root.addWidget(self.banner)

        # --- roster play toggles --------------------------------------------------
        self.roster_note = QLabel("Roster (checked = playing this week):")
        self.roster_note.setObjectName("secondary")
        root.addWidget(self.roster_note)
        self.roster_area = QScrollArea()
        self.roster_area.setWidgetResizable(True)
        self.roster_area.setFixedHeight(150)
        self.roster_widget = QWidget()
        self.roster_layout = QVBoxLayout(self.roster_widget)
        self.roster_layout.setContentsMargins(4, 4, 4, 4)
        self.roster_layout.setSpacing(2)
        self.roster_area.setWidget(self.roster_widget)
        root.addWidget(self.roster_area)

        # --- results ---------------------------------------------------------
        self.starters_table = QTableWidget(0, 3)
        self.starters_table.setHorizontalHeaderLabels(["Slot", "Player", "Pts"])
        self.starters_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.starters_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.starters_table.verticalHeader().setVisible(False)
        self.starters_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.starters_table.setFixedHeight(10 * 28 + 40)
        root.addWidget(self.starters_table)

        self.sits_table = QTableWidget(0, 2)
        self.sits_table.setHorizontalHeaderLabels(["Player", "Why"])
        self.sits_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.sits_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.sits_table.verticalHeader().setVisible(False)
        self.sits_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.sits_table.setFixedHeight(4 * 28 + 40)
        root.addWidget(self.sits_table)

        self.summary_label = QLabel("")
        self.summary_label.setObjectName("secondary")
        self.summary_label.setWordWrap(True)
        root.addWidget(self.summary_label)

        self.cat_table = QTableWidget(0, 3)
        self.cat_table.setHorizontalHeaderLabels(["Cat", "Gap", "W/L/T"])
        self.cat_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.cat_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.cat_table.verticalHeader().setVisible(False)
        self.cat_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.cat_table.setFixedHeight(9 * 28 + 40)
        root.addWidget(self.cat_table)

        self.ir_note = QLabel(_IR_NOTE)
        self.ir_note.setObjectName("secondary")
        self.ir_note.setWordWrap(True)
        root.addWidget(self.ir_note)

        self.team_combo.currentIndexChanged.connect(self._rebuild_roster)

        self.apply_result(service.load_last())
        _offline.apply_view_fallback(self, service, self.offline_banner)

    # -- data loading -----------------------------------------------------

    def apply_result(self, result: SyncResult) -> None:
        """(Re)load snapshot/teams from a SyncResult (any origin), like
        ``MatchupView.apply_result``."""
        if result.snapshot is not None:
            self.snapshot = result.snapshot
            _offline.hide_banner(self.offline_banner)
            self._refresh_combos()

    def _refresh_combos(self) -> None:
        assert self.snapshot is not None
        self.team_combo.blockSignals(True)
        self.opp_combo.blockSignals(True)
        self.week_combo.blockSignals(True)
        try:
            names = [team.get("name", "") for team in self.snapshot.get("teams", [])]
            self.team_combo.clear()
            self.team_combo.addItems(names)
            self.opp_combo.clear()
            self.opp_combo.addItems(names)
            if len(names) > 1:
                self.opp_combo.setCurrentIndex(1)
            weeks = sorted(
                {
                    str(entry["week"])
                    for entry in self.snapshot.get("schedule", [])
                    if entry.get("week") is not None
                }
            )
            self.week_combo.clear()
            self.week_combo.addItems(weeks or ["1"])
            if not weeks:
                self.week_note.setText(
                    "No schedule yet — assuming week 1; season projections compare."
                )
            else:
                self.week_note.setText(_WEEK_NOTE)
        finally:
            self.team_combo.blockSignals(False)
            self.opp_combo.blockSignals(False)
            self.week_combo.blockSignals(False)
        self._rebuild_roster()

    # -- roster toggles ------------------------------------------------------

    def _rebuild_roster(self) -> None:
        """One checked ``QCheckBox`` per resolved roster player (team change)."""
        for box in self._boxes:
            box.setParent(None)
            box.deleteLater()
        self._boxes = []
        if self.snapshot is None:
            return
        rows, _ = _team_roster_rows(self.service, self.team_combo.currentText())
        for row in rows:
            box = QCheckBox(row.get("name", ""))
            box.setChecked(True)  # default: everyone plays (noted by optimize)
            self._boxes.append(box)
            self.roster_layout.addWidget(box)

    def _playing(self) -> frozenset[str] | None:
        """Checked names, or None when everyone is checked (optimize default)."""
        if not self._boxes or all(box.isChecked() for box in self._boxes):
            return None
        return frozenset(box.text() for box in self._boxes if box.isChecked())

    # -- actions ---------------------------------------------------------------

    def optimize(self) -> None:
        """Run ``lineup.optimize`` synchronously and render the result."""
        team = self.team_combo.currentText()
        opp = self.opp_combo.currentText()
        if not team or not opp:
            self._clear_results()
            _status.set_status(self.banner, "info", "Pick a team and an opponent first.")
            return

        my_rows, my_missing = _team_roster_rows(self.service, team)
        opp_rows, opp_missing = _team_roster_rows(self.service, opp)
        notes: list[str] = []
        if my_missing:
            notes.append(f"{team}: not in pool: {', '.join(my_missing)} (skipped).")
        if opp_missing:
            notes.append(f"{opp}: not in pool: {', '.join(opp_missing)} (skipped).")
        if not my_rows or not opp_rows:
            self._clear_results()
            _status.set_status(
                self.banner,
                "info",
                "Empty roster: no keepers/picks resolved in the pool."
                + (("\n" + " ".join(notes)) if notes else ""),
            )
            return

        self._rows_by_name = {row.get("name", ""): row for row in my_rows}
        try:
            result = lineup_mod.optimize(
                my_rows,
                engine.project_roster(opp_rows, opp),
                name=team,
                playing=self._playing(),
                mc_trials=self.mc_spin.value(),
                seed=self.seed_spin.value(),
            )
        except ValueError as exc:
            self.last_result = None
            self._clear_results()
            _status.set_status(self.banner, "danger", str(exc))
            return

        self.last_result = result
        _status.set_status(
            self.banner,
            "success",
            _DONE_NOTE + (("\n" + " ".join(notes + result.notes)) if notes or result.notes else ""),
        )
        self._render(team, result)

    def _clear_results(self) -> None:
        self.last_result = None
        self._rows_by_name = {}
        _clear_table(self.starters_table)
        _clear_table(self.sits_table)
        _clear_table(self.cat_table)
        self.summary_label.setText("")

    def _render(self, team: str, result: LineupResult) -> None:
        # starters in SLOTS order; Pts = per-starter season projection
        starter_rows = [
            self._rows_by_name.get(name)
            for _, name in result.starters
            if self._rows_by_name.get(name) is not None
        ]
        starter_proj = engine.project_roster(starter_rows, team)
        self.starters_table.setRowCount(len(result.starters))
        for i, (slot, name) in enumerate(result.starters):
            pts = (
                starter_proj.players[i].values["pts"]
                if i < len(starter_proj.players)
                else 0.0
            )
            for col, text in enumerate((slot, name, f"{pts:.1f}")):
                item = QTableWidgetItem(text)
                if col == 2:  # Pts is a number
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                        )
                self.starters_table.setItem(i, col, item)

        # sitters from the optimizer + any toggled-off players (they never
        # enter the search, so they are absent from result.sits)
        starter_set = {name for _, name in result.starters}
        sit_rows = [(name, result.rationale.get(name, "")) for name in result.sits]
        for row in self._rows_by_name.values():
            name = row.get("name", "")
            if name and name not in starter_set and name not in result.sits:
                sit_rows.append((name, "not playing (toggled off)"))
        self.sits_table.setRowCount(len(sit_rows))
        for i, (name, why) in enumerate(sit_rows):
            for col, text in enumerate((name, why)):
                self.sits_table.setItem(i, col, QTableWidgetItem(text))

        outcomes = dict(zip(engine.CATS, result.cat_outcomes))
        self.cat_table.setRowCount(len(engine.CATS))
        for i, cat in enumerate(engine.CATS):
            texts = (CAT_LABELS[cat], _fmt_gap(cat, result.gaps[cat]),
                     outcomes[cat][0])
            for col, text in enumerate(texts):
                item = QTableWidgetItem(text)
                if col == 1:  # Gap is a number
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                        )
                self.cat_table.setItem(i, col, item)

        mine, theirs = result.cat_wins
        text = (
            f"{team}: {mine} vs {theirs} cats — margin {result.margin:+.2f}"
        )
        if result.p_win is not None:
            text += f"  |  P(win)={result.p_win:.4f} (seed {self.seed_spin.value()})"
        self.summary_label.setText(text)

    # -- test seams ---------------------------------------------------------------

    def pick_teams(self, team: str, opp: str) -> None:
        it = self.team_combo.findText(team)
        io = self.opp_combo.findText(opp)
        if it >= 0:
            self.team_combo.setCurrentIndex(it)
        if io >= 0:
            self.opp_combo.setCurrentIndex(io)

    def set_checked(self, name: str, checked: bool) -> None:
        """Toggle one roster player's play state (test seam for the toggles)."""
        for box in self._boxes:
            if box.text() == name:
                box.setChecked(checked)
                return


__all__ = ["LineupView"]
