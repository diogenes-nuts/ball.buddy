## Plan: P6 scorer port

**Location:** new `ball_buddy/domain/scorer.py`. Rationale: pure scoring math, no I/O; keeps `recommend.py`'s P2 surface (Suggestion, fallback, reason bits) untouched; mirrors autodraft's engine/scoring.py separation; independently testable.

**Constants (module-top, draft-day tunables):** `MARKET_WEIGHT=0.45`, `FIT_WEIGHT=0.55`, `TAG_ADJUSTMENT=0.10`, `REACH_FACTOR=0.8`, `VALUE_FACTOR=1.25`, `HOLE_MULT=1.25`, `COVERED_MULT=0.75`, `COVERED_THRESHOLD=0.5`, `VALUE_GAP_TOP_FRACTION=0.10`, `VALUE_GAP_MIN_CANDIDATES=10`, `VALUE_GAP_DEFAULT_ROUNDS=2`, and `WEIGHTS: dict[str, float]` — one entry per ball.buddy cat key (`engine.CATS`: pts, reb, ast, stl, blk, to, three, fg_pct, ft_pct), all 1.0 (autodraft league.json has all-1 weights; module constant, not settings, per autodraft precedent).

**Mapping (autodraft → ball.buddy):**
- z → pool row `z_*` cols via `importer.Z_FIELD_FOR` (reuse, import it); **negate `z_to`** at parse (source z_to ≈ +0.999 corr with to_pg, not sign-corrected)
- rank → row `rank` (int); rank_max = max over full pool
- adp → row `adp_round` (float|None; blank allowed)
- overall pick → `picks.current_pick(snake, picks).overall` (league.py:330, 1-based snake index)
- per-cat edge → **new** scorer math on signed z (NOT P2 category_gaps: edge = roster mean z − pool mean z per cat; **empty roster → −pool_mean**, per needs.py — rejects autodraft's −1.0); status hole <0 / covered ≥0.5 / ok
- weights → module WEIGHTS (all 1.0)

**Signatures:**
```python
def score_pool(rows, my_rows, overall, team_count, top_n=10) -> list[Suggestion]
```
- `rows`: full pool rows (dict[str,str], pool CSV incl. z_*, adp_round); `my_rows`: my secured pool rows (from board `_team_projections`); `overall`: current pick overall; `team_count`: len(start_order) for the gap threshold. Blank z cell → 0.0 for that cat; blank adp → tag NO_ADP, excluded from gap flag; no rank → market 0. Tolerance documented in docstring.
- Returns `recommend.Suggestion` (reuse existing dataclass — don't redefine). reason = " · ".join: `mkt {rank}/{rank_max} → {market:.2f}`, `fit {fit:+.2f}z: holes A, B; covered C` (only weight>0 cats), tag bit (`REACH: ADP x.x vs pick N` / `VALUE: …` / `ADP x.x on board` / `no ADP`), optional `value gap: rank R, ADP A — market oversleeping`, then P2 bits appended: top-2 filled cat gaps (`fills … gaps`, via existing `category_gaps`/`cat_fill` on projections) and C1 scarcity bit — kept as additional reasons, not score.

**recommend.py changes:** in `recommend_need_aware`, keep signature; when teams/my_team valid, replace the P2 score line with a `scorer.score_pool(...)` call (needs `overall` + `team_count` → add as optional kwargs, default 0/0 → caller passes). Keep `_fallback` verbatim. Delete `NEED_WEIGHT`/`SCARCITY_WEIGHT` (score no longer uses them; reason bits need no weights). Keep `category_gaps`/`cat_fill` exports (board `_render_relative` → relative.py uses them too — verify before deleting).

**board.py (minimal, no P7 UI):** in `_render_suggestions`, fetch `current_pick(...)` (already fetched), pass `my_rows=projections[my_team]`, `overall`, `team_count=len(self.start_order)` to `recommend_need_aware`. Call-site only.

**Tests** `tests/domain/test_scorer.py`, fake pool (z + adp + rank): market ordering; fit overrides market for a hole cat; 1.25 vs 0.75 multiplier visible in ordering; REACH tag (cheap high-rank) and VALUE tag adjust scores; gap flag fires (top-decile, adp > floor+2·teams); **TO flip: low-TO (negative signed z_to before flip → positive after) ranks higher fit than same-rank high-TO**; empty my_team → fallback; blank adp row survives (no tag); blank z row survives (fit 0, market only).

**Finish:** `.venv\Scripts\pytest` + `ruff check .` green; update `agents/006_board/status.md` Recommender section (formula, constants, tolerance rules, TO-flip note, edge empty→−pool_mean decision).

**Risks:** (a) `data/players.csv` absent locally — tests must use fixtures, never real pool; (b) verify relative.py/recommend.py import graph before touching `category_gaps`; (c) board.py:355 `_render_relative` must not break.