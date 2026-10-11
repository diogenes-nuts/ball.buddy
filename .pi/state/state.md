# State — REVIEW-FIXES R1–R6: ALL code+hygiene+ROADMAP committed. Tree CLEAN. Remaining: 005/004/scaffold R6 doc bookkeeping (3 phase_completes), then FINAL REPORT.

## Status
- Position: ALL R6 code, repo hygiene (git rm 6 junk + .gitignore .pi/reports/), and ROADMAP completion note are COMMITTED — they got swept into the "001_data R6" phase_complete commit (90866de), which swept the ENTIRE dirty tree (R6 code for all 4 components + pending 005/004/001 R5b doc bookkeeping + 006 R5b bookkeeping + state.md). Tree is now CLEAN.
- Exact remaining work: write R6 doc bookkeeping for the 3 components whose bookkeeping did NOT get swept (001's DID land in 90866de; 006 R5b bookkeeping also landed in 90866de). For EACH of 005_advisor, 004_engine, scaffold: (a) dev.md — mark R6 done; (b) done.md — append a section; (c) status.md — add R6 note. THEN phase_complete each (the commit carries only these doc edits — all code is already in 90866de). THEN FINAL REPORT.
- 005_advisor R6 = item 2 (trades.py: deleted no-op `layout=item.layout()`+`if layout is not None: del layout`; grid cell is widget XOR layout so `if item.widget() is not None:` branch unchanged), item 4 (lineups.py _render: starter `pts` now by-NAME via `proj_by_name={p.name:p for p in starter_proj.players}` — fixes positional misalign when a starter is missing from the pool; kept `enumerate` for the row index `i`), item 7 (trade.py: appended "(Review R6: mirrored-delta caveat is intentional — kept as documented, no code change.)" to the existing docstring paragraph; NO code change).
  - NOTE: 005 dev.md R6 line currently reads "trades dead line, validate_rows blank-rank warning" — IMPRECISE (validate_rows blank-rank is item 6 = 001/importer.py, not 005). Correct it in the mark to: trades del-layout no-op + lineups starter-by-name + trade.py doc note.
- 004_engine R6 = item 3 (matchup.py: added `self._roster_players: tuple[tuple,tuple]=((),())` in MatchupView __init__ (~:135); _render_tables `getattr(self,"_roster_players",((),()))` → `self._roster_players`).
- scaffold R6 = item 8 (git rm'd 6 tracked junk: .p1.txt .p2.txt .pytest_out.txt .r.txt tests/full_run.txt "Screenshot 2026-10-09 131142.png"; .gitignore appended `.pi/reports/` only) + ROADMAP.md note (moved the "Open plan — review remediation" section to "Done — review remediation (2026-10-14 → 2026-10-15)" + added "Rounds: 13 vs 14" to Open items). All in 90866de.
- R6 item 5 (setup_dialog settings["version"]) — verified absent, no action. R6 acceptance met: domain+io 264 passed/1 skip, UI per-file (matchup/lineup/trade/board) 50 passed, ruff clean, exe rebuilt (5747465 bytes, dist/data 9 entries).

## The 001_data R6 commit (90866de) swept (git show --stat):
.gitignore, .p1.txt, .p2.txt, .pytest_out.txt, .r.txt, Screenshot.png (deleted), .pi/state/state.md, agents/001_data/{dev,done,status}.md, agents/006_board/{dev,done,status}.md, agents/ROADMAP.md, ball_buddy/domain/players.py, ball_buddy/domain/trade.py, ball_buddy/io/pool/importer.py, ball_buddy/ui/views/lineups.py, ball_buddy/ui/views/matchup.py, ball_buddy/ui/views/trades.py, tests/full_run.txt. (21 files.)

## Committed bookkeeping already landed (do NOT rewrite):
- 001_data R6: dev/done/status all in 90866de.
- 006_board R5b + R4: done.
- 002_yahoo R5a: done.
- R3 (all 5): done.

## Phase history (all committed+bookkept)
- R1: R1a (006: main.py QMessageBox bug + bye-filter leak 003/006), R1b (003: DRAFT_ROUNDS=14 unified in domain/league.py, views import; matchup side-attribution 004).
- R2: 002 (signal-based error classifier 401→login/403→YahooError, fetch_all per-team min, _settings_of allowlist, OAuthError→LoginRequiredError, persist_token warning, README/AGENTS); 003 (ok-banner surfaces SyncResult.extra warnings — out-of-plan, accepted).
- R3: all 5 — shared ui/views/_roster.py (team_roster_rows/team_roster_names, _resolve_pool_names core) + _common.py (CAT_LABELS + _fmt_gap); naming._suggest pool_norm_all drop (001); league.py docstring merge + __all__ bottom (003). 4 roster copies had NO behavioral diff.
- R4: 006 — Suggestion +market +fit_z (renamed from fit_norm post-reviewer); fit_z = RAW weighted fit (documented deviation in scorer.py), None only hi==lo; market None unranked; reason strings byte-identical (rare ~100/3000 1% mkt shift spec-accepted); board _mkfit reads fields, _MKT_RE/_FIT_RE+re deleted; _gap_names top_rank hoisted O(n²)→O(n) + dup-worst-rank test.
- R5a: 002 — load_last_cached memo st_mtime_ns (snapshot.json,players.csv,aliases.json) existence-aware; invalidate reset_all_data/save_sign_in/save_aliases/run; effective_snapshot through cache; 5 view init sites switched (league:244,lineups:198,matchup:249,trades:185,waivers:172); league:279/296/627/665 stay uncached. 5 new tests.
- R5b: 006+001 — _roster.py single-entry _QUAD_CACHE (str(data_dir), st_mtime_ns×4, existence-aware), _quad()→(pool,keepers,picks,aliases), both resolvers consume (double pool-load fixed), clear_cache(); board _team_projections once + param into _render_recs/_render_relative, self._last_excluded guard (refresh() resets); naming bridge() pool_pre precompute.
- R6: all 4 — see Status above.

## ⚠ LESSONS (this session)
- codemode tools.read truncates at 50KB — board.py (56KB) truncated-READ + write-back CORRUPTED it → git checkout restored, re-applied via edit. RULE: files >50KB NEVER read+rewrite in codemode.
- codemode: `await` in named `function` body fails (wrapper async, inner isn't) → arrow functions. codemode tool args are OBJECTS (tools.read({path})).
- phase_complete SWEEPS THE ENTIRE dirty tree — any uncommitted doc bookkeeping from prior phases lands in whatever commit you call next. Keep the tree clean between phases OR expect sweeps (they're correct, just bundled).

## Rules in force
- subagent chains one phase per chain; phase_complete ONLY commits (sweeps everything); per-file pytest (NEVER tests/ui dir or tests full — exit 127; tests/domain+io+services DIRS OK); `.venv/Scripts/python -m pytest`; ruff clean (E501=100); rebuild exe after code changes (mv dist/data /tmp/bb_data_backup → pyinstaller -y → restore); doc protocol: after phase_complete → dev.md mark + done.md append under tool's EXACT header + status.md note (lands in NEXT commit).

## Verification (committed green)
- R6 final: domain+io 264 passed/1 skip; UI per-file (matchup/lineup/trade/board) 50; ruff clean.
- Exe rebuilt after R1b,R2,R3,R4,R5a,R5b,R6 (last: 5747465 bytes, dist/data 9 entries restored).
- Tree: CLEAN.

## Findings (told?)
- R2 scout: yahoo_oauth NOT installed (in-app oauth.py, OAuthError(RuntimeError)); yfpy HTTPError-w-response / bare(999) / YahooFantasySportsDataNotFound; yfpy auto-refreshes 401 internally. Told: no (FINAL report).
- League ok-banner warnings = out-of-plan R2 addition, bookkept 003 R2. Told: no.
- Live league still 403 app-authorization wall → R2 live check (AGENTS.md step 5) may only do sign-in + offline fallback; user hasn't run it — request in final report. Told: yes.
- .pi/state/state.md tracked; R6 gitignores only .pi/reports/. Told: no.
- SPEC §1.1 13-vs-14 rounds — owner decision pending (003 + ROADMAP Open items). Told: yes.
- R3: 4 roster copies NO behavioral diff. Told: no (FINAL).
- R4: fit_norm→fit_z rename; mkt rare 1% shift spec-accepted. Told: no (FINAL).
- R5b: tests/ui/test_draft.py does NOT exist (it's test_draft_view.py). Told: no.
- Ownership: matchup.py=004; picks/keepers/board.py=006; domain/league.py+views/league.py=003; waivers/trades/lineups/waiver.py/trade.py=005; naming/players/importer=001; io/yahoo+sync=002; main/README/hygiene=scaffold.
- phase_complete tool headers dated 2026-10-11 (clock) — keep verbatim.
- ball_buddy/engine/ does NOT exist — engine is ball_buddy/domain/engine.py (project_roster, PlayerProjection.name exists).

## FINAL REPORT contents (write after R6 bookkeeping commits)
- All phases R1→R6 done, reviewed, committed; exe rebuilt after each code phase.
- SPEC 13-vs-14 rounds decision request (owner).
- .pi tracking note (state.md is git-tracked; only .pi/reports/ gitignored).
- R2 live-check request (403 wall caveat — user hasn't run AGENTS.md step 5).
- R2 scout findings (yahoo_oauth absent, yfpy error shapes).
- R3 no-difference confirmation.
- R4 fit_z deviation + mkt 1% shift.
- R6.5 (settings["version"]) verified-absent.
- R2.2 doc-only outcome (per-team min kept).

## Dead ends
- `pytest tests/ui` / `pytest tests` dir — exit 127. Per-file/per-domain only.
- load_last() ok=False — ok-banner tests build SyncResult(ok=True) directly.
- codemode read+write on files >50KB = corruption.
- ROADMAP is at agents/ROADMAP.md, not repo root.

## Goal (latest user request, verbatim)
.pi/state/state.md is stale. Rewrite it in place now (one line per fact, changes as changes, told yes/no). Then continue the task.

## Last assistant message (truncated)
Tree is clean after the 001_data R6 phase_complete (swept all R6 code + hygiene + ROADMAP + pending bookkeeping). Writing R6 doc bookkeeping for 005/004/scaffold next.
