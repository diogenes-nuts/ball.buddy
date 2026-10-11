"""Draft board (M2.2+): the autodraft-oriented draft helper.

Two columns. Left (stretch): current-pick strip (R{r} / pick n/total /
team, name search with a live partial-match dropdown, Commit / Undo /
Setup) + the sortable available-players table (model-based ``QTableView``
— hundreds of rows, header-click sort by parsed z, double-click or Enter
to enter a pick, POS filter combo in the model). Right: a fixed-width
scrollable rail (recommendations — P6 scorer ordering with tag chips,
mkt/fit summary, human-labeled need cats, top-N spin persisted to
``settings["rec_top_n"]``; then the 9-category comparison panel — My team
/ League median / Gap / Tag, Gap cells stat-colored; then the roster
panel — team dropdown, amber "NOT MY TEAM" flag, keepers then picks in
round order, stat-colored z columns). Each panel sizes to its content;
the rail scrolls vertically, the pool table stays the priority surface.
All banners (offline / danger alerts) live on the board; the draft page
adds only the over-cap keepers alert.

Keeper-forfeit-aware: forfeited picks are derived from the keeper entries
(single source of truth — never stored in draft_picks.json). Logging a
pick and undoing both persist atomically via ``domain/picks.py``
(``io/state.py``). Theme tokens only, plus the stat-color cue
(``ui/theme.py::stat_color``) as cell backgrounds; the neutral 45–55th
percentile band is uncolored.
"""

from __future__ import annotations

from statistics import median

from PySide6.QtCore import (
    QAbstractTableModel,
    QEvent,
    QModelIndex,
    QPoint,
    QSortFilterProxyModel,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QStandardItem,
    QStandardItemModel,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListView,
    QPushButton,
    QScrollArea,
    QSizePolicy,
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
from ball_buddy.ui.theme import FONT_MONO, TEXT_BASE, THEMES, stat_color
from ball_buddy.ui.views import _offline
from ball_buddy.ui.views._common import CAT_LABELS


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
        self._sort_key: tuple[int, bool] | None = None  # (column, ascending)
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
        self._sort_key = None
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
        self._sort_key = None
        self._rebuild()
        self.endResetModel()

    def sort(self, column: int, order: int = Qt.SortOrder.AscendingOrder) -> None:
        """Sort the visible rows by header click (the model owns the data —
        ``QAbstractTableModel.sort`` is a no-op by default).

        z columns sort by the PARSED float ("+1.2" vs "+0.4", not text);
        Rank by int, Name/Pos case-insensitively, Value by parsed float.
        """
        self.beginResetModel()
        self._sort_key = (column, order == Qt.SortOrder.AscendingOrder)
        self._rebuild()
        self.endResetModel()

    def _row_sort_key(self, row: dict[str, str], col: int, ascending: bool = True):
        """Sortable key of a pool row for column ``col``.

        ``None`` (missing stat) sorts LAST in both directions via the
        ``(1,)`` sentinel — an unparseable z is unknown, not zero. The
        numeric value is negated for descending sorts (not a ``reverse``
        pass, which would flip the sentinel to the front).
        """
        if col == 0:
            return (row.get("name", "") or "").casefold()
        if col == 1:
            return (row.get("pos", "") or "").casefold()

        def _num(field: str):
            value = _parse_z(row.get(field, ""))
            if value is None:
                return (1,)
            return (0, -value if not ascending else value)

        if col == 2:
            return _num("value")
        if col == 3:
            return _num("rank")
        return _num(CAT_Z_COLUMN[tuple(CAT_Z_COLUMN)[col - len(self.BASE_COLUMNS)]])

    def _rebuild(self) -> None:
        visible = [
            row
            for row in self._all
            if not self._pos_filter
            or (row.get("pos", "") or "").split("/")[0].strip() == self._pos_filter
        ]
        if self._sort_key is not None:
            column, ascending = self._sort_key
            key = self._row_sort_key
            visible = sorted(visible, key=lambda r: key(r, column, ascending))
        self._visible = visible
        # Precompute per-row display text + stat colors so data() is a flat
        # lookup. Re-polishing a QTableView on every theme toggle used to
        # re-invoke data() ~57k times (parse + erf-based stat_color per cell);
        # precomputing turns the restyle into ~0 Python calls.
        cats = tuple(CAT_Z_COLUMN)
        self._text_rows: list[tuple[str, ...]] = []
        self._z_rows: list[tuple[tuple[str, float | None], ...]] = []
        for row in self._visible:
            base = tuple(
                (row.get(key, "") or "").strip()
                for key in ("name", "pos", "value", "rank")
            )
            z_row: list[tuple[str, float | None]] = []
            stat_texts: list[str] = []
            for cat in cats:
                z = _parse_z(row.get(CAT_Z_COLUMN[cat], ""))
                z_row.append((cat, z))
                stat_texts.append("" if z is None else f"{z:+.1f}")
            self._text_rows.append(base + tuple(stat_texts))
            self._z_rows.append(tuple(z_row))
        self._recompute_colors()

    def _recompute_colors(self) -> None:
        self._colors: list[tuple[QBrush | None, ...]] = []
        for z_row in self._z_rows:
            row_brushes: list[QBrush | None] = []
            for cat, z in z_row:
                if z is None:
                    row_brushes.append(None)
                    continue
                color = stat_color(
                    z, lower_is_better=DIRECTIONS[cat] == "lower", theme=self._theme
                )
                row_brushes.append(None if color.alpha() == 0 else QBrush(color))
            self._colors.append(tuple(row_brushes))

    def set_theme(self, theme_name: str) -> None:
        """Recolor stat cells on a theme switch without rebuilding the pool."""
        if theme_name == self._theme:
            return
        self._theme = theme_name
        self._recompute_colors()
        if self._visible:
            last = len(self._visible) - 1
            self.dataChanged.emit(
                self.index(0, 0),
                self.index(last, self.columnCount() - 1),
                [Qt.ItemDataRole.BackgroundRole],
            )

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
        row_i = index.row()
        col = index.column()
        if col < len(self.BASE_COLUMNS):
            # text cells: Display/Edit ONLY — returning text for every role
            # leaked into CheckStateRole, which made digit cells (rank "1",
            # "2") render with checkbox indicators
            if role not in (
                Qt.ItemDataRole.DisplayRole,
                Qt.ItemDataRole.EditRole,
            ):
                return None
            return self._text_rows[row_i][col]
        if role == Qt.ItemDataRole.DisplayRole:
            return self._text_rows[row_i][col]
        if role == Qt.ItemDataRole.BackgroundRole:
            return self._colors[row_i][col - len(self.BASE_COLUMNS)]
        return None

    def name_at(self, row: int) -> str:
        """Pool name of model row ``row`` (for logging a selected player)."""
        return self._visible[row]["name"]

    def header_text(self, col: int) -> str:
        """Header label of column ``col`` (base columns, then CAT_LABELS)."""
        if col < len(self.BASE_COLUMNS):
            return self.BASE_COLUMNS[col]
        return CAT_LABELS[tuple(CAT_Z_COLUMN)[col - len(self.BASE_COLUMNS)]]

    def widest_text(self, col: int) -> str:
        """Longest display text in column ``col`` (header included).

        Used by the view to compute a font-metric column width —
        ``resizeColumnToContents`` under-measures the stylesheet's mono
        font and clipped cells/headers (e.g. "+3..", "alu").
        """
        best = self.header_text(col)
        for row in self._text_rows:
            if len(row[col]) > len(best):
                best = row[col]
        return best


def _parse_z(text: str) -> float | None:
    """Parsed z-score; None when the cell is blank OR unparseable.

    An unparseable cell is unknown, not zero (matches ``_row_sort_key``'s
    contract) — it renders empty and sorts last in both directions.
    """
    stripped = str(text or "").strip()
    if not stripped:
        return None
    try:
        return float(stripped)
    except ValueError:
        return None


def _primary_pos(row: dict[str, str]) -> str:
    return (row.get("pos", "") or "").split("/")[0].strip()


class _PoolSearchFilter(QSortFilterProxyModel):
    """Substring (case-insensitive) filter over the pool-names model.

    QCompleter's built-in matching is prefix-only; this proxy does the
    real filtering so the dropdown shows partial matches ("jok" →
    "Nikola Jokic") as the user types. QCompleter can't do this: with a
    neutralized (empty) prefix it neither sets the line edit's text nor
    fires its activated signal, so the board owns a small QListView
    popup instead (see DraftBoard.__init__).
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._query = ""

    def set_query(self, query: str) -> None:
        self._query = (query or "").lower()
        # begin/endResetModel re-runs filterAcceptsRow for every row.
        # (invalidateFilter() used to be the cheap path, but Qt 6.11
        # deprecated it and it no longer re-applies the filter — the
        # popup then silently listed ALL players, not just matches.)
        self.beginResetModel()
        self.endResetModel()

    def filterAcceptsRow(self, row: int, parent: QModelIndex) -> bool:  # noqa: N802
        if not self._query:
            return True
        source = self.sourceModel()
        name = (source.data(source.index(row, 0)) or "").lower()
        return self._query in name

    def matched_names(self) -> list[str]:
        """Filtered names (the dropdown's current rows)."""
        return [
            str(self.data(self.index(r, 0))) for r in range(self.rowCount())
        ]


class DraftBoard(QWidget):
    """Autodraft-oriented draft helper: strip + players + relative +
    rosters on the left.

    The snake order lives in ``self.snake`` (14 rounds x teams, even
    rounds reversed — ``_order_of`` mirrors ``league.snake_order``);
    keeper forfeits are shown in the roster panel and consume overall
    pick numbers. Logging a pick (typed name via the partial-match
    dropdown, or double-click) and undoing both persist and re-render
    every panel.
    """

    #: emitted when the user clicks "Setup…" — the host view opens the
    #: SetupDialog (teams/order/keepers/my-team) and refreshes on accept.
    setup_requested = Signal()

    #: Search dropdown height cap (rows); beyond this the popup's own
    #: vertical scrollbar takes over.
    SEARCH_POPUP_MAX_ROWS = 8

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

        # The board owns ALL banners (offline notice + danger alerts) —
        # the draft page's copy of the offline banner was removed
        # (overhaul 3) because both showed identical text and rendered
        # twice in the same window.
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

        # Two columns: left = pick strip + pool table (the scrollable
        # priority surface, keeps all leftover width); right = a fixed
        # width rail (recommendations → comparison → roster, each at
        # content size) that scrolls vertically.
        row = QHBoxLayout()
        root.addLayout(row, 1)

        self.left_panel = QWidget()
        self.left_panel.setObjectName("panel")
        # The pool keeps all leftover window width (a wider window shows
        # more of the table's empty right margin, not dead canvas); the
        # rail is content-width (see _sync_panel_widths).
        self.left_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        row.addWidget(self.left_panel, 1)
        inner = QVBoxLayout(self.left_panel)
        inner.setContentsMargins(8, 8, 8, 8)
        inner.setSpacing(8)

        # --- current-pick strip (one horizontal row: label, entry, buttons) ---
        strip_row = QHBoxLayout()
        self.current_label = QLabel("")
        self.current_label.setObjectName("secondary")
        strip_row.addWidget(self.current_label, 0)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("player name (partial match — or double-click the table)")
        strip_row.addWidget(self.name_edit, 1)
        # Live partial-match dropdown: a QListView popup over the proxy
        # filter (QCompleter can't substring-match AND autofill — its
        # activated path replaces the completion prefix, not the typed
        # query). Typing populates the list; clicking a row (or Enter on
        # the popup) fills the edit; the edit's own Enter commits the pick.
        self._names_model = QStandardItemModel(self)
        self._search_filter = _PoolSearchFilter(self)
        self._search_filter.setSourceModel(self._names_model)
        self.search_popup = QListView(self)
        self.search_popup.setModel(self._search_filter)
        self.search_popup.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        # No Qt.Popup flag: a popup window grabs keyboard focus on show(),
        # which fires the edit's FocusOut and the event filter below hides
        # the popup before it is ever visible. Frameless + the focus-out
        # filter give the same close-on-click-away behavior.
        self.search_popup.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        # A parented top-level (no Qt.Popup) starts VISIBLE when the board
        # first shows — briefly painting the name list at (0,0) over the
        # banner. Explicitly start it hidden; _on_search_text owns show/hide.
        self.search_popup.hide()
        self.search_popup.activated.connect(self._on_search_pick)
        self.name_edit.textChanged.connect(self._on_search_text)
        # Close the popup when the search box loses focus (tabbing away,
        # clicking elsewhere). Row clicks still work: _on_search_pick hides
        # the popup and refocuses the edit itself.
        self.name_edit.installEventFilter(self)

        self.commit_button = QPushButton("Commit pick")
        self.commit_button.setProperty("ink", "true")
        self.commit_button.clicked.connect(self._commit)
        self.name_edit.returnPressed.connect(self._commit)
        strip_row.addWidget(self.commit_button, 0)
        self.undo_button = QPushButton("Undo last")
        self.undo_button.clicked.connect(self.undo)
        strip_row.addWidget(self.undo_button, 0)
        self.setup_button = QPushButton("Setup…")
        self.setup_button.clicked.connect(self.setup_requested.emit)
        strip_row.addWidget(self.setup_button, 0)
        inner.addLayout(strip_row, 0)

        # --- available players (model-based table + POS filter) ----------------
        filter_row = QHBoxLayout()
        pos_label = QLabel("Pos")
        pos_label.setObjectName("secondary")
        filter_row.addWidget(pos_label, 0)
        self.pos_combo = QComboBox()
        self.pos_combo.setCurrentText("All")
        self.pos_combo.currentTextChanged.connect(self._pos_filter_changed)
        filter_row.addWidget(self.pos_combo, 0)
        filter_row.addStretch(1)
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
        # Fixed row height: per-row sizeHintForRow was re-derived on every
        # scroll step (measured ~0.2ms/row → ~180ms per 100 scroll steps);
        # fixed 22px rows make scrolling a flat lookup (~1ms).
        self.player_view.verticalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Fixed
        )
        self.player_view.verticalHeader().setDefaultSectionSize(22)
        # Every column is Interactive and sized to its content ONCE per pool
        # rebuild (``_fit_player_columns`` — font-metric widths). A persistent
        # ResizeToContents mode re-measured all ~200 rows on every app
        # restyle/theme toggle (~635ms of the ~750ms setStyleSheet cost);
        # and Stretch on Name would balloon it on wide windows (user
        # decision: longest-name width, leftover space stays empty).
        self.player_view.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )
        self.player_view.doubleClicked.connect(self._double_clicked)
        self.player_view.setSortingEnabled(True)
        inner.addWidget(self.player_view, 1)

        # --- right rail (recommendations → comparison → roster, scroll) ---
        self.right_rail = QScrollArea()
        right = self.right_rail
        right.setFrameShape(QFrame.Shape.NoFrame)
        right.setWidgetResizable(True)
        # Horizontal scroll only when the window is too narrow for the
        # rail's content width (fixed per render by _sync_panel_widths).
        right.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        right_col = QWidget()
        right.setWidget(right_col)
        right_inner = QVBoxLayout(right_col)
        right_inner.setContentsMargins(0, 0, 0, 0)
        right_inner.setSpacing(8)
        row.addWidget(right, 0)

        # --- recommendations panel ---------------------------------------------
        self.recs_panel = QWidget()
        self.recs_panel.setObjectName("panel")
        self.recs_panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        right_inner.addWidget(self.recs_panel, 0)
        recs_inner = QVBoxLayout(self.recs_panel)
        recs_inner.setContentsMargins(8, 8, 8, 8)
        recs_inner.setSpacing(4)
        self.recs_title = QLabel("Recommendations —")
        self.recs_title.setObjectName("title")
        recs_inner.addWidget(self.recs_title, 0)
        top_row = QHBoxLayout()
        top_label = QLabel("Top")
        top_label.setObjectName("secondary")
        top_row.addWidget(top_label, 0)
        self.top_n_spin = QSpinBox()
        self.top_n_spin.setRange(1, 20)
        self.top_n_spin.setValue(int(self.service.settings().get("rec_top_n", 10)))
        self.top_n_spin.valueChanged.connect(self._top_n_changed)
        top_row.addWidget(self.top_n_spin, 0)
        top_row.addStretch(1)
        recs_inner.addLayout(top_row, 0)
        self.recs_grid = QTableWidget(0, 5)
        self.recs_grid.setHorizontalHeaderLabels(
            ["#", "Player", "Tag", "mkt / fit", "Reason"]
        )
        self.recs_grid.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.recs_grid.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.recs_grid.verticalHeader().setVisible(False)
        # All columns content-width (Reason included) — the rail sizes to
        # its widest panel's content, so the grid must not be greedy.
        self.recs_grid.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        recs_inner.addWidget(self.recs_grid, 0)

        # --- comparison panel: my team vs the league (P3) ----------------------
        self.relative_panel = QWidget()
        self.relative_panel.setObjectName("panel")
        self.relative_panel.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum
        )
        right_inner.addWidget(self.relative_panel, 0)
        relative_inner = QVBoxLayout(self.relative_panel)
        relative_inner.setContentsMargins(8, 8, 8, 8)
        relative_inner.setSpacing(4)
        self.relative_title = QLabel("Comparison")
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
            QHeaderView.ResizeMode.ResizeToContents
        )
        relative_inner.addWidget(self.relative_grid, 0)
        self.relative_panel.setVisible(False)

        # --- roster panel (team dropdown + stat-colored roster) ----------------
        self.roster_panel = QWidget()
        self.roster_panel.setObjectName("panel")
        self.roster_panel.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum
        )
        right_inner.addWidget(self.roster_panel, 0)
        right_inner.addStretch(1)
        # No trailing row stretch: the left panel (Expanding) already claims
        # all leftover window width, so a second stretch would split it and
        # leave dead canvas to the right of the rail.
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
            QHeaderView.ResizeMode.ResizeToContents
        )
        # Content height only: the roster used to balloon to fill the
        # leftover window height (one row in a ~300px box, overhaul-3
        # screenshot). Maximum = never grows past its sizeHint.
        self.roster_grid.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum
        )
        roster_inner.addWidget(self.roster_grid, 0)
        self.roster_panel.setVisible(False)

        self.refresh()

    # -- helpers ---------------------------------------------------------------

    def _theme_name(self) -> str:
        return "dark" if self.service.settings().get("dark_mode") else "light"

    def set_theme(self, theme_name: str) -> None:
        """Recolor the players table on a theme switch (no full rebuild)."""
        self._player_model.set_theme(theme_name)

    def _pos_filter_changed(self, pos: str) -> None:
        self._player_model.set_pos_filter("" if pos == "All" else pos)
        self._fit_player_columns()

    def _fit_player_columns(self) -> None:
        """Fit every column to its content once (pool/filter change).

        Widths come from the view's font metrics over the widest cell text
        (``PlayerTableModel.widest_text`` — header included) plus margin for
        item padding; no column stretches, so leftover horizontal space
        stays empty table background. One-shot ``setColumnWidth`` keeps
        restyle/theme-toggle cost at zero.
        """
        # Measure with the theme's actual cell font — the view's inherited
        # application font is NOT what the QSS `*` rule renders (IBM Plex
        # Mono 13px medium runs wider), so the app font under-measures
        # every column and the z cells truncate to "+…".
        cell_font = QFont()
        cell_font.setFamily(FONT_MONO)
        cell_font.setPixelSize(int(TEXT_BASE.rstrip("px")))
        # Qt's QSS maps CSS `font-weight: 500` to QFont.Weight.Medium.
        cell_font.setWeight(QFont.Weight.Medium)
        fm = QFontMetrics(cell_font)
        for ci in range(self._player_model.columnCount()):
            width = fm.horizontalAdvance(self._player_model.widest_text(ci)) + 24
            self.player_view.setColumnWidth(ci, width)

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
            self._fit_player_columns()
            _offline.hide_banner(self.offline_banner)
            self._set_alert("Sync the league first (League → Sync now)")
            self.current_label.setText("")
            self.commit_button.setEnabled(False)
            self.undo_button.setEnabled(False)
            self.relative_panel.setVisible(False)
            self.roster_panel.setVisible(False)
            self._render_recs(None)
            self._sync_panel_widths()
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
        self._fit_player_columns()
        # Rebuild the search dropdown's source rows (excluded-aware);
        # re-apply the current query so the popup stays in sync.
        names = [n for n in self._pool.names() if n not in excluded]
        self._names_model.setRowCount(len(names))
        for i, name in enumerate(names):
            self._names_model.setItem(i, 0, QStandardItem(name))
        self._search_filter.set_query(self.name_edit.text())
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
        self._sync_panel_widths()

    def _render_strip(self) -> None:
        current = picks_mod.current_pick(self.snake, self.picks)
        total = len(self.snake)
        done = len(self.picks)
        self.commit_button.setEnabled(current is not None)
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

    def showEvent(self, event) -> None:
        # Re-size the rail once it is actually shown: the grid column widths
        # aren't polished with the theme font until show time, so a rail width
        # measured during refresh() (pre-show) under-shoots. Cheap — three
        # tiny grids.
        super().showEvent(event)
        self._sync_panel_widths()

    def eventFilter(self, obj, event) -> bool:
        """Close the search popup when the name edit loses focus."""
        if obj is self.name_edit and event.type() == QEvent.Type.FocusOut:
            self.search_popup.hide()
        return super().eventFilter(obj, event)

    def _sync_panel_widths(self) -> None:
        """Keep the right rail exactly its content width (no dead space,
        no greedy stretch): the rail is its widest panel's content width, and
        on a narrow window the rail's horizontal scrollbar takes over. The
        left panel stretches instead — the pool table keeps all leftover
        window width as empty table background (the Name-column rule).
        """
        # A panel's sizeHint() UNDER-reports its grid (QTableWidget's hint
        # is a stub, not the content) — size the rail to the widest grid's
        # actual columns + the panel chrome (margins 8x2 + border 2x2) so
        # no inner grid needs its own horizontal scrollbar. Force a
        # resize-to-contents first: the column widths lag a frame in
        # ResizeToContents mode, so a stale measurement would size the rail
        # too small. (These are tiny grids, unlike the pool table.)
        rail_w = 0
        for grid in (self.recs_grid, self.relative_grid, self.roster_grid):
            grid.resizeColumnsToContents()
            rail_w = max(
                rail_w,
                sum(grid.columnWidth(ci) for ci in range(grid.columnCount())) + 20,
            )
        self.right_rail.setFixedWidth(rail_w)

    def _sync_recs_height(self) -> None:
        """Keep the recs grid as tall as its rows: a QTableWidget's
        sizeHint covers only a handful of rows, and in the scrollable
        right rail the panel would otherwise collapse (Maximum policy
        = content size, and the content is the grid)."""
        grid = self.recs_grid
        header_h = grid.horizontalHeader().height()
        row_h = grid.verticalHeader().defaultSectionSize() or 22
        grid.setMinimumHeight(header_h + grid.rowCount() * row_h + 4)

    def _render_recs(self, report) -> None:
        """Recommendations rail: P6 scorer ordering with tag chips, a
        mkt/fit summary parsed from the scorer's reason bits, a value-gap
        badge, the list of need cats each player helps (em dash when
        unknown), and the top-N spin (persisted)."""
        grid = self.recs_grid
        grid.setRowCount(0)
        self._sync_recs_height()
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
        self._sync_recs_height()
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
            grid.setItem(
                r,
                4,
                QTableWidgetItem(
                    ", ".join(CAT_LABELS[c] for c in suggestion.cats) or "\u2014"
                ),
            )

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
    def _gp(team_rows) -> float:
        """Games played across a team's secured pool rows (0 if absent)."""
        total = 0.0
        for row in team_rows:
            try:
                total += float(row.get("gp") or 0)
            except (TypeError, ValueError):
                continue
        return total

    @staticmethod
    def _mkfit(suggestion: Suggestion) -> str:
        """'mkt X% / fit Y' from the scorer's structured fields (R4).

        ``market`` is the 0-1 rank value; ``fit_z`` is the raw weighted
        fit (see ``scorer.score_pool``) — NOT a 0-1 normalization. The
        M2.3 fallback leaves both None → em dash (unchanged).
        """
        if suggestion.market is None or suggestion.fit_z is None:
            return "—"
        return f"mkt {suggestion.market * 100:.0f}% / fit {suggestion.fit_z:+.2f}z"

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
        self.relative_title.setText(f"Comparison — {my_team}")
        # per-game values: season totals scaled by each team's games played
        # (pct cats are already rates); the league spread normalizes the
        # gap color (z-score-ish input per ``stat_color``)
        team_rows = self._team_projections(report)
        projections = {
            team: project_roster(team_rows, team)
            for team, team_rows in team_rows.items()
        }
        gps = {team: self._gp(team_rows) for team, team_rows in team_rows.items()}
        grid = self.relative_grid
        theme_name = self._theme_name()
        for c, tag in enumerate(tags):
            cat = tag.cat
            pct = cat in PCT_CATS
            per_game = {}
            for team in projections:
                value = projections[team].cat_values[cat]
                if not pct and gps[team] > 0:
                    value = value / gps[team]
                per_game[team] = value
            mine = per_game[my_team]
            med = median(per_game.values())
            # signed gap, positive = behind (matches the domain's CatTag)
            gap = (mine - med) if DIRECTIONS[cat] == "lower" else (med - mine)
            mine_t = f"{mine:.1%}" if pct else f"{mine:.2f}"
            med_t = f"{med:.1%}" if pct else f"{med:.2f}"
            gap_t = f"{gap:+.1%}" if pct else f"{gap:+.2f}"
            for r, text in enumerate([mine_t, med_t, gap_t, tag.tag]):
                grid.setItem(r, c, QTableWidgetItem(text))
            values = list(per_game.values())
            spread = max(values) - min(values)
            if spread <= 0:
                spread = 1.0
            color = stat_color(-gap / spread, theme=theme_name)
            if color.alpha() != 0:
                for r in (0, 2):
                    item = grid.item(r, c)
                    if item is not None:
                        item.setBackground(QBrush(color))

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

        Shared by the pick-name search dropdown and the recommendations rail.
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

    def _on_search_text(self, text: str) -> None:
        """Re-filter the dropdown on every keystroke and pop it open.

        Re-emitting the query through ``set_query`` is a no-op for an
        unchanged filter (invalidateFilter), so autofill from a click
        doesn't re-pop the popup.
        """
        self._search_filter.set_query(text)
        names = self._search_filter.matched_names()
        if text and names:
            # The popup is a CHILD of the board, so position it in board
            # coordinates — mapToGlobal used to double the board's own
            # offset on a maximized window (popup landed mid-screen).
            self.search_popup.setFixedWidth(self.name_edit.width() + 4)
            # Fixed width but NO fixed height → Qt used the sizeHint's
            # minimum, a single row. Show up to SEARCH_POPUP_MAX_ROWS rows;
            # beyond that the popup's own scrollbar takes over.
            row_h = max(
                self.search_popup.sizeHintForRow(0),
                self.search_popup.fontMetrics().height() + 2,
            )
            rows = min(len(names), self.SEARCH_POPUP_MAX_ROWS)
            self.search_popup.setFixedHeight(rows * row_h + 4)
            self.search_popup.move(
                self.name_edit.mapTo(self, QPoint(0, self.name_edit.height()))
            )
            self.search_popup.show()
        else:
            self.search_popup.hide()

    def _on_search_pick(self, index: QModelIndex) -> None:
        """Autofill the search bar with the clicked dropdown entry."""
        self.name_edit.setText(str(self._search_filter.data(index)))
        self.search_popup.hide()
        self.name_edit.setFocus()

    def _commit(self) -> None:
        self.search_popup.hide()
        self._log(self.name_edit.text().strip())

    def log_selected(self) -> None:
        """Log the player table's selected row (double-click)."""
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
