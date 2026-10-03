# 004_engine — status

Projection + win-prob engine (SPEC §4). **M3 complete** (M3.1 engine, M3.2 view).

## Files

- `ball_buddy/domain/engine.py` — the whole engine (pure python, no Qt, no numpy):
  - Player/roster projections from **real pool columns only**; % categories (FG%, FT%) volume-weighted, never simple averages; per-category formulas per M3.1 plan (see done.md).
  - `matchup(team_a, team_b, ...)` — deterministic gap mode: 9-cat point gaps, per-category W/L/**tie-for-both**, total category wins, winner. No RNG touched in this mode.
  - `win_prob(...)` — seeded Monte-Carlo (local `random.Random(seed)`, reproducible); fixed relative variance prior (no historical variance pre-draft — documented).
  - Configurable matchup-level tie-break: `tie_break="yahoo_default" | "h2h"` (SPEC §1.1 open item; default = more total category wins that season; h2h = better season H2H record; missing evidence → push).
- `agents/004_engine/_smoke.py` — persisted reproducible smoke (fixture pool, gaps, P(A) seed 42 = 0.9763).
- `ball_buddy/ui/views/matchup.py` (M3.2) — Matchup page in the shell: team A/B pickers, week selector (snapshot schedule, fallback first numeric entry), headline P(win) (gap mode instant; MC recompute button w/ visible seed), 9-cat gap bars, per-cat W/L/tie, player marginal table; pre-draft full pool-based rosters (keepers + drafted picks) with 'no lineups yet' notice; theme tokens only. `matchup_tie_break` setting in `data/settings.json` (default `yahoo_default`; `h2h` uses snapshot standings via `_standings()`) — true cat-ties: yahoo_default pushes without per-team category-win evidence (documented), h2h resolves via standings.

## Known open (by design)

- Commissioner confirmation of the 4-4 rule still pending (SPEC §1.1). (`matchup_tie_break` is wired to `data/settings.json` in M3.2 via the Matchup view.)

Plans: dev.md. History: git log; done.md.
