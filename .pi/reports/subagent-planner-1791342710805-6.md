## Goal
Add pure, name-joined Hashtag∪Yahoo pool reconcile (new `domain/reconcile.py`), plug it into inbox scan + manual import, with a testable snapshot→yahoo-players builder and loud reporting.

## Plan
1. **`ball_buddy/io/pool/importer.py`**
   - Add `"source"` to `FIELDNAMES` (insert after `"value"`); `_parse_table`/row builders set `source="Hashtag"` (empty→Hashtag for legacy rows); `write_csv` unchanged (any rows dict).
   - `validate_rows` already tolerates blanks (all checks are `if raw:`) — no change needed; note it in docstring.
2. **New `ball_buddy/domain/reconcile.py`** (pure, no I/O)
   - `YAHOO_POS_MAP: dict[str, str]` — Yahoo label → pool pos (identity for PG/SG/SF/PF/C; "G"→"PG/SG", "F"→"SF/PF", "G/F"→"PG/SG/SF/PF", "UTIL"→"UTL"); unknown labels pass through uppercased.
   - `yahoo_players_from_snapshot(snapshot: dict) -> list[dict]` — walk `snapshot["teams"][*]["players"]`, dedupe by `normalize(name)`, emit `{"name", "pos": "/".join(map), "team": team name, "status"}`; skip blank names. (FA pool is out of scope until auth lands — builder takes the doc, so later callers append FA list.)
   - `make_yahoo_row(name, pos, team) -> dict` — all FIELDNAMES keys; stats/rank/value/z/adp blank, `source="Yahoo"`.
   - `reconcile_pool(hashtag_rows, existing_rows, yahoo_players, aliases=None) -> tuple[list[dict], ReconcileReport]`. Algorithm: (a) keep existing rows whose normalized name matches no Hashtag row (Hashtag authority replaces matches wholesale, ignoring rank — key is `normalize`d name only, aliases honored by mapping alias→pool-name before normalize); (b) append fresh Hashtag rows with `source="Hashtag"`; (c) append `make_yahoo_row` for each yahoo player whose normalized name is in neither Hashtag nor kept rows.
   - `ReconcileReport` dataclass: `added, replaced, kept, orphans: list[str], summary_text()` (e.g. "120 added, 118 replaced, 3 kept — orphans: X, Y").
   - Join helper `_name_key(name, aliases)` reused for (a)/(c).
3. **`ball_buddy/io/pool/inbox.py`** `scan_inbox`: before `write_csv(parsed.rows, pool_path)` (~L167), `existing = load_players(pool_path) if pool_path.exists() else []`; `rows, report = reconcile_pool(parsed.rows, existing, [], aliases)`; `write_csv(rows, ...)`; append `report.summary_text()` to the outcome (new `outcome.reconcile: list[str]` or per-file note) — no alias lookup in headless scan (empty dict) to stay pure-ish; document that inbox merge is name-exact.
4. **`ball_buddy/ui/views/pool_import.py`** `import_html` (L148): same swap — load existing pool, `reconcile_pool(parsed.rows, existing, [], self.service.load_aliases())`, write result; include `report.summary_text()` + orphans in `status_label` (keep existing matched/ambiguous/unmatched tables).
5. **Tests — new `tests/domain/test_reconcile.py`** (+ reuse `tests/fixtures/snapshot_results.json`):
   - builder: `yahoo_players_from_snapshot(to_snapshot(load_results(), LEAGUE_ID))` → contains Jokic with `pos` "C", dedupes, skips blank names (fixture has "Ghost Player").
   - reconcile replaces matched: existing row for "Nikola Jokic" with rank 1, Hashtag row rank 99 → result row is the Hashtag one (proves rank ignored); alias case: alias `{"Jokic": "Nikola Jokic"}` makes Hashtag "Nikola Jokic" replace existing "Jokic" row.
   - keeps yahoo-only: existing Yahoo-sourced row (blank stats) survives when absent from Hashtag; second Hashtag import still keeps it.
   - adds missing: yahoo player absent from both → appended with blank stats.
   - orphans: yahoo player matching nothing in Hashtag but present in existing kept rows reported/kept; unmatched yahoo names land in `orphans` with names in `summary_text()`.
   - blank rows pass `validate_rows` (empty warnings) and `PlayerPool.load`/recommend parse → `_parse_rank`→None.
6. **`agents/001_data/status.md`**: add P5 line (reconcile file, source column, plug-in points); dev.md P5 → done note.
7. Run `.\.venv\Scripts\pytest` + `.\.venv\Scripts\ruff check .`, fix until green.

## Files to Modify
- `ball_buddy/io/pool/importer.py` — `source` column + Hashtag stamping
- `ball_buddy/io/pool/inbox.py` — reconcile at write site
- `ball_buddy/ui/views/pool_import.py` — reconcile at write site + summary in status
- `agents/001_data/status.md`, `agents/001_data/dev.md` — doc updates

## New Files
- `ball_buddy/domain/reconcile.py` — map, builder, row factory, `reconcile_pool`, `ReconcileReport`
- `tests/domain/test_reconcile.py` — tests above

## Risks
- Fixture `positions` already use pool grammar ("PG","C"), so map coverage is untested by fixture — add a synthetic-doc test for "G"/"UTIL".
- Alias direction is roster→pool; reconcile joins Hashtag→existing, so map alias values into pool-name space first.
- `validate_rows` change-free relies on current `if raw:` checks — add the blank-row test to lock that in.
- Inbox scan keeps aliases empty (headless); merge there is exact-normalized only — document in `scan_inbox` docstring so nobody expects alias-aware inbox merges.