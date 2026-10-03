# 005_advisor — status

Advisor logic over 004_engine (SPEC §6). **M4 + M5 + M6 complete** (waiver, lineup, trade — domain + view each).

## Files

- `ball_buddy/domain/waiver.py` — headless waiver ranking:
  - `rank_candidates(...)` — baseline P computed once; per candidate, counterfactual over the FULL drop space (every current roster player, strict `>` first-tie), best drop = max ΔP; reuses `domain/engine.py` (no projection re-implementation).
  - Output per candidate: `delta_p`, `best_drop`, per-category gap deltas (deterministic gap mode), `faab_cost`, `over_budget` flag (vs. remaining budget param), direction-aware rationale (TO improvements read positive, `was` stays raw).
  - Unmatched candidate names → loud `ValueError` (never silent zeros).
  - Deterministic with seed; pure python, no Qt.

## Waiver view (M4.2)

- `ball_buddy/ui/views/waivers.py` — Waivers page: context row, manual candidate entry grid (name + FAAB cost), Rank via `domain/waiver.rank_candidates`, results table (rank, delta-P, best drop, cat deltas, cost, over-budget, rationale), FAAB budget persisted via settings key `waiver_faab_budget`, unmatched names -> banner. Theme tokens only.

## Lineup optimizer (M5.1)

- `ball_buddy/domain/lineup.py` — headless: exhaustive C(14,10) starter-SET search (engine.project_roster is position-agnostic, so the set is what matters), scored by deterministic matchup vs opponent; backtracking slot assignment in fixed order (PG,SG,G,SF,PF,F,C,UTLx3); slot map from the single `pos` column (G<-PG|SG, F<-SF|PF, UTL = >=2 pos tokens; unknown pos excluded with note); `LineupResult` (starters by slot, sits, per-cat gaps, cat_wins, margin, optional seeded `p_win`, per-sitter rationale, notes); <10 playable or unfillable slot -> ValueError; IR/BN split is an M5.2 display concern. Deterministic; ~40ms for 14 players. Known gap (documented): if a perturbation makes the best SET unslot-able, optimize raises instead of falling back to the next-best set.

## Lineup view (M5.2)

- `ball_buddy/ui/views/lineups.py` — Lineups page: my team/opponent/week combos (matchup/waivers pattern; empty schedule → single "1" + loud week note), one checked QCheckBox per resolved roster player (unchecked → `playing=frozenset`, all checked → `playing=None`), mc_trials spinbox (default 0 = deterministic gap mode) + seed (42), **Optimize** runs `domain/lineup.optimize` synchronously (reuse, no re-implementation; no recompute on toggle). Renders: starters table in fixed SLOTS order (Pts = `engine.project_roster` per-starter season pts), sits table (Player, Why from `result.rationale`; toggled-off players get a display-only "not playing" row), 9-cat table (Gap, W/L/T), summary `"mine vs theirs cats — margin ±x.xx"` + optional `P(win)=... (seed ...)` when mc_trials>0, IR note (display only). `optimize` ValueError → banner with slot named + cleared tables; unresolved names/empty roster → banner warnings (waivers pattern); roster core `_team_roster_rows` duplicated from `MatchupView._load_team_data` (bound-method precedent). `shell.py` wires "Lineups" → LineupView (PlaceholderView fall-through remains for Trades).

## Trade analyzer (M6.1)

- `ball_buddy/domain/trade.py` — headless: `Trade` (my_give/their_give display-name tuples) + `TradeResult` (per-side baseline/delta P(win), deterministic before/after gaps from each side's own perspective, `fairness_flag` when my delta < −0.10, human `summary` with fairness verdict). `analyze_trade` reuses `engine.project_roster` / `win_prob` / `matchup` unchanged; one seeded MC run serves both sides (opponent = `1 − my_p`; pushes treated as losses for both — documented). Validation: one `ValueError` listing every pool/roster miss (never silent), both-sides-empty rejected, roster (non-give) names pool-checked. Pure python, no Qt.
- `tests/domain/test_trade.py` — 11 cases (waiver-style fixtures, trials=50 shared seed, symmetry at 2000 trials, 2-for-2 swap, roster-miss raise, summary format).

## Trade view (M6.2)

- `ball_buddy/ui/views/trades.py` — Trades page: my team/opponent combos (waivers/lineups pattern; **no week picker** — `analyze_trade` scores season projections, a week control would be dead UI, justified in the module docstring), seed spin (0..2^31-1, default 42) + trials spin (1..100_000, default 200 = domain default), **Analyze** runs `domain/trade.analyze_trade` synchronously (seconds-scale, no worker thread). Trade entry: "I give" / "They give" combos filled with the current teams' resolved roster names (`_team_roster_names` is a module-level function in `waivers.py`, duplicated here verbatim, no import) + Add/Remove rows in a give grid; selected gives cleared on team/opponent change (a stale give would otherwise raise from the domain). Renders: per-side 9-cat tables (Before/After/Delta, `CAT_LABELS` + lineups' `_fmt_gap` pattern, fixed-height 9*28+40), summary line `"you: b -> b+d   them: b -> b+d   (seed s, t trials)"`. Success banner = `result.summary` (contains the fairness verdict "likely a bad deal") + unresolved-name notes; `analyze_trade` ValueError (e.g. both sides empty) -> banner with tables cleared; empty roster -> "Empty roster..." banner (waivers pattern). `shell.py` wires "Trades" -> TradeView; all NAV_ITEMS now have real views, so the old PlaceholderView fall-through was replaced with a loud `AssertionError` (future labels must add a branch, not silently get a placeholder) and `ui/views/placeholders.py` deleted. Theme tokens only (title/secondary/banner objectNames, `ink` property on the primary button).
- `tests/ui/test_trade_view.py` — 6 cases (P1-P4 fixture, Red vs Blue): happy path (banner "you"/"them", 9x2 tables, summary seed/trials), fairness flag on P1-for-P4 ("bad deal"), both-sides-empty domain ValueError -> banner, no-snapshot banner, ghost keeper -> "Empty roster" + name in banner (no raise), trials spinbox reflected in summary.

## Next (dev.md)

- (none — M6 complete; next roadmap item is M7 packaging).

Plans: dev.md. History: git log; done.md.
