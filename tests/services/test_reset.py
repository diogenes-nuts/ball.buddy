"""SyncService.reset_all_data: wipes the data dir; loaders survive a wiped dir."""

from pathlib import Path

from ball_buddy.domain import keepers as keepers_mod
from ball_buddy.domain import picks as picks_mod
from ball_buddy.services.sync import SyncService

DATA_FILES = (
    "settings.json",
    "yahoo_tokens.json",
    "players.csv",
    "aliases.json",
    "snapshot.json",
    "keepers.json",
    "draft_picks.json",
)


def test_reset_wipes_dir_and_loaders_succeed(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    for name in DATA_FILES:
        (data_dir / name).write_text("x", encoding="utf-8")
    assert (data_dir / "settings.json").exists()

    service = SyncService(data_dir)
    assert service.reset_all_data() is True
    assert not data_dir.exists()

    # everything must survive a wiped dir: loaders return empty defaults,
    # and the next save recreates the directory.
    assert service.settings() == {}
    assert service.logged_in is False
    assert service.load_aliases() == {}
    result = service.load_last()
    assert result.snapshot is None
    assert keepers_mod.load(data_dir / "keepers.json") == []
    assert picks_mod.load(data_dir / "draft_picks.json") == []

    service.save_settings({"league_id": "1"})
    assert data_dir.exists()
    assert service.settings()["league_id"] == "1"
