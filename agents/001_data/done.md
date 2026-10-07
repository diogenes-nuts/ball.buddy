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
