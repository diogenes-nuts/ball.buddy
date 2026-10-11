# State — REVIEW-FIXES R1–R6: R1–R5b ALL committed+bookkept. R6 code+hygiene EDITS DONE; next: ROADMAP note, tests, exe, then 4 phase_completes (001/005/004/scaffold), then FINAL REPORT.

## Status
- Position: ALL R6 code edits + repo hygiene APPLIED (uncommitted). 8/8 R6 items handled (item 5 was the deleted no-op — no action). Next: (1) ROADMAP.md note "review remediation complete" (file is agents/ROADMAP.md NOT root); (2) run per-file tests for touched areas; (3) ruff; (4) rebuild exe; (5) phase_complete 4×: 001_data R6 (players._by_raw + importer blank-rank dup-skip), 005_advisor R6 (trades del-layout no-op + lineups starter_proj by-name + trade.py doc note), 004_engine R6 (matchup _roster_players init + getattr drop), scaffold R6 (git rm 6 junk + .gitignore .pi/reports/ + ROADMAP note); (6) FINAL REPORT.
- R6 EDITS APPLIED (this turn, uncommitted):
  1. players.py: DELETED `self._by_raw = {row["name"]: row for row in self.rows}` (3 lines, was :27-29; unused — only the definition existed).
  2. importer.py validate_rows: `if rec.get("rank") in seen_ranks:` → `if rec.get("rank") and rec.get("rank") in seen_ranks:` (skip blank-rank dup warning — Yahoo rows all rank="").
  3. trades.py: deleted no-op `layout = item.layout()` + `if layout is not None: del layout` (was :293-295); now `item = takeAt(0)` then directly `if item.widget() is not None:` (del layout was a pure no-op — only deleted a Python ref, not the C++ object; grid cell is widget XOR layout so widget branch is unchanged).
  4. matchup.py: added `self._roster_players: tuple[tuple, tuple] = ((), ())` in MatchupView __init__ (after last_result, ~:135); changed _render_tables `getattr(self, "_roster_players", ((), ()))` → `self._roster_players`.
  5. lineups.py _render: `starter_proj.players[i]` positional → by-name `proj_by_name = {p.name: p for p in starter_proj.players}` then `player = proj_by_name.get(name); pts = player.values["pts"] if player is not None else 0.0` (fixes misalign when a starter is missing from the pool → starter_rows shorter than result.starters). Added a 2-line comment.
  6. trade.py: docstring note appended to the existing mirrored-delta paragraph "(Review R6: the mirrored-delta caveat is intentional — kept as documented, no code change.)" — NO code change.
  7. git rm'd 6 tracked junk: .p1.txt .p2.txt .pytest_out.txt .r.txt tests/full_run.txt "Screenshot 2026-10-09 131142.png" (rm_exit=0). Screenshot only referenced by the plan itself + state notes — safe.
  8. .gitignore: appended `.pi/reports/` (NOT .pi/state/ — that stays tracked).
- R6 item 5 (setup_dialog settings["version"]) — verified absent, NO action (already in plan as struck-through).

## What I still must verify before commit
- per-file tests: tests/domain (players/trade/importer touched → but importer is io, trade/players domain) → run `tests/domain` (dir OK) + `tests/io` (dir OK, importer) + per-file UI: test_matchup_view.py test_lineup_view.py test_trade_view.py.
- ruff clean (E501=100).
- exe rebuild (mv dist/data /tmp/bb_data_backup → pyinstaller -y → restore).
- lineups.py:340-343: I removed the `for i, ... in enumerate(...)` — confirm no leftover `i` references in that loop body (the enumerate was only for the positional index; the rest of the loop uses slot/name only).

## R5b (committed) — 006+001
- _roster.py single-entry _QUAD_CACHE (str(data_dir), st_mtime_ns×4 of players.csv/keepers.json/draft_picks.json/aliases.json, existence-aware); _quad() → (pool,keepers,picks,aliases); _resolve_pool_names + team_roster_rows both consume (double pool-load fixed); clear_cache(); aliases via service.aliases_path.
- board.py: _team_projections once in render() + param into _render_recs/_render_relative (None→fallback); self._last_excluded guard, refresh() resets.
- naming.py: bridge() pool_pre (norm,base,suffix,last,displays) precompute (for-loop, hoisted base/suffix); containment + _suggest (now takes pool_pre, internal) read it.

## R5a (committed) — 002
- load_last_cached memo st_mtime_ns (snapshot.json,players.csv,aliases.json) existence-aware; invalidate reset_all_data/save_sign_in/save_aliases/run; effective_snapshot through cache; 5 view init sites switched; league:279/296/627/665 stay uncached. 5 new tests. Reviewer PASS.

## R4 (committed) — 006
- Suggestion +market +fit_z (renamed from fit_norm); fit_z = RAW weighted fit (documented), None only hi==lo; market None unranked; reason strings byte-identical (rare ~100/3000 1% mkt shift spec-accepted). board _mkfit reads fields; _MKT_RE/_FIT_RE + re import deleted. _gap_names top_rank hoisted O(n²)→O(n) + dup-worst-rank test.

## R3 (committed+bookkept) — all 5
- shared ui/views/_roster.py + _common.py (CAT_LABELS + _fmt_gap); naming._suggest pool_norm_all drop; league.py docstring merge + __all__ bottom. 4 roster copies had NO behavioral diff.

## ⚠ LESSONS (this session)
- codemode tools.read truncates at 50KB — board.py (56KB) truncated-READ + write-back CORRUPTED it → git checkout restored, re-applied via edit tool. RULE: files >50KB NEVER read+rewrite in codemode.
- codemode: `await` in named `function` body fails (wrapper async, inner isn't) → arrow functions. codemode tool args are OBJECTS (tools.read({path})).

## Rules in force
- subagent chains one phase per chain; phase_complete ONLY commits; per-file pytest (NEVER tests/ui dir or tests full — exit 127; tests/domain+io+services DIRS OK); `.venv/Scripts/python -m pytest`; ruff clean; rebuild exe after code changes; doc protocol: after phase_complete → dev.md mark + done.md append under tool's EXACT header + status.md section (lands in NEXT commit).

## Verification
- Committed green through R5b: R1(domain 168) R2(io 95+1sk, services 15, league_view 16) R3(12 ui, domain 168) R4(61, domain 169) R5a(services 20, io 95+1sk, 7 ui 84) R5b(domain 169, ui per-file 65). ruff clean throughout.
- Exe: rebuilt after R1b,R2,R3,R4,R5a,R5b. NOT yet rebuilt for R6.
- Tree: clean except .pi/state/state.md + uncommitted R6 edits above.

## Findings (told?)
- R2 scout: yahoo_oauth NOT installed (in-app oauth.py, OAuthError(RuntimeError)); yfpy HTTPError-w-response / bare(999) / YahooFantasySportsDataNotFound; yfpy auto-refreshes 401. Told: no (final report).
- League ok-banner warnings = out-of-plan R2 addition, bookkept 003 R2. Told: no.
- Live league still 403 app-authorization wall → R2 live check (AGENTS.md step 5) may only do sign-in + offline fallback; user hasn't run it — request in final report. Told: yes.
- .pi/state/state.md tracked; R6 gitignores only .pi/reports/. Told: no.
- SPEC §1.1 13-vs-14 rounds — owner decision pending (003 status/done). Told: yes.
- R3: 4 roster copies NO behavioral differences. Told: no (final report).
- R4: fit_norm→fit_z rename; mkt rare 1% shift spec-accepted. Told: no (final report).
- R5b reviewer: tests/ui/test_draft.py does NOT exist (it's test_draft_view.py). Told: no.
- Ownership: matchup.py=004; picks/keepers/board.py=006; domain/league.py+views/league.py=003; waivers/trades/lineups/waiver.py/trade.py=005; naming/players/importer=001; io/yahoo+sync=002; main/README/hygiene=scaffold.
- phase_complete tool headers dated 2026-10-11 (clock) — keep verbatim.
- ball_buddy/engine/ does NOT exist — engine module is ball_buddy/domain/engine.py (project_roster, PlayerProjection.name exists).

## FINAL REPORT contents (to write after R6 commits)
- All phases R1→R6 + exe rebuilt after each; SPEC 13-vs-14 decision request; .pi tracking note; R2 live-check request (403 wall caveat); R2 scout findings; R3 no-difference confirmation; R4 fit_z deviation + mkt shift; R6.5 verified-absent; R2.2 doc-only outcome.

## Dead ends
- `pytest tests/ui` / `pytest tests` dir — exit 127. Per-file/per-domain only.
- load_last() ok=False — ok-banner tests build SyncResult(ok=True) directly.
- codemode read+write on files >50KB = corruption.
- ROADMAP is at agents/ROADMAP.md, not repo root.

## Goal (latest user request, verbatim)
.pi/state/state.md is stale. Rewrite it in place now (one line per fact, changes as changes, told yes/no). Then continue the task.

## Last assistant message (truncated)
All R6 code edits applied; git rm'd 6 junk files + added .pi/reports/ to .gitignore.
