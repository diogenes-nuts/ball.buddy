"""Headless H2H lineup optimizer (M5.1, no Qt).

Picks the 10-man starting set from canonical pool rows (FIELDNAMES schema,
one slash-joined ``pos`` column) that wins the most deterministic head-to-head
categories against an opponent ``RosterProjection``, then assigns the 10
starters to the 10 lineup slots.

Slot mapping (fixed order, one position column only):
    PG  <- ``PG`` in pos ; SG <- ``SG`` ; G <- ``PG`` or ``SG``
    SF  <- ``SF`` ; PF <- ``PF`` ; F <- ``SF`` or ``PF`` ; C <- ``C``
    UTL <- any player with >= 2 distinct pos tokens (multi-position only; a
           pure ``C`` has 1 token and is not UTL-eligible).
Unknown/empty pos tokens: the player is excluded from the starters with a
warning note (never silently UTL-ified).

Algorithm (exhaustive over starter SETS + per-set slot matching; NOT DP):
``engine.project_roster`` is position-agnostic — the projection depends only
on the 10-player set — so every 10-combination of the playing rows is scored
with ``engine.project_roster`` + deterministic ``engine.matchup(mc=False)``
(reused, not re-implemented). Best by key ``((my_wins, -opp_wins), margin)``
where ``margin`` sums the direction-adjusted gaps over the categories we win.
Mixed count/pct units are acceptable: ``margin`` is a tie-break only, never
the primary decision. Ties keep the lex-smallest name tuple (combinations()
over a name-sorted list yields lex order, so the first best wins). For the
best set, slots are filled by deterministic backtracking in the fixed slot
order (PG, SG, G, SF, PF, F, C, UTL, UTL, UTL), players tried in name order.
``mc_trials > 0`` runs one seeded ``engine.win_prob`` on the final candidate
and stores ``p_win`` in the result WITHOUT changing the choice.

IR: this module emits exactly 10 starters + 4 sitters. The IR/BN split is an
M5.2 display concern and is deliberately not done here.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field

from ball_buddy.domain import engine
from ball_buddy.io.pool.importer import VALID_POS

SLOTS: tuple[str, ...] = ("PG", "SG", "G", "SF", "PF", "F", "C", "UTL", "UTL", "UTL")

SINGLE_SLOTS: tuple[str, ...] = ("PG", "SG", "G", "SF", "PF", "F", "C")


@dataclass
class LineupResult:
    """Optimal 10-starter lineup + sitters vs one opponent projection.

    ``starters`` is (slot, player) in fixed SLOTS order (the three UTL slots
    are indistinguishable beyond order). ``gaps`` are season-total gaps
    (us - opponent) per category. ``margin`` is the tie-break score (sum of
    direction-adjusted gaps over categories we win; mixed units). ``p_win``
    is the seeded MC win probability when ``mc_trials > 0`` (None otherwise,
    and never used to change the choice). ``rationale`` has one line per
    sitter; ``notes`` carries the all-play assumption, excluded
    unknown-pos players, and projection warnings.
    """

    starters: tuple[tuple[str, str], ...]
    sits: tuple[str, ...]
    gaps: dict[str, float]
    cat_outcomes: tuple[tuple[str, str], ...]
    cat_wins: tuple[int, int]
    margin: float
    p_win: float | None
    rationale: dict[str, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


def _pos_tokens(pos: str) -> frozenset[str]:
    return frozenset(t for t in pos.split("/") if t)


def _slot_ok(tokens: frozenset[str], slot: str) -> bool:
    if slot == "UTL":
        return len(tokens) >= 2
    return (
        (slot == "PG" and "PG" in tokens)
        or (slot == "SG" and "SG" in tokens)
        or (slot == "G" and ("PG" in tokens or "SG" in tokens))
        or (slot == "SF" and "SF" in tokens)
        or (slot == "PF" and "PF" in tokens)
        or (slot == "F" and ("SF" in tokens or "PF" in tokens))
        or (slot == "C" and "C" in tokens)
    )


def _assign(order: list[str], tokens: dict[str, frozenset[str]],
            set_names: frozenset[str]) -> list[str] | None:
    """Deterministic backtracking: fill SLOTS in order, players in name order.

    Returns the 10 chosen names in slot order (or None if unfillable).
    """
    used: set[str] = set()
    picked: list[str | None] = [None] * len(SLOTS)

    def bt(i: int) -> bool:
        if i == len(SLOTS):
            return True
        slot = SLOTS[i]
        for name in (n for n in order if n in set_names and n not in used):
            if not _slot_ok(tokens[name], slot):
                continue
            used.add(name)
            picked[i] = name
            if bt(i + 1):
                return True
            used.discard(name)
            picked[i] = None
        return False

    return list(picked) if bt(0) else None


def _legal_set(set_names: frozenset[str], tokens: dict[str, frozenset[str]]) -> bool:
    return sum(1 for n in set_names if _slot_ok(tokens[n], "UTL")) >= 3


def _margin(gaps: dict[str, float], outcomes: tuple[tuple[str, str], ...]) -> float:
    """Sum of direction-adjusted gaps over the categories we win (tie-break)."""
    total = 0.0
    for cat, (ours, _) in zip(engine.CATS, outcomes):
        if ours != "win":
            continue
        gap = gaps[cat]
        total += -gap if engine.DIRECTIONS[cat] == "lower" else gap
    return total


def optimize(
    my_rows: list[dict[str, str]],
    opponent: engine.RosterProjection,
    name: str = "My Team",
    playing: frozenset[str] | None = None,
    mc_trials: int = 0,
    seed: int | None = None,
) -> LineupResult:
    """Pick the best 10 starters (exhaustive over sets) + slot assignment.

    ``my_rows`` are canonical FIELDNAMES rows. ``playing=None`` means every
    eligible row plays (noted in the result); players not in ``playing``
    auto-sit. Raises ``ValueError`` (naming the specific unfillable slot)
    when fewer than 10 rows are playable or no legal 10-set exists (need >= 3
    multi-position players for the UTL slots).
    """
    if mc_trials < 0:
        raise ValueError("mc_trials must be >= 0")
    notes: list[str] = []
    if playing is None:
        notes.append("no schedule: assuming all play")

    # Eligible rows: known (non-empty) pos tokens only; unknown tokens are
    # excluded from the starters with a warning note, never UTL-ified.
    eligible: list[tuple[str, dict[str, str], frozenset[str]]] = []
    for row in sorted(my_rows, key=lambda r: r.get("name", "")):
        pname = row.get("name", "")
        if playing is not None and pname not in playing:
            continue
        tokens = _pos_tokens(row.get("pos", ""))
        bad = sorted(tokens - VALID_POS)
        if bad or not tokens:
            why = f"unknown pos token(s) {bad}" if bad else "empty pos"
            notes.append(f"excluded {pname} from starters: {why}")
            continue
        eligible.append((pname, row, tokens))

    order = [n for n, _, _ in eligible]
    tokens_of = {n: t for n, _, t in eligible}
    rows_of = {n: r for n, r, _ in eligible}

    if len(eligible) < 10:
        raise ValueError(
            f"PG: only {len(eligible)} playable row(s); need 10 starters"
        )
    for slot in SINGLE_SLOTS:
        if not any(_slot_ok(tokens_of[n], slot) for n in order):
            raise ValueError(f"{slot}: no playable player can fill this slot")
    if sum(1 for n in order if _slot_ok(tokens_of[n], "UTL")) < 3:
        raise ValueError(
            f"UTL: only {sum(1 for n in order if _slot_ok(tokens_of[n], 'UTL'))} "
            "multi-position players; need >= 3 UTL-eligible"
        )

    # Exhaustive over starter sets: projection is position-agnostic, so only
    # the 10-player set matters for the matchup.
    best: tuple[tuple[int, int], float] | None = None
    best_set: frozenset[str] | None = None
    for combo in itertools.combinations(order, 10):
        s = frozenset(combo)
        if not _legal_set(s, tokens_of):
            continue
        roster = engine.project_roster(
            [rows_of[n] for n in sorted(s)], name=name
        )
        result = engine.matchup(roster, opponent, mc=False)
        key = ((result.cat_wins[0], -result.cat_wins[1]), _margin(result.gaps, result.cat_outcomes))
        if best is None or key > best:
            best = key
            best_set = s

    if best_set is None:
        raise ValueError("UTL: no legal 10-man starter set (UTL slots unfillable)")

    slot_pick = _assign(order, tokens_of, best_set)
    if slot_pick is None:
        raise ValueError("C: no legal slot assignment for the best starter set")

    roster = engine.project_roster([rows_of[n] for n in sorted(best_set)], name=name)
    notes.extend(roster.warnings)
    result = engine.matchup(roster, opponent, mc=False)
    starters = tuple(zip(SLOTS, slot_pick))
    sits = tuple(n for n in order if n not in best_set)

    # Per-sitter rationale: the least-damaging legal swap (seat sitter for a
    # starter) and the category where that swap costs us the most.
    rationale: dict[str, str] = {}
    for n in sits:
        best_swap: tuple[float, str, str, str, float] | None = None
        for slot, s in starters:
            swap_set = (best_set - {s}) | {n}
            if not _legal_set(swap_set, tokens_of):
                continue
            if _assign(order, tokens_of, swap_set) is None:
                continue
            swap_roster = engine.project_roster(
                [rows_of[x] for x in sorted(swap_set)], name=name
            )
            swap_result = engine.matchup(swap_roster, opponent, mc=False)
            swap_wins = swap_result.cat_wins[0]
            if best_swap is None or swap_wins > best_swap[0]:
                worst = min(
                    engine.CATS,
                    key=lambda c: (-swap_result.gaps[c]
                                   if engine.DIRECTIONS[c] == "lower"
                                   else swap_result.gaps[c]),
                )
                gap = swap_roster.cat_values[worst] - opponent.cat_values[worst]
                best_swap = (swap_wins, s, slot, worst, gap)
        if best_swap is not None:
            _, s, slot, worst, gap = best_swap
            rationale[n] = (
                f"seat {n}: best legal swap vs {s} in {slot} gives up "
                f"{worst} {gap:+.3f}; lineup gains "
                f"{result.cat_wins[0] - best_swap[0]} cat win(s)"
            )
        else:
            rationale[n] = (
                f"seat {n}: no legal swap; lineup gains "
                f"{result.cat_wins[0]} cat win(s)"
            )

    p_win = None
    if mc_trials > 0:
        p_win = engine.win_prob(roster, opponent, seed=seed, trials=mc_trials)

    return LineupResult(
        starters=starters,
        sits=sits,
        gaps=dict(result.gaps),
        cat_outcomes=result.cat_outcomes,
        cat_wins=(result.cat_wins[0], result.cat_wins[1]),
        margin=_margin(result.gaps, result.cat_outcomes),
        p_win=p_win,
        rationale=rationale,
        notes=notes,
    )


__all__ = ["SLOTS", "LineupResult", "optimize"]
