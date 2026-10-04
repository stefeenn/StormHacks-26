"""Integration tests for Three-Source Velocity Data Model web endpoints."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from web.app import create_app
from web.routes.api import recent_searches_session


@pytest.fixture
def temp_dirs(tmp_path: Path):
    out_dir = tmp_path / "output"
    model_dir = tmp_path / "dataModel"
    out_dir.mkdir(parents=True, exist_ok=True)
    model_dir.mkdir(parents=True, exist_ok=True)
    return {"output": out_dir, "model": model_dir}


@pytest.fixture
def client(temp_dirs):
    recent_searches_session.clear()
    search_service = MagicMock()
    pipeline = MagicMock()
    app = create_app(
        output_dir=str(temp_dirs["output"]),
        scraper_pipeline=pipeline,
        player_search_service=search_service,
    )
    app.config["DATA_MODEL_DIR"] = temp_dirs["model"]
    app.config["TESTING"] = True
    with app.test_client() as test_client:
        yield test_client
    recent_searches_session.clear()


def test_model_status_initially_empty(client, temp_dirs):
    res = client.get("/api/model/status")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["has_synced_data"] is False
    assert data["has_output"] is False
    assert data["has_plot"] is False
    assert data["plot_url"] is None


def test_model_samples_empty(client):
    res = client.get("/api/model/samples")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["samples"] == []


def test_model_samples_discovery(client, temp_dirs):
    out_dir = temp_dirs["output"]
    p_file = out_dir / "chris_sale_2024_pitch_arsenal.csv"
    b_file = out_dir / "shohei_ohtani_2024_pitches_faced.csv"
    h_file = out_dir / "chris_sale_vs_shohei_ohtani_2024.csv"

    p_file.write_text("Pitch Type,Average Velocity (mph),Occurrence Percentage (%)\n4-Seam Fastball,95.0,60.0%\n")
    b_file.write_text("Pitch Type,Average Velocity (mph),Occurrence Percentage (%)\n4-Seam Fastball,95.0,50.0%\n")
    h_file.write_text("Pitch Type,Average Velocity (mph),Occurrence Percentage (%)\n4-Seam Fastball,96.0,100.0%\n")

    res = client.get("/api/model/samples")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert len(data["samples"]) == 1
    sample = data["samples"][0]
    assert sample["filename"] == "chris_sale_vs_shohei_ohtani_2024.csv"
    assert "Chris Sale" in sample["pitcher_name"]
    assert "Shohei Ohtani" in sample["batter_name"]


def test_model_load_sample_and_run(client, temp_dirs):
    out_dir = temp_dirs["output"]
    model_dir = temp_dirs["model"]

    # Setup sample files
    p_file = out_dir / "chris_sale_2024_pitch_arsenal.csv"
    b_file = out_dir / "shohei_ohtani_2024_pitches_faced.csv"
    h_file = out_dir / "chris_sale_vs_shohei_ohtani_2024.csv"

    p_file.write_text("Pitch Type,Average Velocity (mph),Occurrence Percentage (%)\n4-Seam Fastball,95.0,60.0%\nChangeup,85.0,40.0%\n")
    b_file.write_text("Pitch Type,Average Velocity (mph),Occurrence Percentage (%)\n4-Seam Fastball,95.0,50.0%\nChangeup,85.0,50.0%\n")
    h_file.write_text("Pitch Type,Average Velocity (mph),Occurrence Percentage (%)\n4-Seam Fastball,96.0,100.0%\n")

    # Load sample
    load_res = client.post("/api/model/load-sample", json={"filename": "chris_sale_vs_shohei_ohtani_2024.csv"})
    assert load_res.status_code == 200
    load_data = load_res.get_json()
    assert load_data["success"] is True
    assert (model_dir / "inputPitcher.csv").exists()
    assert (model_dir / "inputBatter.csv").exists()
    assert (model_dir / "inputH2H.csv").exists()
    assert (model_dir / "run_meta.json").exists()

    # Check status
    status_res = client.get("/api/model/status")
    status_data = status_res.get_json()
    assert status_data["has_synced_data"] is True
    assert status_data["meta"]["pitcher"]["name"] == "Chris Sale"

    # Run model
    run_res = client.post("/api/model/run", json={
        "bet_line": 95.0,
        "under_odds": -115,
        "over_odds": -105,
        "stake": 100.0,
        "n_sims": 500,
    })
    assert run_res.status_code == 200
    run_data = run_res.get_json()
    assert run_data["success"] is True
    assert "result" in run_data
    assert "answer" in run_data["result"]
    assert "sides" in run_data["result"]
    assert "line" in run_data["result"]
    assert run_data["plot_url"] is not None

    # Check plot route
    plot_res = client.get("/api/model/plot")
    assert plot_res.status_code == 200
    assert plot_res.mimetype == "image/png"
    assert plot_res.headers.get("Cache-Control") == "no-cache, no-store, must-revalidate"


def test_model_run_validation(client, temp_dirs):
    # Invalid bet line
    res = client.post("/api/model/run", json={"bet_line": 200.0})
    assert res.status_code == 400
    assert "between 50 and 125" in res.get_json()["error"]

    # Invalid string line
    res = client.post("/api/model/run", json={"bet_line": "not-a-number"})
    assert res.status_code == 400

    # No files in dataModel
    res = client.post("/api/model/run", json={"bet_line": 95.0})
    assert res.status_code == 400
    assert "No pitch speed data found" in res.get_json()["error"]


def test_model_switching_samples_clears_previous_plot_and_output(client, temp_dirs):
    out_dir = temp_dirs["output"]
    model_dir = temp_dirs["model"]

    # Matchup 1
    p1 = out_dir / "chris_sale_2024_pitch_arsenal.csv"
    b1 = out_dir / "shohei_ohtani_2024_pitches_faced.csv"
    h1 = out_dir / "chris_sale_vs_shohei_ohtani_2024.csv"
    p1.write_text("Pitch Type,Average Velocity (mph),Occurrence Percentage (%)\n4-Seam Fastball,95.0,100.0%\n")
    b1.write_text("Pitch Type,Average Velocity (mph),Occurrence Percentage (%)\n4-Seam Fastball,95.0,100.0%\n")
    h1.write_text("Pitch Type,Average Velocity (mph),Occurrence Percentage (%)\n4-Seam Fastball,95.0,100.0%\n")

    # Matchup 2
    p2 = out_dir / "tarik_skubal_2024_pitch_arsenal.csv"
    b2 = out_dir / "aaron_judge_2024_pitches_faced.csv"
    h2 = out_dir / "tarik_skubal_vs_aaron_judge_2024.csv"
    p2.write_text("Pitch Type,Average Velocity (mph),Occurrence Percentage (%)\n4-Seam Fastball,97.0,100.0%\n")
    b2.write_text("Pitch Type,Average Velocity (mph),Occurrence Percentage (%)\n4-Seam Fastball,97.0,100.0%\n")
    h2.write_text("Pitch Type,Average Velocity (mph),Occurrence Percentage (%)\n4-Seam Fastball,97.0,100.0%\n")

    # 1. Load Matchup 1 and run model
    client.post("/api/model/load-sample", json={"filename": "chris_sale_vs_shohei_ohtani_2024.csv"})
    run_res = client.post("/api/model/run", json={"bet_line": 95.0, "n_sims": 500})
    assert run_res.status_code == 200

    # Status shows output and plot exist
    status_1 = client.get("/api/model/status").get_json()
    assert status_1["has_output"] is True
    assert status_1["has_plot"] is True
    assert (model_dir / "model_plot.png").exists()

    # 2. Switch to Matchup 2
    load_res = client.post("/api/model/load-sample", json={"filename": "tarik_skubal_vs_aaron_judge_2024.csv"})
    assert load_res.status_code == 200

    # Status must now show NO output and NO plot until new generation!
    status_2 = client.get("/api/model/status").get_json()
    assert status_2["has_output"] is False
    assert status_2["has_plot"] is False
    assert status_2["plot_url"] is None
    assert not (model_dir / "model_plot.png").exists()
    assert not (model_dir / "model_output.json").exists()

