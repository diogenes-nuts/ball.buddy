# Project

## Info

_Build, test, and run commands + environment notes. Brief; no function/structure detail (that lives in component status docs under agents/)._

### Setup (once)

```
python -m venv .venv
.venv\Scripts\pip install PySide6 pytest ruff pyinstaller
```

Pins per `pyproject.toml` (PySide6 6.11.2, pytest 9.1.1, ruff 0.16.10, pyinstaller 6.22.3 — newest Py-3.14-resolvable releases, exact pins of those; no editable install).

### Run

```
.\.venv\Scripts\python -m ball_buddy.main
```

### Test

```
.\.venv\Scripts\pytest
```

### Lint

```
.\.venv\Scripts\ruff check .
```

### Build (PyInstaller onedir)

```
.\.venv\Scripts\pyinstaller --onedir --windowed --name ball.buddy --collect-submodules PySide6 --paths . ball_buddy\main.py
```

Run the result with `.\dist\ball.buddy\ball.buddy.exe` (the `build\` dir is PyInstaller's work area; both are gitignored).

### Environment

- Python 3.14.7 at `C:\Users\User\AppData\Local\Python\pythoncore-3.14-64` (system, no global installs — always use `.venv`).
- Windows: run the app via `python -m ball_buddy.main`; the venv must be created inside the repo (`.venv`).
- UI theme: tactile-cream-ui, light only in M0; Qt can't do box-shadow/gradients — control gradients approximated with flat fill + 1px light top border (documented in `ball_buddy/ui/theme.py`).
