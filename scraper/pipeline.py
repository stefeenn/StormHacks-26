"""Pipeline orchestrator coordinating client, parser, extractor, and exporter."""

import logging
from pathlib import Path
from typing import List, Optional, Union

from scraper.client import BaseballSavantClient
from scraper.config import DEFAULT_SEASON, normalize_count, resolve_team_id
from scraper.data_model_sync import DataModelSync
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
        data_model_sync: Optional[DataModelSync] = None,
    ):
        self.client = client or BaseballSavantClient()
        self.parser = parser or TeamPageParser()
        self.pitch_analyzer = pitch_analyzer or PitchAnalyzer()
        self.player_search = player_search or PlayerSearchService()
        self.data_model_sync = data_model_sync

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
        count: Optional[str] = None,
        output_path: Optional[Union[str, Path]] = None,
    ) -> Path:
        """Fetch pitcher Statcast data, compute velocities and occurrence percentages, and export to CSV.
        
        Args:
            pitcher: Pitcher name (e.g. 'Tarik Skubal') or MLB ID.
            pitcher_hand: Pitcher throwing hand ('L', 'R', or 'both').
            batter: Optional batter name (e.g. 'Matt Olson') or MLB ID.
            batter_stance: Batter stance ('left', 'right', or 'both').
            season: MLB season year (defaults to 2026).
            count: Optional ball-strike count filter ('0-0', '2-1', etc.).
            output_path: Optional destination CSV path.
            
        Returns:
            Path of the exported CSV file.
        """
        norm_count = normalize_count(count) if count else None

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
            + (f" count {norm_count}" if norm_count else "")
            + f" in season {season}..."
        )

        csv_text = self.client.fetch_statcast_pitches(
            pitcher_id=pitcher_id,
            batter_id=batter_id,
            season=season,
            count=norm_count,
        )

        result_df = self.pitch_analyzer.analyze(
            raw_data=csv_text,
            pitcher_hand=pitcher_hand,
            batter_stance=batter_stance,
            count=norm_count,
        )

        if not output_path:
            p_slug = pitcher_name.lower().replace(" ", "_").replace(".", "").replace(",", "")
            c_slug = f"_count_{norm_count.replace('-', '_')}" if norm_count else ""
            if batter_name:
                b_slug = batter_name.lower().replace(" ", "_").replace(".", "").replace(",", "")
                dest = Path(f"output/{p_slug}_vs_{b_slug}_{season}{c_slug}.csv")
            else:
                dest = Path(f"output/{p_slug}_{season}{c_slug}_pitch_arsenal.csv")
        else:
            dest = Path(output_path)

        dest.parent.mkdir(parents=True, exist_ok=True)
        result_df.to_csv(dest, index=False)
        logger.info(f"Successfully exported {len(result_df)} pitch types to {dest}")
        return dest

    def scrape_batter_pitches_to_csv(
        self,
        batter: Union[str, int],
        batter_stance: str,
        pitcher: Optional[Union[str, int]] = None,
        pitcher_hand: str = "both",
        season: int = DEFAULT_SEASON,
        count: Optional[str] = None,
        output_path: Optional[Union[str, Path]] = None,
    ) -> Path:
        """Fetch batter Statcast data, compute pitch velocities and occurrence percentages faced, and export to CSV.
        
        Args:
            batter: Batter name (e.g. 'Matt Olson') or MLB ID.
            batter_stance: Batter stance ('left', 'right', or 'both').
            pitcher: Optional pitcher name (e.g. 'Tarik Skubal') or MLB ID.
            pitcher_hand: Pitcher throwing hand ('L', 'R', or 'both').
            season: MLB season year (defaults to 2026).
            count: Optional ball-strike count filter ('0-0', '2-1', etc.).
            output_path: Optional destination CSV path.
            
        Returns:
            Path of the exported CSV file.
        """
        norm_count = normalize_count(count) if count else None

        # Resolve Batter
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

        # Resolve Pitcher (if provided)
        pitcher_id = None
        pitcher_name = None
        if pitcher:
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

        logger.info(
            f"Querying Statcast for batter {batter_name} (Stance: {batter_stance})"
            + (f" vs pitcher {pitcher_name} (Throws: {pitcher_hand})" if pitcher_name else f" (Pitcher Hand: {pitcher_hand})")
            + (f" count {norm_count}" if norm_count else "")
            + f" in season {season}..."
        )

        csv_text = self.client.fetch_statcast_pitches(
            pitcher_id=pitcher_id,
            batter_id=batter_id,
            player_type="batter",
            season=season,
            count=norm_count,
        )

        result_df = self.pitch_analyzer.analyze(
            raw_data=csv_text,
            pitcher_hand=pitcher_hand,
            batter_stance=batter_stance,
            count=norm_count,
        )

        if not output_path:
            b_slug = batter_name.lower().replace(" ", "_").replace(".", "").replace(",", "")
            c_slug = f"_count_{norm_count.replace('-', '_')}" if norm_count else ""
            if pitcher_name:
                p_slug = pitcher_name.lower().replace(" ", "_").replace(".", "").replace(",", "")
                dest = Path(f"output/{b_slug}_vs_{p_slug}_{season}{c_slug}.csv")
            else:
                dest = Path(f"output/{b_slug}_{season}{c_slug}_pitches_faced.csv")
        else:
            dest = Path(output_path)

        dest.parent.mkdir(parents=True, exist_ok=True)
        result_df.to_csv(dest, index=False)
        logger.info(f"Successfully exported {len(result_df)} pitch types to {dest}")
        return dest

    def scrape_head_to_head_to_csv(
        self,
        mode: str,
        pitcher: Union[str, int],
        pitcher_hand: str,
        batter: Union[str, int],
        batter_stance: str,
        season: int = DEFAULT_SEASON,
        count: Optional[str] = None,
        output_path: Optional[Union[str, Path]] = None,
        sync_data_model: bool = True,
        data_model_dir: Optional[Union[str, Path]] = None,
    ) -> dict:
        """Fetch three sets of Statcast data for a head-to-head matchup:
        1. First player mentioned's individual statistics
        2. Second player mentioned's individual statistics
        3. Head-to-head matchup statistics
        
        Args:
            mode: Search mode indicating which player was entered first ('pitcher' or 'batter').
            pitcher: Pitcher name or MLB ID.
            pitcher_hand: Pitcher throwing hand ('L', 'R', or 'both').
            batter: Batter name or MLB ID.
            batter_stance: Batter stance ('left', 'right', or 'both').
            season: MLB season year (defaults to DEFAULT_SEASON).
            count: Optional ball-strike count filter ('0-0', '2-1', etc.).
            output_path: Optional custom output path for the head-to-head CSV.
            sync_data_model: Whether to copy outputs into dataModel/ (default True).
            data_model_dir: Optional custom path to dataModel directory.
            
        Returns:
            Dictionary containing metadata, player dicts, matchup dict, files_in_order list:
            [player1_file, player2_file, h2h_file], and data_model_sync status.
        """
        # Resolve names for labeling
        if isinstance(pitcher, int) or (isinstance(pitcher, str) and str(pitcher).isdigit()):
            p_info = self.player_search.find_pitcher(int(pitcher))
            pitcher_name = p_info.full_name if p_info else f"Pitcher_{pitcher}"
        else:
            p_info = self.player_search.find_pitcher(pitcher)
            pitcher_name = p_info.full_name if p_info else str(pitcher)

        if isinstance(batter, int) or (isinstance(batter, str) and str(batter).isdigit()):
            b_info = self.player_search.find_batter(int(batter))
            batter_name = b_info.full_name if b_info else f"Batter_{batter}"
        else:
            b_info = self.player_search.find_batter(batter)
            batter_name = b_info.full_name if b_info else str(batter)

        norm_count = normalize_count(count) if count else None

        if mode == "batter":
            # 1. First player mentioned: Batter (individual)
            p1_file = self.scrape_batter_pitches_to_csv(
                batter=batter,
                batter_stance=batter_stance,
                pitcher=None,
                pitcher_hand="both",
                season=season,
                count=norm_count,
            )
            # 2. Second player mentioned: Pitcher (individual)
            p2_file = self.scrape_pitcher_arsenal_to_csv(
                pitcher=pitcher,
                pitcher_hand=pitcher_hand,
                batter=None,
                batter_stance="both",
                season=season,
                count=norm_count,
            )
            # 3. Head-to-Head matchup
            h2h_file = self.scrape_batter_pitches_to_csv(
                batter=batter,
                batter_stance=batter_stance,
                pitcher=pitcher,
                pitcher_hand=pitcher_hand,
                season=season,
                count=norm_count,
                output_path=output_path,
            )
            result = {
                "mode": "batter",
                "player1": {
                    "name": batter_name,
                    "role": "Batter",
                    "type": "batter",
                    "file": p1_file,
                },
                "player2": {
                    "name": pitcher_name,
                    "role": "Pitcher",
                    "type": "pitcher",
                    "file": p2_file,
                },
                "matchup": {
                    "name": f"{batter_name} vs {pitcher_name}",
                    "role": "Head-to-Head",
                    "type": "matchup",
                    "file": h2h_file,
                },
                "files_in_order": [p1_file, p2_file, h2h_file],
                "season": season,
                "count": norm_count,
            }
        else:
            # mode == "pitcher" (default)
            # 1. First player mentioned: Pitcher (individual)
            p1_file = self.scrape_pitcher_arsenal_to_csv(
                pitcher=pitcher,
                pitcher_hand=pitcher_hand,
                batter=None,
                batter_stance="both",
                season=season,
                count=norm_count,
            )
            # 2. Second player mentioned: Batter (individual)
            p2_file = self.scrape_batter_pitches_to_csv(
                batter=batter,
                batter_stance=batter_stance,
                pitcher=None,
                pitcher_hand="both",
                season=season,
                count=norm_count,
            )
            # 3. Head-to-Head matchup
            h2h_file = self.scrape_pitcher_arsenal_to_csv(
                pitcher=pitcher,
                pitcher_hand=pitcher_hand,
                batter=batter,
                batter_stance=batter_stance,
                season=season,
                count=norm_count,
                output_path=output_path,
            )
            result = {
                "mode": "pitcher",
                "player1": {
                    "name": pitcher_name,
                    "role": "Pitcher",
                    "type": "pitcher",
                    "file": p1_file,
                },
                "player2": {
                    "name": batter_name,
                    "role": "Batter",
                    "type": "batter",
                    "file": p2_file,
                },
                "matchup": {
                    "name": f"{pitcher_name} vs {batter_name}",
                    "role": "Head-to-Head",
                    "type": "matchup",
                    "file": h2h_file,
                },
                "files_in_order": [p1_file, p2_file, h2h_file],
                "season": season,
                "count": norm_count,
            }

        if sync_data_model:
            syncer = self.data_model_sync or DataModelSync(data_model_dir=data_model_dir)
            try:
                sync_res = syncer.sync_matchup(
                    matchup_result=result,
                    pitcher_hand=pitcher_hand,
                    batter_stance=batter_stance,
                )
                result["data_model_sync"] = sync_res
            except Exception as e:
                logger.warning(f"Failed to sync files to dataModel: {e}", exc_info=True)
                result["data_model_sync"] = {"success": False, "error": str(e)}

        return result

