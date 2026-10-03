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

## 2026-10-04 — M6.1 — Trade scoring domain (slice 1/2 of M6): domain/trade.analyze_trade scores a player-for-player swap by delta-P(win) per side via one shared seeded MC run reusing engine.project_roster/win_prob/matchup, deterministic before/after 9-cat gaps per side's own perspective, fairness_flag (my delta < -0.10) + human summary, one loud ValueError listing every pool/roster/give miss. 11 new tests (waiver-style fixtures, symmetry at 2000 trials, 2-for-2 swap, summary format). 218 tests green, ruff clean.

New `ball_buddy/domain/trade.py`: `Trade` (my_give/their_give display-name
tuples) + `TradeResult` (per-side baseline/delta P(win), deterministic
gaps before/after per side's own perspective, `fairness_flag` = my delta
< -0.10, human `summary`). `analyze_trade` reuses `engine.project_roster` /
`win_prob`/`matchup` unchanged; one seeded MC run serves both sides
(opponent = `1 - my_p`, pushes treated as losses for both — documented).
Validation: one `ValueError` listing all roster/pool/give misses; both-
sides-empty rejected. Tests: `tests/domain/test_trade.py` (11 cases,
waiver-style fixtures, trials=50 shared seed; symmetry at 2000 trials).

Reviewer fixes (same day): (a) removed dead "net league P rises" summary
suffix — mathematically unreachable since `their_delta_p == -my_delta_p`
under the `1-p` construction; summary now appends a fairness verdict
(" likely a bad deal"/" looks fair") instead. (b) `_validate` now also
pool-checks roster (non-give) names — a roster name missing from the pool
previously crashed inside `project_roster` with `AttributeError` instead
of the loud single `ValueError`. (c) tests added: roster-miss raises,
2-for-2 swap, summary format.

- `ui/views/lineups.py` (wired into shell): context row, playing toggles, Optimize with mc_trials/seed spinboxes (default 0 = instant gap mode; MC shows P(win) with visible seed), starters/sits/rationale/9-cat outlook tables; reuse domain/lineup.optimize (zero search code in view — verified by grep); banner on unfillable-slot ValueError (reproduced offscreen: 'only 9 playable row(s)'); theme tokens only.
- Reviewer: all flagged items hand-verified non-defects except success-banner wording (fixed: separate `_DONE_NOTE`); starter-toggle test coverage nit left (non-blocking).
- Exe rebuilt (lineups.py newer than dist). Verify: 207 passed / 1 skipped, ruff clean, offscreen smoke OK (starters by slot, 4 sits, MC 0.51 seed 7, error banner).

## 2026-10-03 — M5.2 — Lineup view (UI, slice 2/2 of M5): Lineups page in shell — team/opp/week combos, per-player play toggles (checked=playing; all checked → playing=None), mc_trials default 0 (deterministic gap mode) + seed, Optimize → domain.lineup.optimize (reuse), 10-slot starter table with per-starter projected pts, sits + rationale (toggled-off players shown display-only), 9-cat outlook (gap + W/L/T) + cat-win margin + optional seeded P(win); ValueError → banner with slot named + cleared tables; IR slot display-only note. 207 tests green (5 new UI tests), ruff clean, offscreen MainWindow smoke OK.

## 2026-10-04 — M6.2 — Trade view (slice 2/2 — M6 complete): Trades page in shell — team/opp combos (no week picker: analyze_trade is season-projection based), seed/trials spinboxes (42/200 defaults), I-give/They-give entry from resolved roster combos, Analyze via domain/trade.analyze_trade (synchronous), per-side Before/After/Delta 9-cat tables + P(win) summary line, fairness verdict in banner, ValueError -> banner. shell.py PlaceholderView fall-through replaced with loud AssertionError (all NAV_ITEMS have real views), ui/views/placeholders.py deleted. 6 UI tests (happy path, fairness flag, empty-sides ValueError, no-snapshot, ghost keepers, trials spinbox), 224 passed / 1 skipped, ruff clean, exe rebuilt.

- Reviewer-caught defect (fixed same day): `_rebuild_give_grid`'s takeAt loop called `deleteLater()` on EVERY widget it removed — including the still-live give labels/Remove buttons that were then re-added; after the 2nd/3rd Add, once the event loop ran, those widgets were destroyed -> next Remove/Analyze raised `RuntimeError: wrapped C++ object has been deleted`. Fix: only deleteLater() widgets not in the live set (labels+remove of `_my_gives`/`_their_gives`).
- Regression test: `test_process_events_after_add_keeps_live_gives` — 2 Adds + 1 Their-Add, then flushes deferred deletes the way the real event loop does (`processEvents()` + `sendPostedEvents(None, DeferredDelete)`; plain `processEvents()` does NOT flush them), then reads `give["label"].text()` and clicks Remove. Verified it fails on the pre-fix code (RuntimeError) and passes post-fix.
