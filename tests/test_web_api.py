"""Unit and integration tests for the Baseball Savant web interface and REST API."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from scraper.player_search import PlayerInfo
from web.app import create_app


@pytest.fixture
def mock_search_service():
    service = MagicMock()
    mock_pitcher = PlayerInfo(
        player_id=669373,
        full_name="Tarik Skubal",
        primary_position="P",
        is_pitcher=True,
        pitch_hand="L",
        bat_side="R",
        active=True,
    )
    mock_batter = PlayerInfo(
        player_id=660271,
        full_name="Shohei Ohtani",
        primary_position="DH",
        is_pitcher=False,
        pitch_hand="R",
        bat_side="L",
        active=True,
    )

    def search_side_effect(query, player_type=None):
        if "skubal" in str(query).lower():
            return [mock_pitcher]
        elif "ohtani" in str(query).lower():
            return [mock_batter]
        return []

    service.search_player.side_effect = search_side_effect
    return service


@pytest.fixture
def mock_pipeline(tmp_path: Path):
    pipeline = MagicMock()

    def fake_pitcher_scrape(*args, **kwargs):
        out_file = tmp_path / "tarik_skubal_2026_pitch_arsenal.csv"
        out_file.write_text("Pitch Type,Average Velocity (mph),Occurrence Percentage (%)\n4-Seam Fastball,96.8,45.2%\nChangeup,86.5,30.1%\n")
        return out_file

    def fake_batter_scrape(*args, **kwargs):
        out_file = tmp_path / "shohei_ohtani_2026_pitches_faced.csv"
        out_file.write_text("Pitch Type,Average Velocity (mph),Occurrence Percentage (%)\nSlider,84.2,40.0%\n4-Seam Fastball,95.1,60.0%\n")
        return out_file

    def fake_head_to_head_scrape(mode="pitcher", *args, **kwargs):
        p1_file = tmp_path / "tarik_skubal_2026_pitch_arsenal.csv"
        p1_file.write_text("Pitch Type,Average Velocity (mph),Occurrence Percentage (%)\n4-Seam Fastball,96.8,45.2%\nChangeup,86.5,30.1%\n")
        p2_file = tmp_path / "shohei_ohtani_2026_pitches_faced.csv"
        p2_file.write_text("Pitch Type,Average Velocity (mph),Occurrence Percentage (%)\nSlider,84.2,40.0%\n4-Seam Fastball,95.1,60.0%\n")
        h2h_file = tmp_path / "tarik_skubal_vs_shohei_ohtani_2026.csv"
        h2h_file.write_text("Pitch Type,Average Velocity (mph),Occurrence Percentage (%)\nSlider,89.5,100.0%\n")
        return {
            "mode": mode,
            "player1": {"name": "Tarik Skubal", "role": "Pitcher", "file": p1_file},
            "player2": {"name": "Shohei Ohtani", "role": "Batter", "file": p2_file},
            "matchup": {"name": "Tarik Skubal vs Shohei Ohtani", "file": h2h_file},
            "files_in_order": [p1_file, p2_file, h2h_file],
            "season": 2026,
        }

    pipeline.scrape_pitcher_arsenal_to_csv.side_effect = fake_pitcher_scrape
    pipeline.scrape_batter_pitches_to_csv.side_effect = fake_batter_scrape
    pipeline.scrape_head_to_head_to_csv.side_effect = fake_head_to_head_scrape
    return pipeline


@pytest.fixture
def client(tmp_path: Path, mock_search_service, mock_pipeline):
    app = create_app(
        output_dir=str(tmp_path),
        scraper_pipeline=mock_pipeline,
        player_search_service=mock_search_service,
    )
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_index_page_loads(client):
    """Verify main page renders with centered title, dropdown, and modal markup."""
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Baseball Savant Statcast Explorer" in html
    assert "header-center-title" in html
    assert "recent-dropdown-container" in html
    assert "csv-modal" in html
    assert "Recent Searches" in html


def test_api_search_player_empty(client):
    """Verify searching with empty query returns empty list."""
    resp = client.get("/api/search/player?query=")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["results"] == []


def test_api_search_player_found(client):
    """Verify searching player returns structured player info."""
    resp = client.get("/api/search/player?query=Skubal&type=pitcher")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["results"]) == 1
    p = data["results"][0]
    assert p["full_name"] == "Tarik Skubal"
    assert p["is_pitcher"] is True
    assert p["pitch_hand"] == "L"


def test_api_scrape_pitcher_validation(client):
    """Verify scrape returns 400 if pitcher name is missing in pitcher mode."""
    resp = client.post(
        "/api/scrape",
        data=json.dumps({"search_mode": "pitcher", "pitcher_name": ""}),
        content_type="application/json",
    )
    assert resp.status_code == 400
    assert "Pitcher name is required" in resp.get_json()["error"]


def test_api_scrape_batter_validation(client):
    """Verify scrape returns 400 if batter name is missing in batter mode."""
    resp = client.post(
        "/api/scrape",
        data=json.dumps({"search_mode": "batter", "batter_name": ""}),
        content_type="application/json",
    )
    assert resp.status_code == 400
    assert "Batter name is required" in resp.get_json()["error"]


def test_api_scrape_pitcher_success(client):
    """Verify executing pitcher scrape returns generated file details and parsed CSV data."""
    payload = {
        "search_mode": "pitcher",
        "pitcher_name": "Tarik Skubal",
        "pitcher_hand": "L",
        "batter_name": "",
        "batter_stance": "both",
        "season": 2026,
    }
    resp = client.post(
        "/api/scrape",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["filename"] == "tarik_skubal_2026_pitch_arsenal.csv"
    assert "Pitch Type" in data["columns"]
    assert len(data["rows"]) == 2
    assert data["rows"][0]["Pitch Type"] == "4-Seam Fastball"


def test_api_recent_searches(client, tmp_path: Path):
    """Verify /api/recent discovers CSV files in output folder."""
    # Create sample CSV in the output directory
    csv_file = tmp_path / "chris_sale_2021_pitch_arsenal.csv"
    csv_file.write_text("Pitch Type,Average Velocity,Occurrence\n4-Seam Fastball,94.8,56.5%\n")

    resp = client.get("/api/recent")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "recent" in data
    filenames = [item["filename"] for item in data["recent"]]
    assert "chris_sale_2021_pitch_arsenal.csv" in filenames


def test_api_csv_data_security_traversal(client):
    """Verify path traversal attempts in /api/csv-data are rejected."""
    resp = client.get("/api/csv-data?filename=../secret.csv")
    assert resp.status_code == 400
    assert "Invalid filename" in resp.get_json()["error"]


def test_api_csv_data_not_found(client):
    """Verify requesting non-existent CSV returns 404."""
    resp = client.get("/api/csv-data?filename=missing_file.csv")
    assert resp.status_code == 404


def test_api_csv_data_success(client, tmp_path: Path):
    """Verify reading valid CSV file parses headers and rows properly."""
    csv_file = tmp_path / "test_arsenal.csv"
    csv_file.write_text("Pitch Type,Velocity,Usage\nSinker,92.5,45%\nSlider,84.1,55%\n")

    resp = client.get("/api/csv-data?filename=test_arsenal.csv")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["filename"] == "test_arsenal.csv"
    assert data["columns"] == ["Pitch Type", "Velocity", "Usage"]
    assert len(data["rows"]) == 2
    assert data["total_rows"] == 2


def test_api_clear_output(client, tmp_path: Path):
    """Verify /api/clear-output wipes generated files."""
    file1 = tmp_path / "file1.csv"
    file1.write_text("data")
    assert file1.exists()

    resp = client.post("/api/clear-output")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["cleared_count"] >= 1
    assert not file1.exists()


def test_api_scrape_matchup_success(client):
    """Verify head-to-head scrape returns 3 sets of data (player1, player2, and matchup)."""
    payload = {
        "search_mode": "pitcher",
        "pitcher_name": "Tarik Skubal",
        "pitcher_hand": "L",
        "batter_name": "Shohei Ohtani",
        "batter_stance": "left",
        "season": 2026,
    }
    resp = client.post(
        "/api/scrape",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["is_matchup"] is True
    assert data["filename"] == "tarik_skubal_vs_shohei_ohtani_2026.csv"
    assert "player1" in data
    assert "player2" in data
    assert "matchup" in data
    assert data["player1"]["name"] == "Tarik Skubal"
    assert data["player1"]["role"] == "Pitcher"
    assert data["player2"]["name"] == "Shohei Ohtani"
    assert data["player2"]["role"] == "Batter"
    assert data["matchup"]["name"] == "Tarik Skubal vs Shohei Ohtani"
    assert len(data["player1"]["rows"]) == 2
    assert len(data["player2"]["rows"]) == 2
    assert len(data["matchup"]["rows"]) == 1


def test_api_csv_data_matchup(client, tmp_path: Path):
    """Verify /api/csv-data identifies head-to-head files and returns companion data."""
    p1 = tmp_path / "chris_sale_2026_pitch_arsenal.csv"
    p1.write_text("Pitch Type,Velocity,Usage\nSlider,85.2,40%\n")
    p2 = tmp_path / "shohei_ohtani_2026_pitches_faced.csv"
    p2.write_text("Pitch Type,Velocity,Usage\nFastball,96.1,60%\n")
    h2h = tmp_path / "chris_sale_vs_shohei_ohtani_2026.csv"
    h2h.write_text("Pitch Type,Velocity,Usage\nSlider,86.0,100%\n")

    resp = client.get("/api/csv-data?filename=chris_sale_vs_shohei_ohtani_2026.csv")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["is_matchup"] is True
    assert "player1" in data
    assert "player2" in data
    assert "matchup" in data
    assert data["player1"]["filename"] == "chris_sale_2026_pitch_arsenal.csv"
    assert data["player2"]["filename"] == "shohei_ohtani_2026_pitches_faced.csv"
    assert data["matchup"]["filename"] == "chris_sale_vs_shohei_ohtani_2026.csv"


def test_api_download_zip_success(client, tmp_path: Path):
    """Verify /api/download-zip packages files into a valid zip archive."""
    f1 = tmp_path / "f1.csv"
    f1.write_text("a,b\n1,2\n")
    f2 = tmp_path / "f2.csv"
    f2.write_text("c,d\n3,4\n")

    resp = client.get("/api/download-zip?files=f1.csv&files=f2.csv&zip_name=my_export.zip")
    assert resp.status_code == 200
    assert resp.mimetype == "application/zip"
    assert "my_export.zip" in resp.headers.get("Content-Disposition", "")

    import io
    import zipfile
    zf = zipfile.ZipFile(io.BytesIO(resp.data))
    namelist = zf.namelist()
    assert "f1.csv" in namelist
    assert "f2.csv" in namelist
    assert zf.read("f1.csv").decode("utf-8") == "a,b\n1,2\n"


def test_api_download_zip_no_files(client):
    """Verify /api/download-zip returns 400 when no files are requested."""
    resp = client.get("/api/download-zip")
    assert resp.status_code == 400


