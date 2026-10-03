# scaffold — done

## 2026-10-03 — M0 — Repo scaffold: pyproject with pinned deps (PySide6 6.11.2 on Python 3.14.7), PySide6 shell (left nav sidebar + tactile-cream-ui theme, Draft placeholder view), 5 passing tests, ruff clean, PyInstaller onedir exe builds and runs, AGENTS.md filled with build/test/run commands.

Deliverables as committed:

- `pyproject.toml` — Python 3.14; pinned PySide6 6.11.2, pytest 9.1.1, ruff 0.16.10, pyinstaller 6.22.3 (conservative pins: newest releases resolvable on Py-3.14 on this machine; risk per SPEC §10 item 4).
- `ball_buddy/` package — `main.py` entry; `ui/shell.py` `MainWindow` (200px left sidebar: League/Matchup/Waivers/Lineups/Trades/Draft; QStackedWidget views; Draft checked by default); `ui/theme.py` tactile-cream-ui light theme (cream palette, 2px hard outlines, monospace, dense; QSS workarounds documented); styled placeholder Draft view + minimal placeholders for the rest.
- `tests/` — 5 tests, all passing; offscreen construction via QT_QPA_PLATFORM=offscreen; widget-order + nav-state assertions.
- ruff config in pyproject; `ruff check .` clean.
- PyInstaller: onedir `--windowed --name ball.buddy --collect-submodules PySide6` → `dist/ball.buddy/ball.buddy.exe` builds and launches (event loop runs).
- `AGENTS.md` Info section: setup/run/test/lint/build commands + environment notes (system Python 3.14.7, repo-local .venv, theme constraints).
- Reviewer verdict PASS; post-review fixes: `QPushButton:focus` rule added (theme.py), sidebar/stack order corrected so the nav renders left (shell.py).
