# 002_yahoo — status

Yahoo adapter: the only module that talks to the Yahoo API. Real wrapper is **`yfpy==17.0.0`** (SPEC's `yffapi`/`pyffl` don't exist on PyPI — verified).

## Files

- `ball_buddy/io/yahoo/client.py` — facade over yfpy `YahooFantasySportsQuery`; deferred import (missing consumer key surfaces as `LoginRequiredError`, not yfpy's `sys.exit(1)`); lazy instance; `LoginRequiredError` / `YahooError`.
- `ball_buddy/io/yahoo/snapshot.py` — maps yfpy models to small explicit dict shapes → stable `snapshot.json` (league, teams, draft order, schedule).
- `ball_buddy/io/state.py` — salvaged atomic-write JSON (from autodraft `state.py`): tmp+rename, no torn files.
- `ball_buddy/services/sync.py` — `SyncService(data_dir)`: settings (league_id, consumer key in `data/settings.json`), `sync()` → snapshot, login-required / offline fallback to last snapshot; manual team-order support.
- Settings UI: `SettingsDialog` + button in `ball_buddy/ui/views/league.py`; `data/` is gitignored (tokens).

## Behavior

- Login: user goes League → Settings → login (yfpy 3-legged OAuth opens browser). Headless-safe: no browser → clear `LoginRequiredError` → UI shows last snapshot + stale notice.
- All non-adapter code is yfpy-free and testable with fixtures (`tests/fixtures/`).

Plans: dev.md (none active). History: git log; done.md.
