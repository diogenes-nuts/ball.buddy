## Goal
Add a Setup dialog (P1, 006_board) that edits draft order, team names, keepers, and MY team, persisting to existing stores so `board.py` works unchanged; retire the duplicate manual-team/keeper surfaces.

## Plan

1. **New `ball_buddy/ui/views/setup_dialog.py`** — `class SetupDialog(QDialog)`:
   - `__init__(self, service: SyncService, parent: QWidget | None = None)` — load `settings = service.settings()`, `teams = settings.get("manual_teams") or []` (fallback: `effective_snapshot()` team names so it's usable in live mode), `keepers = keepers_mod.load(service.data_dir / keepers_mod.KEEPERS_FILE)`, `my_team = settings.get("my_team", "")`.
   - Teams table: `QTableWidget` cols `("Team" editable, "My team" QCheckBox)` + Add/Remove/Up/Down `QPushButton`s. Keepers table: cols `("Team" QComboBox, "Player" QLineEdit+QCompleter over `PlayerPool.load(service.pool_path).names()``, "Cost round" QSpinBox 1..`MAX_COST_ROUND`(13), "Opt out" QCheckBox, "Status")` + Add/Remove.
   - `def _save(self) -> None`: entries from keepers table; `resolved = keepers_mod.resolve(entries, pool.names(), service.load_aliases())`; `errors = keepers_mod.validate(entries, team_names, resolved)` → if errors, `banner-danger` label + return (no accept). Else: `settings["manual_teams"] = ordered_names`; `settings["manual_draft_order"] = ordered_names`; `settings["my_team"] = name of checked row or ""`; `service.save_settings(settings)`; `keepers_mod.save(entries, service.data_dir / keepers_mod.KEEPERS_FILE)`; `self.accept()`. Save/Cancel via `QDialogButtonBox` (pattern: league.py:58 SettingsDialog).
2. **`board.py`**: `DraftBoard` gets `setup_requested = Signal()` and a "Setup…" `QPushButton` in the controls block (board.py:60-78); click emits the signal. No other board changes.
3. **`draft.py`**: delete the keeper grid (`self.table`, `_add_row`, `_rows`, `_entries_from_grid`, `update_statuses`, `_update_alert`, `_resolved`, `_save`, save_button) → replace with a one-line `QLabel` pointer ("Draft order, team names, and keepers: use Setup on the draft board below."). Keep embedded board + `refresh()` (still loads snapshot + keepers.json → `_rebuild_board(saved)`). Connect `self.board.setup_requested` in `_rebuild_board` to `self._open_setup`: `if SetupDialog(self.service, self).exec() == QDialog.DialogCode.Accepted: self.refresh()`.
4. **`league.py`**: remove `manual_teams_edit` + note + the `settings["manual_teams"] = ...` line from `SettingsDialog` (league.py:88-101, :148-151). Leave the League view's up/down `manual_draft_order` editor (league.py:335-360) — it's the live-mode fallback, not a duplicate of the dialog.
5. **Team resolution (verify, no change needed)**: offline `effective_snapshot` (sync.py:200) → `manual_snapshot(manual_teams)` (snapshot.py:214): team list order = `manual_teams` order, `draft.order=[]`; board's `start_order_for` (picks.py:123) falls to `manual_draft_order` merged with team names — both written in order → order renames flow. Keepers flow via `draft.refresh()` → `_rebuild_board(saved)` → `DraftBoard(service, keepers)`; `(teams, saved)` key (draft.py:195) forces rebuild on rename/keeper change. Real Yahoo snapshots ignore `manual_teams` (sync.py:203) — renames are manual-mode only; order edits only affect the fallback order.

## Files
- new `ball_buddy/ui/views/setup_dialog.py`; `ball_buddy/ui/views/board.py` (signal+button); `ball_buddy/ui/views/draft.py` (grid→pointer, `_open_setup`); `ball_buddy/ui/views/league.py` (remove `manual_teams_edit`); new `tests/ui/test_setup_dialog.py`; check `tests/ui/test_draft*.py`/`test_league*.py` for removed widgets and update.

## Tests (offscreen, pattern: tests/ui/test_board.py — QT_QPA_PLATFORM=offscreen, module `qapp`, `make_service(tmp_path)`, manual mode: `save_settings` with `manual_teams`, `write_csv` pool)
- order: reorder+rename in dialog, Save → `settings["manual_teams"]`/`manual_draft_order` new order → `DraftBoard.refresh()` `start_order` matches; MY team checked → `settings["my_team"]`.
- keepers: add row Save → `keepers_mod.load` has entry, board cell shows "Keeper: X"; remove row Save → gone; opt-out → pick not forfeited.
- validation: two active keepers same cost round → alert shown, `exec`/Save does not persist, dialog not accepted.

## Risks
- Board widget re-added to layout on rebuild — `setParent(None)` then `addWidget` is safe, but the signal connect must happen each rebuild (draft.py `_rebuild_board`).
- `my_team` is new/unused by other views (lineups/waivers/trades pickers) — additive, no migration.
- Round count: use 13 (`MAX_COST_ROUND`), ignore picks.py:17-18 docstring discrepancy.
- Verify no existing test references `manual_teams_edit` or the draft table before deletion.

## Finish
`.venv\Scripts\pytest` + `.venv\Scripts\ruff check .` green.

Meatbag, plan's ready — the scout's findings check out (I re-verified `effective_snapshot`/`start_order_for`/keepers flow); no service or snapshot-doc changes are needed at all.