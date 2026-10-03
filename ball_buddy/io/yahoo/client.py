"""Facade over yfpy's ``YahooFantasySportsQuery``.

The client owns the yfpy instance (constructed lazily so a missing consumer
key surfaces as :class:`LoginRequiredError` instead of yfpy's ``sys.exit(1)``)
and exposes :meth:`fetch_all`, which runs the M1 fetch set (plan §2) and
returns the raw model objects for :mod:`ball_buddy.io.yahoo.snapshot` to map
onto plain dicts.

yfpy's auth (yahoo-oauth, 3-legged) opens a browser; without one it prints
the URL for manual code entry. After a successful query the token fields are
persisted via :meth:`persist_token` so later launches refresh silently.
"""

from __future__ import annotations

import contextlib
import sys
from pathlib import Path


class YahooError(RuntimeError):
    """A Yahoo fetch failed for a non-auth reason (network, rate limit...)."""


class LoginRequiredError(YahooError):
    """No usable credentials, or the saved token is dead: re-sign in (R2)."""


_TOKEN_FIELDS = (
    "access_token",
    "guid",
    "refresh_token",
    "token_time",
    "token_type",
    "consumer_key",
    "consumer_secret",
)


class YahooClient:
    """One client per (league_id, game) pair; query is injectable for tests."""

    def __init__(self, query: object, consumer_key: str, consumer_secret: str) -> None:
        self._query = query
        self._consumer_key = consumer_key
        self._consumer_secret = consumer_secret

    @classmethod
    def from_settings(cls, settings: dict, tokens: dict | None) -> YahooClient:
        """Build a client from ``settings.json``/``yahoo_tokens.json`` dicts.

        ``YahooFantasySportsQuery.__init__`` calls ``sys.exit(1)`` when the
        consumer key/secret is missing — map that to LoginRequiredError.
        """
        try:
            from yfpy import query as yfpy_query
        except ImportError as exc:  # pragma: no cover - yfpy is a hard dep
            raise LoginRequiredError(f"yfpy is not installed: {exc}") from exc

        league_id = settings.get("league_id", "")
        consumer_key = settings.get("consumer_key", "")
        consumer_secret = settings.get("consumer_secret", "")
        if not league_id or not consumer_key or not consumer_secret:
            raise LoginRequiredError(
                "Yahoo consumer key, secret, and league id must be set (Sign in)"
            )
        with contextlib.redirect_stdout(sys.stderr):
            with contextlib.suppress(SystemExit):
                query = yfpy_query.YahooFantasySportsQuery(
                    league_id=league_id,
                    game_code="nba",
                    yahoo_access_token_json=tokens,
                    env_var_fallback=False,
                    save_token_data_to_env_file=False,
                    browser_callback=True,
                )
        if query is None:
            raise LoginRequiredError(
                "Yahoo login was not completed (consumer key/secret invalid?)"
            )
        return cls(query, consumer_key, consumer_secret)

    @property
    def logged_in(self) -> bool:
        """True once a live token exists (i.e. a query has succeeded)."""
        oauth = getattr(self._query, "oauth", None)
        if oauth is None:
            return False
        return all(getattr(oauth, field, None) for field in ("access_token", "guid"))

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
            if any(word in message.lower() for word in ("token", "oauth", "auth", "401", "403")):
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
