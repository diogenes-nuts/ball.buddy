## Plan — M4.2: Waivers view (UI)

**Goal:** Wire the "Waivers" nav page (placeholder today) to a new `WaiverView` with manual candidate entry, FAAB budget, and a ranked ΔP(win) results table reusing `rank_candidates` unchanged.

### Decisions (final — do not re-decide)

1. **Layout** (top→bottom in `WaiverView`, copy matchup.py patterns):
   - Context row: `team_combo` ("My team"), `opp_combo` ("Opponent"), `week_combo` — populated exactly like `MatchupView._refresh_combos` (matchup.py:197) from `snapshot["teams"]`/schedule weeks; week is display-only pre-draft (same note as matchup).
   - Budget row: `QLabel("FAAB remaining: $")` + `QSpinBox` (0–100, default 100) → persisted as `settings["waiber_faab_budget"]` via `service.settings()`/`save_settings` (matchup tie-break pattern, matchup.py:383).
   - Entry area: header note label `"Pre-draft: candidates are entered manually — no Yahoo waiver order yet."` + rows of (`QLineEdit` name, `QSpinBox` cost 0–99 with "0 = free" label, Remove button) + "Add candidate" button. Grid pattern from draft.py.
   - `Rank` button (synchronous, like "Run Monte-Carlo"; trials=200 default is seconds-scale at pre-draft roster sizes).
   - `QLabel` banner (objectName "banner", wordWrap) for warnings/errors.
   - Results `QTableWidget(0, 8)`: Rank, Candidate, ΔP(win), Best drop, Top-2 cat Δ, Cost, Over budget, Rationale. No-edit, NoSelection, stretch header, `verticalHeader().setVisible(False)` (matchup table pattern, matchup.py:150). ΔP shown `f"{r.delta_p:+.4f}"`; top-2 = top 2 direction-adjusted `cat_delta` (TO negated) joined `"PTS +5 / TO +1"`; over-budget cell "YES"/"" using `r.over_budget`.

2. **FAAB:** budget spinbox value passed as `faab_budget` to `rank_candidates`; per-candidate cost spinbox → `WaiverCandidate(name, faab_cost=value)`. Empty name rows are skipped (not an error); all-empty → banner "Add at least one candidate."

3. **Baseline roster source chain (document in view docstring):** `keepers.json` + `draft_picks.json` (per selected team) → `keepers_mod.resolve(..., pool.names(), service.load_aliases())` → resolved pool names → `rank_candidates(roster_names, opponent_names, pool=PlayerPool.load(service.pool_path), ...)` (waiver.py:58 resolves internally). `_load_team_data` is a bound `MatchupView` method (matchup.py:222) — **not importable**; deliberately duplicate the small name-resolution core (~15 lines) as module function `_team_roster_names(service, team) -> tuple[list[str], list[str]]` returning (resolved pool names, unresolved names) — do NOT refactor matchup.py in this slice. Opponent names built the same way for `opp_combo`'s team. Unresolved roster names → banner warning, not a crash. Banner always includes "No lineups yet — projecting full rosters from keepers + drafted picks."

4. **Errors:** wrap `rank_candidates` in try/except `ValueError` (unmatched candidate/roster/opponent names, waiver.py:39) → `banner.setText(str(e))`, clear table; never an exception.

5. **Test plan** `tests/ui/test_waiver_view.py` (mirror test_matchup_view.py scaffolding: `QT_QPA_PLATFORM=offscreen` at top, module `qapp` fixture, `_row`/P1–P4 fixture pool via `FIELDNAMES`/`write_csv`, keepers Red=P1,P2 Blue=P3,P4, fixture snapshot via `load_results`/`to_snapshot`/`save_snapshot`):
   - Build view; `apply_result`/populate combos; pick Red vs Blue.
   - Add 2 candidates via test seams (expose `add_candidate(name, cost)` and `rank()` methods): "P3" cost 5, "P4" cost 0; set budget 100 → `rank()` → assert 2 rows, row0 candidate "P3" (higher ΔP than P4), both have non-empty best_drop (roster non-empty).
   - Set budget spin to 4 → `rank()` → row for P3 has over-budget flag set.
   - Add candidate "Ghost" → `rank()` → banner contains "unresolved" (error surfaced), table rowcount reflects the failure (clear), no exception raised.
   - Assert budget persisted: `service.settings()["waiber_faab_budget"] == 4`.

### Files

| File | Change |
|---|---|
| `ball_buddy/ui/views/waivers.py` | **NEW** — `WaiverView` (above) + `_team_roster_names` helper; theme tokens only (`theme.INK_FILL` etc.), no raw hex; `__all__ = ["WaiverView"]` |
| `ball_buddy/ui/shell.py` | import `WaiverView`; in `_build_stack` (shell.py:94) `elif label == "Waivers": stack.addWidget(WaiverView(self.sync_service))` |
| `tests/ui/test_waiver_view.py` | **NEW** — offscreen tests above |

### Risks
- MC cost: keep trials at 200 (default); tests use 2-man rosters so it's fast — do not add a trials spinbox.
- `PlayerPool.load` on missing `players.csv` — fixture test writes the CSV; live pre-import the pool may be empty → `rank_candidates` raises ValueError → banner handles it.
- Don't touch `matchup.py`, `waiver.py`, or domain code at all. No new deps, no git commits. Run `pytest` + `ruff check .` before exit.