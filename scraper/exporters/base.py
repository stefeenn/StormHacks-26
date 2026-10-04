"""Abstract base exporter interface."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Union
from scraper.models import ScrapedDataset


class BaseExporter(ABC):
    """Abstract interface for data exporters."""

    @abstractmethod
    def export(
        self,
        dataset: ScrapedDataset,
        destination: Union[str, Path],
        **kwargs: Any,
    ) -> Path:
        """Export a ScrapedDataset to a destination file.
        
        Args:
            dataset: The dataset containing scraped records.
            destination: File path destination.
            **kwargs: Exporter specific parameters.
            
        Returns:
            Path object of the written file.
        """
        pass
