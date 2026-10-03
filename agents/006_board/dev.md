# 006_board — dev

## M2.2 — Snake draft board (slice 2/3)

Scope: the live board view.
- Draft order: 12-team snake (13 rounds) from the league snapshot's manual/saved order (`domain/league.py` snake_order), with keeper cost-round picks shown as forfeited/used for that team (opted-out keepers return the pick).
- Pick entry/tracking: current pick highlighted, enter a player (pool lookup), advance; undo last pick; persists to `data/draft_picks.json` (atomic).
- Board table: rounds down, picks per round, team + picked player (or "—" for forfeited keeper picks).
- UI: tactile-cream tokens only; offscreen-testable.

## M2.3 — Pool value recommender (slice 3/3)

Scope: per-pick value rankings from the pool (salvage autodraft `004_engine` ValueGapScorer if still applicable; if the salvaged scorer is too board-coupled, a simpler position-aware rank on pool value columns is acceptable — planner decides from actual code).
- "Suggested" panel per current pick: top-N pool players with value; excluded if already drafted/kept (incl. active keepers).
- Exit criteria (ROADMAP M2): board shows 12-team snake with all forfeited keeper picks; keeper entry round-trips; recommender rankings sane on the real pool.
