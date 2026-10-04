# Component index

One line per component: NNN_name — what it does (one sentence).

- Build order: agents/ROADMAP.md (M0–M7, ported from agents/SPEC.md §7; M2 draft board is first feature)

- scaffold — repo shell: pyproject + pinned deps, PySide6 main window (tactile-cream-ui theme, 6 real views), pytest/ruff/PyInstaller wired up; app icon (assets/icon.ico via scripts/make_icon.py) + frozen-aware data dir (pathing.py) + reset-all-data + app.log error UX + README (M7 complete — ROADMAP done)
- 001_data — player pool (Hashtag import-v4 salvage) + name bridging with loud unmatched report
- 002_yahoo — yfpy adapter (OAuth, sync league/teams/draft-order/schedule), atomic JSON snapshot, offline fallback
- 003_league — local league model: teams, draft order, schedule, manual team order
- 006_board — draft-day board (M2 complete): keeper entry + snake board + pool value recommender
- 004_engine — 9-cat projection engine (gap mode + seeded MC win-prob, configurable tie-break) + Matchup view (M3 complete)
- 005_advisor — waiver ranking (FAAB-aware delta-P) + lineup optimizer (start/sit) + trade analyzer (delta-P per side, fairness flag), each with its view (M4+M5+M6 complete); M7 packaging next
