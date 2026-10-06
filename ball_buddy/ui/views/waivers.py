"""Waivers view (M4.2): manual candidate entry, FAAB budget, ranked Delta P(win).

Pre-draft there is no Yahoo waiver order yet, so candidates are entered
manually (name + FAAB cost). "Rank" reuses ``domain/waiver.rank_candidates``
unchanged (trials=200 default — seconds-scale at pre-draft roster sizes, so
it runs synchronously like "Run Monte-Carlo" in the matchup view).

Baseline roster source chain (per picked team): ``keepers.json`` +
``draft_picks.json`` entries for that team -> ``keepers_mod.resolve(...)``
against ``pool.names()`` with ``aliases.json`` -> resolved pool (display)
names, which ``rank_candidates`` resolves to pool rows internally.
``MatchupView._load_team_data`` is a bound method (not importable), so the
small name-resolution core is deliberately duplicated here as
:func:`_team_roster_names` (no matchup.py refactor in this slice).
Unresolved roster/opponent names surface as banner warnings, never a crash;
unresolved *candidate* names raise ``ValueError`` from ``rank_candidates``
and are shown in the banner with the results table cleared.

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
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ball_buddy.domain import keepers as keepers_mod
from ball_buddy.domain import picks as picks_mod
from ball_buddy.domain.engine import PCT_CATS
from ball_buddy.domain.keepers import KeeperEntry
from ball_buddy.domain.players import PlayerPool
from ball_buddy.domain.waiver import WaiverCandidate, rank_candidates
from ball_buddy.services.sync import SyncResult, SyncService
from ball_buddy.ui.views import _offline, _status
from ball_buddy.ui.views.matchup import CAT_LABELS

_RESULT_NOTE = (
    "No lineups yet — projecting full rosters from keepers + drafted picks."
)
_ENTRY_NOTE = "Pre-draft: candidates are entered manually — no Yahoo waiver order yet."
_COLUMNS = (
    "Rank", "Candidate", "ΔP(win)", "Best drop",
    "Top-2 cat Δ", "Cost", "Over budget", "Rationale",
)


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


def _top2_cat_delta(cat_delta: dict[str, float]) -> str:
    """Top 2 direction-adjusted cat deltas (``to`` negated), e.g.
    ``"PTS +5 / TO +1"`` — positive always reads as "improves"."""
    scored = sorted(
        (cat, value * (-1.0 if cat == "to" else 1.0))
        for cat, value in cat_delta.items()
    )
    scored.sort(key=lambda item: item[1], reverse=True)
    parts = [
        f"{CAT_LABELS[cat]} {value:+.4f}" if cat in PCT_CATS
        else f"{CAT_LABELS[cat]} {value:+.0f}"
        for cat, value in scored[:2]
    ]
    return " / ".join(parts)


class WaiverView(QWidget):
    """Waivers page: pickers, FAAB budget, manual candidate rows, ranked table."""

    def __init__(self, service: SyncService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.service = service
        self.snapshot: dict | None = None
        self._rows: list[dict] = []
        self._next_row = 0

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

        self.title_label = QLabel("Waivers")
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
        root.addLayout(grid)

        self.week_note = QLabel(
            "Week is display-only pre-draft (season projections compare)."
        )
        self.week_note.setObjectName("secondary")
        root.addWidget(self.week_note)

        # --- budget ------------------------------------------------------------
        budget_row = QHBoxLayout()
        budget_row.addWidget(QLabel("FAAB remaining: $"))
        self.budget_spin = QSpinBox()
        self.budget_spin.setRange(0, 100)
        self.budget_spin.setValue(int(service.settings().get("waiver_faab_budget", 100)))
        budget_row.addWidget(self.budget_spin)
        budget_row.addStretch(1)
        root.addLayout(budget_row)

        # --- candidate entry -----------------------------------------------------
        self.entry_note = QLabel(_ENTRY_NOTE)
        self.entry_note.setObjectName("secondary")
        self.entry_note.setWordWrap(True)
        root.addWidget(self.entry_note)

        self.candidate_grid = QGridLayout()
        self.candidate_grid.setSpacing(4)
        header = QHBoxLayout()
        header.addWidget(QLabel("Name"))
        header.addWidget(QLabel("Cost (0 = free)"))
        header.addWidget(QLabel(""))
        self.candidate_grid.addLayout(header, 0, 0, 1, 3)
        root.addLayout(self.candidate_grid)

        self.add_button = QPushButton("Add candidate")
        self.add_button.clicked.connect(lambda: self.add_candidate())
        root.addWidget(self.add_button, 0, Qt.AlignmentFlag.AlignLeft)

        self.rank_button = QPushButton("Rank")
        self.rank_button.setProperty("ink", "true")
        self.rank_button.clicked.connect(self.rank)
        root.addWidget(self.rank_button, 0, Qt.AlignmentFlag.AlignLeft)

        # --- banner ------------------------------------------------------------
        self.banner = QLabel(_RESULT_NOTE)
        self.banner.setObjectName("banner-info")
        self.banner.setWordWrap(True)
        root.addWidget(self.banner)

        # --- results table ---------------------------------------------------------
        self.result_table = QTableWidget(0, len(_COLUMNS))
        self.result_table.setHorizontalHeaderLabels(_COLUMNS)
        self.result_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.result_table.setSelectionMode(
            QAbstractItemView.SelectionMode.NoSelection
        )
        self.result_table.verticalHeader().setVisible(False)
        self.result_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        root.addWidget(self.result_table, 1)

        self.budget_spin.valueChanged.connect(self._save_budget)

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
        finally:
            self.team_combo.blockSignals(False)
            self.opp_combo.blockSignals(False)
            self.week_combo.blockSignals(False)

    # -- candidate rows -------------------------------------------------------

    def _add_row(self, name: str, cost: int) -> dict:
        row_index = self._next_row
        self._next_row += 1

        name_edit = QLineEdit()
        name_edit.setPlaceholderText("player name")
        name_edit.setText(name)
        cost_spin = QSpinBox()
        cost_spin.setRange(0, 99)
        cost_spin.setValue(cost)
        remove_button = QPushButton("Remove")
        row_data = {"row": row_index, "name": name_edit, "cost": cost_spin,
                    "remove": remove_button}
        remove_button.clicked.connect(
            lambda _checked, row=row_data: self._remove_row(row)
        )
        self._rows.append(row_data)
        self.candidate_grid.addWidget(name_edit, row_index + 1, 0)
        self.candidate_grid.addWidget(cost_spin, row_index + 1, 1)
        self.candidate_grid.addWidget(remove_button, row_index + 1, 2)
        return row_data

    def _remove_row(self, row: dict) -> None:
        if row in self._rows:
            self._rows.remove(row)
        for widget in (row["name"], row["cost"], row["remove"]):
            widget.setParent(None)
            widget.deleteLater()

    # -- actions ---------------------------------------------------------------

    def _save_budget(self, value: int) -> None:
        settings = self.service.settings()
        settings["waiver_faab_budget"] = value
        self.service.save_settings(settings)

    def rank(self) -> None:
        """Rank the entered candidates synchronously and render the table."""
        team = self.team_combo.currentText()
        opp = self.opp_combo.currentText()
        if not team or not opp:
            self._clear_results()
            _status.set_status(self.banner, "info", "Pick a team and an opponent first.")
            return
        candidates: list[WaiverCandidate] = []
        for row in self._rows:
            name = row["name"].text().strip()
            if not name:
                continue  # empty rows are skipped, not an error
            candidates.append(WaiverCandidate(name=name, faab_cost=row["cost"].value()))
        if not candidates:
            self._clear_results()
            _status.set_status(self.banner, "info", "Add at least one candidate.")
            return

        roster_names, missing = _team_roster_names(self.service, team)
        opp_names, opp_missing = _team_roster_names(self.service, opp)
        notes: list[str] = []
        if missing:
            notes.append(f"{team}: not in pool: {', '.join(missing)} (skipped).")
        if opp_missing:
            notes.append(f"{opp}: not in pool: {', '.join(opp_missing)} (skipped).")

        try:
            rankings = rank_candidates(
                candidates,
                roster_names,
                opp_names,
                pool=PlayerPool.load(self.service.pool_path),
                faab_budget=self.budget_spin.value(),
            )
        except ValueError as exc:
            _status.set_status(self.banner, "danger", str(exc))
            self._clear_results()
            return

        _status.set_status(
            self.banner, "success", _RESULT_NOTE + (("\n" + " ".join(notes)) if notes else "")
        )
        self._render_rankings(rankings)

    def _clear_results(self) -> None:
        self.result_table.setRowCount(0)

    def _render_rankings(self, rankings: list) -> None:
        self.result_table.setRowCount(len(rankings))
        for i, r in enumerate(rankings):
            cost = r.candidate.faab_cost
            texts = (
                str(i + 1),
                r.pool_name,
                f"{r.delta_p:+.4f}",
                r.best_drop or "",
                _top2_cat_delta(r.cat_delta),
                str(cost if cost is not None else 0),
                "YES" if r.over_budget else "",
                r.rationale,
            )
            for col, text in enumerate(texts):
                item = QTableWidgetItem(text)
                if col in (0, 2, 5):  # rank, delta-P, FAAB cost: numbers
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                        )
                self.result_table.setItem(i, col, item)

    # -- test seams ---------------------------------------------------------------

    def add_candidate(self, name: str = "", cost: int = 0) -> dict:
        """Add one candidate row (test seam doubles as the button callback)."""
        return self._add_row(name, cost)

    def pick_teams(self, team: str, opp: str) -> None:
        it = self.team_combo.findText(team)
        io = self.opp_combo.findText(opp)
        if it >= 0:
            self.team_combo.setCurrentIndex(it)
        if io >= 0:
            self.opp_combo.setCurrentIndex(io)


__all__ = ["WaiverView"]
