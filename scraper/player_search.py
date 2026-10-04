"""Player lookup and search service using MLB Stats API and Baseball Savant."""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union
import requests

from scraper.config import DEFAULT_HEADERS, DEFAULT_TIMEOUT

logger = logging.getLogger(__name__)


@dataclass
class PlayerInfo:
    """Structured information about an MLB player."""
    player_id: int
    full_name: str
    primary_position: str
    is_pitcher: bool
    pitch_hand: str
    bat_side: str
    active: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.player_id,
            "full_name": self.full_name,
            "primary_position": self.primary_position,
            "is_pitcher": self.is_pitcher,
            "pitch_hand": self.pitch_hand,
            "bat_side": self.bat_side,
            "active": self.active,
        }


class PlayerSearchService:
    """Service for searching players across MLB Stats API."""

    def __init__(self, session: Optional[requests.Session] = None, timeout: int = DEFAULT_TIMEOUT):
        self.session = session or requests.Session()
        self.timeout = timeout
        if not session:
            self.session.headers.update(DEFAULT_HEADERS)

    def search_player(
        self,
        query: Union[str, int],
        player_type: Optional[str] = None,
    ) -> List[PlayerInfo]:
        """Search for a player by name or ID.
        
        Args:
            query: Player full name (e.g. 'Tarik Skubal'), 'Last, First', or MLB ID.
            player_type: Optional filter: 'pitcher' or 'batter'.
            
        Returns:
            List of matching PlayerInfo objects ordered by relevance.
        """
        clean_query = str(query).strip()
        if not clean_query:
            return []

        # If numeric ID
        if clean_query.isdigit():
            return self._lookup_by_id(int(clean_query))

        # Normalize "Last, First" into "First Last"
        if "," in clean_query:
            parts = [p.strip() for p in clean_query.split(",", 1)]
            if len(parts) == 2 and parts[1]:
                clean_query = f"{parts[1]} {parts[0]}"

        url = f"https://statsapi.mlb.com/api/v1/people/search?names={requests.utils.quote(clean_query)}"
        try:
            resp = self.session.get(url, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            raw_people = data.get("people", [])
        except Exception as e:
            logger.error(f"Error querying MLB player search for '{clean_query}': {e}")
            return []

        results: List[PlayerInfo] = []
        for p in raw_people:
            pos = p.get("primaryPosition", {}).get("abbreviation", "")
            pos_code = str(p.get("primaryPosition", {}).get("code", ""))
            is_pitcher = pos == "P" or pos_code == "1"
            p_hand = p.get("pitchHand", {}).get("code", "")
            b_side = p.get("batSide", {}).get("code", "")
            active = bool(p.get("active", False))

            results.append(
                PlayerInfo(
                    player_id=int(p["id"]),
                    full_name=p["fullName"],
                    primary_position=pos,
                    is_pitcher=is_pitcher,
                    pitch_hand=p_hand,
                    bat_side=b_side,
                    active=active,
                )
            )

        # Sort order: active first, then position matching
        p_type = (player_type or "").lower()
        if p_type == "pitcher":
            results.sort(key=lambda x: (x.is_pitcher, x.active), reverse=True)
        elif p_type == "batter":
            results.sort(key=lambda x: (not x.is_pitcher, x.active), reverse=True)
        else:
            results.sort(key=lambda x: x.active, reverse=True)

        return results

    def _lookup_by_id(self, player_id: int) -> List[PlayerInfo]:
        """Look up player directly by MLB ID."""
        url = f"https://statsapi.mlb.com/api/v1/people/{player_id}"
        try:
            resp = self.session.get(url, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            people = data.get("people", [])
            if not people:
                return []
            p = people[0]
            pos = p.get("primaryPosition", {}).get("abbreviation", "")
            pos_code = str(p.get("primaryPosition", {}).get("code", ""))
            return [
                PlayerInfo(
                    player_id=int(p["id"]),
                    full_name=p["fullName"],
                    primary_position=pos,
                    is_pitcher=pos == "P" or pos_code == "1",
                    pitch_hand=p.get("pitchHand", {}).get("code", ""),
                    bat_side=p.get("batSide", {}).get("code", ""),
                    active=bool(p.get("active", False)),
                )
            ]
        except Exception as e:
            logger.error(f"Error querying MLB player ID {player_id}: {e}")
            return []

    def find_pitcher(self, query: Union[str, int]) -> Optional[PlayerInfo]:
        """Find the best matching pitcher for a name or ID."""
        matches = self.search_player(query, player_type="pitcher")
        return matches[0] if matches else None

    def find_batter(self, query: Union[str, int]) -> Optional[PlayerInfo]:
        """Find the best matching batter for a name or ID."""
        matches = self.search_player(query, player_type="batter")
        return matches[0] if matches else None

