"""Metric registry and modular field extraction for Baseball Savant data."""

from typing import Any, Callable, Dict, List, Optional
from scraper.config import METRIC_ALIASES
from scraper.models import PlayerRecord


# Metric formatting definitions (e.g. format batting average as .300)
def format_batting_average(val: Any) -> str:
    """Format batting average as .XXX (or original)."""
    if val is None:
        return ""
    if isinstance(val, (float, int)):
        if 0.0 <= val < 1.0:
            formatted = f"{val:.3f}"
            return formatted[1:] if formatted.startswith("0") else formatted
        return f"{val:.3f}"
    val_str = str(val).strip()
    return val_str


def format_standard_float(val: Any, decimals: int = 1) -> str:
    """Format float with standard decimal places."""
    if val is None:
        return ""
    if isinstance(val, (float, int)):
        return f"{val:.{decimals}f}"
    return str(val)


def format_integer(val: Any) -> str:
    """Format integer with thousands separator."""
    if val is None:
        return ""
    if isinstance(val, int):
        return f"{val:,}"
    return str(val)


# Built-in metric specifications
METRIC_SPECS: Dict[str, Dict[str, Any]] = {
    "BA": {
        "display_name": "Batting Average",
        "description": "Hits divided by At Bats",
        "formatter": format_batting_average,
    },
    "OBP": {
        "display_name": "On-Base Percentage",
        "description": "On-Base Percentage",
        "formatter": format_batting_average,
    },
    "SLG": {
        "display_name": "Slugging Percentage",
        "description": "Total bases divided by At Bats",
        "formatter": format_batting_average,
    },
    "OPS": {
        "display_name": "OPS",
        "description": "OBP + SLG",
        "compute": lambda r: (
            (r.get_metric("OBP") or 0.0) + (r.get_metric("SLG") or 0.0)
            if r.get_metric("OBP") is not None and r.get_metric("SLG") is not None
            else None
        ),
        "formatter": lambda v: f"{v:.3f}" if isinstance(v, (float, int)) else str(v or ""),
    },
    "xBA": {
        "display_name": "Expected Batting Average",
        "description": "Statcast expected batting average based on exit velo & launch angle",
        "formatter": format_batting_average,
    },
    "ExitVelocity": {
        "display_name": "Exit Velocity (mph)",
        "description": "Average exit velocity off the bat",
        "formatter": lambda v: format_standard_float(v, 1),
    },
    "Hard Hit %": {
        "display_name": "Hard Hit %",
        "description": "Percentage of balls hit 95+ mph",
        "formatter": lambda v: format_standard_float(v, 1),
    },
    "HR": {
        "display_name": "Home Runs",
        "description": "Total home runs",
        "formatter": format_integer,
    },
    "H": {
        "display_name": "Hits",
        "description": "Total hits",
        "formatter": format_integer,
    },
    "AB": {
        "display_name": "At Bats",
        "description": "Total at bats",
        "formatter": format_integer,
    },
    "PA": {
        "display_name": "Plate Appearances",
        "description": "Total plate appearances",
        "formatter": format_integer,
    },
}


class FieldSelector:
    """Configures and extracts selected fields and metrics from player records."""

    def __init__(
        self,
        metrics: Optional[List[str]] = None,
        use_friendly_headers: bool = True,
        custom_formatters: Optional[Dict[str, Callable[[Any], str]]] = None,
    ):
        """
        Args:
            metrics: List of metric codes/aliases, e.g. ['BA'], ['batting_average', 'HR'].
                     If None or empty, defaults to ['BA'].
            use_friendly_headers: Whether to use 'Batting Average' instead of 'BA'.
            custom_formatters: Optional custom formatters for specific metrics.
        """
        self.metrics = metrics or ["BA"]
        self.use_friendly_headers = use_friendly_headers
        self.custom_formatters = custom_formatters or {}
        self._resolved_fields = self._resolve_metrics(self.metrics)

    def _resolve_metrics(self, requested: List[str]) -> List[Dict[str, Any]]:
        """Map requested metrics to internal keys, display names, and formatters."""
        resolved = []
        for item in requested:
            clean = item.strip()
            # Check aliases
            key = METRIC_ALIASES.get(clean.lower(), clean)
            spec = METRIC_SPECS.get(key, {})

            display_name = (
                spec.get("display_name", key) if self.use_friendly_headers else key
            )
            formatter = self.custom_formatters.get(
                key, spec.get("formatter", lambda v: str(v) if v is not None else "")
            )
            compute_fn = spec.get("compute")

            resolved.append(
                {
                    "raw_key": key,
                    "display_name": display_name,
                    "formatter": formatter,
                    "compute": compute_fn,
                }
            )
        return resolved

    def get_column_headers(self, player_header: str = "Player") -> List[str]:
        """Return the column header names."""
        headers = [player_header]
        for field in self._resolved_fields:
            headers.append(field["display_name"])
        return headers

    def extract_row(
        self,
        record: PlayerRecord,
        player_header: str = "Player",
        formatted: bool = True,
    ) -> Dict[str, Any]:
        """Extract a single row dictionary from a PlayerRecord according to configuration."""
        row: Dict[str, Any] = {player_header: record.name}
        for field in self._resolved_fields:
            key = field["raw_key"]
            compute_fn = field["compute"]
            if compute_fn:
                val = compute_fn(record)
            else:
                val = record.get_metric(key)

            if formatted and field["formatter"]:
                display_val = field["formatter"](val)
            else:
                display_val = val

            row[field["display_name"]] = display_val

        return row

    def get_sort_key_for_metric(self, record: PlayerRecord, metric_name: str) -> Any:
        """Retrieve raw numeric value for reliable sorting."""
        key = METRIC_ALIASES.get(metric_name.strip().lower(), metric_name.strip())
        spec = METRIC_SPECS.get(key, {})
        compute_fn = spec.get("compute")
        if compute_fn:
            val = compute_fn(record)
        else:
            val = record.get_metric(key)

        if val is None or val == "":
            return float("-inf")
        if isinstance(val, (int, float)):
            return val
        try:
            return float(str(val).replace(",", ""))
        except ValueError:
            return str(val)
