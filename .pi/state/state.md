# State — ball.buddy: projection import pipeline (P4 inbox committed; P5 reconcile next)
(Rewrite this whole file at every checkpoint. Never append.)

"Told" = user has heard this from you in plain words.

## Status
- Position: 001_data. P4 import inbox DONE + phase-committed (338 passed, ruff clean). Doc archive of P4 (dev.md→done.md) + doc commit in flight NOW. Then P5 (Hashtag∪Yahoo reconcile) chain.
- Exact next step: (1) rewrite dev.md removing P4 (create done.md w/ P4 header), git commit docs; (2) launch P5 chain (scout→planner→worker→reviewer→fix).
- In flight: 001_data dev.md/done.md doc edits only.

## Findings (told yes unless noted)
- User's projections = saved Hashtag import-v4 HTML, top-200 only; Hashtag updates regularly → wants automation. Told yes.
- P4 built (told yes): data/inbox/ drop folder; launch scan + Rescan button; SHA-256 per file in inbox_state.json; auto-import valid v4 → players.csv (prev → players.prev.csv, ONE per scan = undo restores pre-scan); unparseable → named error banner, file stays; pool cache invalidated (pool_changed signal, board offline branch reloads); manual import of inbox file recorded in state; in_inbox() canonical path check.
- P5 spec agreed (told yes): name-join ONLY (user: Yahoo ranks ≠ Hashtag ranks — never join on rank; rank col = Hashtag rank when present, None for Yahoo rows); Hashtag = projection authority (replace on match); Yahoo rows (rosters+FA pool, name/pos/team, blank stats) survive re-imports; loud added/replaced/orphan counts; test vs mock Yahoo doc offline; live only when auth lands.
- import.html + import_files/ at repo root: user's rm was BLOCKED by user → gitignored instead; files still on disk. Told no — ask user if they still want them deleted.
- Draft v2 (006_board P1-P3) complete + pushed (9c174c2): setup dialog, category-level recommender, BUILD/COAST/PUNT panel. Exe has all of it.
- 403 persists post dev-program acceptance → offline-first (002_yahoo status updated).
- League: 12 teams, 13 rounds, 24 keepers, FAAB 100, top-4, pure 9-cat; draft Oct 15–20, 2026.
- User rules: mine-only relative lens; no timer/lock-in; all secured active; C2 rejected.

## Verification
- Baseline: P4 phase commit — 338 passed + 1 skipped, ruff clean.
- dist/data/players.csv = 200 rows from import.html (headless pre-populated earlier); dist/data/ restored into rebuilt exe.

## Env gotchas (carry forward)
- Windows bash: FORWARD SLASHES everywhere (backslash args mangle).
- edit() atomic; non-ASCII oldText (em dash) fails.
- pyinstaller -y wipes dist/ — mv dist/data aside, restore after; close running exe first (file locks).
- Subagent chains: local inference → sequential; scout→planner→worker→reviewer→fix; phase_complete commits then dev.md→done.md + doc commit.
- Stack: Py 3.14.7, PySide6 6.11.2, yfpy 17.0.0, cryptography 50.0.2, pytest 9.1.1, ruff 0.16.10, pyinstaller 6.22.3.

## Dead ends
- Yahoo auth: all 403 post-acceptance (2026-10-08). Offline path is the plan. Told yes.
- P2 position-level need: wrong level → category-level. Told yes.
