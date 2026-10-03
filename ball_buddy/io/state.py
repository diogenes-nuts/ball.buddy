"""Atomic JSON persistence (salvaged from autodraft ``state.py``, generalized).

Saves go through a same-directory temp file + ``os.replace`` so a crash never
leaves a half-written file behind. Every document carries a ``version`` and a
UTC ``updated_at``; :func:`load_json` rejects other versions and malformed
files with :class:`StateError` instead of returning half-valid data.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path


class StateError(ValueError):
    """A JSON document is malformed, unreadable, or from a different version."""


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def save_json(payload: dict, path: str | Path, version: int) -> None:
    """Write ``payload`` to ``path`` atomically (tmp file + os.replace).

    Adds ``version`` and a UTC ``updated_at`` to the document; payload keys
    take precedence if they already set either.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    document = {"version": version, "updated_at": _now_iso()}
    document.update(payload)
    data = json.dumps(document, indent=2, ensure_ascii=False) + "\n"
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(data)
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def load_json(path: str | Path, expected_version: int) -> dict | None:
    """Read and validate a document; ``None`` if the file does not exist.

    Raises :class:`StateError` on invalid JSON, a non-object document, or a
    version mismatch.
    """
    path = Path(path)
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise StateError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise StateError(f"{path} must contain a JSON object")
    version = raw.get("version")
    if version != expected_version:
        raise StateError(
            f"{path} has version {version!r}; this build expects {expected_version}"
        )
    return raw
