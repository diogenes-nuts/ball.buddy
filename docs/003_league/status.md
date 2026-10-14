# 003_league — status

Local league model over the Yahoo snapshot: teams, rosters, draft order, schedule.

## Files

- `ball_buddy/domain/league.py` — league/teams/draft-order/schedule model; salvaged `snake_order` + config loaders from autodraft; manual team-order mapping (`_manual_order_for` in the League view applies saved names, drops stale, appends new).
- `ball_buddy/io/yahoo/snapshot.py` — snapshot document shape (see 002_yahoo status).
- `ball_buddy/ui/views/league.py` — League page: snapshot table, stale/offline notice, Settings dialog (with a destructive "Reset all data…" button behind an explicit confirm, wired to `SyncService.reset_all_data`, M7.2). Schedule pane shows only the leader's own rows: a bye row renders only when it belongs to that team (R1a — `or entry.get("bye")` previously leaked every team's bye into the pane); the opponent column relies on the snapshot's team_a<team_b invariant (comment in code). R2: the post-sync "ok" banner surfaces `SyncResult.extra["warnings"]` (e.g. "token not persisted: no refresh_token") inline after "Synced just now.".

League rules baked in per docs/SPEC.md §1.1: 12 teams, snake 13 rounds (R1b: `DRAFT_ROUNDS` lives in `domain/league.py`; owner 2026-10-15 confirmed SPEC §1.1 authoritative — `DRAFT_ROUNDS = 13`, the IR is a conditional 14th roster slot, not drafted), 14-slot roster (10 active + 3 BN + 1 conditional IR), 2 keepers/team, FAAB $100 only add path, 3 adds/wk, top-4 playoffs.

## R3 (2026-10-11)

- `domain/league.py` docstrings merged into one top-of-file doc (notes `DRAFT_ROUNDS` lives there, re-exported by picks); `ui/views/league.py` `__all__` moved to file bottom.
Plans: none active (R1b/R2/R3 complete — see done.md). History: git log; done.md.
