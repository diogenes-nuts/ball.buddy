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
import shutil
import time
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

    def reset_all_data(self) -> bool:
        """Wipe the whole data dir (settings, tokens, pool, snapshot, keepers, picks).

        Everything recreates on the next save (all savers mkdir parents), and
        all loaders treat a missing file as the empty default — so the app
        keeps running on its in-memory state; restart for a truly clean slate.

        Returns True if the dir is fully wiped; False if something is still
        there (e.g. a locked file), so callers can tell the user.
        """
        shutil.rmtree(self.data_dir, ignore_errors=True)
        return not self.data_dir.exists()

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

    # -- sign-in / token management --------------------------------------------

    def _client_from_tokens(self, settings: dict, tokens: dict) -> YahooClient:
        self._client = YahooClient.from_tokens(settings, tokens)
        return self._client

    def _live_tokens(self) -> dict | None:
        """Saved token dict, refreshed when the access token is stale.

        We do the refresh here (never via yahoo_oauth's internal path, which
        would use the 'oob' callback). Returns None when not signed in.
        """
        tokens = auth.load_tokens(self.data_dir)
        if not tokens or not tokens.get("access_token"):
            return None
        if time.time() - float(tokens.get("token_time") or 0) < 3240:
            return tokens
        from ball_buddy.io.yahoo import oauth

        settings = self.settings()
        payload = oauth.refresh_access_token(
            tokens["refresh_token"],
            settings.get("consumer_key", ""),
            settings.get("consumer_secret", ""),
        )
        fresh = oauth.new_token_dict(payload, tokens["consumer_key"], tokens["consumer_secret"])
        auth.save_tokens(self.data_dir, fresh)
        return fresh

    def sign_in_ready(self) -> tuple[str, str]:
        """Consumer key/secret for the sign-in dialog; LoginRequiredError if unset.

        The secret is optional: public clients (Yahoo console "OAuth Client
        type: Public") have no secret and sign in with PKCE instead.
        """
        settings = self.settings()
        key = settings.get("consumer_key", "")
        secret = settings.get("consumer_secret", "")
        if not key:
            raise LoginRequiredError(
                "Set the consumer key in League -> Settings first."
            )
        return key, secret

    def save_sign_in(self, tokens: dict) -> None:
        """Persist a fresh token dict and drop any stale client."""
        auth.save_tokens(self.data_dir, tokens)
        self._client = None  # next sync builds a client from the fresh token

    # -- sync ----------------------------------------------------------------

    def _build_client(self) -> YahooClient:
        if self._client is not None:
            return self._client
        tokens = self._live_tokens()
        if tokens is None:
            raise LoginRequiredError("Sign in to Yahoo first (League -> Sign in).")
        return self._client_from_tokens(self.settings(), tokens)

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

    def effective_snapshot(self) -> dict | None:
        """The snapshot every view should render from.

        The last saved Yahoo snapshot when one exists (``load_last()``);
        otherwise, if the user entered a manual team list in Settings
        (``manual_teams``), a synthetic minimal snapshot so the draft board,
        keeper entry, and the team-picker views work offline. The synthetic
        doc is not written to snapshot.json — the real Yahoo snapshot always
        wins once one exists.
        """
        document = self.load_last().snapshot
        if document is None:
            manual = (self.settings().get("manual_teams") or [])
            document = snapshot_mod.manual_snapshot(
                manual, str(self.settings().get("league_id", ""))
            ) or None
        return document

    def load_last(self) -> SyncResult:
        """Offline fallback: the last saved snapshot + its age (or empty).

        No manual-team fallback here: a SyncResult with a snapshot would
        look like a real (stale) sync to status banners. Views use
        :meth:`effective_snapshot` for the manual case.
        """
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
