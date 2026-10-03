## Goal
Build `ball_buddy/domain/lineup.py`: headless lineup optimizer — pick the 10 legal starters out of a 14-man roster maximizing deterministic category wins vs the opponent's `RosterProjection`, per M5.1 in `agents/005_advisor/dev.md`.

## Plan

**1. Slot mapping (from the ACTUAL pool column — there is one: `pos`, importer.py:38, slash-joined tokens ⊆ {PG,SG,SF,PF,C}, importer.py:70; there is NO utl flag, NO F/G token).**
- PG ← "PG" in pos; SG ← "SG"; G ← "PG" or "SG"; SF ← "SF"; PF ← "PF"; F ← "SF" or "PF"; C ← "C".
- UTL ← player has ≥2 distinct pos tokens (multi-position only). Pure-C players are not UTL-eligible. Unknown/empty pos tokens → excluded from starters + warning (cannot fill any slot).

**2. Roster model input.** `optimize(my_rows: list[dict[str,str]] (canonical FIELDNAMES rows), opponent: RosterProjection, name="My Team", playing: frozenset[str] | None = None) -> LineupResult`. `playing=None` → all play (adds note "no schedule: assuming all play"); players not in `playing` are auto-sit. Reuse `engine.project_roster`/`engine.matchup(mc=False)` — no re-implementation.

**3. Algorithm (decided: exhaustive over starter SETS + per-set slot matching; NOT DP).** Key fact: `engine.project_roster` is position-agnostic — the roster projection depends only on the 10-player *set*, not slot assignment. So: iterate `itertools.combinations(sorted(playing rows), 10)` = C(14,10) = **1001 candidates**; per candidate: project_roster → deterministic `matchup` → keep best by key `((my_wins, -opp_wins), margin, -lex(sorted names))` where margin = Σ direction-adjusted gap over winning cats (tie-break only; mixed units acceptable). For the best set, produce the slot assignment by backtracking over slots in fixed order (PG,SG,G,SF,PF,F,C,UTL,UTL,UTL), players tried in name order → ≤10×10, deterministic. Complexity ≈ 1001 × (10-player projection + 9-cat compare + tiny matching) ≪ 10 ms. DP rejected (pct pooling is non-additive per player, so category-wins objective doesn't decompose over subsets; exhaustive-set is simpler and faster here). MC polish: `mc_trials: int = 0` param — when >0, run `engine.win_prob` once on the final candidate and store `p_win` in the result WITHOUT changing the choice (search stays fast/deterministic; M5.2 can display it).

**4. Output.** `@dataclass LineupResult`: `starters: tuple[tuple[str,str],...]` (slot→player, slot order above), `sits: tuple[str,...]` (sorted), `gaps: dict[str,float]`, `cat_outcomes`, `cat_wins: tuple[int,int]`, `margin: float`, `p_win: float | None`, `rationale: dict[str,str]` (one line per sitter: e.g. "seat {name}: gives up {cat} {val} vs {filler} in {slot}; lineup gains {Δ} cat win(s)"), `notes: list[str]` (all-play assumption, unknown-pos players, warnings). Determinism: names sort everywhere; equal-key sets → lex-smallest name tuple. Fewer than 10 playable rows, or no legal set for any 10-subset (raise `ValueError` with the specific unfillable slot) → error.

**5. IR.** Optimizer emits exactly the 10 starters + 4 sitters; which sitter is IR/BN is a M5.2 display concern — say so in module docstring.

**6. Tests — `tests/domain/test_lineup.py`.** Fixture: 14 hand-written FIELDNAMES rows with clear pos spread (2 PG, 2 PG/SG, 1 SG, 2 SF, 2 PF, 1 SF/PF, 2 C, 1 PG/SG/SF, 1 SG/PF, 1 C/PF — i.e. ≥3 multi-pos for UTL).
   - **Greedy-wrong scenario (hand-checked, expected answer in this plan):** opponent roster set with `cat_values` exactly 1.0 above us in every cat except FT% (opponent 0.45, us base 0.40), and TO (opponent 2.0 vs us 2.5 so we already win TO). Naive greedy (seat the 7 highest-pts players) leaves our pooled FT% at 0.40 → 6-cat loss. Row "Zeta" (PG/SG, 2 pts_pg, ft_pct 0.80, huge fta_pg) and "Yankee" (C/PF, 3 pts_pg, ft_pct 0.75) sit out under greedy; the optimum swaps both in → pooled FT% ≥ 0.50, TO still won, and the two swapped-out players' category value is low, so cat wins flip to 7–1. Assert: expected starter name set equals the optimum set (compute it by hand: all rows except the 4 weakest category contributors among non-Zeta/Yankee), cat_wins[0] > cat_wins[1], Zeta & Yankee in starters, margin > 0.
   - **Constraint property test:** for 5 fixture rosters, assert exactly one player per slot key, each starter's pos satisfies the mapping of its slot, UTL starters all multi-pos, 10 starters + 4 sits = 14 disjoint names.
   - Determinism: 20 repeated calls → identical `LineupResult` (dataclass equality).
   - `playing` edge: `playing=frozenset()` → `ValueError`; subset of 12 with a 2-pos player removed so <3 UTL-eligible remain → `ValueError` naming "UTL".
   - `mc_trials=1000, seed` → `p_win` in [0,1], choice unchanged vs mc_trials=0.

## Files to Modify
- `ball_buddy/domain/lineup.py` — new module (slot map, `optimize`, `LineupResult`, backtracking `assign_slots`, rationale builder).
- `tests/domain/test_lineup.py` — new tests above.

## Risks
- Roster projection sums ALL 10 starters regardless of slot (engine.py `project_roster` semantics) — matches how Yahoo H2H counts only starters; but our "sits" contribute nothing, consistent with engine tests.
- Margin tie-break mixes count/pct units — documented as tie-break-only.
- If a real pool row has an unknown pos token (importer warns but keeps it), it's excluded from play with a note; don't silently UTL-ify.

**Final report (≤2000 chars):**

## Conclusion
M5.1 = one new module `ball_buddy/domain/lineup.py` + one test file. No re-decisions left.

**Key findings**
- Pool has ONE position column: `pos` (importer.py:38), slash-joined tokens from {PG,SG,SF,PF,C} only (importer.py:70). No utl flag, no F/G tokens. So: G←PG|SG, F←SF|PF, others literal; **UTL = ≥2 pos tokens** (multi-pos only). Unknown pos → excluded + note.
- `engine.project_roster` is position-agnostic (engine.py:157): roster projection depends only on the 10-player SET. Therefore search = **exhaustive over C(14,10)=1001 sets** (project_roster → deterministic `matchup(mc=False)`, key = (my_cat_wins, -opp_cat_wins, margin, lex names)) + tiny backtracking slot-matching for the winner. ≪10 ms. DP rejected (pct pooling non-additive → cat-wins objective doesn't decompose). Optional `mc_trials>0` runs `win_prob` on the final candidate, reports `p_win`, never changes the choice.
- Input: 14 canonical FIELDNAMES rows + opponent `RosterProjection` + `playing: frozenset|None` (None = all-play note; absent → auto-sit).
- Output `LineupResult`: starters [(slot,player)] in fixed slot order (PG,SG,G,SF,PF,F,C,UTL×3), sits, gaps, cat_outcomes, cat_wins, margin, p_win, per-sitter one-line rationale, notes. Deterministic (name tie-breaks). <10 playable or no legal set → ValueError naming the slot.
- IR: emits exactly 10 starters + 4 sitters; IR/BN split is M5.2 (docstring).

**Files**
- `ball_buddy/domain/lineup.py` (new)
- `tests/domain/test_lineup.py` (new): 14-row fixture; hand-checked greedy-wrong case (opponent ahead in 8 cats; optimum swaps in two high-FTA% multi-pos rows Zeta PG/SG 0.80 FT, Yankee C/PF 0.75 FT → FT% flips, 7–1; greedy top-7-pts loses 6 cats — expected starter set asserted); property test (exactly 10/1 per slot, pos legality, UTL multi-pos); determinism ×20; empty `playing` → ValueError; <3 UTL-eligible → ValueError; mc_trials path.

**Open issues:** margin tie-break mixes count/pct units (tie-break only, documented); no new deps, no Qt, no commits.