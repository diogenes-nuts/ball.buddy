"""Trade view (M6.2): trade entry (I give / They give), analyze_trade,
per-side before/after category-gap tables, fairness verdict banner.

Pick my team / opponent, add players to each side of the deal from the
resolved roster combos (keepers + picks looked up in ``players.csv`` — the
the ``waivers`` module-level :func:`_team_roster_names` name-resolution core
is duplicated here verbatim, no import), then "Analyze" runs
``domain/trade.analyze_trade`` synchronously (default 200 trials, seeded —
seconds-scale, no worker thread, same call pattern as waivers/lineups).
Renders each side's 9-category gaps Before/After/Delta (deterministic
season-total gaps, each side's own perspective) plus the Delta-P(win)
summary line with the seed/trials used.

Deliberately NO week picker (unlike matchups/waivers/lineups):
``analyze_trade`` scores full rosters via ``engine.project_roster`` season
projections, so a week control would be dead UI — nothing would consume it.

Unresolved roster names surface as banner warnings (waivers pattern); an
``analyze_trade`` ``ValueError`` (e.g. both sides empty, give not on the
named roster) surfaces in the banner with the tables cleared.

All colors come from :mod:`ball_buddy.ui.theme` tokens (no raw hex).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ball_buddy.domain import engine
from ball_buddy.domain import keepers as keepers_mod
from ball_buddy.domain import picks as picks_mod
from ball_buddy.domain import trade as trade_mod
from ball_buddy.domain.engine import CATS
from ball_buddy.domain.keepers import KeeperEntry
from ball_buddy.domain.players import PlayerPool
from ball_buddy.domain.trade import Trade, TradeResult
from ball_buddy.services.sync import SyncResult, SyncService
from ball_buddy.ui.views import _offline, _status
from ball_buddy.ui.views.matchup import CAT_LABELS

_BASE_NOTE = "No trade entered — pick players above, then Analyze."
_PROJ_NOTE = (
    "Trade scoring uses season projections of full rosters (no week — "
    "analyze_trade is week-agnostic)."
)


def _fmt_gap(cat: str, value: float) -> str:
    if cat in engine.COUNT_CATS:
        return f"{value:+.0f}"
    return f"{value:+.8f}"


def _team_roster_names(
    service: SyncService, team_name: str
) -> tuple[list[str], list[str]]:
    """Resolved pool names (keepers + picks for ``team_name``, deduped, order
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
    out: list[str] = []
    missing: list[str] = []
    for name in names:
        pool_name = resolved.get(name)
        if pool_name is None:
            if name not in missing:
                missing.append(name)
        elif pool_name not in out:
            out.append(pool_name)
    return out, missing


class TradeView(QWidget):
    """Trades page: pickers, per-side give combos, Analyze, cat-gap tables."""

    def __init__(self, service: SyncService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.service = service
        self.snapshot: dict | None = None
        self.last_result: TradeResult | None = None
        self._my_gives: list[dict] = []
        self._their_gives: list[dict] = []

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

        self.title_label = QLabel("Trades")
        self.title_label.setObjectName("title")
        grid.addWidget(self.title_label, 0, 0)

        self.team_combo = QComboBox()
        self.opp_combo = QComboBox()

        grid.addWidget(QLabel("My team:"), 0, 1)
        grid.addWidget(self.team_combo, 0, 2)
        grid.addWidget(QLabel("Opponent:"), 0, 3)
        grid.addWidget(self.opp_combo, 0, 4)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Seed:"))
        self.seed_spin = QSpinBox()
        self.seed_spin.setRange(0, 2**31 - 1)
        self.seed_spin.setValue(42)
        row2.addWidget(self.seed_spin)
        row2.addWidget(QLabel("Trials:"))
        self.trials_spin = QSpinBox()
        self.trials_spin.setRange(1, 100_000)
        self.trials_spin.setValue(200)  # domain default
        row2.addWidget(self.trials_spin)
        self.analyze_button = QPushButton("Analyze")
        self.analyze_button.setProperty("ink", "true")  # primary-button pattern (waivers/lineups)
        self.analyze_button.clicked.connect(self.analyze)
        row2.addWidget(self.analyze_button)
        row2.addStretch(1)
        grid.addLayout(row2, 1, 0, 1, 5)
        root.addLayout(grid)

        self.note_label = QLabel(_PROJ_NOTE)
        self.note_label.setObjectName("secondary")
        root.addWidget(self.note_label)

        # --- trade entry ---------------------------------------------------------
        my_row = QHBoxLayout()
        my_row.addWidget(QLabel("I give:"))
        self.my_give_combo = QComboBox()
        my_row.addWidget(self.my_give_combo)
        my_add = QPushButton("Add")
        my_add.clicked.connect(
            lambda: self.add_give("my", self.my_give_combo.currentText())
        )
        my_row.addWidget(my_add)
        my_row.addStretch(1)
        root.addLayout(my_row)

        their_row = QHBoxLayout()
        their_row.addWidget(QLabel("They give:"))
        self.their_give_combo = QComboBox()
        their_row.addWidget(self.their_give_combo)
        their_add = QPushButton("Add")
        their_add.clicked.connect(
            lambda: self.add_give("their", self.their_give_combo.currentText())
        )
        their_row.addWidget(their_add)
        their_row.addStretch(1)
        root.addLayout(their_row)

        self.give_grid = QGridLayout()
        self.give_grid.setSpacing(4)
        root.addLayout(self.give_grid)

        # --- banner ------------------------------------------------------------
        self.banner = QLabel(_BASE_NOTE)
        self.banner.setObjectName("banner-info")
        self.banner.setWordWrap(True)
        root.addWidget(self.banner)

        self.summary_label = QLabel("")
        self.summary_label.setObjectName("secondary")
        self.summary_label.setWordWrap(True)
        root.addWidget(self.summary_label)

        self.my_table = QTableWidget(0, 4)
        self.my_table.setHorizontalHeaderLabels(["Cat", "Before", "After", "Delta"])
        self.my_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.my_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.my_table.verticalHeader().setVisible(False)
        self.my_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.my_table.setFixedHeight(9 * 28 + 40)
        root.addWidget(self.my_table)

        self.their_table = QTableWidget(0, 4)
        self.their_table.setHorizontalHeaderLabels(
            ["Cat", "Before", "After", "Delta"]
        )
        self.their_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.their_table.setSelectionMode(
            QAbstractItemView.SelectionMode.NoSelection
        )
        self.their_table.verticalHeader().setVisible(False)
        self.their_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.their_table.setFixedHeight(9 * 28 + 40)
        root.addWidget(self.their_table)

        self.team_combo.currentIndexChanged.connect(self._rebuild_give_combos)
        self.opp_combo.currentIndexChanged.connect(self._rebuild_give_combos)

        self.apply_result(service.load_last())
        _offline.apply_view_fallback(self, service, self.offline_banner)

    # -- data loading -----------------------------------------------------

    def apply_result(self, result: SyncResult) -> None:
        """(Re)load snapshot/teams from a SyncResult (any origin), like
        ``WaiverView.apply_result``."""
        if result.snapshot is not None:
            self.snapshot = result.snapshot
            _offline.hide_banner(self.offline_banner)
            self._refresh_combos()

    def _refresh_combos(self) -> None:
        assert self.snapshot is not None
        self.team_combo.blockSignals(True)
        self.opp_combo.blockSignals(True)
        try:
            names = [team.get("name", "") for team in self.snapshot.get("teams", [])]
            self.team_combo.clear()
            self.team_combo.addItems(names)
            self.opp_combo.clear()
            self.opp_combo.addItems(names)
            if len(names) > 1:
                self.opp_combo.setCurrentIndex(1)
        finally:
            self.team_combo.blockSignals(False)
            self.opp_combo.blockSignals(False)
        self._rebuild_give_combos()

    # -- give entry ----------------------------------------------------------

    def _rebuild_give_combos(self) -> None:
        """Refill the give combos for the current teams; selected gives are
        cleared — a stale give would otherwise raise from the domain (loud,
        but pointless once the roster changed under it)."""
        self._clear_gives()
        if self.snapshot is None:
            my_names: list[str] = []
            opp_names: list[str] = []
        else:
            my_names, _ = _team_roster_names(self.service, self.team_combo.currentText())
            opp_names, _ = _team_roster_names(
                self.service, self.opp_combo.currentText()
            )
        self.my_give_combo.blockSignals(True)
        self.their_give_combo.blockSignals(True)
        try:
            self.my_give_combo.clear()
            self.my_give_combo.addItems(my_names)
            self.their_give_combo.clear()
            self.their_give_combo.addItems(opp_names)
        finally:
            self.my_give_combo.blockSignals(False)
            self.their_give_combo.blockSignals(False)
        self._rebuild_give_grid()

    def _clear_gives(self) -> None:
        for gives in (self._my_gives, self._their_gives):
            for give in gives:
                give["label"].setParent(None)
                give["label"].deleteLater()
                give["remove"].setParent(None)
                give["remove"].deleteLater()
            gives.clear()
        self._rebuild_give_grid()

    def add_give(self, side: str, name: str) -> dict | None:
        """Add one give on ``side`` ("my"/"their") (test seam doubles as the
        Add-button callback). Empty names are ignored, not an error."""
        if not name:
            return None
        give = {"label": QLabel(name), "remove": QPushButton("Remove")}
        give["remove"].clicked.connect(
            lambda _checked, g=give: self.remove_give(side, g)
        )
        (self._my_gives if side == "my" else self._their_gives).append(give)
        self._rebuild_give_grid()
        return give

    def remove_give(self, side: str, give: dict) -> None:
        gives = self._my_gives if side == "my" else self._their_gives
        if give in gives:
            gives.remove(give)
        give["label"].setParent(None)
        give["label"].deleteLater()
        give["remove"].setParent(None)
        give["remove"].deleteLater()
        self._rebuild_give_grid()

    def _rebuild_give_grid(self) -> None:
        """Grid: header (I give / They give), then one row per give — two name
        labels + Remove buttons (waivers _add_row/_remove_row pattern).
        Rebuilt from scratch (QLayout has no clear()). Only widgets that no
        longer belong to a live give are deleteLater()'d — the still-live
        give labels/buttons are re-added below, and deleteLater() on a
        re-added widget destroys it once the event loop runs (RuntimeError
        on the next Remove/Analyze)."""
        live = {
            w
            for gives in (self._my_gives, self._their_gives)
            for give in gives
            for w in (give["label"], give["remove"])
        }
        while self.give_grid.count():
            item = self.give_grid.takeAt(0)
            layout = item.layout()
            if layout is not None:
                del layout
            elif item.widget() is not None:
                if item.widget() not in live:
                    item.widget().deleteLater()
        self.give_grid.addWidget(QLabel("I give"), 0, 0)
        self.give_grid.addWidget(QLabel("They give"), 0, 2)
        rows = max(len(self._my_gives), len(self._their_gives))
        for i in range(rows):
            if i < len(self._my_gives):
                self.give_grid.addWidget(self._my_gives[i]["label"], i + 1, 0)
                self.give_grid.addWidget(self._my_gives[i]["remove"], i + 1, 1)
            if i < len(self._their_gives):
                self.give_grid.addWidget(self._their_gives[i]["label"], i + 1, 2)
                self.give_grid.addWidget(self._their_gives[i]["remove"], i + 1, 3)

    # -- actions ---------------------------------------------------------------

    def analyze(self) -> None:
        """Run ``trade.analyze_trade`` synchronously and render the result."""
        team = self.team_combo.currentText()
        opp = self.opp_combo.currentText()
        if self.snapshot is None or not team or not opp:
            self._clear_results()
            _status.set_status(self.banner, "info", "Pick a team and an opponent first.")
            return

        my_names, my_missing = _team_roster_names(self.service, team)
        opp_names, opp_missing = _team_roster_names(self.service, opp)
        notes: list[str] = []
        if my_missing:
            notes.append(f"{team}: not in pool: {', '.join(my_missing)} (skipped).")
        if opp_missing:
            notes.append(f"{opp}: not in pool: {', '.join(opp_missing)} (skipped).")
        if not my_names or not opp_names:
            self._clear_results()
            _status.set_status(
                self.banner,
                "info",
                "Empty roster: no keepers/picks resolved in the pool."
                + (("\n" + " ".join(notes)) if notes else ""),
            )
            return

        trade = Trade(
            tuple(give["label"].text() for give in self._my_gives),
            tuple(give["label"].text() for give in self._their_gives),
        )
        try:
            result = trade_mod.analyze_trade(
                trade,
                my_names,
                opp_names,
                PlayerPool.load(self.service.pool_path),
                trials=self.trials_spin.value(),
                seed=self.seed_spin.value(),
            )
        except ValueError as exc:
            self.last_result = None
            self._clear_results()
            _status.set_status(self.banner, "danger", str(exc))
            return

        self.last_result = result
        _status.set_status(
            self.banner, "success", result.summary + (("\n" + " ".join(notes)) if notes else "")
        )
        self._render(result)

    def _clear_results(self) -> None:
        self.last_result = None
        self.my_table.setRowCount(0)
        self.their_table.setRowCount(0)
        self.summary_label.setText("")

    def _render(self, result: TradeResult) -> None:
        for table, before, after in (
            (self.my_table, result.my_gaps_before, result.my_gaps_after),
            (self.their_table, result.their_gaps_before, result.their_gaps_after),
        ):
            table.setRowCount(len(CATS))
            for i, cat in enumerate(CATS):
                b = before[cat]
                a = after[cat]
                for col, text in enumerate(
                    (CAT_LABELS[cat], _fmt_gap(cat, b), _fmt_gap(cat, a),
                     _fmt_gap(cat, a - b))
                ):
                    item = QTableWidgetItem(text)
                    if col > 0:  # Before/After/Delta are numbers
                        item.setTextAlignment(
                            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                            )
                    table.setItem(i, col, item)

        self.summary_label.setText(
            f"you: {result.my_baseline_p:.4f} -> "
            f"{result.my_baseline_p + result.my_delta_p:.4f}   "
            f"them: {result.their_baseline_p:.4f} -> "
            f"{result.their_baseline_p + result.their_delta_p:.4f}   "
            f"(seed {self.seed_spin.value()}, {self.trials_spin.value()} trials)"
        )

    # -- test seams ---------------------------------------------------------------

    def pick_teams(self, team: str, opp: str) -> None:
        it = self.team_combo.findText(team)
        io = self.opp_combo.findText(opp)
        if it >= 0:
            self.team_combo.setCurrentIndex(it)
        if io >= 0:
            self.opp_combo.setCurrentIndex(io)


__all__ = ["TradeView"]
