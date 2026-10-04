"""Parser for Baseball Savant team pages."""

import logging
import re
from typing import Any, Dict, List, Optional
from bs4 import BeautifulSoup

from scraper.models import PlayerRecord, ScrapedDataset
from scraper.parsers.base import BaseParser

logger = logging.getLogger(__name__)


class TeamPageParser(BaseParser):
    """Parses Baseball Savant team pages (e.g. /team/119) for hitting and pitching stats."""

    KNOWN_CATEGORIES = {
        "hitting": "statcastHitting",
        "pitching": "statcastPitching",
    }

    def __init__(self, default_category: str = "hitting"):
        self.default_category = default_category.lower()

    def parse(
        self,
        content: str,
        category: Optional[str] = None,
        team_id: int = 119,
        season: int = 2026,
        **kwargs: Any,
    ) -> ScrapedDataset:
        """Parse team page HTML and return a ScrapedDataset.
        
        Args:
            content: Raw HTML text of the team page.
            category: 'hitting' or 'pitching' (defaults to self.default_category).
            team_id: MLB team ID.
            season: Season year.
            
        Returns:
            ScrapedDataset containing parsed player records.
        """
        cat = (category or self.default_category).lower()
        soup = BeautifulSoup(content, "html.parser")

        table = self._find_stat_table(soup, cat)
        if not table:
            raise ValueError(f"Could not find statistical table for category '{cat}' on team page.")

        headers = self._extract_headers(table)
        logger.debug(f"Extracted headers for {cat}: {headers}")

        records = self._extract_rows(table, headers, team_id, season)

        return ScrapedDataset(
            category=cat,
            team_id=team_id,
            season=season,
            headers=headers,
            records=records,
            metadata={"source": "baseballsavant.mlb.com/team"},
        )

    def _find_stat_table(self, soup: BeautifulSoup, category: str):
        """Locate the table element for the requested category."""
        container_id = self.KNOWN_CATEGORIES.get(category)
        if container_id:
            container = soup.find("div", id=container_id)
            if container:
                table = container.find("table")
                if table:
                    return table

        # Fallback heuristic: find tables and check header content
        tables = soup.find_all("table")
        for tbl in tables:
            th_texts = [th.get_text(strip=True).upper() for th in tbl.find_all("th")]
            if category == "hitting" and "BA" in th_texts and "HR" in th_texts:
                return tbl
            elif category == "pitching" and ("ERA" in th_texts or "PITCHES" in th_texts):
                return tbl

        # If only one table or first table
        return tables[0] if tables else None

    def _extract_headers(self, table) -> List[str]:
        """Extract column headers from the table thead."""
        thead = table.find("thead")
        if not thead:
            return []

        rows = thead.find_all("tr")
        if not rows:
            return []

        # Typically the last <tr> in <thead> contains the individual column headers
        header_tr = rows[-1]
        headers = []
        for th in header_tr.find_all("th"):
            text = th.get_text(separator=" ", strip=True)
            # Remove line breaks or extra spaces in header text (e.g. 'Launch \n Angle' -> 'Launch Angle')
            clean_text = re.sub(r"\s+", " ", text).strip()
            headers.append(clean_text)

        return headers

    def _extract_rows(
        self, table, headers: List[str], team_id: int, season: int
    ) -> List[PlayerRecord]:
        """Extract player rows from table tbody."""
        tbody = table.find("tbody")
        if not tbody:
            return []

        records: List[PlayerRecord] = []
        rows = tbody.find_all("tr")

        for tr in rows:
            tds = tr.find_all("td")
            if not tds:
                continue

            # First cell has player info
            player_td = tds[0]
            link = player_td.find("a")
            player_id = None
            if link and link.get("href"):
                href = link.get("href")
                match = re.search(r"(\d+)", href)
                if match:
                    player_id = match.group(1)
            elif tr.get("id"):
                match = re.search(r"(\d+)", tr.get("id"))
                if match:
                    player_id = match.group(1)

            # Extract player name text
            bold = player_td.find("b")
            if bold:
                raw_name = bold.get_text(strip=True)
            elif link:
                raw_name = link.get_text(strip=True)
            else:
                raw_name = player_td.get_text(strip=True)

            cleaned_name = PlayerRecord.clean_player_name(raw_name)

            # Check if this row is an aggregate (e.g. 'Dodgers', 'MLB', 'Totals')
            is_aggregate = (
                player_id is None
                or raw_name.lower() in ["dodgers", "mlb", "totals", "team total", "league total"]
                or "team" in raw_name.lower()
            )

            # Map metrics to columns
            metrics: Dict[str, Any] = {}
            for i, td in enumerate(tds):
                col_name = headers[i] if i < len(headers) else f"Col_{i}"
                if col_name in ["Player"]:
                    continue

                val_text = td.get_text(strip=True)
                metrics[col_name] = self._normalize_value(val_text)

            rec = PlayerRecord(
                player_id=player_id,
                raw_name=raw_name,
                name=cleaned_name,
                season=season,
                team_id=team_id,
                metrics=metrics,
                is_aggregate=is_aggregate,
            )
            records.append(rec)

        return records

    @staticmethod
    def _normalize_value(val_str: str) -> Any:
        """Convert string values to numeric types (float or int) when possible."""
        if not val_str or val_str in ["-", "--", "N/A", "null"]:
            return None

        clean_str = val_str.replace(",", "").strip()

        # Handle batting average and percentages like '.288' or '-.123'
        if re.match(r"^-?\.\d+$", clean_str):
            try:
                return float(clean_str)
            except ValueError:
                return clean_str

        # Handle regular floats e.g. '89.5'
        if re.match(r"^-?\d+\.\d+$", clean_str):
            try:
                return float(clean_str)
            except ValueError:
                return clean_str

        # Handle integers e.g. '579'
        if re.match(r"^-?\d+$", clean_str):
            try:
                return int(clean_str)
            except ValueError:
                return clean_str

        return clean_str

