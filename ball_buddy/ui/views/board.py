"""Draft board (M2.2+): the autodraft-oriented draft helper.

Left column: current-pick strip (R{r} / pick n/total / team, name search,
Log selected / Commit / Undo / Setup), the available-players table
(model-based ``QTableView`` — hundreds of rows, double-click or "Log" to
enter a pick, POS filter combo in the model), the 9-category relative
panel (My team / League median / Gap / Tag — Gap cells stat-colored), and
the roster panel (team dropdown, amber "NOT MY TEAM" flag, keepers then
picks in round order, stat-colored z columns). Right: the recommendations
rail (P6 scorer ordering with tag chips, mkt/fit summary, value-gap
badge, verbatim reason, top-N spin persisted to ``settings["rec_top_n"]``).

Keeper-forfeit-aware: forfeited picks are derived from the keeper entries
(single source of truth — never stored in draft_picks.json). Logging a
pick and undoing both persist atomically via ``domain/picks.py``
(``io/state.py``). Theme tokens only, plus the stat-color cue
(``ui/theme.py::stat_color``) as cell backgrounds; the neutral 45–55th
percentile band is uncolored.
"""

from __future__ import annotations

import re

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QCompleter,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTableView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ball_buddy.domain import picks as picks_mod
from ball_buddy.domain.engine import DIRECTIONS, PCT_CATS, project_roster
from ball_buddy.domain.keepers import KeeperEntry
from ball_buddy.domain.league import Pick
from ball_buddy.domain.naming import bridge
from ball_buddy.domain.players import PlayerPool
from ball_buddy.domain.recommend import Suggestion, recommend_need_aware
from ball_buddy.domain.relative import category_tags
from ball_buddy.domain.scorer import CAT_Z_COLUMN
from ball_buddy.services.sync import SyncService
from ball_buddy.ui.theme import THEMES, stat_color
from ball_buddy.ui.views import _offline
from ball_buddy.ui.views.matchup import CAT_LABELS

# Reason-bit parsers for the rail's mkt/fit summary (the scorer's reason
# string is the single source of the split numbers — "mkt 3/50 → 0.94"
# and "fit +0.42z").
_MKT_RE = re.compile(r"mkt (\d+)/(\d+) \u2192 ([\d.]+)")
_FIT_RE = re.compile(r"fit ([+\-][\d.]+)z")


class PlayerTableModel(QAbstractTableModel):
    """Available pool rows for the draft table (model-based, hundreds of
    rows — per-row widgets/buttons would not scale).

    Columns: Name, Pos, Value, Rank, then one column per engine cat in
    ``CATS`` order holding the pool's signed z (canonical column via
    ``scorer.CAT_Z_COLUMN``). Stat cells carry a ``BackgroundRole`` from
    ``theme.stat_color`` (transparent in the neutral 45–55th percentile
    band; ``to`` is lower-is-better, since the pool's raw ``z_to`` is not
    sign-corrected). The POS filter (primary position, "All" = no filter)
    is applied in the model, not the view.
    """

    BASE_COLUMNS = ("Name", "Pos", "Value", "Rank")

    def __init__(
        self,
        rows: list[dict[str, str]],
        excluded: set[str],
        theme_name: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._theme = theme_name
        self._pos_filter = ""
        self._all: list[dict[str, str]] = []
        self._visible: list[dict[str, str]] = []
        self.reset_pool(rows, excluded, theme_name)

    def reset_pool(
        self,
        rows: list[dict[str, str]],
        excluded: set[str],
        theme_name: str,
    ) -> None:
        """Swap in a fresh pool (refresh path) and rebuild the visible set."""
        self.beginResetModel()
        self._theme = theme_name
        self._all = [
            row
            for row in rows
            if (row.get("name") or "").strip() and (row.get("name") or "").strip() not in excluded
        ]
        self._rebuild()
        self.endResetModel()

    def set_pos_filter(self, pos: str) -> None:
        """Primary-position filter ("" = All)."""
        self._pos_filter = (pos or "").strip()
        self.beginResetModel()
        self._rebuild()
        self.endResetModel()

    def _rebuild(self) -> None:
        self._visible = [
            row
            for row in self._all
            if not self._pos_filter
            or (row.get("pos", "") or "").split("/")[0].strip() == self._pos_filter
        ]

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._visible)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return len(self.BASE_COLUMNS) + len(CAT_Z_COLUMN)

    def headerData(  # noqa: N802
        self, section: int, orientation, role: int = Qt.ItemDataRole.DisplayRole
    ) -> str | None:
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            if section < len(self.BASE_COLUMNS):
                return self.BASE_COLUMNS[section]
            return CAT_LABELS[tuple(CAT_Z_COLUMN)[section - len(self.BASE_COLUMNS)]]
        return str(section + 1)

    def data(  # noqa: N802
        self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole
    ) -> object:
        if not index.isValid():
            return None
        row = self._visible[index.row()]
        col = index.column()
        if col < len(self.BASE_COLUMNS):
            key = ("name", "pos", "value", "rank")[col]
            return (row.get(key, "") or "").strip()
        if role == Qt.ItemDataRole.DisplayRole:
            z = _parse_z(row.get(CAT_Z_COLUMN[tuple(CAT_Z_COLUMN)[col - 4]], ""))
            return "" if z is None else f"{z:+.1f}"
        if role == Qt.ItemDataRole.BackgroundRole:
            cat = tuple(CAT_Z_COLUMN)[col - 4]
            z = _parse_z(row.get(CAT_Z_COLUMN[cat], ""))
            if z is None:
                return None
            color = stat_color(
                z, lower_is_better=DIRECTIONS[cat] == "lower", theme=self._theme
            )
            if color.alpha() == 0:
                return None
            return QBrush(color)
        return None

    def name_at(self, row: int) -> str:
        """Pool name of model row ``row`` (for logging a selected player)."""
        return self._visible[row]["name"]


def _parse_z(text: str) -> float | None:
    """Parsed z-score; None when the source cell is blank (renders empty)."""
    stripped = str(text or "").strip()
    if not stripped:
        return None
    try:
        return float(stripped)
    except ValueError:
        return 0.0


def _primary_pos(row: dict[str, str]) -> str:
    return (row.get("pos", "") or "").split("/")[0].strip()


class DraftBoard(QWidget):
    """Autodraft-oriented draft helper: strip + players + relative +
    rosters on the left, recommendations rail on the right.

    The snake order lives in ``self.snake`` (13 rounds x teams, even
    rounds reversed — ``_order_of`` mirrors ``league.snake_order``);
    keeper forfeits are shown in the roster panel and consume overall
    pick numbers. Logging a pick (typed name, double-click, or "Log")
    and undoing both persist and re-render every panel.
    """

    #: emitted when the user clicks "Setup…" — the host view opens the
    #: SetupDialog (teams/order/keepers/my-team) and refreshes on accept.
    setup_requested = Signal()

    def __init__(self, service: SyncService, keepers: list[KeeperEntry]) -> None:
        super().__init__()
        self.service = service
        self.keepers = list(keepers)
        self.picks: list[picks_mod.DraftPick] = []
        self.snake: list[Pick] = []
        self.start_order: list[str] = []
        self.picks_path = service.data_dir / picks_mod.PICKS_FILE
        self._keeper_cells: dict[tuple[int, int], str] = {}  # (round, order) -> player
        self._pool = PlayerPool.load(service.pool_path)
        self._loaded_picks: list[picks_mod.DraftPick] = []
        self._pick_error = ""
        self._report = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        self.offline_banner = QLabel("")
        self.offline_banner.setObjectName("banner-info")
        self.offline_banner.setWordWrap(True)
        self.offline_banner.setVisible(False)
        root.addWidget(self.offline_banner)

        self.alert_banner = QLabel("")
        self.alert_banner.setObjectName("banner-danger")
        self.alert_banner.setWordWrap(True)
        self.alert_banner.setVisible(False)
        root.addWidget(self.alert_banner)

        main_row = QVBoxLayout()
        root.addLayout(main_row, 1)
        left = QVBoxLayout()
        right = QVBoxLayout()
        main_row.addLayout(left, 1)
        main_row.addLayout(right, 0)

        left_panel = QWidget()
        left_panel.setObjectName("panel")
        left.addWidget(left_panel, 1)
        inner = QVBoxLayout(left_panel)
        inner.setContentsMargins(8, 8, 8, 8)
        inner.setSpacing(8)

        # --- current-pick strip ------------------------------------------------
        strip = QVBoxLayout()
        self.current_label = QLabel("")
        self.current_label.setObjectName("secondary")
        strip.addWidget(self.current_label)

        controls = QVBoxLayout()
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("player name (or double-click the table)")
        controls.addWidget(self.name_edit)

        buttons = QVBoxLayout()
        buttons.setSpacing(4)
        self.commit_button = QPushButton("Commit pick")
        self.commit_button.setProperty("ink", "true")
        self.commit_button.clicked.connect(self._commit)
        self.name_edit.returnPressed.connect(self._commit)
        buttons.addWidget(self.commit_button)
        self.log_button = QPushButton("Log selected")
        self.log_button.clicked.connect(self.log_selected)
        buttons.addWidget(self.log_button)
        self.undo_button = QPushButton("Undo last")
        self.undo_button.clicked.connect(self.undo)
        buttons.addWidget(self.undo_button)
        self.setup_button = QPushButton("Setup…")
        self.setup_button.clicked.connect(self.setup_requested.emit)
        buttons.addWidget(self.setup_button)
        controls.addLayout(buttons)

        strip_row = QVBoxLayout()
        strip_row.addLayout(strip)
        strip_row.addLayout(controls)
        inner.addLayout(strip_row, 0)

        # --- available players (model-based table + POS filter) ----------------
        filter_row = QVBoxLayout()
        pos_row = QVBoxLayout()
        pos_label = QLabel("Pos")
        pos_label.setObjectName("secondary")
        self.pos_combo = QComboBox()
        self.pos_combo.setCurrentText("All")
        self.pos_combo.currentTextChanged.connect(self._pos_filter_changed)
        pos_row.addWidget(pos_label)
        pos_row.addWidget(self.pos_combo)
        filter_row.addLayout(pos_row)
        inner.addLayout(filter_row, 0)

        self._player_model = PlayerTableModel(
            self._pool.rows, set(), self._theme_name(), self
        )
        self.player_view = QTableView()
        self.player_view.setModel(self._player_model)
        self.player_view.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.player_view.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.player_view.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.player_view.verticalHeader().setVisible(False)
        self.player_view.doubleClicked.connect(self._double_clicked)
        inner.addWidget(self.player_view, 1)

        # --- relative panel: my team vs the league (P3) ------------------------
        self.relative_panel = QWidget()
        self.relative_panel.setObjectName("panel")
        left.addWidget(self.relative_panel, 0)
        relative_inner = QVBoxLayout(self.relative_panel)
        relative_inner.setContentsMargins(8, 8, 8, 8)
        relative_inner.setSpacing(4)
        self.relative_title = QLabel("My team vs league")
        self.relative_title.setObjectName("title")
        relative_inner.addWidget(self.relative_title)
        self.relative_grid = QTableWidget(4, len(CAT_Z_COLUMN))
        self.relative_grid.setHorizontalHeaderLabels(
            [CAT_LABELS[cat] for cat in CAT_Z_COLUMN]
        )
        self.relative_grid.setVerticalHeaderLabels(
            ["My team", "League median", "Gap", "Tag"]
        )
        self.relative_grid.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.relative_grid.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.relative_grid.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        relative_inner.addWidget(self.relative_grid, 0)
        self.relative_panel.setVisible(False)

        # --- roster panel (team dropdown + stat-colored roster) ----------------
        self.roster_panel = QWidget()
        self.roster_panel.setObjectName("panel")
        left.addWidget(self.roster_panel, 0)
        roster_inner = QVBoxLayout(self.roster_panel)
        roster_inner.setContentsMargins(8, 8, 8, 8)
        roster_inner.setSpacing(4)
        roster_head = QVBoxLayout()
        self.roster_title = QLabel("Roster")
        self.roster_title.setObjectName("title")
        roster_head.addWidget(self.roster_title)
        roster_row = QVBoxLayout()
        self.roster_combo = QComboBox()
        self.roster_combo.currentTextChanged.connect(
            lambda _name: self._render_roster(self._report)
        )
        self.roster_flag = QLabel("NOT MY TEAM")
        self.roster_flag.setVisible(False)
        roster_row.addWidget(self.roster_combo)
        roster_row.addWidget(self.roster_flag)
        roster_head.addLayout(roster_row)
        roster_inner.addLayout(roster_head, 0)
        self.roster_grid = QTableWidget(0, 4 + len(CAT_Z_COLUMN))
        self.roster_grid.setHorizontalHeaderLabels(
            list(PlayerTableModel.BASE_COLUMNS[:3])
            + ["From"]
            + [CAT_LABELS[cat] for cat in CAT_Z_COLUMN]
        )
        self.roster_grid.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.roster_grid.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.roster_grid.verticalHeader().setVisible(False)
        self.roster_grid.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        roster_inner.addWidget(self.roster_grid, 0)
        self.roster_panel.setVisible(False)

        # --- recommendations rail (right) ---------------------------------------
        rail_panel = QWidget()
        rail_panel.setObjectName("panel")
        right.addWidget(rail_panel, 1)
        rail_inner = QVBoxLayout(rail_panel)
        rail_inner.setContentsMargins(8, 8, 8, 8)
        rail_inner.setSpacing(4)
        self.recs_title = QLabel("Recommendations —")
        self.recs_title.setObjectName("title")
        rail_inner.addWidget(self.recs_title)
        top_row = QVBoxLayout()
        top_label = QLabel("Top")
        top_label.setObjectName("secondary")
        self.top_n_spin = QSpinBox()
        self.top_n_spin.setRange(1, 20)
        self.top_n_spin.setValue(int(self.service.settings().get("rec_top_n", 10)))
        self.top_n_spin.valueChanged.connect(self._top_n_changed)
        top_row.addWidget(top_label)
        top_row.addWidget(self.top_n_spin)
        rail_inner.addLayout(top_row, 0)
        self.recs_grid = QTableWidget(0, 5)
        self.recs_grid.setHorizontalHeaderLabels(
            ["#", "Player", "Tag", "mkt / fit", "Reason"]
        )
        self.recs_grid.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.recs_grid.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.recs_grid.verticalHeader().setVisible(False)
        self.recs_grid.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        rail_inner.addWidget(self.recs_grid, 1)

        self.refresh()

    # -- helpers ---------------------------------------------------------------

    def _theme_name(self) -> str:
        return "dark" if self.service.settings().get("dark_mode") else "light"

    def _pos_filter_changed(self, pos: str) -> None:
        self._player_model.set_pos_filter("" if pos == "All" else pos)

    def _double_clicked(self, index: QModelIndex) -> None:
        self.log_selected()

    def _top_n_changed(self, value: int) -> None:
        settings = self.service.settings()
        settings["rec_top_n"] = value
        self.service.save_settings(settings)
        self._render_recs(self._report)

    # -- data loading ----------------------------------------------------------

    def refresh(self) -> None:
        """Rebuild the board from the effective snapshot + keepers + saved picks.

        The effective snapshot is the last Yahoo snapshot when one exists,
        else the manual team list from Settings (offline draft-day mode).
        """
        snapshot = self.service.effective_snapshot()
        if snapshot is None:
            self._pool = PlayerPool.load(self.service.pool_path)  # keep pool current
            self.start_order = []
            self.snake = []
            self.picks = []
            self._report = None
            self._player_model.reset_pool(
                [], set(), self._theme_name()
            )
            _offline.hide_banner(self.offline_banner)
            self._set_alert("Sync the league first (League → Sync now)")
            self.current_label.setText("")
            self.commit_button.setEnabled(False)
            self.log_button.setEnabled(False)
            self.undo_button.setEnabled(False)
            self.relative_panel.setVisible(False)
            self.roster_panel.setVisible(False)
            self._render_recs(None)
            return

        if _offline.is_manual(snapshot):
            _offline.show_banner(self.offline_banner)
        else:
            _offline.hide_banner(self.offline_banner)

        self.start_order = picks_mod.start_order_for(snapshot, self.service.settings())
        self._pool = PlayerPool.load(self.service.pool_path)  # may change between refreshes
        self.snake = picks_mod.build_snake(self.start_order, self.keepers)
        try:
            self.picks = picks_mod.load(self.picks_path)
            self._pick_error = ""
        except Exception as exc:  # StateError surfaced in the banner
            self.picks = list(self._loaded_picks)
            self._pick_error = f"draft_picks.json: {exc}"
        self._loaded_picks = list(self.picks)
        self._keeper_cells = {}
        for entry in self.keepers:
            if not entry.opted_out:
                self._keeper_cells[
                    (entry.cost_round, self._order_of(entry.team, entry.cost_round))
                ] = entry.player
        self.render()
        if self._pick_error:
            self._set_alert(self._pick_error)

    def _order_of(self, team: str, rnd: int) -> int:
        """The snake order (1-based) of ``team`` in round ``rnd``.

        Odd rounds run in start order, even rounds reversed — mirroring
        ``league.snake_order``, which is what the render step looks up by.
        """
        index = self.start_order.index(team)
        return index + 1 if rnd % 2 == 1 else len(self.start_order) - index

    # -- rendering ---------------------------------------------------------------

    def render(self) -> None:
        """Redraw strip, players table, relative panel, roster, and rail."""
        teams = len(self.start_order)
        if not teams:
            return
        report = bridge(
            [pick.player for pick in self.picks],
            self._pool.names(),
            self.service.load_aliases(),
        )
        self._report = report
        excluded = self._excluded_names(report)
        self._player_model.reset_pool(
            self._pool.rows, excluded, self._theme_name()
        )
        self.name_edit.setCompleter(
            QCompleter(
                [n for n in self._pool.names() if n not in self._excluded_names(report)]
            )
        )
        # POS filter options: distinct primary positions in the pool.
        # Signals stay live: restoring the kept text (or resetting to "All")
        # re-applies the model filter, so it can never desync from the combo.
        positions = [
            p
            for p in ("PG", "SG", "SF", "PF", "C")
            if any(_primary_pos(r) == p for r in self._pool.rows)
        ]
        keep = self.pos_combo.currentText()
        self.pos_combo.clear()
        self.pos_combo.addItems(["All", *positions])
        for i in range(self.pos_combo.count()):
            if self.pos_combo.itemText(i) == keep:
                self.pos_combo.setCurrentIndex(i)
                break
        # roster team dropdown (keep the selection when it survives).
        keep_team = self.roster_combo.currentText()
        self.roster_combo.blockSignals(True)
        self.roster_combo.clear()
        self.roster_combo.addItems(self.start_order)
        my_team = str(self.service.settings().get("my_team", ""))
        default = keep_team if keep_team in self.start_order else (
            my_team if my_team in self.start_order else (self.start_order[0] or "")
        )
        self.roster_combo.setCurrentText(default)
        self.roster_combo.blockSignals(False)
        self._render_strip()
        self._render_roster(report)
        self._render_relative(report)
        self._render_recs(report)

    def _render_strip(self) -> None:
        current = picks_mod.current_pick(self.snake, self.picks)
        total = len(self.snake)
        done = len(self.picks)
        self.commit_button.setEnabled(current is not None)
        self.log_button.setEnabled(current is not None and self._player_model.rowCount() > 0)
        self.undo_button.setEnabled(bool(self.picks))
        if current is None:
            if self.snake:
                self.current_label.setText(
                    f"Draft complete — {done} of {total} picks entered."
                )
            return
        self.current_label.setText(
            f"R{current.round} · pick {current.overall}/{total} · {current.team}"
        )

    def _render_recs(self, report) -> None:
        """Recommendations rail: P6 scorer ordering with tag chips, a
        mkt/fit summary parsed from the scorer's reason bits, a value-gap
        badge, the verbatim reason, and the top-N spin (persisted)."""
        grid = self.recs_grid
        grid.setRowCount(0)
        if not self.start_order or report is None:
            self.recs_title.setText("Recommendations —")
            return
        if not self._pool.rows:
            self.recs_title.setText("Recommendations —")
            return
        current = picks_mod.current_pick(self.snake, self.picks)
        if current is None:
            self.recs_title.setText("Recommendations — draft complete")
            return
        top_n = self.top_n_spin.value()
        suggestions = recommend_need_aware(
            self._pool.rows,
            self._excluded_names(report),
            self._team_projections(report),
            my_team=str(self.service.settings().get("my_team", "")),
            overall=current.overall,
            team_count=len(self.start_order),
            top_n=top_n,
        )
        self.recs_title.setText(f"Recommendations (top {len(suggestions)})")
        grid.setRowCount(len(suggestions))
        theme = THEMES[self._theme_name()]
        for r, suggestion in enumerate(suggestions):
            grid.setItem(r, 0, QTableWidgetItem(str(r + 1)))
            grid.setItem(r, 1, QTableWidgetItem(suggestion.name))
            tag_item = QTableWidgetItem(self._tag_label(suggestion))
            gap_flag = suggestion.gap
            if gap_flag:
                tag_item.setText(tag_item.text() + " · GAP")
            if gap_flag:
                tag_item.setBackground(_brush(theme["warning_bg"]))
                tag_item.setForeground(_brush(theme["warning_text"]))
            elif suggestion.tag == "VALUE":
                tag_item.setBackground(_brush(theme["success_bg"]))
                tag_item.setForeground(_brush(theme["success_text"]))
            elif suggestion.tag == "REACH":
                tag_item.setBackground(_brush(theme["info_bg"]))
                tag_item.setForeground(_brush(theme["info_text"]))
            grid.setItem(r, 2, tag_item)
            grid.setItem(r, 3, QTableWidgetItem(self._mkfit(suggestion)))
            grid.setItem(r, 4, QTableWidgetItem(suggestion.reason))

    @staticmethod
    def _tag_label(suggestion: Suggestion) -> str:
        if suggestion.tag == "REACH":
            return "REACH"
        if suggestion.tag == "VALUE":
            return "VALUE"
        if suggestion.tag == "NO_ADP":
            return "no ADP"
        if suggestion.tag == "ON":
            return "on board"
        return "—"

    @staticmethod
    def _mkfit(suggestion: Suggestion) -> str:
        """'mkt X% / fit Y' parsed from the scorer's reason bits."""
        mkt = _MKT_RE.search(suggestion.reason)
        fit = _FIT_RE.search(suggestion.reason)
        if not (mkt and fit):
            return "—"
        return f"mkt {float(mkt.group(3)) * 100:.0f}% / fit {fit.group(1)}z"

    def _render_relative(self, report=None) -> None:
        """Per-category BUILD/COAST/PUNT tags for my team vs the league (P3).

        9 columns x 4 rows (My team / League median / Gap / Tag). The Gap
        row is stat-colored: gap is normalized by the league spread
        (z-score-ish input, per ``stat_color``) and sign-flipped so
        positive = ahead = green, negative = behind = red; the neutral
        45–55th percentile band stays uncolored. Hides the panel when no
        my-team is set, there is no start order, or ``category_tags``
        falls back to ``None``.
        """
        if report is None:
            report = self._report
        my_team = str(self.service.settings().get("my_team", ""))
        if not my_team or not self.start_order:
            self.relative_panel.setVisible(False)
            return
        tags = category_tags(
            self._team_projections(report),
            my_team,
            self._pool.rows,
            self._excluded_names(report),
        )
        if tags is None:
            self.relative_panel.setVisible(False)
            return
        self.relative_panel.setVisible(True)
        self.relative_title.setText(f"My team vs league — {my_team}")
        # league spread per cat (for the gap-row color normalization)
        projections = {
            team: project_roster(team_rows, team)
            for team, team_rows in self._team_projections(report).items()
        }
        grid = self.relative_grid
        theme_name = self._theme_name()
        for c, tag in enumerate(tags):
            pct = tag.cat in PCT_CATS
            mine = f"{tag.mine:.4f}" if pct else f"{tag.mine:.1f}"
            med = f"{tag.median:.4f}" if pct else f"{tag.median:.1f}"
            gap = f"{tag.gap:+.4f}" if pct else f"{tag.gap:+.1f}"
            for r, text in enumerate([mine, med, gap, tag.tag]):
                grid.setItem(r, c, QTableWidgetItem(text))
            values = [proj.cat_values[tag.cat] for proj in projections.values()]
            spread = max(values) - min(values)
            if spread <= 0:
                spread = 1.0
            color = stat_color(-tag.gap / spread, theme=theme_name)
            gap_item = grid.item(2, c)
            if color.alpha() != 0 and gap_item is not None:
                gap_item.setBackground(QBrush(color))

    def _render_roster(self, report=None) -> None:
        """Selected team's roster: keepers (round + opt-out) then picks in
        round order, with the same stat-colored z columns as the players
        table. Amber "NOT MY TEAM" flag when the selection differs from
        ``settings["my_team"]``."""
        if not self.start_order:
            self.roster_panel.setVisible(False)
            return
        self.roster_panel.setVisible(True)
        team = self.roster_combo.currentText()
        my_team = str(self.service.settings().get("my_team", ""))
        flag_visible = bool(my_team) and team != my_team
        self.roster_flag.setVisible(flag_visible)
        if flag_visible:
            theme = THEMES[self._theme_name()]
            self.roster_flag.setStyleSheet(
                f"background-color: {theme['warning_bg']}; "
                f"color: {theme['warning_text']}; border: 2px solid "
                f"{theme['outline']}; border-radius: 8px; padding: 2px 8px;"
            )
        else:
            self.roster_flag.setStyleSheet("")
        if report is None:
            report = self._report
        bridged = report.matched if report is not None else {}
        rows: list[tuple[str, str, str, str | None]] = []  # name, from, opt_out, ...
        for entry in self.keepers:
            if entry.team != team:
                continue
            label = f"keeper R{entry.cost_round}"
            if entry.opted_out:
                label += " (opted out)"
            rows.append((entry.player, label, "out" if entry.opted_out else "", None))
        for pick in sorted(
            (p for p in self.picks if p.team == team), key=lambda p: (p.round, p.slot)
        ):
            rows.append((pick.player, f"pick R{pick.round}", "", bridged.get(pick.player)))
        self.roster_grid.setRowCount(len(rows))
        theme_name = self._theme_name()
        for r, (name, label, _state, resolved) in enumerate(rows):
            pool_row = self._pool.get(resolved or name)
            self.roster_grid.setItem(r, 0, QTableWidgetItem(name))
            self.roster_grid.setItem(r, 1, QTableWidgetItem((pool_row or {}).get("pos", "")))
            self.roster_grid.setItem(r, 2, QTableWidgetItem((pool_row or {}).get("value", "")))
            self.roster_grid.setItem(r, 3, QTableWidgetItem(label))
            if pool_row is None:
                continue
            for c, cat in enumerate(CAT_Z_COLUMN):
                z = _parse_z(pool_row.get(CAT_Z_COLUMN[cat], ""))
                item = QTableWidgetItem("" if z is None else f"{z:+.1f}")
                if z is not None:
                    color = stat_color(
                        z, lower_is_better=DIRECTIONS[cat] == "lower", theme=theme_name
                    )
                    if color.alpha() != 0:
                        item.setBackground(QBrush(color))
                self.roster_grid.setItem(r, 4 + c, item)

    def _team_projections(self, report=None) -> dict[str, list[dict[str, str]]]:
        """Pool rows per team of its secured players (recommender input).

        Secured = entered picks (alias-bridged via ``report`` when given)
        + active keepers; opted-out keepers' players stay in the pool,
        not the projection. All secured players count — no starter/bench
        distinction. Teams with no secured players map to an empty list
        (they still count toward the league median).
        """
        secured: dict[str, list[str]] = {team: [] for team in self.start_order}
        for pick in self.picks:
            name = (
                report.matched.get(pick.player, pick.player)
                if report is not None
                else pick.player
            )
            secured.setdefault(pick.team, []).append(name)
        for entry in self.keepers:
            if not entry.opted_out:
                secured.setdefault(entry.team, []).append(entry.player)
        projections: dict[str, list[dict[str, str]]] = {}
        for team, names in secured.items():
            rows = [row for name in names if (row := self._pool.get(name)) is not None]
            projections[team] = rows
        return projections

    def _excluded_names(self, report=None) -> set[str]:
        """Names to keep out of suggestions: drafted/kept + bridged pool names.

        Shared by the pick-name completer and the recommendations rail.
        With a ``report`` (bridged picks) its matched pairs exclude both
        sides; without one the raw entered pick names are used directly.
        Opted-out keepers are excluded from the forfeited-pick snake but
        their player stays draftable, so they remain suggestable.
        """
        excluded = {entry.player for entry in self.keepers if not entry.opted_out}
        if report is None:
            excluded |= {pick.player for pick in self.picks}
        else:
            excluded |= set(report.matched)
            excluded |= set(report.matched.values())
        return excluded

    # -- actions -----------------------------------------------------------------

    def _set_alert(self, text: str) -> None:
        self.alert_banner.setText(text)
        self.alert_banner.setVisible(bool(text))

    def _commit(self) -> None:
        self._log(self.name_edit.text().strip())

    def log_selected(self) -> None:
        """Log the player table's selected row (double-click or "Log")."""
        selected = self.player_view.selectionModel().selectedRows()
        if not selected:
            self._set_alert("Select a player in the table first.")
            return
        self._log(self._player_model.name_at(selected[0].row()))

    def _log(self, name: str) -> None:
        current = picks_mod.current_pick(self.snake, self.picks)
        if current is None:
            self._set_alert("Draft complete — nothing left to pick.")
            return
        if not name:
            self._set_alert("Enter a player name first.")
            return
        entered_names = {pick.player for pick in self.picks}
        if name in entered_names:
            self._set_alert(f"{name!r} is already drafted.")
            return
        report = bridge(
            [name], self._pool.names(), self.service.load_aliases()
        )
        self.picks.append(
            picks_mod.DraftPick(
                round=current.round, slot=current.order, team=current.team, player=name
            )
        )
        picks_mod.save(self.picks, self.picks_path)
        self._loaded_picks = list(self.picks)
        self.name_edit.clear()
        if name not in report.matched:
            self._set_alert(
                f"{name!r} did not match the pool — saved anyway; add an "
                "aliases.json entry to fix."
            )
        else:
            self._set_alert("")
        self.render()

    def undo(self) -> None:
        if not self.picks:
            return
        self.picks.pop()
        picks_mod.save(self.picks, self.picks_path)
        self._loaded_picks = list(self.picks)
        self._set_alert("")
        self.render()


def _brush(text: str) -> QBrush:
    return QBrush(QColor(text))


__all__ = ["DraftBoard", "PlayerTableModel"]
