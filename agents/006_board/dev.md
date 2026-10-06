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

### P3 — Relative panel
Per 9 categories: my team projection vs league distribution (all teams from picks so
far), with BUILD / COAST / PUNT tags. Live as picks are entered. (Tag thresholds
defined by planner from the league-relative distribution, e.g. percentile-based.)

Verification per phase: pytest + ruff green; offscreen UI tests where the app has them.
