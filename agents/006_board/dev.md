# 006_board — dev

## Plan: Draft v2 (before 2026-10-15..20 draft; ~1 week)

Context: Yahoo 403 persists post-dev-program-acceptance → offline-first; the board is a
standalone draft-day sidecar (Yahoo's live draft room runs mechanics + timer + autopick).
User decisions (2026-10-08):

- Mine-only analysis: other teams are analyzed under the hood solely to surface my team's
  RELATIVE strengths/weaknesses (is a strength strong enough to compete; is a weakness
  too weak to salvage → punt).
- Recommender = B (need-aware vs league-relative gaps) + C1 (observed position scarcity
  from picks made so far — facts, not prediction). No C2 demand simulation (compounding
  errors across 11 managers; observation accumulates faster than the window where
  prediction would help). No timer/lock-in (Yahoo client has built-in timer + autopick;
  duplication is scope waste).
- Team projection during draft: ALL secured players count as active (draft picks +
  active keepers). No starter/bench distinction — it only matters in-season once >10
  players are playing on a day.
- Keepers: manual entry until/if Yahoo auth lands; setup dialog replaces the 24-row
  keeper grid as the manual-entry surface. Draft-order + team-name edits live there too.
- Migration into the season engine: deferred (assume auth eventually comes).

### P2 — Need-aware recommender (B + C1) — CATEGORY-LEVEL (spec correction 2026-10-06)
First pass implemented POSITION-level need (per-pos value totals); wrong level for a
9-cat H2H game — the compete/punt question is per-category. Rework required.

Team projection: `engine.project_roster(secured_rows, team_name, usage_factor=1.0)`
(all secured players active; no starter/bench). League median per category = median
across all teams' `cat_values[cat]`. My gap per cat: `gap_c` = how far I sit BELOW the
median in category c's better direction (higher for the 8, lower for `to`); positive =
I'm behind.

Normalization (category units are incomparable — PTS in hundreds, FT% a fraction):
`spread_c` = max−min of cat c across teams (0 → treat spread as 1). Normalized gap
g_c = gap_c/spread_c ∈ [0,∞); candidate fill f_c = player_c/spread_c for higher cats,
f_c = (1 − player_c/spread_c) for `to` (low-TO quality). 

Score per candidate = pool value + need + scarcity, where
`need = Σ_c min(g_c, f_c)` (gap actually filled, normalized units; [0, 9]) and
scarcity = max(0, median remaining count across positions − remaining count at the
candidate's primary position) (C1, unchanged). Weights as named module constants
(NEED_WEIGHT, SCARCITY_WEIGHT, default 1.0) for draft-day tuning.

Reason string: value bit + the top 2 gap-filling categories by filled amount
(e.g. "fills ft_pct & pts gaps") + scarcity bit when > 0.

Tests: need-beats-raw-value (candidate filling my weakest cat outranks higher-value
candidate filling nothing); `to` direction (low-TO player fills my TO gap, high-TO
doesn't); bias cancellation (uniform shift of a stat column keeps ordering); opted-out
keeper still eligible; my_team unset → M2.3 fallback. Exclusions unchanged.
Bench/starter: all secured players count.

### P3 — Relative panel
Per 9 categories: my team projection vs league distribution (all teams from picks so
far), with BUILD / COAST / PUNT tags. Live as picks are entered. (Tag thresholds
defined by planner from the league-relative distribution, e.g. percentile-based.)

Verification per phase: pytest + ruff green; offscreen UI tests where the app has them.
