# State — overhaul 6: code+tests+docs done, rebuilding exe now
(Rewrite this whole file at every checkpoint. Never append.)

## Status
- Position: OVERHAUL 6 COMMITTED (0c9a00c), exe rebuilt (overhaul-6 build on disk), docs in place. Awaiting user re-screenshot.
- Exact next step: user re-screenshots → verify: popup appears on typing, no "+…" truncation, pool fills window width, stat colors back, opens fullscreen. Dev.md phase count bumped to 1–6 (uncommitted, lands next).
- In flight: dirty = theme.py, board.py, main.py, test_board.py, docs (status/done 006_board). dev.md unchanged this round (no §6 was written).

## User round 3 (told yes — diagnosed + fixed)
1. "No popup appears. Doesn't work." 2. "columns are no longer the width of their contents, neither the right rail or the pool resize when the window is expanded" + "Can we default to opening in fullscreen?" (→ yes) 3. "Looks good, though we lost the stat-correlated color in the player pool."

## Findings (all offscreen-confirmed, /tmp/repro*.py, /tmp/final_check.py)
- POPUP: Qt.Popup flag → show() steals focus → FocusOut → own eventFilter hides it. Fix: FramelessWindowHint only. Verified visible+rows.
- TRUNCATION: app default font metrics vs Plex Mono 13 medium render (+8px). Fix: QFont(FONT_MONO, 13px, QFont.Weight.Medium) — NOTE setWeight rejects int, use enum.
- STAT COLORS: plain `QTableView::item { … }` QSS rule kills model BackgroundRole (QStyleSheetStyle takes over). Fix: rule → QTableWidget::item only; :selected rules safe. Verified coexist with teal row.
- LAYOUT: left panel Expanding + stretch (was content-fixed in overhaul 5 → dead canvas); rail stays content-width. Verified 850→1050 on resize.
- FULLSCREEN: main.py showMaximized().
- phase_complete silently no-ops on untracked `nul` (told no). app.log no new tracebacks.

## Verification
- Baseline 19ea097 green. Post-fix (uncommitted): ui per-file ALL GREEN (board 25, draft 5, inbox 4, league 13, lineup 5, matchup 9, setup 13, sign_in 4, theme 5, trade 7, waiver 5), ruff clean, offscreen final_check all 4 behaviors OK.
- exe on disk = overhaul-6 build (rebuilt 0c9a00c; dist/data restored after).

## U-turns
- left panel fixed → stretch (overhaul 5 over-inference; user req was rail only)
- Qt.Popup → frameless only (focus steal)
- QTableView::item rule → QTableWidget-only (BackgroundRole killer)
- app-font metrics → theme cell font metrics
- invalidateFilter → model reset; QCompleter → QListView (ph2); data-role → model.sort() (ph4)

## Dead ends
- invalidateFilter Qt 6.11; plain ::item QSS on QTableView; setWeight(int); `app` vs `qapp` in tests; reverse=True desc; backslash args; QCompleter prefix/empty
