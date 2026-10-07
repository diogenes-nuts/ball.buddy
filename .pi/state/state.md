# State — ball.buddy: projection pipeline COMPLETE (P4 inbox + P5 reconcile committed/pushed; draft Oct 15–20)
(Rewrite this whole file at every checkpoint. Never append.)

"Told" = user has heard this from you in plain words.

## Status
- Position: 001_data projection pipeline done: P4 import inbox (338 passed) + P5 name-join reconcile (351 passed), all committed + pushed (..7cc9b2a). No open phases anywhere.
- Exact next step: MEATBAG rebuilds exe (ask me or I do it) to get P4/P5 into the exe; then drop Hashtag HTML into dist/data/inbox/ and verify launch auto-import banner + undo. Draft-week remaining: run full offline rehearsal (Setup → import → picks → recommender/panel), tune NEED_WEIGHT/SCARCITY_WEIGHT.
- In flight: none (tree clean, pushed).
- Unresolved small item: import.html + import_files/ still on disk at repo root (gitignored; user blocked rm earlier) — ask if they want them deleted. Told no.

## Findings (told yes unless noted)
- P4 (told yes): data/inbox/ drop folder; launch scan + Rescan; SHA-256 dedupe (inbox_state.json); valid v4 → players.csv, players.prev.csv per scan (undo = pre-scan); unparseable → named error banner, file stays; pool_changed invalidates board/recommender cache; manual inbox import records state.
- P5 (told yes): name-join ONLY (never rank); Hashtag = projection authority (matched → replace); Yahoo rostered players appended blank-stat (rank/value "—", engine zeros) and SURVIVE later Hashtag imports; wired into both inbox auto-import + manual import via yahoo_players_from_snapshot(snapshot.json) — offline-safe no-op; loud "N replaced, M new, K kept — orphans: …" in inbox banner. FA pool out of scope until auth lands.
- Reviewer caught P5 dead-code Yahoo path pre-fix → now live snapshot-backed (both call sites).
- Draft v2 (006_board P1-P3) done (9c174c2): setup dialog, category-level recommender, BUILD/COAST/PUNT panel.
- 403 persists post dev-program acceptance → offline-first.
- League: 12 teams, 13 rounds, 24 keepers, FAAB 100, top-4, pure 9-cat; draft Oct 15–20, 2026.
- User rules: mine-only relative lens; no timer/lock-in; all secured active; C2 rejected.

## Verification
- Baseline: 7cc9b2a (pushed) — 351 passed + 1 skipped, ruff clean.
- dist/ exe has P1-P3 but NOT P4/P5 (needs rebuild).

## Env gotchas (carry forward)
- Windows bash: FORWARD SLASHES everywhere.
- edit() atomic; non-ASCII oldText (em dash) fails.
- pyinstaller -y wipes dist/ — mv dist/data aside, restore after; close running exe first (file locks).
- python heredoc print with non-ASCII → cp1252 console crash on Windows; write files with encoding="utf-8" (fine), avoid printing unicode.
- Subagent chains: sequential (local inference); scout→planner→worker→reviewer→fix; phase_complete → dev.md→done.md + doc commit → push.
- Stack: Py 3.14.7, PySide6 6.11.2, yfpy 17.0.0, cryptography 50.0.2, pytest 9.1.1, ruff 0.16.10, pyinstaller 6.22.3.

## Dead ends
- Yahoo auth: all 403 post-acceptance (2026-10-08). Offline path is the plan. Told yes.
- P2 position-level need: wrong level → category-level. Told yes.
