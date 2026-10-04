"""HTTP client for Baseball Savant with retries, headers, and error handling."""

import logging
from pathlib import Path
from typing import Optional, Union
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from scraper.config import (
    BASE_URL,
    DEFAULT_HEADERS,
    DEFAULT_MAX_RETRIES,
    DEFAULT_SEASON,
    DEFAULT_TIMEOUT,
    resolve_team_id,
)

logger = logging.getLogger(__name__)


class BaseballSavantClient:
    """Handles HTTP communication with Baseball Savant."""

    def __init__(
        self,
        base_url: str = BASE_URL,
        headers: Optional[dict] = None,
        timeout: int = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        cache_dir: Optional[Union[str, Path]] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.cache_dir = Path(cache_dir) if cache_dir else None
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.session = requests.Session()
        req_headers = dict(DEFAULT_HEADERS)
        if headers:
            req_headers.update(headers)
        self.session.headers.update(req_headers)

        # Configure retry strategy
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=1.0,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def fetch_url(self, url: str, params: Optional[dict] = None) -> str:
        """Fetch raw HTML/text from a full URL."""
        logger.debug(f"Fetching URL: {url} with params {params}")
        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            logger.error(f"Failed to fetch {url}: {e}")
            raise RuntimeError(f"Error fetching Baseball Savant page ({url}): {e}") from e

    def fetch_team_page(
        self,
        team_identifier: Optional[Union[str, int]] = None,
        season: int = DEFAULT_SEASON,
        team_id: Optional[Union[str, int]] = None,
    ) -> str:
        """Fetch team page HTML for a given team ID or abbreviation and season.
        
        Args:
            team_identifier: Team code (e.g. 'LAD') or team ID (e.g. 119).
            season: MLB season year (default: 2026).
            team_id: Optional alias for team_identifier.
            
        Returns:
            Raw HTML string.
        """
        target = team_id if team_id is not None else team_identifier
        if target is None:
            raise ValueError("Either team_identifier or team_id must be provided.")
        resolved_id = resolve_team_id(target)
        cache_file = None
        if self.cache_dir:
            cache_file = self.cache_dir / f"team_{resolved_id}_season_{season}.html"
            if cache_file.exists():
                logger.info(f"Loading cached team page: {cache_file}")
                return cache_file.read_text(encoding="utf-8")

        url = f"{self.base_url}/team/{resolved_id}"
        params = {"season": season}
        html = self.fetch_url(url, params=params)

        if cache_file:
            cache_file.write_text(html, encoding="utf-8")

        return html

    def fetch_statcast_pitches(
        self,
        pitcher_id: Optional[Union[int, str]] = None,
        batter_id: Optional[Union[int, str]] = None,
        season: int = DEFAULT_SEASON,
        pitcher_throws: Optional[str] = None,
        stand: Optional[str] = None,
        player_type: str = "pitcher",
    ) -> str:
        """Fetch Statcast pitch-by-pitch CSV data from Baseball Savant.
        
        Args:
            pitcher_id: Optional MLB ID of the pitcher.
            batter_id: Optional MLB ID of the batter.
            season: Season year (defaults to 2026).
            pitcher_throws: Optional pitcher hand ('L' or 'R').
            stand: Optional batter stance ('L' or 'R').
            player_type: Primary subject type ('pitcher' or 'batter').
            
        Returns:
            Raw CSV text response from Statcast search.
        """
        if not pitcher_id and not batter_id:
            raise ValueError("At least one of pitcher_id or batter_id must be provided.")

        cache_file = None
        if self.cache_dir:
            p_str = f"pitcher_{pitcher_id}" if pitcher_id else "all_pitchers"
            b_str = f"batter_{batter_id}" if batter_id else "all_batters"
            p_hand = f"_pthrows_{pitcher_throws}" if pitcher_throws else ""
            b_stand = f"_stand_{stand}" if stand else ""
            cache_file = self.cache_dir / f"statcast_{player_type}_{p_str}_{b_str}_s{season}{p_hand}{b_stand}.csv"
            if cache_file.exists():
                logger.info(f"Loading cached Statcast pitch data: {cache_file}")
                return cache_file.read_text(encoding="utf-8")

        url = f"{self.base_url}/statcast_search/csv"
        params = {
            "all": "true",
            "hfSea": f"{season}|",
            "player_type": player_type,
            "type": "details",
        }
        if pitcher_id is not None:
            params["pitchers_lookup[]"] = str(pitcher_id)
        if batter_id is not None:
            params["batters_lookup[]"] = str(batter_id)
        if pitcher_throws and pitcher_throws.upper() in ["R", "L"]:
            params["pitcher_throws"] = pitcher_throws.upper()
        if stand and stand.upper() in ["R", "L"]:
            params["stand"] = stand.upper()

        logger.info(
            f"Fetching Statcast pitch data (player_type={player_type}) "
            + (f"pitcher {pitcher_id}" if pitcher_id else "all pitchers")
            + (f" vs batter {batter_id}" if batter_id else "")
            + f" (season {season})..."
        )
        csv_text = self.fetch_url(url, params=params)

        if cache_file:
            cache_file.write_text(csv_text, encoding="utf-8")

        return csv_text

