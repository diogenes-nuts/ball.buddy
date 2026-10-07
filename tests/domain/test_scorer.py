"""scorer.score_pool (P6 market/fit composite) tests.

Fake pool rows (z_* + adp_round + rank) — never the real players.csv.
Plain dicts, pure stdlib, no Qt, no I/O."""

from ball_buddy.domain import scorer
from ball_buddy.domain.recommend import recommend_need_aware
from ball_buddy.domain.scorer import score_pool


def zrow(
    name: str,
    rank: str = "",
    adp: str = "",
    z_pts: str = "0",
    z_reb: str = "0",
    z_ast: str = "0",
    z_stl: str = "0",
    z_blk: str = "0",
    z_to: str = "0",
    z_three: str = "0",
    z_fg_pct: str = "0",
    z_ft_pct: str = "0",
    value: str = "",
    pos: str = "C",
) -> dict[str, str]:
    """A pool row with z columns + rank + adp_round (blanks allowed)."""
    return {
        "name": name,
        "pos": pos,
        "rank": rank,
        "value": value,
        "adp_round": adp,
        "z_pts": z_pts,
        "z_reb": z_reb,
        "z_ast": z_ast,
        "z_stl": z_stl,
        "z_blk": z_blk,
        "z_to": z_to,
        "z_three": z_three,
        "z_fg_pct": z_fg_pct,
        "z_ft_pct": z_ft_pct,
    }


def names(result) -> list[str]:
    return [s.name for s in result]


def test_market_ordering_with_identical_fit():
    # z all zero, no ADP: the composite degrades to pure market order
    # (rank asc, i.e. (rank_max - rank)/rank_max desc).
    rows = [
        zrow("Third", rank="3"),
        zrow("First", rank="1"),
        zrow("Second", rank="2"),
    ]
    result = score_pool(rows, [], overall=10, team_count=10)
    assert names(result) == ["First", "Second", "Third"]
    assert result[0].rank == 1
    assert "mkt 1/3" in result[0].reason
    assert "no ADP" in result[0].reason


def test_fit_overrides_market_for_a_hole_cat():
    # I'm dead last at pts (hole, x1.25). A rank-2 candidate strong at
    # pts beats a rank-1 candidate who is blank at pts: the 0.55 fit
    # weight dominates the 0.45 market weight (fit spread 1.5z, market
    # spread 1 rank of 2).
    my_rows = [zrow("Mine", z_pts="-1")]
    rows = [
        zrow("HighRank", rank="1", z_pts="0"),
        zrow("PtsGuy", rank="2", z_pts="1.5"),
    ]
    result = score_pool(rows, my_rows, overall=10, team_count=10)
    assert names(result) == ["PtsGuy", "HighRank"]
    assert "holes pts" in result[0].reason


def test_hole_vs_covered_multiplier_visible_in_ordering():
    # Two same-fit-magnitude candidates: Q is +1z at pts, P +1z at reb.
    # reb is neutral for me in both cases; pts is a HOLE (edge < 0) in the
    # first, COVERED (edge >= 0.5) in the second. The 1.25 vs 0.75
    # multiplier on Q's pts flips the ordering: hole -> Q (1.25) beats
    # P (1.0); covered -> Q (0.75) loses to P (1.0).
    rows = [
        zrow("Q", rank="9", z_pts="1"),
        zrow("P", rank="10", z_reb="1"),
    ]
    # pool means: z_pts 0.5, z_reb 0.5; my z_reb 0.5 -> reb edge 0 (neutral)
    hole_my = [zrow("Mine", z_pts="-1", z_reb="0.5")]  # pts edge -1.5 -> hole
    covered_my = [zrow("Mine", z_pts="1", z_reb="0.5")]  # pts edge 0.5 -> covered
    hole = score_pool(rows, hole_my, overall=50, team_count=10)
    assert names(hole) == ["Q", "P"]
    assert "holes pts" in hole[0].reason
    covered = score_pool(rows, covered_my, overall=50, team_count=10)
    assert names(covered) == ["P", "Q"]
    assert "covered pts" in covered[0].reason
    assert "holes" not in covered[0].reason


def test_reach_tag_penalizes_and_value_tag_bonuses():
    # Same rank, same z: REACH (adp well before our pick) costs
    # TAG_ADJUSTMENT and sorts last; VALUE (adp well after) gains it and
    # sorts first; the in-range ADP ("on board") is in the middle.
    rows = [
        zrow("Reach", rank="1", adp="2"),
        zrow("OnBoard", rank="1", adp="10"),
        zrow("Value", rank="1", adp="20"),
    ]
    result = score_pool(rows, [], overall=10, team_count=10)
    assert names(result) == ["Value", "OnBoard", "Reach"]
    by_name = {s.name: s for s in result}
    assert "VALUE: ADP 20.0 vs pick 10" in by_name["Value"].reason
    assert "ADP 10.0 on board" in by_name["OnBoard"].reason
    assert "REACH: ADP 2.0 vs pick 10" in by_name["Reach"].reason


def test_value_gap_flag_fires():
    # 20 candidates, top decile = ranks 1..2. Decile floor = ADP of the
    # rank-2 player (5.0); threshold = 5.0 + 2*10 = 25.0. The rank-1
    # player at ADP 30 is overslept and carries the gap reason; the
    # rank-2 player (ADP == floor, not past the threshold) does not.
    rows = [zrow(f"F{i}", rank=str(i + 3)) for i in range(18)]
    rows.append(zrow("Floor", rank="2", adp="5"))
    rows.append(zrow("Sleepy", rank="1", adp="30"))
    result = score_pool(rows, [], overall=10, team_count=10, top_n=20)
    by_name = {s.name: s for s in result}
    assert "value gap: rank 1, ADP 30.0" in by_name["Sleepy"].reason
    assert "market oversleeping" in by_name["Sleepy"].reason
    assert "value gap" not in by_name["Floor"].reason
    assert "value gap" not in by_name["F3"].reason


def test_to_sign_flipped_low_to_outranks_high_to():
    # Source z_to is NOT sign-corrected (positive z_to == high TO == bad):
    # LowTo carries z_to=-1 (clean hands) and HighTo z_to=+1; the scorer
    # negates it, so with a TO hole the low-TO candidate outranks the
    # same-rank high-TO candidate.
    my_rows = [zrow("Mine", z_to="1")]
    rows = [
        zrow("HighTo", rank="1", z_to="1"),
        zrow("LowTo", rank="2", z_to="-1"),
    ]
    result = score_pool(rows, my_rows, overall=10, team_count=10)
    assert names(result) == ["LowTo", "HighTo"]
    assert "holes to" in result[0].reason


def test_empty_my_rows_edge_is_negative_pool_mean():
    # No secured players: per-cat edge = -pool mean (NOT a synthetic
    # -1.0). A cat where the pool is positive on average is a hole.
    rows = [zrow("A", rank="1", z_pts="1")]
    result = score_pool(rows, [], overall=10, team_count=10)
    assert "holes pts" in result[0].reason
    # pool mean z_pts = 0.5 -> my mean 0 -> edge -0.5 < 0 -> hole
    result2 = score_pool([zrow("A", rank="1", z_pts="0")], [], overall=10, team_count=10)
    assert "holes" not in result2[0].reason


def test_blank_adp_row_survives_without_tag_or_gap():
    rows = [zrow("NoAdp", rank="1"), zrow("HasAdp", rank="2", adp="10")]
    result = score_pool(rows, [], overall=10, team_count=10)
    # NoAdp keeps its better market rank (no penalty); HasAdp is on-board
    # (0.8*10 <= 10 <= 1.25*10) so no adjustment.
    assert names(result) == ["NoAdp", "HasAdp"]
    by_name = {s.name: s for s in result}
    assert "no ADP" in by_name["NoAdp"].reason
    assert "ADP 10.0 on board" in by_name["HasAdp"].reason
    assert "value gap" not in by_name["NoAdp"].reason


def test_blank_z_row_survives_fit_zero_market_only():
    # Blank z cells -> 0.0 per cat (fit +0.00z, no holes/covered); the
    # row is still ordered by market rank.
    rows = [
        zrow("BlankZ", rank="1", z_pts="", z_reb="", z_to=""),
        zrow("ZeroZ", rank="2"),
    ]
    result = score_pool(rows, [], overall=10, team_count=10)
    assert names(result) == ["BlankZ", "ZeroZ"]
    assert "fit +0.00z" in result[0].reason
    assert "holes" not in result[0].reason
    assert "covered" not in result[0].reason


def test_blank_rank_sorts_last_market_zero():
    rows = [zrow("Unranked"), zrow("Ranked", rank="1")]
    result = score_pool(rows, [], overall=10, team_count=10)
    assert names(result) == ["Ranked", "Unranked"]
    assert result[1].rank is None
    assert "mkt unrated (market 0.00)" in result[1].reason


def test_empty_pool_returns_empty():
    assert score_pool([], [], overall=1, team_count=10) == []
    assert score_pool([zrow("Only", rank="1")], [], overall=1, team_count=10, top_n=0) == []


def test_weights_all_ones():
    from ball_buddy.domain.engine import CATS

    assert set(scorer.WEIGHTS) == set(CATS)
    assert all(w == 1.0 for w in scorer.WEIGHTS.values())


def test_recommend_need_aware_empty_my_team_falls_back():
    # teams known but the scorer gets my_rows=[] — no crash, P6 reason
    # bits (and the fallback only when my_team is missing/unknown/blank).
    rows = [zrow("A", rank="1"), zrow("B", rank="2")]
    result = recommend_need_aware(rows, set(), {"Me": []}, my_team="Me",
                                  overall=5, team_count=10)
    assert names(result) == ["A", "B"]
    assert "mkt 1/2" in result[0].reason
    # missing my_team -> M2.3 fallback reasons
    fallback = recommend_need_aware(rows, set(), None, my_team="")
    assert fallback[0].reason == "pool rank 1"
