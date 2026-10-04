"""Pipeline orchestrator coordinating client, parser, extractor, and exporter."""

import logging
from pathlib import Path
from typing import List, Optional, Union

from scraper.client import BaseballSavantClient
from scraper.config import DEFAULT_SEASON, resolve_team_id
from scraper.extractors.registry import FieldSelector
from scraper.exporters.csv_exporter import CsvExporter
from scraper.models import ScrapedDataset
from scraper.parsers.team_page import TeamPageParser

logger = logging.getLogger(__name__)


class ScraperPipeline:
    """End-to-end scraper pipeline for Baseball Savant data."""

    def __init__(
        self,
        client: Optional[BaseballSavantClient] = None,
        parser: Optional[TeamPageParser] = None,
    ):
        self.client = client or BaseballSavantClient()
        self.parser = parser or TeamPageParser()

    def scrape_team(
        self,
        team: Union[str, int] = "LAD",
        season: int = DEFAULT_SEASON,
        category: str = "hitting",
    ) -> ScrapedDataset:
        """Fetch and parse data for a team and season.
        
        Args:
            team: Team code (e.g. 'LAD') or team ID (e.g. 119).
            season: MLB season year.
            category: Stat category ('hitting' or 'pitching').
            
        Returns:
            ScrapedDataset containing parsed records.
        """
        team_id = resolve_team_id(team)
        logger.info(f"Fetching team page for team ID {team_id}, season {season}...")
        html = self.client.fetch_team_page(team_id=team_id, season=season)

        logger.info(f"Parsing {category} statistics...")
        dataset = self.parser.parse(
            content=html,
            category=category,
            team_id=team_id,
            season=season,
        )
        return dataset

    def scrape_team_hitting_to_csv(
        self,
        team: Union[str, int] = "LAD",
        season: int = DEFAULT_SEASON,
        metrics: Optional[List[str]] = None,
        sort_by: Optional[str] = "BA",
        sort_descending: bool = True,
        exclude_aggregates: bool = True,
        output_path: Union[str, Path] = "output/dodgers_2026_batting_averages.csv",
        use_friendly_headers: bool = True,
        player_header: str = "Player",
    ) -> Path:
        """Fetch team hitting data, select metrics, sort, and export to CSV.
        
        Args:
            team: Team code or ID (defaults to 'LAD').
            season: Season year (defaults to 2026).
            metrics: List of metrics (defaults to ['BA']).
            sort_by: Metric or column to sort by (defaults to 'BA').
            sort_descending: Sort direction (default True).
            exclude_aggregates: Whether to exclude team/league totals (default True).
            output_path: Destination CSV path.
            use_friendly_headers: Use 'Batting Average' instead of 'BA' (default True).
            player_header: Column header for player name (default 'Player').
            
        Returns:
            Path of the generated CSV file.
        """
        dataset = self.scrape_team(team=team, season=season, category="hitting")

        selector = FieldSelector(
            metrics=metrics or ["BA"],
            use_friendly_headers=use_friendly_headers,
        )

        exporter = CsvExporter(
            selector=selector,
            sort_by=sort_by,
            sort_descending=sort_descending,
            exclude_aggregates=exclude_aggregates,
            player_header=player_header,
        )

        out_file = exporter.export(dataset, destination=output_path)
        logger.info(f"Scrape pipeline complete! Saved to: {out_file}")
        return out_file
