"""Baseball Savant modular scraper package."""

from scraper.client import BaseballSavantClient
from scraper.config import BASE_URL, MLB_TEAM_IDS, resolve_team_id
from scraper.extractors.registry import FieldSelector, METRIC_SPECS
from scraper.exporters.base import BaseExporter
from scraper.exporters.csv_exporter import CsvExporter
from scraper.models import PlayerRecord, ScrapedDataset
from scraper.parsers.base import BaseParser
from scraper.parsers.team_page import TeamPageParser
from scraper.pipeline import ScraperPipeline
from scraper.utils import clear_output_directory

__all__ = [
    "BaseballSavantClient",
    "BaseParser",
    "TeamPageParser",
    "PlayerRecord",
    "ScrapedDataset",
    "FieldSelector",
    "METRIC_SPECS",
    "BaseExporter",
    "CsvExporter",
    "ScraperPipeline",
    "clear_output_directory",
    "BASE_URL",
    "MLB_TEAM_IDS",
    "resolve_team_id",
]

