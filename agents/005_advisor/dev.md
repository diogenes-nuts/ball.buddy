# 005_advisor — dev

Advisor logic (waiver, lineup, trade) consuming 004_engine. SPEC §6.

## M5.1 — Lineup optimizer (domain, headless)

Scope: per-day start/sit recommendations (SPEC §6.2), opponent-specific category targeting.
- Input: my 14-man roster (pool-bridged players), the opponent's projected roster (engine), day context (which players play today — pre-draft: no schedule lines, so a "all play" assumption + loud notice; M5.2 lets the user toggle who plays), IR rule awareness (10 active + 3 BN + 1 conditional IR).
- Output: recommended active 10 (respecting slot constraints: PG/SG/G/SF/PF/F/C/3 UTL eligibility) + sit list, chosen to maximize P(win) against the opponent (engine); secondary: which categories the lineup wins/loses vs opponent and by how much.
- Search: the slot-constrained assignment is a small combinatorial problem (~14 players into 10 slots) — decide exact algorithm in the plan (exhaustive with pruning / greedy-then-local-search / DP); must be deterministic and fast (<1s on 14 players).
- Rationale per seated starter: one line (which cat it helps, what it costs).
- Tests: fixture pool, hand-check a scenario where the greedy pick is wrong (proves search quality), slot-constraint correctness, IR eligibility, determinism.

## M5.2 — Lineup view (UI)

Scope: Lineups page (placeholder today): day picker (from schedule), playing/not-playing toggles per player (pre-draft manual), "Optimize" button, recommended lineup table (slot, player, projected contribution) vs current/suggested sit, category outlook vs opponent, one-click "start these" display only (no Yahoo writes — v1 is read-only).
- Exit (ROADMAP M5): "daily recommendations + explanations."

## M6 (trades) — planned later, sliced at its turn.
