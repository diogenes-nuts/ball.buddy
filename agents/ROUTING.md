# Component index

One line per component: NNN_name — what it does (one sentence).

- Build order: agents/ROADMAP.md (M0–M7, ported from agents/SPEC.md §7; M2 draft board is first feature)

- scaffold — repo shell: pyproject + pinned deps, PySide6 main window (tactile-cream-ui theme, nav + Draft placeholder), pytest/ruff/PyInstaller wired up
- 001_data — player pool (Hashtag import-v4 salvage) + name bridging with loud unmatched report
- 002_yahoo — yfpy adapter (OAuth, sync league/teams/draft-order/schedule), atomic JSON snapshot, offline fallback
- 003_league — local league model: teams, draft order, schedule, manual team order
- 006_board — draft board: keeper entry (M2.1) + live draft board (M2.2)
