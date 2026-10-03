# 006_board — done

## 2026-10-03 — M2.1 — Keeper entry (slice 1/3 of draft board): keepers domain model (team, pool-bridged player, cost round, opt-out), atomic persistence to data/keepers.json, bulk entry grid in Draft view (24 keepers, per-team cap validation, loud unmatched flags, cap-drop alert). 128 tests green, ruff clean.

- `domain/keepers.py`: model + validation (max 2 active/team, cost round 1–13, duplicate player across teams = error); opt-out semantics (player back to pool, pick back to team).
- `data/keepers.json` via `io/state.py` atomic save/load; corrupt >2-per-team files → loud cap-drop alert, no silent loss.
- `ui/views/draft.py`: entry grid (team, player + pool lookup, cost round, opt-out), per-row resolved/unmatched status, save flow; pool loaded once per refresh (no N+1).
- Post-review fixes: silent cap-drop surfaced via banner-alert; pool-load N+1 removed.
- Verify: 128 passed / 1 skipped, ruff clean, offscreen smoke OK (save → round-trip → unmatched flag → cap-drop alert).
