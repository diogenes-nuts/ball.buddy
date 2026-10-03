# 004_engine — dev

Projection + win-prob engine (SPEC §4 004_engine). Consumes pool (001_data) + league snapshot (003_league).

## M3.1 — Projection engine (headless, no UI)

Scope: everything 004_engine needs, zero Qt.
- Player projections: from pool columns (see importer FIELDNAMES — use what exists; usage-adjusted where possible per SPEC §4) → projected category points + percentages (volume-weighted for % cats), season-long context (games played) for weekly normalization.
- Roster projection: aggregate active roster (10 starters per league config) to 9-cat totals.
- Matchup: project both rosters, per-category gap + win/loss per cat (ties per Yahoo default), configurable matchup-level tie-break (SPEC §1.1 open item: default = more total category wins that season).
- Variance + Monte-Carlo win-prob per SPEC §4 (deterministic seed option); **deterministic gap mode** for fast UI (no MC).
- No season data yet (pre-draft) → projections stand on pool priors; design so real game data can feed in later without redesign (adapter point in the plan).
- Tests: fixture pool, hand-checkable 2-team matchup (assert specific gaps/P(win)), tie-break config, determinism (same seed same result).

## M3.2 — Matchup view (UI)

Scope: the Matchup page in the shell (currently placeholder).
- Pick week (all weeks available from snapshot schedule; pre-draft = projection-only with a clear "no lineups yet — using full rosters" notice).
- Headline P(win), 9-cat gap bars, per-category W/L/L, player marginal table (top movers for this matchup per SPEC §4 player marginal table).
- Uses deterministic gap mode for instant response; optional MC recompute button.
- Theme tokens only; offscreen-testable.
- Exit (ROADMAP M3): "matchup screen correct by hand-check on one real week."
