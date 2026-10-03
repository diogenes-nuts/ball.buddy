## M1 Verification: PASS overall (1 critical doc/guard gap, rest nits)

**1. Tests/lint — PASS.** `pytest`: `102 passed, 1 skipped in 0.50s`; `ruff check .`: `All checks passed!` (skip = full Hashtag export test, gated on `data/hashtag_import.html` not existing).

**2. Yahoo adapter — PASS.** `ball_buddy/io/yahoo/client.py` genuinely wraps `yfpy.query.YahooFantasySportsQuery` (lazy import, `game_code="nba"`, `from_settings` maps yfpy's `sys.exit(1)` → `LoginRequiredError`). PyPI claim verified: `pip index versions yffapi` / `pyffl` → `No matching distribution found`. Degradation verified in code + tests: `services/sync.py:run()` catches `LoginRequiredError`→`needs_login`, `YahooError`→`error`, keeps `_age()`; `tests/services/test_sync.py` covers no-creds (l.75), token-expiry (l.84), network-failure-keeps-old-snapshot (l.100), corrupt snapshot (l.156) — all pass.

**3. Snapshot persistence — PASS.** `io/state.py` is a faithful generalization of `.salvage/state.py` (diff: mkstemp-same-dir + `os.replace` + version check intact, generalized to `save_json/load_json`); atomicity test l.23. Offline fallback: offscreen test `tests/ui/test_league_view.py:121` renders "last synced"/"showing last snapshot" banner — passes.

**4. Pool import + bridging — PASS.** Ran real fixture headlessly: 3 players parsed, `bridge("Nikola Jokic",…)` matched, unknown player → unmatched with suggestions. `ui/views/pool_import.py:106-141` fills matched/ambiguous/unmatched tables + status counts; `league.py:90-93,236-241` shows ink-filled `banner-alert` "N roster players unmatched". Not silent.

**5. Theme — PASS.** `league.py`/`pool_import.py` contain zero raw hex; only objectNames (`banner`, `banner-alert`, `panel`, `title`, `secondary`). New `theme.py` rules (l.135-172) use only existing token constants (INK_FILL/TEXT_ON_INK/SUNKEN/SURFACE/DIVIDER).

**6. autodraft — PASS (caveat).** `git status`: zero modified tracked files; untracked `agents/*/done.md` + `.pi/` exist (timestamps predate this session; note for worker).

**7. Git — PASS.** `git log`: only 3 commits (M0 phase + 2 pre-M0); all M1 work uncommitted, awaiting phase commit.

**8. Pin — PASS.** `pyproject.toml:12` `"yfpy==17.0.0"`; installed `yfpy 17.0.0`.

### Defects
1. **Critical-ish (guard gap): `data/` NOT gitignored.** Plan §1 explicitly required it; `.gitignore` diff adds only `.salvage/`. `data/yahoo_tokens.json` (consumer secret + OAuth token) would be swept into the auto phase-commit after the user's live login. Fix: add `data/` to `.gitignore`.
2. `ball_buddy/ui/views/league.py:380-395` — no way in UI to enter league_id/consumer_key; user must hand-write `data/settings.json` (plan's live-checklist step 2 "enter league id" is impossible as written). Fix: settings fields or documented manual step.
3. `AGENTS.md` — plan §8 unimplemented: no yfpy in setup line, no `Data` note, no M1 live-checklist block.
4. `ball_buddy/ui/views/league.py:277-280` — when `manual_draft_order` exists, `names_in_order = list(team_names)` ignores the saved manual order (only saved after first sync anyway). Fix: map manual order names into the start order.
5. Nit: empty junk dir `%temp%pipcheck/` in repo root (from pip check); nit: no `UNMATCHED` per-row marker in roster table (plan §5) — roster isn't per-player table, banner+dialog cover it.

### User live-verification checklist (sanity-checked)
1. **Login:** start app → League → "Sign in to Yahoo" → browser OAuth → then press **Sync now** (login alone only constructs the client; token persists after a *successful* sync via `persist_token`, client.py:129).
2. **First sync:** pre-req you must do first: hand-create `data/settings.json` = `{"version":1,"league_id":"<id from Yahoo URL>","consumer_key":"...","consumer_secret":"..."}` (see defect 2). Expect 12 teams + settings populated; pre-draft order/schedule may be empty → up/down manual order + "No schedule yet" placeholder should render.
3. **Pool import:** League → "Import pool" → pick `N:\LLM\projects\autodraft\data\hashtag_import.html` (exists, 2.3MB) → expect matched/ambiguous/unmatched tables; add aliases to `data/aliases.json` for ambiguous.
4. **Offline fallback:** delete `data/yahoo_tokens.json` (or kill network) → restart → League shows "Offline — showing last snapshot (synced <age>)" banner, no crash.
5. Note: do this **before** any exit/commit, and only after defect 1 is fixed (tokens would otherwise get committed).