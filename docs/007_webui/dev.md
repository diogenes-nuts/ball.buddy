# 007_webui — dev

## Plan: M8 — Electron + Web UI migration (2026-10-15)

Context: user wants better styling/layout control, Electron or Tauri. Assessment: the
Python core (`domain/`, `io/`, `services/`, ~3,300 lines) is UI-agnostic — the UI drives
`SyncService` from a QThread, no Qt in core. `ui/` (~4,000 lines) is 100% Qt. 26 of 54
test files touch Qt (view tests).

User decisions (2026-10-15):

- **Electron** (not Tauri): one language for the new stack, trivial sidecar spawn from
  Node, no Rust; 100MB install accepted ("double-click the exe" is paramount).
- **Keep the Python core** behind an API (sidecar), no TypeScript rewrite of the logic.
- **Vanilla TypeScript** frontend (Vite build, no framework) — six data views are DOM
  tables, not component trees.
- **FastAPI + uvicorn** sidecar server.
- **Drop the clipboard-paste OAuth fallback** — keep the loopback redirect path
  (`begin_sign_in` local https callback server already exists in
  `ball_buddy/io/yahoo/oauth.py:29`); sign-in UI waits on the callback, no paste field.
  (No loopback server to build — it exists.)
- **Pure port**: same 6 views, same features, same offline snapshot banner. Tinkering
  with looks, not behavior.
- **Packaging unchanged in shape**: onedir `dist\ball.buddy\ball.buddy.exe`, same
  gitignored `dist\` flow, same `dist/data` move-aside-then-restore rebuild rule.
- **Style re-orientation**: discard ALL prior style decisions (QSS, `theme.py` palette
  work, tactile-cream-ui tokens.json, stat_color QSS workarounds). Single source of
  truth: the `app-ui-design` skill + its `tokens.css` (copied verbatim into the
  frontend). Light default, `data-theme` override + `prefers-color-scheme`.

Principle: the Python core never changes behavior. We wrap it in an API server,
replace `ui/` with Electron + TS, delete PySide6 once parity is proven. The old
`ball_buddy/` stays intact until Phase 5.

## Phases

### Phase 0 — Prep

- Tag the current working build (`v1-pyside`); it is the parity reference.
- Install Node 22 LTS + npm. `.gitignore`: `frontend/dist`, `frontend/node_modules`,
  `dist-electron`.
- `pyproject.toml` pins: add `fastapi`, `uvicorn` (newest Py-3.14-resolvable, exact
  pins, same discipline as the existing pins).

### Phase 1 — API server (Python)

New `server/` package (FastAPI + uvicorn, one process, spawned by Electron):

- `GET /api/state` — full app state as JSON: settings, snapshot (or manual fallback),
  teams, pool rows, picks, keepers, schedule, logged_in flag, snapshot age. Frontend
  loads once, then patches via WS events.
- `POST /api/actions/*` — thin verbs that call the same `SyncService` / domain
  functions the Qt views call today: `sync_now`, `import_pool` (file path in →
  matched/ambiguous/unmatched out), `log_pick`, `undo_pick`, `save_lineup`,
  `save_manual_order`, `save_keepers`, `sign_in`, `cancel_sign_in`, `reset_data`,
  `put_settings` (incl. `dark_mode`).
- `WS /ws` — events: sync progress lines, sync done/error, `signed_in`, `state_changed`.
  Draft board's "sync every 30s + progress banner" becomes a server-push loop.
- Sign-in: `POST /api/actions/sign_in` → `begin_sign_in` (existing loopback server) →
  `webbrowser.open` (system browser, unchanged) → WS `signed_in` when the callback
  lands. Token persists only after a successful sync — keep that rule.
- Long actions (sync) run in a background task; the old QThread pattern moves into the
  server, not the frontend.
- Tests: `tests/api/` via FastAPI `TestClient`; the 28 non-Qt test files stay green
  untouched.

Exit: API tests green; a curl/`TestClient` walk hits every action the views need.

### Phase 2 — Electron shell

- `electron/main.ts`: single-instance lock → spawn sidecar (`core_server.exe`,
  PyInstaller one-file) with a random free port on argv → poll `/api/health` →
  `BrowserWindow` loads `frontend/dist/index.html`. Kill sidecar on quit.
- Dev mode: `npm run dev` = uvicorn in-process + Vite dev server + HMR.
- `ball_buddy/pathing.py` frozen-data-dir logic unchanged (the sidecar is the frozen
  process — `resolve_data_dir()` already handles exe-adjacent `data/`).

Exit: dev shell shows a blank page talking to the real server; prod shell spawns the
sidecar exe.

### Phase 3 — Frontend foundation

Vite + vanilla TS, no framework, no CSS-in-JS. `frontend/src/`:

- `tokens.css` — copied verbatim from the `app-ui-design` skill (the single style
  source; no other palette constants exist in the codebase).
- `app.ts`, `store.ts` (state + WS subscription + optimistic updates), `api.ts`,
  one `views/*.ts` per page, `components/table.ts` primitive.
- App shell per the skill: glass left sidebar (app mark, league id, 6 nav items,
  dark-mode checkbox in footer, version), `--gap-module` content grid, top banner
  slot (offline banner, danger alerts).
- Theme: `data-theme` on `<html>`, persisted via `settings["dark_mode"]`; default
  follows `prefers-color-scheme`.
- Table primitive encodes the skill rules: hairline `--rule` rows, no vertical
  gridlines, mono tabular right-aligned numbers, sticky muted header, row height by
  visible row count (48/40/34px), hover tint, accent-tint selected row + 2px leading
  marker.
- `stat_color` port: pure TS function mirroring
  `ball_buddy/ui/theme.py::stat_color` (percentile via normal CDF; 45–55th band
  uncolored; lerp pale-tint → endpoint). Parity test: sampled inputs → expected
  class/band. Endpoint values re-derived from `tokens.css` status colors per theme
  (the old `_STAT_ENDPOINTS` were QSS-specific; in CSS the tints come straight from
  `--success`/`--danger` at low opacity — re-check readability on both themes and
  record any deviation in status.md per the skill's process rule).

Exit: shell + sidebar + theme toggle + one sample data table, both themes, passing
`prefers-reduced-motion`.

### Phase 4 — Port the 6 views (one per step; each verified before the next)

1. **League** — settings form, Sign in (wait-on-callback spinner, **no paste field** —
   fallback dropped), Sync now, pool import tables (matched/ambiguous/unmatched),
   reset-data confirm.
2. **Draft board** — the big one. Current-pick strip + name-search dropdown (left);
   available-players table (client-side sort/filter — hundreds of rows are fine in
   DOM); right rail: Recommendations → Comparison → Roster, stat-colored cells via
   the ported function. Sort semantics must match the old model (parsed float,
   missing values last in both directions). Optimistic pick/undo (client copies state,
   server confirms).
3. **Lineup** — start/sit optimizer output table.
4. **Matchup** — win-prob + seed table.
5. **Waivers** — ranked list + reasons.
6. **Trades** — offer builder + ΔP per side.

Rule: all ranking/recommendation math stays in Python (engine/advisor/scorer); the
frontend renders, never recomputes.

Exit: every view renders from `/api/state` + action calls; both themes.

### Phase 5 — Parity check + deletion

- Side-by-side run vs the `v1-pyside` build; walk every view + offline banner path
  (delete `data/yahoo_tokens.json`, restart → banner, no crash).
- Delete: `ball_buddy/ui/` (~4,000 lines), `ball_buddy/main.py`, PySide6 + pytest-qt
  from `pyproject.toml`, `scripts/make_icon.py` Qt offscreen render (replace with a
  static SVG app mark → `assets/icon.ico` via a small dependency-free script), the 26
  Qt view test files (replaced by view tests in `tests/` for the frontend where
  practical; core action coverage is already in `tests/api/`).
- `server/main.py` becomes the Python entry.

Exit: zero `PySide6` references in the repo; full test suite green; the combined-
`pytest` offscreen flake is gone with Qt.

### Phase 6 — Packaging

- Two PyInstaller builds: `core_server.exe` (one-file sidecar) + `ball.buddy.exe`
  (Electron, onedir, `assets/icon.ico`).
- `ball.buddy.exe` in `dist\ball.buddy\` launches the sidecar from the same dir —
  same "double-click the exe" surface; same `dist\` lock rule (close the app before
  rebuild; `pyinstaller -y` wipes `dist\` → move `dist/data` aside, restore after).
- README rewritten (new build/run commands, SmartScreen note for the unsigned
  sidecar, loopback sign-in instead of paste). AGENTS.md Build/Run/Test/Environment
  sections updated (Node 22 pin, `npm run` commands, new venv deps).

Exit: fresh-clone build produces a working `dist\ball.buddy\ball.buddy.exe`.

## Risks

- **Stat-color parity** — the one presentation-logic piece that must look right;
  mitigated by the parity test (Phase 3) + a screenshot review.
- **Draft-day latency** — WS on localhost is fine, but the board keeps a client-side
  state copy so pick/undo feel instant (optimistic update, server confirms).
- **SmartScreen** on first unsigned run — accepted for a friend-facing local tool
  (README note).
- **Version churn** — pin `package.json` exactly, like the Python pins.
- **Pool-table size** — hundreds of rows in a DOM `<table>` is fine; if it ever gets
  slow, the table primitive is the only place to add windowing.
