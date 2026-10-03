# 001_data — status

Player pool: Hashtag import-v4 salvage + name bridging. "How good players are" (vs. 002_yahoo's "who is where").

## Files

- `ball_buddy/io/pool/importer.py` — salvaged verbatim from autodraft: `parse_file`, `write_csv`, `validate_rows`, FIELDNAMES (import-v4 format).
- `ball_buddy/domain/players.py` — player model over the pool CSV (`data/players.csv`).
- `ball_buddy/domain/naming.py` — name normalization + pool↔league bridging; **unmatched players are surfaced loudly** (report list, UI banner + dialog), never silently dropped.
- `ball_buddy/ui/views/pool_import.py` — import dialog + unmatched report view (tactile-cream tokens).
- Alias support: `data/aliases.json` (manual pool-name ↔ Yahoo-name overrides).

Plans: dev.md (none active). History: git log.
