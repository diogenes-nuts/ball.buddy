# 001_data — dev

(no active plans)

## Plan: Projection inbox + pool reconciliation (2026-10-06)

Context: user's projection source is a saved Hashtag import-v4 page (top-200 only,
e.g. repo-root import.html). Hashtag updates rankings regularly → automate refresh.
Yahoo pool (sub-200 players) arrives only when/after auth lands; reconcile by NAME
(user: Yahoo ranks ≠ Hashtag ranks — never join on rank; rank column is always the
Hashtag rank when present, None for Yahoo-appended rows).

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

### P5 — Reconcile Hashtag ∪ Yahoo (logic now, live when auth lands)
- Hashtag is projection authority: on Hashtag import, bridged-matched names are
  REPLACED with fresh rows (name join via naming + aliases.json — never rank).
- Yahoo rows survive: sync (when auth works) appends known players (rosters + FA
  pool) absent from the pool — name/pos/team, blank stats, rank None, value blank
  (UI "—", engine zeros). Later Hashtag imports MERGE: Hashtag wins on matches,
  Yahoo rows kept, nothing silently deleted.
- Loud reporting: added/replaced/kept-orphan counts + orphans in the existing
  unmatched report. Test against a mock Yahoo doc (offline).
