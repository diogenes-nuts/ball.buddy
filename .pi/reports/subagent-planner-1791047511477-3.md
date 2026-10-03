## Goal
M2.1: keeper entry (data model + `data/keepers.json` persistence + Draft-page bulk entry UI), foundation for the M2.2 board.

## Decisions (no re-decisions left)
1. **Model** — new `ball_buddy/domain/keepers.py`: `KeeperEntry` frozen dataclass `(team, player, cost_round, opted_out)` — player stored **as entered**; resolution is computed, not persisted. `MAX_COST_ROUND = 13` (SPEC §1.1, 13-round snake; league.py:22 `DRAFT_ROUNDS=14` mismatch is an M2.2 issue, do NOT touch). `validate(entries, teams) -> list[str]`: error if team unknown; >2 entries per team (opted-out counts toward 2); `cost_round` not in 1..13; duplicate player across teams — dedupe key = **resolved pool name if resolved, else `naming.normalize(player)`**; duplicate `(team, cost_round)` among **non-opted-out** entries only (opted-out consumes no pick; mirrors `_validate_keepers`, league.py:217).
2. **Persistence** — `keepers.py` also owns `load(path)`/`save(entries, path)` via `io/state.py` `save_json`/`load_json`, `KEEPERS_VERSION = 1`, payload `{"keepers": [{team, player, cost_round, opted_out}]}` at `data/keepers.json`; corrupt/wrong-version → `StateError` (players.py:14 importing io is precedent).
3. **View** — rewrite `ball_buddy/ui/views/draft.py` → `DraftView(service: SyncService)` (shell passes `self.sync_service`). Teams come from `service.load_last().snapshot` team names; **no snapshot → banner "Sync the league first (League → Sync now)", Save disabled.** Grid = QTableWidget, **2 pre-allocated rows per team** (24 rows for 12 teams; structurally caps at 2/team — supersedes the "team picker"; col 0 is plain team-name text). Cols: Team | Player (QLineEdit + `QCompleter` over `PlayerPool.load(service.pool_path).names()`) | Cost round (QSpinBox 1–13, default 1) | Opt out (QCheckBox) | Status. Rows with empty player = ignored on save.
4. **Resolved vs unresolved** — on `textChanged`/save, resolve each entered name via `naming.bridge([entered], pool_names, service.load_aliases())`; Status col shows pool name, or `UNMATCHED` (+ first suggestion, no emoji); ink-filled `banner-alert` label: "N keeper name(s) unmatched — fix spelling or add data/aliases.json entries" (same loud rule as league.py:144). Unmatched keepers **still save** (flagged, not blocked); only `validate()` errors block Save (errors join in the same banner-alert).
5. **Save** — "Save keepers" button (`ink="true"`): validate → `keepers.save(...)` → re-resolve → success `banner` "Saved N keepers to keepers.json".

## Plan
1. Create `ball_buddy/domain/keepers.py` (model, validate, load/save, `resolve(entries, pool, aliases) -> dict[raw_name, pool_name|None]` reusing `naming.bridge` per row).
2. Rewrite `ball_buddy/ui/views/draft.py` per §3–5; theme tokens only (`panel`, `banner`, `banner-alert`, table styles — no new hex).
3. `ball_buddy/ui/shell.py`: `DraftView()` → `DraftView(self.sync_service)` (line ~59).
4. Tests (below).
5. `ruff check .` + `pytest`; create `agents/006_board/status.md` marking M2.1 done (phase workflow handles the commit — no manual git).

## Files to Modify
- `ball_buddy/ui/views/draft.py` — full rewrite (placeholder → keeper entry page)
- `ball_buddy/ui/shell.py` — one line: pass sync service to DraftView

## New Files
- `ball_buddy/domain/keepers.py` — model + validation + keepers.json IO + resolution
- `tests/domain/test_keepers.py` — round-trip via `save_json`/`load_json` (tmp_path), version mismatch raises `StateError`; validation: 3rd keeper for a team, cost_round 0 and 14, cross-team duplicate (incl. alias/normalize-equal: "Jokic" vs "Nikola Jokic" both resolving to pool "Jokic"), same `(team, round)` blocked for active but allowed when one is opted-out, opted-out counts toward team's 2
- `tests/ui/test_draft_view.py` — offscreen, reuse `FakeQuery`/`snapshot_results.json` fixture (pattern of tests/ui/test_league_view.py): renders 2 rows/team from fixture snapshot; no-snapshot → save disabled + banner; fill row 0 (set combo-less widgets: text, spin, check) → save → `keepers.json` exists with 1 entry, Status shows pool name; unmatched name → Status `UNMATCHED` + banner-alert visible; >2/team impossible via grid but `validate` reachable on hand-built entries
- `agents/006_board/status.md` — M2.1 slice note

## Risks
- `league.py` `DRAFT_ROUNDS = 14` (league.py:22) vs SPEC 13 rounds — cost-round cap 13 per task; M2.2 must reconcile the board round count, leave this slice alone.
- `QCompleter` on `QLineEdit` items inside `QTableWidget` needs `setCellWidget` — test with the actual widget, not the model item.
- Fixture snapshot has 2 teams (4 grid rows), not 12 — tests assert row-count = 2×teams, not 24.