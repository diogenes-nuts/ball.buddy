# 001_data — dev

(no active plans)

## Plan: Projection inbox + pool reconciliation (2026-10-06)

Context: user's projection source is a saved Hashtag import-v4 page (top-200 only,
e.g. repo-root import.html). Hashtag updates rankings regularly → automate refresh.
Yahoo pool (sub-200 players) arrives only when/after auth lands; reconcile by NAME
(user: Yahoo ranks ≠ Hashtag ranks — never join on rank; rank column is always the
Hashtag rank when present, None for Yahoo-appended rows).

### P5 — Reconcile Hashtag ∪ Yahoo (logic now, live when auth lands) — DONE

Implemented as specified: pure merge in `ball_buddy/domain/reconcile.py`
(Hashtag wins per player on the normalized-name join, aliases applied first,
rank ignored; unmatched existing rows kept; Yahoo players absent everywhere
appended via `make_yahoo_row`; `ReconcileReport` carries added/replaced/kept
plus an `orphans` list surfaced in `summary_text()`). Wired into
`inbox.scan_inbox` (headless: aliases empty, exact-normalized join — see its
docstring; Yahoo side from the last saved `snapshot.json` roster) and
`pool_import.import_html` (alias-aware; Yahoo side from the live snapshot if
present; summary in the status label, also surfaced in the League inbox
banner via `ImportedEntry.note`). `importer.FIELDNAMES` gained `source`;
FA pool stays out of scope until auth. Tests: `tests/domain/test_reconcile.py` (builder + synthetic
G/F/G-F/UTIL label map, replace/alias/keep/add/orphan/blank-stats cases).
- Hashtag is projection authority: on Hashtag import, bridged-matched names are
  REPLACED with fresh rows (name join via naming + aliases.json — never rank).
- Yahoo rows survive: sync (when auth works) appends known players (rosters + FA
  pool) absent from the pool — name/pos/team, blank stats, rank None, value blank
  (UI "—", engine zeros). Later Hashtag imports MERGE: Hashtag wins on matches,
  Yahoo rows kept, nothing silently deleted.
- Loud reporting: added/replaced/kept-orphan counts + orphans in the existing
  unmatched report. Test against a mock Yahoo doc (offline).
