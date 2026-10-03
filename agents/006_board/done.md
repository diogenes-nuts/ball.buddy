# 006_board — done

## 2026-10-03 — M2.1 — Keeper entry (slice 1/3 of draft board): keepers domain model (team, pool-bridged player, cost round, opt-out), atomic persistence to data/keepers.json, bulk entry grid in Draft view (24 keepers, per-team cap validation, loud unmatched flags, cap-drop alert). 128 tests green, ruff clean.

- `domain/keepers.py`: model + validation (max 2 active/team, cost round 1–13, duplicate player across teams = error); opt-out semantics (player back to pool, pick back to team).
- `data/keepers.json` via `io/state.py` atomic save/load; corrupt >2-per-team files → loud cap-drop alert, no silent loss.
- `ui/views/draft.py`: entry grid (team, player + pool lookup, cost round, opt-out), per-row resolved/unmatched status, save flow; pool loaded once per refresh (no N+1).
- Post-review fixes: silent cap-drop surfaced via banner-alert; pool-load N+1 removed.
- Verify: 128 passed / 1 skipped, ruff clean, offscreen smoke OK (save → round-trip → unmatched flag → cap-drop alert).

## 2026-10-03 — M2.2 — Snake draft board view (slice 2/3): 12-team snake order with keeper-aware forfeited picks (opted-out keepers leave picks open), pick entry with pool lookup, undo-last, current-pick highlight, atomic persistence to data/draft_picks.json. 147 tests green, ruff clean; reviewer-caught even-round forfeit bug fixed.

- Pick model + atomic persistence (`data/draft_picks.json`); snake order 12-team x 13 rounds mirroring `league.snake_order`.
- `ui/views/board.py`: 13x12 grid; forfeits "Keeper: <name>"; current pick = first unentered open pick (forfeits consume overall numbers — R2 order 2 = overall 3); undo-last; click/tab navigation.
- Reviewer caught CRITICAL: even-round keeper cells rendered "Keeper: ?" (`_slot_of` used start-order slot instead of snake order). Fix: `_order_of` (odd rounds index+1, even rounds len-index), `_keeper_cells` keyed by snake order; +2 tests (even-round forfeit, opted-out even-round stays open). Also fixed round-13 cells unclickable (bounds check used 12 not grid rowCount 13).
- Verify: 147 passed / 1 skipped, ruff clean, offscreen smoke (even-round keeper cell, round-13 click) OK.

## 2026-10-03 — M2.3 — Pool value recommender (slice 3/3 — M2 complete): per-pick top-N suggestions from real pool rank/value/pos columns, excludes drafted picks + active keepers (opted-out keepers stay draftable), unranked rows show dash. 162 tests green, ruff clean; all ROADMAP M2 exit criteria verified.

- `domain/recommend.py`: top-N per current pick from pool `rank`/`value`/`pos`/`name` only (no invented stats); exclusion = drafted picks + non-opted-out keepers, alias-bridged both sides.
- `board.py` suggest panel: updates per current pick; unranked rows `rank=None` → "—".
- Post-review fixes (all 3 nits pinned with tests): opted-out keepers stay suggestable; unranked rank None (was max+1 = invented "200"); 12-team shape covered by domain test.
- Verify: 162 passed / 1 skipped, ruff clean, offscreen smoke (opted-out keeper, unranked dash) OK. **ROADMAP M2 exit criteria all verified.**
