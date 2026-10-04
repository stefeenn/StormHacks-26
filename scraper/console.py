"""Interactive console input collection and validation for Statcast pitch queries."""

import logging
from typing import Any, Callable, Dict, Optional, Tuple
from scraper.config import normalize_batter_stance, normalize_pitcher_hand
from scraper.player_search import PlayerInfo, PlayerSearchService

logger = logging.getLogger(__name__)


class ConsoleInputHandler:
    """Manages robust console prompts and validation for pitcher and batter inputs."""

    def __init__(
        self,
        search_service: Optional[PlayerSearchService] = None,
        input_fn: Callable[[str], str] = input,
        print_fn: Callable[..., None] = print,
    ):
        self.search_service = search_service or PlayerSearchService()
        self.input_fn = input_fn
        self.print_fn = print_fn

    def prompt_pitcher_name(self) -> Tuple[str, PlayerInfo]:
        """Prompt for pitcher name 100% required, re-requesting until valid and found."""
        while True:
            raw_input = self.input_fn("Enter Pitcher Name: ").strip()
            if not raw_input:
                self.print_fn("❌ Error: Pitcher name is required and cannot be empty. Please re-enter.")
                continue

            # Search for pitcher
            player = self.search_service.find_pitcher(raw_input)
            if not player:
                self.print_fn(
                    f"❌ Error: No pitcher found matching '{raw_input}'. "
                    "Please verify the spelling and re-enter."
                )
                continue

            self.print_fn(
                f"✅ Selected Pitcher: {player.full_name} "
                f"(ID: {player.player_id}, Pos: {player.primary_position}, "
                f"Throws: {player.pitch_hand or 'N/A'})"
            )
            return raw_input, player

    def prompt_pitcher_hand(self) -> str:
        """Prompt for pitcher throwing hand 100% required (L / R / both), re-requesting until valid."""
        while True:
            raw_input = self.input_fn("Enter Pitcher Throwing Hand (L / R / both): ").strip()
            normalized = normalize_pitcher_hand(raw_input)
            if not normalized:
                self.print_fn(
                    "❌ Error: Pitcher throwing hand is required. "
                    "Must be 'L', 'R', or 'both'. Please re-enter."
                )
                continue

            return normalized

    def prompt_batter_name(self) -> Optional[PlayerInfo]:
        """Prompt for batter name (optional). If provided, validates player existence."""
        while True:
            raw_input = self.input_fn(
                "Enter Batter Name (optional, press Enter to search against all batters): "
            ).strip()
            if not raw_input:
                return None

            player = self.search_service.find_batter(raw_input)
            if not player:
                self.print_fn(
                    f"❌ Error: No batter found matching '{raw_input}'. "
                    "Please re-enter a valid batter name (or press Enter to skip)."
                )
                continue

            self.print_fn(
                f"✅ Selected Batter: {player.full_name} "
                f"(ID: {player.player_id}, Pos: {player.primary_position}, "
                f"Bats: {player.bat_side or 'N/A'})"
            )
            return player

    def prompt_batter_stance(self, has_batter: bool) -> str:
        """Prompt for batter stance.
        
        If a batter name was inputted, stance is 100% REQUIRED.
        If no batter name was inputted, stance defaults to 'both' if left empty.
        """
        while True:
            if has_batter:
                prompt_text = "Enter Batter Stance (left / right / both): "
            else:
                prompt_text = "Enter Batter Stance filter (left / right / both) [default: both]: "

            raw_input = self.input_fn(prompt_text).strip()

            if not raw_input:
                if has_batter:
                    self.print_fn(
                        "❌ Error: Batter stance is required when a batter name is specified. "
                        "Must be 'left', 'right', or 'both'. Please re-enter."
                    )
                    continue
                else:
                    return "both"

            normalized = normalize_batter_stance(raw_input)
            if not normalized:
                self.print_fn(
                    "❌ Error: Invalid batter stance. Must be 'left', 'right', or 'both'. "
                    "Please re-enter."
                )
                continue

            return normalized

    def collect_all_inputs(self) -> Dict[str, Any]:
        """Run the interactive flow collecting and validating all 4 input fields."""
        self.print_fn("\n" + "=" * 60)
        self.print_fn("⚾ Statcast Pitch Search - Console Input")
        self.print_fn("=" * 60)

        # 1. Pitcher Name (Required 100%)
        raw_p_name, pitcher_info = self.prompt_pitcher_name()

        # 2. Pitcher Throwing Hand (Required 100%)
        pitcher_hand = self.prompt_pitcher_hand()

        # 3. Batter Name (Optional)
        batter_info = self.prompt_batter_name()

        # 4. Batter Stance (Required if batter name provided, else defaults to both)
        has_batter = batter_info is not None
        batter_stance = self.prompt_batter_stance(has_batter=has_batter)

        self.print_fn("-" * 60)
        self.print_fn("📋 Query Summary:")
        self.print_fn(f"  • Pitcher: {pitcher_info.full_name} (Throws: {pitcher_hand})")
        if batter_info:
            self.print_fn(f"  • Batter:  {batter_info.full_name} (Stance: {batter_stance})")
        else:
            self.print_fn(f"  • Batter:  All batters (Stance: {batter_stance})")
        self.print_fn(f"  • Season:  2026")
        self.print_fn("=" * 60 + "\n")

        return {
            "pitcher_name": pitcher_info.full_name,
            "pitcher_id": pitcher_info.player_id,
            "pitcher_info": pitcher_info,
            "pitcher_hand": pitcher_hand,
            "batter_name": batter_info.full_name if batter_info else None,
            "batter_id": batter_info.player_id if batter_info else None,
            "batter_info": batter_info,
            "batter_stance": batter_stance,
            "season": 2026,
        }

