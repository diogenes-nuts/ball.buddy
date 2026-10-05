"""YahooClient facade tests with a stubbed yfpy query (headless)."""

import json
from pathlib import Path

import pytest

from ball_buddy.io.yahoo import auth
from ball_buddy.io.yahoo.client import LoginRequiredError, YahooClient, YahooError

FIXTURE = Path("tests/fixtures/snapshot_results.json")


def _results_raw() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


class M:
    """Attribute bag; missing attributes return None (like YahooFantasyObject-ish)."""

    def __init__(self, data: dict) -> None:
        for key, value in data.items():
            setattr(self, key, value)
        self._extracted_data = data

    def __getattr__(self, name):
        return None


class FakeQuery:
    """Stub of yfpy YahooFantasySportsQuery exposing the M1 fetch set."""

    def __init__(self, fail_method: str | None = None, fail_exc: Exception | None = None):
        raw = _results_raw()
        self.raw = raw
        self.fail_method = fail_method
        self.fail_exc = fail_exc
        self.calls: list[str] = []
        self.oauth = M(
            {
                "access_token": "tok",
                "guid": "987654321",
                "refresh_token": "ref",
                "token_time": 1.0,
                "token_type": "bearer",
            }
        )

    def _maybe_fail(self, method: str) -> None:
        if self.fail_method == method:
            raise self.fail_exc or RuntimeError("boom")

    def get_current_user(self):
        self.calls.append("user")
        self._maybe_fail("get_current_user")
        return M(self.raw["user"])

    def get_user_leagues_by_game_key(self, game_key):
        self.calls.append("leagues")
        assert game_key == "nba"
        self._maybe_fail("get_user_leagues_by_game_key")
        return [M(league) for league in self.raw["league"]]

    def get_league_settings(self):
        self.calls.append("settings")
        self._maybe_fail("get_league_settings")
        return M(self.raw["settings"])

    def get_league_teams(self):
        self.calls.append("teams")
        self._maybe_fail("get_league_teams")
        teams = []
        for team in self.raw["teams"]:
            team = dict(team)
            team["manager"] = M(team["manager"])
            team["players"] = [M(player) for player in team["players"]]
            teams.append(M(team))
        return teams

    def get_league_draft_results(self):
        self.calls.append("draft")
        return []

    def get_league_standings(self):
        self.calls.append("standings")
        self._maybe_fail("get_league_standings")
        return M(self.raw["standings"])

    def get_team_matchups(self, team_id):
        self.calls.append(f"matchups:{team_id}")
        self._maybe_fail(f"get_team_matchups:{team_id}")
        team_key = {"100": "nba.fake.t100", "200": "nba.fake.t200"}[str(team_id)]
        return [
            M(m) for m in self.raw["matchups"]
            if {"nba.fake.t100", "nba.fake.t200"} == {
                t["team"]["team_key"] for t in m["teams"]
            } or (m["teams"] and m["teams"][0]["team"]["team_key"] == team_key)
        ]


def make_client(fail_method=None, fail_exc=None) -> YahooClient:
    return YahooClient(FakeQuery(fail_method, fail_exc), "key", "secret")


def test_fetch_all_sections():
    client = make_client()
    results = client.fetch_all()
    assert results["user"].guid == "987654321"
    assert len(results["teams"]) == 2
    # team 100 sees all 3; team 200 sees the two that involve it
    assert len(results["matchups"]) == 5  # deduped later by the snapshot adapter
    assert "settings" in results and "standings" in results


def test_logged_in_requires_token_fields():
    client = make_client()
    assert client.logged_in
    client._query.oauth = M({"access_token": None, "guid": None})
    assert not client.logged_in


def test_token_expiry_maps_to_login_required():
    client = make_client(fail_method="get_league_teams", fail_exc=RuntimeError("401 invalid token"))
    with pytest.raises(LoginRequiredError, match="sign in again"):
        client.fetch_all()


def test_403_app_ban_maps_to_yahoo_error_not_relogin():
    """'application is not authorized' (403) is an APP-level ban, not a dead
    token — it must NOT prompt a re-sign-in (which would loop), so it maps to
    a distinct YahooError. Regression for the Yahoo legacy-app read-access
    removal (yfpy issue #84)."""
    client = make_client(
        fail_method="get_league_teams",
        fail_exc=RuntimeError(
            "Attempt to retrieve data at URL ... failed with error: "
            "'This application is not authorized to perform this action.'"
        ),
    )
    with pytest.raises(YahooError, match="blocked this app's fantasy access"):
        client.fetch_all()


def test_auth_sysexit_maps_to_login_required():
    query = FakeQuery()

    def boom():
        raise SystemExit(1)

    query.get_current_user = boom
    client = YahooClient(query, "k", "s")
    with pytest.raises(LoginRequiredError, match="login failed"):
        client.fetch_all()


def test_non_auth_error_maps_to_yahoo_error():
    client = make_client(fail_method="get_league_teams", fail_exc=RuntimeError("rate limited"))
    with pytest.raises(YahooError, match="rate limited"):
        client.fetch_all()


def _token_dict() -> dict:
    return {
        "access_token": "tok",
        "guid": "987654321",
        "refresh_token": "ref",
        "token_time": 1.0,
        "token_type": "bearer",
        "consumer_key": "k123",
        "consumer_secret": "s456",
    }


def test_from_tokens_missing_credentials():
    with pytest.raises(LoginRequiredError, match="consumer key"):
        YahooClient.from_tokens({"league_id": "1"}, {})


def test_from_tokens_requires_access_token():
    with pytest.raises(LoginRequiredError, match="Sign in"):
        YahooClient.from_tokens(
            {"league_id": "847", "consumer_key": "k", "consumer_secret": "s"},
            _token_dict() | {"access_token": None},
        )


def test_from_tokens_passes_credentials_to_yfpy(monkeypatch):
    """Regression: key/secret must reach YahooFantasySportsQuery (yahoo_consumer_* names).

    Real yfpy exits silently (sys.exit(1)) when they're missing — without this
    the sign-in failure was indistinguishable from "invalid credentials".
    """
    import yfpy.query as yfpy_query

    captured = {}

    def fake_query(**kwargs):
        captured.update(kwargs)
        return object()  # any truthy query = construction succeeded

    monkeypatch.setattr(yfpy_query, "YahooFantasySportsQuery", fake_query)
    client = YahooClient.from_tokens({"league_id": "847"}, _token_dict())
    assert captured["yahoo_consumer_key"] == "k123"
    assert captured["yahoo_consumer_secret"] == "s456"
    assert captured["league_id"] == "847"
    assert captured["game_code"] == "nba"
    assert client._query is not None


def test_from_tokens_public_client_empty_secret(monkeypatch):
    """Public client: no secret anywhere. yfpy gets the "public" placeholder
    (it sys.exit(1)s on empty), but the client + persisted token keep "" so
    later token requests take the public-client path (body client_id, PKCE)."""
    import yfpy.query as yfpy_query

    captured = {}

    def fake_query(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(yfpy_query, "YahooFantasySportsQuery", fake_query)
    client = YahooClient.from_tokens(
        {"league_id": "847", "consumer_key": "pk"}, _token_dict() | {"consumer_secret": ""}
    )
    assert captured["yahoo_consumer_secret"] == "public"
    assert client._consumer_secret == ""
    assert client.token["consumer_secret"] == ""


def test_from_tokens_public_client_persists_empty_secret(monkeypatch, tmp_path: Path):
    """persist_token must store the REAL (empty) secret, not the placeholder."""
    import yfpy.query as yfpy_query

    def fake_query(**kwargs):
        return object()

    monkeypatch.setattr(yfpy_query, "YahooFantasySportsQuery", fake_query)
    client = YahooClient.from_tokens(
        {"league_id": "847", "consumer_key": "pk"}, _token_dict() | {"consumer_secret": ""}
    )
    client._query = make_client()._query  # a FakeQuery with a full oauth object
    client.persist_token(tmp_path)
    tokens = auth.load_tokens(tmp_path)
    assert tokens is not None
    assert tokens["consumer_secret"] == ""


def test_from_tokens_survives_yfpy_exit(monkeypatch):
    """yfpy sys.exit(1) mid-construction must map to LoginRequiredError, not UnboundLocalError."""
    import yfpy.query as yfpy_query

    def fake_query(**kwargs):
        raise SystemExit(1)

    monkeypatch.setattr(yfpy_query, "YahooFantasySportsQuery", fake_query)
    with pytest.raises(LoginRequiredError, match="not completed"):
        YahooClient.from_tokens(
            {"league_id": "847", "consumer_key": "k", "consumer_secret": "s"},
            _token_dict(),
        )


def test_persist_token(tmp_path: Path):
    client = make_client()
    client.persist_token(tmp_path)
    tokens = auth.load_tokens(tmp_path)
    assert tokens is not None
    assert tokens["consumer_key"] == "key"
    assert tokens["guid"] == "987654321"
    assert tokens["access_token"] == "tok"


def test_persist_token_skipped_when_not_logged_in(tmp_path: Path):
    client = make_client()
    client._query.oauth = M({"access_token": None})
    client.persist_token(tmp_path)
    assert auth.load_tokens(tmp_path) is None
