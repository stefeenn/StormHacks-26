"""Unit tests for data exporters."""

import csv
from scraper.models import PlayerRecord, ScrapedDataset
from scraper.extractors.registry import FieldSelector
from scraper.exporters.csv_exporter import CsvExporter


def test_csv_exporter_sorting_and_content(tmp_path):
    p1 = PlayerRecord(
        player_id="1",
        raw_name="Freeman, Freddie",
        name="Freddie Freeman",
        season=2026,
        team_id=119,
        metrics={"BA": 0.288, "HR": 16},
    )
    p2 = PlayerRecord(
        player_id="2",
        raw_name="De Paula, Josue",
        name="Josue De Paula",
        season=2026,
        team_id=119,
        metrics={"BA": 0.323, "HR": 1},
    )
    p3 = PlayerRecord(
        player_id="3",
        raw_name="Alfonzo, Eliezer",
        name="Eliezer Alfonzo",
        season=2026,
        team_id=119,
        metrics={"BA": 0.179, "HR": 0},
    )
    agg = PlayerRecord(
        player_id=None,
        raw_name="Dodgers",
        name="Dodgers",
        season=2026,
        team_id=119,
        metrics={"BA": 0.257, "HR": 204},
        is_aggregate=True,
    )

    dataset = ScrapedDataset(
        category="hitting",
        team_id=119,
        season=2026,
        headers=["Player", "Season", "BA", "HR"],
        records=[p1, p2, p3, agg],
    )

    selector = FieldSelector(metrics=["BA"], use_friendly_headers=True)
    exporter = CsvExporter(
        selector=selector,
        sort_by="BA",
        sort_descending=True,
        exclude_aggregates=True,
    )

    out_file = tmp_path / "test_output.csv"
    exporter.export(dataset, destination=out_file)

    assert out_file.exists()
    with open(out_file, mode="r", encoding="utf-8") as f:
        reader = list(csv.reader(f))

    # Header check
    assert reader[0] == ["Player", "Batting Average"]
    # 3 roster players (aggregate excluded)
    assert len(reader) == 4

    # Descending order check: Josue De Paula (.323) -> Freddie Freeman (.288) -> Eliezer Alfonzo (.179)
    assert reader[1] == ["Josue De Paula", ".323"]
    assert reader[2] == ["Freddie Freeman", ".288"]
    assert reader[3] == ["Eliezer Alfonzo", ".179"]
