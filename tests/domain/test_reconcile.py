"""Reconcile tests: Yahoo snapshot builder + pure pool merge (P5)."""

from ball_buddy.domain.players import PlayerPool
from ball_buddy.domain.reconcile import (
    YAHOO_POS_MAP,
    make_yahoo_row,
    reconcile_pool,
    yahoo_players_from_snapshot,
)
from ball_buddy.io.pool.importer import FIELDNAMES, validate_rows
from ball_buddy.io.yahoo.snapshot import to_snapshot
from tests.io.test_snapshot import LEAGUE_ID, load_results


def _row(**overrides) -> dict:
    """A canonical pool row with blanks; overrides win."""
    row = {f: "" for f in FIELDNAMES}
    row.update(overrides)
    return row


def _doc() -> dict:
    return to_snapshot(load_results(), LEAGUE_ID)


# ---------------------------------------------------------------- builder


def test_builder_collects_and_maps_positions():
    players = yahoo_players_from_snapshot(_doc())
    by_name = {p["name"]: p for p in players}
    assert by_name["Nikola Jokic"]["pos"] == "C"
    assert by_name["Nikola Jokic"]["team"] == "Red"
    assert by_name["Jokic"]["status"] == "IR"  # distinct normalized name, kept
    assert by_name["Shaquille O'Neal"]["team"] == "Blue"


def test_builder_dedupes_and_skips_blank_names():
    doc = _doc()
    # Duplicate name on a second team -> deduped; blank name -> skipped.
    doc["teams"].append(
        {"name": "Green", "players": [
            {"name": "Nikola Jokic", "positions": ["PG"], "status": "ACTIVE"},
            {"name": "", "positions": ["PG"], "status": "ACTIVE"},
        ]}
    )
    players = yahoo_players_from_snapshot(doc)
    jokics = [p for p in players if p["name"] == "Nikola Jokic"]
    assert len(jokics) == 1
    assert jokics[0]["team"] == "Red"  # first occurrence wins
    assert all(p["name"].strip() for p in players)
    # Ghost Player from the fixture has a real name, so it is included.
    assert "Ghost Player" in {p["name"] for p in players}


def test_builder_synthetic_position_labels():
    doc = {
        "teams": [
            {"name": "T", "players": [
                {"name": "Combo", "positions": ["G", "F"], "status": "ACTIVE"},
                {"name": "Flex", "positions": ["G/F", "UTIL"], "status": "ACTIVE"},
                {"name": "Weird", "positions": ["XYZ"], "status": "ACTIVE"},
            ]}
        ]
    }
    players = {p["name"]: p["pos"] for p in yahoo_players_from_snapshot(doc)}
    assert players["Combo"] == YAHOO_POS_MAP["G"] + "/" + YAHOO_POS_MAP["F"]
    assert players["Flex"] == "PG/SG/SF/PF/UTL"
    assert players["Weird"] == "XYZ"  # unknown labels pass through uppercased


def test_make_yahoo_row_shape():
    row = make_yahoo_row("Someone", "C", "Blue")
    assert set(row) == set(FIELDNAMES)
    assert row["name"] == "Someone" and row["pos"] == "C" and row["team"] == "Blue"
    assert row["source"] == "Yahoo"
    assert row["rank"] == "" and row["value"] == "" and row["z_pts"] == ""


# ---------------------------------------------------------------- reconcile


def test_hashtag_replaces_matched_ignoring_rank():
    existing = [_row(name="Nikola Jokic", rank="1", pts_pg="28.0", source="Hashtag")]
    hashtag = [_row(name="Nikola Jokic", rank="99", pts_pg="27.5", source="Hashtag")]
    rows, report = reconcile_pool(hashtag, existing, [])
    assert len(rows) == 1
    assert rows[0]["rank"] == "99" and rows[0]["pts_pg"] == "27.5"
    assert (report.added, report.replaced, report.kept) == (1, 1, 0)
    assert report.summary_text() == "1 replaced, 1 new, 0 kept"


def test_alias_maps_hashtag_to_existing_pool_name():
    existing = [_row(name="Jokic", rank="1", source="Hashtag")]
    hashtag = [_row(name="Nikola Jokic", rank="5", source="Hashtag")]
    rows, report = reconcile_pool(hashtag, existing, [], aliases={"Jokic": "Nikola Jokic"})
    assert len(rows) == 1
    assert rows[0]["name"] == "Nikola Jokic"  # Hashtag row wins
    assert (report.added, report.replaced, report.kept) == (1, 1, 0)


def test_yahoo_only_row_survives_repeated_imports():
    existing = [_row(name="League Only", pos="C", source="Yahoo")]
    rows, report = reconcile_pool([_row(name="Nikola Jokic")], existing, [])
    assert [r["name"] for r in rows] == ["League Only", "Nikola Jokic"]
    # A second Hashtag import still keeps the Yahoo-only row.
    rows2, report2 = reconcile_pool(
        [_row(name="Nikola Jokic"), _row(name="Another")], rows, []
    )
    assert [r["name"] for r in rows2] == ["League Only", "Nikola Jokic", "Another"]
    assert (report2.kept, report2.replaced) == (1, 1)  # Jokic replaced, League Only kept


def test_yahoo_player_absent_everywhere_is_appended():
    existing = []
    hashtag = [_row(name="Nikola Jokic", source="Hashtag")]
    yahoo = [
        {"name": "Nikola Jokic", "pos": "C", "team": "Red", "status": "ACTIVE"},
        {"name": "Fresh Face", "pos": "G", "team": "Blue", "status": "ACTIVE"},
    ]
    rows, report = reconcile_pool(hashtag, existing, yahoo)
    fresh = next(r for r in rows if r["name"] == "Fresh Face")
    assert fresh["source"] == "Yahoo" and fresh["pos"] == "G" and fresh["team"] == "Blue"
    assert fresh["rank"] == "" and fresh["z_pts"] == ""
    assert sum(1 for r in rows if r["name"] == "Nikola Jokic") == 1  # Hashtag copy only
    assert report.added == 2  # 1 hashtag + 1 yahoo


def test_orphans_reported_in_summary():
    existing = [_row(name="Kept One", rank="4", source="Hashtag")]
    hashtag = [_row(name="Nikola Jokic", source="Hashtag")]
    yahoo = [
        # matches an existing kept row -> orphan, but not re-appended
        {"name": "Kept One", "pos": "C", "team": "Red", "status": "ACTIVE"},
        # matches nothing at all -> orphan, appended fresh
        {"name": "Stray Guy", "pos": "C", "team": "Blue", "status": "ACTIVE"},
    ]
    rows, report = reconcile_pool(hashtag, existing, yahoo)
    assert report.orphans == ["Kept One", "Stray Guy"]
    assert "Stray Guy" in report.summary_text() and "Kept One" in report.summary_text()
    assert sum(1 for r in rows if r["name"] == "Kept One") == 1  # kept once, not dup'd
    assert any(r["name"] == "Stray Guy" and r["source"] == "Yahoo" for r in rows)


def test_blank_stats_rows_pass_validate_and_load(tmp_path):
    row = make_yahoo_row("Nobody", "C", "")
    assert row["rank"] == ""
    # Blank stats/rank produce no stat/rank warnings (all checks are `if raw:`).
    blank_warns = validate_rows([row])
    assert not [w for w in blank_warns if "numeric" in w or "outside" in w]
    # A row with a name but no rank is still tolerable (no name warning).
    assert not [w for w in blank_warns if "missing name" in w]

    import csv

    path = tmp_path / "players.csv"
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerow(row)
    pool = PlayerPool.load(path)
    assert pool.names() == ["Nobody"]
    from ball_buddy.domain.recommend import _parse_rank

    assert _parse_rank(row["rank"]) is None
