# 006_board — dev

## Plan: Draft v2 (before 2026-10-15..20 draft; ~1 week)

Context: Yahoo 403 persists post-dev-program-acceptance → offline-first; the board is a
standalone draft-day sidecar (Yahoo's live draft room runs mechanics + timer + autopick).
User decisions (2026-10-08):

- Mine-only analysis: other teams are analyzed under the hood solely to surface my team's
  RELATIVE strengths/weaknesses (is a strength strong enough to compete; is a weakness
  too weak to salvage → punt).
- Recommender = B (need-aware vs league-relative gaps) + C1 (observed position scarcity
  from picks made so far — facts, not prediction). No C2 demand simulation (compounding
  errors across 11 managers; observation accumulates faster than the window where
  prediction would help). No timer/lock-in (Yahoo client has built-in timer + autopick;
  duplication is scope waste).
- Team projection during draft: ALL secured players count as active (draft picks +
  active keepers). No starter/bench distinction — it only matters in-season once >10
  players are playing on a day.
- Keepers: manual entry until/if Yahoo auth lands; setup dialog replaces the 24-row
  keeper grid as the manual-entry surface. Draft-order + team-name edits live there too.
- Migration into the season engine: deferred (assume auth eventually comes).

Verification per phase: pytest + ruff green; offscreen UI tests where the app has them.

## Plan: Draft helper rework (2026-10-06, after Draft v2)

Context: user directives — (1) the 13×12 snake BOARD GRID is unnecessary (Yahoo's
draft client shows board info); the draft view orients around RECOMMENDATIONS like
the user's prior web tracker (N:/LLM/projects/autodraft: left = available-players
table → needs → rosters; right rail = recommendations; sticky topbar w/ pick info +
undo). (2) "My Team vs League" transposed: CATEGORIES AS THE TOP ROW, data as rows
beneath (My team / League median / Gap / Tag). (3) GLOBAL rule: every stat shown in
the UI carries a relative-strength color cue — good=green, bad=red, neutral=uncolored,
gradient between (autodraft: percentile-of-z gradient, dark red ≤5th pct, neutral
band 45–55th, dark green ≥95th, TO sign-flipped so greener is always better).

User confirmations: same orientation as autodraft (pool table main surface, recs in
right rail); roster panel shows ONE team at a time (default mine, dropdown to switch,
UI flag when not my team); use autodraft's scoring formula (0.45·market + 0.55·fit
+ tag adjustments, hole 1.25 / ok 1.0 / covered 0.75 multipliers, REACH/VALUE tags,
value-gap flag) — replaces the P2 formula.

### P7 — Draft Helper UI
theme.py: percentile color helper (green/red/neutral gradient, TO flipped) used by
EVERY stat cell in the app. New draft view layout (autodraft orientation): slim pick
strip (R{r} · pick {n}/156 · {team} + search + Log + Undo); left main: available
players table (pos filter, all 9 stats color-coded, per-row Log button); right rail:
Recommendations (top-N default 10, adjustable 1–20, reasons verbatim, gap badge,
REACH/VALUE chips); transposed My-Team-vs-League panel (cats as top row; rows: My
team / League median / Gap / Tag; stats color-coded); single-team roster panel
(dropdown, default my team, "not my team" flag). Snake grid + board.py pick grid
REMOVED (pick model/persistence + undo stay — the strip drives them). Setup dialog
unchanged.
