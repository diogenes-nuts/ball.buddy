# State — ball.buddy: M1–M3 done, M4 waivers next
(Rewrite this whole file at every checkpoint. Never append. If a fact
no longer matters, delete it — git history keeps the trail.)

"Told" = user has heard this from you in plain words. Reading it in a log
does not count.

## Status
- Position: M1 (yahoo/league/data), M2 (draft board, 3 slices), M3 (engine + matchup view, 2 slices) all committed. Next: M4 waiver advisor (005_advisor) — likely 1-2 slices (domain ΔP(win) logic, then UI). Then M5 lineups, M6 trades, M7 packaging. Slice large phases per user.
- Exact next step: write agents/005_advisor/dev.md (M4 scope), launch M4 chain (planner→worker→reviewer→worker).
- In flight: 004_engine docs updated (status/done, ROUTING) — land in M4 commit.
- Rules in force (user's own words): draft tracker top priority; tactile-cream-ui for ALL UI; slice large phases (subagent ctx); implement all remaining phases sequentially without pausing.

## Verification
- Baseline (M3 commit): pytest 178 passed + 1 skipped, ruff clean, exe at dist/ball.buddy/ball.buddy.exe (rebuilt M3.2). Offscreen smoke pattern: _smoke.py file, QT_QPA_PLATFORM=offscreen, QApplication([]) FIRST, temp data dir.
- Failing / not-yet: live Yahoo login still user-performed (AGENTS.md "M1 live check"; step 1 = League → Settings). Real-week matchup hand-check pending (no synced data in workspace). Open league items: 4-4 tie-break (user→comm; h2h mode works via standings, yahoo_default pushes without per-team cat-win evidence — documented), trade deadline + tx cutoff.
- data_tmp_check/ leftover dir: deletion blocked by safety gate, gitignored, harmless — user can delete manually. told no (will tell at next user-visible report).

## Findings
- Yahoo wrapper reality: yffapi/pyffl don't exist on PyPI (SPEC wrong); real = **yfpy 17.0.0** (3-legged OAuth opens browser; LoginRequiredError path). SPEC §3 correction still pending — do when convenient (told yes of the fact, spec edit pending).
- Engine math (M3.1, hand-verified twice): fixture gaps pts +520 / fg_pct +0.03187 / ft_pct +0.00578, cat wins 7-2, P(A) seed42 = 0.9763 reproducible; % cats volume-weighted; ties count both (deterministic + MC); no numpy, no Qt in domain. told yes.
- M3.2 reviewer-caught blocking bug: h2h tie-break never got standings evidence → always Push; fixed via _standings() from snapshot. told yes.
- M2.2 reviewer-caught critical: even-round keeper forfeits showed "?" (slot vs snake order); fixed via _order_of. told yes.
- Subagent abort pattern: M1 worker aborted mid-run (~90% survived on disk); recovery = inspect (pytest/ruff/status) then resume via fix-chain. User: inspect then resume if it recurs. told yes.
- Reviewer false-positive pattern: M3.1 reviewer flagged 5 "defects", fix worker hand-verified all 5 as non-defects — chains self-correct; don't panic on defect counts. told no (internal).
- M0 stack: Python 3.14.7, PySide6 6.11.2, pytest 9.1.1, ruff 0.16.10, pyinstaller 6.22.3, yfpy 17.0.0; repo-local .venv. told yes.
- League facts (user-confirmed): roster 14 = 10 active + 3 BN + 1 conditional IR (no IR draft round). 24 keepers pre-draft (cost = prev round + comm penalty; in-app entry + opt-out). FAAB $100 ONLY add path; 3 adds/wk, unlimited drops, 3-day hold. Lineups daily, per-player game-start deadline. Playoffs top 4, 2 byes, single elim, end 2-3 wks before NBA season. told yes.
- Phase order: M1 ✓, M2 ✓ (draft board complete), M3 ✓, M4 waivers, M5 lineups, M6 trades, M7 packaging. told yes.

## U-turns
- Slicing: single big chains → per-slice chains (user directive after M1 abort). told yes.
- SPEC Yahoo lib: yffapi/pyffl → yfpy 17.0.0. told yes.

## Dead ends
- edit() non-ASCII in oldText (≥ § – —): round-trip failures; ASCII-only anchors or fresh-read copies. told no (internal).
- pyinstaller into non-empty dist/ needs -y. told no (internal, minor).
- MainWindow() without QApplication([]) first: hard crash rc=127, output lost. told no (internal).
