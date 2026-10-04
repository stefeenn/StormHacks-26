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
    "BASE_URL",
    "MLB_TEAM_IDS",
    "resolve_team_id",
]

