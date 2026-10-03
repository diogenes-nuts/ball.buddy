"""SyncService: auth -> fetch -> snapshot -> name-bridge report (headless).

No Qt. The UI drives it from a QThread via :meth:`run`, which returns a
:class:`SyncResult`. Failures are typed, never raised through the thread:

- :class:`client.LoginRequiredError` -> ``needs_login`` (R2, no crash);
- any other error -> ``error`` message for the status banner.

Offline fallback: when a sync cannot happen (no token, no network),
:meth:`load_last` returns the previously saved snapshot and its age, and the
UI shows a "stale — last synced <ts>" banner (plan §3).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from ball_buddy.domain.naming import MatchReport, bridge
from ball_buddy.domain.players import PlayerPool
from ball_buddy.io.yahoo import auth
from ball_buddy.io.yahoo import snapshot as snapshot_mod
from ball_buddy.io.yahoo.client import LoginRequiredError, YahooClient, YahooError


@dataclass
class SyncResult:
    """Outcome of one :meth:`SyncService.run` call (thread-safe payload)."""

    ok: bool = False
    error: str = ""
    needs_login: bool = False
    snapshot: dict | None = None
    report: MatchReport | None = None
    snapshot_age_seconds: float | None = None
    extra: dict = field(default_factory=dict)


class SyncService:
    """One service per data directory (``data/`` at the repo root)."""

    def __init__(self, data_dir: str | Path, client: YahooClient | None = None) -> None:
        self.data_dir = Path(data_dir)
        self._client = client
        self.snapshot_path = self.data_dir / "snapshot.json"
        self.aliases_path = self.data_dir / "aliases.json"
        self.pool_path = self.data_dir / "players.csv"

    # -- settings ------------------------------------------------------------

    def settings(self) -> dict:
        return auth.load_settings(self.data_dir)

    def save_settings(self, settings: dict) -> None:
        auth.save_settings(self.data_dir, settings)

    @property
    def logged_in(self) -> bool:
        return self.data_dir.joinpath("yahoo_tokens.json").exists()

    def save_aliases(self, aliases: dict[str, str]) -> None:
        """Persist the user-editable alias table (``{"roster": "pool"}``)."""
        self.aliases_path.parent.mkdir(parents=True, exist_ok=True)
        self.aliases_path.write_text(
            json.dumps(aliases, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    def load_aliases(self) -> dict[str, str]:
        if not self.aliases_path.exists():
            return {}
        try:
            raw = json.loads(self.aliases_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        return raw if isinstance(raw, dict) else {}

    # -- sync ----------------------------------------------------------------

    def _build_client(self) -> YahooClient:
        if self._client is not None:
            return self._client
        tokens = auth.load_tokens(self.data_dir)
        settings = self.settings()
        self._client = YahooClient.from_settings(settings, tokens)
        return self._client

    def run(self) -> SyncResult:
        """Full sync: fetch all sections, save snapshot, bridge names.

        Raises nothing for auth/network failures — they are encoded in the
        returned :class:`SyncResult`.
        """
        result = SyncResult()
        try:
            client = self._build_client()
        except LoginRequiredError as exc:
            result.needs_login = True
            result.error = str(exc)
            result.snapshot_age_seconds = self._age()
            return result

        try:
            results = client.fetch_all()
        except LoginRequiredError as exc:
            result.needs_login = True
            result.error = str(exc)
            result.snapshot_age_seconds = self._age()
            return result
        except YahooError as exc:
            result.error = str(exc)
            result.snapshot_age_seconds = self._age()
            return result

        settings = self.settings()
        manual_order = settings.get("manual_draft_order") or None
        document = snapshot_mod.to_snapshot(
            results, str(settings.get("league_id", "")), manual_order
        )
        snapshot_mod.save_snapshot(document, self.snapshot_path)
        client.persist_token(self.data_dir)

        result.ok = True
        result.snapshot = document
        result.report = self.bridge_names(document)
        return result

    def load_last(self) -> SyncResult:
        """Offline fallback: the last saved snapshot + its age (or empty)."""
        result = SyncResult()
        result.snapshot_age_seconds = self._age()
        if not self.snapshot_path.exists():
            return result
        try:
            document = snapshot_mod.load_snapshot(self.snapshot_path)
        except snapshot_mod.SnapshotError as exc:
            result.error = str(exc)
            return result
        result.snapshot = document
        if document is not None and self.pool_path.exists():
            try:
                result.report = self.bridge_names(document)
            except (ValueError, OSError):
                pass
        return result

    # -- bridging --------------------------------------------------------------

    def bridge_names(self, document: dict) -> MatchReport:
        """Bridge every roster player name in ``document`` against the pool."""
        pool = PlayerPool.load(self.pool_path)
        roster_names: list[str] = []
        for team in document.get("teams", []):
            roster_names.extend(p["name"] for p in team.get("players", []) if p.get("name"))
        return bridge(roster_names, pool.names(), self.load_aliases())

    def _age(self) -> float | None:
        """Age of the saved snapshot in seconds, or None if never synced."""
        if not self.snapshot_path.exists():
            return None
        try:
            raw = self.snapshot_path.read_text(encoding="utf-8")
            updated = json.loads(raw).get("updated_at")
        except (json.JSONDecodeError, OSError):
            return None
        if not updated:
            return None
        try:
            parsed = datetime.fromisoformat(updated)
        except ValueError:
            return None
        return max(0.0, (datetime.now(parsed.tzinfo) - parsed).total_seconds())


__all__ = ["SyncResult", "SyncService"]
