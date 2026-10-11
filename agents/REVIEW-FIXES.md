# REVIEW-FIXES — code-review remediation plan (2026-10-14)

Source: full-repo code review (2026-10-14), findings audited with line numbers.
Scope: every module under `ball_buddy/`. No implementation has started; this
file is the master plan. Per-component bookkeeping lives in each component's
`dev.md` stub ("Review remediation R1–R6").

## Ground rules (every phase)

- Per-directory pytest runs (`tests/ui/*.py`, `tests/domain`, `tests/io`,
  `tests/services` each pass individually) — the combined Qt-views run
  hard-kills (pre-existing env flake). Ruff clean.
- **Rebuild the exe after every code change** (AGENTS.md policy): move
  `dist/data` aside, `pyinstaller -y`, restore `dist/data`.
- `phase_complete` per affected component with the shared phase id
  (`R1`…`R6`) — no manual commits.
- UI-touching phases get a screenshot/visual check when the user can provide
  one; Yahoo-behavior phases (R2) need the manual live check (user runs the
  app) because OAuth cannot be exercised from tests.

## Phase map

| Phase | Title | Components | Risk |
|---|---|---|---|
| R1 | Correctness bugs (cross-view) | scaffold, 003_league, 004_engine, 006_board | low |
| R2 | Yahoo error handling + snapshot robustness | 002_yahoo | medium (live Yahoo check needed) |
| R3 | Shared roster resolver + view constants (refactor) | 005_advisor, 004_engine, 006_board, 001_data, 003_league | low (pure refactor) |
| R4 | Structured Suggestion fields + scorer fix | 006_board | low |
| R5 | Caching + performance | 002_yahoo, 006_board, 001_data, (005_advisor optional) | medium (invalidation bugs are subtle) |
| R6 | Dead code, minor cleanups, repo hygiene | 001_data, 005_advisor, 004_engine, scaffold | trivial |

Order: R1 → R2 → R3 → R4 → R5 → R6. R3 must precede R5 (the cache lives in
the shared resolver). R4 is independent of R3 but sequenced after it to keep
each phase's diff small.

---

## R1 — Correctness bugs (cross-view)

Goal: fix the six verified bugs without touching structure.

1. **`main.py:49` — crash dialog never shows.** `QMessageBox.critical(
   "ball.buddy", title, text)` passes a str as the *parent widget* →
   `TypeError`, swallowed by the surrounding `except Exception: pass`.
   Change to `QMessageBox.critical(None, ...)`. Add a test that installs the
   hook and asserts the message-box construction is attempted with a
   `(None|QApplication, str, str)` signature (patch `QMessageBox.critical`
   in `tests/test_excepthook.py`; also assert the hook still re-raises via
   `default_hook`).
2. **`ui/views/league.py:541` — other teams' byes render in team 1's
   schedule.** Filter `first_team in (a, b) or entry.get("bye")` matches
   every bye row (bye entries carry `team_a=<bye team>`, `team_b=""`).
   Fix: include a bye row only when `entry.get("team_a") == first_team`.
   Test in `tests/ui/test_league_view.py`: schedule with a bye for team 2 →
   team 1's pane must not show it.
3. **`domain/keepers.py:93` — same team keeping the same player twice is
   accepted.** Dedupe only fires cross-team (`first_team != entry.team`).
   Track `(resolved_key, team)` pairs; a repeat is an error ("{team!r} keeps
   {player!r} twice"). Note: the same player on two *different* teams must
   keep erroring as today. Tests in `tests/domain/test_keepers.py` (both
   cases).
4. **13 vs 14 draft rounds.** `domain/picks.py:26` `DRAFT_ROUNDS = 13`
   (aliased to `keepers.MAX_COST_ROUND`) vs `ui/views/league.py:41`
   `DRAFT_ROUNDS = 14`. The board's snake and the League view's rendered
   snake disagree, so pick numbering / `current_pick` / "overall" diverge
   between pages. Fix: define `DRAFT_ROUNDS = 14` (SPEC §1.1 roster size) in
   ONE place — `domain/league.py` next to the snake code — and have
   `domain/picks.py` and `ui/views/league.py` import it. `keepers.
   MAX_COST_ROUND = 13` stays as the keeper-cost cap (a 14-round roster can
   still have keeper costs in 1..13 since round 14 is the last pick; keep
   the existing keeper-validation bound and note it in the docstring).
   Tests: `tests/domain/test_picks.py` + `tests/ui/test_league_view.py` +
   `tests/ui/test_board.py` assert 14-round snakes on both surfaces.
5. **`ui/views/matchup.py:456-457` — side attribution by value equality.**
   `side = "A" if player in players_a` mislabels an identical player
   (same name + stats) appearing on both rosters as "A". Build the rows with
   the side carried explicitly (`for side, players in (("A", players_a),
   ("B", players_b)): for player in players: ...`) instead of membership
   tests. Test in `tests/ui/test_matchup_view.py`: identical player on both
   sides renders one "A" row and one "B" row.
6. **`ui/views/board.py:308-316` — `_parse_z` returns 0.0 for unparseable
   cells.** Contradicts `_row_sort_key`'s "unparseable is unknown, not zero"
   contract (only blank → None). Change `except ValueError: return None`
   so garbled cells render empty and sort last. Audit the two call sites
   (`board.py:171` sort key — already treats None as unknown; `board.py:209`
   and `:1097` display — None renders as ""). Tests in `tests/ui/
   test_board.py`: a pool row with `z_pts="abc"` renders empty and sorts
   after numeric rows in both directions.

Acceptance: all six fixes green per-directory; ruff clean; exe rebuilt.
Bookkeeping: scaffold + 003_league + 004_engine + 006_board status.md updates;
phase_complete per component.

## R2 — Yahoo error handling + snapshot robustness (002_yahoo)

Goal: stop misleading users about auth failures; cut per-sync API calls;
remove private-attribute dependence.

1. **`io/yahoo/client.py:162` — classifier too broad.** After the existing
   "application is not authorized" app-ban check, the substring test
   `("token","oauth","auth","401","403")` maps e.g. private-league
   authorization errors to "sign in again". Rework `_call` to classify on
   signal, not substrings:
   - `requests.HTTPError` → status 401 → `LoginRequiredError`; 403 →
     `YahooError` (unless the app-ban message, already handled); else
     `YahooError`.
   - yahoo-oauth's own auth exceptions (`oauth2` errors, "invalid_grant",
     "token expired") → `LoginRequiredError` — keep a narrow keyword list
     for those specific phrases only (`invalid_grant`, `token_expired`,
     `access token`), drop the bare words `"auth"`, `"403"`.
   - Everything else stays `YahooError`.
   Design the exact mapping against what yahoo_oauth 2.1.1 actually raises
   (scout the installed package source first). Tests in
   `tests/io/test_yahoo_client.py`: each class of raised exception maps to
   the right error type and message.
2. **`io/yahoo/client.py:173` — one `get_team_matchups` per team** (12+
   calls per sync; rate-limit prone). Scout yfpy's API for a league-level
   variant (`get_league_matchups_by_week(week)` or similar) and pick the
   minimum-call shape that still yields the full-season schedule the
   snapshot dedupe expects (`snapshot._schedule_from_matchups` is unchanged
   — it already dedupes by (week, pair)). If yfpy only offers per-week
   league calls, loop weeks 1..playoff-start (still ≤ ~17 calls, and no
   per-team fan-out); document the chosen shape in the docstring. Tests:
   existing `tests/io/test_yahoo_client.py` fetch_all test updated to the
   new call pattern with a fake query.
3. **`io/yahoo/snapshot.py:143` — `_settings_of` reads yfpy's private
   `_extracted_data`.** Extract an explicit allowlist of fields
   (`draft_type`, `draft_pick_time`, `draft_time`, and whatever the League
   view consumes) via getattr with defaults; when the private attr is
   absent/changed, log a warning into the snapshot's warnings channel
   instead of silently returning `{}`. Tests in `tests/io/test_snapshot.py`:
   a settings stub without `_extracted_data` produces an empty settings dict
   + a surfaced warning, not a crash.
4. **`services/sync.py` — refresh `OAuthError` leaks as "unexpected sync
   error".** `_live_tokens` lets `oauth.OAuthError` (plain RuntimeError)
   escape `_build_client`; `SyncService.run` only catches
   `LoginRequiredError`/`YahooError`. Catch `OAuthError` in `_live_tokens`
   and re-raise as `LoginRequiredError("Yahoo sign-in expired — sign in
   again")` so the UI's needs_login path handles it. Verify the old token
   file is NOT overwritten on refresh failure (current order is
   refresh-then-save, so it is safe — add a regression test asserting the
   saved tokens survive a failed refresh). Tests in
   `tests/services/test_sync.py`.
5. **`io/yahoo/client.py persist_token` — silent non-persistence.** If
   `refresh_token` is missing, `all(_TOKEN_FIELDS)` fails and the token is
   never saved with zero feedback. Return/save a note: raise nothing, but
   append a warning to the SyncResult (thread it through `run()`) —
   "token not persisted: Yahoo returned no refresh_token" — so the user
   knows every launch will re-run sign-in. Test in
   `tests/io/test_yahoo_client.py`.
6. **Docs:** README (friend-facing) gets one line about
   `data/oauth_key.pem` being a local-only self-signed key used for the
   localhost callback (safety note from the review; behavior unchanged).
   AGENTS.md M1 live-check gains step: after R2, re-run sign-in → sync →
   offline fallback once against the real league (user runs it).

Acceptance: per-directory tests green; ruff clean; exe rebuilt; user's
manual live check passes (sign in, sync, kill token file, restart → offline
banner). Bookkeeping: 002_yahoo status.md + dev.md/done.md updates.

## R3 — Shared roster resolver + view constants (pure refactor)

Goal: one implementation of the keepers+picks→pool resolution used by four
views; shared display constants; small naming/league cleanups. No behavior
change.

1. **New `ball_buddy/ui/views/_roster.py`** with
   `team_roster_rows(service, team_name) -> tuple[list[dict[str,str]],
   list[str]]` (rows + unresolvable names) and a thin
   `team_roster_names(...)` wrapper returning `(names, missing)`. Body =
   today's `MatchupView._load_team_data` core verbatim (the most complete
   variant). Replace the four copies:
   - `ui/views/matchup.py:357` `_load_team_data` → delegate to the module
     (keep the method as a one-line wrapper so existing call sites/tests
     don't churn).
   - `ui/views/waivers.py:60` `_team_roster_names` → delete, import.
   - `ui/views/trades.py:69` `_team_roster_names` → delete, import.
   - `ui/views/lineups.py:78` `_team_roster_rows` → delete, import.
   Tests: existing view tests must stay green unchanged (they exercise the
   seam); add one direct unit test for `_roster` (dedupe order kept,
   missing list, empty team name) in a new `tests/ui/test_roster.py`.
2. **New `ball_buddy/ui/views/_common.py`**: move `CAT_LABELS` (from
   `matchup.py`) and `_fmt_gap` (duplicated in matchup.py, lineups.py,
   trades.py) there; update imports in `board.py:80`, `lineups.py:54`,
   `trades.py:53`, `waivers.py:49`, `matchup.py`. Keep
   `matchup.CAT_LABELS` as a re-export alias for one release cycle so any
   stray import keeps working (drop the alias in the same phase once grep
   shows no remaining users — both steps land together).
3. **`domain/naming.py:140` — `_suggest`'s `pool_norm_all` param** always
   receives the same dict as `pool_norm`; drop the parameter and its
   second loop source. Internal-only signature (leading underscore).
4. **`domain/league.py`** — merge the two module docstrings into one
   (top-of-file), and note in the docstring that `DRAFT_ROUNDS` (from R1)
   now lives here.
5. **`ui/views/league.py:671` — move `__all__`** to the bottom after
   `SignInDialog`/`_SignInExchangeWorker` (pure placement fix).

Acceptance: all view tests green per-directory; ruff clean; grep shows a
single roster-resolution implementation and a single CAT_LABELS definition;
exe rebuilt. Bookkeeping: 005_advisor + 004_engine + 006_board + 001_data +
003_league status.md updates (file lists change).

## R4 — Structured Suggestion fields + scorer fix (006_board)

Goal: stop parsing human strings as data; fix the O(n²) wart.

1. **`domain/recommend.py Suggestion`** gains `market: float | None = None`
   and `fit_norm: float | None = None`. `scorer.score_pool` populates both
   (market stays None for unranked rows; fit_norm None only when the fit
   range is degenerate). The M2.3 fallback path leaves them None — UI shows
   the em dash, same as today.
2. **`ui/views/board.py:975-986 _mkfit`** reads the new fields instead of
   `_MKT_RE`/`_FIT_RE`; delete the two regexes and the "reason-string as
   API" comment. `reason` strings themselves are unchanged (they remain the
   human-readable record).
3. **`domain/scorer.py:192-194`** — hoist `top_rank = max(r.rank for r in
   decile)` out of the per-row generator in `_gap_names` (O(n²) → O(n));
   behavior identical, covered by the existing `_gap_names` cases in
   `tests/domain/test_scorer.py` (add one asymmetric-decile case if missing).

Acceptance: `tests/domain/test_recommend.py` + `tests/domain/test_scorer.py`
+ `tests/ui/test_board.py` green per-directory; ruff clean; the rail renders
identically (screenshot check when available); exe rebuilt.

## R5 — Caching + performance

Goal: remove redundant I/O and recompute without changing any result.

1. **`services/sync.py` — cached `load_last`.** Add
   `load_last_cached()` that memoizes the parsed snapshot + bridge report
   keyed on the mtimes of `snapshot.json` and `players.csv` (re-bridge only
   when either changed); `reset_all_data`/`save_sign_in`/`run` invalidate
   explicitly. All six views' `apply_result(service.load_last())` init
   calls switch to the cached variant (single stat call instead of
   CSV-parse + full bridge ×6). Keep plain `load_last()` as the uncached
   truth for tests. Invalidation test in `tests/services/test_sync.py`:
   mutate players.csv → next cached call re-bridges (matched count changes).
2. **`ui/views/_roster.py` (from R3) — mtime-keyed cache** for the
   (players.csv, keepers.json, draft_picks.json, aliases.json) quad so view
   actions stop re-parsing four files per click. Cache lives in the module
   (data_dir-keyed), invalidated on mtime change; a `clear_cache()` test
   seam for `tests/ui/test_roster.py`.
3. **`ui/views/board.py render()` — compute once, thread down.**
   `_team_projections(report)` is currently called three times per render
   (board.py:913, 999, 1012); compute it once at the top of `render()` and
   pass the dict into `_render_recs`, `_render_relative`, and the roster
   panel. Also skip the names-model rebuild when the excluded set is
   unchanged since the last render (guard with a stored copy) — pick/undo
   always changes it, theme toggles and re-renders don't.
4. **`domain/naming.py bridge()` — precompute** the pool's
   `(base, suffix, display)` triples once per call instead of
   re-`split_suffix`-ing every pool name for every roster name.
5. **Optional (only if the user reports waiver slowness on the real
   roster):** `domain/waiver.rank_candidates` batches its per-drop MC runs
   through one RNG with prebuilt (mu, sigma) lists, and/or
   `engine.matchup` gains an optional prebuilt-params argument. Default:
   skip — the docstrings already accept seconds-scale; revisit after the
   real draft if needed.

Acceptance: results identical (all per-directory tests green; board
screenshot unchanged); startup does one pool load + one bridge (assert via
a counter test in `tests/services/test_sync.py`); ruff clean; exe rebuilt.
Watch: cache invalidation is THE risk — every mutation path (import,
undo, reset, save order) must invalidate or re-stat.

## R6 — Dead code, minor cleanups, repo hygiene

1. `domain/players.py:27` — delete unused `_by_raw`.
2. `ui/views/trades.py:339` — delete the no-op `if layout is not None:
   del layout` branch.
3. `ui/views/matchup.py` — initialize `self._roster_players = ((), ())` in
   `__init__`; drop the `getattr` fallback in `_render_tables`.
4. `ui/views/lineups.py _render` — look up starter projections by name
   (`starter_proj` per player) instead of the positional
   `starter_proj.players[i]` pairing.
5. `ui/views/setup_dialog.py _save` — stop writing `settings["version"]`
   (io/state.save_json owns `version`); today it only shadows, but the
   override path is a foot-gun if they ever diverge.
6. `io/pool/importer.py validate_rows:242` — skip the duplicate-rank
   warning for blank ranks (multiple Yahoo-sourced rows all have `rank=""`
   → warning spam). Only warn for non-empty duplicate ranks.
7. `domain/trade.py` — no code change: the `1 − p` mirror-delta caveat is
   documented; record the review decision here and leave it.
8. Repo hygiene (scaffold): delete junk tracked in git — `.p1.txt`,
   `.p2.txt`, `.pytest_out.txt`, `.r.txt`, `tests/full_run.txt`,
   `Screenshot 2026-10-09 131142.png` (keep a copy in the chat history if
   it's referenced by past docs), and gitignore `.pi/reports/`. Confirm the
   screenshot isn't referenced by any doc before deleting.

Acceptance: per-directory tests green; ruff clean; exe rebuilt; git status
shows the junk gone. Bookkeeping: status.md updates for the touched
components; final ROADMAP note that the review remediation is complete.

---

## Explicit no-action decisions (documented, from the review)

- `oauth.py` fixed port 8480 (collides only with a second app instance;
  clear error already) and the unencrypted `oauth_key.pem` (localhost-only
  throwaway cert) — behavior kept, README note added in R2.
- `trade.py` summary presenting the mirrored "them" delta — kept.
- yfpy `_extracted_data` was kept in R2's rewrite ONLY behind an explicit
  allowlist + warning; full model-field mapping is future work if yfpy
  upgrades break it.
- Deeper MC micro-optimization (R5.5) — deferred until real-world slowdown.
