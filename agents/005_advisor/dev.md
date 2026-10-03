# 005_advisor — dev

Advisor logic (waiver, lineup, trade) consuming 004_engine. SPEC §6.

## M4.1 — Waiver scoring (domain, headless)

Scope: rank waiver-wire candidates by ΔP(win) vs. the user's team this week (SPEC §6.1).
- Inputs: user team's projected roster (engine), waiver candidate list (pool-bridged; source = Yahoo waiver wire when synced, fixture pre-draft), team's drop constraint (unlimited drops, 3 adds/wk — the relevant constraint: which current roster player gets dropped), FAAB context ($100 budget, cost per candidate if available, else free).
- For each candidate: best counterfactual = add candidate, drop the current player whose loss minimizes damage (evaluate the small space: each bench/weak starter); ΔP(win) = P(with add+drop) − P(as-is) via engine (seeded MC + deterministic gap both).
- Output ranked: candidate, ΔP(win), implied drop, per-category delta, FAAB cost, one-line rationale (which cat the add helps most).
- Pre-draft reality: no real waiver wire — fixture-driven; UI (M4.2) must clearly say "no wire data yet — entering candidates manually" with a manual-candidate entry path.
- Tests: fixture league, hand-checked ΔP ordering, drop-selection correctness, determinism.

## M4.2 — Waiver view (UI)

Scope: Waivers page (placeholder today).
- Week + opponent context (reuse matchup view patterns), candidate list (manual entry pre-draft / wire when synced), ranked results table (ΔP, drop, cat deltas, cost, rationale), FAAB budget display + per-candidate bid input.
- Theme tokens only; offscreen-testable.
- Exit (ROADMAP M4): "ranked list with ΔP(win) per candidate."

## M5 (lineups) + M6 (trades) — planned later, sliced at their turn.
