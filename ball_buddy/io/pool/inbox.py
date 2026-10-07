"""Drop-folder auto-import of Hashtag import-v4 HTML exports (P4).

Headless (no Qt). A user drops saved Hashtag export pages into
``data/inbox/``; :func:`scan_inbox` (run at launch and on "Rescan inbox")
parses each new/changed ``*.html`` in sort order and rewrites
``data/players.csv``, keeping the previous file at ``data/players.prev.csv``
so the last import can be undone. Per-file state (SHA-256) lives in
``data/inbox_state.json`` via :mod:`ball_buddy.io.state`; unchanged files are
skipped, unparseable files are reported (and left in place).
"""

from __future__ import annotations

import hashlib
import os
import shutil
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from ball_buddy.io.pool.importer import ImportError, parse_file, write_csv
from ball_buddy.io.state import StateError, load_json, save_json

VERSION = 1

_STATE_KEY = "files"


@dataclass
class ImportedEntry:
    """One file successfully imported by a scan."""

    file: str
    players: int
    imported_at: str


@dataclass
class InboxError:
    """One file that could not be parsed (it stays in the inbox)."""

    file: str
    message: str


@dataclass
class InboxOutcome:
    """Result of one :func:`scan_inbox` pass."""

    imported: list[ImportedEntry] = field(default_factory=list)
    errors: list[InboxError] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)


def inbox_dir(data_dir: str | Path) -> Path:
    """The drop folder (``data/inbox``), created on demand."""
    path = Path(data_dir) / "inbox"
    path.mkdir(parents=True, exist_ok=True)
    return path


def state_path(data_dir: str | Path) -> Path:
    return Path(data_dir) / "inbox_state.json"


def in_inbox(data_dir: str | Path, path: str | Path) -> bool:
    """True when ``path`` lives inside the inbox folder (canonical comparison,
    so relative/symlinked dialog results compare equal; no mkdir side effect).
    """
    try:
        return (
            Path(path).resolve().parent
            == (Path(data_dir) / "inbox").resolve()
        )
    except OSError:
        return False


def load_state(data_dir: str | Path) -> dict:
    """Load the per-file state map; a missing or corrupt file yields ``{}``."""
    try:
        raw = load_json(state_path(data_dir), VERSION)
    except StateError:
        return {}
    return raw or {}


def save_state(data_dir: str | Path, state: dict) -> None:
    save_json(state, state_path(data_dir), VERSION)


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _prev_pool_path(data_dir: str | Path) -> Path:
    return Path(data_dir) / "players.prev.csv"


def restore_prev_pool(data_dir: str | Path) -> bool:
    """Undo the last inbox import: ``players.prev.csv`` -> ``players.csv``.

    Returns True when a previous pool existed and was restored.
    """
    prev = _prev_pool_path(data_dir)
    if not prev.exists():
        return False
    os.replace(prev, Path(data_dir) / "players.csv")
    return True


def record_import(
    data_dir: str | Path, path: str | Path, players: int | None = None
) -> bool:
    """Record ``path``'s SHA-256 in the state file (cheap manual-flow dedupe).

    Only applies to files inside the inbox folder; any other path is a no-op.
    Returns True when the state was updated.
    """
    path = Path(path)
    if not in_inbox(data_dir, path):
        return False
    state = load_state(data_dir)
    files = state.setdefault(_STATE_KEY, {})
    entry = dict(files.get(path.name) or {})
    entry["sha256"] = sha256_file(path)
    entry["imported_at"] = datetime.now(UTC).isoformat()
    if players is not None:
        entry["players"] = players
    files[path.name] = entry
    save_state(data_dir, state)
    return True


def scan_inbox(data_dir: str | Path) -> InboxOutcome:
    """Import every new/changed ``*.html`` in the inbox (sort order).

    Per file: same stored SHA-256 -> unchanged; parse failure -> reported
    error (file stays, scan continues); success -> the pool is replaced and
    the state entry is updated. Each successful import is state-committed
    before the next file is touched.

    Undo is per scan, not per file: the existing ``players.csv`` is saved
    once as ``players.prev.csv`` before the first import of this scan, so
    :func:`restore_prev_pool` returns to the pre-import pool even when a
    scan ingests several files.
    """
    outcome = InboxOutcome()
    state = load_state(data_dir)
    files = state.setdefault(_STATE_KEY, {})
    pool_path = Path(data_dir) / "players.csv"
    prev_saved = False

    for path in sorted(inbox_dir(data_dir).glob("*.html")):
        digest = sha256_file(path)
        stored = files.get(path.name) or {}
        if stored.get("sha256") == digest:
            outcome.unchanged.append(path.name)
            continue
        try:
            parsed = parse_file(path)
        except ImportError as exc:
            outcome.errors.append(InboxError(path.name, str(exc)))
            continue

        if pool_path.exists() and not prev_saved:
            shutil.copyfile(pool_path, _prev_pool_path(data_dir))
            prev_saved = True
        write_csv(parsed.rows, pool_path)

        imported_at = datetime.now(UTC).isoformat()
        files[path.name] = {
            "sha256": digest,
            "imported_at": imported_at,
            "players": len(parsed.rows),
        }
        save_state(data_dir, state)
        outcome.imported.append(
            ImportedEntry(file=path.name, players=len(parsed.rows), imported_at=imported_at)
        )
    return outcome


__all__ = [
    "InboxError",
    "InboxOutcome",
    "ImportedEntry",
    "VERSION",
    "inbox_dir",
    "in_inbox",
    "load_state",
    "record_import",
    "restore_prev_pool",
    "save_state",
    "scan_inbox",
    "sha256_file",
    "state_path",
]
