"""Tests for the salvaged Hashtag importer (re-parented verbatim; paths only)."""

import copy
from pathlib import Path

import pytest

from ball_buddy.io.pool.importer import (
    FIELDNAMES,
    GP_FALLBACK,
    normalize_gp,
    normalize_pos,
    parse_file,
    parse_import,
    validate_rows,
)

FIXTURE = "tests/fixtures/hashtag_sample.html"
FULL_EXPORT = "data/hashtag_import.html"


def test_parse_sample_rows():
    parsed = parse_file(FIXTURE)
    assert len(parsed.rows) == 3  # header + 1 pseudo-header row are skipped
    assert parsed.warnings == []
    assert parsed.adp_source == "Yahoo"
    assert parsed.horizon == "2026-27 Rest of Season Projections"


def test_parse_sample_jokic():
    jokic = parse_file(FIXTURE).rows[0]
    assert jokic["name"] == "Nikola Jokic"
    assert jokic["rank"] == "1"
    assert jokic["adp_round"] == "2.9"
    assert jokic["pos"] == "C"
    assert jokic["team"] == "DEN"
    assert jokic["gp"] == "72"
    assert jokic["mpg"] == "35.1"
    assert jokic["fg_pct"] == "0.573"
    assert jokic["fga_pg"] == "18.3"
    assert jokic["ft_pct"] == "0.816"
    assert jokic["fta_pg"] == "6.8"
    assert jokic["three_pg"] == "1.8"
    assert jokic["pts_pg"] == "28.4"
    assert jokic["reb_pg"] == "12.7"
    assert jokic["ast_pg"] == "10.4"
    assert jokic["stl_pg"] == "1.6"
    assert jokic["blk_pg"] == "0.7"
    assert jokic["to_pg"] == "3.5"
    assert jokic["value"] == "15.90"
    assert jokic["z_fg_pct"] == "3.9157881000"
    assert jokic["z_to"] == "2.2636246822"
    assert jokic["adp_source"] == "Yahoo"
    assert jokic["notes"].startswith("Hashtag | 2026-27 Rest of Season Projections")
    assert "Games-played risk (& wear)." in jokic["notes"]


def test_parse_sample_trailing_row():
    faller = parse_file(FIXTURE).rows[2]
    assert faller["pos"] == "SF/PF"  # comma-separated source normalized to slash
    assert faller["adp_round"] == ""  # late pool has no ADP
    assert faller["z_blk"] == "-1.2500000000"  # negative z-scores allowed
    assert "Depth piece & rotation risk." in faller["notes"]
    assert faller["value"] == "0.12"


def test_parse_raises_without_table():
    with pytest.raises(ValueError, match="not found"):
        parse_import("<html><body>no grid view here</body></html>")


def test_parse_raises_without_data_rows():
    page = (
        '<table id="ContentPlaceHolder1_GridView1">'
        "<tr><th>R#</th><th>PLAYER</th></tr></table>"
    )
    with pytest.raises(ValueError, match="no data rows"):
        parse_import(page)


def test_normalize_pos():
    assert normalize_pos("PG,SG") == ("PG/SG", None)
    assert normalize_pos("C") == ("C", None)
    pos, warn = normalize_pos("X,PF")
    assert pos == "X/PF"
    assert warn is not None and "X" in warn


def test_normalize_gp():
    assert normalize_gp("72") == ("72", None)
    gp, warn = normalize_gp("")
    assert gp == GP_FALLBACK
    assert warn is not None
    gp, warn = normalize_gp("0")
    assert gp == GP_FALLBACK
    assert warn is not None


def test_validate_rows_flags_bad_values():
    bad = copy.deepcopy(parse_file(FIXTURE).rows[0])
    bad["name"] = ""
    bad["rank"] = "x1"
    bad["pos"] = "PG/X"
    bad["fg_pct"] = "2.00"
    bad["z_pts"] = "abc"
    warns = validate_rows([bad])
    joined = "\n".join(warns)
    assert "missing name" in joined
    assert "unknown POS token" in joined
    assert "fg_pct" in joined
    assert "z_pts" in joined


def test_write_csv_round_trip(tmp_path):
    from ball_buddy.io.pool.importer import load_players, write_csv

    rows = parse_file(FIXTURE).rows
    out = tmp_path / "players.csv"
    assert write_csv(rows, out) == 3
    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert lines[0] == ",".join(FIELDNAMES)
    assert len(lines) == 4  # header + 3 players
    assert load_players(out) == rows


@pytest.mark.skipif(
    not Path(FULL_EXPORT).exists(),
    reason="saved premium export (data/hashtag_import.html) not present",
)
def test_full_export_anchors():
    parsed = parse_file(FULL_EXPORT)
    assert len(parsed.rows) == 200
    assert parsed.adp_source == "Yahoo"
    first = parsed.rows[0]
    assert first["name"] == "Nikola Jokic"
    assert first["rank"] == "1"
    assert first["value"] == "15.90"
    assert first["adp_round"] == "2.9"
    assert first["gp"] == "72"
    assert first["fg_pct"] == "0.573"
    assert first["fga_pg"] == "18.3"
    assert first["fta_pg"] == "6.8"
    assert parsed.rows[1]["value"] == "14.25"
    assert parsed.rows[2]["value"] == "14.10"
    assert all(len(r) == len(FIELDNAMES) for r in parsed.rows)
