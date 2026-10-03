# 004_engine — done

## 2026-10-03 — M3.1 — Projection engine (slice 1/2 of M3, headless): per-player/roster 9-cat projections from real pool columns (volume-weighted % cats), deterministic gap mode + seeded Monte-Carlo win-prob, per-category ties count both, configurable matchup tie-break (yahoo_default | h2h). 170 tests green, ruff clean.

- `domain/engine.py`: pure python (no Qt/numpy); projections from real pool columns only; FG%/FT% volume-weighted; `matchup()` deterministic gap mode (no RNG), `win_prob()` seeded MC (local `random.Random(seed)`, fixed relative variance prior — no historical variance pre-draft, documented).
- Per-category ties count for BOTH teams (deterministic + MC paths); matchup-level tie-break `yahoo_default | h2h` (ValueError on bad value; missing H2H evidence → push) per SPEC §1.1 open item.
- Reviewer flagged 5 potential defects; fix worker independently hand-recomputed and verified all 5 as non-defects (roster A pts 1520, fg 18.1÷38, B ft 0.872; gaps pts +520, fg_pct +0.03187, ft_pct +0.00578; P(A) seed42 = 0.9763 bit-identical across runs).
- Persisted smoke: `agents/004_engine/_smoke.py` (cat wins 7-2, winner A, reproducible=True).
- Verify: 170 passed / 1 skipped, ruff clean.
- Deferred to M3.2: `matchup_tie_break` wiring into `data/settings.json`; commissioner confirmation of 4-4 rule (SPEC §1.1 open item).
