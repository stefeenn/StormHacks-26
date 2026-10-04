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
from scraper.pitch_analyzer import PitchAnalyzer
from scraper.player_search import PlayerSearchService

logger = logging.getLogger(__name__)


class ScraperPipeline:
    """End-to-end scraper pipeline for Baseball Savant data."""

    def __init__(
        self,
        client: Optional[BaseballSavantClient] = None,
        parser: Optional[TeamPageParser] = None,
        pitch_analyzer: Optional[PitchAnalyzer] = None,
        player_search: Optional[PlayerSearchService] = None,
    ):
        self.client = client or BaseballSavantClient()
        self.parser = parser or TeamPageParser()
        self.pitch_analyzer = pitch_analyzer or PitchAnalyzer()
        self.player_search = player_search or PlayerSearchService()

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

    def scrape_pitcher_arsenal_to_csv(
        self,
        pitcher: Union[str, int],
        pitcher_hand: str,
        batter: Optional[Union[str, int]] = None,
        batter_stance: str = "both",
        season: int = DEFAULT_SEASON,
        output_path: Optional[Union[str, Path]] = None,
    ) -> Path:
        """Fetch pitcher Statcast data, compute velocities and occurrence percentages, and export to CSV.
        
        Args:
            pitcher: Pitcher name (e.g. 'Tarik Skubal') or MLB ID.
            pitcher_hand: Pitcher throwing hand ('L', 'R', or 'both').
            batter: Optional batter name (e.g. 'Matt Olson') or MLB ID.
            batter_stance: Batter stance ('left', 'right', or 'both').
            season: MLB season year (defaults to 2026).
            output_path: Optional destination CSV path.
            
        Returns:
            Path of the exported CSV file.
        """
        # Resolve Pitcher
        if isinstance(pitcher, int) or (isinstance(pitcher, str) and str(pitcher).isdigit()):
            pitcher_id = int(pitcher)
            p_info = self.player_search.find_pitcher(pitcher_id)
            pitcher_name = p_info.full_name if p_info else f"Pitcher_{pitcher_id}"
        else:
            p_info = self.player_search.find_pitcher(pitcher)
            if not p_info:
                raise ValueError(f"Could not find pitcher matching '{pitcher}'.")
            pitcher_id = p_info.player_id
            pitcher_name = p_info.full_name

        # Resolve Batter (if provided)
        batter_id = None
        batter_name = None
        if batter:
            if isinstance(batter, int) or (isinstance(batter, str) and str(batter).isdigit()):
                batter_id = int(batter)
                b_info = self.player_search.find_batter(batter_id)
                batter_name = b_info.full_name if b_info else f"Batter_{batter_id}"
            else:
                b_info = self.player_search.find_batter(batter)
                if not b_info:
                    raise ValueError(f"Could not find batter matching '{batter}'.")
                batter_id = b_info.player_id
                batter_name = b_info.full_name

        logger.info(
            f"Querying Statcast for {pitcher_name} (Throws: {pitcher_hand})"
            + (f" vs {batter_name} (Stance: {batter_stance})" if batter_name else f" (Stance: {batter_stance})")
            + f" in season {season}..."
        )

        csv_text = self.client.fetch_statcast_pitches(
            pitcher_id=pitcher_id,
            batter_id=batter_id,
            season=season,
        )

        result_df = self.pitch_analyzer.analyze(
            raw_data=csv_text,
            pitcher_hand=pitcher_hand,
            batter_stance=batter_stance,
        )

        if not output_path:
            p_slug = pitcher_name.lower().replace(" ", "_").replace(".", "").replace(",", "")
            if batter_name:
                b_slug = batter_name.lower().replace(" ", "_").replace(".", "").replace(",", "")
                dest = Path(f"output/{p_slug}_vs_{b_slug}_{season}.csv")
            else:
                dest = Path(f"output/{p_slug}_{season}_pitch_arsenal.csv")
        else:
            dest = Path(output_path)

        dest.parent.mkdir(parents=True, exist_ok=True)
        result_df.to_csv(dest, index=False)
        logger.info(f"Successfully exported {len(result_df)} pitch types to {dest}")
        return dest
