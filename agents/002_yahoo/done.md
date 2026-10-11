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

## 2026-10-11 — R2 — R2: signal-based error classifier (401→login, 403/generic→YahooError, narrow phrase list), fetch_all per-team minimum documented (no per-week loop), _settings_of getattr allowlist + snapshot warnings key, OAuthError→LoginRequiredError in _live_tokens, persist_token missing-refresh_token warning into SyncResult, README/AGENTS docs; exe rebuilt

From agents/REVIEW-FIXES.md R2 (owner-decisions from cross-exam baked in: R2.2 became doc-only).

- `io/yahoo/client.py _call` — the old substring classifier `("token","oauth","auth","401","403")` mislabeled private-league authorization errors as "sign in again". Now: requests.HTTPError with `.response` → 401 = `LoginRequiredError` (yfpy auto-refreshes 401s internally, so an escaped 401 means the token is dead), else `YahooError` (a `.response`-less HTTPError is yfpy's 999 rate-limit — `YahooError`); narrow phrase list ("invalid_grant", "invalid token", "token expired", "access token") → `LoginRequiredError`; everything else `YahooError`; the app-ban 403 message check keeps precedence. Scout: the `yahoo_oauth` package is NOT installed — OAuth is in-app (`oauth.py`, `OAuthError(RuntimeError)`); yfpy raises HTTPError-with-response via raise_for_status + bare HTTPError for the 999 case + `YahooFantasySportsDataNotFound`.
- `client.py fetch_all` (R2.2, doc-only) — per-team `get_team_matchups` (12 full-season calls/sync) recorded as the verified minimum-call shape in the docstring; the per-week league fan-out (17–20 calls) is lossy (drops playoff rows) — explicitly NOT implemented.
- `io/yahoo/snapshot.py _settings_of` — getattr allowlist (`draft_type`, `draft_pick_time`, `draft_time`, `waiver_type` — the fields the app consumes) instead of yfpy's private `_extracted_data` dump; when the private attr is absent, a warning is appended to the snapshot doc's new additive `warnings: []` key (old snapshots safe; `.get("warnings") or []`). `settings is None` still early-returns `{}` (accepted per plan).
- `services/sync.py _live_tokens` — `oauth.OAuthError` (plain RuntimeError) no longer escapes to "unexpected sync error": caught, re-raised as `LoginRequiredError("Yahoo sign-in expired — sign in again")`. Regression test: a failed refresh leaves the saved token file UNCHANGED (refresh-then-save order) + needs_login.
- `client.py persist_token` — missing token fields (no `refresh_token`) no longer silently skip persistence: optional `warnings` list param; `sync.run` threads snapshot + persist warnings into `SyncResult.extra["warnings"]`.
- UI surface (bookkept under 003_league R2): League ok-banner appends the warnings after "Synced just now." (4 lines, theme tokens, `result.extra.get("warnings") or []`).
- Docs: README sign-in step — `oauth_cert.pem`/`oauth_key.pem` are local-only self-signed loopback keys; AGENTS.md M1 live-check step 5 — post-R2 manual re-run (sign-in → sync → offline fallback).
- Verify: tests/io 95+1 skipped, tests/services 15, test_league_view 16, ruff clean; exe rebuilt (5.74MB). Pending: user manual live check (AGENTS.md step 5) — note the live league fetch is still behind the app-authorization 403 wall (see status), so the check may only exercise sign-in + offline fallback.
