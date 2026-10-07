# 006_board — done

## 2026-10-03 — M2.1 — Keeper entry (slice 1/3 of draft board): keepers domain model (team, pool-bridged player, cost round, opt-out), atomic persistence to data/keepers.json, bulk entry grid in Draft view (24 keepers, per-team cap validation, loud unmatched flags, cap-drop alert). 128 tests green, ruff clean.

- `domain/keepers.py`: model + validation (max 2 active/team, cost round 1–13, duplicate player across teams = error); opt-out semantics (player back to pool, pick back to team).
- `data/keepers.json` via `io/state.py` atomic save/load; corrupt >2-per-team files → loud cap-drop alert, no silent loss.
- `ui/views/draft.py`: entry grid (team, player + pool lookup, cost round, opt-out), per-row resolved/unmatched status, save flow; pool loaded once per refresh (no N+1).
- Post-review fixes: silent cap-drop surfaced via banner-alert; pool-load N+1 removed.
- Verify: 128 passed / 1 skipped, ruff clean, offscreen smoke OK (save → round-trip → unmatched flag → cap-drop alert).

## 2026-10-03 — M2.2 — Snake draft board view (slice 2/3): 12-team snake order with keeper-aware forfeited picks (opted-out keepers leave picks open), pick entry with pool lookup, undo-last, current-pick highlight, atomic persistence to data/draft_picks.json. 147 tests green, ruff clean; reviewer-caught even-round forfeit bug fixed.

- Pick model + atomic persistence (`data/draft_picks.json`); snake order 12-team x 13 rounds mirroring `league.snake_order`.
- `ui/views/board.py`: 13x12 grid; forfeits "Keeper: <name>"; current pick = first unentered open pick (forfeits consume overall numbers — R2 order 2 = overall 3); undo-last; click/tab navigation.
- Reviewer caught CRITICAL: even-round keeper cells rendered "Keeper: ?" (`_slot_of` used start-order slot instead of snake order). Fix: `_order_of` (odd rounds index+1, even rounds len-index), `_keeper_cells` keyed by snake order; +2 tests (even-round forfeit, opted-out even-round stays open). Also fixed round-13 cells unclickable (bounds check used 12 not grid rowCount 13).
- Verify: 147 passed / 1 skipped, ruff clean, offscreen smoke (even-round keeper cell, round-13 click) OK.

## 2026-10-03 — M2.3 — Pool value recommender (slice 3/3 — M2 complete): per-pick top-N suggestions from real pool rank/value/pos columns, excludes drafted picks + active keepers (opted-out keepers stay draftable), unranked rows show dash. 162 tests green, ruff clean; all ROADMAP M2 exit criteria verified.

- `domain/recommend.py`: top-N per current pick from pool `rank`/`value`/`pos`/`name` only (no invented stats); exclusion = drafted picks + non-opted-out keepers, alias-bridged both sides.
- `board.py` suggest panel: updates per current pick; unranked rows `rank=None` → "—".
- Post-review fixes (all 3 nits pinned with tests): opted-out keepers stay suggestable; unranked rank None (was max+1 = invented "200"); 12-team shape covered by domain test.
- Verify: 162 passed / 1 skipped, ruff clean, offscreen smoke (opted-out keeper, unranked dash) OK. **ROADMAP M2 exit criteria all verified.**

## 2026-10-06 — P1 — Draft v2 P1: Setup dialog (draft order, team names, keepers w/ opt-out, my-team flag) replaces the keeper grid + manual team list; includes 002_yahoo refresh-redirect_uri fix (invalid_grant on first post-expiry sync)
- `ui/views/setup_dialog.py`: teams & draft-order table (rename, Add/Remove, Move up/down, "My team" checkbox) + keepers table (team combo, player pool completer, cost round 1–13, opt-out, resolved/UNMATCHED status w/ "try <suggestions>" hints). Writes settings manual_teams + manual_draft_order (ordered list) + my_team, and keepers.json; validate/empty/duplicate-name errors block Save; corrupt keepers.json refuses save.
- `draft.py`: keeper grid removed → pointer to Setup; League Settings "Team list (offline)" field removed; board `setup_requested` signal + "Setup…" button, rebuild on accept.
- `002_yahoo` fix (landed in this commit): refresh grant must replay the EXACT grant redirect_uri (OAuth2 4124 §6); token dict persists callback_uri; old hardcoded https://www.yahoo.com caused 400 invalid_grant "invalid refresh token" on first post-expiry sync.
- Review fixes: duplicate/empty team names block Save; status column suggestions; 3 new UI tests.
- Verify: 299 passed / 1 skipped, ruff clean.

## 2026-10-06 — P2 — Draft v2 P2: need-aware recommender reworked to CATEGORY-level (9-cat via engine.project_roster, league-median gap fill normalized by per-cat spread, `to` direction handled, C1 scarcity, reason strings) after first position-level pass was rejected as wrong level
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
- Review pass: fill clamped to [0,1] both directions; 'value 0' vs 'no pool value' reason distinction; pre-draft pct-dilution limitation documented. Verify: 309 passed / 1 skipped, ruff clean.

## 2026-10-06 — P3 — Draft v2 P3: relative panel — per-category my-team-vs-league with BUILD/COAST/PUNT tags (top-3 BUILD; bottom-3 PUNT when best remaining undrafted fill closes <25% of the normalized gap; else COAST), live per pick
### P3 — Relative panel
Per 9 categories: my team projection vs league distribution (all teams from picks so
far), with BUILD / COAST / PUNT tags. Live as picks are entered. (Tag thresholds
defined by planner from the league-relative distribution, e.g. percentile-based.)
- Impl: domain/relative.py category_tags (top_n=3 / bottom_n=3 / punt_close=0.25, 'to' direction handled, pre-draw COAST fallback, no-my-team → hidden); P2 helpers promoted public (category_gaps / cat_fill); board panel wired to the same refresh as the suggest panel. Verify: 321 passed / 1 skipped, ruff clean; review PASS, zero defects.

## 2026-10-07 — P6 — Scorer port: autodraft ValueGapScorer (0.45 market + 0.55 fit, hole/ok/covered multipliers, REACH/VALUE tags, value-gap flag) in domain/scorer.py; P2 need/scarcity demoted to reason bits; M2.3 fallback kept
### P6 — Scorer port (domain, offline-testable)
Port autodraft engine/scoring.py ValueGapScorer + needs.py edge math to ball_buddy
domain (new module or extend recommend.py; read the autodraft sources for the exact
formulas): market = (rankMax − rank)/rankMax; fit = Σ weight·z·multiplier over 9 cats
using the pool's z_* columns (blank z → 0, player excluded from fit contribution);
per-category edge = roster signed-z mean per slot vs pool mean, status hole/ok/covered
(covered ≥ +0.5z — re-derive thresholds against our 9-cat pool, document); score =
0.45·market + 0.55·fit_norm + tag adjustments (REACH/VALUE vs ADP-vs-overall-pick,
±0.10); value-gap flag (top-decile rank, ADP > 2 rounds past decile floor). Keep
P2's league-relative need + C1 scarcity as ADDITIONAL reason bits (they're still
true); score itself is autodraft's. Keep the M2.3 fallback (no my_team → plain rank).
Candidates enforce ownership (exclude drafted+active keepers; opted-out draftable).
- Impl: domain/scorer.py (market/fit/tags/gap-flag; z from pool z_* cols; per-slot edge hole/ok/covered); P2 recommend_need_aware score replaced, need+scarcity kept as reason bits; board call-site swap only. Verify: 364 passed / 1 skipped, ruff clean; review PASS (3 non-blocking nitpicks left as-is).
