"""recommend() (M2.3) + recommend_need_aware() (P2: B + C1) tests.

Plain dict rows, pure stdlib — no Qt, no I/O. The P2 tests use
canonical FIELDNAMES stat rows so the engine's category projections
are exercised for real (gp ~ 60-80, pts_pg 5-30, pct 0.6-0.95)."""

from ball_buddy.domain.recommend import (
    cat_fill,
    recommend,
    recommend_need_aware,
)


def row(name: str, rank: str = "", value: str = "", pos: str = "C") -> dict[str, str]:
    return {"name": name, "pos": pos, "rank": rank, "value": value}


def stat_row(
    name: str,
    pos: str = "C",
    rank: str = "",
    value: str = "",
    gp: float = 70,
    pts_pg: float = 10,
    reb_pg: float = 5,
    ast_pg: float = 2,
    stl_pg: float = 1,
    blk_pg: float = 0.5,
    to_pg: float = 2,
    three_pg: float = 1,
    fg_pct: float = 0.48,
    fga_pg: float = 15,
    ft_pct: float = 0.75,
    fta_pg: float = 5,
    z_pts: float = 0.0,
    z_reb: float = 0.0,
    z_ast: float = 0.0,
    z_stl: float = 0.0,
    z_blk: float = 0.0,
    z_to: float = 0.0,
    z_three: float = 0.0,
    z_fg_pct: float = 0.0,
    z_ft_pct: float = 0.0,
) -> dict[str, str]:
    """A full canonical FIELDNAMES row (name/pos/rank/value + 9 stats + gp + z)."""
    return {
        "name": name,
        "pos": pos,
        "rank": rank,
        "value": value,
        "gp": str(gp),
        "pts_pg": str(pts_pg),
        "reb_pg": str(reb_pg),
        "ast_pg": str(ast_pg),
        "stl_pg": str(stl_pg),
        "blk_pg": str(blk_pg),
        "to_pg": str(to_pg),
        "fg_pct": str(fg_pct),
        "fga_pg": str(fga_pg),
        "ft_pct": str(ft_pct),
        "fta_pg": str(fta_pg),
        "three_pg": str(three_pg),
        "z_pts": str(z_pts),
        "z_reb": str(z_reb),
        "z_ast": str(z_ast),
        "z_stl": str(z_stl),
        "z_blk": str(z_blk),
        "z_to": str(z_to),
        "z_three": str(z_three),
        "z_fg_pct": str(z_fg_pct),
        "z_ft_pct": str(z_ft_pct),
    }


def test_orders_by_rank_ascending():
    rows = [row("Gamma", "3", "50"), row("Beta", "1", "90"), row("Alpha", "2", "70")]
    result = recommend(rows, set())
    assert [s.name for s in result] == ["Beta", "Alpha", "Gamma"]
    assert [s.rank for s in result] == [1, 2, 3]


def test_value_breaks_rank_ties_descending():
    rows = [row("Low", "3", "50"), row("High", "3", "70"), row("Top", "1", "90")]
    result = recommend(rows, set())
    assert [s.name for s in result] == ["Top", "High", "Low"]


def test_blank_value_displays_empty_and_sorts_last_within_rank():
    rows = [row("Blank", "2", ""), row("Priced", "2", "40")]
    result = recommend(rows, set())
    assert [s.name for s in result] == ["Priced", "Blank"]
    assert result[1].value == ""


def test_excluded_names_dropped():
    rows = [
        row("Drafted One", "1", "90"),
        row("Kept Two", "2", "80"),
        row("Alias Matched Pool Name", "3", "70"),
        row("Fresh Three", "4", "60"),
    ]
    excluded = {"Drafted One", "Kept Two", "Alias Matched Pool Name"}
    result = recommend(rows, excluded)
    assert [s.name for s in result] == ["Fresh Three"]


def test_blank_rank_sorts_after_ranked_stable_by_row_order():
    rows = [row("Zed", ""), row("Beta", "1", "90"), row("Ann", "", "5")]
    result = recommend(rows, set())
    assert [s.name for s in result] == ["Beta", "Zed", "Ann"]
    # unranked rows carry rank=None (UI displays "—"), never an invented number
    assert [s.rank for s in result] == [1, None, None]


def test_unparseable_rank_treated_as_blank():
    rows = [row("Weird", "n/a"), row("Beta", "1")]
    result = recommend(rows, set())
    assert [s.name for s in result] == ["Beta", "Weird"]


def test_top_n_truncates():
    rows = [row(f"P{i}", str(i)) for i in range(1, 8)]
    result = recommend(rows, set(), top_n=3)
    assert [s.name for s in result] == ["P1", "P2", "P3"]


def test_empty_pool_and_all_excluded():
    assert recommend([], set()) == []
    rows = [row("Only", "1")]
    assert recommend(rows, {"Only"}) == []


def test_suggestion_fields_passthrough():
    rows = [row("Someone", "7", "12.5", pos="PG/SG")]
    (s,) = recommend(rows, set())
    assert s.name == "Someone" and s.pos == "PG/SG" and s.value == "12.5"
    assert s.rank == 7 and s.reason == ""


# --- P2: recommend_need_aware ------------------------------------------------


def test_need_aware_fallback_without_my_team():
    # no my-team (blank / unknown / empty teams) -> M2.3 order + reasons
    rows = [row("Gamma", "3", "50"), row("Beta", "1", "90"), row("Alpha", "2", "70")]
    teams = {"Alpha": [row("Beta", "1", "90")]}
    for my_team, team_set in [("", teams), ("Nobody", teams), ("Alpha", {})]:
        result = recommend_need_aware(rows, set(), team_set, my_team=my_team)
        assert [s.name for s in result] == ["Beta", "Alpha", "Gamma"]
        assert result[0].reason == "pool rank 1"
        assert result[1].reason == "pool rank 2"


def test_need_aware_unranked_row_reason():
    # P6 path (my team known, no stat cells): unranked rows sort after
    # ranked ones and their reason reports the missing rank, not a rank.
    rows = [row("Zed", ""), row("Beta", "1", "90")]
    result = recommend_need_aware(rows, set(), {"Me": []}, my_team="Me")
    assert [s.name for s in result] == ["Beta", "Zed"]
    assert "mkt unrated" in result[1].reason
    assert "no ADP" in result[1].reason


def test_fallback_unranked_reason_via_rejecting_my_team():
    rows = [row("Zed", ""), row("Beta", "1", "90")]
    result = recommend_need_aware(rows, set(), None, my_team="")
    assert [s.name for s in result] == ["Beta", "Zed"]
    assert result[1].reason == "unranked (top pool order)"


def test_need_aware_beats_raw_value():
    # Me is dead last at pts AND blk in the pool z (hole in both); every
    # other category is identical league-wide. A lower-rank candidate with
    # strong pts/blk z (the fit) must outrank the higher-rank candidate
    # who is blank in both, and the P2 fill bits still name the filled cats.
    teams = {
        "Me": [stat_row("M1", pts_pg=10, blk_pg=0, z_pts=-1, z_blk=-1)],
        "T2": [stat_row("T21", pts_pg=25, blk_pg=1)],
        "T3": [stat_row("T31", pts_pg=25, blk_pg=1)],
        "T4": [stat_row("T41", pts_pg=25, blk_pg=1)],
    }
    pool = [
        stat_row("HighVal", rank="1", value="100", pts_pg=0, blk_pg=0),
        stat_row("NeedFill", rank="2", value="99", pts_pg=25, blk_pg=1,
                 z_pts=1, z_blk=1),
    ]
    result = recommend_need_aware(pool, set(), teams, my_team="Me")
    assert [s.name for s in result] == ["NeedFill", "HighVal"]
    assert "mkt 2/2" in result[0].reason
    assert "holes pts, blk" in result[0].reason
    assert "fills pts & blk gaps" in result[0].reason
    assert "fills" not in result[1].reason  # fills nothing


def test_need_aware_to_direction():
    # Lower-is-better category: Me is WORST in TO (280 vs median 122.5,
    # spread 210 -> gap 0.75). A low-TO candidate fills the gap; a
    # high-TO candidate (league-worst) fills nothing.
    teams = {
        "Me": [stat_row("M1", to_pg=4, z_to=1)],
        "T2": [stat_row("T21", to_pg=2, z_to=0.5)],
        "T3": [stat_row("T31", to_pg=1.5, z_to=0.25)],
        "T4": [stat_row("T41", to_pg=1, z_to=0)],
    }
    pool = [
        stat_row("Clumsy", rank="1", value="50", to_pg=3, z_to=0.5),
        stat_row("CleanHands", rank="2", value="50", to_pg=0.5, z_to=-0.5),
    ]
    result = recommend_need_aware(pool, set(), teams, my_team="Me")
    assert [s.name for s in result] == ["CleanHands", "Clumsy"]
    assert "fills to gaps" in result[0].reason
    assert "fills" not in result[1].reason


def test_need_aware_bias_cancellation():
    # A uniform +10 on every player's pts_pg (pool AND teams, same gp)
    # must not change the need-aware ordering: my gap vs the median and
    # the league spread shift equally, and every candidate's fill stays
    # capped at the gap, so the constant need shift cancels.
    teams = {
        "Me": [stat_row("M1", pts_pg=10)],
        "T2": [stat_row("T21", pts_pg=20)],
        "T3": [stat_row("T31", pts_pg=25)],
        "T4": [stat_row("T41", pts_pg=30)],
    }
    pool = [
        stat_row("P1", rank="1", value="100", pts_pg=30),
        stat_row("P2", rank="2", value="90", pts_pg=25),
        stat_row("P3", rank="3", value="80", pts_pg=20),
    ]
    shifted_teams = {
        team: [stat_row(row["name"], pts_pg=float(row["pts_pg"]) + 10)]
        for team, rows in teams.items()
        for row in rows
    }
    shifted_pool = [
        stat_row(row["name"], rank=row["rank"], value=row["value"],
                 pts_pg=float(row["pts_pg"]) + 10)
        for row in pool
    ]
    base = [
        s.name
        for s in recommend_need_aware(pool, set(), teams, my_team="Me")
    ]
    shifted_order = [
        s.name
        for s in recommend_need_aware(shifted_pool, set(), shifted_teams, my_team="Me")
    ]
    assert base == ["P1", "P2", "P3"]
    assert base == shifted_order


def test_need_aware_reason_names_filled_cat():
    # The reason string names the engine CAT key that is actually filled.
    teams = {
        "Me": [stat_row("M1", to_pg=4, z_to=1)],
        "T2": [stat_row("T21", to_pg=1)],
        "T3": [stat_row("T31", to_pg=1)],
        "T4": [stat_row("T41", to_pg=1)],
    }
    pool = [stat_row("CleanHands", rank="1", value="50", to_pg=0.5)]
    (s,) = recommend_need_aware(pool, set(), teams, my_team="Me")
    assert "fills to gaps" in s.reason
    assert "pts" not in s.reason  # no pts gap -> pts never named


def test_need_aware_value_cell_passthrough():
    # A real value cell of "0" is distinct from a blank cell in the
    # Suggestion (the UI column); the reason is the P6 bits in both.
    rows = [
        row("Zeroed", rank="1", value="0"),
        row("Blank", rank="2", value=""),
    ]
    teams = {"Me": []}
    result = recommend_need_aware(rows, set(), teams, my_team="Me")
    assert result[0].value == "0"
    assert result[1].value == ""
    assert result[0].reason != result[1].reason


def test_cat_fill_clamped_to_unit_interval():
    # Higher cats: a candidate who beats the league max clamps at 1.0.
    # ``to``: a negative-to candidate clamps at 1.0, a league-worse one at 0.
    assert cat_fill("pts", 300.0, 100.0) == 1.0
    assert cat_fill("to", -10.0, 100.0) == 1.0
    assert cat_fill("to", 150.0, 100.0) == 0.0
    assert 0.0 <= cat_fill("fg_pct", 0.0, 0.2) <= 1.0


def test_need_aware_exclusions_and_top_n():
    pool = [
        stat_row("KeptOne", rank="1", value="90"),
        stat_row("FreshOne", rank="2", value="80"),
        stat_row("FreshTwo", rank="3", value="70"),
    ]
    teams = {"Me": [stat_row("M1")]}
    result = recommend_need_aware(
        pool, {"KeptOne"}, teams, my_team="Me", top_n=2
    )
    assert [s.name for s in result] == ["FreshOne", "FreshTwo"]
    assert not any(s.name in {"KeptOne"} for s in result)
    assert recommend_need_aware(
        [row("Only", "1")], {"Only"}, {"Me": []}, my_team="Me"
    ) == []
