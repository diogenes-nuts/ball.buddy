# State — board search popup sizing (multi-row dropdown) — DONE
(Rewrite this whole file at every checkpoint. Never append. If a fact
no longer matters, delete it — git history keeps the trail.)

"Told" = user has heard this from you in plain words. Reading it in a log
does not count.

## Status
- Position: 006_board search popup height fix — complete: code + test green, ruff clean, exe rebuilt (data/ moved+restored), status.md updated. Awaiting user visual check.
- Exact next step: none; report to user. Uncommitted in working tree: board.py, tests/ui/test_board.py, agents/006_board/status.md (+ earlier transient-box fix) — auto-commit on clean exit.
- Rules in force: always rebuild exe after code changes; per-directory pytest (combined Qt-views run hard-kills, env flake).

## Verification
- Baseline: 250165e + transient-box fix (26 passed) + popup-height fix → `tests/ui/test_board.py` 27 passed, test_draft_view + test_league_view 43 passed, ruff clean. Exe rebuilt 2026-10-13 (build 85s).
- Test failure during dev was my own wrong expected counts (POOL "e" matches 5/6; cap case 9 matches → 8 rows) — fix code itself never misbehaved.

## Findings
- Popup had setFixedWidth, no height → Qt sizeHint minimum = 1 row. Fix: `SEARCH_POPUP_MAX_ROWS = 8` + `setFixedHeight(rows × row_h + 4)` in `_on_search_text`; row_h = max(sizeHintForRow(0), fontMetrics height + 2). User asked "at least 5, scrollbar fine" → chose 8. — told yes
- Qt textChanged quirk: setText with identical text does NOT re-fire — test must clear() first. — internal
- Search semantics (single case-insensitive substring) confirmed correct by user; pool genuinely has few matches for short distinctive queries (jok→1). — told yes

## U-turns
- (none)

## Dead ends
- (none new)
