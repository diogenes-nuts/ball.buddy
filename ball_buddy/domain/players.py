"""Local player pool (canonical players.csv).

Reads the pool written by the in-app Hashtag import
(:mod:`ball_buddy.io.pool.importer`) into an in-memory index keyed by
normalized name for the name-bridging ladder (``domain/naming.py``).
"""

from __future__ import annotations

from pathlib import Path

from ball_buddy.domain.naming import normalize
from ball_buddy.io.pool.importer import FIELDNAMES, load_players


class PlayerPool:
    """The local player pool with a normalized-name index."""

    def __init__(self, rows: list[dict[str, str]]) -> None:
        self.rows: list[dict[str, str]] = [
            row for row in rows if row.get("name")
        ]
        self._by_name: dict[str, list[dict[str, str]]] = {}
        for row in self.rows:
            key = normalize(row["name"])
            self._by_name.setdefault(key, []).append(row)
        self._by_raw: dict[str, dict[str, str]] = {
            row["name"]: row for row in self.rows
        }

    def __len__(self) -> int:
        return len(self.rows)

    def names(self) -> list[str]:
        """All pool player names (display form)."""
        return [row["name"] for row in self.rows]

    def get(self, name: str) -> dict[str, str] | None:
        """Exact (normalized) lookup; first row when duplicates exist."""
        rows = self._by_name.get(normalize(name))
        return rows[0] if rows else None

    def candidates(self, name: str) -> list[dict[str, str]]:
        """All rows sharing a normalized name (ambiguity detection)."""
        return list(self._by_name.get(normalize(name), []))

    def all(self) -> list[dict[str, str]]:
        return list(self.rows)

    @classmethod
    def load(cls, path: str | Path) -> PlayerPool:
        """Load ``players.csv`` (must have the canonical FIELDNAMES header)."""
        path = Path(path)
        if not path.exists():
            return cls([])
        with open(path, encoding="utf-8", newline="") as handle:
            header = handle.readline().strip()
        if header != ",".join(FIELDNAMES):
            raise ValueError(
                f"{path} does not look like a ball.buddy players.csv "
                "(import one via the League view first)"
            )
        return cls(load_players(path))


__all__ = ["PlayerPool", "load_players"]
