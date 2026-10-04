"""Abstract base class for all Baseball Savant HTML/JSON parsers."""

from abc import ABC, abstractmethod
from typing import Any
from scraper.models import ScrapedDataset


class BaseParser(ABC):
    """Abstract parser interface."""

    @abstractmethod
    def parse(self, content: str, **kwargs: Any) -> ScrapedDataset:
        """Parse raw content (HTML or JSON) into a ScrapedDataset.
        
        Args:
            content: Raw content string from HTTP response.
            **kwargs: Parser-specific arguments (e.g. team_id, season, category).
            
        Returns:
            Structured ScrapedDataset instance.
        """
        pass

