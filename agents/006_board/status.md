# 006_board — status

Draft-day board (first feature per SPEC §1.2). **M2 complete** (M2.1 keepers, M2.2 snake board, M2.3 recommender).

## Files

- `ball_buddy/domain/keepers.py` — keeper model: team, player (pool-bridged via `naming`), cost round (1–13), `opted_out`. Opt-out semantics per SPEC §1.1: player back to pool eligibility, cost-round pick back to team. Validation: max 2 active keepers/team, cost round 1–13, no duplicate player.
- `ball_buddy/domain/picks.py` (or wherever M2.2 placed the pick model — see git) — pick model: round, snake order, team, player (pool-bridged or null), forfeited flag.
- `data/keepers.json`, `data/draft_picks.json` (gitignored) — atomic persistence via `io/state.py`.
- `ball_buddy/ui/views/setup_dialog.py` — Setup dialog (P1): teams & draft-order table (rename rows, Add/Remove/Move up/down, "My team" checkbox), keepers table (team combo, player + pool completer, cost round 1–13, opt-out, resolved/UNMATCHED status), Save/Cancel via QDialogButtonBox. `keepers_mod.validate` errors show a banner-danger and block Save, as do empty and duplicate team names (the board indexes picks by name); unmatched/ambiguous names are flagged in the Status column (unmatched shows "try <suggestions>", ambiguous lists candidates) but still saved. Writes `settings["manual_teams"]` + `settings["manual_draft_order"]` (same ordered list) + `settings["my_team"]` and data/keepers.json — the stores `board.py` already reads, so the board works unchanged. Corrupt keepers.json refuses Save (won't clobber). No manual teams yet (live mode): seeds the team list from `effective_snapshot()`.
- `ball_buddy/ui/views/draft.py` — draft page: offline banner, over-cap (2/team) keepers.json drop alert, embedded board; keeper entry grid removed in favor of a pointer to Setup (the duplicate manual-team surface in League Settings was also removed). `_rebuild_board` reconnects the board's `setup_requested` signal on every rebuild.
- `ball_buddy/ui/views/board.py` — snake board: 13 rounds x 12 picks grid, snake order (`_order_of` mirrors `league.snake_order`; even rounds reversed), keeper forfeits shown as "Keeper: <name>" (opted-out keepers leave the pick open), current pick highlighted (first unentered open pick; forfeits consume overall numbers), pick entry with pool lookup + quick commit, undo-last, tab/click navigation.
- `tests/ui/test_board.py` — snake math, forfeited computation (odd + even rounds, opted-out), pick persistence + undo, offscreen UI tests.
- `tests/ui/test_setup_dialog.py` — Setup dialog: reorder/rename + my-team persistence → board `start_order` follows, keeper add/remove/opt-out round-trip to keepers.json + board cells, validate errors (same round, >2/team) block Save without persisting, corrupt keepers.json refuses save, live-mode team seeding from the snapshot, empty/duplicate team names block Save, UNMATCHED status carries "try <suggestions>" hints.

## Recommender (M2.3)

- `ball_buddy/domain/recommend.py` — per-pick top-N from real pool columns (`rank`, `value`, `pos`, `name`); excludes drafted picks + active keepers; **opted-out keepers stay draftable/suggestable** (their pick isn't forfeited); unranked rows carry `rank=None` → UI "—" (no invented numbers).
- Suggestion panel in `board.py` updates per current pick; alias bridging both sides.

## Setup dialog (P1)

`DraftBoard` gained a `setup_requested` Signal + a "Setup…" button in the controls block; `DraftView` opens `SetupDialog` on it and calls `refresh()` on accept — the `(teams, saved)` key in `_rebuild_board` forces a board rebuild on rename/keeper changes, which is how order/renames/keepers flow to the board. Team row order in the dialog IS the draft start order: offline `effective_snapshot` → `manual_snapshot(manual_teams)` keeps team order = list order with `draft.order=[]`, and `picks.start_order_for` falls back to `manual_draft_order` (same ordered list, both written by the dialog). Real Yahoo snapshots always win: renames are manual-mode only, and order edits only affect the fallback order when Yahoo gives no live order (the League view's up/down editor remains the live-mode fallback for that case). `settings["my_team"]` is additive — no other view reads it yet (lineups/waivers/trades pickers).

## Offline mode (manual team list)

`board.py` and `draft.py` (embedded board) resolve teams from `SyncService.effective_snapshot()` (see `agents/002_yahoo/status.md` "Offline mode"): the last Yahoo snapshot when one exists, else a synthetic doc from `settings["manual_teams"]` (edited via Draft -> Setup; the old League -> Settings "Team list (offline)" field was removed). A shared "Offline - manual team list" banner (`ball_buddy/ui/views/_offline.py`) is shown while in manual mode; no teams at all -> the old "Sync the league first" alert. Everything else is unchanged: keepers from `keepers.json`, snake math, commits/undo, suggestions.

Plans: dev.md. History: git log; done.md.
