# 002_yahoo — done

## 2026-10-03 — M1 — Yahoo sync + league model + pool import: yfpy 17.0.0 adapter (OAuth device flow, deferred import, LoginRequiredError), league/teams/draft-order/schedule sync to atomic-write JSON snapshot, Hashtag pool import with name bridging + unmatched report, League/Settings UI, offline fallback. 104 tests green, ruff clean, exe rebuilt.

Deliverables (spanning 001_data + 002_yahoo + 003_league; see agents/M1-plan.md for the full design):

- `io/yahoo/client.py` — yfpy facade, deferred import, `LoginRequiredError`/`YahooError`; `io/yahoo/snapshot.py` — yfpy models → stable dict shapes; `io/state.py` — salvaged atomic JSON writes.
- `domain/league.py` — league model (salvaged config/`snake_order` from autodraft), teams, draft order, schedule, manual team-order mapping.
- `domain/players.py` + `domain/naming.py` — player pool model, name normalization, bridging with explicit unmatched report.
- `io/pool/importer.py` — salvaged verbatim from autodraft (`parse_file`, `write_csv`, `validate_rows`, FIELDNAMES) + in-app import flow.
- `services/sync.py` — `SyncService`: settings, sync → snapshot, offline fallback, `save_settings`.
- UI (tactile-cream-ui, reuses `theme.py` tokens): `views/league.py` (snapshot display, stale/offline notice, SettingsDialog), `views/pool_import.py` (import + unmatched report).
- `yfpy==17.0.0` pinned in pyproject; `data/` gitignored.
- Post-review fixes: `data/` gitignore, SettingsDialog (league_id/consumer key), AGENTS.md live-check steps, manual team-order mapping fix, +2 tests.
- Verify: 104 passed / 1 skipped, ruff clean, offscreen smoke OK, PyInstaller exe rebuilt.
