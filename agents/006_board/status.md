# 006_board — status

Draft-day board (first feature per SPEC §1.2). M2.1 done; M2.2 (snake board view) + M2.3 (value recommender) remaining in dev.md.

## Files (M2.1)

- `ball_buddy/domain/keepers.py` — keeper model: team, player (pool-bridged via `naming` when resolvable), cost round (1–13), `opted_out` flag. Opt-out semantics per SPEC §1.1: opted-out player returns to pool eligibility; the cost-round pick returns to the owning team. Validation: max 2 active keepers/team, cost round 1–13, no duplicate player across teams.
- `data/keepers.json` (gitignored) — persistence via `io/state.py` atomic writes. Corrupt/legacy files with >2 per team surface a loud cap-drop alert, never silently discarded.
- `ball_buddy/ui/views/draft.py` — Draft view: bulk keeper entry grid (up to 24 rows: team picker, player name with pool lookup, cost-round spinner, opt-out checkbox), resolved/unmatched status per row (unmatched flagged loudly, not blocking), save enabled on valid entries, alert banner (banner-alert token).

## Next (dev.md)

- M2.2: snake board view — 12-team order, keeper-aware forfeited picks, pick-by-pick entry/tracking.
- M2.3: pool-based value recommender (salvaged ValueGapScorer).

Plans: dev.md. History: git log; done.md.
