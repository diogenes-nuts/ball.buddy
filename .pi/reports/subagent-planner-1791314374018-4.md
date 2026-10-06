## Goal
Add P3 "relative panel" to DraftBoard: per-category BUILD/COAST/PUNT tags for my team vs the league, refreshed live in the same `render()` chain as the suggest panel (board.py:212-248).

## Plan
1. **`ball_buddy/domain/recommend.py`** — promote `_category_gaps`→`category_gaps` and `_cat_fill`→`cat_fill` (drop underscore), add both to `__all__` (line 311), update the internal call at line 248. Justification: P3's tag thresholds are gap thresholds on the exact same normalized-gap math; duplicating median/spread/direction + the zero-inflation caveat (recommend.py:186-191) is worse. Grep confirms no tests/other code reference the privates — rename is safe, P2 tests stay green.
2. **New `ball_buddy/domain/relative.py`** (separate from recommend.py: independent decision concept, keeps the recommender focused):
   - `@dataclass(frozen=True) CatTag`: `cat, mine, median, gap, gap_norm, rank, best_fill_norm, tag` (`gap` = signed, positive = behind, better direction; `tag` ∈ BUILD/COAST/PUNT).
   - `def category_tags(teams: dict[str, list[dict[str, str]]], my_team: str, pool_rows: list[dict[str, str]], excluded: set[str], top_n: int = 3, bottom_n: int = 3, punt_close: float = 0.25) -> list[CatTag] | None`
   - Pure, stdlib + engine; projects all teams via `project_roster` (empty roster → zeros, per engine); gap/spread via `recommend.category_gaps`; `None` when `teams` empty or `my_team` blank/unknown (same fallback semantics as `recommend_need_aware`).
3. **Exact tag rules** (n = team count, per cat): rank = 1-based position sorted best-first by `DIRECTIONS` (tie → team name asc, deterministic); `spread` per recommend (0 → 1); `gap` better-direction; `gap_norm = max(0, gap)/spread`; `best_fill_norm` = max of `recommend.cat_fill(cat, v, spread)` over non-excluded pool players via `project_player` (0.0 if none — `to` quality = low turnovers already handled by `cat_fill`). Then:
   - `spread == 0` (all teams equal — pre-draft) → **COAST** (no signal; docstring: tags only meaningful once picks exist)
   - `rank ≤ 3` → **BUILD** (strength strong enough to compete/extend)
   - `rank ≥ n − bottom_n + 1` **and** `best_fill_norm < punt_close × gap_norm` → **PUNT** (bottom, and remaining pool can't close ~25% of the gap → unsalvageable)
   - else → **COAST**
4. **`ball_buddy/ui/views/board.py`** —
   - `__init__`: build `self.relative_panel` mirroring the suggest panel (board.py:128-152): `QWidget#panel` + `QLabel#title` + `QTableWidget(9, 5)` headers `["Cat", "Mine", "Median", "Gap", "Tag"]`, NoSelection, stretch header, maxHeight ~300, initially hidden; added as sibling **below** the suggest panel in `inner`.
   - `render()`: add `self._render_relative(report)` as the 4th call after `_render_suggestions(report)`; in `refresh()`'s no-snapshot early return, also hide the panel.
   - `_render_relative(report)`: `my_team = str(self.service.settings().get("my_team", ""))`; hide if blank or `not self.start_order`; else `relative.category_tags(self._team_projections(report), my_team, self._pool.rows, self._excluded_names(report))`; `None` → hide; else fill 9 rows — `CAT_LABELS` imported from `ball_buddy.ui.views.matchup`; count cats `f"{v:.1f}"`, pct `f"{v:.4f}"`, gap signed `f"{g:+.1f}"`/`f"{g:+.4f}"`; title "My team vs league"; v1 tags are monochrome text (coloring deferred).
5. **Tests** —
   - New `tests/domain/test_relative.py` (FIELDNAMES stat dicts, 12 teams × 1 player): top pts → BUILD; bottom pts + zero-reb pool → PUNT; bottom + pool player closing >25% of gap → COAST; middle team → COAST; `to`: lowest TO → BUILD, highest TO + weak pool → PUNT; unknown/blank my_team → None; all-zero teams → all COAST; threshold boundaries (fill exactly 0.25×gap → COAST, just under → PUNT).
   - `tests/ui/test_board.py`: add `make_manual_service_12(tmp_path)` helper (`settings["manual_teams"]` = 12 names + `my_team="Alpha"`); pool containing one keeper player per team (Alpha pts_pg 12.0 vs 1–11 others; Alpha low `reb_pg`, others high) + weak filler pool; `DraftBoard(service, keepers)` → `refresh()` → assert `relative_panel` visible, 9 rows, pts row tag "BUILD", reb row "PUNT"; second test without `my_team` → `relative_panel.isHidden()`.
6. `.\.venv\Scripts\pytest` + `.\.venv\Scripts\ruff check .` green; add a "Relative panel (P3)" section to `agents/006_board/status.md` (files, exact tag rules, `_category_gaps`/`_cat_fill` promotion note, pre-draft caveat).

## Files to Modify
- `ball_buddy/domain/recommend.py` — rename two privates, extend `__all__`
- `ball_buddy/ui/views/board.py` — panel widget, `_render_relative`, hide paths
- `tests/ui/test_board.py` — 12-team manual helper + 2 offscreen UI tests
- `agents/006_board/status.md` — P3 section

## New Files
- `ball_buddy/domain/relative.py` — `CatTag` + `category_tags`
- `tests/domain/test_relative.py` — tag-threshold tests incl. `to` direction

## Risks
- Keeper-based UI fixture: `_team_projections` silently drops keeper players not in the pool (board.py:314-341) — fixture pool must include every keeper name.
- 0.25 punt-close / top-3 are heuristic: expose as keyword defaults, document as draft-day tunables.
- Pre-draft zero inflation (recommend.py:186-191) → the `spread == 0 → COAST` guard keeps tags stable/noise-free early.
- Rank ties: fixed name-asc tiebreak so tags are deterministic and testable.