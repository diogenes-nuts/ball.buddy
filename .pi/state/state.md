# State — ball.buddy: M0 scaffold in flight
(Rewrite this whole file at every checkpoint. Never append. If a fact
no longer matters, delete it — git history keeps the trail.)

"Told" = user has heard this from you in plain words. Reading it in a log
does not count.

## Status
- Position: M0 in flight — subagent chain (planner→worker→reviewer→worker) launched. Files so far: agents/SPEC.md (design + league profile §1.1), agents/ROADMAP.md (M0–M7 build order), agents/ROUTING.md. No code, no git yet (worker does git init, no manual commits — phase_complete commits).
- Exact next step: run M0 chain, then phase_complete(component, "M0", summary) and follow returned doc steps.
- In flight: M0 chain output pending.
- Rules in force (user's own words): draft tracker is top priority / first feature after scaffolding; **use the tactile-cream-ui skill for ALL UI decisions throughout this project** (new, this turn).

## Verification
- Baseline: no code, no tests, no git. Docs read clean; SPEC moved to agents/SPEC.md with all cross-refs updated.
- Failing / not-yet: M0 not started (this turn). Open: 4-4 tie-break rule (user to check w/ comm), trade deadline + tx cutoff (read from Yahoo at M1).
- Now passing and what fixed it: —

## Findings
- League facts (user-confirmed, pre-draft 2026): roster 14 = 10 active + 3 BN + 1 conditional IR (no IR draft round; eligible only if injured while owned). 24 keepers finalized pre-draft, cost = prev round + comm penalty (in-app entry, per-keeper opt-out). FAAB $100 is ONLY add path; 3 adds/wk, unlimited drops, 3-day drop hold. Lineups daily, per-player game-start deadline. Playoffs top 4, 2 byes, single elim, end 2-3 weeks before NBA season. told yes.
- Open: 4-4 matchup tie-break disputed (Yahoo default vs season H2H); configurable in 004_engine, default Yahoo. told yes.
- Phase order (user): M2 = draft board first feature; M3 matchup, M4 waivers, M5 lineups, M6 trades, M7 packaging. told yes.
- Spec at agents/SPEC.md; §7 is a pointer to agents/ROADMAP.md. told yes.
- Tactile-cream-ui applies to all UI work in this project (user rule, this turn). told yes.

## U-turns
- draft board: "later phase (M6)" → first feature (M2): user pre-draft, wants it this draft. told yes.
- Roadmap: duplicated SPEC §7 table → single source agents/ROADMAP.md; SPEC §7 = pointer. told yes.

## Dead ends
- edit() non-ASCII in oldText (≥ § –): round-trip failures (U+2265, U+2013, U+00A7). Use ASCII-only anchors or copy from fresh read. Don't mix edits for different files in one call (atomic failure). told no (internal).
