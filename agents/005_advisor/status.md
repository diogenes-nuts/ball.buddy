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

Plans: dev.md. History: git log; done.md.
