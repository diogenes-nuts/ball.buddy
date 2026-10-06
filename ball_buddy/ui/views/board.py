"""Draft board (M2.2): 13-round snake grid with pick entry + undo.

Keeper-forfeit-aware: forfeited picks are derived from the keeper entries
(single source of truth — they are never stored in draft_picks.json).
Entering a pick and undoing both persist atomically via
``domain/picks.py`` (``io/state.py``). Theme tokens only
(``panel``/``banner-info``/``banner-danger``/``secondary``/``title``/ink
buttons); the
current-pick cell uses stock Qt selection highlight.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCompleter,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ball_buddy.domain import picks as picks_mod
from ball_buddy.domain.keepers import KeeperEntry
from ball_buddy.domain.league import Pick
from ball_buddy.domain.naming import bridge
from ball_buddy.domain.players import PlayerPool
from ball_buddy.domain.recommend import recommend
from ball_buddy.services.sync import SyncService
from ball_buddy.ui.views import _offline


class DraftBoard(QWidget):
    """Snake draft grid: current-pick strip on top, 13 x teams table below.

    Column *c* of round *r* holds the team at snake position (r, c+1), so
    round 1 reads in start order and each row snakes left-right.
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

        panel = QWidget()
        panel.setObjectName("panel")
        root.addWidget(panel, 1)
        inner = QVBoxLayout(panel)
        inner.setContentsMargins(8, 8, 8, 8)
        inner.setSpacing(8)

        # --- current-pick strip ------------------------------------------------
        strip = QVBoxLayout()
        self.current_label = QLabel("")
        self.current_label.setObjectName("secondary")
        strip.addWidget(self.current_label)

        controls = QVBoxLayout()
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("player name")
        controls.addWidget(self.name_edit)

        buttons = QVBoxLayout()
        buttons.setSpacing(4)
        self.commit_button = QPushButton("Commit pick")
        self.commit_button.setProperty("ink", "true")
        self.commit_button.clicked.connect(self._commit)
        self.name_edit.returnPressed.connect(self._commit)
        buttons.addWidget(self.commit_button)
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

        # --- grid ----------------------------------------------------------------
        self.grid = QTableWidget(0, 0)
        self.grid.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.grid.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.grid.verticalHeader().setVisible(False)
        self.grid.horizontalHeader().setVisible(False)
        self.grid.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.grid.cellClicked.connect(self._cell_clicked)
        inner.addWidget(self.grid, 1)

        # --- suggested top-N pool players (M2.3) ---------------------------------
        suggest_panel = QWidget()
        suggest_panel.setObjectName("panel")
        inner.addWidget(suggest_panel, 0)
        suggest_inner = QVBoxLayout(suggest_panel)
        suggest_inner.setContentsMargins(8, 8, 8, 8)
        suggest_inner.setSpacing(4)
        self.suggest_title = QLabel("Suggested pool players")
        self.suggest_title.setObjectName("title")
        suggest_inner.addWidget(self.suggest_title)
        self.suggest_grid = QTableWidget(0, 4)
        self.suggest_grid.setHorizontalHeaderLabels(["Player", "Pos", "Value", "Rank"])
        self.suggest_grid.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.suggest_grid.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.suggest_grid.verticalHeader().setVisible(False)
        self.suggest_grid.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.suggest_grid.setMaximumHeight(140)
        suggest_inner.addWidget(self.suggest_grid, 0)

        self.refresh()

    # -- data loading ----------------------------------------------------------

    def refresh(self) -> None:
        """Rebuild the grid from the effective snapshot + keepers + saved picks.

        The effective snapshot is the last Yahoo snapshot when one exists,
        else the manual team list from Settings (offline draft-day mode).
        """
        snapshot = self.service.effective_snapshot()
        if snapshot is None:
            self.start_order = []
            self.snake = []
            self.picks = []
            self.grid.setRowCount(0)
            self.grid.setColumnCount(0)
            _offline.hide_banner(self.offline_banner)
            self._set_alert("Sync the league first (League → Sync now)")
            self.current_label.setText("")
            self.commit_button.setEnabled(False)
            self.undo_button.setEnabled(False)
            self._render_suggestions()
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
        """Redraw the grid, strip, and suggest panel from self.snake / self.picks."""
        teams = len(self.start_order)
        if not teams:
            return
        rows = len({pick.round for pick in self.snake})
        self.grid.setRowCount(rows)
        self.grid.setColumnCount(teams)
        entered = {(pick.round, pick.slot): pick for pick in self.picks}
        report = bridge(
            [pick.player for pick in self.picks],
            self._pool.names(),
            self.service.load_aliases(),
        )
        self.name_edit.setCompleter(
            QCompleter(
                [n for n in self._pool.names() if n not in self._excluded_names(report)]
            )
        )
        for pick in self.snake:
            r, c = pick.round - 1, pick.order - 1
            if pick.forfeited:
                text = f"Keeper: {self._keeper_cells.get((pick.round, pick.order), '?')}"
            else:
                entered_pick = entered.get((pick.round, pick.order))
                if entered_pick is None:
                    text = ""
                else:
                    value = self._value_of(
                        entered_pick.player, report.matched.get(entered_pick.player)
                    )
                    text = (
                        f"{entered_pick.player} ({value})" if value else entered_pick.player
                    )
            self.grid.setItem(r, c, QTableWidgetItem(text))
        self._render_strip()
        self._render_suggestions(report)

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
            f"Round {current.round}, pick {current.order} of "
            f"{len(self.start_order)} — {current.team} — overall "
            f"{current.overall}/{total}"
        )
        grid_row, grid_col = current.round - 1, current.order - 1
        self.grid.setCurrentCell(grid_row, grid_col)
        self.grid.selectRow(grid_row)

    def _render_suggestions(self, report=None) -> None:
        """Top-N pool players (rank order) minus drafted/kept, in the panel."""
        if report is None:
            report = bridge(
                [pick.player for pick in self.picks],
                self._pool.names(),
                self.service.load_aliases(),
            )
        grid = self.suggest_grid
        if not self._pool.rows:
            self.suggest_title.setText("Suggested pool players —")
            grid.setRowCount(0)
            return
        if picks_mod.current_pick(self.snake, self.picks) is None:
            self.suggest_title.setText("Suggested pool players — draft complete")
            grid.setRowCount(0)
            return
        suggestions = recommend(self._pool.rows, self._excluded_names(report))
        self.suggest_title.setText(f"Suggested pool players (top {len(suggestions)})")
        grid.setRowCount(len(suggestions))
        for r, suggestion in enumerate(suggestions):
            for c, text in enumerate(
                [
                    suggestion.name,
                    suggestion.pos,
                    suggestion.value,
                    str(suggestion.rank) if suggestion.rank is not None else "—",
                ]
            ):
                grid.setItem(r, c, QTableWidgetItem(text))

    def _value_of(self, entered_name: str, bridged: str | None) -> str:
        row = self._pool.get(bridged or entered_name)
        return (row or {}).get("value", "") or ""

    def _excluded_names(self, report=None) -> set[str]:
        """Names to keep out of suggestions: drafted/kept + bridged pool names.

        Shared by the pick-name completer and the M2.3 suggest panel. With a
        ``report`` (bridged picks) its matched pairs exclude both sides;
        without one the raw entered pick names are used directly. Opted-out
        keepers are excluded from the forfeited-pick grid but their player
        stays draftable, so they remain suggestable.
        """
        excluded = {entry.player for entry in self.keepers if not entry.opted_out}
        if report is None:
            excluded |= {pick.player for pick in self.picks}
        else:
            excluded |= set(report.matched)
            excluded |= set(report.matched.values())
        return excluded

    def _poolable_names(self, report=None) -> list[str]:
        """Pool names minus already-drafted / kept player names."""
        excluded = self._excluded_names(report)
        return [name for name in self._pool.names() if name not in excluded]

    # -- actions -----------------------------------------------------------------

    def _set_alert(self, text: str) -> None:
        self.alert_banner.setText(text)
        self.alert_banner.setVisible(bool(text))

    def _commit(self) -> None:
        current = picks_mod.current_pick(self.snake, self.picks)
        if current is None:
            self._set_alert("Draft complete — nothing left to pick.")
            return
        name = self.name_edit.text().strip()
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

    def _cell_clicked(self, row: int, col: int) -> None:
        """Jump to a cell's pick only if it is the earliest open pick."""
        if not (0 <= row < self.grid.rowCount() and 0 <= col < self.grid.columnCount()):
            return
        pick = self.snake[row * len(self.start_order) + col]
        current = picks_mod.current_pick(self.snake, self.picks)
        if current is not None and (pick.round, pick.order) == (
            current.round,
            current.order,
        ):
            self.render()  # re-highlight; no skipping ahead


__all__ = ["DraftBoard"]
