"""recommend() (M2.3) tests: pure top-N pool ranking on plain dict rows."""

from ball_buddy.domain.recommend import Suggestion, recommend


def row(name: str, rank: str = "", value: str = "", pos: str = "C") -> dict[str, str]:
    return {"name": name, "pos": pos, "rank": rank, "value": value}


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
    assert s == Suggestion("Someone", "PG/SG", "12.5", 7)
