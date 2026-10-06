# State — ball.buddy: Draft v2 (P1 done+committed; P2 rework in flight — category-level scoring)
(Rewrite this whole file at every checkpoint. Never append.)

"Told" = user has heard this from you in plain words.

## Status
- Position: 006_board Draft v2. P1 (Setup dialog) DONE + committed (4d8763c, doc archive 70be56d). P2 first pass ran and "passed" review but I caught a DESIGN deviation: it implemented POSITION-level need (value totals per pos), not CATEGORY-level (9-cat) need — wrong for a 9-cat H2H game. Spec corrected in dev.md; rework chain launched.
- Exact next step: P2 rework subagent chain (worker rework → reviewer) running; on completion: phase_complete 006_board P2 (includes dev.md spec-correction text), archive to done.md, then P3 (relative panel BUILD/COAST/PUNT).
- P3 still open in dev.md (relative panel: my team vs league distribution per cat, BUILD/COAST/PUNT tags, live on pick entry).
- In flight: dirty tree = P2 rework (recommend.py, board.py, tests) once chain lands.

## Findings (told yes)
- 403 persists post dev-program acceptance → offline-first; Yahoo 403 = app-authorization, separate from program acceptance (recorded in 002_yahoo status).
- P2 spec (corrected, told no — user hasn't seen the correction; tell them): team projection = engine.project_roster(secured, usage_factor=1.0) (all secured active, no starter/bench); league median per cat across 12 teams; normalized gap fill via per-cat spread (max−min; 0→1); score = value + Σ min(g_c, f_c) + C1 scarcity; `to` direction handled (low-TO fills gap); weights NEED_WEIGHT/SCARCITY_WEIGHT constants; reason = value + top-2 filled cats + scarcity.
- User rules: mine-only (relative lens), no timer/lock-in (Yahoo owns it, "if I timeout I've failed"), all-secured-active, C2 rejected (my reasoning endorsed).
- engine.py has project_player/project_roster w/ pooled pct (3889.3% bug fix), CATS/COUNT_COLUMN/PCT_COLUMN/DIRECTIONS — REUSE, don't recompute.
- P1: setup dialog (setup_dialog.py), my_team in settings, keeper grid → pointer, league offline team list removed; 299 passed at P1.
- Pool CSV has all 9 cats + z-scores + rank/value/adp (FIELDNAMES in io/pool/importer.py).
- Draft Oct 15–20, ~1 week. 14 teams… no: 12 teams, 13 rounds, 24 keepers, FAAB 100, top-4, 9-cat pure. (League is 12 teams/156 picks.)

## Verification
- Baseline: 70be56d — 299 passed + 1 skipped, ruff clean (P1). P2 first pass reached 307 passed but is being reworked (position→category).

## Env gotchas (carry forward)
- Windows bash: forward slashes everywhere (pyinstaller backslash args mangle).
- edit() atomic; non-ASCII oldText (em dash) fails.
- pyinstaller -y wipes dist/ — mv dist/data aside.
- Local inference: sequential chains only.
- Stack: Py 3.14.7, PySide6 6.11.2, yfpy 17.0.0, cryptography 50.0.2, pytest 9.1.1, ruff 0.16.10, pyinstaller 6.22.3.

## Dead ends
- Yahoo auth: re-sign-in/PKCE/scope + dev-program acceptance all 403. Don't build against sync. Told yes.
- P2 position-level need: wrong level for 9-cat game (passes tests but answers the wrong question). Told no.
