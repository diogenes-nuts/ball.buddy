# 006_board — status

Draft-day board (first feature per SPEC §1.2). **M2 complete** (M2.1 keepers, M2.2 snake board, M2.3 recommender).

## Files

- `ball_buddy/domain/keepers.py` — keeper model: team, player (pool-bridged via `naming`), cost round (1–13), `opted_out`. Opt-out semantics per SPEC §1.1: player back to pool eligibility, cost-round pick back to team. Validation: max 2 active keepers/team, cost round 1–13, no duplicate player.
- `ball_buddy/domain/picks.py` (or wherever M2.2 placed the pick model — see git) — pick model: round, snake order, team, player (pool-bridged or null), forfeited flag.
- `data/keepers.json`, `data/draft_picks.json` (gitignored) — atomic persistence via `io/state.py`.
- `ball_buddy/ui/views/draft.py` — keeper entry grid (24 rows: team, player + pool lookup, cost round, opt-out), resolved/unmatched status, cap-drop alert.
- `ball_buddy/ui/views/board.py` — snake board: 13 rounds x 12 picks grid, snake order (`_order_of` mirrors `league.snake_order`; even rounds reversed), keeper forfeits shown as "Keeper: <name>" (opted-out keepers leave the pick open), current pick highlighted (first unentered open pick; forfeits consume overall numbers), pick entry with pool lookup + quick commit, undo-last, tab/click navigation.
- `tests/ui/test_board.py` — snake math, forfeited computation (odd + even rounds, opted-out), pick persistence + undo, offscreen UI tests.

## Recommender (M2.3)

- `ball_buddy/domain/recommend.py` — per-pick top-N from real pool columns (`rank`, `value`, `pos`, `name`); excludes drafted picks + active keepers; **opted-out keepers stay draftable/suggestable** (their pick isn't forfeited); unranked rows carry `rank=None` → UI "—" (no invented numbers).
- Suggestion panel in `board.py` updates per current pick; alias bridging both sides.

Plans: dev.md. History: git log; done.md.
