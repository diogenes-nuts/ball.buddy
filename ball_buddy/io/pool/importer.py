"""Hashtag Basketball import-v4 parser and canonical players.csv I/O.

Parses a saved Hashtag `import-v4/fantasy-basketball-projections` page
(ASP.NET WebForms, single GridView) into the canonical player pool schema
used by every other component. Stdlib only.

Format notes (locked in agents/001_data/done.md, 001_data Phase 0 entry):
- Per-stat cells carry a visible value in `L{CAT}_{i}`, a quality bucket in
  hidden `HF{cat}zz_{i}`, and a z-score in hidden `HF{CAT}_{i}`.
- FG%/FT% cells carry an un-id'd `(FGM/FGA)` / `(FTM/FTA)` per-game span.
- Sticky pseudo-header `<tr>` rows (no ids) repeat every 13th row and are
  skipped by the id-keyed parse.
- POS is comma-separated in source (`PG,SG`) and normalized to slash.
- Player notes live in `data-bs-original-title` spans on the player cell.
"""

from __future__ import annotations

import csv
import html
import io
import os
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path


class ImportError(ValueError):
    """The page is not a usable Hashtag import-v4 export (bad table, no rows)."""


GRID_ID = "ContentPlaceHolder1_GridView1"
GP_FALLBACK = "82"

# Canonical players.csv column order.
FIELDNAMES: list[str] = [
    "name", "pos", "team", "gp", "mpg", "pts_pg", "reb_pg", "ast_pg",
    "stl_pg", "blk_pg", "to_pg", "fg_pct", "fga_pg", "ft_pct", "fta_pg",
    "three_pg", "adp_round", "rank", "value", "source",
    "z_fg_pct", "z_ft_pct", "z_three", "z_pts", "z_reb", "z_ast",
    "z_stl", "z_blk", "z_to", "adp_source", "notes",
]

# Per-stat field -> Hashtag stat id.
STAT_IDS: dict[str, str] = {
    "fg_pct": "FGP",
    "ft_pct": "FTP",
    "three_pg": "TGM",
    "pts_pg": "PTS",
    "reb_pg": "REB",
    "ast_pg": "AST",
    "stl_pg": "STL",
    "blk_pg": "BLK",
    "to_pg": "TUR",
}

# Per-stat field -> canonical z-score column (names are not uniform: z_pts, not z_pts_pg).
Z_FIELD_FOR: dict[str, str] = {
    "fg_pct": "z_fg_pct",
    "ft_pct": "z_ft_pct",
    "three_pg": "z_three",
    "pts_pg": "z_pts",
    "reb_pg": "z_reb",
    "ast_pg": "z_ast",
    "stl_pg": "z_stl",
    "blk_pg": "z_blk",
    "to_pg": "z_to",
}

VALID_POS: frozenset[str] = frozenset({"PG", "SG", "SF", "PF", "C"})

# DDPOSFROM select values -> ADP source label.
ADP_SOURCE_VALUES: dict[str, str] = {"1": "Yahoo", "2": "Fantrax", "3": "ESPN"}


@dataclass
class ParsedImport:
    """Result of parsing a saved Hashtag export page."""

    rows: list[dict[str, str]]
    adp_source: str = ""
    horizon: str = ""
    warnings: list[str] = field(default_factory=list)


def _clean(fragment: str) -> str:
    """Collapse whitespace and unescape an HTML text fragment."""
    return re.sub(r"\s+", " ", html.unescape(fragment)).strip()


def normalize_pos(raw: str) -> tuple[str, str | None]:
    """Normalize a comma-separated POS cell to our slash form (`PG/SG`)."""
    tokens = [t.strip().upper() for t in raw.split(",") if t.strip()]
    unknown = [t for t in tokens if t not in VALID_POS]
    if unknown:
        return "/".join(tokens), f"unknown POS token(s) {unknown} in {raw!r}"
    return "/".join(tokens), None


def normalize_gp(raw: str) -> tuple[str, str | None]:
    """Validate projected GP; fall back to a full season (82) when unusable."""
    cleaned = raw.strip()
    try:
        if float(cleaned) > 0:
            return str(int(float(cleaned))), None
    except ValueError:
        pass
    return GP_FALLBACK, f"gp {cleaned!r} missing/invalid; using fallback {GP_FALLBACK}"


def _selected_option(select_html: str) -> tuple[str, str]:
    """Return (value, label) of the selected <option>, or ("", "")."""
    for m in re.finditer(r"<option([^>]*)>([^<]*)</option>", select_html):
        if "selected" in m.group(1):
            vm = re.search(r'value="([^"]*)"', m.group(1))
            return (vm.group(1) if vm else "", m.group(2).strip())
    return "", ""


def detect_controls(page: str) -> tuple[str, str]:
    """Auto-detect (adp_source, projection horizon) from the saved controls."""
    adp_source = ""
    m = re.search(
        r'<select[^>]*id="ContentPlaceHolder1_DDPOSFROM"[^>]*>.*?</select>', page, re.S
    )
    if m:
        val, label = _selected_option(m.group(0))
        adp_source = ADP_SOURCE_VALUES.get(val, val or label)

    horizon = ""
    m = re.search(
        r'<select[^>]*id="ContentPlaceHolder1_DDDURATION"[^>]*>.*?</select>', page, re.S
    )
    if m:
        _, horizon = _selected_option(m.group(0))
    return adp_source, horizon


def _span_value(row_html: str, id_name: str, suffix: str) -> str:
    """Text of the id'd span `<span id="{GRID_ID}_{id_name}_{suffix}">`."""
    m = re.search(rf'id="{GRID_ID}_{id_name}_{suffix}"[^>]*>([^<]*)<', row_html)
    return _clean(m.group(1)) if m else ""


def _zvalue(row_html: str, suffix: str, cat_id: str) -> str:
    m = re.search(rf'id="{GRID_ID}_HF{cat_id}_{suffix}"[^>]*value="([^"]*)"', row_html)
    return m.group(1).strip() if m else ""


def _name(row_html: str, suffix: str) -> str:
    m = re.search(rf'id="{GRID_ID}_HyperLink1_{suffix}"[^>]*>([^<]+)<', row_html)
    return _clean(m.group(1)) if m else ""


def _notes(player_cell: str) -> str:
    bits = re.findall(r'data-bs-original-title="([^"]*)"', player_cell)
    return "; ".join(_clean(b) for b in bits if b.strip())


def _rate_pairs(cell_html: str) -> tuple[str, str]:
    """Extract (fgm/ftm, fga/fta) from the un-id'd `(m/a)` span of a cell."""
    m = re.search(r"\((\d+(?:\.\d+)?)/(\d+(?:\.\d+)?)\)", cell_html)
    if not m:
        return "", ""
    return m.group(1), m.group(2)


def _parse_table(
    table_html: str, adp_source: str, horizon: str
) -> tuple[list[dict[str, str]], list[str]]:
    rows: list[dict[str, str]] = []
    warns: list[str] = []
    provenance = " | ".join(p for p in ("Hashtag", horizon) if p)
    for row_html in re.findall(r"<tr[^>]*>(.*?)</tr>", table_html, re.S):
        m = re.search(rf'{GRID_ID}_LFGP_(\d+)"', row_html)
        if not m:
            continue  # header / sticky pseudo-header row
        suffix = m.group(1)
        suffixes = set(re.findall(rf'{GRID_ID}_[A-Za-z0-9]+_(\d+)"', row_html))
        if len(suffixes) > 1:
            warns.append(f"row idx {suffix}: mismatched cell ids {sorted(suffixes)}; skipped")
            continue

        tds = re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.S)
        if len(tds) < 17:
            warns.append(f"row idx {suffix}: only {len(tds)} cells; skipped")
            continue
        # The R# cell may carry a rank-change arrow span; take the leading number.
        rank_m = re.match(r"\s*(\d+)", tds[0])
        if not rank_m:
            warns.append(f"row idx {suffix}: non-numeric R# {_clean(tds[0])!r}; skipped")
            continue
        rank = rank_m.group(1)

        name = _name(row_html, suffix)
        pos_raw = _clean(tds[3])
        gp_raw = _clean(tds[5])
        _, ft_attempted = _rate_pairs(tds[8])
        _, fg_attempted = _rate_pairs(tds[7])
        notes = _notes(tds[1])

        rec: dict[str, str] = {f: "" for f in FIELDNAMES}
        rec["name"] = name
        rec["pos"], pos_warn = normalize_pos(pos_raw)
        if pos_warn:
            warns.append(f"{name or rank}: {pos_warn}")
        rec["team"] = _clean(tds[4])
        rec["gp"], gp_warn = normalize_gp(gp_raw)
        if gp_warn:
            warns.append(f"{name or rank}: {gp_warn}")
        rec["mpg"] = _clean(tds[6])
        rec["fga_pg"] = fg_attempted
        rec["fta_pg"] = ft_attempted
        rec["adp_round"] = _clean(tds[2])
        rec["rank"] = rank
        for stat, cat_id in STAT_IDS.items():
            rec[stat] = _span_value(row_html, f"L{cat_id}", suffix)
            rec[Z_FIELD_FOR[stat]] = _zvalue(row_html, suffix, cat_id)
        rec["value"] = _span_value(row_html, "Label1", suffix)
        rec["adp_source"] = adp_source
        rec["source"] = "Hashtag"
        rec["notes"] = f"{provenance} | {notes}" if notes else provenance
        rows.append(rec)
    return rows, warns


def validate_rows(rows: list[dict[str, str]]) -> list[str]:
    """Validate parsed rows; return a list of human-readable warnings.

    Blank stat/z cells are tolerated (every check is guarded by ``if raw:``),
    so non-Hashtag rows (e.g. Yahoo rows with empty stats from
    :mod:`ball_buddy.domain.reconcile`) pass with no warnings.
    """
    warns: list[str] = []
    seen_ranks: set[str] = set()
    for rec in rows:
        label = rec.get("name") or f"rank {rec.get('rank', '?')}"
        if not rec.get("name"):
            warns.append(f"rank {rec.get('rank', '?')}: missing name; skipped downstream use")
        if rec.get("rank") in seen_ranks:
            warns.append(f"{label}: duplicate rank {rec.get('rank')}")
        seen_ranks.add(rec.get("rank", ""))

        pos_tokens = rec.get("pos", "").split("/")
        unknown = [p for p in pos_tokens if p and p not in VALID_POS]
        if unknown:
            warns.append(f"{label}: unknown POS token(s) {unknown}")

        for stat in ("fg_pct", "ft_pct"):
            raw = rec.get(stat, "")
            if raw:
                try:
                    if not 0.0 < float(raw) <= 1.0:
                        warns.append(f"{label}: {stat}={raw} outside (0, 1]")
                except ValueError:
                    warns.append(f"{label}: {stat}={raw!r} is not numeric")

        for stat in Z_FIELD_FOR.values():
            raw = rec.get(stat, "")
            if raw:
                try:
                    float(raw)  # negatives allowed
                except ValueError:
                    warns.append(f"{label}: {stat}={raw!r} is not numeric")
    return warns


def parse_import(page: str) -> ParsedImport:
    """Parse a saved Hashtag export page into canonical rows (+ warnings)."""
    start = page.find(f'id="{GRID_ID}"')
    if start == -1:
        raise ImportError(f"table id='{GRID_ID}' not found in page")
    end = page.find("</table>", start)
    table_html = page[start:end] if end != -1 else page[start:]
    adp_source, horizon = detect_controls(page)
    rows, warns = _parse_table(table_html, adp_source, horizon)
    if not rows:
        raise ImportError("no data rows found in the Hashtag GridView")
    warns.extend(validate_rows(rows))
    return ParsedImport(rows=rows, adp_source=adp_source, horizon=horizon, warnings=warns)


def parse_file(path: str | Path) -> ParsedImport:
    """Read and parse a saved Hashtag export page from disk."""
    return parse_import(Path(path).read_text(encoding="utf-8"))


def write_csv(rows: list[dict[str, str]], path: str | Path) -> int:
    """Write canonical rows to CSV atomically (tmp file + os.replace).

    Returns the row count written.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=FIELDNAMES)
    writer.writeheader()
    writer.writerows(rows)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(buffer.getvalue())
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    return len(rows)


def load_players(path: str | Path) -> list[dict[str, str]]:
    """Load a canonical players.csv back into row dicts (for 002+ components)."""
    with open(path, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))
