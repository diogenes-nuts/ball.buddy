# State — ball.buddy: M1–M5.1 done; M5.2 full implementation in flight
(Rewrite this whole file at every checkpoint. Never append. If a fact
no longer matters, delete it — git history keeps the trail.)

"Told" = user has heard this from you in plain words. Reading it in a log
does not count.

## Status
- Position: M0, M1, M2 (3 slices), M3 (2 slices), M4 (2 slices), M5.1 all COMMITTED via phase_complete. Next: **M5.2 Lineups page — FULL implementation (user decided after scope discussion: full, not thin)**: day/week picker, per-player playing toggles, Optimize button, recommended lineup table (slot, player, contribution) vs sits, category outlook vs opponent, rationale lines, optional MC p_win display, "start these" display only (no Yahoo writes — v1 read-only). Chain: planner→worker→reviewer→worker.
- Exact next step: launch M5.2 chain; on completion phase_complete(005_advisor, M5.2), docs (005_advisor status/dev/done — M5.1 entries ALREADY in done.md; dev.md has only M5.2 + M6 stubs), then M6 trades (sliced), M7 packaging.
- In flight: nothing half-done (M5.1 committed clean). 005_advisor status.md says "M5.2 scope review pending" — update it when M5.2 starts/finishes.
- Rules in force (user's own words): draft tracker top priority; tactile-cream-ui for ALL UI decisions; slice large phases (subagent ctx); implement all remaining phases sequentially without pausing; if a subagent aborts, inspect then resume; M5.2 = full implementation (not the thin variant).

## Verification
- Baseline (M5.1 commit): pytest 202 passed + 1 skipped, ruff clean, exe at dist/ball.buddy/ball.buddy.exe (rebuilt at M4.2; rebuild only if UI/packaging files change).
- Offscreen smoke pattern: _smoke.py file (QApplication([]) FIRST — constructing MainWindow without it hard-crashes rc=127 with lost output), QT_QPA_PLATFORM=offscreen, temp data dir, delete after. Domain smokes: plain python scripts, no Qt.
- Failing / not-yet: live Yahoo login still user-performed (AGENTS.md "M1 live check": step 1 = League → Settings dialog). Real-week matchup hand-check pending (no synced data). Open league items: 4-4 tie-break (user→comm; h2h mode works via snapshot standings, yahoo_default pushes without per-team cat-win evidence — documented), trade deadline + tx cutoff. data_tmp_check/ junk dir: deletion blocked by safety gate, gitignored, user can delete manually (told yes).
- Now passing: all 202 tests.

## Findings
- Yahoo wrapper reality: yffapi/pyffl do NOT exist on PyPI (SPEC §3/§10 wrong — SPEC correction still pending, do when convenient); real = **yfpy 17.0.0** (3-legged OAuth opens browser; deferred import; LoginRequiredError). told yes.
- M5.1 engine facts (committed): pool has ONE position column `pos` (slash-joined, tokens ⊆ {PG,SG,SF,PF,C}, no F/G/UTL tokens); slot map: G<-PG|SG, F<-SF|PF, UTL = >=2 tokens, unknown pos excluded+note. engine.project_roster is POSITION-AGNOSTIC (set-only) -> optimizer = exhaustive C(14,10)=1001 sets + backtracking slot fill, ~40ms. mc_trials reports p_win without changing choice. told yes.
- M5.1 bug caught by finish-worker: _assign returned list(set) hash order -> non-deterministic slot labels; fixed to slot-order recording. told yes.
- M5.1 test hand-check: plan's 7-1 target wrong, computed optimum 8-1 (FT% pool needs Zeta AND Yankee: ~0.4915>0.45; each alone ~0.4471). Documented in test docstring. told yes.
- M5.1 known documented gap: if best SET is unslot-able, optimize() raises instead of falling back to next-best set. told yes.
- Subagent chain failures seen: (a) M1 worker aborted mid-run ~90% of work survived -> inspect+fix-chain recovered; (b) M5.1 chain TWICE returned no output at planner->worker handoff (planner report survived in .pi/reports/subagent-planner-*.md) -> recovered by running worker as SINGLE subagent with plan embedded. Pattern: on chain no-output, check .pi/reports/ for the last planner report and drive remaining steps singly. told yes (recovery), told no (internal mechanics).
- User feedback on M5: subagents burned tokens on hypothetical-lineup verification theater; user expected worker to fail, it didn't; decision = proceed FULL M5.2 anyway. told yes.
- M0–M4 verified highlights: M2.2 even-round keeper forfeit bug (fixed, _order_of snake order); M3.2 h2h tie-break never got standings evidence (fixed, _standings()); M4.2 settings-key typo waiber->waiver_faab_budget. All reviewer-caught. told yes.
- M0 stack: Python 3.14.7, PySide6 6.11.2, pytest 9.1.1, ruff 0.16.10, pyinstaller 6.22.3, yfpy 17.0.0; repo-local .venv; pyinstaller needs -y into non-empty dist/. told yes.
- League facts (user-confirmed, pre-draft 2026): roster 14 = 10 active + 3 BN + 1 conditional IR (no IR draft round; injured-while-owned). 24 keepers (cost = prev round + comm penalty; in-app entry + per-keeper opt-out). FAAB $100 ONLY add path; 3 adds/wk, unlimited drops, 3-day hold. Lineups daily, per-player game-start deadline. Playoffs top 4, 2 byes, single elim, end 2-3 wks before NBA season. Pure 9-cat unweighted. told yes.
- Phase order + status: M0 scaffold ✓, M1 yahoo/league/data ✓, M2 draft board ✓ (first feature, complete), M3 engine+matchup ✓, M4 waivers ✓, M5 lineups (5.1 ✓, 5.2 in flight), M6 trades, M7 packaging. told yes.

## U-turns
- M5.2 scope: user initially asked to narrow (I recommended thin); after M5.1 succeeded user chose FULL implementation. told yes.
- Slicing: big single chains -> per-slice chains (user directive after M1 abort). told yes.
- SPEC Yahoo lib: yffapi/pyffl -> yfpy 17.0.0. told yes.

## Dead ends
- edit() non-ASCII in oldText (≥ § – —): round-trip failures; ASCII-only anchors or fresh-read copies; don't mix cross-file edits in one call. told no (internal).
- pyinstaller into non-empty dist/ needs -y. told no (internal, minor).
- MainWindow() without QApplication([]) first: hard crash rc=127, output lost. told no (internal).
