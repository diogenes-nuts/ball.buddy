# 001_data — dev

(no active plans)

## Plan: Projection inbox + pool reconciliation (2026-10-06)

Context: user's projection source is a saved Hashtag import-v4 page (top-200 only,
e.g. repo-root import.html). Hashtag updates rankings regularly → automate refresh.
Yahoo pool (sub-200 players) arrives only when/after auth lands; reconcile by NAME
(user: Yahoo ranks ≠ Hashtag ranks — never join on rank; rank column is always the
Hashtag rank when present, None for Yahoo-appended rows).

## Plan: Review remediation (2026-10-14) — see agents/REVIEW-FIXES.md

Phases R1..R6; this component participates in: R1 (DRAFT_ROUNDS unification, keepers dup), R3 (roster resolver extraction, naming cleanup), R5 (bridging precompute). No active phase until implementation starts.
