# 005_advisor — dev

Advisor logic (waiver, lineup, trade) consuming 004_engine. SPEC §6.

## M6.2 — Trade view (UI) — done 2026-10-04 (M6 complete)

Trades page shipped (see status.md). Trade entry (my-give / their-give
combos over resolved roster names), Analyze via `domain/trade.analyze_trade`
(seed + trials spinboxes, domain default 200), per-side before/after
9-cat gap tables (Before/After/Delta), fairness verdict + delta-P summary
in banner/summary; ValueError -> banner (waivers pattern). No week picker
(analyze_trade is week-agnostic season-projection scoring — documented in
the view docstring). Exit (ROADMAP M6): "what-if delta-P(win) per side,
before/after category gaps, fairness flag" — all three covered by the view
(banner + summary line: delta-P per side; tables: per-cat before/after/
delta; banner: "likely a bad deal" fairness verdict).
