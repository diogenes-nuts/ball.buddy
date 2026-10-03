## M4.1 Plan — Waiver scoring (headless)

**Goal:** Add `ball_buddy/domain/waiver.py` ranking waiver candidates by ΔP(win) via 004_engine reuse.

### Decisions (final, no re-deciding)

**1. Data shapes** (in `waiver.py`, frozen dataclasses):
- `WaiverCandidate(name: str, faab_cost: int | None = None)` — `None` = free/no cost.
- `WaiverRanking(candidate, pool_name: str, best_drop: str | None, baseline_p: float, delta_p: float, cat_delta: dict[str, float], over_budget: bool, rationale: str)` — `cat_delta[cat]` = raw A−B gap after minus before; `best_drop=None` only when roster is empty.

**2. Signature:**
```python
def rank_candidates(
    candidates: list[WaiverCandidate],
    roster_names: list[str],       # pool names (bridged upstream)
    opponent_names: list[str],
    pool: PlayerPool,
    faab_budget: int | None = None,  # remaining FAAB; None = don't check
    trials: int = 200, seed: int | None = None,
    tie_break: str = "yahoo_default",
) -> list[WaiverRanking]
```
Resolution via `PlayerPool.get` (naming.py:42). Any unmatched candidate OR roster/opponent name → `ValueError` listing all unresolved (loud, not silent). `faab_cost` must be `None` or `>= 0` else `ValueError`.

**3. Algorithm (exact):**
1. Resolve all names to pool rows.
2. `base = project_roster(roster_rows, "Team")`; `opp = project_roster(opp_rows, "Opp")` (engine.py:113).
3. `baseline_p = win_prob(base, opp, seed=seed, trials=trials)` (engine.py:305); `base_gaps = matchup(base, opp, mc=False).gaps` (deterministic, cheap).
4. Per candidate: evaluate **ALL** current roster players as drop candidates (no bench-first — space is ~14×14, exact): for each `drop i`, rows' = roster_rows − rows[i] + candidate row → `project_roster` → `delta_i = win_prob(rows', opp, seed, trials) − baseline_p`. `best = argmax delta_i` (first in roster order on ties → deterministic). Empty roster: single eval, no drop, `best_drop=None`.
5. `cat_delta` from deterministic `matchup(mc=False).gaps` of best counterfactual minus `base_gaps` (no MC needed).
6. `rationale`: best cat by direction-adjusted improvement — score `= cat_delta[cat] × (−1 if cat=="to" else +1)` (engine.py DIRECTIONS, engine.py:40); format `f"{cat.upper()} {raw_delta:+.0f} (was {base_gaps[cat]:+.0f})"`, e.g. `REB +120 (was -80)`.
7. `over_budget = faab_budget is not None and faab_cost is not None and faab_cost > faab_budget`.
8. Sort: `delta_p` desc, tie-break `faab_cost` asc (None→0), then candidate name.
Runtime note in module docstring: default N=200 → ~14×14×200 MC matchup ≈ a few seconds (one shared `random.Random(seed)` — engine seeds per call, fine).

**4. Tests** — new `tests/domain/test_waiver.py`, `trials=50` for speed. Fixture (mirror test_engine.py:17 `_row`): 4-person roster = 2 strong (S1 high-PTS, S2 high-AST) + 2 weak (W1, W2 lowest overall); opponent 3 mid rows; candidates: `Star` (dominant PTS/REB), `Point` (big AST, near-redundant vs S2), `Mid` (average).
- `test_ranking_order`: seed=7 → result[0].candidate.name == "Star", result[0].delta_p > result[2].delta_p.
- `test_best_drop`: "Point" entry → `best_drop == "W2"` (weakest overall; adding an AST guard only helps when the weak slot is replaced).
- `test_determinism`: two calls, same seed → identical `delta_p` per candidate.
- `test_budget`: budget=20, Star cost=30 → `over_budget` True; Point cost=None → False.
- `test_unmatched`: candidate "Not A Player" → `ValueError` matching the name; missing roster name → `ValueError`.
- `test_empty_roster`: roster_names=[] → one entry per candidate, `best_drop is None`, no crash.
Expected hand-check ordering: **Star > Point > Mid** (verify during impl; if MC noise at 50 trials breaks ordering, raise to 200 — noted here in advance so it's not a re-decision).

### Files
- New `ball_buddy/domain/waiver.py` — module above; `__all__ = ["WaiverCandidate", "WaiverRanking", "rank_candidates"]`. Imports: `ball_buddy.domain.engine` (project_roster, matchup, win_prob), `ball_buddy.domain.players.PlayerPool`. No Qt, no new deps.
- New `tests/domain/test_waiver.py`.
- New `agents/005_advisor/status.md` — 3-5 lines: M4.1 done, headless, no wire data (fixture/manual only).

### Risks
- MC noise at low trials can reorder near-ties → pin seed + use distinct strength tiers so ordering is robust.
- `win_prob` re-seeds its own RNG per call (engine.py:317) → counterfactuals and baseline share the seed; fine, deterministic per call.
- Do not commit (task constraint); `data/` untouched — pure domain + tests.