"""Integration tests for ScraperPipeline pitch scraping."""

from pathlib import Path
from unittest.mock import MagicMock
import pandas as pd
import pytest

from scraper.pipeline import ScraperPipeline
from scraper.player_search import PlayerInfo


MOCK_STATCAST_CSV = """pitch_type,release_speed,p_throws,stand,pitch_name
SI,96.8,L,L,Sinker
SI,97.2,L,L,Sinker
FF,98.5,L,L,4-Seam Fastball
CH,88.0,L,L,Changeup
SL,89.5,L,L,Slider
"""


def test_scrape_pitcher_arsenal_to_csv(tmp_path):
    mock_client = MagicMock()
    mock_client.fetch_statcast_pitches.return_value = MOCK_STATCAST_CSV

    mock_search = MagicMock()
    mock_search.find_pitcher.return_value = PlayerInfo(
        669373, "Tarik Skubal", "P", True, "L", "R", True
    )
    mock_search.find_batter.return_value = PlayerInfo(
        621566, "Matt Olson", "1B", False, "R", "L", True
    )

    pipeline = ScraperPipeline(
        client=mock_client,
        player_search=mock_search,
    )

    out_file = tmp_path / "skubal_vs_olson.csv"

    exported = pipeline.scrape_pitcher_arsenal_to_csv(
        pitcher="Tarik Skubal",
        pitcher_hand="L",
        batter="Matt Olson",
        batter_stance="left",
        season=2026,
        output_path=out_file,
    )

    assert exported.exists()
    df = pd.read_csv(exported)
    assert list(df.columns) == [
        "Pitch Type",
        "Average Velocity (mph)",
        "Occurrence Percentage (%)",
    ]
    assert len(df) == 4
    # Sinker: 2 out of 5 = 40.0%, avg speed = 97.0
    sinker = df[df["Pitch Type"] == "Sinker"].iloc[0]
    assert sinker["Average Velocity (mph)"] == 97.0
    assert sinker["Occurrence Percentage (%)"] == "40.0%"


def test_scrape_batter_pitches_to_csv(tmp_path):
    mock_client = MagicMock()
    mock_client.fetch_statcast_pitches.return_value = MOCK_STATCAST_CSV

    mock_search = MagicMock()
    mock_search.find_batter.return_value = PlayerInfo(
        621566, "Matt Olson", "1B", False, "R", "L", True
    )
    mock_search.find_pitcher.return_value = PlayerInfo(
        669373, "Tarik Skubal", "P", True, "L", "R", True
    )

    pipeline = ScraperPipeline(
        client=mock_client,
        player_search=mock_search,
    )

    out_file = tmp_path / "olson_vs_skubal.csv"

    exported = pipeline.scrape_batter_pitches_to_csv(
        batter="Matt Olson",
        batter_stance="left",
        pitcher="Tarik Skubal",
        pitcher_hand="L",
        season=2026,
        output_path=out_file,
    )

    assert exported.exists()
    df = pd.read_csv(exported)
    assert list(df.columns) == [
        "Pitch Type",
        "Average Velocity (mph)",
        "Occurrence Percentage (%)",
    ]
    assert len(df) == 4
    mock_client.fetch_statcast_pitches.assert_called_with(
        pitcher_id=669373,
        batter_id=621566,
        player_type="batter",
        season=2026,
        count=None,
    )


def test_scrape_head_to_head_pitcher_mode(tmp_path):
    mock_client = MagicMock()
    mock_client.fetch_statcast_pitches.return_value = MOCK_STATCAST_CSV

    mock_search = MagicMock()
    mock_search.find_pitcher.return_value = PlayerInfo(
        669373, "Tarik Skubal", "P", True, "L", "R", True
    )
    mock_search.find_batter.return_value = PlayerInfo(
        621566, "Matt Olson", "1B", False, "R", "L", True
    )

    pipeline = ScraperPipeline(
        client=mock_client,
        player_search=mock_search,
    )

    h2h_dest = tmp_path / "custom_skubal_vs_olson.csv"
    res = pipeline.scrape_head_to_head_to_csv(
        mode="pitcher",
        pitcher="Tarik Skubal",
        pitcher_hand="L",
        batter="Matt Olson",
        batter_stance="left",
        season=2026,
        output_path=h2h_dest,
    )

    assert res["mode"] == "pitcher"
    assert res["player1"]["name"] == "Tarik Skubal"
    assert res["player1"]["role"] == "Pitcher"
    assert res["player2"]["name"] == "Matt Olson"
    assert res["player2"]["role"] == "Batter"
    assert res["matchup"]["name"] == "Tarik Skubal vs Matt Olson"

    # Verify all 3 files generated exist and match files_in_order in order: p1, p2, h2h
    assert len(res["files_in_order"]) == 3
    p1_file, p2_file, h2h_file = res["files_in_order"]
    assert p1_file == res["player1"]["file"]
    assert p2_file == res["player2"]["file"]
    assert h2h_file == res["matchup"]["file"]
    assert h2h_file == h2h_dest

    assert p1_file.exists()
    assert p2_file.exists()
    assert h2h_file.exists()


def test_scrape_head_to_head_batter_mode(tmp_path):
    mock_client = MagicMock()
    mock_client.fetch_statcast_pitches.return_value = MOCK_STATCAST_CSV

    mock_search = MagicMock()
    mock_search.find_batter.return_value = PlayerInfo(
        621566, "Matt Olson", "1B", False, "R", "L", True
    )
    mock_search.find_pitcher.return_value = PlayerInfo(
        669373, "Tarik Skubal", "P", True, "L", "R", True
    )

    pipeline = ScraperPipeline(
        client=mock_client,
        player_search=mock_search,
    )

    h2h_dest = tmp_path / "custom_olson_vs_skubal.csv"
    res = pipeline.scrape_head_to_head_to_csv(
        mode="batter",
        pitcher="Tarik Skubal",
        pitcher_hand="L",
        batter="Matt Olson",
        batter_stance="left",
        season=2026,
        output_path=h2h_dest,
    )

    assert res["mode"] == "batter"
    assert res["player1"]["name"] == "Matt Olson"
    assert res["player1"]["role"] == "Batter"
    assert res["player2"]["name"] == "Tarik Skubal"
    assert res["player2"]["role"] == "Pitcher"
    assert res["matchup"]["name"] == "Matt Olson vs Tarik Skubal"

    assert len(res["files_in_order"]) == 3
    p1_file, p2_file, h2h_file = res["files_in_order"]
    assert p1_file == res["player1"]["file"]
    assert p2_file == res["player2"]["file"]
    assert h2h_file == res["matchup"]["file"]
    assert h2h_file == h2h_dest

    assert p1_file.exists()
    assert p2_file.exists()
    assert h2h_file.exists()


def test_scrape_pitcher_arsenal_with_count(tmp_path):
    mock_client = MagicMock()
    mock_client.fetch_statcast_pitches.return_value = MOCK_STATCAST_CSV

    mock_search = MagicMock()
    mock_search.find_pitcher.return_value = PlayerInfo(
        669373, "Tarik Skubal", "P", True, "L", "R", True
    )

    pipeline = ScraperPipeline(
        client=mock_client,
        player_search=mock_search,
    )

    exported = pipeline.scrape_pitcher_arsenal_to_csv(
        pitcher="Tarik Skubal",
        pitcher_hand="L",
        season=2024,
        count="2-1",
    )

    assert "count_2_1" in exported.name
    mock_client.fetch_statcast_pitches.assert_called_with(
        pitcher_id=669373,
        batter_id=None,
        season=2024,
        count="2-1",
    )


