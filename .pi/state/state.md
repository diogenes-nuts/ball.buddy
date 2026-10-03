# State — ball.buddy: M2 draft board (sliced), M3–M7 to follow
(Rewrite this whole file at every checkpoint. Never append. If a fact
no longer matters, delete it — git history keeps the trail.)

"Told" = user has heard this from you in plain words. Reading it in a log
does not count.

## Status
- Position: M1 committed (002_yahoo M0-style phase commit "002_yahoo M1"). Next: M2 draft board, SLICED (user directive): 2.1 keeper entry + data model, 2.2 snake board view (keeper-aware forfeited picks + pick entry), 2.3 pool value recommender. One subagent chain per slice (planner→worker→reviewer→worker; small slices may drop one worker). Then M3, M4, M5, M6, M7 — all sliced if large. Docs for 001/002/003 written (land in next commit); ROUTING updated.
- Exact next step: launch M2.1 chain (keeper entry: bulk entry of 24 keepers with team + cost round, per-keeper opt-out, persistence to data/ dir, UI in Draft view per tactile-cream-ui; planner→worker→reviewer→worker).
- In flight: none. M1 verify baseline: 104 passed/1 skipped, ruff clean, offscreen smoke OK, exe rebuilt post-fix.
- Rules in force (user's own words): draft tracker top priority; tactile-cream-ui for ALL UI; **break large phases into smaller slices to avoid subagent ctx blowups** (new, this turn); implement all remaining phases sequentially without pausing.

## Verification
- Baseline (M1 commit): pytest 104 passed + 1 skipped; ruff clean; offscreen smoke needs QApplication([]) BEFORE MainWindow (else rc=127 crash with lost output — pytest fixture does this for you); exe at dist/ball.buddy/ball.buddy.exe (rebuilt M1).
- Failing / not-yet: live Yahoo login still user-performed (AGENTS.md "M1 live check" steps; step 1 = League → Settings dialog, no hand-written settings.json). Open league items: 4-4 tie-break (user→comm), trade deadline + tx cutoff.
- Now passing and what fixed it: M1 post-review fixes (data/ gitignore, SettingsDialog, manual team-order mapping, AGENTS live-check).

## Findings
- Yahoo wrapper reality: **yffapi/pyffl do not exist on PyPI** (SPEC was wrong); real one is **yfpy 17.0.0** (3-legged OAuth, opens browser; deferred import in client.py; LoginRequiredError when no consumer key). SPEC §3 should be corrected when convenient. told yes.
- data/ (gitignored): settings.json (tokens!), players.csv, aliases.json, snapshot.json — at repo root, not data_tmp junk (leftover data_tmp_check/ gitignored, blocked deletion).
- Subagent abort pattern: M1 worker aborted mid-run at "step 2" (not manual; possibly ctx/timeout) but ~90% of work survived on disk. Recovery = inspect (pytest/ruff/status) then resume with fix-chain. User: if it happens again, inspect then resume. told yes.
- Shell quirk on this box: `timeout`/`which` missing; some python runs return rc=127 with lost stdout (buffering) when the process dies — write smoke to a .py file + QApplication first. told no (internal).
- M0 stack: Python 3.14.7, PySide6 6.11.2, pytest 9.1.1, ruff 0.16.10, pyinstaller 6.22.3; repo-local .venv. told yes.
- League facts (user-confirmed): roster 14 = 10 active + 3 BN + 1 conditional IR (no IR draft round). 24 keepers pre-draft, cost = prev round + comm penalty (in-app entry + opt-out). FAAB $100 ONLY add path; 3 adds/wk, unlimited drops, 3-day hold. Lineups daily, per-player game-start deadline. Playoffs top 4, 2 byes, single elim, end 2-3 wks before NBA season. told yes.
- Phase order: M2 draft board (sliced), M3 matchup, M4 waivers, M5 lineups, M6 trades, M7 packaging. told yes.

## U-turns
- M1 slice strategy: single chain → aborted; recovered via fix-chain. Going forward: slice large phases per user. told yes.
- SPEC Yahoo lib: yffapi/pyffl → yfpy 17.0.0 (verified on PyPI). told yes.

## Dead ends
- edit() non-ASCII in oldText (≥ § – —): round-trip failures; ASCII-only anchors or copy from fresh read. told no (internal).
- pyinstaller into non-empty dist/ needs -y. told no (internal, minor).
- MainWindow() without QApplication([]) first: hard crash rc=127, output lost. told no (internal).
