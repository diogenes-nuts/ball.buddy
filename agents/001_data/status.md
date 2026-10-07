# 001_data — status

Player pool: Hashtag import-v4 salvage + name bridging. "How good players are" (vs. 002_yahoo's "who is where").

## Files

- `ball_buddy/io/pool/importer.py` — salvaged verbatim from autodraft: `parse_file`, `write_csv`, `validate_rows`, FIELDNAMES (import-v4 format).
- `ball_buddy/domain/players.py` — player model over the pool CSV (`data/players.csv`).
- `ball_buddy/domain/naming.py` — name normalization + pool↔league bridging; **unmatched players are surfaced loudly** (report list, UI banner + dialog), never silently dropped.
- `ball_buddy/ui/views/pool_import.py` — import dialog + unmatched report view (tactile-cream tokens); a manual import of an inbox file records it in `inbox_state.json` (scan dedupe).
- `ball_buddy/io/pool/inbox.py` — P4 drop folder: `scan_inbox` auto-imports valid Hashtag v4 HTML from `data/inbox/` into `players.csv` (prev kept as `players.prev.csv` once per scan, per-file SHA-256 state in `inbox_state.json`, `restore_prev_pool` undo restores the pre-scan pool even for multi-file scans). Headless; UI wiring in `ui/views/league.py` (Pool row: path + Open inbox + Rescan, banner + undo, `pool_changed` signal → shell refreshes the draft board's cached pool).
- Alias support: `data/aliases.json` (manual pool-name ↔ Yahoo-name overrides).

Plans: dev.md (P4 inbox done; P5 reconcile next). History: git log.
