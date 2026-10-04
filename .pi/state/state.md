# State — ball.buddy: ROADMAP COMPLETE (M0–M7 all committed)
(Rewrite this whole file at every checkpoint. Never append. If a fact
no longer matters, delete it — git history keeps the trail.)

"Told" = user has heard this from you in plain words. Reading it in a log
does not count.

## Status
- Position: **ALL ROADMAP PHASES DONE.** M0–M6 committed earlier; M7.1 (icon + frozen data dir) commit 6d09541, M7.2 (reset + error UX + README) commit 67edb6c. In flight: uncommitted doc-only edits (ROUTING.md, agents/scaffold/status.md + done.md M7.2 entry) — no more phases exist to carry them; they land on the next commit or the repo-lifecycle auto-commit on clean exit. Do NOT git commit manually.
- Exact next step: none (project complete). Possible follow-ups only if user asks: user-performed live Yahoo login (AGENTS.md "M1 live check" steps; League → Settings), real-week matchup hand-check (needs synced data), trade deadline + tx cutoff league items, 4-4 tie-break (user → comm).
- Rules in force (user's own words): draft tracker top priority; tactile-cream-ui for ALL UI decisions; slice large phases (subagent ctx); implement all remaining phases sequentially without pausing; if a subagent aborts, inspect then resume.

## Verification
- Final baseline (67edb6c): pytest 234 passed + 1 skipped, ruff clean, exe dist/ball.buddy/ball.buddy.exe (5.46 MB, with icon, rebuilt at M7.2).
- Failing / not-yet: live Yahoo login still user-performed. Real-week matchup hand-check pending (no synced data). Open league items: 4-4 tie-break (user→comm; h2h mode works via snapshot standings, yahoo_default pushes without per-team cat-win evidence — documented), trade deadline + tx cutoff. data_tmp_check/ junk dir: deletion blocked by safety gate, gitignored, user can delete manually (told yes).

## Findings
- Yahoo wrapper: yffapi/pyffl do NOT exist on PyPI; real = **yfpy 17.0.0**. SPEC corrected in agents/SPEC.md (3 mentions) and committed with M7.1. told yes.
- M5.1 engine facts: pool ONE `pos` column (slash-joined, tokens ⊆ {PG,SG,SF,PF,C}); G<-PG|SG, F<-SF|PF, UTL = >=2 tokens; project_roster position-agnostic → optimizer = C(14,10)=1001 sets + backtracking fill, ~40ms; mc_trials doesn't change the choice. told yes.
- M6 trade facts: their_delta_p == -my_delta_p exactly (1-p construction) → fairness_flag (my delta < -0.10) is the only quality signal; pushes treated as losses for both (documented); view has no week picker (season projections); give entry = combo lists over resolved roster names. shell.py: PlaceholderView fall-through → AssertionError, placeholders.py DELETED (all 6 NAV_ITEMS real). told yes.
- M6.2 bug (reviewer-caught): _rebuild_give_grid deleteLater()'d kept live widgets → RuntimeError after 2nd Add once event loop ran; fixed with live-set guard + regression test (processEvents alone does NOT flush deferred deletes — sendPostedEvents(widget, DeferredDelete) needed). told yes.
- M7.1 facts: data dir was Path(__file__).parents[2]/"data" → under frozen onedir that was _internal/data (wrong); now pathing.resolve_data_dir() (frozen → next to exe). Icon = build-time PNG-in-ICO via scripts/make_icon.py (zero new deps, PySide6 painter only), shared draw_app_icon() for window + .ico. told yes.
- M7.2 facts: reset = rmtree(ignore_errors) + return not exists (True = fully wiped); all loaders tolerate wiped dir (empty defaults); post-reset Qt font warning can recreate data/ with only app.log — cosmetic, loader reads as empty (reviewer-accepted, documented). excepthook: log_path inside try so re-raise to default hook always survives; qInstallMessageHandler ≥ Warning → data/app.log (dev console loses Qt warnings to file — known, acceptable). told yes.
- Subagent ops: single sequential subagent calls (planner/worker/reviewer each own call, plan embedded in worker task) have worked every time since the M5.1 chain handoff failures. On no-output, check .pi/reports/ for the last planner report. Rebuild note: a RUNNING ball.buddy.exe locks qoffscreen.dll — kill it before pyinstaller or build fails PermissionError (worker killed a stray instance during M7.2). told no (internal).
- M0 stack: Python 3.14.7, PySide6 6.11.2, pytest 9.1.1, ruff 0.16.10, pyinstaller 6.22.3 (.venv/Scripts/pyinstaller.exe; `python -m pyinstaller` fails), yfpy 17.0.0; -y into non-empty dist/. told yes.
- League facts (user-confirmed, pre-draft 2026): roster 14 = 10 active + 3 BN + 1 cond IR; 24 keepers (cost = prev round + comm penalty; in-app entry + opt-out); FAAB $100 only add path, 3 adds/wk, unlimited drops, 3-day hold; lineups daily; playoffs top 4, 2 byes, single elim; pure 9-cat unweighted. told yes.
- Phase status: M0 scaffold ✓, M1 yahoo/league/data ✓, M2 draft board ✓, M3 engine+matchup ✓, M4 waivers ✓, M5 lineups ✓, M6 trades ✓, M7 packaging ✓ — ROADMAP complete. told yes.

## U-turns
- Slicing: big chains -> per-slice -> single sequential subagent calls (all reliable since). told no (internal).
- SPEC Yahoo lib: yffapi/pyffl -> yfpy 17.0.0 (SPEC corrected+committed). told yes.

## Dead ends
- edit() non-ASCII in oldText: round-trip failures; ASCII-only anchors or fresh-read copies; don't mix cross-file edits in one call. told no (internal).
- pyinstaller: needs -y into non-empty dist/; `python -m pyinstaller` no (use .venv/Scripts/pyinstaller.exe); running exe locks qoffscreen.dll (kill first). told no (internal, minor).
- MainWindow() without QApplication([]) first: hard crash rc=127, output lost. told no (internal).
