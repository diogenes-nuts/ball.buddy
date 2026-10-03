# M1 Plan — Yahoo sync + pool import + offline fallback

Scope (ROADMAP M1): OAuth login, sync league/teams/draft order/schedule → local
JSON snapshot, in-app Hashtag pool import, name bridging with loud unmatched
report, stale/offline fallback. No commits (phase workflow commits).

## Decision: Yahoo library is `yfpy`, not `yffapi`

Verified against PyPI today: **`yffapi` and `pyffl` do not exist on PyPI
(404)** — SPEC §3 guessed. The real, maintained wrapper is **`yfpy` 17.0.0**
(uberfastman, pure-Python wheel, deps: requests, python-dotenv==1.1.1,
stringcase==1.2.0, yahoo-oauth==2.1.1; yahoo-oauth needs py<4.0,>=3.10 → OK on
3.14). It supports `game_code="nba"`. All API surface below was read from the
extracted wheel, not guessed.

Pin in `pyproject.toml` `[project] dependencies`: `yfpy==17.0.0` (additive; do
not touch existing pins).

## 1. Module tree additions (SPEC §3 layering: UI → services → domain → io)

```
ball_buddy/
  io/
    state.py            # salvaged atomic-write JSON (from autodraft/state.py)
    pool/
      __init__.py
      importer.py       # salvaged VERBATIM from autodraft/autodraft/importer.py
                        # (module name change only: autodraft. -> ball_buddy.io.pool.)
    yahoo/
      __init__.py
      auth.py           # token + consumer-key persistence (data/yahoo_tokens.json,
                        # data/settings.json), wraps yfpy auth inputs
      client.py         # YahooClient facade over yfpy.query.YahooFantasySportsQuery
      snapshot.py       # snapshot model <-> JSON, save/load via io.state
  domain/
    league.py           # salvaged from autodraft: config.py (LeagueConfig, loaders,
                        # validators) + league.py (Pick, snake_order, forfeited_picks).
                        # Keep code verbatim; only import paths change.
    players.py          # PlayerPool: read players.csv (csv.DictReader, FIELDNAMES
                        # from io.pool.importer), name index, get(name_key)
    naming.py           # normalize / match / MatchReport (see §5)
  services/
    sync.py             # SyncService: auth → fetch → snapshot → bridge report
                        # (headless, no Qt)
  ui/
    views/league.py     # League view (new, replaces league placeholder)
    views/pool_import.py# import dialog
```

Data dir: `data/` at repo root, **gitignored** (add `data/` to .gitignore, keep
`data/.gitkeep`). Files: `settings.json` (league_id, consumer_key/secret),
`yahoo_tokens.json`, `players.csv`, `aliases.json`, `snapshot.json`.

## 2. Yahoo calls (yfpy reality, verified from wheel source)

`YahooClient(league_id, game_code="nba")` constructs
`yfpy.query.YahooFantasySportsQuery(league_id=..., game_code="nba",
yahoo_access_token_json=<saved dict or None>, browser_callback=True,
env_var_fallback=False)`. Auth: yahoo-oauth does the 3-legged OAuth2 (browser
opens; if browser disabled it prints the URL for manual paste). After a query
succeeds, persist `query.oauth` token fields (access_token, guid,
refresh_token, token_time, token_type, consumer_key, consumer_secret) to
`data/yahoo_tokens.json` (atomic write) for next launch. Token expiry → yfpy
raises; catch in SyncService → set `needs_login` state, never crash (SPEC R2).

Fetch set for M1 (yfpy method → snapshot section):

| yfpy call | snapshot section |
|---|---|
| `get_current_user()` | `user.guid` (login proof) |
| `get_user_leagues_by_game_key("nba")` | pick the league where `league_id` matches (league name) |
| `get_league_settings()` | `league.settings` (draft_type, draft_pick_time, draft_time, season type) |
| `get_league_teams()` | `teams[]` (team_id, name, manager, logo, roster with player names/positions/slots) |
| `get_league_draft_results()` | `draft.results` (empty pre-draft — that's fine) |
| `get_league_standings()` | `standings[]` (likely empty pre-season) |
| `get_team_matchups(team_id)` for each team | `schedule[]` (dedupe: keep each (week, a, b) once; flag bye weeks) |

Draft order pre-draft: `get_league_settings()` may not expose commissioner
start order. **Manual fallback** (already in SPEC §4 002_yahoo): League view has
an editable "draft order" row (12 team names, drag-free: up/down buttons)
persisted to `data/settings.json`; `LeagueConfig` builds from snapshot order or
manual order. Salvaged `snake_order(league)` does the rest.

Snapshot serialization: every yfpy model is a `YahooFantasyObject` with
`to_json()` / `_extracted_data` — adapter maps each call result to a small
plain-dict shape (team_id, name, manager, players[{player_key, name,
positions, status}]) — do NOT dump raw `_extracted_data` wholesale (keeps the
snapshot stable against yfpy model churn, SPEC R1).

### Live-verification checklist (user runs; worker cannot)

1. `.\.venv\Scripts\pip install yfpy==17.0.0` then start app, League view →
   "Sign in to Yahoo": browser opens, code entry, app shows logged-in guid.
2. Enter league id (from the Yahoo league URL), "Sync now": 12 real teams +
   managers appear; settings (draft time/type) populated.
3. Check what pre-draft Yahoo actually returns for draft start order +
   schedule — if empty, confirm the manual-order fallback + empty-schedule
   placeholder render correctly (expected this pre-draft; record findings in
   agents/002_yahoo/done.md).
4. Import a saved Hashtag import-v4 HTML (reuse
   `N:\LLM\projects\autodraft\data\hashtag_import.html` or a fresh save):
   players loaded, matched count shown, unmatched list visible.
5. Kill network (or run with a bad token), restart app: last snapshot shows
   with a stale "last synced <ts>" banner; no crash.
6. Re-sign-in after token expiry works (delete `data/yahoo_tokens.json`,
   restart, sync).

## 3. Snapshot schema + atomic write

`data/snapshot.json`, `SNAPSHOT_VERSION = 1`, fields:

```
{version, updated_at (UTC iso), user: {guid},
 league: {key, name, settings: {...raw settings dict...}},
 teams: [{team_id, name, manager, logo_url, players:
          [{player_key, name, positions[], status, slot}]}],
 draft: {type, pick_time, time, order: [team_ids...] or null, results: [...]},
 schedule: [{week, team_a, team_b, bye: bool}],
 standings: [...],
 source: "live" | "manual-order"}
```

`io/state.py`: salvage `autodraft/state.py` — `save_state`/`load_state`
generalized to `save_json(payload, path, version)` / `load_json(path,
expected_version)` (mkstemp in same dir + `os.replace`, version check,
`StateError` on malformed). Keep `autodraft/tests/test_state.py` re-parented.
`io/yahoo/snapshot.py`: `to_snapshot(client_results) -> dict` and
`Snapshot.load(path)` raising `StaleSnapshot`-free load (load returns the dict
plus its `updated_at`; UI decides stale). Offline fallback = simply load the
file; "stale" = any age shown in banner (no hard cutoff).

## 4. Pool import in-app (Hashtag salvage)

Source format: saved Hashtag `import-v4/fantasy-basketball-projections` HTML
page (the only viable flow — Hashtag's page isn't fetchable headless; the
salvaged script documents the manual save step). Salvage
`autodraft/autodraft/importer.py` → `ball_buddy/io/pool/importer.py` unchanged
(`parse_file`, `write_csv`, `validate_rows`, FIELDNAMES). Also salvage
`autodraft/tests/test_importer.py`, `test_convert_hashtag.py`, and fixture
`autodraft/tests/fixtures/hashtag_sample.html` → `tests/fixtures/`.
`convert_hashtag.py` script itself: discard (CLI not needed; the import dialog
calls `parse_file` + `write_csv` directly).
Dialog flow: `QFileDialog.getOpenFileName` (filter `*.html`) → `parse_file` →
show warnings count + `validate_rows` warnings → `write_csv(data/players.csv)`
→ rebuild `PlayerPool` → run name bridge (§5) against the current snapshot
rosters → show match report in the dialog (matched / ambiguous / unmatched
tables).

## 5. Name bridging (001_data, risk R3 — loud, not fuzzy-only)

`domain/naming.py`:
- `normalize(name) -> str`: casefold, strip non-letters/digits/space
  (kills apostrophes/periods/hyphens: `O'Neal`, `De'Anthony`), collapse
  whitespace. Suffixes (`Jr`, `Sr`, `Ii`, `Iii`, `Iv`) split off into
  `suffix`; matching compares (base, suffix) — pool "Jokic" vs roster
  "Nikola Jokic" handled by first+last containment below.
- Match ladder, per roster player name:
  1. alias table `data/aliases.json` (`{"roster name": "pool name"}`,
     user-editable; pre-seeded `{}`) — exact roster-name key wins;
  2. exact normalized full-name hit in pool;
  3. pool name is roster name or roster name is pool name (first-name
     optional: "Nikola Jokic" ↔ "Jokic");
  4. else **unmatched** with top-3 suggestions by last-name equality.
  Two-or-more pool candidates at ladder step 3/4 → **ambiguous** (list them,
  user resolves by adding an alias entry — that's the v1 fix, no auto-pick).
- `MatchReport` dataclass: `matched: dict[roster_name, pool_name]`,
  `ambiguous: dict[roster_name, list[pool_name]]`,
  `unmatched: list[(roster_name, suggestions)]`, `pool_unused: int`.
- Loud surfacing: League view shows an ink-filled (red-on-cream via existing
  INK_FILL/TEXT_ON_INK tokens) banner `N roster players unmatched` while any
  unmatched exist; import dialog lists all three buckets; unmatched players
  must also carry a `⚠`-free text marker `UNMATCHED` in the roster table (no
  emoji per theme rules).

## 6. UI additions (tactile-cream-ui; reuse theme.py tokens only)

`ui/views/league.py` — replaces the "League" placeholder in
`ui/shell.py` `_build_stack`:
- Header row: league name (`#title`), last-synced `#secondary` label, three
  buttons right: "Sign in" (only before login), "Sync now" (`ink="true"`),
  "Import pool".
- Status banner strip (QLabel, `#panel` surface): offline/stale state or
  `Synced <time>`. Unmatched banner (ink-filled) below it when report has
  unmatched/ambiguous.
- Body (QSplitter, 3 panes, all `#panel` QWidget frames):
  1. Teams: QTableWidget — team, manager, roster size, IR (14-slot roster per
     SPEC §1.1).
  2. Draft: order list (QTableWidget: round, overall, team, status) built by
     salvaged `snake_order` from `LeagueConfig`; if no live order, an
     "edit order" mode (up/down QPushButtons per row) persisted to settings.
  3. Schedule: QTableWidget week/opponent/bye; empty-state label
     `#secondary` "No schedule yet (pre-draft)".
- Sync runs in a `QThread` (worker = `SyncService.run()`); signals:
  `finished(SyncResult)`, `failed(str)`, `login_required()`; buttons disabled
  during sync; failed message shown in banner (token expiry → "Sign in"
  reappears, R2).
`ui/views/pool_import.py` — modal QDialog: file picker button, warnings label,
result labels, unmatched QTableWidget. All colors from existing tokens; if
QTableWidget needs a style, add rules in `theme.py` using existing token
constants (SURFACE/OUTLINE/DIVIDER/TEXT_SECONDARY) — no new hex values.
`shell.py` change: only the stack construction line for "League".

## 7. pytest plan (all headless; Qt tests via QT_QPA_PLATFORM=offscreen)

- `tests/io/test_state.py` — re-parented `autodraft/tests/test_state.py`
  (adapted to generalized save_json/load_json).
- `tests/io/test_snapshot.py` — to_snapshot round-trip from a fixture results
  dict; version mismatch raises; corrupt JSON raises StateError.
- `tests/io/test_importer.py`, `tests/io/test_convert_hashtag.py` — re-parented
  verbatim (import paths); fixture `tests/fixtures/hashtag_sample.html`
  (copy from autodraft).
- `tests/domain/test_league.py` — re-parented `autodraft/tests/test_league.py`
  + config loader tests (re-parent `test_` from autodraft config coverage as
  exists).
- `tests/domain/test_naming.py` — normalization cases (O'Neal, Jr., case,
  double space), ladder steps 1–3, ambiguity, unmatched+suggestions, alias
  override.
- `tests/io/test_yahoo_client.py` — fake `YahooFantasySportsQuery` (stub
  object with the 7 methods above returning fixture dicts) injected into
  YahooClient; asserts snapshot sections; token-expiry exception → needs_login.
- `tests/services/test_sync.py` — full pipeline with fake client + real files
  in tmp_path: snapshot written, MatchReport produced from a fixture roster
  vs fixture players.csv; no-token path → loads existing snapshot (offline
  fallback).
- `tests/ui/test_league_view.py` — offscreen: LeagueView with fixture snapshot
  renders team rows; unmatched banner appears when report has unmatched;
  stale banner when no network stub.
Fixture: `tests/fixtures/snapshot_results.json` (hand-written, 2 teams is
enough for unit tests; 12-team shape covered by schema keys).

## 8. AGENTS.md changes (Info section only)

- Setup line: `pip install` adds `yfpy` (or note it's a runtime dep installed
  by `pip install -e .`/pyproject).
- Add `### Data` note: `data/` is gitignored local state (settings, tokens,
  players.csv, aliases.json, snapshot.json).
- Add `### M1 live check` block: the 6-step live-verification checklist (§2)
  as manual user steps.

## 9. Deps (verified on this machine, Python 3.14.7, venv)

New: `yfpy==17.0.0` (pure-Python wheel confirmed via pip download; transitive
pinned automatically: yahoo-oauth 2.1.1, python-dotenv 1.1.1, stringcase
1.2.0, requests 2.32.5). Nothing else. Existing pins untouched.
