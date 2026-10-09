# 006_board — done

## 2026-10-09 — overhaul 7 — Third screenshot review: rail sized to actual grid content (sizeHint is a stub — inner h-scrollbars gone, dead canvas right of the rail gone), search popup anchored under the search bar (mapToGlobal on a child widget double-offset it to mid-screen on a maximized window)

### 7.1 — Rail still h-scrolled + dead space to its right
- Root cause (offscreen repro): `_sync_panel_widths` sized the rail from the panels' `sizeHint()`, but **QTableWidget's sizeHint is a stub** (reports ~272–384px while the grids' real content is 478–754px column-sum) → rail pinned at ~292px → every inner grid got its own horizontal scrollbar. The dead canvas right of the rail came from a trailing `row.addStretch(1)` splitting leftover width with the left panel. Fix: `rail_w = max(sum(grid.columnWidth(ci)) + 20 (margins 8×2 + border 2×2))` after forcing `resizeColumnsToContents()` (column widths lag a frame in ResizeToContents mode); trailing stretch removed — the left panel (Expanding) claims all leftover. Re-synced in a new `showEvent` too: grid columns only polish with the theme font at show time, so a pre-show measurement under-shoots.

### 7.2 — Search popup floated mid-screen
- Root cause: the popup is a CHILD of the board (`QListView(self)`, `isWindow()` False) but `_on_search_text` positioned it with `name_edit.mapToGlobal(…)` — GLOBAL coordinates fed into a child `move()`, which expects BOARD-LOCAL coordinates. Off-screen (board at 0,0) the offset is 0 so tests never saw it; in the real maximized app (board offset ~250px) the popup landed at ~2× the offset — mid-screen. Fix: `move(name_edit.mapTo(self, QPoint(0, height)))` + width set before `show()`.

Tests: rail test now asserts `rail.width() == max(grid column-sum + 20)` after `show()` (sizeHint-era 480/panel-width asserts gone); popup test keeps the real `setText` path. All ui per-file green, ruff clean, exe rebuilt.

## 2026-10-08 — overhaul 6 — Second screenshot review: search popup actually appears (Qt.Popup flag stole focus → own focus-out filter killed it on show), pool columns truly content-width (theme cell font for metrics — app font under-measured ~8px), left panel stretches again (rail stays content-width), stat-color backgrounds restored (plain QTableView::item QSS rule drops model BackgroundRole), app opens maximized

### 6.1 — Search popup never appeared
- Root cause (offscreen repro): `Qt.Popup` windows grab keyboard focus on `show()` → the search edit's `FocusOut` → the overhaul-5 event filter hid the popup before it was ever visible (geometry + narrowed rows were all fine). Fix: drop `Qt.Popup`, keep `FramelessWindowHint`; the focus-out filter still closes it on click-away.

### 6.2 — Columns narrower than their content ("+…" truncation)
- `_fit_player_columns` measured with the view's inherited application font, but the theme's `*` rule renders **IBM Plex Mono 13px medium** (~8px wider advances: "+1.23" 60→65, longest name 276→299). Fix: measure with a `QFont(FONT_MONO, pixelSize 13, Weight.Medium)` built from the theme's own constants.

### 6.3 — Dead canvas on wide windows → left panel stretches again
- Overhaul 5 content-fixed BOTH panels (left = table width), but the user's content-width request was about the **rail** — a fixed left panel left ~half the fullscreen empty. Fix: left panel `Expanding` + row stretch (leftover = empty pool-table background, the Name-column rule); rail keeps its `_sync_panel_widths` content width.

### 6.4 — Stat-color backgrounds lost
- Isolated by pixel-level offscreen bisection: a **plain `QTableView::item { … }` QSS rule** (no `:selected`) makes `QStyleSheetStyle` take over item painting and drops model `BackgroundRole` — every stat-tinted cell painted surface. Overhaul 5 had widened the padding rule's selector to include `QTableView`. Fix: `QTableWidget::item` only; the `:selected` rules (which do NOT kill backgrounds) stay, so full-row teal + stat tints coexist. Gotcha documented in the theme QSS source.

### 6.5 — Open maximized
- `main.py` `show()` → `showMaximized()` (user ask).

Tests: popup test now drives the real `setText` path + asserts `isVisible()` and keeps the focus-out close assert; layout test asserts left panel `Expanding` + rail == widest panel content (480-gone). All ui per-file green, ruff clean, exe rebuilt.

## 2026-10-08 — overhaul 5 — Screenshot-review fixes: search dropdown actually narrows (Qt 6.11 neutered invalidateFilter — root cause), popup closes on focus-out, both board columns content-width left-packed (replaces the stretch + RAIL_WIDTH=480 from overhaul 4), teal accent tokens on active UI state app-wide

### 5.1 — Search dropdown bug (user: "it shows ALL players in the drop down, not only the names with the searched term")

- **Root cause:** the popup proxy's `set_query` re-filtered via `QSortFilterProxyModel.invalidateFilter()`, which Qt 6.11 **deprecated and turned into a no-op** — the popup silently kept showing every name. Verified offscreen before fixing.
- Fix: `set_query` → `beginResetModel()`/`endResetModel()` (proxy re-queries rows on reset). Verified: typing narrows to the matching rows, clearing restores the full list. Scope per user: **only the dropdown narrows** — the pool table itself is never filtered by the search box.
- Popup now **closes when the search box loses focus**: `name_edit` event filter → `QEvent.Type.FocusOut` → `search_popup.hide()`. Click-to-autofill is safe (pick handler hides the popup first; the popup carries `Qt.Popup`, so outside-click auto-close is handled by Qt).

### 5.2 — Content-width columns, no dead space (user: "the side rail should also be exactly its content width if the window is wide enough, only scroll horizontally on narrow")

- `_sync_panel_widths()` (called at the end of every `render()` and in the refresh no-snapshot path): left panel = pool table's exact column-content width (sum of column widths + table frame 4px + panel margins 16px + panel border 4px); right rail = its widest panel's sizeHint width. Both left-packed; the row's stretch keeps leftover window width as empty canvas. Narrow window: the rail's horizontal scrollbar (AsNeeded) takes over; pool keeps priority.
- Recs "Reason" column: `Stretch` → `ResizeToContents` (it was what made the rail greedy, and the grid had a fixed 480px fallback).

### 5.3 — Teal accent on active UI (user: "teal sounds great… accents on active ui functions throughout the entire app would be nice")

- New theme tokens `accent`/`accent_text` — light `#16605A` on `#F5EFE0`, dark `#4FD1C5` on `#1B1913` — applied to every ACTIVE-state control: nav active tab (was ink), checked checkboxes, input focus border, text selections (QLineEdit + popup/combo list items), combo/list selections, and table rows (full-row `QTableView::item:selected` background, light + dark, explicit rules for both QTableWidget and QTableView — QSS does not inherit between the two).
- Ink primary buttons deliberately stay ink (action, not state — flagged to user as a judgment call).

Tests: `test_search_dropdown_narrows_and_closes_on_blur` (narrowing + restore + focus-out close), `test_two_column_layout_right_rail_scroll` updated (rail == max panel content width, left panel == table content + chrome, no inner h-scrollbar), Reason-column mode assert. All ui per-file green, ruff clean, exe rebuilt.

## 2026-10-08 — overhaul 4 — Two-column layout: left = pick strip + pool table (priority surface), right = scrollable rail Recs → Comparison → Roster (content-size panels); pool table columns sortable by header click (model sorts by parsed z, missing last in both directions). *(Overhaul 5 later made both columns content-width left-packed instead of stretch + fixed 480.)*

4. **Two-column layout** — board became left column (pick strip + pool table, the
   scrollable priority surface, keeps all leftover width) + right column (QScrollArea:
   Recommendations, then Comparison, then Roster, each a panel at content size).
   Right rail fixed preferred width (RAIL_WIDTH=480), vertical scroll only; recs rows
   stay NoSelection. Pool-table columns sortable by header click, sorted by parsed
   values (z columns by parsed float, Rank by int, Name/Pos case-insensitive).

   Implemented in `board.py`: layout is `root → alert_banner + QHBoxLayout(row)`;
   `row` holds `left_panel` (stretch 1: strip + POS filter + pool table) and the
   right rail `self.right_rail` (QScrollArea, NoFrame, widgetResizable, h-scrollbar
   AlwaysOff, `setFixedWidth(RAIL_WIDTH)`) wrapping a plain widget whose layout holds
   `recs_panel → relative_panel → roster_panel → addStretch`. Recs moved into its own
   panel (new `recs_panel`, Preferred/Maximum, 8px margins) above Comparison in the
   rail; Comparison and Roster panels re-parented to the rail (both now Preferred/
   Maximum). `recs_grid.setMinimumHeight(header + rows*22 + 4)` in `_sync_recs_height()`
   (called at both `setRowCount` sites) — a QTableWidget sizeHint covers only a few
   rows and would collapse in the scroll rail. Sorting: `player_view
   .setSortingEnabled(True)`; `PlayerTableModel.sort()` (QAbstractTableModel.sort is a
   NO-OP by default — a data role alone does nothing) stores `_sort_key (col, asc)`
   and re-runs `_rebuild`, which `sorted()`s the filtered rows by `_row_sort_key(row,
   col, ascending)`: Name/Pos case-folded, Value/Rank/z by parsed float via
   `_parse_z`, missing values `(1,)` sentinel LAST in both directions — the number is
   negated for descending instead of using `reverse=True` (which flips the sentinel to
   the front). `set_pos_filter`/`reset_pool` clear the sort (pool order).
   Module docstring rewritten for the two-column layout. `QFrame` + `QScrollArea`
   imports added.
   Notes: the plan's "model supplies a data role" became a real model-side `sort()`
   (Qt requires it; the data role was only the mechanism for *how* to order). Roster
   grid's 13 content-width columns (~630px) exceed the 480 rail → the roster panel
   gets its own horizontal scrollbar inside the panel (QTableWidget default AsNeeded);
   accepted — moving the roster to the left column was the alternative.
   Tests (test_board.py): `test_pool_table_sortable_by_parsed_z` (parsed-z asc/desc
   numeric order — "+0.4"<"+1.1"<"+2.0"<"+9.9", missing last in BOTH directions, rank
   numeric "1"<"10", POS filter resets sort) + `test_two_column_layout_right_rail_
   scroll` (panels are rail-viewport children in order, rail width 480, Maximum
   vertical policy, recs min-height > 0).
   Status: done — pool table is the priority surface with sortable numeric columns;
   recs/comparison/roster sit in a scrollable content-size rail. Visual verify pending
   (no local snapshot to render).

## 2026-10-08 — overhaul 3 — Recs + chrome cleanup: recs Reason human-labeled (CAT_LABELS), single offline banner (board owns all banners; page keeps keepers alert only), redundant "Draft board" title + page status banner removed, Roster panel stops stretching, stale docstring fixed

3. **Recs + chrome cleanup** — recs Reason column shows human labels via CAT_LABELS
   (FG%/FT%/3P/Pts/Reb/Ast/Stl/Blk/To) instead of raw keys; remove the duplicate
   offline banner (keep the board-level one; the DraftView one stays only for the
   no-snapshot danger case or is removed — pick whichever renders exactly one banner
   in every state and say which); remove the redundant "Draft board" title; Roster
   panel stops stretching to fill leftover height (content height, no stretch factor);
   fix the stale module docstring in board.py ("recommendations rail on the right").

   Implemented: recs Reason now joins `CAT_LABELS[c]` (was raw cat keys). Banner
   dedupe — the **board owns ALL banners** (offline notice + danger alerts, including
   the no-snapshot "Sync the league first"); `DraftView` dropped its own offline
   banner, its (always-empty) status banner, the redundant "Draft board" title, and
   the `_offline` import; the page's `alert_banner` is now keepers-only (over-cap /
   keepers.json parse). The Roster panel's grid got
   `QSizePolicy(Preferred, Maximum)` so it no longer balloons to fill the leftover
   window height. board.py module docstring corrected (recs sit between the pool table
   and Comparison; banners live on the board).

## 2026-10-08 — overhaul 2 — Search dropdown: QLineEdit + QListView popup with live partial (substring) matches that autofill on click; dropped the redundant Log selected button (double-click + Enter remain)

2. **Search dropdown + single pick path** — the name edit's completer becomes a themed,
   visible dropdown with PARTIAL (substring, case-insensitive) matching of pool names
   (QCompleter over a proxy model, or custom filter model; popup styled from theme
   tokens — background/outline/radius, readable in both themes); selecting an entry
   fills the edit. Drop the "Log selected" button entirely (double-click + Enter remain).
   Completer list = current excluded-aware name set (keep the render() wiring).

   Implemented as a self-owned `QLineEdit` + `QListView` popup (NOT QCompleter): an
   empty-prefix QCompleter neither sets the line edit's text nor fires its activated
   signal (both verified), so the board owns `_PoolSearchFilter` (a substring,
   case-insensitive `QSortFilterProxyModel` over an excluded-aware
   `QStandardItemModel` of pool names) and a themed `search_popup` QListView. Typing
   re-filters + pops the list under the edit; clicking a row (`activated`) autofills
   the edit; the edit's own Enter commits. "Log selected" button removed (double-click
   + Enter remain); `theme.py` gained a `QListView` rule so the popup is themed in
   both palettes.

## 2026-10-08 — overhaul 1 — Pool table columns: font-metric content widths for all columns (fixes clipped z-cells/headers), Name no longer stretches — leftover space stays empty

1. **Pool table readability** — stat columns get a fixed per-column width wide enough
   for the mono font + 1-decimal z (no clipping of value cells OR headers); Name column
   switches from Stretch to ResizeToContents (longest-name width, re-fit on pool/filter
   change via existing `_fit_player_columns`). Leftover horizontal space is left empty
   (table background), not absorbed by any column.


## 2026-10-03 — M2.1 — Keeper entry (slice 1/3 of draft board): keepers domain model (team, pool-bridged player, cost round, opt-out), atomic persistence to data/keepers.json, bulk entry grid in Draft view (24 keepers, per-team cap validation, loud unmatched flags, cap-drop alert). 128 tests green, ruff clean.

- `domain/keepers.py`: model + validation (max 2 active/team, cost round 1–13, duplicate player across teams = error); opt-out semantics (player back to pool, pick back to team).
- `data/keepers.json` via `io/state.py` atomic save/load; corrupt >2-per-team files → loud cap-drop alert, no silent loss.
- `ui/views/draft.py`: entry grid (team, player + pool lookup, cost round, opt-out), per-row resolved/unmatched status, save flow; pool loaded once per refresh (no N+1).
- Post-review fixes: silent cap-drop surfaced via banner-alert; pool-load N+1 removed.
- Verify: 128 passed / 1 skipped, ruff clean, offscreen smoke OK (save → round-trip → unmatched flag → cap-drop alert).

## 2026-10-03 — M2.2 — Snake draft board view (slice 2/3): 12-team snake order with keeper-aware forfeited picks (opted-out keepers leave picks open), pick entry with pool lookup, undo-last, current-pick highlight, atomic persistence to data/draft_picks.json. 147 tests green, ruff clean; reviewer-caught even-round forfeit bug fixed.

- Pick model + atomic persistence (`data/draft_picks.json`); snake order 12-team x 13 rounds mirroring `league.snake_order`.
- `ui/views/board.py`: 13x12 grid; forfeits "Keeper: <name>"; current pick = first unentered open pick (forfeits consume overall numbers — R2 order 2 = overall 3); undo-last; click/tab navigation.
- Reviewer caught CRITICAL: even-round keeper cells rendered "Keeper: ?" (`_slot_of` used start-order slot instead of snake order). Fix: `_order_of` (odd rounds index+1, even rounds len-index), `_keeper_cells` keyed by snake order; +2 tests (even-round forfeit, opted-out even-round stays open). Also fixed round-13 cells unclickable (bounds check used 12 not grid rowCount 13).
- Verify: 147 passed / 1 skipped, ruff clean, offscreen smoke (even-round keeper cell, round-13 click) OK.

## 2026-10-03 — M2.3 — Pool value recommender (slice 3/3 — M2 complete): per-pick top-N suggestions from real pool rank/value/pos columns, excludes drafted picks + active keepers (opted-out keepers stay draftable), unranked rows show dash. 162 tests green, ruff clean; all ROADMAP M2 exit criteria verified.

- `domain/recommend.py`: top-N per current pick from pool `rank`/`value`/`pos`/`name` only (no invented stats); exclusion = drafted picks + non-opted-out keepers, alias-bridged both sides.
- `board.py` suggest panel: updates per current pick; unranked rows `rank=None` → "—".
- Post-review fixes (all 3 nits pinned with tests): opted-out keepers stay suggestable; unranked rank None (was max+1 = invented "200"); 12-team shape covered by domain test.
- Verify: 162 passed / 1 skipped, ruff clean, offscreen smoke (opted-out keeper, unranked dash) OK. **ROADMAP M2 exit criteria all verified.**

## 2026-10-06 — P1 — Draft v2 P1: Setup dialog (draft order, team names, keepers w/ opt-out, my-team flag) replaces the keeper grid + manual team list; includes 002_yahoo refresh-redirect_uri fix (invalid_grant on first post-expiry sync)
- `ui/views/setup_dialog.py`: teams & draft-order table (rename, Add/Remove, Move up/down, "My team" checkbox) + keepers table (team combo, player pool completer, cost round 1–13, opt-out, resolved/UNMATCHED status w/ "try <suggestions>" hints). Writes settings manual_teams + manual_draft_order (ordered list) + my_team, and keepers.json; validate/empty/duplicate-name errors block Save; corrupt keepers.json refuses save.
- `draft.py`: keeper grid removed → pointer to Setup; League Settings "Team list (offline)" field removed; board `setup_requested` signal + "Setup…" button, rebuild on accept.
- `002_yahoo` fix (landed in this commit): refresh grant must replay the EXACT grant redirect_uri (OAuth2 4124 §6); token dict persists callback_uri; old hardcoded https://www.yahoo.com caused 400 invalid_grant "invalid refresh token" on first post-expiry sync.
- Review fixes: duplicate/empty team names block Save; status column suggestions; 3 new UI tests.
- Verify: 299 passed / 1 skipped, ruff clean.

## 2026-10-06 — P2 — Draft v2 P2: need-aware recommender reworked to CATEGORY-level (9-cat via engine.project_roster, league-median gap fill normalized by per-cat spread, `to` direction handled, C1 scarcity, reason strings) after first position-level pass was rejected as wrong level
### P2 — Need-aware recommender (B + C1) — CATEGORY-LEVEL (spec correction 2026-10-06)
First pass implemented POSITION-level need (per-pos value totals); wrong level for a
9-cat H2H game — the compete/punt question is per-category. Rework required.

Team projection: `engine.project_roster(secured_rows, team_name, usage_factor=1.0)`
(all secured players active; no starter/bench). League median per category = median
across all teams' `cat_values[cat]`. My gap per cat: `gap_c` = how far I sit BELOW the
median in category c's better direction (higher for the 8, lower for `to`); positive =
I'm behind.

Normalization (category units are incomparable — PTS in hundreds, FT% a fraction):
`spread_c` = max−min of cat c across teams (0 → treat spread as 1). Normalized gap
g_c = gap_c/spread_c ∈ [0,∞); candidate fill f_c = player_c/spread_c for higher cats,
f_c = (1 − player_c/spread_c) for `to` (low-TO quality). 

Score per candidate = pool value + need + scarcity, where
`need = Σ_c min(g_c, f_c)` (gap actually filled, normalized units; [0, 9]) and
scarcity = max(0, median remaining count across positions − remaining count at the
candidate's primary position) (C1, unchanged). Weights as named module constants
(NEED_WEIGHT, SCARCITY_WEIGHT, default 1.0) for draft-day tuning.

Reason string: value bit + the top 2 gap-filling categories by filled amount
(e.g. "fills ft_pct & pts gaps") + scarcity bit when > 0.

Tests: need-beats-raw-value (candidate filling my weakest cat outranks higher-value
candidate filling nothing); `to` direction (low-TO player fills my TO gap, high-TO
doesn't); bias cancellation (uniform shift of a stat column keeps ordering); opted-out
keeper still eligible; my_team unset → M2.3 fallback. Exclusions unchanged.
Bench/starter: all secured players count.
- Review pass: fill clamped to [0,1] both directions; 'value 0' vs 'no pool value' reason distinction; pre-draft pct-dilution limitation documented. Verify: 309 passed / 1 skipped, ruff clean.

## 2026-10-06 — P3 — Draft v2 P3: relative panel — per-category my-team-vs-league with BUILD/COAST/PUNT tags (top-3 BUILD; bottom-3 PUNT when best remaining undrafted fill closes <25% of the normalized gap; else COAST), live per pick
### P3 — Relative panel
Per 9 categories: my team projection vs league distribution (all teams from picks so
far), with BUILD / COAST / PUNT tags. Live as picks are entered. (Tag thresholds
defined by planner from the league-relative distribution, e.g. percentile-based.)
- Impl: domain/relative.py category_tags (top_n=3 / bottom_n=3 / punt_close=0.25, 'to' direction handled, pre-draw COAST fallback, no-my-team → hidden); P2 helpers promoted public (category_gaps / cat_fill); board panel wired to the same refresh as the suggest panel. Verify: 321 passed / 1 skipped, ruff clean; review PASS, zero defects.

## 2026-10-07 — P6 — Scorer port: autodraft ValueGapScorer (0.45 market + 0.55 fit, hole/ok/covered multipliers, REACH/VALUE tags, value-gap flag) in domain/scorer.py; P2 need/scarcity demoted to reason bits; M2.3 fallback kept
### P6 — Scorer port (domain, offline-testable)
Port autodraft engine/scoring.py ValueGapScorer + needs.py edge math to ball_buddy
domain (new module or extend recommend.py; read the autodraft sources for the exact
formulas): market = (rankMax − rank)/rankMax; fit = Σ weight·z·multiplier over 9 cats
using the pool's z_* columns (blank z → 0, player excluded from fit contribution);
per-category edge = roster signed-z mean per slot vs pool mean, status hole/ok/covered
(covered ≥ +0.5z — re-derive thresholds against our 9-cat pool, document); score =
0.45·market + 0.55·fit_norm + tag adjustments (REACH/VALUE vs ADP-vs-overall-pick,
±0.10); value-gap flag (top-decile rank, ADP > 2 rounds past decile floor). Keep
P2's league-relative need + C1 scarcity as ADDITIONAL reason bits (they're still
true); score itself is autodraft's. Keep the M2.3 fallback (no my_team → plain rank).
Candidates enforce ownership (exclude drafted+active keepers; opted-out draftable).
- Impl: domain/scorer.py (market/fit/tags/gap-flag; z from pool z_* cols; per-slot edge hole/ok/covered); P2 recommend_need_aware score replaced, need+scarcity kept as reason bits; board call-site swap only. Verify: 364 passed / 1 skipped, ruff clean; review PASS (3 non-blocking nitpicks left as-is).

## 2026-10-07 — P7 — Draft Helper UI: snake grid removed; autodraft-oriented view (slim pick strip, color-coded available-players table w/ search+pos filter+Log, right recs rail top-1..20, transposed My-Team-vs-League panel, single-team roster panel w/ dropdown+not-mine flag); theme.py percentile stat-color helper (green/red/neutral, TO flipped) applied to all stat cells, light+dark
### P7 — Draft Helper UI
theme.py: percentile color helper (green/red/neutral gradient, TO flipped) used by
EVERY stat cell in the app. New draft view layout (autodraft orientation): slim pick
strip (R{r} · pick {n}/156 · {team} + search + Log + Undo); left main: available
players table (pos filter, all 9 stats color-coded, per-row Log button); right rail:
Recommendations (top-N default 10, adjustable 1–20, reasons verbatim, gap badge,
REACH/VALUE chips); transposed My-Team-vs-League panel (cats as top row; rows: My
team / League median / Gap / Tag; stats color-coded); single-team roster panel
(dropdown, default my team, "not my team" flag). Snake grid + board.py pick grid
REMOVED (pick model/persistence + undo stay — the strip drives them). Setup dialog
unchanged.
- Impl: board.py rewritten to the helper layout (grid deleted, pick model/persistence + undo + snake/keeper forfeits intact); theme.py stat-color helper (percentile-of-z, TO flipped, light+dark); relative panel transposed (cats as top row); roster panel single-team w/ dropdown + not-mine flag; recs rail top-N (settings rec_top_n, spin 1-20) w/ mkt/fit split + tag chips + verbatim reasons; available table model-based w/ search + pos filter + Log. Review fixes: dead _poolable_names removed, single tag-chip setBackground, blank z renders '' (not +0.0). Verify: every file passes individually; pre-existing offscreen combined-run 127 flake unchanged.
