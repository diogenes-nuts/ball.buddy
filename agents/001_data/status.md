# 001_data — status

Player pool: Hashtag import-v4 salvage + name bridging. "How good players are" (vs. 002_yahoo's "who is where").

## Files

- `ball_buddy/io/pool/importer.py` — salvaged verbatim from autodraft: `parse_file`, `write_csv`, `validate_rows`, FIELDNAMES (import-v4 format).
- `ball_buddy/domain/players.py` — player model over the pool CSV (`data/players.csv`).
- `ball_buddy/domain/naming.py` — name normalization + pool↔league bridging; **unmatched players are surfaced loudly** (report list, UI banner + dialog), never silently dropped.
- `ball_buddy/ui/views/pool_import.py` — import dialog + unmatched report view (tactile-cream tokens); a manual import of an inbox file records it in `inbox_state.json` (scan dedupe).
- `ball_buddy/io/pool/inbox.py` — P4 drop folder: `scan_inbox` auto-imports valid Hashtag v4 HTML from `data/inbox/` into `players.csv` (prev kept as `players.prev.csv` once per scan, per-file SHA-256 state in `inbox_state.json`, `restore_prev_pool` undo restores the pre-scan pool even for multi-file scans). Headless; UI wiring in `ui/views/league.py` (Pool row: path + Open inbox + Rescan, banner + undo, `pool_changed` signal → shell refreshes the draft board's cached pool).
- Alias support: `data/aliases.json` (manual pool-name ↔ Yahoo-name overrides).
- P5: `ball_buddy/domain/reconcile.py` — pure, name-joined Hashtag∪Yahoo pool merge: `YAHOO_POS_MAP` (Yahoo label → pool pos, unknown passes through uppercased), `yahoo_players_from_snapshot` (rosters → deduped `{name,pos,team,status}`; FA pool out of scope until auth), `make_yahoo_row` (blank-stats Yahoo row), `reconcile_pool(hashtag, existing, yahoo, aliases)` → `(rows, ReconcileReport{added,replaced,kept,orphans,summary_text})`. Hashtag wins per player (normalized-name join, aliases applied first, rank ignored); unmatched existing rows survive; Yahoo players absent everywhere are appended. Plugged into `inbox.scan_inbox` (headless → aliases empty, exact-normalized join; Yahoo side fed from the last saved `data/snapshot.json` roster via `yahoo_players_from_snapshot` — no snapshot/corrupt → empty side, no crash) and `pool_import.import_html` (alias-aware; Yahoo side fed from the live snapshot if present; summary in status label). Report wording: "N replaced, M new, K kept — orphans: …"; the per-file summary rides `ImportedEntry.note` and the League inbox banner shows it. `importer.FIELDNAMES` gained a `source` column ("Hashtag"/"Yahoo"); `validate_rows` tolerates blank stat cells (`if raw:` guards); board renders blank value as "—" like blank rank.

Plans: dev.md (P4 inbox done; P5 reconcile done). History: git log.
