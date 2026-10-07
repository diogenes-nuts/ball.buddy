# State — ball.buddy: Draft helper rework (user: drop board, orient around recommendations; check autodraft repo)
(Rewrite this whole file at every checkpoint. Never append.)

"Told" = user has heard this from you in plain words.

## Status
- Position: NEW TASK — restructure draft helper per user's 3 directives (2026-10-06). Scouting N:/LLM/projects/autodraft web UI in progress (ls done: agents/006_ui, static/, autodraft/ board code).
- User directives (told yes, restated below):
  1. DRAFT BOARD IS UNNECESSARY — Yahoo draft client shows all board info. Draft helper should orient around PLAYER RECOMMENDATIONS (team need + draft value). User has a prior web-UI draft tracker in N:/LLM/projects/autodraft — CHECK IT for layout inspiration (agents/006_ui, static/, autodraft/board.py, 003_board docs).
  2. "My Team vs League" table: CATEGORIES AS TOP ROW (transpose — currently categories are rows); other data as rows beneath.
  3. GLOBAL RULE: every stat in the UI gets a color cue for relative strength — good=green, bad=red, neutral=uncolored, gradient between. (This is a cross-cutting theme.py-level rule; should go into tactile-cream usage / theme.py helper + all stat-rendering sites.)
- Exact next step: scout autodraft repo (006_ui + static/ + agents/006_ui docs) for the tracker's information layout → propose new draft-helper layout (recommendation-centric: current pick, top-N with reasons, relative panel transposed, scarcity strip; board grid removed/hidden but pick entry still needed? ASK or infer — picks must still be recorded locally for analysis; likely a slim "log the pick" strip instead of the full grid) → plan into 006_board dev.md → chain.
- Open question to resolve in design: keep a MINIMAL pick-entry affordance (current pick + enter pick + undo) since local analysis needs picks; the full 13×12 grid goes away.
- In flight: none uncommitted except .pi/state.

## Findings (told yes unless noted)
- All committed + pushed through 7cc9b2a; exe rebuilt w/ P1-P5; dist/data/players.csv fixed (was missing `source` col from pre-P5 headless write → app refused launch; now 200 rows source=hashtag; strict header check in players.py is intentional).
- players.csv FIELDNAMES NOW include `source` (P5): name..value, source, z_*, adp_source, notes.
- 006_board current: board.py (snake grid + suggest panel + P3 relative panel), setup_dialog.py (P1), recommend.py (P2 category-level), relative.py (P3 BUILD/COAST/PUNT), draft.py (view w/ offline banner + embedded board).
- P2: score = value + NEED_WEIGHT*need + SCARCITY_WEIGHT*scarcity; need = Σ min(g_c,f_c) 9-cat league-relative via engine.project_roster(usage_factor=1.0); reason strings; fallback to M2.3 when my_team unset.
- P3: category_tags (BUILD top-3 / PUNT bottom-3 + best remaining fill <25% gap / COAST); hidden w/o my_team.
- 001_data P4/P5 done: inbox auto-import (data/inbox/, sha-256, prev/undo, banners), reconcile name-join (Hashtag authority, Yahoo rows survive, blank-stat rows, source col, loud report in banner). 351 passed + 1 skipped, ruff clean at 7cc9b2a.
- 403 persists post dev-program acceptance → offline-first; Yahoo sync dead until auth.
- League: 12 teams, 13 rounds, 24 keepers, FAAB 100, top-4, pure 9-cat; draft Oct 15–20, 2026.
- User rules: mine-only relative lens; no timer/lock-in; all secured active; C2 rejected; name-join only (never rank).

## Verification
- Baseline: 7cc9b2a (pushed) — 351 passed + 1 skipped, ruff clean.
- Exe: rebuilt with P1-P5 + fixed players.csv; user to confirm it launches.

## Env gotchas (carry forward)
- Windows bash: FORWARD SLASHES everywhere (backslash args mangle).
- edit() atomic; non-ASCII oldText (em dash) fails.
- pyinstaller -y wipes dist/ — mv dist/data /tmp/bbdata first, restore after; close running exe first (file locks).
- python heredoc print w/ non-ASCII → cp1252 console crash; write files encoding="utf-8", avoid printing unicode.
- Subagent chains: sequential (local inference); scout→planner→worker→reviewer→fix; phase_complete → dev.md→done.md + doc commit → push.
- Stack: Py 3.14.7, PySide6 6.11.2, yfpy 17.0.0, cryptography 50.0.2, pytest 9.1.1, ruff 0.16.10, pyinstaller 6.22.3.
- Headless writes to dist/data/players.csv must use CURRENT FIELDNAMES (incl. source) or app won't launch.

## Dead ends
- Yahoo auth: all 403 post-acceptance (2026-10-08). Told yes.
- P2 position-level need: wrong level → category-level. Told yes.
