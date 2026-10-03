# 005_advisor — done

## 2026-10-03 — M4.1 — Waiver scoring domain (slice 1/2 of M4): rank_candidates computes baseline P once, per-candidate full drop-space counterfactuals (best drop = max delta-P via engine), ranked list with delta_p, per-cat deltas, FAAB budget flag, direction-aware rationale, loud unmatched-name errors. 187 tests green, ruff clean.

- `domain/waiver.py`: baseline once, all-roster-drop scan (strict `>` first-tie), sort `(-delta_p, cost, name)`; FAAB over-budget flag; unmatched names -> ValueError listing all misses.
- Reviewer PASS x7; fix worker independently hand-verified (Point: baseline 0.72, best drop W2, delta_p +0.26 — exact match).
- Post-review: rationale sign-adjusted for `to` direction.
- Verify: 187 passed / 1 skipped, ruff clean.

## 2026-10-03 — M4.2 — Waiver view (slice 2/2 — M4 complete): Waivers page wired into shell, manual candidate entry (pre-draft, name + FAAB cost), rank via domain/waiver.rank_candidates, results table (rank, delta-P, best drop, cat deltas, cost, over-budget, rationale), persisted FAAB budget, unmatched names surface as banner. 192 tests green, ruff clean, exe rebuilt.

- `ui/views/waivers.py`: context row (team/opponent/week, matchup-view patterns), candidate entry grid, Rank button, results table, FAAB budget persisted via settings (key `waiver_faab_budget`), unmatched -> banner not crash; theme tokens only.
- Post-review: settings-key typo `waiber_faab_budget` fixed; all other flagged items hand-verified non-defects (scoring lives in domain, budget persisted, ordering stable).
- Exe rebuilt. Verify: 192 passed / 1 skipped, ruff clean, offscreen smoke OK.

## 2026-10-03 — M5.1 — Lineup optimizer domain (slice 1/2 of M5): exhaustive C(14,10) starter-set search over engine projections with deterministic backtracking slot assignment (PG/SG/G/SF/PF/F/C/3 UTL, UTL = multi-pos), per-cat gaps + per-sitter rationale, optional seeded MC p_win. 202 tests green, ruff clean. NOTE: M5 scope review requested by user before M5.2 UI.

- `domain/lineup.py`: set-exhaustive search (project_roster position-agnostic -> C(14,10)=1001 candidates, deterministic matchup key), backtracking slot fill in fixed order; slot map from single `pos` column (G<-PG|SG, F<-SF|PF, UTL = >=2 tokens); `mc_trials` reports p_win without changing the choice; ~40ms for 14 players.
- Finish-worker caught + fixed real bug: `_assign` returned `list(used)` (hash order) -> slot labels misassigned + non-deterministic across processes; now records picks in slot order.
- Test hand-check: plan's "7-1" target didn't hold; computed optimum is 8-1 (FT% pool needs Zeta AND Yankee both starting: (8*410*.40 + 492*.80 + 574*.75)/3348 ~ 0.4915 > 0.45; each alone ~0.4471) — arithmetic in test docstring.
- Known documented gap: best SET unslot-able -> raises instead of next-best-set fallback.
- Verify: 202 passed / 1 skipped, ruff clean.

## 2026-10-03 — M5.2 — Lineups view (slice 2/2 — M5 complete): Lineups page with week/opponent context, per-player playing toggles, Optimize via domain/lineup.optimize (gap mode instant, optional seeded MC with visible P(win)), 10-starters-by-slot table + sits with rationale + 9-cat outlook, ValueError -> banner not crash. 207 tests green, ruff clean, exe rebuilt.

- `ui/views/lineups.py` (wired into shell): context row, playing toggles, Optimize with mc_trials/seed spinboxes (default 0 = instant gap mode; MC shows P(win) with visible seed), starters/sits/rationale/9-cat outlook tables; reuse domain/lineup.optimize (zero search code in view — verified by grep); banner on unfillable-slot ValueError (reproduced offscreen: 'only 9 playable row(s)'); theme tokens only.
- Reviewer: all flagged items hand-verified non-defects except success-banner wording (fixed: separate `_DONE_NOTE`); starter-toggle test coverage nit left (non-blocking).
- Exe rebuilt (lineups.py newer than dist). Verify: 207 passed / 1 skipped, ruff clean, offscreen smoke OK (starters by slot, 4 sits, MC 0.51 seed 7, error banner).

## 2026-10-03 — M5.2 — Lineup view (UI, slice 2/2 of M5): Lineups page in shell — team/opp/week combos, per-player play toggles (checked=playing; all checked → playing=None), mc_trials default 0 (deterministic gap mode) + seed, Optimize → domain.lineup.optimize (reuse), 10-slot starter table with per-starter projected pts, sits + rationale (toggled-off players shown display-only), 9-cat outlook (gap + W/L/T) + cat-win margin + optional seeded P(win); ValueError → banner with slot named + cleared tables; IR slot display-only note. 207 tests green (5 new UI tests), ruff clean, offscreen MainWindow smoke OK.
