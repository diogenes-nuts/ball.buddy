# 006_board — dev

## M2.3 — Pool value recommender (slice 3/3)

Scope: per-pick value rankings from the pool (salvage autodraft `004_engine` ValueGapScorer if still applicable; if the salvaged scorer is too board-coupled, a simpler position-aware rank on pool value columns is acceptable — planner decides from actual code).
- "Suggested" panel per current pick: top-N pool players with value; excluded if already drafted/kept (incl. active keepers).
- Exit criteria (ROADMAP M2): board shows 12-team snake with all forfeited keeper picks; keeper entry round-trips; recommender rankings sane on the real pool.
