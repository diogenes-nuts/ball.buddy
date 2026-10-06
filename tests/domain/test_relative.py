"""category_tags (P3 relative panel) tests.

Plain dict rows, pure stdlib — no Qt, no I/O. Uses canonical FIELDNAMES
stat rows so the engine's category projections are exercised for real
(gp fixed at 70; per-game rates scale to season totals).

Fixture shape: 12 teams x 1 keeper player; per-test overrides vary one
category so exactly that category has a non-zero league spread and the
other 8 categories stay at spread 0 (all-COAST noise floor).
"""

from ball_buddy.domain.relative import BUILD, COAST, PUNT, category_tags

NAMES = [
    "Alpha", "Bravo", "Charlie", "Delta", "Echo", "Foxtrot",
    "Golf", "Hotel", "India", "Juliet", "Kilo", "Lima",
]


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
) -> dict[str, str]:
    """A full canonical FIELDNAMES row (name/pos/rank/value + stats + gp)."""
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
    }


def twelve_teams(overrides: dict[str, dict] | None = None) -> dict[str, list[dict[str, str]]]:
    """12 teams, one keeper each; ``overrides`` patches stat kwargs per team."""
    overrides = overrides or {}
    return {
        name: [stat_row(f"KP-{name}", **overrides.get(name, {}))] for name in NAMES
    }


def by_cat(tags: list) -> dict[str, object]:
    return {tag.cat: tag for tag in tags}


def test_top_team_builds_and_flat_cats_coast():
    # Alpha has the league-best pts (12.0 x 70 = 840 vs 11..1 x 70); every
    # other category is identical league-wide (spread 0 -> COAST).
    teams = {
        name: [stat_row(f"KP-{name}", pts_pg=float(13 - i))]
        for i, name in enumerate(NAMES, start=1)
    }
    tags = by_cat(category_tags(teams, "Alpha", [], set()))
    assert tags["pts"].tag == BUILD
    assert tags["pts"].rank == 1
    assert tags["pts"].gap < 0  # ahead: negative gap in the better direction
    for cat in ("reb", "ast", "stl", "blk", "to", "three", "fg_pct", "ft_pct"):
        assert tags[cat].tag == COAST
        assert tags[cat].rank is not None


def test_bottom_punt_when_pool_cannot_close():
    # Alpha last at reb (1 x 70 = 70 vs 10 x 70 = 700; median 700, spread
    # 630, gap_norm 1.0). A zero-reb pool can't close 25% of the gap.
    teams = twelve_teams({"Alpha": {"reb_pg": 1.0}})
    for name in NAMES[1:]:
        teams[name][0] = stat_row(f"KP-{name}", reb_pg=10.0)
    pool = [stat_row("Reb Zero", reb_pg=0.0)]
    tags = by_cat(category_tags(teams, "Alpha", pool, set()))
    assert tags["reb"].tag == PUNT
    assert tags["reb"].rank == 12
    assert tags["reb"].best_fill_norm == 0.0
    assert tags["reb"].gap_norm == 1.0


def test_bottom_coast_when_pool_closes_the_gap():
    # Same reb setup, but the pool's best reb player fills 210/630 =
    # 0.333 >= 0.25 x gap_norm(1.0) -> salvageable -> COAST.
    teams = twelve_teams({"Alpha": {"reb_pg": 1.0}})
    for name in NAMES[1:]:
        teams[name][0] = stat_row(f"KP-{name}", reb_pg=10.0)
    pool = [stat_row("Reb Closer", reb_pg=3.0)]
    tags = by_cat(category_tags(teams, "Alpha", pool, set()))
    assert tags["reb"].tag == COAST
    assert abs(tags["reb"].best_fill_norm - 210.0 / 630.0) < 1e-12


def test_middle_team_coasts():
    # 12 pts tiers 1..12; Golf (7th, 490) is rank 6 — neither in the top 3
    # (BUILD) nor bottom 3 (PUNT candidate) -> COAST.
    teams = {
        name: [stat_row(f"KP-{name}", pts_pg=float(i))]
        for i, name in enumerate(NAMES, start=1)
    }
    tags = by_cat(category_tags(teams, "Golf", [], set()))
    assert tags["pts"].tag == COAST
    assert tags["pts"].rank == 6


def test_to_direction_lowest_tos_builds():
    # Lower-is-better category: Alpha with the league-lowest TO (1 x 70)
    # is rank 1 -> BUILD.
    teams = twelve_teams({"Alpha": {"to_pg": 1.0}})
    for name in NAMES[1:]:
        teams[name][0] = stat_row(f"KP-{name}", to_pg=2.0)
    tags = by_cat(category_tags(teams, "Alpha", [], set()))
    assert tags["to"].tag == BUILD
    assert tags["to"].rank == 1


def test_to_direction_highest_tos_punts_with_weak_pool():
    # Alpha worst at TO (12 x 70 = 840 vs 1..11 x 70; median 455, spread
    # 770, gap 385 -> gap_norm 0.5). A high-TO pool player (11 x 70 =
    # 770) fills 1 - 770/770 = 0.0 < 0.25 x gap_norm -> PUNT.
    teams = twelve_teams({"Alpha": {"to_pg": 12.0}})
    for i, name in enumerate(NAMES[1:], start=1):
        teams[name][0] = stat_row(f"KP-{name}", to_pg=float(i))
    pool = [stat_row("Clumsy", to_pg=11.0)]
    tags = by_cat(category_tags(teams, "Alpha", pool, set()))
    assert tags["to"].tag == PUNT
    assert tags["to"].rank == 12
    assert tags["to"].gap == 385.0
    assert tags["to"].best_fill_norm == 0.0


def test_fallbacks_return_none():
    teams = twelve_teams()
    assert category_tags({}, "Alpha", [], set()) is None
    assert category_tags(teams, "", [], set()) is None
    assert category_tags(teams, "Nobody", [], set()) is None


def test_all_zero_teams_all_coast():
    # Every roster empty -> every category flat across the league -> no
    # signal, all COAST (pre-draft guard).
    tags = category_tags({name: [] for name in NAMES[:4]}, "Alpha", [], set())
    assert tags is not None
    assert {tag.tag for tag in tags} == {COAST}
    assert all(tag.rank is not None for tag in tags)


def test_punt_threshold_boundaries():
    # 4 teams, Alpha last at pts (0 vs 280/420/560 x 70gp): median 350,
    # spread 560, gap_norm 350/560 = 0.625. Punt threshold = 0.25 x
    # gap_norm = exactly 87.5/560 (a pool fill of pts_pg 1.25 x 70gp).
    teams = {
        "Alpha": [stat_row("KP-Alpha", pts_pg=0.0)],
        "B1": [stat_row("KP-B1", pts_pg=4.0)],
        "B2": [stat_row("KP-B2", pts_pg=6.0)],
        "B3": [stat_row("KP-B3", pts_pg=8.0)],
    }
    # fill exactly 0.25 x gap_norm: NOT strictly below -> COAST.
    tags = by_cat(category_tags(teams, "Alpha", [stat_row("Edge", pts_pg=1.25)], set()))
    assert tags["pts"].tag == COAST
    assert abs(tags["pts"].best_fill_norm - 87.5 / 560.0) < 1e-12
    # just under (86.8/560 < 87.5/560) -> PUNT.
    tags = by_cat(
        category_tags(teams, "Alpha", [stat_row("Edge", pts_pg=1.24)], set())
    )
    assert tags["pts"].tag == PUNT


def test_excluded_pool_rows_are_ignored_for_fill():
    # A strong reb player who is excluded (already drafted/kept) must not
    # rescue the category: the fill search skips it.
    teams = twelve_teams({"Alpha": {"reb_pg": 1.0}})
    for name in NAMES[1:]:
        teams[name][0] = stat_row(f"KP-{name}", reb_pg=10.0)
    pool = [stat_row("Reb Closer", reb_pg=3.0), stat_row("Reb Zero", reb_pg=0.0)]
    tags = by_cat(
        category_tags(teams, "Alpha", pool, {"Reb Closer"})
    )
    assert tags["reb"].tag == PUNT
    assert tags["reb"].best_fill_norm == 0.0
