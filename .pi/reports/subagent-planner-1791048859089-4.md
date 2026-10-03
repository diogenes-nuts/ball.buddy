## Goal
Add the M2.2 snake draft board (13-round, keeper-forfeit-aware, pick entry + undo, atomic persistence) as a new domain module, a board widget, and its UI section in DraftView.

## Plan
1. **New `ball_buddy/domain/picks.py`** (mirrors `domain/keepers.py` style):
   - `PICKS_VERSION = 1`, `PICKS_FILE = "draft_picks.json"`.
   - `@dataclass(frozen=True) DraftPick: round: int; slot: int; team: str; player: str` (player = entered name, non-empty; **forfeited picks are NOT stored** — derived from keepers, single source of truth).
   - `load(path) -> list[DraftPick]`, `save(picks, path)` via `io/state.py` (same contract as `keepers.load/save`).
   - `keeper_forfeits(entries: list[KeeperEntry]) -> set[tuple[str, int]]` — only `not opted_out` keepers.
   - `build_snake(start_order: list[str], entries: list[KeeperEntry], rounds: int = keepers_mod.MAX_COST_ROUND) -> list[league.Pick]` — constructs a minimal `LeagueConfig(teams=start_order, start_order=..., rounds=13, games_per_week=3.5, slots=(), categories=(), weights={}, keepers=tuple(Keeper(t, p, cr) for non-opted-out entries))` exactly as `views/league.py:342-350` does, then returns `league.snake_order(config)`.
   - `start_order_for(snapshot: dict | None, settings: dict) -> list[str]` — priority: `snapshot["draft"]["order"]` (team-id→name via `teams`) → `settings["manual_draft_order"]` merged per `_manual_order_for` (drop stale, append new in snapshot order) → snapshot team order.
   - `current_pick(snake: list[league.Pick], picks: list[DraftPick]) -> league.Pick | None` — first pick in snake order that is not forfeited and has no entered DraftPick (None = draft complete).

2. **New `ball_buddy/ui/views/board.py`** — `class DraftBoard(QWidget)`, constructor `(service: SyncService, keepers: list[KeeperEntry])`. Theme: object names `panel`/`banner`/`banner-alert`/`secondary`/`title`, `setProperty("ink","true")` on primary buttons — tokens only.
   - **Current-pick strip** (top, in a `panel`): QLabel `secondary` ("Round 3, pick 7 of 12 — Blue — overall 23/156") + `QLineEdit` with `QCompleter` over pool names minus already-drafted names + "Commit pick" (`ink`) + "Undo last" buttons.
   - **Grid** `QTableWidget(13, len(start_order))`: column *c* of round *r* = team at snake position (r, c+1) (i.e. round 1 column order = start order, so the snake snakes left-right per row). Cell text: forfeited → `Keeper: <player>`; picked → `<player> (<value>)` where value from `PlayerPool.get(bridged).get("value")` if non-empty (bridge entered names via `naming.bridge` once per render, aliases from `service.load_aliases()`); open → `""`. Current pick cell: `grid.setCurrentCell(r-1, c-1)` + `selectRow` (stock Qt highlight, no new token).
   - `commit(name)`: reject empty / already-picked / forfeited current pick; resolve via bridge (unmatched allowed, flagged in `banner-alert` as in DraftView); append `DraftPick(current.round, current.order, current.team, name)`, `save_json` via `picks_mod.save`, re-render (current advances automatically).
   - `undo()`: drop last element of the picks list, save, re-render.
   - `cellClicked(r, c)` → jump: set current to that pick **only if it is the earliest open pick** (no skipping ahead) — re-render.
   - State stored on the widget: `self.picks: list[DraftPick]`, `self.snake`, `self.start_order`, `self.picks_path = service.data_dir / "draft_picks.json"`. No-snapshot → banner-alert "Sync the league first".

3. **Edit `ball_buddy/ui/views/draft.py`**: after the existing keeper panel, add the board: in `refresh()`, after computing `self.teams`, load saved keepers (already read in `refresh`) + `picks_mod.load` and build `self.board = DraftBoard(self.service, saved_keepers)`; re-init the board in `refresh()` when teams/keepers change. Keeper section keeps its current layout; add a "Draft board" title label above the new widget.

4. **Tests** (no new deps):
   - `tests/domain/test_picks.py`:
     - 12-team × 13-round snake: 156 picks; round 1 = start order, round 2 exactly reversed, round 3 = start order; `overall` sequential.
     - Forfeits: active keeper at (T, 3) → that pick `forfeited=True`; opted-out keeper → pick open; two active keepers different rounds → both forfeited.
     - `current_pick`: skips forfeited + entered; None when all open picks entered.
     - `start_order_for`: live order wins; manual order merges/drops-stale/appends-new; fallback to snapshot order.
     - `load`/`save` round-trip incl. missing-file → `[]`, version mismatch → `StateError`.
   - `tests/ui/test_board.py` (offscreen, reuse `make_view`/`save_fixture_snapshot`/`write_pool` pattern from `tests/ui/test_draft_view.py`, 2-team fixture):
     - 13×2 grid renders; keeper at round 1 (Red) shows `Keeper: X` and current pick starts at R1 pick 2.
     - Enter name + commit → `draft_picks.json` written (reload via `picks_mod.load`), cell shows name, current advances past it.
     - Undo → file has one fewer pick, cell blank again, current moves back.
     - Picked cell shows `(value)` when pool row has `value`.
     - DraftView still renders with board embedded (existing tests keep passing).

## Files to Modify
- `ball_buddy/ui/views/draft.py` — embed `DraftBoard` below keeper grid, feed it saved keepers.

## New Files
- `ball_buddy/domain/picks.py` — DraftPick model, snake/forfeit/order computation, atomic persistence.
- `ball_buddy/ui/views/board.py` — DraftBoard widget.
- `tests/domain/test_picks.py`, `tests/ui/test_board.py`.

## Risks
- **SPEC §1.1 says 13 rounds; `views/league.py:34` has `DRAFT_ROUNDS = 14`** (roster-size comment). Board hardcodes 13 via `keepers_mod.MAX_COST_ROUND` per SPEC §1.1 — do not "fix" league.py's 14 in this slice; flag it.
- Don't reuse `league.Keeper` validation for entries (keeper entries are already validated in M2.1); `build_snake` maps them without re-validating.
- Column-rotated grid (snake left-right per row) makes column index ≠ fixed team — cell-click mapping must go through `snake[r*teams + c]`, not the team name.
- Existing `test_draft_view.py` fixtures construct `DraftView(service)` — adding the board in `__init__`/`refresh` must not break no-snapshot path (board shows only the alert banner).

Report to Meatbag: plan above is final and worker-ready.