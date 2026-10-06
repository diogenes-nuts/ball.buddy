# State — ball.buddy: dark mode + flat controls DONE, green (290+1), exe rebuilt, final report pending
(Rewrite this whole file at every checkpoint. Never append. If a fact
no longer matters, delete it — git history keeps the trail.)

"Told" = user has heard this from you in plain words. Reading it in a log
does not count.

## Status
- User: "Might as well throw in a dark mode. I also want to get rid of the gradient frame around buttons" — DONE. 290 passed + 1 skipped, ruff clean. Exe rebuilt with dark mode (dist/data preserved: moved to /tmp during pyinstaller -y, restored). Tree uncommitted (auto-commit on clean exit; no manual commits).
- Next: final report to user (was interrupted by rebuild). Report = what's in "What changed" below.

## What changed (this session, all done + tested)
- theme.py: palette dicts LIGHT + DARK (from tokens.json) + _style(palette) + apply_theme(app, "light"|"dark"). Flat control fills: ALL border-top-color lines removed (gradient frame gone; states = flat fill shifts). Dark inverts: outline cream, ink_fill cream (active nav + ink buttons + checkboxes = cream fill, dark text).
- shell.py: "Dark mode" QCheckBox in sidebar footer (self.theme_toggle test seam); toggle -> apply_theme + persist settings["dark_mode"]; __init__ order FIXED: _build_stack() now runs BEFORE _build_sidebar() (layout order preserved, toggle needs sync_service).
- main.py: theme applied from persisted settings AFTER MainWindow construction, before show() (no light flash on dark install).
- Tests: test_shell.py +2 (toggle applies+persists with monkeypatched resolve_data_dir->tmp_path; both palettes build valid styles). 290+1.
- Docs: agents/scaffold/status.md (theme line, shell footer line, "Not yet" = only box-shadow fidelity + bundled fonts left); AGENTS.md env line (light+dark, flat fills).

## Prior session (committed? no — c198f43 predates cream reconciliation; tree had cream-UI changes + now dark mode, all uncommitted until auto-commit)
- Cream-UI reconciliation: status-colored banners (banner-info/success/danger), _status.py set_status, display-face titles (Trebuchet degrade), sidebar footer name+version, ink active-nav, input/checkbox styling, 28px rows, numeric right-align. Docs done.

## Env gotchas
- Windows bash: forward slashes. edit() atomic — failed call applies NOTHING (QCheckBox import loss this session: 2nd edit of a 2-edit call failed, 1st applied? NO — whole call failed; had to re-add import separately). Non-ASCII (em dash) oldText fails -> sed/python heredoc.
- pyinstaller -y wipes dist/ — ALWAYS mv dist/data /tmp/bbdata first, restore after. Check tasklist for running exe first.
- PySide6 6.11: QTableWidgetItem.setTextAlignment accepts OR'd flags (int() wrapper = deprecation warning).
- Stack: Py 3.14.7, PySide6 6.11.2, yfpy 17.0.0, cryptography 50.0.2, pytest 9.1.1, ruff 0.16.10, pyinstaller 6.22.3.
- League facts: 14 teams; 24 keepers; FAAB $100; top-4 playoffs; pure 9-cat. Yahoo reactivation pending.

## Goal (latest user message, verbatim)
Might as well throw in a dark mode. I also want to get rid of the gradient frame around buttons
