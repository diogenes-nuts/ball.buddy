# 003_league — status

Local league model over the Yahoo snapshot: teams, rosters, draft order, schedule.

## Files

- `ball_buddy/domain/league.py` — league/teams/draft-order/schedule model; salvaged `snake_order` + config loaders from autodraft; manual team-order mapping (`_manual_order_for` in the League view applies saved names, drops stale, appends new).
- `ball_buddy/io/yahoo/snapshot.py` — snapshot document shape (see 002_yahoo status).
- `ball_buddy/ui/views/league.py` — League page: snapshot table, stale/offline notice, Settings dialog (with a destructive "Reset all data…" button behind an explicit confirm, wired to `SyncService.reset_all_data`, M7.2). Schedule pane shows only the leader's own rows: a bye row renders only when it belongs to that team (R1a — `or entry.get("bye")` previously leaked every team's bye into the pane); the opponent column relies on the snapshot's team_a<team_b invariant (comment in code). R2: the post-sync "ok" banner surfaces `SyncResult.extra["warnings"]` (e.g. "token not persisted: no refresh_token") inline after "Synced just now.".

League rules baked in per agents/SPEC.md §1.1: 12 teams, snake 14 rounds (R1b: `DRAFT_ROUNDS = 14` now lives in `domain/league.py`; SPEC §1.1 still reads "13 rounds + conditional 14th IR slot" — implementation follows the review plan's 14, SPEC reconciliation is an owner decision), 14-slot roster (10 active + 3 BN + 1 conditional IR), 2 keepers/team, FAAB $100 only add path, 3 adds/wk, top-4 playoffs.

Plans: dev.md (none active). History: git log.
