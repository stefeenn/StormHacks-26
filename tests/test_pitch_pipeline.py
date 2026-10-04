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
    )
