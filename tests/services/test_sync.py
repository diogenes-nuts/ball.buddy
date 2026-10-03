"""SyncService pipeline tests: fake client + real files in tmp_path."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ball_buddy.io.pool.importer import write_csv  # noqa: E402
from ball_buddy.io.yahoo.client import YahooClient  # noqa: E402
from ball_buddy.services.sync import SyncService  # noqa: E402
from tests.io.test_yahoo_client import FakeQuery  # noqa: E402

POOL_ROWS = [
    {"name": "Nikola Jokic", "pos": "C", "team": "DEN", "gp": "72"},
    {"name": "Karl Malone", "pos": "C", "team": "UTA", "gp": "80"},
]
POOL_FIELDS = list(POOL_ROWS[0].keys())


def make_service(
    tmp_path: Path, client: FakeQuery | YahooClient | None = None
) -> SyncService:
    if isinstance(client, FakeQuery):
        client = YahooClient(client, "key", "secret")
    service = SyncService(tmp_path, client=client)
    service.save_settings({"league_id": "1234", "consumer_key": "k", "consumer_secret": "s"})
    return service


def write_pool(service: SyncService) -> None:
    from ball_buddy.io.pool.importer import FIELDNAMES

    full = [{f: "" for f in FIELDNAMES} for _ in POOL_ROWS]
    for row, full_row in zip(POOL_ROWS, full):
        full_row.update(row)
    write_csv(full, service.pool_path)


def test_full_sync_pipeline(tmp_path):
    service = make_service(tmp_path, client=FakeQuery())
    write_pool(service)
    result = service.run()
    assert result.ok, result.error
    assert result.needs_login is False
    assert result.snapshot is not None
    assert [t["name"] for t in result.snapshot["teams"]] == ["Red", "Blue"]
    assert service.snapshot_path.exists()
    raw = json.loads(service.snapshot_path.read_text(encoding="utf-8"))
    assert raw["version"] == 1
    assert raw["teams"] == result.snapshot["teams"]

    # bridging: roster = [Nikola Jokic, Ghost Player, Shaquille O'Neal, Jokic]
    # pool = [Nikola Jokic, Karl Malone]
    report = result.report
    assert report is not None
    assert report.matched == {
        "Nikola Jokic": "Nikola Jokic",  # exact
        "Jokic": "Nikola Jokic",  # unique first-name-optional containment
    }
    unmatched_names = [name for name, _ in report.unmatched]
    assert "Shaquille O'Neal" in unmatched_names
    assert "Ghost Player" in unmatched_names


def test_sync_saves_aliases_and_uses_them(tmp_path):
    service = make_service(tmp_path, client=FakeQuery())
    write_pool(service)
    service.save_aliases({"Shaquille O'Neal": "Karl Malone"})
    result = service.run()
    assert result.ok
    assert result.report.matched["Shaquille O'Neal"] == "Karl Malone"


def test_no_credentials_needs_login(tmp_path):
    service = SyncService(tmp_path, client=None)
    service.save_settings({"league_id": "1234"})  # no consumer key/secret
    result = service.run()
    assert result.ok is False
    assert result.needs_login is True
    assert "consumer key" in result.error


def test_token_expiry_needs_login(tmp_path):
    class DeadQuery:
        oauth = None

        def get_current_user(self):
            raise RuntimeError("401: token expired")

        def get_league_teams(self):
            raise RuntimeError("401: token expired")

    service = make_service(tmp_path, client=YahooClient(DeadQuery(), "k", "s"))
    result = service.run()
    assert result.needs_login is True
    assert result.ok is False


def test_fetch_failure_keeps_old_snapshot(tmp_path):
    good = make_service(tmp_path, client=FakeQuery())
    assert good.run().ok

    class BoomQuery:
        oauth = None

        def get_current_user(self):
            return None

        def get_user_leagues_by_game_key(self, key):
            raise RuntimeError("network down")

        def get_league_settings(self):
            raise RuntimeError("network down")

        def get_league_teams(self):
            raise RuntimeError("network down")

        def get_league_draft_results(self):
            raise RuntimeError("network down")

        def get_league_standings(self):
            raise RuntimeError("network down")

        def get_team_matchups(self, team_id):
            raise RuntimeError("network down")

    broken = make_service(tmp_path, client=YahooClient(BoomQuery(), "k", "s"))
    result = broken.run()
    assert result.ok is False
    assert result.needs_login is False
    assert "network down" in result.error
    # offline fallback: last snapshot still loadable
    last = broken.load_last()
    assert last.snapshot is not None
    assert [t["name"] for t in last.snapshot["teams"]] == ["Red", "Blue"]
    assert last.snapshot_age_seconds is not None and last.snapshot_age_seconds >= 0


def test_load_last_without_any_sync(tmp_path):
    service = make_service(tmp_path, client=FakeQuery())
    result = service.load_last()
    assert result.snapshot is None
    assert result.snapshot_age_seconds is None


def test_load_last_with_pool_bridges(tmp_path):
    service = make_service(tmp_path, client=FakeQuery())
    write_pool(service)
    assert service.run().ok
    last = service.load_last()
    assert last.report is not None
    assert last.report.matched.get("Nikola Jokic") == "Nikola Jokic"


def test_load_last_corrupt_snapshot_reports_error(tmp_path):
    service = make_service(tmp_path, client=FakeQuery())
    service.snapshot_path.write_text("{not json", encoding="utf-8")
    result = service.load_last()
    assert result.snapshot is None
    assert "not valid JSON" in result.error
