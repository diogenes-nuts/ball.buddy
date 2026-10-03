## M3.1 Plan — Projection Engine (headless)

**Goal:** Pure-python `ball_buddy/domain/engine.py` — pool → 9-cat season projections → deterministic matchup gaps + seeded Monte-Carlo win prob, with configurable 4-4 tie-break. No Qt, no numpy, no new deps, no git.

### 1. Column → category map (importer FIELDNAMES, all real)
| cat | source | season value per player |
|---|---|---|
| pts/reb/ast/stl/blk/to/three | `pts_pg`…`three_pg` (per-game) | `rate × gp` (gp from `gp` col) |
| fg_pct | `fg_pct`, weight `fga_pg × gp` | volume-weighted at roster level |
| ft_pct | `ft_pct`, weight `fta_pg × gp` | volume-weighted at roster level |
No gaps: all 9 cats are covered. Missing/non-numeric cell → that player contributes 0 in that cat and a loud warning string is collected (never invented). `%` cat with Σ volume = 0 → pooled 0.0 + warning `"...: no FG/FT attempts; projected 0"`.

### 2. Projection formulas
- Per player: `season[cat] = rate × gp` (counts); pct cats keep `pct` + `attempts = attempt_pg × gp`.
- Roster (counts): `Σ_i season[i] × usage_factor` (default 1.0; single scalar knob — pre-draft both teams share roster shape so it cancels in gaps; this is the usage-adjust seam).
- Roster FG%: `Σ(pct_i × att_i) / Σ(att_i)`; FT% analogous. (Kills the 3889.3% bug.)
- Matchup gap = season totals (`gap = A − B`); TO gap positive = A worse (direction from `LeagueCategory.direction`).

### 3. Variance + Monte-Carlo
Fixed relative-variance prior (documented constant `REL_SIGMA`, pre-draft, no history): `pts .25, reb .30, ast .35, stl .50, blk .50, to .40, three .35, fg_pct .02, ft_pct .01`.
- Per player, count cat: `σ_i = REL_SIGMA[cat] × season_i`; per trial sample `max(0, gauss(season_i, σ_i))`, roster = Σ.
- Per roster, % cat: single draw `clamp01(gauss(pooled, REL_SIGMA × pooled))`.
- `win_prob`: N trials (default 10 000), each trial → 9-cat compare (win/loss/tie-for-both) → cat-wins; winner = more cat wins, else tie-break (below). `random.Random(seed)`; `seed=None` = unseeded.
- **Deterministic gap mode** = same inputs, `mc=False`: point gaps + cat scores + tie-break winner only.
- `week` param accepted but unused pre-draft (season scale cancels in per-cat compare) — signature kept for M3.2.

### 4. Tie-break (SPEC §1.1 open item)
Param `tie_break: "yahoo_default" | "h2h"` (default `yahoo_default`); later persisted in `data/settings.json` as `matchup_tie_break`. Caller supplies evidence: `catwins: dict[team,int]` (season total cat wins; pre-draft: projected) and/or `h2h: dict[team,tuple[wins,losses]]`. 4-4 (or 4.5-4.5) → `yahoo_default`: higher `catwins`; `h2h`: better H2H record (fewer losses, then more wins). Missing data / equal → matchup = push (win prob counts as 0.5 win for each… no: push, contributes nothing to either side's wins; P = A wins fraction).

### 5. Module: `ball_buddy/domain/engine.py`
`PlayerProjection` (name, gp, values, fg_attempts, ft_attempts), `RosterProjection` (name, cat_values[9], warnings), `MatchupResult` (gaps[9], cat_outcomes (a/b: "win"/"loss"/"tie"), cat_wins (a,b), winner: str|None, p_win: float|None, warnings).
Functions: `project_player(row)`, `project_roster(rows, name, usage_factor=1.0)`, `matchup(a, b, week=1, tie_break="yahoo_default", catwins=None, h2h=None, mc=False, seed=None, trials=10000)`, `win_prob(a, b, seed, trials, ...)` thin wrapper. Adapter point: engine consumes only the 9 stat cols + gp — a later `ProjectionSource` seam feeds real box-score rows unchanged.

### 6. Tests — `tests/domain/test_engine.py` (inline fixture, 4 players ×2 teams, gp=40)
P1: pts20 reb8 ast5 stl1.5 blk1.0 to2.0 three3.0 fg.50 fga20 ft.90 fta5 · P2: pts18 reb10 ast4 stl1.0 blk1.2 to2.5 three2.0 fg.45 fga18 ft.85 fta4 · P3: pts15 reb5 ast8 stl1.2 blk.8 to3.0 three2.5 fg.48 fga15 ft.92 fta3 · P4: pts10 reb4 ast3 stl.5 blk.5 to1.0 three1.0 fg.40 fga12 ft.80 fta2.
TeamA=[P1,P2], TeamB=[P3,P4]. Assert exact (≈1e-9) roster values: A: pts 1520, reb 720, ast 360, stl 100, blk 88, to 180, three 200, fg 18.1/38≈0.47631579, ft 7.9/9≈0.87777778; B: 1000, 360, 440, 68, 52, 160, 140, 12/27≈0.44444444, 4.36/5=0.872.
Gap tests: gaps = A−B: pts +520, reb +360, ast −80, stl +32, blk +36, to +20 (→B wins TO), three +60, fg +0.03187135, ft +0.00577778; cat_wins A 7, B 2; deterministic winner "A".
Tie test: identical projections (A vs A) → all 9 "tie", winner None; with `catwins={"A":6,"B":5}` yahoo_default → "A"; with `h2h={"A":(1,3),"B":(3,1)}` → "B".
MC: seed=42 → p_win ∈ (0.5, 1.0) and P(B)<0.5; same seed twice → bit-identical p_win; `p_win` always in [0,1].

### Files
- **New** `ball_buddy/domain/engine.py` — everything above.
- **New** `tests/domain/test_engine.py` — tests above.
- Nothing modified (league.py categories/directions consumed as-is; importer untouched).

### Risks
- Float ties in MC: use raw `>` (ties count for both per SPEC) — fine.
- `usage_factor` is a deliberate simplification of SPEC's lineup-shape adjustment; document in module docstring, no redesign later since it's a scalar.
- Ruff: keep lines <100, no `dict[str, float]`-style issues (3.14, `from __future__ import annotations`).

---

**Report (orchestrator view):** Plan locked. All 9 cats map to real FIELDNAMES cols (per-game rates × `gp`; fg_pct/ft_pct volume-weighted by `fga_pg`/`fta_pg`×`gp`) — zero gaps. Season-total formulas; single scalar `usage_factor` (cancels pre-draft) as usage-adjust seam. MC: fixed REL_SIGMA prior (pts .25 … fg .02, ft .01), per-player N(μ,σ) for counts, single draw for pooled %s, seed param, 10k trials; deterministic mode = `mc=False`. Tie-break param `tie_break` ("yahoo_default"|"h2h", caller-supplied `catwins`/`h2h`, push if no data). New files only: `ball_buddy/domain/engine.py`, `tests/domain/test_engine.py`; hand-computed fixture numbers in plan (A 7-2 B, exact gaps e.g. pts +520, fg 18.1/38). Open: commissioner must confirm 4-4 rule (§1.1) — engine makes it configurable per SPEC, default Yahoo.