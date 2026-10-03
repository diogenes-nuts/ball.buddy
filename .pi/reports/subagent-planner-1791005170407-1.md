## M0 plan — ball.buddy scaffold (N:/LLM/projects/ball.buddy)

Env facts: Python 3.14.7 at C:\Users\User\AppData\Local\Python\pythoncore-3.14-64 (no venv yet; PySide6/pytest/ruff/pyinstaller NOT installed). Pip index (Py 3.14-resolvable): PySide6 6.11.2, pytest 9.1.1, ruff 0.16.10, pyinstaller 6.22.3.

**1. venv + tree.** `python -m venv .venv`. Create:
```
ball_buddy/__init__.py  (VERSION="0.0.0")
ball_buddy/main.py      (entry: QApplication → ui.shell.MainWindow → exec)
ball_buddy/ui/{__init__.py, theme.py, shell.py}
ball_buddy/ui/views/{__init__.py, draft.py, placeholders.py}
ball_buddy/services/__init__.py  ball_buddy/domain/__init__.py  ball_buddy/io/__init__.py
tests/{__init__.py, test_domain_import.py, test_shell.py}
pyproject.toml  ruff is configured in it  .gitignore (.venv dist build __pycache__ .pytest_cache)
```
Domain/__init__.py holds one tiny pure-Python value (e.g. `CATEGORIES: tuple[str,...]` = 9 cats) so the domain-import test is real. No other logic in M0.

**2. pyproject.toml.** `[project] name="ball-buddy", version="0.0.0", requires-python=">=3.14,<3.15", dependencies=["PySide6==6.11.2"]`; `[dependency-groups] dev=["pytest==9.1.1","ruff==0.16.10","pyinstaller==6.22.3"]`; `[build-system]` hatchling. Pin rationale (R5): exact pins of the newest Py-3.14-resolvable releases, verified resolvable on this machine via pip index; record fallbacks in a comment: PySide6 6.10.3, pytest 9.0.3, pyinstaller 6.19.0 (first versions with stable 3.14 support). `[[tool.uv]]`/hatch not needed — use plain pip + `[tool.pytest.ini_options] testpaths=["tests"]`. Ruff: `line-length=100, target-version="py314", lint.select=["E","F","I","UP"]`, exclude dist/build.

**3. UI (tactile-cream-ui — tokens from skill tokens.json, light theme only for M0).** `theme.py` = single Qt stylesheet string mapping tokens: canvas #F5EFE0 (window), surface #FBF7EC, sunken #EBE4D1, outline 2px solid #000000 on every container AND control, radius 0 for containers / 8px for buttons, font-family "IBM Plex Mono", Consolas, monospace; base font 13px, secondary text #5E584B, muted #736C5B (never on sunken), ink-fill button #1C1A16 bg / #F5EFE0 text; nav item = control-styled button (gradient approximated: Qt can't do box-shadow — accepted documented deviation: flat surface + 2px outline + 1px light top border via `border-top-color`). Density: 32px nav button height, 4px-scale spacing (4/8/12/16/24), no emoji, sentence-case labels. `shell.py`: QMainWindow, fixed left sidebar (QVBoxLayout, 6 nav buttons: League, Matchup, Waivers, Lineups, Trades, Draft; Draft selected by default, checked state = sunken bg), QStackedWidget: 5 placeholder pages (placeholders.py: centered QLabel "coming soon" on surface panel) + real `draft.DraftView`: 2px-outlined panel titled "draft board" (semibold 16px), body 13px "draft mode lands in M2" — the only page that isn't the generic placeholder.

**4. Tests.** `test_domain_import.py`: import ball_buddy.domain + CATEGORIES len 9 — must NOT import PySide6 (assert "PySide6" not in sys.modules after import). `test_shell.py`: fixture sets `os.environ["QT_QPA_PLATFORM"]="offscreen"` BEFORE any PySide6 import; construct QApplication + MainWindow; assert 6 nav labels in order and clicking League switches stack index.

**5. Build.** `.venv\Scripts\pyinstaller --onedir --windowed --name ball.buddy --collect-submodules PySide6 --paths . ball_buddy\main.py` → dist\ball.buddy\ball.buddy.exe. (No spec file needed; command is the spec.)

**6. AGENTS.md Info** — exact content: Setup `python -m venv .venv; .venv\Scripts\pip install "pyproject.toml"` style: `.venv\Scripts\pip install PySide6==6.11.2 && .venv\Scripts\pip install -e .` is NOT used (no install); simpler: `.venv\Scripts\pip install PySide6 pytest ruff pyinstaller` (versions per pyproject). Run: `.\.venv\Scripts\python -m ball_buddy.main`. Test: `.\.venv\Scripts\pytest`. Lint: `.\.venv\Scripts\ruff check .`. Build: the §5 command, then `.\dist\ball.buddy\ball.buddy.exe`.

**7. Verify (SPEC §9, in order, all from repo root):** ① `.\.venv\Scripts\pytest -q` (expect 3+ pass) ② `.\.venv\Scripts\ruff check .` (clean) ③ `.\.venv\Scripts\python -c "import ball_buddy, ball_buddy.domain; print('ok')"` ④ §5 build, then run dist exe, confirm window with sidebar + Draft page.

**8. git.** `git init` + `git config user.name/user.email` only if unset locally? NO — just `git init`; stage nothing, commit nothing (phase_complete commits).

**Risks:** Qt stylesheet can't express box-shadow/real gradients (documented deviation, not a blocker); 6.11.2 is 2 months old — if wheel install fails on 3.14.7, drop to 6.10.3 and update pins+AGENTS.md; keep tokens in theme.py as named constants so M2 can swap.