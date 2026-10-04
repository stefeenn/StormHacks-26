"""Data models for baseball player statistics and scraped datasets."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import pandas as pd


@dataclass
class PlayerRecord:
    """Represents a player record and their statistics."""
    player_id: Optional[str]
    raw_name: str
    name: str
    season: int
    team_id: int
    metrics: Dict[str, Any] = field(default_factory=dict)
    is_aggregate: bool = False

    @classmethod
    def clean_player_name(cls, raw_name: str) -> str:
        """Convert 'Last, First' into 'First Last' cleanly."""
        cleaned = raw_name.strip()
        if "," in cleaned:
            parts = [p.strip() for p in cleaned.split(",", 1)]
            if len(parts) == 2 and parts[1]:
                return f"{parts[1]} {parts[0]}"
        return cleaned

    def get_metric(self, field_name: str, default: Any = None) -> Any:
        """Retrieve a metric by exact key or lowercase alias."""
        if field_name in self.metrics:
            return self.metrics[field_name]
        
        # Check case-insensitively
        for k, v in self.metrics.items():
            if k.lower() == field_name.lower():
                return v
        return default

    def to_dict(self, include_metadata: bool = True) -> Dict[str, Any]:
        """Convert record to a dictionary."""
        res: Dict[str, Any] = {}
        if include_metadata:
            res["Player ID"] = self.player_id
            res["Player Name"] = self.name
            res["Raw Name"] = self.raw_name
            res["Season"] = self.season
            res["Team ID"] = self.team_id
            res["Is Aggregate"] = self.is_aggregate
        else:
            res["Player"] = self.name
            
        res.update(self.metrics)
        return res


@dataclass
class ScrapedDataset:
    """Represents a collection of scraped records with metadata."""
    category: str
    team_id: int
    season: int
    headers: List[str] = field(default_factory=list)
    records: List[PlayerRecord] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def filter_roster_players(self) -> List[PlayerRecord]:
        """Return only individual roster players, excluding team/league aggregates."""
        return [r for r in self.records if not r.is_aggregate]

    def to_dataframe(self, exclude_aggregates: bool = True) -> pd.DataFrame:
        """Convert dataset to a pandas DataFrame."""
        recs = self.filter_roster_players() if exclude_aggregates else self.records
        data = [r.to_dict() for r in recs]
        return pd.DataFrame(data)

    def get_summary(self) -> Dict[str, Any]:
        """Return a summary of the scraped dataset."""
        return {
            "category": self.category,
            "team_id": self.team_id,
            "season": self.season,
            "total_records": len(self.records),
            "roster_players_count": len(self.filter_roster_players()),
            "available_headers": self.headers,
        }
