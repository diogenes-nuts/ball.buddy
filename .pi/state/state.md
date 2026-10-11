# State — REVIEW-FIXES R1–R6: R1,R2,R3,R4,R5a,R5b all implemented; R5b mid-commit (006+001 pending), then R6

## Status
- Position: R5b fully implemented + reviewer PASS + cosmetic naming.py hoist applied + tests/domain 169 green + ruff clean + exe rebuilt (dist/data restored, 9 entries).
- Exact next step: (1) phase_complete 006_board R5b (summary: _roster.py quad mtime cache + clear_cache; board render _team_projections computed once + _last_excluded names-model guard with refresh() reset; sweeps 002 R5a doc bookkeeping) and 001_data R5b (summary: naming.bridge precomputes (norm,base,suffix,last,displays) pool triples once per call; reviewer cosmetic hoist applied); (2) bookkeeping for 006+001: dev.md R5 mark (006: "R5 (done — …)" in its Participates line; 001: mark R5 bridging precompute done in its plan line), done.md append under each tool's EXACT header (get from their calls), status.md: 002_yahoo R5a section ALREADY WRITTEN + 002 dev.md/done.md R5a ALREADY DONE — those landed in R5a commit's next commit = R5b commit; (3) then R6 chain (tiny), then FINAL REPORT.
- R5b worker/reviewer facts for done.md sections: _roster.py: single-entry module cache _QUAD_CACHE keyed (str(data_dir), st_mtime_ns×4 of players.csv/keepers.json/draft_picks.json/aliases.json, existence-aware None); _quad() (:41) returns (pool,keepers,picks,aliases); both _resolve_pool_names (:72) and team_roster_rows (:101) consume it → double pool-load fixed; clear_cache() :67; service.aliases_path is the aliases path (sync.py:90). NEW test test_quad_cache_hits_and_invalidates in tests/ui/test_roster.py (monkeypatched load counter + os.utime mtime bump + clear_cache). board.py: projections computed once at render() :788, threaded as PARAM (default None→self-compute fallback) into _render_recs (:833) + _render_relative (:832); old inline 3rd site ~:1029 now uses the local; self._last_excluded :391 stored attr, guard :793-801, refresh() resets it :714 (worker's fix — guard initially broke 3 search-dropdown tests). naming.py: pool_pre precompute :87-93 (now a for-loop with local base/suffix hoist — reviewer's cosmetic suggestion applied), containment :122 + _suggest :144-171 (signature now takes pool_pre, internal-only; call sites :106/:138); matching semantics byte-equivalent vs HEAD (reviewer verified, incl. empty-base rows still in pool_pre but last="" filters identically; containment keeps `if not pool_base: continue`).
- R5b test results (reviewer): tests/domain 169; tests/ui per-file (roster, board, matchup, lineup, trade, waiver, draft_view) 65 passed; ruff clean. NOTE reviewer: tests/ui/test_draft.py does NOT exist — it's test_draft_view.py.
- R5a (002, committed): load_last_cached memo st_mtime_ns over (snapshot.json, players.csv, aliases.json) existence-aware; invalidation reset_all_data/save_sign_in/save_aliases/run; effective_snapshot through cache; 5 view init sites switched (league.py:244, lineups:198, matchup:249, trades:185, waivers:172); league.py:279/296/627/665 stay uncached (post-mutation). 5 new tests in test_sync.py (counter=1, players.csv re-bridge, aliases re-bridge, reset+run, uncached). Reviewer PASS (shared SyncResult read-only; SyncWorker QThread only calls run(); manual/offline fallback intact).
- R4 (006, committed): Suggestion +market +fit_z (renamed from fit_norm post-reviewer); fit_z = RAW weighted fit (documented deviation), None only hi==lo; market None unranked; reason strings byte-identical (reviewer: rare ~100/3000 (rank,rank_max) 1% mkt shift from 2dp truncation — spec-accepted); board _mkfit reads fields, _MKT_RE/_FIT_RE+re import deleted; _gap_names top_rank hoisted O(n²)→O(n) + test_value_gap_floor_over_duplicate_worst_rank_decile_members.
- ⚠ CODEMODE TRUNCATION INCIDENT: codemode tools.read truncates at 50KB — board.py (56KB) got truncated-READ then write-back CORRUPTED it (lost 120+ lines). git checkout restored it; re-applied R4 board edits via edit tool. RULE: for files >50KB, NEVER read+rewrite in codemode — use edit with fresh oldText, or bash python scripts for whole-file transforms.
- R3 (all 5 components, committed + bookkept): shared ui/views/_roster.py + _common.py; naming._suggest pool_norm_all drop; league.py docstring merge + __all__ bottom.
- Rules in force: subagent chains one phase per chain; phase_complete ONLY commits; per-file pytest (NEVER tests/ui dir or tests full — exit 127; use tests/domain or tests/io or tests/services dirs OK); `.venv/Scripts/python -m pytest`; ruff clean (E501=100); rebuild exe after code changes (mv dist/data /tmp/bb_data_backup → pyinstaller -y → restore); doc protocol: after phase_complete → dev.md mark + done.md append under tool's EXACT header + status.md section (lands in NEXT commit).

## Verification
- Committed green: R1 (excepthook 3, keepers 19, league_view 15, board 28, matchup 10, draft 5, domain 168); R2 (io 95+1sk, services 15, league_view 16); R3 (12 ui files, domain 168); R4 (recommend+scorer+board 61, domain 169); R5a (services 20, io 95+1sk, 7 ui files 84).
- Uncommitted (will land in R5b commit): R5b code (tests: domain 169, ui per-file 65) + 002_yahoo R5a doc bookkeeping (dev/done/status).
- Exe: rebuilt after R1b, R2, R3, R4, R5a, R5b (dist/data restored each time, 9 entries).
- Tree: clean except .pi/state/state.md + uncommitted R5b code/docs listed above.

## Findings (told)
- R2 scout: yahoo_oauth NOT installed (in-app oauth.py); yfpy HTTPError-w-response/bare(999)/YahooFantasySportsDataNotFound; yfpy auto-refreshes 401. Final report.
- Live league still 403 app-authorization wall → R2 live check (AGENTS.md step 5) may only do sign-in + offline fallback; user hasn't run it — request in final report. Told.
- .pi/state/state.md tracked by git; R6 gitignores only .pi/reports/. Not told.
- SPEC §1.1 13-vs-14 rounds — owner decision pending (003 status/done). Told.
- R3: 4 roster copies had NO behavioral differences (rows-vs-names split preserved). Final report.
- R4: fit_norm→fit_z rename (misleading name); mkt % rare 1% shift spec-accepted. Final report.
- R5b reviewer: test_draft.py doesn't exist (it's test_draft_view.py); naming.py cosmetic hoist applied. Internal.
- Ownership map: matchup.py=004; picks/keepers/board.py=006; domain/league.py+views/league.py=003; waivers/trades/lineups/waiver.py/trade.py=005; naming/players/importer=001; io/yahoo+sync=002; main/README/hygiene=scaffold.
- phase_complete tool headers dated 2026-10-11 (clock) — keep verbatim.

## R6 targets (full detail in agents/REVIEW-FIXES.md §R6)
One tiny chain; components 001+005+004+scaffold: 1 players.py:27 delete unused _by_raw; 2 trades.py:339 delete no-op `if layout is not None: del layout`; 3 matchup.py init self._roster_players=((),()) + drop getattr in _render_tables; 4 lineups.py _render (~:248-250 RE-GREP) starter projections by NAME not positional players[i]; 5 DELETED item (verified absent); 6 importer.py validate_rows:242 skip blank-rank dup warning; 7 trade.py doc note only; 8 git rm .p1.txt .p2.txt .pytest_out.txt .r.txt tests/full_run.txt "Screenshot 2026-10-09 131142.png" (tracked; screenshot unreferenced) + .gitignore .pi/reports/ (only reports/, NOT .pi/state/). ROADMAP.md "review remediation complete" note. phase_complete per component. Then FINAL REPORT: all phases + exe each; SPEC 13-vs-14 decision request; .pi tracking note; R2 live-check request (403 wall caveat); R2 scout findings; R3 no-difference confirmation; R4 fit_z deviation + mkt shift; R6.5 verified-absent; R2.2 doc-only outcome.

## U-turns
- "tests/services 52 baseline" wrong (real 13→15). Internal.

## Dead ends
- `pytest tests/ui` / `pytest tests` dir — exit 127. Per-file/per-domain only.
- load_last() ok=False — ok-banner tests build SyncResult(ok=True) directly.
- codemode read+write on files >50KB = corruption (see incident above).
- codemode: `await` inside named `function` bodies fails (wrapper async, inner isn't) — use arrow functions.

## Goal (latest user request, verbatim)
Context is approaching the compaction threshold. Rewrite .pi/state/state.md in place now — this is the last chance before compaction; make it a complete rollup of the current state and update the active component's status.md/dev.md if a phase boundary was crossed. Then continue the task.

## Last assistant message (truncated)
PASS. Quick check on the reviewer's cosmetic note, then exe + commits:
