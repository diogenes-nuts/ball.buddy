# ROADMAP

Top-level plan for ball.buddy, ported from `agents/SPEC.md` §7 (the spec remains the source of truth for design; this file is the build order). Phases are user-facing milestones; each may contain multiple per-component plan phases (those live in `agents/<NNN>/dev.md`). Component docs are created when a component's first plan is written.

**Priority (user-stated, pre-draft 2026):** M2 (draft board) is the first feature — this year's draft happens before the season. M3–M5 = the weekly-season app. M6–M7 secondary.

| Phase | Components | Deliverable | Exit criteria |
|---|---|---|---|
| **M0** | (repo) | Scaffold: repo per doc-structure, `pyproject.toml`, PySide6 skeleton (main window + nav), PyInstaller onedir build producing a runnable exe, pytest/ruff green on the shell | exe runs; local verify commands documented in AGENTS.md |
| **M1** | 002_yahoo, 003_league, 001_data | OAuth login, sync league/teams/draft order/schedule, JSON snapshot persisted; pool import in-app (Hashtag salvage) | login→sync works against the real league; pool loaded with matched names; stale/offline fallback shows last snapshot |
| **M2** | 006_board | **Draft mode (first feature)**: snake draft board with keeper-aware forfeited picks, bulk keeper entry (24 keepers, per-keeper opt-out), pick-by-pick live tracking, pool-based value recommender (salvaged `003_board` + ValueGapScorer) | board correctly shows the 12-team snake with all forfeited keeper picks; keeper entry round-trips; recommender rankings sane on the real pool |
| **M3** | 004_engine | Matchup view (headline P(win), 9-cat gap bars, player marginal table) | the matchup screen is correct by hand-check on one real week |
| **M4** | 005_advisor | Waiver ranking (SPEC §6.1), incl. FAAB-aware ΔP(win) per candidate | ranked list with ΔP(win) per candidate |
| **M5** | 005_advisor | Lineup optimizer (SPEC §6.2), per-day, 10 actives + IR-aware | daily recommendations + explanations |
| **M6** | 005_advisor | Trade analyzer (SPEC §6.3): what-if ΔP(win) per side, before/after category gaps, fairness flag | — |
| **M7** | (packaging) | Installer-grade exe folder, icon, settings reset, error UX | hand to a friend; it works |

## Component map (SPEC §4)

- `001_data` — player pool import (Hashtag import-v4 salvage), name bridging, player cache.
- `002_yahoo` — Yahoo adapter (yffapi/pyffl behind one facade), OAuth, sync, offline snapshot.
- `003_league` — local league model: teams, rosters, schedule, standings, waiver wire.
- `004_engine` — projections + Monte-Carlo win-prob; deterministic gap mode; configurable matchup tie-break.
- `005_advisor` — waiver, lineup, trade logic (consumes 004_engine).
- `006_board` — draft-day board (first feature, M2).

## Done — review remediation (2026-10-14 → 2026-10-15)

Full-repo code review produced a six-phase remediation plan: **agents/REVIEW-FIXES.md** (R1 correctness bugs → R2 Yahoo error handling → R3 shared resolver refactor → R4 structured Suggestion fields → R5 caching/perf → R6 dead code + hygiene). **All six phases are implemented, reviewed, and committed** (per-component notes in each `agents/<NNN>/done.md`; the exe was rebuilt after every code-changing phase). One residual owner decision: SPEC §1.1 reads "13 rounds + conditional 14th IR slot" while the implementation standardizes on `DRAFT_ROUNDS = 14` (unified in R1b) — reconciliation is the owner's call (see 003_league done.md).

## Open items (SPEC §1.1)

- **Rounds: 13 vs 14** — SPEC §1.1 says "13 rounds + conditional 14th IR slot"; the code uses `DRAFT_ROUNDS = 14`. Owner to confirm which is authoritative and reconcile the SPEC.
- Matchup-level 4-4 tie-break rule — user to confirm with commissioner; 004_engine must be configurable (default: Yahoo).
- Trade deadline date + transaction cutoff time — read from Yahoo league settings at M1 sync, manual-entry fallback.
