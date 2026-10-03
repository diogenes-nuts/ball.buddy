# scaffold — status

Repo scaffold for ball.buddy: Python package `ball_buddy` with a PySide6 desktop shell, tactile-cream-ui theme, and a runnable PyInstaller onedir build. No feature logic yet (components 001–006 not started).

## Files

- `pyproject.toml` — pins: PySide6 6.11.2, pytest 9.1.1, ruff 0.16.10, pyinstaller 6.22.3 (newest Py-3.14-resolvable; see AGENTS.md).
- `ball_buddy/main.py` — entry point (`python -m ball_buddy.main`).
- `ball_buddy/ui/shell.py` — `MainWindow`: left nav sidebar (League, Matchup, Waivers, Lineups, Trades, Draft) + QStackedWidget; Draft view checked by default.
- `ball_buddy/ui/theme.py` — tactile-cream-ui light theme as QSS: warm cream palette, 2px hard outlines, monospace type, dense layout. Qt QSS limitations (no box-shadow/true gradients) approximated with flat fills + 1px light top borders; documented inline. Dark theme not implemented (M7 candidate).
- `ball_buddy/ui/` views — placeholder views per nav item; Draft is a styled placeholder (M2 replaces with the real board).
- `tests/` — 5 tests: package imports, offscreen app construction (QT_QPA_PLATFORM=offscreen), widget-order/nav-state assertions.
- `ball.buddy.spec` + PyInstaller onedir build → `dist/ball.buddy/ball.buddy.exe` (rebuild commands in AGENTS.md; `build/`, `dist/` gitignored).
- `info.md` — AutoDraft domain brief (salvage context source for 001_data / 006_board).

## Not yet

- No services/domain/io layers populated (M1+ per agents/ROADMAP.md).
- Dark theme, box-shadow fidelity, full font stack — deferred nits from M0 review (M7 polish).

Plans: dev.md (none yet).
