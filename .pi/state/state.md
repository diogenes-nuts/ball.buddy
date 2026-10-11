# State — review-remediation plan written; awaiting go-ahead

"Told" = user has heard this from me in plain words.

## Status
- Position: PLAN WRITTEN, implementation NOT started (user: "Write all of this into a detailed plan, split into small, logical phases. Do not begin implementing." — told yes).
- Exact next step: on the user's go, start R1 (phase 1 of agents/REVIEW-FIXES.md) via the scout→planner→worker→reviewer chain, phase_complete per component with shared phase ids R1..R6.
- In flight: none.
- Rules in force: rebuild exe after every code change; per-directory pytest runs (combined Qt run hard-kills, env flake); phase_complete commits — never git commit manually.

## Verification
- Baseline (pre-R1): last known green 250165e + popup fix; tests/ui/test_board.py 27 passed; nothing changed since (review + plan writing only).

## Findings
- Master plan: agents/REVIEW-FIXES.md — 6 phases: R1 correctness bugs (main.py:49 dialog bug, league.py:541 BYE filter, keepers.py:93 same-team dup, 13/14 DRAFT_ROUNDS unification → one constant in domain/league.py, matchup.py:457 value-equality side, board.py:308 _parse_z) → R2 yahoo (classifier on signal not substrings, league-level matchups fetch, snapshot settings allowlist, OAuthError→LoginRequiredError in _live_tokens, persist_token surfacing, README oauth_key note) → R3 pure refactor (ui/views/_roster.py replaces 4 verbatim resolver copies, ui/views/_common.py CAT_LABELS+_fmt_gap, naming._suggest param drop, league.py docstring merge + __all__ move) → R4 (Suggestion.market/fit_norm fields replace reason-string regex parsing, scorer.py:192 O(n²) hoist) → R5 (sync.load_last_cached mtime-keyed, _roster.py cache, board render-once + names-model guard, bridge precompute; waiver MC batching optional/deferred) → R6 (dead code: players._by_raw, trades del-layout no-op, matchup init, lineups positional lookup, setup_dialog version shadow, importer blank-rank warning spam, junk file removal).
- Component stubs appended to all 7 dev.md files; ROADMAP.md has an "Open plan — review remediation" section pointing at REVIEW-FIXES.md. — told yes
- Order rationale: R3 before R5 (cache lives in the shared resolver); R4 independent but sequenced after R3 for small diffs. — told yes

## U-turns
- (none)

## Dead ends
- (none)
