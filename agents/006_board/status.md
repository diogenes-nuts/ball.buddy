# 006_board — status

Draft board: keeper entry (M2.1 done) + live 13-round draft board (M2.2, next).

## M2.1 — keeper entry (done)

- `ball_buddy/domain/keepers.py` — `KeeperEntry(team, player, cost_round, opted_out)` frozen dataclass (player stored as entered; resolution computed, not persisted); `validate(entries, teams, resolved)` (unknown team, >2/team with opted-out counting, cost round 1..13, cross-team duplicate deduped on resolved pool name else `naming.normalize`, same (team, round) only for non-opted-out — mirrors `_validate_keepers`); `resolve(entries, pool, aliases)` via `naming.bridge`; `load`/`save` `data/keepers.json` through `io/state.py` (`KEEPERS_VERSION = 1`, corrupt/wrong-version → `StateError`).
- `ball_buddy/ui/views/draft.py` — rewritten placeholder → keeper entry page: QTableWidget, 2 pre-allocated rows per team (structural 2/team cap, no team picker), Player = QLineEdit + QCompleter over the pool, Cost round QSpinBox 1–13, Opt out QCheckBox, Status column (pool name / `UNMATCHED (try <first suggestion>)`). No snapshot → banner-alert "Sync the league first (League → Sync now)", Save disabled. Unmatched keepers flagged in the same banner-alert but still save; only `validate()` errors block Save. Save → atomic keepers.json write → "Saved N keepers to keepers.json" banner. Theme tokens only.
- `ball_buddy/ui/shell.py` — one line: `DraftView(self.sync_service)`.
- Tests: `tests/domain/test_keepers.py` (round-trip, version/corrupt StateError, all validation rules incl. alias-equal "Jokic" vs "Nikola Jokic"), `tests/ui/test_draft_view.py` (offscreen, fixture snapshot: 2 rows/team, no-snapshot banner, fill→save, unmatched flag, validate block, opt-out flag).

Deviations: none. Open for M2.2: reconcile `league.py` `DRAFT_ROUNDS = 14` (league.py:22) with the SPEC 13-round snake (keepers cap at 13 per SPEC §1.1).
