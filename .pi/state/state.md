# State — REVIEW-FIXES remediation: R1a done (commit pending via phase_complete), R1b next

## Status
- Position: R1a (items 1–3) implemented + reviewed PASS + precedence fix applied + tested. In the middle of R1a bookkeeping: 006_board status.md update, exe rebuild, phase_complete for R1a components (scaffold, 006_board; 003_league unchanged this sub-phase — keepers.py is 006's file per its status.md line 12).
- Exact next step: (1) update agents/006_board/status.md keepers.py line — validation now "no duplicate (player, team); same team keeping same player twice is an error" (was "no duplicate player"); (2) rebuild exe (no process running per last check — verify again; move dist/data aside → pyinstaller -y → restore); (3) phase_complete component=006_board phase=R1a, then component=scaffold phase=R1a (or pick the component id the tool wants — try per-component calls); (4) then launch R1b chain (items 4–6: DRAFT_ROUNDS unify, matchup side attribution, _parse_z None).
- In flight: working tree has R1a diffs + plan doc + status edits. data/ untouched.
- Rules in force: user: implement R1–R6 via subagent chains, one phase per chain, split large phases as needed; phase commits ONLY via phase_complete; per-file pytest (never `pytest tests/ui` dir or `pytest tests` — exit 127 flake); invoke as `.venv/Scripts/python -m pytest`; ruff clean; rebuild exe after code changes.

## Verification
- Baseline @ 024b167: tests/domain 168 passed (worker's count; my earlier "43" was stale/wrong probe), tests/io 69, tests/services 52, ruff clean (31 files), tests/ui per-file green.
- R1a green: test_excepthook 3 passed, test_keepers 19, test_league_view 14 (after precedence fix), tests/domain 168, ruff clean.
- Flake: `pytest tests/ui` whole dir → exit 127 no output. Per-file + per-domain-dir is the verification unit.

## Findings
- R1a worker claims: main.py:50 critical is 2-arg (parent, text) — NO title arg (plan's 3-arg description was wrong; str-parent bug real); keepers dedupe via set[(key,team)] + first_team_by_key, message "{team!r} keeps {player!r} twice"; cross-team regression test unchanged.
- Reviewer (R1a): PASS 3/3; "opponent column quirk" is a non-issue (snapshot.py:103-104 sorts pairs team_a<team_b; first_team=teams[0] in practice lowest-id) → added 3-line invariant comment in league.py (then superseded by _visible() refactor — the comment stays, double-check it still reads right).
- Reviewer caught precedence fragility in schedule filter `not bye and x or y` (and/or implicit precedence) → refactored to explicit `_visible(entry)` helper at league.py (~528-543); 14/14 tests + ruff clean after refactor.
- 006_board/status.md line 12 = keepers.py entry (says "no duplicate player" — needs the same-team-twice wording); line 13 = picks.py (R1b territory: DRAFT_ROUNDS import note).
- scaffold/status.md already updated (excepthook bullet mentions R1a dialog fix).
- R1b targets (verified this session): picks.py:26 DRAFT_ROUNDS=13 (=MAX_COST_ROUND alias) vs views/league.py:41 DRAFT_ROUNDS=14; unify in domain/league.py (R1b owns it; R3 docstring-merge refers to it); board snake is data-driven? NO — board.py:744 uses picks_mod.build_snake; views/league.py:499 builds throwaway LeagueConfig(rounds=DRAFT_ROUNDS). MAX_COST_ROUND=13 stays (keeper cost cap; round-14 pick has no keeper cost) + docstring note. matchup.py:456-457 `side = "A" if player in players_a` → explicit side-carrying loop. board.py:308-316 `_parse_z` except ValueError → None (call sites 171 sort key / 209 / 1097 display already None-safe per _row_sort_key at 159).
- R2 targets: client.py:162 classifier, :173 fetch_all per-team (R2.2 = doc-only now), snapshot.py:143 _extracted_data, sync.py:160-164 _live_tokens OAuthError escape, client.py:184 persist_token silent no-op → SyncResult warning, README oauth_key.pem line, AGENTS.md M1 step.
- R3: _roster.py new module (matchup._load_team_data core verbatim; wrappers at matchup.py:357, waivers.py:60, trades.py:69, lineups.py:78), _common.py (CAT_LABELS def matchup.py:84, import board.py:80; _fmt_gap defs lineups.py:54 + trades.py:53, import matchup.py:28), naming.py:155+166 _suggest pool_norm_all param drop, domain/league.py docstring merge + DRAFT_ROUNDS home note, views/league.py:671 __all__ → bottom.
- R4: recommend.py Suggestion + market/fit_norm; scorer.py:206 score_pool populates (fit_norm None when degenerate range; market None for unranked); board.py:972-979 _mkfit reads fields, delete _MKT_RE/_FIT_RE; M2.3 fallback leaves None (em dash); scorer.py:192-194 hoist top_rank.
- R5a: sync.load_last_cached keyed on mtimes(snapshot.json, players.csv, aliases.json) + explicit invalidation in reset_all_data/save_sign_in/save_aliases/run + effective_snapshot through cache (sync.py:210; callers board.py:715, draft.py:82, setup_dialog.py:58, _offline.py:49) + counter test (1 load+bridge at startup) + invalidation tests (players.csv AND aliases.json mutation).
- R5b: _roster quad cache (players.csv, keepers.json, draft_picks.json, aliases.json; data_dir-keyed; clear_cache() seam) + board render once (_team_projections at 913/999/1012) + names-model rebuild skip when excluded set unchanged + naming.py:408 precompute triples.
- R6: players.py:27 _by_raw; trades.py:339 del; matchup.py _roster_players init; lineups.py:248-250 by-name starter lookup; importer.py:242 blank-rank; trade.py doc note; git rm 4 dotfiles + tests/full_run.txt + screenshot; .gitignore .pi/reports/ (note: .pi has 28 tracked files incl. state.md + eras — ONLY reports/ to ignore, keep rest tracked per user? flag at R6).
- Phase ids: R1a/R1b per component (006_board + scaffold; R1b adds 003_league? picks.py+league.py are 003's files per its status — yes 003 gets R1b; 004_engine untouched by R1? R1 items touch scaffold(main.py), 003(league view? views/league.py is 003's), 006(keepers/picks/board). R1b: 003 (views/league.py + domain/picks? picks.py — check ownership: 006 status line 13 claims picks.py) + 006 (board.py, domain/league.py if that's 003's — domain/league.py is 003's per status). So R1b = 003 + 006.

## U-turns
- Opponent-column "fix now" → DEFER (invariant makes it safe); reviewer confirmed, I added comment only. Told no.
- My turn-1 "43 baseline" for tests/domain was wrong; real is 168. Told no (internal note).

## Dead ends
- `pytest tests/ui` dir run — exit 127. Per-file only.
