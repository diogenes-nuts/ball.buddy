# State — ball.buddy: M1–M6 complete; M7 packaging is next
(Rewrite this whole file at every checkpoint. Never append. If a fact
no longer matters, delete it — git history keeps the trail.)

"Told" = user has heard this from you in plain words. Reading it in a log
does not count.

## Status
- Position: M0–M6 ALL COMMITTED via phase_complete (M6.1 trade domain, M6.2 trade view). Next: **M7 packaging** (ROADMAP: "installer-grade exe folder, icon, settings reset, error UX" / exit: "hand to a friend; it works") — sliced at its turn.
- Exact next step: slice M7 (planner→worker→reviewer per slice); candidates: icon + pyinstaller icon arg, settings reset (clear data/), global error UX, final rebuild + smoke. Then done — all of ROADMAP.
- In flight: uncommitted doc edits only (ROUTING.md, 005_advisor dev.md M6.2 removal) — land with M7's first commit.
- Rules in force (user's own words): draft tracker top priority; tactile-cream-ui for ALL UI decisions; slice large phases (subagent ctx); implement all remaining phases sequentially without pausing; if a subagent aborts, inspect then resume.

## Verification
- Baseline (M6.2 commit): pytest 225 passed + 1 skipped, ruff clean, exe at dist/ball.buddy/ball.buddy.exe (rebuilt at M6.2).
- Offscreen smoke pattern: _smoke.py file (QApplication([]) FIRST — constructing MainWindow without it hard-crashes rc=127 with lost output), QT_QPA_PLATFORM=offscreen, temp data dir, delete after.
- Failing / not-yet: live Yahoo login still user-performed (AGENTS.md "M1 live check": League → Settings dialog). Real-week matchup hand-check pending (no synced data). Open league items: 4-4 tie-break (user→comm; h2h mode works via snapshot standings, yahoo_default pushes without per-team cat-win evidence — documented), trade deadline + tx cutoff. data_tmp_check/ junk dir: deletion blocked by safety gate, gitignored, user can delete manually (told yes).
- Now passing: all 225 tests.

## Findings
- Yahoo wrapper reality: yffapi/pyffl do NOT exist on PyPI (SPEC §3/§10 wrong — SPEC correction still pending, do when convenient); real = **yfpy 17.0.0** (3-legged OAuth opens browser; deferred import; LoginRequiredError). told yes.
- M5.1 engine facts (committed): pool has ONE position column `pos` (slash-joined, tokens ⊆ {PG,SG,SF,PF,C}); slot map: G<-PG|SG, F<-SF|PF, UTL = >=2 tokens. engine.project_roster POSITION-AGNOSTIC -> optimizer = C(14,10)=1001 sets + backtracking slot fill, ~40ms. mc_trials reports p_win without changing choice. told yes.
- M6 trade facts (committed): their_delta_p == -my_delta_p exactly (1-p construction) so fairness_flag (my delta < -0.10) is the only quality signal; pushes treated as losses for both — documented. View: no week picker (season projections); give entry = combo lists over resolved roster names (gives must be on roster). shell.py: PlaceholderView fall-through → AssertionError, placeholders.py DELETED (all 6 NAV_ITEMS have real views). told yes.
- M6.2 bug caught by reviewer: _rebuild_give_grid deleteLater()'d kept live widgets → RuntimeError "wrapped C++ object deleted" on 2nd Add after event loop; fixed with live-set guard + regression test (processEvents alone does NOT flush deferred deletes — needed sendPostedEvents(widget, DeferredDelete)). told yes.
- Subagent chain failures seen: (a) M1 worker aborted mid-run ~90% survived -> inspect+fix-chain recovered; (b) M5.1 chain TWICE returned no output at planner->worker handoff (planner report survived in .pi/reports/) -> recovered by running worker as SINGLE subagent with plan embedded. Pattern holds — all M6 subagent calls ran singly, worked. told yes (recovery), told no (internal mechanics).
- M0 stack: Python 3.14.7, PySide6 6.11.2, pytest 9.1.1, ruff 0.16.10, pyinstaller 6.22.3 (.venv/Scripts/pyinstaller.exe exists; `python -m pyinstaller` does NOT work), yfpy 17.0.0; repo-local .venv; pyinstaller needs -y into non-empty dist/. told yes.
- League facts (user-confirmed, pre-draft 2026): roster 14 = 10 active + 3 BN + 1 conditional IR. 24 keepers (cost = prev round + comm penalty; in-app entry + per-keeper opt-out). FAAB $100 ONLY add path; 3 adds/wk, unlimited drops, 3-day hold. Lineups daily. Playoffs top 4, 2 byes, single elim, end 2-3 wks before NBA season. Pure 9-cat unweighted. told yes.
- Phase order + status: M0 scaffold ✓, M1 yahoo/league/data ✓, M2 draft board ✓ (first feature, complete), M3 engine+matchup ✓, M4 waivers ✓, M5 lineups ✓, M6 trades ✓, M7 packaging NEXT. told yes.

## U-turns
- Slicing: big single chains -> per-slice chains (user directive after M1 abort); later converged to single sequential subagent calls (planner/worker/reviewer each own call) which have all worked. told no (internal).
- SPEC Yahoo lib: yffapi/pyffl -> yfpy 17.0.0. told yes.

## Dead ends
- edit() non-ASCII in oldText (≥ § – —): round-trip failures; ASCII-only anchors or fresh-read copies; don't mix cross-file edits in one call. told no (internal).
- pyinstaller into non-empty dist/ needs -y; `python -m pyinstaller` fails (no module), use .venv/Scripts/pyinstaller.exe. told no (internal, minor).
- MainWindow() without QApplication([]) first: hard crash rc=127, output lost. told no (internal).
