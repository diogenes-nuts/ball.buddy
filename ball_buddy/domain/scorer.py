"""P6 market/fit scorer — the composite pool ranking behind the recommender.

Pure scoring math, no I/O, no Qt. Ports autodraft's
``engine/scoring.py::ValueGapScorer`` onto ball.buddy's canonical
``players.csv`` rows (dict[str, str]):

- **market** — the pool's own rank signal: ``(rank_max − rank) / rank_max``
  (1.0 for the #1-ranked row, 0.0 for the last).
- **fit** — the candidate's signed per-category z (pool z columns via
  ``importer.Z_FIELD_FOR``; ``z_to`` NEGATED at parse — the source does not
  sign-correct turnovers, so raw z_to correlates +0.999 with raw to_pg),
  weighted by ``WEIGHTS`` and per-category multipliers from my roster's
  edge: per cat ``edge = my roster mean signed z − pool mean signed z``;
  ``edge < 0`` → hole (× ``HOLE_MULT``), ``edge >= COVERED_THRESHOLD`` →
  covered (× ``COVERED_MULT``), else ×1. Fit is min-max normalized over
  the candidates (all-equal → 0.5).
- **tag** — REACH (``adp < REACH_FACTOR * overall`` — the market expects
  this player to go before us: −``TAG_ADJUSTMENT``), VALUE
  (``adp > VALUE_FACTOR * overall`` — the market is behind us:
  +``TAG_ADJUSTMENT``), else "on board" (0).
- **score** = ``MARKET_WEIGHT * market + FIT_WEIGHT * fit_norm + tag_adj``.
- **value gap** (extra reason only, never the score): top-decile
  candidates (rank in the top ``VALUE_GAP_TOP_FRACTION`` of the pool)
  whose ADP slips more than ``VALUE_GAP_DEFAULT_ROUNDS`` full rounds
  (× ``team_count``) past the decile's ADP floor (the ADP of the
  worst-ranked decile player carrying a modeled ADP) — "market
  oversleeping". Needs ≥ ``VALUE_GAP_MIN_CANDIDATES`` candidates.

Tolerance (deliberately laxer than autodraft, which raises on blanks):
a blank z cell → 0.0 for that cat; a blank ``adp_round`` → ``None``
(tag "no ADP", excluded from the gap flag); a blank/unparseable rank →
market 0 and ``Suggestion.rank=None``; blank name → row skipped.

Decisions that differ from autodraft, intentionally:
- empty my roster → per-cat edge = ``−pool mean`` (a team with no secured
  players gets no synthetic −1.0 hole everywhere; the pool baseline is
  the honest starting point);
- the composite returns the recommender's existing
  ``recommend.Suggestion`` (name/pos/value/rank/reason) so the board
  panel and its 5-column table are untouched — the raw split numbers
  stay in the reason string.
"""

from __future__ import annotations

from dataclasses import dataclass

from ball_buddy.domain.engine import CATS
from ball_buddy.domain.recommend import Suggestion
from ball_buddy.io.pool.importer import Z_FIELD_FOR

# Draft-day tunables (module constants, not settings — engine calibration,
# mirroring autodraft's ValueGapScorer).
MARKET_WEIGHT = 0.45
FIT_WEIGHT = 0.55
TAG_ADJUSTMENT = 0.10
REACH_FACTOR = 0.8
VALUE_FACTOR = 1.25
HOLE_MULT = 1.25
COVERED_MULT = 0.75
COVERED_THRESHOLD = 0.5
VALUE_GAP_TOP_FRACTION = 0.10
VALUE_GAP_MIN_CANDIDATES = 10
VALUE_GAP_DEFAULT_ROUNDS = 2

# Per-cat weights: one entry per engine cat key, all 1.0 (autodraft's
# league.json carries all-1 weights; kept as a module constant for
# draft-day tuning, not in settings).
WEIGHTS: dict[str, float] = {cat: 1.0 for cat in CATS}

# Engine cat key -> canonical players.csv z column (built from
# importer.Z_FIELD_FOR; source names are not uniform: z_pts, not z_pts_pg).
CAT_Z_COLUMN: dict[str, str] = {
    cat: Z_FIELD_FOR[stat]
    for cat, stat in (
        ("pts", "pts_pg"),
        ("reb", "reb_pg"),
        ("ast", "ast_pg"),
        ("stl", "stl_pg"),
        ("blk", "blk_pg"),
        ("to", "to_pg"),
        ("three", "three_pg"),
        ("fg_pct", "fg_pct"),
        ("ft_pct", "ft_pct"),
    )
}

# Source z_to is NOT sign-corrected (correlates +0.999 with raw to_pg);
# negate it so a higher signed z means a better contribution in every cat.
_NEGATED_CATS: frozenset[str] = frozenset({"to"})


@dataclass(frozen=True)
class _Row:
    """One parsed pool row: market signals + signed per-cat z."""

    name: str
    pos: str
    value: str
    rank: int | None
    adp: float | None
    z: dict[str, float]


def _parse_number(text: object) -> float | None:
    try:
        return float(str(text).strip())
    except ValueError:
        return None


def _parse_row(row: dict[str, str]) -> _Row | None:
    name = (row.get("name") or "").strip()
    if not name:
        return None
    rank_text = (row.get("rank") or "").strip()
    rank: int | None = None
    try:
        candidate = int(rank_text)
        if candidate > 0:
            rank = candidate
    except ValueError:
        rank = None
    adp_raw = (row.get("adp_round") or "").strip()
    adp = _parse_number(adp_raw) if adp_raw else None
    z: dict[str, float] = {}
    for cat, column in CAT_Z_COLUMN.items():
        value = _parse_number(row.get(column, "")) or 0.0
        if cat in _NEGATED_CATS:
            value = -value
        z[cat] = value
    return _Row(
        name=name,
        pos=(row.get("pos", "") or "").strip(),
        value=(row.get("value", "") or "").strip(),
        rank=rank,
        adp=adp,
        z=z,
    )


def _reach_tag(adp: float | None, overall: int) -> str:
    """REACH (market ahead of us), VALUE (market behind us), ON, NO_ADP."""
    if adp is None:
        return "NO_ADP"
    if adp < REACH_FACTOR * overall:
        return "REACH"
    if adp > VALUE_FACTOR * overall:
        return "VALUE"
    return "ON"


def _tag_reason(tag: str, adp: float | None, overall: int) -> str:
    if tag == "NO_ADP":
        return "no ADP"
    adp_text = f"ADP {adp:.1f}"
    if tag == "REACH":
        return f"REACH: {adp_text} vs pick {overall}"
    if tag == "VALUE":
        return f"VALUE: {adp_text} vs pick {overall}"
    return f"{adp_text} on board"


def _fit_reason(fit: float, edges: dict[str, float]) -> str:
    text = f"fit {fit:+.2f}z"
    holes = [cat for cat in CATS if WEIGHTS[cat] > 0 and edges[cat] < 0]
    covered = [
        cat for cat in CATS if WEIGHTS[cat] > 0 and edges[cat] >= COVERED_THRESHOLD
    ]
    parts = []
    if holes:
        parts.append("holes " + ", ".join(holes))
    if covered:
        parts.append("covered " + ", ".join(covered))
    if parts:
        text += ": " + "; ".join(parts)
    return text


def _gap_names(candidates: list[_Row], team_count: int) -> frozenset[str]:
    """Names of the candidates the market is oversleeping (see module doc)."""
    if len(candidates) < VALUE_GAP_MIN_CANDIDATES:
        return frozenset()
    cutoff = max(1, int(len(candidates) * VALUE_GAP_TOP_FRACTION))
    decile = [
        row
        for row in candidates
        if row.rank is not None and row.rank <= cutoff and row.adp is not None
    ]
    if not decile:
        return frozenset()
    floor_adp = max(
        row.adp for row in decile if row.rank == max(r.rank for r in decile)
    )
    threshold = floor_adp + VALUE_GAP_DEFAULT_ROUNDS * team_count
    return frozenset(
        row.name
        for row in candidates
        if row.rank is not None
        and row.rank <= cutoff
        and row.adp is not None
        and row.adp > threshold
    )


def score_pool(
    rows: list[dict[str, str]],
    my_rows: list[dict[str, str]],
    overall: int,
    team_count: int,
    top_n: int = 10,
) -> list[Suggestion]:
    """Score the pool for one pick: market + fit + tag, top ``top_n``.

    ``rows`` is the full candidate pool (canonical pool rows incl. ``z_*``
    and ``adp_round``); ``my_rows`` are MY team's secured pool rows (hole /
    covered edge from their signed-z means); ``overall`` is the current
    pick's 1-based snake index (tag boundaries); ``team_count`` is the
    start-order length (value-gap round threshold). Returns
    ``recommend.Suggestion`` in score order (ties: rank asc, unranked last,
    then row order); ``reason`` is " · "-joined: market bit, fit bit
    (holes / covered, weight>0 cats only), tag bit, optional value-gap bit.
    Tolerances: blank z → 0.0, blank adp → "no ADP" (no gap flag), no
    rank → market 0 (``rank=None``).
    """
    candidates = [parsed for parsed in (_parse_row(r) for r in rows) if parsed]
    if not candidates:
        return []
    # Secured rows are (usually) not in the candidate set — parse them
    # straight from my_rows, no pool-membership check.
    my = [parsed for parsed in (_parse_row(r) for r in my_rows) if parsed]

    rank_max = max((row.rank for row in candidates if row.rank is not None), default=0)
    pool_mean = {
        cat: sum(row.z[cat] for row in candidates) / len(candidates) for cat in CATS
    }
    edges: dict[str, float] = {}
    for cat in CATS:
        if my:
            mine = sum(row.z[cat] for row in my) / len(my)
            edges[cat] = mine - pool_mean[cat]
        else:
            edges[cat] = -pool_mean[cat]
    mults = {
        cat: (
            HOLE_MULT
            if edges[cat] < 0
            else COVERED_MULT if edges[cat] >= COVERED_THRESHOLD else 1.0
        )
        for cat in CATS
    }

    fits = [
        sum(WEIGHTS[cat] * row.z[cat] * mults[cat] for cat in CATS)
        for row in candidates
    ]
    lo, hi = min(fits), max(fits)

    gap_names = _gap_names(candidates, team_count)

    out: list[Suggestion] = []
    for index, (row, fit) in enumerate(zip(candidates, fits, strict=True)):
        market = 0.0 if row.rank is None else (rank_max - row.rank) / rank_max
        fit_norm = 0.5 if hi == lo else (fit - lo) / (hi - lo)
        tag = _reach_tag(row.adp, overall)
        tag_adj = (
            TAG_ADJUSTMENT
            if tag == "VALUE"
            else -TAG_ADJUSTMENT if tag == "REACH" else 0.0
        )
        score = MARKET_WEIGHT * market + FIT_WEIGHT * fit_norm + tag_adj
        if row.rank is None:
            market_bit = "mkt unrated (market 0.00)"
        else:
            market_bit = f"mkt {row.rank}/{rank_max} → {market:.2f}"
        bits = [
            market_bit,
            _fit_reason(fit, edges),
            _tag_reason(tag, row.adp, overall),
        ]
        if row.name in gap_names:
            bits.append(
                f"value gap: rank {row.rank}, ADP {row.adp:.1f} — market oversleeping"
            )
        out.append(
            (
                -score,
                1 if row.rank is None else 0,
                row.rank or 0,
                index,
                Suggestion(
                    name=row.name,
                    pos=row.pos,
                    value=row.value,
                    rank=row.rank,
                    reason=" · ".join(bits),
                ),
            )
        )
    out.sort(key=lambda entry: entry[:4])
    return [entry[4] for entry in out[:top_n]]


__all__ = [
    "CAT_Z_COLUMN",
    "COVERED_MULT",
    "COVERED_THRESHOLD",
    "FIT_WEIGHT",
    "HOLE_MULT",
    "MARKET_WEIGHT",
    "REACH_FACTOR",
    "TAG_ADJUSTMENT",
    "VALUE_FACTOR",
    "VALUE_GAP_DEFAULT_ROUNDS",
    "VALUE_GAP_MIN_CANDIDATES",
    "VALUE_GAP_TOP_FRACTION",
    "WEIGHTS",
    "score_pool",
]
