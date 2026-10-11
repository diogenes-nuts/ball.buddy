# 003_league — done

## 2026-10-11 — R1b — R1b: DRAFT_ROUNDS=14 unified in domain/league.py (views/league.py local 14 const deleted, imports shared constant); SPEC 13-vs-14 flag noted for owner

From agents/REVIEW-FIXES.md R1 (item 4; shared phase id with 004/006, committed under each component).

- `ui/views/league.py` — deleted the local `DRAFT_ROUNDS = 14` (:41); imports the shared constant from `domain/league.py` (defined there at :323-326 next to the snake code). League-view rendered snake and board snake now provably identical (`test_league_view.py::test_draft_rounds_constant_shared_with_domain` asserts `is` identity across all three surfaces).
- `domain/league.py` — `DRAFT_ROUNDS = 14` + comment (SPEC §1.1: 14-slot roster, 14 draft rounds; round 14 has no keeper cost → `keepers.MAX_COST_ROUND = 13` intentionally stays 13).
- Open owner decision: agents/SPEC.md:32 still reads "Snake, 13 rounds" + conditional 14th IR slot; implementation follows the review plan's 14. SPEC reconciliation pending.
- Exe rebuilt (dist\ball.buddy\ball.buddy.exe). Verify: test_league_view 15, test_board 28, test_draft_view 5, tests/domain 168, ruff clean.

R1a (committed under scaffold, 2026-10-11): League schedule pane filter — bye rows now render only for their own team (`or entry.get("bye")` previously leaked every team's bye into team 1's pane); refactored to an explicit `_visible(entry)` helper; opponent column relies on the snapshot team_a<team_b invariant (comment in code, quirk deliberately not "fixed").
