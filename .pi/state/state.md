# State — ball.buddy: Draft v2 complete; user loading projection pool from import.html (Hashtag import-v4)
(Rewrite this whole file at every checkpoint. Never append.)

"Told" = user has heard this from you in plain words.

## Status
- Position: Draft v2 (P1 setup dialog / P2 category-level recommender / P3 relative panel) ALL DONE, committed + pushed (3c51674..9c174c2). Exe rebuilt with P1+P2+P3, dist/data/ restored (settings+token+cert).
- ACTIVE TASK: user wants to "integrate my projections" → pointed me at `import.html` (repo root, 2.2MB) — it IS a saved Hashtag import-v4 page (same format the app's Pool→"Import pool" already handles; saved from hashtagbasketball.com/import-v4). So no new importer needed: load via existing Pool import dialog, or run importer headless to pre-populate dist/data/players.csv.
- Exact next step: verify importer parses import.html (ball_buddy/io/pool/importer.parse_file / in-app dialog), then either (a) tell Meatbag: run exe → Pool view → Import pool → pick import.html → review unmatched table → Save, or (b) run the parse headless and write dist/data/players.csv. Then confirm recommender/panel light up with real data.
- In flight: none committed; import.html is at repo root (untracked — decide: leave untracked or gitignore; data artifacts live in gitignored data dirs).

## Findings (told yes unless noted)
- Pool = data/players.csv canonical FIELDNAMES: name, pos, team, gp, mpg, pts_pg, reb_pg, ast_pg, stl_pg, blk_pg, to_pg, fg_pct, fga_pg, ft_pct, fta_pg, three_pg, adp_round, rank, value, z_*(9), adp_source, notes. Told yes (column table).
- Engine consumes gp × per-game rates; FG%/FT% need fga_pg/fta_pg for attempt-weighted pooling (project_roster). z_*/mpg/notes NOT consumed by draft mode.
- P2 recommender: score = value + NEED_WEIGHT*need + SCARCITY_WEIGHT*scarcity (constants in domain/recommend.py, draft-day tuning knobs); need = Σ min(g_c, f_c) 9-cat league-relative (engine.project_roster usage_factor=1.0, all secured active); C1 scarcity = remaining pos count vs median. Reason strings. Fallback to M2.3 ranking when my_team unset. Known limitation: pre-draft pct-cat signal diluted (documented).
- P3: domain/relative.py category_tags — BUILD top-3 / PUNT bottom-3 + best remaining undrafted fill <25% normalized gap / else COAST; hidden w/o my_team; pre-draw COAST fallback.
- P1: ui/views/setup_dialog.py (order/names/keepers/my_team → settings + keepers.json); keeper grid → pointer; League offline team list removed.
- 403 "application is not authorized" persists AFTER dev-program acceptance (2026-10-08) → offline-first; refresh-redirect_uri bug (invalid_grant) fixed in same window (recorded 002_yahoo status).
- League: 12 teams, 13 rounds, 24 keepers, FAAB 100, top-4, pure 9-cat. Draft Oct 15–20, 2026 (~1 week).
- User rules: mine-only relative lens; no timer/lock-in (Yahoo owns it); all secured active (no starter/bench); C2 demand-sim rejected (his endorsement of my reasoning).

## Verification
- Baseline: 9c174c2 (pushed) — 321 passed + 1 skipped, ruff clean.
- Exe build: P1+P2+P3 in dist; user closed old running exe (PID lock broke first build attempt).

## Env gotchas (carry forward)
- Windows bash here: FORWARD SLASHES everywhere — backslash args mangle (pyinstaller ball_buddy\main.py → ball_buddymain.py; .\.venv\ fails).
- edit() call atomic (one bad edit kills all); non-ASCII oldText (em dash) fails — match pure-ASCII regions.
- pyinstaller -y wipes dist/ — mv dist/data aside FIRST, restore after. Running ball.buddy.exe locks dist files — close app before rebuild.
- Local inference: sequential subagent chains only; scout→planner→worker→reviewer→fix worker per phase; phase_complete commits, then dev.md→done.md archive + commit docs.
- Stack: Py 3.14.7, PySide6 6.11.2, yfpy 17.0.0, cryptography 50.0.2, pytest 9.1.1, ruff 0.16.10, pyinstaller 6.22.3. venv at .venv, Python system 3.14.7.

## Dead ends
- Yahoo auth: re-sign-in/PKCE/scope (pre-acceptance) AND dev-program acceptance (2026-10-08) all 403. Don't build against live sync; offline path is the plan. Told yes.
- P2 position-level need: wrong level for 9-cat game — reworked to category-level. Told yes.
