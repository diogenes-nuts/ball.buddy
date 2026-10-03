# 004_engine — done

## 2026-10-03 — M3.1 — Projection engine (slice 1/2 of M3, headless): per-player/roster 9-cat projections from real pool columns (volume-weighted % cats), deterministic gap mode + seeded Monte-Carlo win-prob, per-category ties count both, configurable matchup tie-break (yahoo_default | h2h). 170 tests green, ruff clean.

- `domain/engine.py`: pure python (no Qt/numpy); projections from real pool columns only; FG%/FT% volume-weighted; `matchup()` deterministic gap mode (no RNG), `win_prob()` seeded MC (local `random.Random(seed)`, fixed relative variance prior — no historical variance pre-draft, documented).
- Per-category ties count for BOTH teams (deterministic + MC paths); matchup-level tie-break `yahoo_default | h2h` (ValueError on bad value; missing H2H evidence → push) per SPEC §1.1 open item.
- Reviewer flagged 5 potential defects; fix worker independently hand-recomputed and verified all 5 as non-defects (roster A pts 1520, fg 18.1÷38, B ft 0.872; gaps pts +520, fg_pct +0.03187, ft_pct +0.00578; P(A) seed42 = 0.9763 bit-identical across runs).
- Persisted smoke: `agents/004_engine/_smoke.py` (cat wins 7-2, winner A, reproducible=True).
- Verify: 170 passed / 1 skipped, ruff clean.
- Deferred to M3.2: `matchup_tie_break` wiring into `data/settings.json`; commissioner confirmation of 4-4 rule (SPEC §1.1 open item).

## 2026-10-03 — M3.2 — Matchup view (slice 2/2 — M3 complete): team/week pickers, headline P(win) (gap mode instant, seeded MC recompute), 9-cat gap bars, per-cat W/L/tie, player marginal table, tie_break wired to settings (yahoo_default | h2h with snapshot standings). 178 tests green, ruff clean, exe rebuilt.

- `ui/views/matchup.py` in the shell: team/week pickers, P(win) (gap mode default; MC button w/ visible seed), 9-cat gap bars, per-cat W/L/tie, marginal table; pre-draft full-roster projection with 'no lineups yet' notice; theme tokens only.
- Reviewer-caught BLOCKING: `_recompute` never passed tie-break evidence → true cat-ties always "Push" even in h2h mode. Fix: `_standings()` builds `{team: (W, L)}` from snapshot standings and passes `h2h=` to the engine; +regression test (identical rosters 9-9: yahoo_default=Push, h2h with Blue 5-0 = Blue wins).
- Post-review fixes: duplicate keepers.resolve pass merged; week selector no longer silently falls back to 1 (first numeric entry).
- Exe rebuilt (app module changed). Verify: 178 passed / 1 skipped, ruff clean, offscreen smoke OK (render, standings-backed h2h, settings persist, MC run).
- Open: real-week hand-check against synced data/ (no synced data in workspace); 4-4 rule commissioner confirmation (SPEC §1.1).
