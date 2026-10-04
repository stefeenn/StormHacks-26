"""Unit tests for the end-to-end scraper pipeline."""

import csv
from unittest.mock import MagicMock
from scraper.pipeline import ScraperPipeline
from tests.test_parser import SAMPLE_HTML


def test_pipeline_mocked_run(tmp_path):
    mock_client = MagicMock()
    mock_client.fetch_team_page.return_value = SAMPLE_HTML

    pipeline = ScraperPipeline(client=mock_client)
    out_file = tmp_path / "dodgers_test.csv"

    res_path = pipeline.scrape_team_hitting_to_csv(
        team="LAD",
        season=2026,
        metrics=["BA"],
        sort_by="BA",
        sort_descending=True,
        output_path=out_file,
    )

    assert res_path == out_file
    assert out_file.exists()

    with open(out_file, mode="r", encoding="utf-8") as f:
        rows = list(csv.reader(f))

    assert rows[0] == ["Player", "Batting Average"]
    # Freeman (.288) > Ohtani (.275)
    assert rows[1] == ["Freddie Freeman", ".288"]
    assert rows[2] == ["Shohei Ohtani", ".275"]

