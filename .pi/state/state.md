# State — ball.buddy: M1–M7 sequential implementation
(Rewrite this whole file at every checkpoint. Never append. If a fact
no longer matters, delete it — git history keeps the trail.)

"Told" = user has heard this from you in plain words. Reading it in a log
does not count.

## Status
- Position: M1 of M1–M7 in flight (user order: "all remaining phases sequentially, subagent chain per phase: planner→worker→reviewer→worker").
- Exact next step: launch M1 chain (002_yahoo + 003_league + 001_data: OAuth login, sync league/teams/draft order/schedule, JSON snapshot; Hashtag pool import). On PASS: phase_complete, docs, then immediately M2 chain (draft board — user's #1 priority), M3, M4, M5, M6, M7 without pausing.
- In flight: none (M0 committed clean; scaffold docs landed in M0 commit + routing).
- Rules in force (user's own words): draft tracker top priority / first feature; tactile-cream-ui skill for ALL UI decisions; implement all remaining phases sequentially, one chain each.

## Verification
- Baseline (post-M0 commit): pytest 5 passed, ruff clean, offscreen app constructs, PyInstaller exe builds at dist/ball.buddy/ball.buddy.exe.
- Failing / not-yet: M1–M7 not started. Open league items: 4-4 tie-break (user to check w/ comm; engine configurable, default Yahoo), trade deadline + tx cutoff (read from Yahoo at M1).
- Now passing and what fixed it: M0 nits (focus indicator, sidebar order) fixed + exe rebuilt post-fix.

## Findings
- M0 stack on this machine: Python 3.14.7, PySide6 6.11.2, pytest 9.1.1, ruff 0.16.10, pyinstaller 6.22.3; repo-local .venv, no editable install. told yes.
- Qt QSS: no box-shadow/true gradients; approximated (flat fill + 1px top border); dark theme deferred M7. told yes.
- info.md (AutoDraft brief, 353 lines) in repo at ball.buddy/info.md = salvage context for 001_data/006_board. told yes.
- Salvage source: N:/LLM/projects/autodraft (untouched) — import-v4 pool, state.py atomic writes, 003_board, ValueGapScorer.
- League facts (user-confirmed, pre-draft 2026): roster 14 = 10 active + 3 BN + 1 conditional IR (no IR draft round; injured-while-owned only). 24 keepers pre-draft (cost = prev round + comm penalty; in-app entry + per-keeper opt-out). FAAB $100 ONLY add path; 3 adds/wk, unlimited drops, 3-day hold. Lineups daily, per-player game-start deadline. Playoffs top 4, 2 byes, single elim, end 2-3 wks before NBA season. told yes.
- Phase order: M1 yahoo+league+data, M2 draft board (first feature), M3 matchup, M4 waivers, M5 lineups, M6 trades, M7 packaging. told yes.
- Spec: agents/SPEC.md; build order agents/ROADMAP.md; spec §7 = pointer. told yes.
- yffapi is the main Yahoo API (OAuth device flow, no browser window needed for headless-ish use); pyffl as fallback — M1 planner should verify real packages' APIs before designing adapter.

## U-turns
- draft board: M6 → M2 (first feature). told yes.
- Roadmap: SPEC §7 table → single source agents/ROADMAP.md. told yes.

## Dead ends
- edit() non-ASCII in oldText (≥ § – —): round-trip failures; use ASCII-only anchors or copy from fresh read. told no (internal).
- pyinstaller into non-empty dist/ needs -y. told no (internal, minor).
