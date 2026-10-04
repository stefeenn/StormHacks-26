"""Unit tests verifying that head-to-head matchup queries generate 3 datasets
and spit out results in the console in exact order:
1. First player mentioned's stats
2. Second player mentioned's stats
3. Head-to-head stats
"""

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from main import run_pitch_scraper, run_batter_scraper


def test_pitch_scraper_head_to_head_console_order(tmp_path: Path):
    """Verify that in pitcher mode with a batter, preview tables are displayed in order:
    1. Pitcher individual stats
    2. Batter individual stats
    3. Head-to-head stats
    """
    p1_file = tmp_path / "chris_sale_2026_pitch_arsenal.csv"
    p2_file = tmp_path / "shohei_ohtani_2026_pitches_faced.csv"
    h2h_file = tmp_path / "chris_sale_vs_shohei_ohtani_2026.csv"

    p1_file.write_text("Pitch Type,Velocity\nSlider,85.0\n")
    p2_file.write_text("Pitch Type,Velocity\nFastball,95.0\n")
    h2h_file.write_text("Pitch Type,Velocity\nSlider,86.0\n")

    mock_pipeline = MagicMock()
    mock_pipeline.scrape_head_to_head_to_csv.return_value = {
        "mode": "pitcher",
        "player1": {"name": "Chris Sale", "role": "Pitcher", "file": p1_file},
        "player2": {"name": "Shohei Ohtani", "role": "Batter", "file": p2_file},
        "matchup": {"name": "Chris Sale vs Shohei Ohtani", "file": h2h_file},
        "files_in_order": [p1_file, p2_file, h2h_file],
        "season": 2026,
    }

    mock_args = MagicMock()
    mock_args.output = None
    mock_args.verbose = False

    inputs = {
        "pitcher_name": "Chris Sale",
        "pitcher_hand": "L",
        "batter_name": "Shohei Ohtani",
        "batter_stance": "left",
        "season": 2026,
    }

    with patch("main.display_csv_preview") as mock_preview:
        run_pitch_scraper(mock_args, mock_pipeline, inputs=inputs)

        mock_pipeline.scrape_head_to_head_to_csv.assert_called_once_with(
            mode="pitcher",
            pitcher="Chris Sale",
            pitcher_hand="L",
            batter="Shohei Ohtani",
            batter_stance="left",
            season=2026,
            count=None,
            output_path=None,
        )

        assert mock_preview.call_count == 3
        calls = [c[0][0] for c in mock_preview.call_args_list]
        # Order: 1. Chris Sale (first mentioned), 2. Shohei Ohtani (second mentioned), 3. H2H
        assert calls == [p1_file, p2_file, h2h_file]


def test_batter_scraper_head_to_head_console_order(tmp_path: Path):
    """Verify that in batter mode with a pitcher, preview tables are displayed in order:
    1. Batter individual stats (first player mentioned)
    2. Pitcher individual stats (second player mentioned)
    3. Head-to-head stats
    """
    b1_file = tmp_path / "shohei_ohtani_2026_pitches_faced.csv"
    p2_file = tmp_path / "chris_sale_2026_pitch_arsenal.csv"
    h2h_file = tmp_path / "shohei_ohtani_vs_chris_sale_2026.csv"

    b1_file.write_text("Pitch Type,Velocity\nFastball,95.0\n")
    p2_file.write_text("Pitch Type,Velocity\nSlider,85.0\n")
    h2h_file.write_text("Pitch Type,Velocity\nSlider,86.0\n")

    mock_pipeline = MagicMock()
    mock_pipeline.scrape_head_to_head_to_csv.return_value = {
        "mode": "batter",
        "player1": {"name": "Shohei Ohtani", "role": "Batter", "file": b1_file},
        "player2": {"name": "Chris Sale", "role": "Pitcher", "file": p2_file},
        "matchup": {"name": "Shohei Ohtani vs Chris Sale", "file": h2h_file},
        "files_in_order": [b1_file, p2_file, h2h_file],
        "season": 2026,
    }

    mock_args = MagicMock()
    mock_args.output = None
    mock_args.verbose = False

    inputs = {
        "batter_name": "Shohei Ohtani",
        "batter_stance": "left",
        "pitcher_name": "Chris Sale",
        "pitcher_hand": "L",
        "season": 2026,
    }

    with patch("main.display_csv_preview") as mock_preview:
        run_batter_scraper(mock_args, mock_pipeline, inputs=inputs)

        mock_pipeline.scrape_head_to_head_to_csv.assert_called_once_with(
            mode="batter",
            pitcher="Chris Sale",
            pitcher_hand="L",
            batter="Shohei Ohtani",
            batter_stance="left",
            season=2026,
            count=None,
            output_path=None,
        )

        assert mock_preview.call_count == 3
        calls = [c[0][0] for c in mock_preview.call_args_list]
        # Order: 1. Shohei Ohtani (first mentioned), 2. Chris Sale (second mentioned), 3. H2H
        assert calls == [b1_file, p2_file, h2h_file]
