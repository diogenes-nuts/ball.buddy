# 005_advisor — dev

Advisor logic (waiver, lineup, trade) consuming 004_engine. SPEC §6.

## M5.2 — Lineup view (UI) — done 2026-10-03

Lineups page shipped (see status.md). Exit (ROADMAP M5): "daily recommendations + explanations."

## M6.1 — Trade scoring (domain) — done 2026-10-04

New `ball_buddy/domain/trade.py`: `Trade` (my_give/their_give display-name
tuples) + `TradeResult` (per-side baseline/delta P(win), deterministic
gaps before/after per side's own perspective, `fairness_flag` = my delta
< −0.10, human `summary`). `analyze_trade` reuses `engine.project_roster` /
`win_prob`/`matchup` unchanged; one seeded MC run serves both sides
(opponent = `1 − my_p`, pushes treated as losses for both — documented).
Validation mirrors waiver `_resolve`: one `ValueError` listing all
roster/pool misses; both-sides-empty rejected. Tests:
`tests/domain/test_trade.py` (8 cases, waiver-style fixtures, trials=50
shared seed; symmetry at 2000 trials). No UI (M6.2 later).

Reviewer fixes (same day): (a) removed dead "net league P rises" summary
suffix — mathematically unreachable since `their_delta_p == -my_delta_p`
under the `1-p` construction; summary now appends a fairness verdict
(" likely a bad deal"/" looks fair") instead. (b) `_validate` now also
pool-checks roster (non-give) names — a roster name missing from the pool
previously crashed inside `project_roster` with `AttributeError` instead
of the loud single `ValueError`. (c) tests added: roster-miss raises,
2-for-2 swap, summary format (11 tests total).

## M6.2 — Trade view (UI) — planned later, sliced at its turn.

Trade entry (my-give / their-give, pool-bridged names), Analyze via
`domain/trade.analyze_trade`, per-side before/after tables, fairness
verdict banner; ValueError -> banner (waivers pattern).
