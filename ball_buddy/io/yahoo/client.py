"""Facade over yfpy's ``YahooFantasySportsQuery``.

The client owns the yfpy instance and exposes :meth:`fetch_all`, which runs
the M1 fetch set (plan §2) and returns the raw model objects for
:mod:`ball_buddy.io.yahoo.snapshot` to map onto plain dicts.

Sign-in is NOT done here: yfpy's own browser flow needs a console
(``input()``), which the windowed exe doesn't have. The app drives OAuth
itself (see :mod:`ball_buddy.io.yahoo.oauth`) and hands a live token dict
to :meth:`from_tokens`. yfpy's constructor still ``sys.exit(1)``s on config
problems — that is mapped to :class:`LoginRequiredError`.
"""

from __future__ import annotations

import contextlib
import sys
import time
from pathlib import Path


class YahooError(RuntimeError):
    """A Yahoo fetch failed for a non-auth reason (network, rate limit...)."""


class LoginRequiredError(YahooError):
    """No usable credentials, or the saved token is dead: re-sign in (R2)."""


# consumer_secret is deliberately absent: public clients legitimately have an
# empty secret (PKCE). "guid" is absent too: it is bookkeeping only (no API
# call sends it) and can legitimately be empty for non-JWT tokens; every
# other field must be present.
_TOKEN_FIELDS = (
    "access_token",
    "refresh_token",
    "token_time",
    "token_type",
    "consumer_key",
)


class YahooClient:
    """One client per (league_id, game) pair; query is injectable for tests."""

    def __init__(
        self,
        query: object,
        consumer_key: str,
        consumer_secret: str,
        token_payload: dict | None = None,
    ) -> None:
        self._query = query
        self._consumer_key = consumer_key
        self._consumer_secret = consumer_secret
        self._token = token_payload or {}

    @classmethod
    def from_tokens(cls, settings: dict, tokens: dict) -> YahooClient:
        """Build a client from settings + a LIVE token dict.

        The token must be fresh enough that yfpy's internal
        ``token_is_valid()`` (a 3540-second window off ``token_time``) is
        true — otherwise yahoo_oauth would try to refresh with a callback
        URI we don't control. Callers refresh before constructing.

        ``YahooFantasySportsQuery.__init__`` calls ``sys.exit(1)`` on
        config problems — map that to LoginRequiredError.
        """
        try:
            from yfpy import query as yfpy_query
        except ImportError as exc:  # pragma: no cover - yfpy is a hard dep
            raise LoginRequiredError(f"yfpy is not installed: {exc}") from exc

        league_id = settings.get("league_id", "")
        consumer_key = tokens.get("consumer_key") or settings.get("consumer_key", "")
        consumer_secret = (
            tokens.get("consumer_secret") or settings.get("consumer_secret", "")
        )
        if not league_id or not consumer_key:
            raise LoginRequiredError(
                "Yahoo consumer key and league id must be set (Sign in)"
            )
        if not tokens.get("access_token"):
            raise LoginRequiredError("Sign in to Yahoo first (League -> Sign in).")
        # token_time=0 would make yahoo_oauth consider the token stale and
        # refresh with its own callback; stamp now so the internal check
        # passes and its (unused) refresh path is never taken.
        # yfpy exits on an EMPTY consumer secret, but public clients have
        # no secret at all — pass a placeholder to it (never sent to Yahoo;
        # yfpy's OAuth object never re-authenticates while the token is
        # fresh). The client itself keeps the real (possibly empty) value.
        yfpy_secret = consumer_secret or "public"
        yfpy_token_json = dict(tokens)
        yfpy_token_json.setdefault("token_time", time.time())
        yfpy_token_json["consumer_secret"] = yfpy_secret
        query = None
        with contextlib.redirect_stdout(sys.stderr):
            with contextlib.suppress(SystemExit):
                query = yfpy_query.YahooFantasySportsQuery(
                    league_id=league_id,
                    game_code="nba",
                    yahoo_consumer_key=consumer_key,
                    yahoo_consumer_secret=yfpy_secret,
                    yahoo_access_token_json=yfpy_token_json,
                    env_var_fallback=False,
                    save_token_data_to_env_file=False,
                )
        if query is None:
            raise LoginRequiredError(
                "Yahoo login was not completed (consumer key/secret invalid?)"
            )
        token_json = dict(tokens)
        token_json.setdefault("token_time", time.time())
        return cls(query, consumer_key, consumer_secret, token_json)

    @property
    def token(self) -> dict:
        """The live token dict this client was built from."""
        return dict(self._token)

    @property
    def logged_in(self) -> bool:
        """True once a live token exists (i.e. a query has succeeded)."""
        oauth = getattr(self._query, "oauth", None)
        if oauth is not None:
            if all(getattr(oauth, f, None) for f in ("access_token", "guid")):
                return True
        return bool(self._token.get("access_token"))

    @property
    def token_fresh(self) -> bool:
        """True while the access token is inside Yahoo's ~1h validity window.

        Conservative margin (5 min) so callers refresh before it would
        actually be rejected.
        """
        token_time = self._token.get("token_time") or 0
        return time.time() - float(token_time) < 3240

    def _call(self, method: str, *args: object) -> object:
        """Run one yfpy call, mapping auth failures to LoginRequiredError."""
        try:
            with contextlib.redirect_stdout(sys.stderr):
                return getattr(self._query, method)(*args)
        except SystemExit as exc:  # yfpy sys.exit(1) on auth/config problems
            raise LoginRequiredError(f"Yahoo login failed during {method} ({exc})") from exc
        except LoginRequiredError:
            raise
        except Exception as exc:  # yahoo-oauth raises requests.* on dead tokens
            message = str(exc) or exc.__class__.__name__
            lowered = message.lower()
            # 403 "application is not authorized" is an APP-level ban (Yahoo
            # disabled the app's fantasy read access), not a dead token — a
            # re-sign-in won't fix it, so surface it as a distinct error.
            if "application is not authorized" in lowered:
                raise YahooError(
                    "Yahoo has blocked this app's fantasy access (403 "
                    "'application is not authorized'). Re-signing in won't "
                    f"help: {message}"
                ) from exc
            if any(word in lowered for word in ("token", "oauth", "auth", "401", "403")):
                raise LoginRequiredError(f"Yahoo token is dead — sign in again: {message}") from exc
            raise YahooError(f"Yahoo call {method} failed: {message}") from exc

    def fetch_all(self) -> dict:
        """Run the M1 fetch set; raw yfpy models keyed by snapshot section."""
        teams = self._call("get_league_teams")
        matchups = []
        for team in teams:
            team_id = getattr(team, "team_id", None) or getattr(team, "team_key", None)
            if team_id is not None:
                matchups.extend(self._call("get_team_matchups", team_id))
        return {
            "user": self._call("get_current_user"),
            "league": self._call("get_user_leagues_by_game_key", "nba"),
            "settings": self._call("get_league_settings"),
            "teams": teams,
            "draft_results": self._call("get_league_draft_results"),
            "standings": self._call("get_league_standings"),
            "matchups": matchups,
        }

    def persist_token(self, data_dir: str | Path) -> None:
        """Save the live token dict (refreshable) for the next launch."""
        if not self.logged_in:
            return
        from ball_buddy.io.yahoo import auth

        tokens = auth.extract_tokens(
            self._query, self._consumer_key, self._consumer_secret
        )
        if all(tokens.get(field) for field in _TOKEN_FIELDS):
            auth.save_tokens(data_dir, tokens)

    def __getattr__(self, name: str) -> object:
        """Passthrough for direct yfpy access in tests/ad-hoc use."""
        if name.startswith("_"):
            raise AttributeError(name)
        return getattr(self.__dict__["_query"], name)
