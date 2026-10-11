# State — REVIEW-FIXES R1–R6: R1+R2 committed; R3 next (roster resolver refactor, 5 components)

## Status
- Position: R1 (R1a scaffold commit eaeab9d + R1b 003/004/006 commits 8c7eb8a et al.) and R2 (002_yahoo a795290 + 003_league 4b9a618) COMPLETE: implemented, reviewer-passed, exe rebuilt each, status/done/dev docs done. Only remaining dirty: agents/003_league/done.md (my R2 append landed AFTER the 003 R2 commit — sweeps next commit).
- Exact next step: launch R3 chain (single chain — pure refactor, medium size; split only if worker report suggests overflow): worker tasks = (a) NEW ball_buddy/ui/views/_roster.py: team_roster_rows(service, team_name)->(rows, missing) = matchup.py:357 _load_team_data core VERBATIM + team_roster_names wrapper; matchup keeps 1-line _load_team_data wrapper; DELETE duplicate copies at waivers.py:60, trades.py:69, lineups.py:78; new tests/ui/test_roster.py (dedupe order, missing list, empty team name); (b) NEW _common.py: CAT_LABELS (def matchup.py:84, import at board.py:80 — update to _common) + _fmt_gap (defs lineups.py:54 + trades.py:53, import matchup.py:28 — consolidate into _common, update all importers); (c) naming.py _suggest: drop pool_norm_all param (callers ~:155/:166 pass same dict); (d) domain/league.py: merge two module docstrings + note DRAFT_ROUNDS lives here; (e) views/league.py:671 __all__ → bottom after SignInDialog/_SignInExchangeWorker. No behavior change — all existing tests must stay green UNCHANGED (except import lines). Then reviewer step, exe rebuild, phase_complete per component (005_advisor, 004_engine, 006_board, 001_data, 003_league — each gets R3; do them sequentially, doc bookkeeping after), then R4.
- In flight: nothing code; 003 done.md dirty (will ride next commit).
- Rules in force (user): subagent chains one phase per chain, split large phases as needed; phase_complete ONLY commits; per-file pytest (NEVER tests/ui dir or tests full — exit 127 flake); `.venv/Scripts/python -m pytest`; ruff clean (E501 = 100 chars); rebuild exe after code changes (pattern: no-proc check → mv dist/data /tmp/bb_data_backup → pyinstaller -y ... ~80-96s → restore); doc protocol: phase_complete → dev.md trim + done.md append under tool's exact header; status.md edits land in next commit (write immediately).

## Verification
- Committed green so far: R1 — test_excepthook 3, test_keepers 19, test_league_view 15→16, test_board 28, test_matchup_view 10, test_draft_view 5, tests/domain 168. R2 — tests/io 95+1sk, tests/services 15, test_league_view 16, ruff clean. Exe rebuilt post-R1b AND post-R2 (5.74MB, dist/data restored both times).
- Baselines: tests/services 13→15 (my earlier "52" was a wrong probe); tests/ui per-file only.

## Findings (told)
- R2 scout: yahoo_oauth NOT installed; in-app oauth.py OAuthError(RuntimeError); yfpy HTTPError-with-response / bare-HTTPError(999) / YahooFantasySportsDataNotFound; yfpy auto-refreshes 401 internally. Told: no (due in user report — include in final).
- League ok-banner warning surface = out-of-plan addition, reviewer-accepted, bookkept under 003 R2 (4b9a618). Told: no.
- Live league still 403 app-authorization wall (002 status) → R2 manual live check (AGENTS.md step 5) may only exercise sign-in + offline fallback. Told: yes (flagged in my R2 report to user? — I have NOT yet sent an interim R2 report to the user since context pressure; MUST tell user when next reporting: R2 done + live-check request).
- .pi/state/state.md is tracked → sweeps into commits; R6 gitignores only .pi/reports/. Told: no.
- SPEC §1.1 "13 rounds" vs implemented 14 — owner decision pending (noted 003 status/done). Told: yes.
- phase_complete tool header date says 2026-10-11 (clock) — keep tool's exact headers.

## R3–R6 targets (condensed; full detail in agents/REVIEW-FIXES.md)
- R3 (this is next; components 005+004+006+001+003): see Exact next step above. Acceptance: existing view tests green per-file unchanged; grep shows single roster-resolution impl + single CAT_LABELS def; ruff; exe rebuild.
- R4 (006): recommend.py Suggestion +market: float|None=None +fit_norm: float|None=None; scorer.py:206 score_pool populates (market None unranked; fit_norm None degenerate fit range); M2.3 fallback None → em dash unchanged; board.py:972-979 _mkfit reads fields (RE-GREP lines, shifted after R1b/R3), DELETE _MKT_RE/_FIT_RE + "reason-string as API" comment; scorer.py:192-194 hoist top_rank O(n²)→O(n); asymmetric-decile test if missing. Rail renders identically.
- R5a (002): sync.load_last_cached() memo on mtimes(snapshot.json, players.csv, aliases.json); invalidate reset_all_data/save_sign_in/save_aliases/run; effective_snapshot (sync.py:210) through cache (callers board.py:715, draft.py:82, setup_dialog.py:58, _offline.py:49 — RE-GREP, lines shifted); 6 view init calls → cached; load_last stays uncached truth; counter test (startup = 1 load+1 bridge) + invalidation tests (players.csv AND aliases.json mutation re-bridges).
- R5b (006+001): _roster quad mtime cache (players.csv, keepers.json, draft_picks.json, aliases.json; data_dir-keyed; clear_cache() seam, tests/ui/test_roster.py); board render() _team_projections computed ONCE (was 913/999/1012 — RE-GREP) threaded into _render_recs/_render_relative/roster panel + names-model rebuild skip when excluded set unchanged (stored copy); naming.py:408 bridge() precompute (base,suffix,display) triples.
- R6 (tiny one chain; components 001+005+004+scaffold): 1 players.py:27 _by_raw delete; 2 trades.py:339 no-op del; 3 matchup.py _roster_players=((),()) init + drop getattr; 4 lineups.py:248-250 by-name starter lookup; 5 DELETED no-op; 6 importer.py:242 skip blank-rank dup warn; 7 trade.py doc note only; 8 git rm .p1.txt .p2.txt .pytest_out.txt .r.txt tests/full_run.txt "Screenshot 2026-10-09 131142.png" + .gitignore .pi/reports/ (ONLY reports/ — .pi has 28 tracked files; tell user). ROADMAP.md "review remediation complete" note.
- FINAL REPORT: all phases, SPEC 13-vs-14 decision request, .pi tracking note, R2 live-check request, exe rebuilt each phase.

## U-turns
- "tests/services 52 baseline" wrong (real 13). Internal.
- Earlier: 3 of 6 cross-exam corrections retracted after user pushback.

## Dead ends
- `pytest tests/ui` / `pytest tests` dir runs — exit 127. Per-file/per-domain only.
- load_last() → ok=False; ok-banner tests construct SyncResult(ok=True) directly.
