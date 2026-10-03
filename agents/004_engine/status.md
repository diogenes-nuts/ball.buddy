# 004_engine — status

Headless projection + win-prob engine (SPEC §4). M3.1 done; M3.2 (matchup view UI) remaining in dev.md.

## Files

- `ball_buddy/domain/engine.py` — the whole engine (pure python, no Qt, no numpy):
  - Player/roster projections from **real pool columns only**; % categories (FG%, FT%) volume-weighted, never simple averages; per-category formulas per M3.1 plan (see done.md).
  - `matchup(team_a, team_b, ...)` — deterministic gap mode: 9-cat point gaps, per-category W/L/**tie-for-both**, total category wins, winner. No RNG touched in this mode.
  - `win_prob(...)` — seeded Monte-Carlo (local `random.Random(seed)`, reproducible); fixed relative variance prior (no historical variance pre-draft — documented).
  - Configurable matchup-level tie-break: `tie_break="yahoo_default" | "h2h"` (SPEC §1.1 open item; default = more total category wins that season; h2h = better season H2H record; missing evidence → push).
- `agents/004_engine/_smoke.py` — persisted reproducible smoke (fixture pool, gaps, P(A) seed 42 = 0.9763).

## Known open (by design)

- Commissioner confirmation of the 4-4 rule still pending (SPEC §1.1). (`matchup_tie_break` is wired to `data/settings.json` in M3.2 via the Matchup view.)

Plans: dev.md (M3.2). History: git log; done.md.
