"""Matchup view (M3.2): team pickers, week, P(win) headline, 9-cat gap bars.

Pre-draft roster source: per picked team, the resolved keeper entries
(``keepers.json`` via ``domain/keepers.resolve`` + ``aliases.json``) union
the entered ``DraftPick`` players (``draft_picks.json``), each looked up in
``players.csv`` via :class:`PlayerPool` (deduped, order kept). There are no
lineups yet, so full-roster projection is shown with a banner.

The headline starts in deterministic mode (category score + winner/push).
"Run Monte-Carlo" recomputes synchronously (a few seconds at 10k trials
pre-draft — acceptable, noted here instead of a worker thread). The
``week`` parameter is accepted by the engine but unused pre-draft (season
scale cancels in the per-category compare).

All colors come from :mod:`ball_buddy.ui.theme` tokens (no raw hex).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen
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
from ball_buddy.domain.engine import PlayerProjection
from ball_buddy.domain.keepers import KeeperEntry
from ball_buddy.domain.players import PlayerPool
from ball_buddy.services.sync import SyncResult, SyncService
from ball_buddy.ui import theme
from ball_buddy.ui.views import _offline

CAT_LABELS: dict[str, str] = {
    "pts": "Pts", "reb": "Reb", "ast": "Ast", "stl": "Stl", "blk": "Blk",
    "to": "To", "three": "3P", "fg_pct": "FG%", "ft_pct": "FT%",
}

# _GapBars geometry constants.
_ROW_H = 24
_GROUP_GAP = 10
_LABEL_W = 64
_RIGHT_PAD = 24


def _fmt_gap(cat: str, value: float) -> str:
    if cat in engine.COUNT_CATS:
        return f"{value:+.0f}"
    return f"{value:+.8f}"


def _fmt_value(cat: str, value: float) -> str:
    if cat in engine.COUNT_CATS:
        return f"{value:.1f}"
    return f"{value:.4f}"


class _GapBars(QWidget):
    """paintEvent-drawn 9-category gap bars (7-count / 2-pct groups).

    Each group shares one scale = max |gap| in the group. A-favorable bars
    (bar pointing left, :data:`theme.INK_FILL`), B-favorable (pointing
    right, :data:`theme.TEXT_MUTED`), tie = a :data:`theme.DIVIDER` tick at
    the center axis. "A-favorable" follows ``engine.DIRECTIONS``: for ``to``
    a positive gap means A is *worse*, so the bar points right.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.gaps: dict[str, float] = {}
        height = len(engine.CATS) * _ROW_H + _GROUP_GAP
        self.setFixedHeight(height)
        self.setMinimumWidth(320)

    def set_gaps(self, gaps: dict[str, float]) -> None:
        self.gaps = dict(gaps)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt naming
        painter = QPainter(self)
        painter.setFont(self.font())
        width = self.width()
        center = _LABEL_W + max(10, (width - _LABEL_W - _RIGHT_PAD) / 2)
        half = max(10.0, center - _LABEL_W - 8)

        label_pen = QPen(QColor(theme.TEXT_SECONDARY))
        painter.setPen(label_pen)

        y = 4
        for group_index, cats in enumerate((engine.COUNT_CATS, engine.PCT_CATS)):
            if group_index:
                y += _GROUP_GAP
            scale = max((abs(self.gaps.get(cat, 0.0)) for cat in cats), default=0.0)
            if scale <= 0:
                scale = 1.0
            # center axis for the group
            axis_pen = QPen(QColor(theme.DIVIDER), 1)
            painter.setPen(axis_pen)
            group_top = y
            group_h = len(cats) * _ROW_H
            painter.drawLine(int(center), group_top, int(center), group_top + group_h)
            for cat in cats:
                painter.setPen(label_pen)
                painter.drawText(
                    0, y, _LABEL_W - 8, _ROW_H,
                    int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
                    CAT_LABELS[cat],
                )
                signed = (
                    self.gaps.get(cat, 0.0)
                    if engine.DIRECTIONS[cat] == "higher"
                    else -self.gaps.get(cat, 0.0)
                )
                bar_y = y + (_ROW_H - 10) // 2
                if abs(signed) < 1e-12:
                    painter.setPen(QPen(QColor(theme.DIVIDER), 2))
                    painter.drawLine(
                        int(center), y + 4, int(center), y + _ROW_H - 4
                    )
                else:
                    length = int(abs(self.gaps.get(cat, 0.0)) / scale * half)
                    color = theme.INK_FILL if signed > 0 else theme.TEXT_MUTED
                    start = center - length if signed > 0 else center
                    painter.fillRect(int(start), bar_y, max(2, length), 10, QColor(color))
                y += _ROW_H
        painter.end()


class MatchupView(QWidget):
    """Matchup page: pickers, banner, headline, gap bars, cat + marginal tables."""

    def __init__(self, service: SyncService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.service = service
        self.snapshot: dict | None = None
        self.last_result: engine.MatchupResult | None = None

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

        self.title_label = QLabel("Matchup")
        self.title_label.setObjectName("title")
        grid.addWidget(self.title_label, 0, 0)

        self.team_a_combo = QComboBox()
        self.team_b_combo = QComboBox()
        self.week_combo = QComboBox()
        self.tie_break_combo = QComboBox()
        self.tie_break_combo.addItems(engine.TIE_BREAK_MODES)
        settings = service.settings()
        stored = settings.get("matchup_tie_break", engine.TIE_BREAK_MODES[0])
        index = self.tie_break_combo.findText(stored)
        self.tie_break_combo.setCurrentIndex(index if index >= 0 else 0)

        self.seed_spin = QSpinBox()
        self.seed_spin.setRange(0, 2**31 - 1)
        self.seed_spin.setValue(42)
        self.trials_spin = QSpinBox()
        self.trials_spin.setRange(1, 1_000_000)
        self.trials_spin.setValue(10_000)

        grid.addWidget(QLabel("Team A:"), 0, 1)
        grid.addWidget(self.team_a_combo, 0, 2)
        grid.addWidget(QLabel("Team B:"), 0, 3)
        grid.addWidget(self.team_b_combo, 0, 4)
        grid.addWidget(QLabel("Week:"), 0, 5)
        grid.addWidget(self.week_combo, 0, 6)
        grid.addWidget(QLabel("Tie-break:"), 0, 7)
        grid.addWidget(self.tie_break_combo, 0, 8)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Seed:"))
        row2.addWidget(self.seed_spin)
        row2.addWidget(QLabel("Trials:"))
        row2.addWidget(self.trials_spin)
        self.mc_button = QPushButton("Run Monte-Carlo")
        self.mc_button.clicked.connect(self._run_mc)
        row2.addWidget(self.mc_button)
        row2.addStretch(1)
        grid.addLayout(row2, 1, 0, 1, 9)
        root.addLayout(grid)

        self.week_note = QLabel(
            "Week is accepted but unused pre-draft (season projections compare)."
        )
        self.week_note.setObjectName("secondary")
        root.addWidget(self.week_note)

        # --- banner ------------------------------------------------------------
        self.banner = QLabel(
            "No lineups yet — projecting full rosters from keepers + drafted picks."
        )
        self.banner.setObjectName("banner-info")
        self.banner.setWordWrap(True)
        root.addWidget(self.banner)

        # --- headline + MC result ------------------------------------------------
        self.headline_label = QLabel("")
        self.headline_label.setObjectName("title")
        root.addWidget(self.headline_label)
        self.mc_label = QLabel("")
        self.mc_label.setObjectName("secondary")
        root.addWidget(self.mc_label)

        # --- gap bars ---------------------------------------------------------
        self.gap_bars = _GapBars(self)
        root.addWidget(self.gap_bars)

        # --- per-category table -------------------------------------------------
        self.cat_table = QTableWidget(0, 5)
        self.cat_table.setHorizontalHeaderLabels(["Cat", "Gap", "A", "B", "W/L"])
        self.cat_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.cat_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.cat_table.verticalHeader().setVisible(False)
        self.cat_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.cat_table.setFixedHeight(9 * 28 + 40)
        root.addWidget(self.cat_table)

        # --- marginal table -------------------------------------------------------
        self.marginal_table = QTableWidget(0, 11)
        self.marginal_table.setHorizontalHeaderLabels(
            ["Player", "Side", "Pts", "Reb", "Ast", "Stl", "Blk", "To", "3P",
             "FG%", "FT%"]
        )
        self.marginal_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.marginal_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.marginal_table.verticalHeader().setVisible(False)
        self.marginal_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        root.addWidget(self.marginal_table, 1)

        self.team_a_combo.currentIndexChanged.connect(self._recompute)
        self.team_b_combo.currentIndexChanged.connect(self._recompute)
        self.week_combo.currentIndexChanged.connect(self._recompute)
        self.tie_break_combo.currentIndexChanged.connect(self._on_tie_break_changed)

        self.apply_result(service.load_last())
        _offline.apply_view_fallback(self, service, self.offline_banner)

    # -- data loading -----------------------------------------------------

    def apply_result(self, result: SyncResult) -> None:
        """(Re)load snapshot/teams from a SyncResult (any origin), like
        ``LeagueView.apply_result``."""
        if result.snapshot is not None:
            self.snapshot = result.snapshot
            _offline.hide_banner(self.offline_banner)
            self._refresh_combos()
        self._recompute()

    def _refresh_combos(self) -> None:
        assert self.snapshot is not None
        self.team_a_combo.blockSignals(True)
        self.team_b_combo.blockSignals(True)
        self.week_combo.blockSignals(True)
        try:
            names = [team.get("name", "") for team in self.snapshot.get("teams", [])]
            self.team_a_combo.clear()
            self.team_a_combo.addItems(names)
            self.team_b_combo.clear()
            self.team_b_combo.addItems(names)
            if len(names) > 1:
                self.team_b_combo.setCurrentIndex(1)
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
            self.team_a_combo.blockSignals(False)
            self.team_b_combo.blockSignals(False)
            self.week_combo.blockSignals(False)

    # -- roster building ------------------------------------------------------

    def _load_team_data(self, team_name: str) -> tuple[list[dict[str, str]], list[str]]:
        """Pool rows (kept players resolved + entered picks, deduped, order
        kept), plus the kept/picked names that did not resolve into the pool
        (surfaced as warnings, never a crash). One ``keepers.resolve`` pass.
        """
        pool = PlayerPool.load(self.service.pool_path)
        aliases = self.service.load_aliases()
        keepers = keepers_mod.load(self.service.data_dir / keepers_mod.KEEPERS_FILE)
        picks = picks_mod.load(self.service.data_dir / picks_mod.PICKS_FILE)
        if not team_name:
            return [], []
        names = [entry.player for entry in keepers if entry.team == team_name] + [
            pick.player for pick in picks if pick.team == team_name
        ]
        # keepers.resolve only needs the player names; cost_round/team are unused
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

    def _standings(self) -> dict[str, tuple[int, int]]:
        """``{team name: (wins, losses)}`` from the snapshot standings
        (empty pre-draft — the engine then reports push on a cat-tie)."""
        out: dict[str, tuple[int, int]] = {}
        for entry in (self.snapshot or {}).get("standings", []):
            name = entry.get("name", "")
            if name:
                out[name] = (int(entry.get("wins", 0) or 0),
                             int(entry.get("losses", 0) or 0))
        return out

    # -- compute + render --------------------------------------------------------

    def _selected_week(self) -> int:
        """Current week as int; falls back to the first numeric combo item
        (never a silent constant) if the current text is not numeric."""
        try:
            return int(self.week_combo.currentText())
        except ValueError:
            pass
        for i in range(self.week_combo.count()):
            try:
                return int(self.week_combo.itemText(i))
            except ValueError:
                continue
        return 1

    def _recompute(self, mc: bool = False) -> None:
        if self.snapshot is None:
            self.headline_label.setText("No snapshot — sync a league first.")
            return
        team_a = self.team_a_combo.currentText()
        team_b = self.team_b_combo.currentText()
        if not team_a or not team_b:
            self.headline_label.setText("Pick two teams.")
            return

        rows_a, missing_a = self._load_team_data(team_a)
        rows_b, missing_b = self._load_team_data(team_b)
        warning_notes: list[str] = []
        if not rows_a or not rows_b:
            warning_notes.append("Empty roster: no keepers/picks resolved in the pool.")
        for team, missing in ((team_a, missing_a), (team_b, missing_b)):
            if missing:
                warning_notes.append(
                    f"{team}: not in pool: {', '.join(missing)} (skipped)."
                )

        roster_a = engine.project_roster(rows_a, team_a)
        roster_b = engine.project_roster(rows_b, team_b)
        result = engine.matchup(
            roster_a,
            roster_b,
            week=self._selected_week(),
            tie_break=self.tie_break_combo.currentText(),
            h2h=self._standings(),
            mc=mc,
            seed=self.seed_spin.value() if mc else None,
            trials=self.trials_spin.value(),
        )
        result.warnings = [*warning_notes, *result.warnings]
        self.last_result = result
        self._roster_players = (roster_a.players, roster_b.players)
        self._render(team_a, team_b, result)
        if mc:
            p = result.p_win if result.p_win is not None else 0.0
            self.mc_label.setText(
                f"P({team_a} wins) = {p:.4f} "
                f"(seed {self.seed_spin.value()}, {self.trials_spin.value()} trials)"
            )
        else:
            self.mc_label.setText("")

    def _render(
        self, team_a: str, team_b: str, result: engine.MatchupResult
    ) -> None:
        wins_a, wins_b = result.cat_wins
        if result.winner:
            self.headline_label.setText(
                f"{result.winner} wins ({wins_a}-{wins_b} cats)"
            )
        else:
            self.headline_label.setText(
                f"Push ({wins_a}-{wins_b} cats) — no tie-break evidence."
            )
        extra = "\n".join(dict.fromkeys(result.warnings))
        self.week_note.setText(
            "Week is accepted but unused pre-draft (season projections compare).\n"
            + extra
            if extra
            else "Week is accepted but unused pre-draft (season projections compare)."
        )

        self.gap_bars.set_gaps(result.gaps)
        self._render_tables(result)

    def _render_tables(self, result: engine.MatchupResult) -> None:
        players_a, players_b = getattr(self, "_roster_players", ((), ()))
        outcomes = dict(zip(engine.CATS, result.cat_outcomes))
        self.cat_table.setRowCount(len(engine.CATS))
        for i, cat in enumerate(engine.CATS):
            a_out, _ = outcomes[cat]
            cell_wl = "A" if a_out == "win" else ("tie" if a_out == "tie" else "B")
            a_val, b_val = self._side_values(cat, players_a, players_b)
            for col, text in enumerate(
                (CAT_LABELS[cat], _fmt_gap(cat, result.gaps[cat]),
                 _fmt_value(cat, a_val), _fmt_value(cat, b_val), cell_wl)
            ):
                self.cat_table.setItem(i, col, QTableWidgetItem(text))

        # marginal table: signed count-cat contribution to the gap (A +, B -)
        rows: list[tuple[float, str, str, PlayerProjection, list[float]]] = []
        for player in list(players_a) + list(players_b):
            side = "A" if player in players_a else "B"
            sign = 1.0 if side == "A" else -1.0
            count_values = [sign * player.values[cat] for cat in engine.COUNT_CATS]
            magnitude = max(abs(v) for v in count_values)
            rows.append((magnitude, side, player.name, player, count_values))
        rows.sort(key=lambda item: item[0], reverse=True)
        self.marginal_table.setRowCount(min(20, len(rows)))
        for i, (_, side, name, _, count_values) in enumerate(rows[:20]):
            texts = [name, side] + [f"{v:+.1f}" for v in count_values] + ["–", "–"]
            for col, text in enumerate(texts):
                self.marginal_table.setItem(i, col, QTableWidgetItem(text))

    @staticmethod
    def _side_values(
        cat: str,
        players_a: tuple,
        players_b: tuple,
    ) -> tuple[float, float]:
        if cat in engine.COUNT_CATS:
            return (
                sum(p.values[cat] for p in players_a),
                sum(p.values[cat] for p in players_b),
            )
        # pct cats: pooled weighted by attempt volume (same as engine)
        def pool(players: tuple) -> float:
            num = sum(p.values[cat] * p.attempts(cat) for p in players)
            den = sum(p.attempts(cat) for p in players)
            return num / den if den > 0 else 0.0
        return pool(players_a), pool(players_b)

    # -- actions ---------------------------------------------------------------

    def _run_mc(self) -> None:
        self._recompute(mc=True)

    def _on_tie_break_changed(self) -> None:
        settings = self.service.settings()
        settings["matchup_tie_break"] = self.tie_break_combo.currentText()
        self.service.save_settings(settings)
        self._recompute()

    # -- test seams ---------------------------------------------------------------

    def pick_teams(self, a: str, b: str) -> None:
        ia = self.team_a_combo.findText(a)
        ib = self.team_b_combo.findText(b)
        if ia >= 0:
            self.team_a_combo.setCurrentIndex(ia)
        if ib >= 0:
            self.team_b_combo.setCurrentIndex(ib)


__all__ = ["MatchupView", "_GapBars", "CAT_LABELS"]
