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

from ball_buddy.domain.reconcile import reconcile_pool, yahoo_players_from_snapshot
from ball_buddy.io.pool.importer import ImportError, load_players, parse_file, write_csv
from ball_buddy.io.state import StateError, load_json, save_json
from ball_buddy.io.yahoo.snapshot import SnapshotError, load_snapshot

VERSION = 1

_STATE_KEY = "files"


@dataclass
class ImportedEntry:
    """One file successfully imported by a scan."""

    file: str
    players: int
    imported_at: str
    note: str = ""  # reconcile_pool summary for this file


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


def _snapshot_players(data_dir: str | Path) -> list[dict]:
    """Rostered Yahoo players from the last snapshot (``[]`` when absent/corrupt)."""
    try:
        document = load_snapshot(Path(data_dir) / "snapshot.json")
    except SnapshotError:
        return []
    return yahoo_players_from_snapshot(document) if document else []


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

    The incoming rows are reconciled against the existing pool via
    :func:`ball_buddy.domain.reconcile.reconcile_pool` before writing
    (Hashtag rows replace matches by normalized name; existing rows that
    match nothing survive). Rostered players from the last saved Yahoo
    snapshot (``data/snapshot.json``, if any) are fed in as the Yahoo side:
    players absent everywhere are appended with blank stats. The scan is
    headless, so the alias table is intentionally left empty: the inbox
    merge is exact-normalized only — do not expect alias-aware merges here
    (the in-app import dialog is alias-aware).

    The per-file reconcile summary is stored in each
    :class:`ImportedEntry`'s ``note`` so callers can surface it.
    """
    outcome = InboxOutcome()
    state = load_state(data_dir)
    files = state.setdefault(_STATE_KEY, {})
    pool_path = Path(data_dir) / "players.csv"
    yahoo_players = _snapshot_players(data_dir)
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
        existing = load_players(pool_path) if pool_path.exists() else []
        rows, report = reconcile_pool(parsed.rows, existing, yahoo_players)
        write_csv(rows, pool_path)

        imported_at = datetime.now(UTC).isoformat()
        files[path.name] = {
            "sha256": digest,
            "imported_at": imported_at,
            "players": len(rows),
        }
        save_state(data_dir, state)
        outcome.imported.append(
            ImportedEntry(
                file=path.name,
                players=len(rows),
                imported_at=imported_at,
                note=report.summary_text(),
            )
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
