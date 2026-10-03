# 005_advisor — status

Advisor logic over 004_engine (SPEC §6). **M4 + M5 + M6.1 (trade domain) complete**; M6.2 (trade view) remaining in dev.md.

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

## Next (dev.md)

- M6.2: Trades page (UI) — trade entry + analyze via `domain/trade.analyze_trade`, result tables + fairness verdict.

Plans: dev.md. History: git log; done.md.
