# scaffold — status

Repo scaffold for ball.buddy: Python package `ball_buddy` with a PySide6 desktop shell, tactile-cream-ui theme, and a runnable PyInstaller onedir build (icon, frozen-aware data dir, reset, error UX — M7 complete). Feature logic lives in components 001–006.

## Files

- `pyproject.toml` — pins: PySide6 6.11.2, pytest 9.1.1, ruff 0.16.10, pyinstaller 6.22.3 (newest Py-3.14-resolvable; see AGENTS.md).
- `ball_buddy/main.py` — entry point (`python -m ball_buddy.main`); friend-facing error UX (M7.2): global excepthook + Qt message handler append to `<data_dir>/app.log` and point the user at that file.
- `README.md` — friend-facing first-run guide (M7.2): run the exe, data/ location, Settings → sign-in → sync → pool import, reset + crash-log pointers.
- `ball_buddy/ui/shell.py` — `MainWindow`: left nav sidebar (League, Matchup, Waivers, Lineups, Trades, Draft) + QStackedWidget; Draft view checked by default. Spec sidebar shell: surface fill + 2px right edge, app name (display face) above `v{VERSION}` (mono, secondary) in a divider-separated footer + a "Dark mode" checkbox (persisted as `settings["dark_mode"]`, live re-applies the stylesheet; `main.py` applies the persisted theme before first show). Window icon from the shared app-mark painter; data dir via `pathing.resolve_data_dir()`.
- `ball_buddy/pathing.py` — `resolve_data_dir()`: repo-root `data/` in dev, exe-adjacent `data/` when frozen (PyInstaller onedir).
- `ball_buddy/ui/appicon.py` — `draw_app_icon(size)`: the cream rounded-square + basketball mark (window icon and icon.ico source).
- `scripts/make_icon.py` — build-time: renders `assets/icon.ico` (256×256 PNG-in-ICO) offscreen; run before `pyinstaller`.
- `assets/icon.ico` — generated app icon (committed binary, wired into `ball.buddy.spec` + AGENTS.md build command).
- `ball_buddy/ui/theme.py` — tactile-cream-ui light + dark themes as QSS built from per-palette token dicts (`LIGHT`/`DARK` from tokens.json; `apply_theme(app, "light"|"dark")`, both palettes share one stylesheet layout). Full token set: warm cream palette + status colors (success/warning/danger/info), 2px hard outlines, monospace body, rounded display face for titles (`#title`/`#appname`; Quicksand → Trebuchet MS degrade on Windows), styled inputs/combos/spinboxes (sunken), checkboxes, 28px table rows, ink-fill active nav (dark inverts ink to cream). Banner classes: `banner` (alias of `banner-info`), `banner-success`, `banner-danger`. User deviation: controls use a FLAT fill (no gradient, no 1px light top-border frame) — states shift the flat fill. Qt QSS limitations (no box-shadow/row-hover) documented in the module docstring.
- `ball_buddy/ui/views/_status.py` — `set_status(label, kind, text)`: switches a banner QLabel between info/success/danger classes (re-polish on switch, empty text hides). Engine views (matchup/waivers/trades/lineups) color their result banners by outcome; board/draft/league use their own `_set_banner` with the same class names.
- `ball_buddy/ui/` views — League/Matchup/Waivers/Lineups/Trades/Draft (all real; PlaceholderView deleted at M6.2 — shell asserts on unknown nav labels). Numeric table columns right-aligned (spec).
- `tests/test_shell.py`, `tests/test_pathing.py`, `tests/test_excepthook.py` — shell construction, nav state (every nav item), data dir (frozen/dev), window icon, app.log error hook (see done.md for M7.1).
- `ball.buddy.spec` + PyInstaller onedir build → `dist/ball.buddy/ball.buddy.exe` (rebuild commands in AGENTS.md; `build/`, `dist/` gitignored).
- `info.md` — AutoDraft domain brief (salvage context source for 001_data / 006_board).

## Not yet

- Box-shadow fidelity (flat-fill approximations instead), full font stack (bundling Quicksand/IBM Plex Mono) — deferred nits from M0 review (out of M7 scope by decision). Dark theme was deferred but added at the user's request (see theme.py line).

Plans: dev.md (none yet).
