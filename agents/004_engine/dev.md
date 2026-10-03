# 004_engine — dev

Projection + win-prob engine (SPEC §4 004_engine). Consumes pool (001_data) + league snapshot (003_league).

## M3.2 — Matchup view (UI)

Scope: the Matchup page in the shell (currently placeholder).
- Pick week (all weeks available from snapshot schedule; pre-draft = projection-only with a clear "no lineups yet — using full rosters" notice).
- Headline P(win), 9-cat gap bars, per-category W/L/L, player marginal table (top movers for this matchup per SPEC §4 player marginal table).
- Uses deterministic gap mode for instant response; optional MC recompute button.
- Theme tokens only; offscreen-testable.
- Exit (ROADMAP M3): "matchup screen correct by hand-check on one real week."

## M3.2 — done (no git commit per task constraints)

- New `ball_buddy/ui/views/matchup.py`: `MatchupView` (team A/B combos, week combo
  from `snapshot["schedule"]`, tie-break combo persisted to settings key
  `matchup_tie_break`, MC button + seed 42 / trials 10000 spins), `_GapBars`
  paintEvent widget (7-count / 2-pct groups, group scale = max |gap|,
  A-favorable INK_FILL left, B-favorable TEXT_MUTED right, tie DIVIDER tick,
  direction via `engine.DIRECTIONS`), per-cat table (Cat/Gap/A/B/W-L),
  marginal table (rostered players both sides, signed count-cat contribution,
  top 20 by max |contribution|, FG%/FT% = "–"). Roster source pre-draft:
  resolved keepers.json + entered draft_picks.json looked up via PlayerPool,
  deduped; banner "No lineups yet — projecting full rosters from keepers +
  drafted picks." All colors via `theme` constants.
- `shell.py`: Matchup placeholder -> `MatchupView(self.sync_service)`.
- New `tests/ui/test_matchup_view.py` (7 tests, offscreen): reuses M3.1
  fixture rows P1-P4 (Red keeps P1/P2, Blue keeps P3/P4) — asserts headline
  "Red wins (7-2 cats)", all 9 gap cells (+520/+360/-80/+32/+36/+20/+60,
  fg +0.03187135, ft +0.00577778), cat W/L A/A/B/A/A/B/A/A/A, marginal order
  P1/P2/P3/P4 with signs, week combo [1, 2], MC click seed 42/10000 ->
  "0.9763", tie-break persist, empty-roster no-crash.
