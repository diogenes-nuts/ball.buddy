"""Yahoo auth inputs: settings + token persistence under ``data/``.

``settings.json`` holds the user-provided consumer key/secret, league id, and
the manual draft order fallback. ``yahoo_tokens.json`` holds the yfpy
refreshable access-token dict so relaunches skip the browser dance. Both are
written atomically via :mod:`ball_buddy.io.state`.
"""

from __future__ import annotations

from pathlib import Path

from ball_buddy.io.state import load_json, save_json

SETTINGS_VERSION = 1
TOKENS_VERSION = 1


def load_settings(data_dir: str | Path) -> dict:
    """Settings dict, or an empty one if none exists yet."""
    path = Path(data_dir) / "settings.json"
    raw = load_json(path, SETTINGS_VERSION)
    return raw if raw is not None else {}


def save_settings(data_dir: str | Path, settings: dict) -> None:
    save_json(settings, Path(data_dir) / "settings.json", SETTINGS_VERSION)


def load_tokens(data_dir: str | Path) -> dict | None:
    """Saved Yahoo access-token dict, or ``None`` (not signed in yet)."""
    path = Path(data_dir) / "yahoo_tokens.json"
    return load_json(path, TOKENS_VERSION)


def save_tokens(data_dir: str | Path, tokens: dict) -> None:
    save_json(tokens, Path(data_dir) / "yahoo_tokens.json", TOKENS_VERSION)


def extract_tokens(query: object, consumer_key: str, consumer_secret: str) -> dict:
    """Build the persistable token dict from a live yfpy query object.

    ``query.oauth`` is the yahoo-oauth ``OAuth2`` instance; the yfpy
    constructor requires exactly these fields in the token dict.
    """
    oauth = getattr(query, "oauth", None)
    return {
        "access_token": getattr(oauth, "access_token", None),
        "guid": getattr(oauth, "guid", None),
        "refresh_token": getattr(oauth, "refresh_token", None),
        "token_time": getattr(oauth, "token_time", None),
        "token_type": getattr(oauth, "token_type", None),
        "consumer_key": consumer_key,
        "consumer_secret": consumer_secret,
    }
