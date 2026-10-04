"""CSV exporter for Baseball Savant scraped data."""

import csv
import logging
from pathlib import Path
from typing import List, Optional, Union

from scraper.extractors.registry import FieldSelector
from scraper.models import PlayerRecord, ScrapedDataset
from scraper.exporters.base import BaseExporter

logger = logging.getLogger(__name__)


class CsvExporter(BaseExporter):
    """Exports scraped player datasets to CSV with configurable sorting and columns."""

    def __init__(
        self,
        selector: Optional[FieldSelector] = None,
        sort_by: Optional[str] = "BA",
        sort_descending: bool = True,
        exclude_aggregates: bool = True,
        player_header: str = "Player",
    ):
        """
        Args:
            selector: FieldSelector defining which columns to export.
            sort_by: Metric/field to sort records by (e.g. 'BA', 'Player').
            sort_descending: If True, sorts highest to lowest for metrics.
            exclude_aggregates: If True, excludes team/league summary rows.
            player_header: Display header for the player name column.
        """
        self.selector = selector or FieldSelector()
        self.sort_by = sort_by
        self.sort_descending = sort_descending
        self.exclude_aggregates = exclude_aggregates
        self.player_header = player_header

    def export(
        self,
        dataset: ScrapedDataset,
        destination: Union[str, Path],
        **kwargs,
    ) -> Path:
        """Export dataset records to CSV file.
        
        Args:
            dataset: ScrapedDataset to export.
            destination: Path to write the CSV to.
            
        Returns:
            Path of the exported file.
        """
        output_path = Path(destination)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Select records
        records: List[PlayerRecord] = (
            dataset.filter_roster_players()
            if self.exclude_aggregates
            else list(dataset.records)
        )

        # Sort records
        if self.sort_by:
            if self.sort_by.lower() in ["player", "name", "player name"]:
                records.sort(
                    key=lambda r: r.name.lower(),
                    reverse=self.sort_descending,
                )
            else:
                records.sort(
                    key=lambda r: self.selector.get_sort_key_for_metric(r, self.sort_by),
                    reverse=self.sort_descending,
                )

        headers = self.selector.get_column_headers(player_header=self.player_header)

        with open(output_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()

            for record in records:
                row = self.selector.extract_row(
                    record,
                    player_header=self.player_header,
                    formatted=True,
                )
                writer.writerow(row)

        logger.info(f"Successfully exported {len(records)} rows to {output_path}")
        return output_path

