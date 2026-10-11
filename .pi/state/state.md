# State — REVIEW-FIXES.md cross-examination (deep re-audit done; 2 of 6 proposed corrections stand)

## Status
- Position: Presented assessment (turn 1); user demanded deeper verification of each proposed correction; deep re-audit complete; corrected accounting about to be delivered.
- Exact next step: Deliver the retracted/refined assessment; user then decides which doc edits to apply. No code changes yet.
- In flight: none (read-only audit).
- Rules in force (user's own words): "dig deeply into each proposed correction... there may be context you missed. I want more reasoning before I am willing to apply your corrections."

## Verification
- Baseline: audit-only; no tests run, no commit touched.
- Method: 4 rounds of batched codemode reads/greps incl. git history (log -p, -S), yfpy site-packages source, data/ files.

## Findings (current; told yes/no = delivered to user yet)
- DEEP AUDIT REVERSED 3 of my 6 proposed corrections (turn-1 audit misread pruned outputs; told no — delivering now):
  - R1.1 RETRACTED: current main.py:56 DOES call `default_hook(...)` at end of hook (log → dialog → re-raise; M7.2 commit 67edb6c message says "re-raise always survives"). Doc's test spec ("assert hook re-raises via default_hook") matches current behavior; item is fine as written. My "self-contradictory" call was a misread.
  - R1.4 RETRACTED: snapshot doc carries NO rounds key (to_snapshot keys verified); board uses `picks_mod.build_snake` (board.py:744) not LeagueConfig; League view builds throwaway LeagueConfig with view-local DRAFT_ROUNDS=14 (views/league.py:499). Exactly the two sources the doc unifies — doc is complete, no extra check needed.
  - R6.8 RETRACTED: ALL five junk files (4 dotfiles + tests/full_run.txt) are git-TRACKED (wc -l 5), screenshot tracked too; .pi/ is tracked with 28 files (18 subagent reports + 9 eras + state.md) so "gitignore .pi/reports/" is meaningful, not preemptive. Doc is right on both counts.
- R2.2 CORRECTION DOWNGRADED (kill → clarify): doc's own decision rule "pick the minimum-call shape" guards against implementing the worse option; per-team full-season is 1 HTTP query/team (yfpy query.py:2685-2689) = 12 < ~17-20 per-week. BUT the per-week fallback branch is functionally LOSSY: doc's own bound "weeks 1..playoff-start" would drop playoff schedule rows (per-team calls include is_playoffs matchups). Also "cut per-sync API calls" goal is a mislabel if outcome = no change. Recommend: edit item (mark per-week branch inferior/lossy, reframe goal as "verify + document shape"), not delete.
- R5.1 CORRECTION STANDS, now with exact lines: bridge_names (sync.py:250) bridges on snapshot+pool+`self.load_aliases()` (3 inputs); save_aliases exists at sync.py:78-82 but is NOT in doc's invalidation list (reset/save_sign_in/run) → aliases.json must join the mtime key. STRONGER: effective_snapshot (sync.py:210) calls UNCACHED load_last internally and is the board's rebuild path (board.py:715) + draft.py:82 + setup_dialog.py:58 + _offline.py:49 — switching only the 5-6 view init calls to load_last_cached leaves board/draft paying full cost; acceptance test would pass while the win is half-missed. told no
- R6.5 CORRECTION STANDS: setup_dialog._save (318-357) writes only manual_teams/manual_draft_order/my_team + keepers file; zero `settings["version"]` writes in current tree (grep all "version" hits listed; none in setup_dialog). Doc describes a foot-gun that doesn't exist (git -S hit was M1-era league.py before the dialog split). Delete the item. told no
- Round-1 verified-clean items (unchanged): R1.2/1.3/1.5/1.6 bugs all real at cited lines; R2.1 classifier (client.py:162), R2.3 (_extracted_data snapshot.py:143), R2.4 (OAuthError escape, client.py:113-119 catches only YahooError/RequestException; tokens-not-overwritten claim TRUE — save after _live_tokens in run()), R2.5 (persist_token silent no-op) all confirmed; R3 four roster copies + CAT_LABELS (matchup.py:84 def, board.py:80 import); R4 regex-parsed reasons (board.py:972-979) + O(n²) top_rank (scorer.py); R5.3 (_team_projections at 913/999/1012); R5.4 (naming.py:408 per-name re-split); R6.1 _by_raw players.py:27; R6.2 trades.py:339 no-op del; R6.3 getattr fallback; R6.4 positional starter_proj.players[i]; R6.6 importer.py:242 blank-rank warn.

## U-turns
- My 6 corrections → 2 stand + 1 partial: round-1 pruned codemode outputs were misread on 3 items (R1.1 hook tail, R1.4 board rounds path, R6.8 tracked-file counts). Lesson: never assert absence (e.g. "no re-raise", "untracked") from pruned output — re-grep explicitly. told no

## Dead ends
- (none; R2.2 per-week loop still a plan-level no: more calls AND drops playoff rows)
