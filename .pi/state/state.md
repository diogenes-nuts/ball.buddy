# State — overhaul 7: third screenshot review (rail h-scroll + dead right space; popup floats mid-screen)
(Rewrite this whole file at every checkpoint. Never append.)

## Status
- Position: OVERHAUL 7 code+tests DONE in working tree (uncommitted). Both fixes verified in source: (1) _sync_panel_widths now does resizeColumnsToContents() + rail_w = max grid column-sum + 20 chrome (sizeHint was a stub — offscreen: sizeHint 272-384 vs real grids 478-754); called at render tail (~818), refresh no-snapshot path (~726), AND new showEvent override (~842, theme-polished widths). (2) Popup = child QListView but was moved with mapToGlobal (GLOBAL into child-local move → 2× offset = mid-screen); now mapTo(self, QPoint(0, height)) board-local + setFixedWidth(edit+4) before show. Trailing row.addStretch(1) already removed (left panel Expanding claims leftover).
- Exact next step: docs (done.md overhaul-7 section, status.md rail/popup lines, dev.md phase count 1–7) → rebuild exe (mv dist/data → dist_data_backup, pyinstaller -y fwd slashes ~90s, restore) → phase_complete(006_board, overhaul 7) → tell Meatbag to re-screenshot.
- In flight: board.py + test_board.py modified, verified green; dev.md phase-count bump pending; no stray files (crops/diags deleted; .pi/state/era-*.md untracked = internal, fine to sweep; old Screenshot 2026-10-08*.png show D — already gone from disk, tracked at HEAD, deletion OK; Screenshot 2026-10-09 131142.png tracked via WIP commit 32c65f2).
- Rules in force: always rebuild exe after code changes; mv dist/data aside first, restore after; per-file pytest only (combined dies exit 127). Address user as Meatbag. phase_complete per phase.

## User round 4 (2026-10-09, told: yes — fixes explained on next report)
- "LOTS of issues here, let me know what you see."
- "The side rail still requires scrolling, and there's a ton of wasted space to the right of it."
- "The popup for the search appears to work better, but it shows up floating in the middle of the screen instead of under the search bar."
- Screenshot 131142 crops (text-only review after llama.cpp vision crash): pool table GOOD (stat colors, no truncation, fills left); rail = 3 panels each ~295px with inner h-scrollbars + dead canvas right of rail; stray small bordered box over the offline banner's left edge (~x225-300,y85-130) — almost certainly the misplaced search popup (child painted at the wrong local offset).
- Llama.cpp vision crashed & disabled — continue text-only; Qt QImage can crop PNGs when pixel inspection is needed.

## Findings
- POPUP ROOT CAUSE: child widget (QListView(self)) + move() in GLOBAL coords = board-local misplacement; maximized board offset ~250px → popup landed ~2× offset. Fix = mapTo(self) + width-before-show (implemented).
- RAIL ROOT CAUSE: QTableWidget sizeHint is a stub (under-reports 2-3×); panel.sizeHint() useless. Fix = measure actual column sums after resizeColumnsToContents + 20 chrome (implemented). Trailing row stretch removed.
- Prior rounds all committed: overhaul 6 (0c9a00c), 5 (19ea097), 4 (83d3bed era), P6/P7 etc.

## Verification
- NOW GREEN (working tree): ruff clean (board.py + test_board.py), test_board.py 25 passed, ALL ui per-file green (board 25, draft 5, inbox 4, league 13, lineup 5, matchup 9, setup 13, sign_in 4, theme 5, trade 7, waiver 5).
- Baseline 0c9a00c was all-green too; exe on disk = overhaul-6 build (STALE — rebuild pending).
- test_board.py: rail test now asserts rail.width() == max(sum(grid col widths)+20) after show(); popup test uses real setText path.

## Dead ends
- PIL not in venv or system python (use Qt QImage for crops); /tmp unreadable (crop to project root); invalidateFilter Qt 6.11; plain QTableView::item QSS; setWeight(int); backslash args; QCompleter prefix/empty; reverse=True desc.

## U-turns
- Qt.Popup → frameless only (overhaul 6); left panel fixed → stretch (overhaul 6); panel.sizeHint-based rail width → grid column-sum measurement (overhaul 7); mapToGlobal → mapTo(self) (overhaul 7).
