# 005_advisor — status

Advisor logic over 004_engine (SPEC §6). M4.1 done (waiver domain); M4.2 (waiver view UI) remaining in dev.md.

## Files

- `ball_buddy/domain/waiver.py` — headless waiver ranking:
  - `rank_candidates(...)` — baseline P computed once; per candidate, counterfactual over the FULL drop space (every current roster player, strict `>` first-tie), best drop = max ΔP; reuses `domain/engine.py` (no projection re-implementation).
  - Output per candidate: `delta_p`, `best_drop`, per-category gap deltas (deterministic gap mode), `faab_cost`, `over_budget` flag (vs. remaining budget param), direction-aware rationale (TO improvements read positive, `was` stays raw).
  - Unmatched candidate names → loud `ValueError` (never silent zeros).
  - Deterministic with seed; pure python, no Qt.

## Next (dev.md)

- M4.2: Waivers page (manual candidate entry pre-draft, ranked table, FAAB budget + bid input).

## Lineup optimizer (M5.1)

- `ball_buddy/domain/lineup.py` — headless: exhaustive C(14,10) starter-SET search (engine.project_roster is position-agnostic, so the set is what matters), scored by deterministic matchup vs opponent; backtracking slot assignment in fixed order (PG,SG,G,SF,PF,F,C,UTLx3); slot map from the single `pos` column (G<-PG|SG, F<-SF|PF, UTL = >=2 pos tokens; unknown pos excluded with note); `LineupResult` (starters by slot, sits, per-cat gaps, cat_wins, margin, optional seeded `p_win`, per-sitter rationale, notes); <10 playable or unfillable slot -> ValueError; IR/BN split is an M5.2 display concern. Deterministic; ~40ms for 14 players. Known gap (documented): if a perturbation makes the best SET unslot-able, optimize raises instead of falling back to the next-best set.

## Lineup view (M5.2)

- `ball_buddy/ui/views/lineups.py` — Lineups page: my team/opponent/week combos (matchup/waivers pattern; empty schedule → single "1" + loud week note), one checked QCheckBox per resolved roster player (unchecked → `playing=frozenset`, all checked → `playing=None`), mc_trials spinbox (default 0 = deterministic gap mode) + seed (42), **Optimize** runs `domain/lineup.optimize` synchronously (reuse, no re-implementation; no recompute on toggle). Renders: starters table in fixed SLOTS order (Pts = `engine.project_roster` per-starter season pts), sits table (Player, Why from `result.rationale`; toggled-off players get a display-only "not playing" row), 9-cat table (Gap, W/L/T), summary `"mine vs theirs cats — margin ±x.xx"` + optional `P(win)=... (seed ...)` when mc_trials>0, IR note (display only). `optimize` ValueError → banner with slot named + cleared tables; unresolved names/empty roster → banner warnings (waivers pattern); roster core `_team_roster_rows` duplicated from `MatchupView._load_team_data` (bound-method precedent). `shell.py` wires "Lineups" → LineupView (PlaceholderView fall-through remains for Trades).

Plans: dev.md. History: git log; done.md.
