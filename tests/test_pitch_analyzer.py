"""Unit tests for PitchAnalyzer."""

import numpy as np
import pandas as pd
import pytest

from scraper.pitch_analyzer import PitchAnalyzer


@pytest.fixture
def sample_statcast_df():
    data = [
        # Tarik Skubal throws L vs Matt Olson stands L
        {"pitch_name": "Sinker", "release_speed": 97.0, "p_throws": "L", "stand": "L"},
        {"pitch_name": "Sinker", "release_speed": 98.0, "p_throws": "L", "stand": "L"},
        {"pitch_name": "4-Seam Fastball", "release_speed": 99.0, "p_throws": "L", "stand": "L"},
        {"pitch_name": "Changeup", "release_speed": 88.0, "p_throws": "L", "stand": "L"},
        # Skubal throws L vs RHB
        {"pitch_name": "4-Seam Fastball", "release_speed": 97.0, "p_throws": "L", "stand": "R"},
        {"pitch_name": "Changeup", "release_speed": 86.0, "p_throws": "L", "stand": "R"},
        {"pitch_name": "Changeup", "release_speed": 87.0, "p_throws": "L", "stand": "R"},
        # Ambidextrous throws R vs LHB
        {"pitch_name": "4-Seam Fastball", "release_speed": 94.0, "p_throws": "R", "stand": "L"},
        # Ambidextrous throws R vs RHB
        {"pitch_name": "Slider", "release_speed": 83.0, "p_throws": "R", "stand": "R"},
    ]
    return pd.DataFrame(data)


def test_analyzer_single_hand_single_stance(sample_statcast_df):
    analyzer = PitchAnalyzer()
    df = analyzer.analyze(sample_statcast_df, pitcher_hand="L", batter_stance="left")

    assert list(df.columns) == [
        "Pitch Type",
        "Average Velocity (mph)",
        "Occurrence Percentage (%)",
    ]
    assert len(df) == 3
    # Sinker was thrown 2 out of 4 times (50.0%), avg velocity 97.5
    sinker_row = df[df["Pitch Type"] == "Sinker"].iloc[0]
    assert sinker_row["Average Velocity (mph)"] == "97.5"
    assert sinker_row["Occurrence Percentage (%)"] == "50.0%"

    # 4-Seam Fastball: 1/4 (25.0%), avg velocity 99.0
    ff_row = df[df["Pitch Type"] == "4-Seam Fastball"].iloc[0]
    assert ff_row["Average Velocity (mph)"] == "99.0"
    assert ff_row["Occurrence Percentage (%)"] == "25.0%"


def test_analyzer_single_hand_both_stance(sample_statcast_df):
    analyzer = PitchAnalyzer()
    df = analyzer.analyze(sample_statcast_df, pitcher_hand="L", batter_stance="both")

    assert list(df.columns) == [
        "Pitch Type",
        "Average Velocity - Left (mph)",
        "Average Velocity - Right (mph)",
        "Occurrence Percentage - Left (%)",
        "Occurrence Percentage - Right (%)",
    ]
    # Sinker only thrown vs Left: 2 out of 4 Left (50.0%), 0 out of 3 Right (0.0%)
    sinker_row = df[df["Pitch Type"] == "Sinker"].iloc[0]
    assert sinker_row["Average Velocity - Left (mph)"] == "97.5"
    assert sinker_row["Average Velocity - Right (mph)"] == "N/A"
    assert sinker_row["Occurrence Percentage - Left (%)"] == "50.0%"
    assert sinker_row["Occurrence Percentage - Right (%)"] == "0.0%"

    # Changeup thrown 1 vs Left (25.0%, 88.0) and 2 vs Right (66.7%, 86.5)
    ch_row = df[df["Pitch Type"] == "Changeup"].iloc[0]
    assert ch_row["Average Velocity - Left (mph)"] == "88.0"
    assert ch_row["Average Velocity - Right (mph)"] == "86.5"
    assert ch_row["Occurrence Percentage - Left (%)"] == "25.0%"
    assert ch_row["Occurrence Percentage - Right (%)"] == "66.7%"


def test_analyzer_both_hand_single_stance(sample_statcast_df):
    analyzer = PitchAnalyzer()
    df = analyzer.analyze(sample_statcast_df, pitcher_hand="both", batter_stance="left")

    assert list(df.columns) == [
        "Pitch Type",
        "Average Velocity - Left (mph)",
        "Average Velocity - Right (mph)",
        "Occurrence Percentage - Left (%)",
        "Occurrence Percentage - Right (%)",
    ]
    # Fastball thrown from Left (99.0, 1/4 = 25.0%) and Right (94.0, 1/1 = 100.0%)
    ff_row = df[df["Pitch Type"] == "4-Seam Fastball"].iloc[0]
    assert ff_row["Average Velocity - Left (mph)"] == "99.0"
    assert ff_row["Average Velocity - Right (mph)"] == "94.0"
    assert ff_row["Occurrence Percentage - Left (%)"] == "25.0%"
    assert ff_row["Occurrence Percentage - Right (%)"] == "100.0%"


def test_analyzer_both_hand_both_stance(sample_statcast_df):
    analyzer = PitchAnalyzer()
    df = analyzer.analyze(sample_statcast_df, pitcher_hand="both", batter_stance="both")

    assert list(df.columns) == [
        "Pitch Type",
        "Average Velocity - Pitcher Left (mph)",
        "Average Velocity - Pitcher Right (mph)",
        "Average Velocity - Batter Left (mph)",
        "Average Velocity - Batter Right (mph)",
        "Occurrence Percentage - Pitcher Left (%)",
        "Occurrence Percentage - Pitcher Right (%)",
        "Occurrence Percentage - Batter Left (%)",
        "Occurrence Percentage - Batter Right (%)",
    ]
    assert len(df) == 4  # Fastball, Changeup, Sinker, Slider


def test_analyzer_empty_data():
    analyzer = PitchAnalyzer()
    empty_df = pd.DataFrame()
    df = analyzer.analyze(empty_df, pitcher_hand="L", batter_stance="right")
    assert list(df.columns) == [
        "Pitch Type",
        "Average Velocity (mph)",
        "Occurrence Percentage (%)",
    ]
    assert len(df) == 0


def test_analyzer_invalid_inputs(sample_statcast_df):
    analyzer = PitchAnalyzer()
    with pytest.raises(ValueError, match="Invalid pitcher throwing hand"):
        analyzer.analyze(sample_statcast_df, pitcher_hand="invalid", batter_stance="left")

    with pytest.raises(ValueError, match="Invalid batter stance"):
        analyzer.analyze(sample_statcast_df, pitcher_hand="L", batter_stance="invalid")


def test_analyzer_with_count_filtering():
    data = [
        {"pitch_name": "Sinker", "release_speed": 97.0, "p_throws": "L", "stand": "L", "balls": 2, "strikes": 1},
        {"pitch_name": "Sinker", "release_speed": 98.0, "p_throws": "L", "stand": "L", "balls": 0, "strikes": 0},
        {"pitch_name": "Changeup", "release_speed": 88.0, "p_throws": "L", "stand": "L", "balls": 2, "strikes": 1},
        {"pitch_name": "4-Seam Fastball", "release_speed": 99.0, "p_throws": "L", "stand": "L", "balls": 3, "strikes": 2},
    ]
    df = pd.DataFrame(data)
    analyzer = PitchAnalyzer()
    res = analyzer.analyze(df, pitcher_hand="L", batter_stance="left", count="2-1")

    # In 2-1 count: only Sinker (1) and Changeup (1), total 2 pitches (50% each)
    assert len(res) == 2
    assert set(res["Pitch Type"]) == {"Sinker", "Changeup"}
    sinker_row = res[res["Pitch Type"] == "Sinker"].iloc[0]
    assert sinker_row["Occurrence Percentage (%)"] == "50.0%"
    assert sinker_row["Average Velocity (mph)"] == "97.0"


