# 005_advisor — done

## 2026-10-03 — M4.1 — Waiver scoring domain (slice 1/2 of M4): rank_candidates computes baseline P once, per-candidate full drop-space counterfactuals (best drop = max delta-P via engine), ranked list with delta_p, per-cat deltas, FAAB budget flag, direction-aware rationale, loud unmatched-name errors. 187 tests green, ruff clean.

- `domain/waiver.py`: baseline once (waiver.py L107-110), all-roster-drop scan (L114-129, strict `>` first-tie; full drop space documented in docstring — deviation from "bench-first" sizing, accepted), sort `(-delta_p, cost, name)`; FAAB `over_budget` flag; unmatched names → `ValueError` listing all misses (L56-71).
- Reviewer PASS on all 7 criteria; fix worker independently re-verified with its own arithmetic: Point (trials=50, seed=7) baseline 0.7200, per-drop deltas S1 −0.42 / S2 −0.08 / W1 +0.24 / W2 +0.26 → best drop W2, delta_p +0.26 — exact match.
- Post-review fix (nit 1): rationale sign-adjusted for `to` direction (`TO +40 (was +20)` — positive always reads "improves").
- Nits 2-4 verified non-defects (faab_cost reachable on candidate; single-opponent scope per dev.md).
- Verify: 187 passed / 1 skipped, ruff clean, engine smoke unchanged (7-2, P seed42 0.9763).
