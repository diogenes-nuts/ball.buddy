# scaffold — done

## 2026-10-03 — M7.1 — Exe packaging foundations (slice 1/2 of M7): frozen-aware resolve_data_dir (exe writes data/ next to itself, not into _internal; dev path unchanged), shared app-icon painter (cream/basketball, tactile-cream) wired to both the window icon and a build-time PNG-in-ICO generator (scripts/make_icon.py, zero new deps) with assets/icon.ico committed and added to ball.buddy.spec + AGENTS.md build command. 3 new tests (frozen/dev branches, shell data_dir+icon). 228 tests green, ruff clean, exe rebuilt with icon.

- `ball_buddy/pathing.py` — `resolve_data_dir()`: `sys.frozen` → `Path(sys.executable).resolve().parent / "data"`; dev → repo-root `data/` (identical to old inline `parents[2]` in shell.py). shell.py now consumes it; no other independent data-dir computation in prod code (verified by grep — all consumers get `data_dir` from SyncService).
- `ball_buddy/ui/appicon.py` — `draw_app_icon(size)`: cream #F4EBDD rounded square, 2px #2B2620 outline, orange ball + seams. Single source for window icon (shell.py setWindowIcon, QPixmap.fromImage) and the .ico.
- `scripts/make_icon.py` — offscreen QGuiApplication (env set before PySide6 import), 256×256 → PNG in a TemporaryDirectory → PNG-in-ICO (ICONDIR + one 256×256 32bpp entry, offset 22). Deterministic fixed constants; committed `assets/icon.ico` (11,557 bytes, header `00 00 01 00`) reproducible.
- `ball.buddy.spec` — `icon=['assets/icon.ico']`; collect_submodules PySide6 + onedir intact, matches AGENTS.md CLI (`--icon assets\icon.ico` added there too).
- Tests: `tests/test_pathing.py` (frozen branch via monkeypatch sys.frozen/executable → tmp_path/"data"; dev branch vs independently computed repo root), `tests/test_shell.py::test_data_dir_and_window_icon` (window.data_dir == resolve_data_dir(), 16px icon pixmap non-null).
- Reviewer: no defects; nits (make_icon ignores QImage.save return; build-script QApplication never quit) left as-is.
- Exe rebuilt: dist\ball.buddy\ball.buddy.exe (5.46 MB) with icon. Verify: 228 passed / 1 skipped, ruff clean, offscreen smoke printed repo data_dir + non-null icon.
