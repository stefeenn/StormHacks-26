"""Tests for DataModelSync service and dataModel synchronization integration."""

import json
from pathlib import Path
from unittest.mock import MagicMock
import pandas as pd
import pytest

from scraper.data_model_sync import DataModelSync, _has_csv_data_rows
from scraper.pipeline import ScraperPipeline
from scraper.player_search import PlayerInfo


MOCK_STATCAST_CSV = """pitch_type,release_speed,p_throws,stand,pitch_name
SI,96.8,L,L,Sinker
SI,97.2,L,L,Sinker
FF,98.5,L,L,4-Seam Fastball
CH,88.0,L,L,Changeup
SL,89.5,L,L,Slider
"""


def test_has_csv_data_rows(tmp_path: Path):
    empty_csv = tmp_path / "empty.csv"
    empty_csv.write_text("Pitch Type,Velocity\n")
    assert not _has_csv_data_rows(empty_csv)

    csv_with_data = tmp_path / "with_data.csv"
    csv_with_data.write_text("Pitch Type,Velocity\nFastball,95.0\n")
    assert _has_csv_data_rows(csv_with_data)

    non_existent = tmp_path / "missing.csv"
    assert not _has_csv_data_rows(non_existent)


def test_data_model_sync_pitcher_mode(tmp_path: Path):
    p_src = tmp_path / "pitcher.csv"
    b_src = tmp_path / "batter.csv"
    h_src = tmp_path / "h2h.csv"

    p_src.write_text("Pitch Type,Velocity\nFastball,96.0\n")
    b_src.write_text("Pitch Type,Velocity\nFastball,94.0\n")
    h_src.write_text("Pitch Type,Velocity\nFastball,97.0\n")

    target_dir = tmp_path / "dataModel"
    syncer = DataModelSync(data_model_dir=target_dir)

    matchup_result = {
        "mode": "pitcher",
        "player1": {"name": "Tarik Skubal", "role": "Pitcher", "type": "pitcher", "file": p_src},
        "player2": {"name": "Matt Olson", "role": "Batter", "type": "batter", "file": b_src},
        "matchup": {"name": "Tarik Skubal vs Matt Olson", "role": "Head-to-Head", "type": "matchup", "file": h_src},
        "season": 2026,
        "count": None,
    }

    res = syncer.sync_matchup(
        matchup_result=matchup_result,
        pitcher_hand="L",
        batter_stance="left",
    )

    assert res["success"] is True
    assert (target_dir / "inputPitcher.csv").exists()
    assert (target_dir / "inputBatter.csv").exists()
    assert (target_dir / "inputH2H.csv").exists()
    assert (target_dir / "run_meta.json").exists()

    with open(target_dir / "run_meta.json") as f:
        meta = json.load(f)

    assert meta["pitcher"]["name"] == "Tarik Skubal"
    assert meta["batter"]["name"] == "Matt Olson"
    assert meta["recommended_model_settings"]["arsenal_column"] == "Left"
    assert meta["recommended_model_settings"]["batter_column"] == "Left"
    assert meta["matchup"]["has_data"] is True


def test_data_model_sync_batter_mode_right_handed(tmp_path: Path):
    p_src = tmp_path / "pitcher.csv"
    b_src = tmp_path / "batter.csv"
    h_src = tmp_path / "h2h.csv"

    p_src.write_text("Pitch Type,Velocity\nFastball,98.0\n")
    b_src.write_text("Pitch Type,Velocity\nFastball,92.0\n")
    h_src.write_text("Pitch Type,Velocity\n")  # Empty matchup

    target_dir = tmp_path / "dataModel"
    syncer = DataModelSync(data_model_dir=target_dir)

    matchup_result = {
        "mode": "batter",
        "player1": {"name": "Aaron Judge", "role": "Batter", "type": "batter", "file": b_src},
        "player2": {"name": "Gerrit Cole", "role": "Pitcher", "type": "pitcher", "file": p_src},
        "matchup": {"name": "Aaron Judge vs Gerrit Cole", "role": "Head-to-Head", "type": "matchup", "file": h_src},
        "season": 2026,
        "count": "3-2",
    }

    res = syncer.sync_matchup(
        matchup_result=matchup_result,
        pitcher_hand="R",
        batter_stance="right",
    )

    assert res["success"] is True
    assert res["has_h2h_data"] is False
    assert res["recommended_model_settings"]["arsenal_column"] == "Right"
    assert res["recommended_model_settings"]["batter_column"] == "Right"

    with open(target_dir / "run_meta.json") as f:
        meta = json.load(f)

    assert meta["pitcher"]["name"] == "Gerrit Cole"
    assert meta["batter"]["name"] == "Aaron Judge"
    assert meta["count"] == "3-2"
    assert meta["matchup"]["has_data"] is False


def test_pipeline_integration_with_sync(tmp_path: Path):
    mock_client = MagicMock()
    mock_client.fetch_statcast_pitches.return_value = MOCK_STATCAST_CSV

    mock_search = MagicMock()
    mock_search.find_pitcher.return_value = PlayerInfo(
        669373, "Tarik Skubal", "P", True, "L", "R", True
    )
    mock_search.find_batter.return_value = PlayerInfo(
        621566, "Matt Olson", "1B", False, "R", "L", True
    )

    target_data_model = tmp_path / "dataModel"
    pipeline = ScraperPipeline(
        client=mock_client,
        player_search=mock_search,
    )

    res = pipeline.scrape_head_to_head_to_csv(
        mode="pitcher",
        pitcher="Tarik Skubal",
        pitcher_hand="L",
        batter="Matt Olson",
        batter_stance="left",
        season=2026,
        output_path=tmp_path / "custom_h2h.csv",
        sync_data_model=True,
        data_model_dir=target_data_model,
    )

    assert "data_model_sync" in res
    assert res["data_model_sync"]["success"] is True
    assert (target_data_model / "inputPitcher.csv").exists()
    assert (target_data_model / "inputBatter.csv").exists()
    assert (target_data_model / "inputH2H.csv").exists()
    assert (target_data_model / "run_meta.json").exists()


def test_pipeline_integration_without_sync(tmp_path: Path):
    mock_client = MagicMock()
    mock_client.fetch_statcast_pitches.return_value = MOCK_STATCAST_CSV

    mock_search = MagicMock()
    mock_search.find_pitcher.return_value = PlayerInfo(
        669373, "Tarik Skubal", "P", True, "L", "R", True
    )
    mock_search.find_batter.return_value = PlayerInfo(
        621566, "Matt Olson", "1B", False, "R", "L", True
    )

    target_data_model = tmp_path / "dataModel"
    pipeline = ScraperPipeline(
        client=mock_client,
        player_search=mock_search,
    )

    res = pipeline.scrape_head_to_head_to_csv(
        mode="pitcher",
        pitcher="Tarik Skubal",
        pitcher_hand="L",
        batter="Matt Olson",
        batter_stance="left",
        season=2026,
        output_path=tmp_path / "custom_h2h.csv",
        sync_data_model=False,
        data_model_dir=target_data_model,
    )

    assert "data_model_sync" not in res
    assert not target_data_model.exists()


def test_end_to_end_model_execution_with_synced_data(tmp_path: Path):
    from dataModel.threeSourceModel import run_model

    mock_client = MagicMock()
    mock_client.fetch_statcast_pitches.return_value = MOCK_STATCAST_CSV

    mock_search = MagicMock()
    mock_search.find_pitcher.return_value = PlayerInfo(
        669373, "Tarik Skubal", "P", True, "L", "R", True
    )
    mock_search.find_batter.return_value = PlayerInfo(
        621566, "Matt Olson", "1B", False, "R", "L", True
    )

    target_data_model = tmp_path / "dataModel"
    pipeline = ScraperPipeline(
        client=mock_client,
        player_search=mock_search,
    )

    res = pipeline.scrape_head_to_head_to_csv(
        mode="pitcher",
        pitcher="Tarik Skubal",
        pitcher_hand="L",
        batter="Matt Olson",
        batter_stance="left",
        season=2026,
        output_path=tmp_path / "custom_h2h.csv",
        sync_data_model=True,
        data_model_dir=target_data_model,
    )

    assert res["data_model_sync"]["success"] is True

    # Execute threeSourceModel using the synced CSV files
    model_res = run_model(
        arsenal_csv=str(target_data_model / "inputPitcher.csv"),
        arsenal_column="Left",
        batter_csv=str(target_data_model / "inputBatter.csv"),
        batter_column="Left",
        matchup_csv=str(target_data_model / "inputH2H.csv"),
        bet_line=95.0,
        n_sims=500,
    )

    assert 0.0 <= model_res["p_over"] <= 1.0
    assert "sides" in model_res
    assert "OVER" in model_res["sides"]
    assert "UNDER" in model_res["sides"]
    assert "answer" in model_res

