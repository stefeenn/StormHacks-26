"""Unit tests for data models."""

from scraper.models import PlayerRecord, ScrapedDataset


def test_clean_player_name():
    assert PlayerRecord.clean_player_name("Freeman, Freddie") == "Freddie Freeman"
    assert PlayerRecord.clean_player_name("Ohtani, Shohei") == "Shohei Ohtani"
    assert PlayerRecord.clean_player_name("Dodgers") == "Dodgers"
    assert PlayerRecord.clean_player_name("  Betts, Mookie  ") == "Mookie Betts"


def test_player_record_get_metric():
    rec = PlayerRecord(
        player_id="518692",
        raw_name="Freeman, Freddie",
        name="Freddie Freeman",
        season=2026,
        team_id=119,
        metrics={"BA": 0.288, "HR": 16, "ExitVelocity": 89.5},
    )
    assert rec.get_metric("BA") == 0.288
    assert rec.get_metric("ba") == 0.288
    assert rec.get_metric("hr") == 16
    assert rec.get_metric("UNKNOWN", default=0.0) == 0.0


def test_scraped_dataset_filter():
    player1 = PlayerRecord(
        player_id="1",
        raw_name="Player, One",
        name="One Player",
        season=2026,
        team_id=119,
        is_aggregate=False,
    )
    aggregate = PlayerRecord(
        player_id=None,
        raw_name="Dodgers",
        name="Dodgers",
        season=2026,
        team_id=119,
        is_aggregate=True,
    )
    dataset = ScrapedDataset(
        category="hitting",
        team_id=119,
        season=2026,
        records=[player1, aggregate],
    )
    roster = dataset.filter_roster_players()
    assert len(roster) == 1
    assert roster[0].name == "One Player"
    assert len(dataset.records) == 2
