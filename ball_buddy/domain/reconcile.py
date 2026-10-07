"""Pool reconcile: pure, name-joined merge of Hashtag and Yahoo player sets (P5).

Takes (a) fresh Hashtag import rows, (b) the existing pool rows (whatever
``players.csv`` currently holds, any source), and (c) a list of Yahoo
players (``{"name", "pos", "team", "status"}``, see
:func:`yahoo_players_from_snapshot`) and produces the merged pool rows plus a
loud :class:`ReconcileReport`.

Rules (no I/O — everything here is pure data in / data out):

- Hashtag is authoritative per player: an existing row whose (alias-mapped,
  normalized) name matches a Hashtag row is replaced wholesale by the
  Hashtag row — rank, stats, and everything else are ignored.
- Existing rows with no Hashtag counterpart survive untouched (kept).
- Every Hashtag row is written (``source="Hashtag"``).
- Every Yahoo player absent from both the Hashtag rows and the kept rows is
  appended via :func:`make_yahoo_row` (``source="Yahoo"``, blank stats).
- The join key is the normalized full name only. Alias entries
  (``{"roster name": "pool name"}``) are applied *before* normalizing so a
  Hashtag row can replace an existing row that lives under the alias target.

Yahoo players that match no Hashtag row are listed in
``report.orphans`` (whether they survived as kept rows or were appended
fresh) and named in ``report.summary_text()``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ball_buddy.domain.naming import normalize
from ball_buddy.io.pool.importer import FIELDNAMES

#: Yahoo position label -> pool position token (identity for the core five).
YAHOO_POS_MAP: dict[str, str] = {
    "PG": "PG",
    "SG": "SG",
    "SF": "SF",
    "PF": "PF",
    "C": "C",
    "G": "PG/SG",
    "F": "SF/PF",
    "G/F": "PG/SG/SF/PF",
    "UTIL": "UTL",
}


def _map_position(label: str) -> str:
    """Map one Yahoo position label to pool grammar; unknown passes through."""
    return YAHOO_POS_MAP.get(label, label.upper())


def yahoo_players_from_snapshot(snapshot: dict) -> list[dict]:
    """Collect the league's rostered Yahoo players from a snapshot doc.

    Walks ``snapshot["teams"][*]["players"]``, dedupes by normalized name
    (first occurrence wins), skips blank names, and emits
    ``{"name", "pos", "team", "status"}`` with ``pos`` mapped to pool
    grammar (``"/".join`` of the mapped labels).

    The free-agent pool is intentionally out of scope (needs auth); later
    callers can append an FA list to the returned list.
    """
    seen: set[str] = set()
    players: list[dict] = []
    for team in snapshot.get("teams") or []:
        team_name = team.get("name", "")
        for player in team.get("players") or []:
            name = (player.get("name") or "").strip()
            if not name:
                continue
            key = normalize(name)
            if key in seen:
                continue
            seen.add(key)
            labels = player.get("positions") or []
            players.append(
                {
                    "name": name,
                    "pos": "/".join(_map_position(p) for p in labels),
                    "team": team_name,
                    "status": player.get("status", ""),
                }
            )
    return players


def make_yahoo_row(name: str, pos: str, team: str) -> dict[str, str]:
    """Build a canonical pool row for a Yahoo-only player (blank stats)."""
    row = {f: "" for f in FIELDNAMES}
    row["name"] = name
    row["pos"] = pos
    row["team"] = team
    row["source"] = "Yahoo"
    return row


@dataclass
class ReconcileReport:
    """Loud accounting of one :func:`reconcile_pool` run."""

    added: int = 0
    replaced: int = 0
    kept: int = 0
    orphans: list[str] = field(default_factory=list)

    def summary_text(self) -> str:
        text = f"{self.replaced} replaced, {self.added} new, {self.kept} kept"
        if self.orphans:
            text += f" — orphans: {', '.join(self.orphans)}"
        return text


def _name_key(name: str, aliases: dict[str, str]) -> str:
    """Join key: map alias->pool name, then normalize (empty string = no key)."""
    resolved = aliases.get(name, name)
    return normalize(resolved)


def reconcile_pool(
    hashtag_rows: list[dict[str, str]],
    existing_rows: list[dict[str, str]],
    yahoo_players: list[dict],
    aliases: dict[str, str] | None = None,
) -> tuple[list[dict[str, str]], ReconcileReport]:
    """Merge Hashtag + existing pool + Yahoo players into canonical rows.

    Returns ``(rows, report)`` — see the module docstring for the rules.
    Existing rows are copied (input lists/dicts are not mutated); rows from
    either source lacking a ``source`` value are stamped ``"Hashtag"``
    (legacy pre-column pools were Hashtag-only).
    """
    aliases = aliases or {}
    report = ReconcileReport()

    hashtag = [dict(rec) for rec in hashtag_rows]
    for rec in hashtag:
        if not rec.get("source"):
            rec["source"] = "Hashtag"
    hashtag_keys = {
        key for key in (_name_key(rec.get("name", ""), aliases) for rec in hashtag) if key
    }

    kept: list[dict[str, str]] = []
    kept_keys: set[str] = set()
    for rec in existing_rows:
        row = dict(rec)
        if not row.get("source"):
            row["source"] = "Hashtag"
        key = _name_key(row.get("name", ""), aliases)
        if key and key in hashtag_keys:
            report.replaced += 1  # Hashtag authority replaces it wholesale
            continue
        kept.append(row)
        if key:
            kept_keys.add(key)
    report.kept = len(kept)

    rows = kept + hashtag
    report.added = len(hashtag)

    orphans: list[str] = []
    for player in yahoo_players:
        name = (player.get("name") or "").strip()
        if not name:
            continue
        key = _name_key(name, aliases)
        if not key:
            continue
        if key in hashtag_keys:
            continue  # Hashtag already covers this player
        if key not in kept_keys:
            rows.append(make_yahoo_row(name, player.get("pos", ""), player.get("team", "")))
            report.added += 1
            kept_keys.add(key)
        orphans.append(name)
    report.orphans = orphans

    return rows, report


__all__ = [
    "ReconcileReport",
    "YAHOO_POS_MAP",
    "make_yahoo_row",
    "reconcile_pool",
    "yahoo_players_from_snapshot",
]
