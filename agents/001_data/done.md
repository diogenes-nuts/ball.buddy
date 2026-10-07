# 001_data — done

## 2026-10-07 — P4 — Import inbox: drop-folder (data/inbox) auto-import on launch + rescan, SHA-256 dedupe in inbox_state.json, players.prev.csv per-scan undo, unparseable-file error banners, pool cache invalidation for board/recommender
### P4 — Import inbox (build now)
- Drop folder: `data/inbox/` (created on demand). Pool view shows the path + "Open
  inbox" button; existing "Import pool" file-pick stays as fallback; "Rescan inbox"
  button for mid-session drops.
- On launch: scan inbox for `.html`; track filename → SHA-256 + imported_at in
  `data/inbox_state.json` (atomic write via io/state.py). New/changed file that
  parses via the existing Hashtag importer → auto-import (write players.csv, keep
  previous as players.prev.csv) + banner "Pool updated from <file> — N players, <date>"
  with one-click undo (restore prev). Unparseable file → error banner naming it;
  file stays in inbox.
- Manual Import-pool dialog: on save, also records the file into inbox_state if it
  came from the inbox (else no-op).
- No Hashtag-login auto-pull (JS app, moving target) — user accepted drop-file flow.
- Impl: io/pool/inbox.py (scan_inbox, restore_prev_pool, in_inbox, one players.prev.csv per scan); UI wiring in ui/views/league.py (Pool row: path + Open inbox + Rescan, banner + undo, pool_changed signal); board offline branch reloads pool; manual import of an inbox file records state. Verify: 338 passed / 1 skipped, ruff clean.
## 2026-10-07 — P5 — Reconcile Hashtag ∪ Yahoo pool (pure, name-joined): source column in players.csv, yahoo snapshot→players builder, reconcile_pool with loud ReconcileReport; plugged into inbox scan (exact-normalized, headless) + manual import (alias-aware)
- `domain/reconcile.py` (pure, no I/O): `YAHOO_POS_MAP` (PG/SG/SF/PF/C identity; G→PG/SG, F→SF/PF, G/F→PG/SG/SF/PF, UTIL→UTL; unknown passes through uppercased); `yahoo_players_from_snapshot` walks snapshot team rosters, dedupes by normalized name, skips blanks (FA pool out of scope until auth — builder takes the doc so later callers append an FA list); `make_yahoo_row` (all FIELDNAMES, blank stats/rank/value/z/adp, source="Yahoo"); `reconcile_pool(hashtag, existing, yahoo, aliases)` → (rows, ReconcileReport).
- Rules: Hashtag authority — an existing row whose alias-mapped normalized name matches a Hashtag row is replaced wholesale (rank ignored); unmatched existing rows survive; every Hashtag row written (source="Hashtag"); Yahoo players absent from Hashtag+kept are appended. Join key is normalized full name; aliases ({roster:pool}) map into pool-name space before normalizing. ReconcileReport{added,replaced,kept,orphans} + summary_text() names the orphans.
- Plugs: `inbox.scan_inbox` reconciles before write (headless → aliases empty; exact-normalized only, documented in docstring; summary per file in ImportedEntry.note); `pool_import.import_html` reconciles alias-aware, summary in status label (matched/ambiguous/unmatched tables unchanged).
- `importer.py`: `source` added to FIELDNAMES after `value`; `_parse_table` stamps "Hashtag" (legacy rows default to "Hashtag" in reconcile); `validate_rows` unchanged (all stat checks are `if raw:`) — docstring notes blanks are tolerated.
- Verify: tests/domain/test_reconcile.py (fixture builder: Jokic pos "C", dedupe, blank-name skip; synthetic G/F/G-F/UTIL labels; replace-ignoring-rank; alias swap; Yahoo-only survival across repeated imports; missing-yahoo append; orphans in summary; blank rows pass validate_rows + PlayerPool.load + _parse_rank→None). Existing inbox tests seed the pool with a fixture name so the replace path keeps row counts. 348 passed / 1 skipped, ruff clean.
