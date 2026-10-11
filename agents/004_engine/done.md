# 004_engine — done

## 2026-10-03 — M3.1 — Projection engine (slice 1/2 of M3, headless): per-player/roster 9-cat projections from real pool columns (volume-weighted % cats), deterministic gap mode + seeded Monte-Carlo win-prob, per-category ties count both, configurable matchup tie-break (yahoo_default | h2h). 170 tests green, ruff clean.

- `domain/engine.py`: pure python (no Qt/numpy); projections from real pool columns only; FG%/FT% volume-weighted; `matchup()` deterministic gap mode (no RNG), `win_prob()` seeded MC (local `random.Random(seed)`, fixed relative variance prior — no historical variance pre-draft, documented).
- Per-category ties count for BOTH teams (deterministic + MC paths); matchup-level tie-break `yahoo_default | h2h` (ValueError on bad value; missing H2H evidence → push) per SPEC §1.1 open item.
- Reviewer flagged 5 potential defects; fix worker independently hand-recomputed and verified all 5 as non-defects (roster A pts 1520, fg 18.1÷38, B ft 0.872; gaps pts +520, fg_pct +0.03187, ft_pct +0.00578; P(A) seed42 = 0.9763 bit-identical across runs).
- Persisted smoke: `agents/004_engine/_smoke.py` (cat wins 7-2, winner A, reproducible=True).
- Verify: 170 passed / 1 skipped, ruff clean.
- Deferred to M3.2: `matchup_tie_break` wiring into `data/settings.json`; commissioner confirmation of 4-4 rule (SPEC §1.1 open item).

## 2026-10-03 — M3.2 — Matchup view (slice 2/2 — M3 complete): team/week pickers, headline P(win) (gap mode instant, seeded MC recompute), 9-cat gap bars, per-cat W/L/tie, player marginal table, tie_break wired to settings (yahoo_default | h2h with snapshot standings). 178 tests green, ruff clean, exe rebuilt.

- `ui/views/matchup.py` in the shell: team/week pickers, P(win) (gap mode default; MC button w/ visible seed), 9-cat gap bars, per-cat W/L/tie, marginal table; pre-draft full-roster projection with 'no lineups yet' notice; theme tokens only.
- Reviewer-caught BLOCKING: `_recompute` never passed tie-break evidence → true cat-ties always "Push" even in h2h mode. Fix: `_standings()` builds `{team: (W, L)}` from snapshot standings and passes `h2h=` to the engine; +regression test (identical rosters 9-9: yahoo_default=Push, h2h with Blue 5-0 = Blue wins).
- Post-review fixes: duplicate keepers.resolve pass merged; week selector no longer silently falls back to 1 (first numeric entry).
- Exe rebuilt (app module changed). Verify: 178 passed / 1 skipped, ruff clean, offscreen smoke OK (render, standings-backed h2h, settings persist, MC run).

## 2026-10-08 — category display order — Reorder all category display to FG%, FT%, 3P, Pts, Reb, Ast, Stl, Blk, TO: engine.CATS/COUNT_CATS + scorer.CAT_Z_COLUMN + matchup view (labels, gap-bars, marginal table) + domain CATEGORIES; added MC_DRAW_ORDER so seeded win-probs stay stable across display reorders

- Ad-hoc cross-cutting change (not a ROADMAP phase). `engine.CATS` is the single source of truth for category display order across every view/table/bar (matchup cat table + gap bars, lineups, trades, board relative/roster/players columns); `COUNT_CATS` follows the same relative order for the count subset. `scorer.CAT_Z_COLUMN` (board grid headers) reordered to match.
- Key subtlety: the seeded Monte-Carlo trial loop iterated `CATS`, so a display reorder would shift the RNG draw order and change every seeded win-prob (flipped test_waiver's Star/Point near-tie; would move the pinned P(A) seed42 = 0.9763). Fix: new `MC_DRAW_ORDER` tuple (the original pts to three to fg_pct to ft_pct order) used ONLY by the MC trial loop, so presentation reorders never touch RNG state. Deterministic gap mode already consumed by cat name, so unaffected.
- Matchup view: gap-bars now render PCT group (FG%/FT%) above the COUNT group; marginal table header reordered to Player,Side,3P,Pts,Reb,Ast,Stl,Blk,To,FG%,FT% (value list auto-follows `COUNT_CATS`, 11 cols aligned). `CAT_LABELS` dict reordered for consistency (lookups order-agnostic).
- `domain/__init__.py` `CATEGORIES` (vestigial, never imported) reordered for consistency.
- Tests: updated the order-sensitive display assertions in `tests/ui/test_matchup_view.py` (wl list, gaps list, marginal col 3 = pts; dash cols 9/10) and `tests/ui/test_board.py` relative panel (pts=col3, reb=col4). Seeded values (waiver ranking, 0.9763, trade delta_p) all UNCHANGED thanks to `MC_DRAW_ORDER`.
- Verify: tests/domain 167, tests/io 85 (1 skip), tests/services 13, all tests/ui files green, ruff clean; `_smoke.py` re-run confirms P(A) seed42 = 0.9763 preserved with gaps emitting in the new order.
- Open: real-week hand-check against synced data/ (no synced data in workspace); 4-4 rule commissioner confirmation (SPEC §1.1).

## 2026-10-11 — R1b — R1b: Matchup marginal table side attribution by explicit (side, players) loop — identical player on both rosters renders one A + one B row

From agents/REVIEW-FIXES.md R1 (item 5).

- `ui/views/matchup.py:456-462` — marginal-table rows built via `for side, players in (("A", players_a), ("B", players_b))` instead of `side = "A" if player in players_a else "B"` (value-equality mislabeled an identical player on both rosters as "A").
- Test: `test_matchup_view.py::test_marginal_table_identical_player_both_sides` — same pool row on both rosters → exactly one ("P1","A") and one ("P1","B") row.
- Verify: test_matchup_view 10, ruff clean; exe rebuilt.


## 2026-10-11 — R3 — R3: matchup.py no longer owns CAT_LABELS (now ui/views/_common.py) and _load_team_data is a one-line delegate to ui/views/_roster.py

`_load_team_data` (matchup.py:292-295) is a one-line wrapper around `_roster.team_roster_rows` (new shared `ui/views/_roster.py`; see 005_advisor R3 for the shared module). `CAT_LABELS` moved out of matchup.py into `ui/views/_common.py` (single definition; matchup imports it). Pure refactor — matchup's table render, gap bars, and all 10 tests unchanged.

## 2026-10-11 — R6 — R6 (docs): 004 R6 bookkeeping — matchup _roster_players init + getattr fallback drop (code swept with the shared R6 commit); carries 005 R6 done.md section

`matchup.py` (code in shared R6 commit 90866de): `MatchupView.__init__` now sets `self._roster_players: tuple[tuple, tuple] = ((), ())` alongside the other `snapshot`/`last_result` inits, and `_render_tables` reads `self._roster_players` directly — the `getattr(self, "_roster_players", ((), ()))` fallback is gone (it papered over the missing init). Pure hygiene; matchup's 10 view tests green.
