# State — ball.buddy: Draft v2 (offline-first draft mode rework, before Oct 15–20 draft)
(Rewrite this whole file at every checkpoint. Never append.)

"Told" = user has heard this from you in plain words.

## Status
- Position: refresh-URI bug fixed + exe rebuilt (dist has fix; uncommitted in tree). User re-ran exe: **403 "application is not authorized" — dev-program acceptance did NOT lift the wall** → offline-first is the plan.
- Draft v2 planning DONE with user (design interview complete, told yes). Plan written to agents/006_board/dev.md: P1 setup dialog (order/names/keepers/my team), P2 need-aware recommender (B + C1), P3 relative panel (BUILD/COAST/PUNT).
- Exact next step: launch P1 subagent chain (scout → planner → worker → reviewer → worker-fix).
- In flight: uncommitted tree (oauth.py, sync.py, 2 test files — refresh fix; dev.md rewritten). Refresh fix verified 290 passed + 1 skipped, ruff clean; not yet live-validated (403 blocks full sync).

## Findings (design decisions, all told yes)
- Mine-only: other teams analyzed under the hood only to surface my relative strengths/weaknesses (compete vs punt).
- Recommender = B (need-aware vs league-relative gaps, same pool → bias cancels) + C1 (observed pos scarcity = facts). NO C2 (11-manager demand sim: compounding errors; observation outpaces prediction window). NO timer/lock-in (Yahoo has built-in timer + autopick; user: "if I ever timeout, I've failed").
- Draft-time team projection = sum of ALL secured players (picks + active keepers); NO starter/bench distinction (only matters in-season, >10 playing in a day).
- Keepers: manual via setup dialog unless Yahoo auth lands first. Migration to season engine deferred (assume auth eventually comes).
- Draft: Oct 15–20, 2026; ~1 week to build.
- 403 wall: persists even after dev-program acceptance. Told yes.

## Verification
- Baseline: 3c51674 (pushed) + uncommitted refresh fix: 290 passed + 1 skipped, ruff clean.
- Live: sign-in/code exchange work; league fetch 403. Told yes.

## Env gotchas (carry forward)
- Windows bash here: forward slashes (./.venv/Scripts/python); pyinstaller args also need forward slashes (ball_buddy\main.py mangled to ball_buddymain.py).
- edit() call atomic; non-ASCII oldText (em dash) fails.
- pyinstaller -y wipes dist/ — mv dist/data aside first.
- Stack: Py 3.14.7, PySide6 6.11.2, yfpy 17.0.0, cryptography 50.0.2, pytest 9.1.1, ruff 0.16.10, pyinstaller 6.22.3.
- Local inference: sequential subagent chains only.

## Dead ends
- Yahoo app authorization: re-sign-in/PKCE/scope (pre-acceptance) AND dev-program acceptance (2026-10-08) — all 403. Don't retry auth as a plan dependency; assume offline. Told yes.
