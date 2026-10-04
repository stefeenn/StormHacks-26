"""Interactive console input collection and validation for Statcast pitch queries."""

import logging
from typing import Any, Callable, Dict, Optional, Tuple
from scraper.config import (
    DEFAULT_SEASON,
    MIN_STATCAST_SEASON,
    MAX_STATCAST_SEASON,
    normalize_batter_stance,
    normalize_count,
    normalize_pitcher_hand,
)
from scraper.player_search import PlayerInfo, PlayerSearchService
from scraper.odds_provider import BaseOddsProvider, ManualConsoleOddsProvider

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

    def prompt_search_mode(self) -> str:
        """Prompt user at the top level to choose between Pitcher Search and Batter Search."""
        self.print_fn("Select Search Mode:")
        self.print_fn("  [1] Pitcher Search")
        self.print_fn("  [2] Batter Search")
        while True:
            raw_input = self.input_fn("Enter choice (1 for Pitcher, 2 for Batter): ").strip().lower()
            if raw_input in ["1", "pitcher", "p"]:
                return "pitcher"
            elif raw_input in ["2", "batter", "b"]:
                return "batter"
            else:
                self.print_fn(
                    "❌ Error: Invalid choice. Please enter '1' for Pitcher Search or '2' for Batter Search."
                )

    def prompt_pitcher_name(self, required: bool = True) -> Tuple[Optional[str], Optional[PlayerInfo]]:
        """Prompt for pitcher name. Required for pitcher search, optional for batter search."""
        while True:
            if required:
                raw_input = self.input_fn("Enter Pitcher Name: ").strip()
                if not raw_input:
                    self.print_fn("❌ Error: Pitcher name is required and cannot be empty. Please re-enter.")
                    continue
            else:
                raw_input = self.input_fn(
                    "Enter Pitcher Name (optional, press Enter to search against all pitchers): "
                ).strip()
                if not raw_input:
                    return None, None

            # Search for pitcher
            player = self.search_service.find_pitcher(raw_input)
            if not player:
                if required:
                    self.print_fn(
                        f"❌ Error: No pitcher found matching '{raw_input}'. "
                        "Please verify the spelling and re-enter."
                    )
                else:
                    self.print_fn(
                        f"❌ Error: No pitcher found matching '{raw_input}'. "
                        "Please re-enter a valid pitcher name (or press Enter to skip)."
                    )
                continue

            self.print_fn(
                f"✅ Selected Pitcher: {player.full_name} "
                f"(ID: {player.player_id}, Pos: {player.primary_position}, "
                f"Throws: {player.pitch_hand or 'N/A'})"
            )
            return raw_input, player

    def prompt_pitcher_hand(self, has_pitcher: bool = True) -> str:
        """Prompt for pitcher throwing hand (L / R / both).
        
        Required if pitcher is specified; defaults to 'both' if searching all pitchers.
        """
        while True:
            if has_pitcher:
                prompt_text = "Enter Pitcher Throwing Hand (L / R / both): "
            else:
                prompt_text = "Enter Pitcher Throwing Hand filter (L / R / both) [default: both]: "

            raw_input = self.input_fn(prompt_text).strip()

            if not raw_input:
                if has_pitcher:
                    self.print_fn(
                        "❌ Error: Pitcher throwing hand is required. "
                        "Must be 'L', 'R', or 'both'. Please re-enter."
                    )
                    continue
                else:
                    return "both"

            normalized = normalize_pitcher_hand(raw_input)
            if not normalized:
                self.print_fn(
                    "❌ Error: Pitcher throwing hand is required. "
                    "Must be 'L', 'R', or 'both'. Please re-enter."
                )
                continue

            return normalized

    def prompt_batter_name(self, required: bool = False) -> Optional[PlayerInfo]:
        """Prompt for batter name. Required for batter search, optional for pitcher search."""
        while True:
            if required:
                raw_input = self.input_fn("Enter Batter Name: ").strip()
                if not raw_input:
                    self.print_fn("❌ Error: Batter name is required and cannot be empty. Please re-enter.")
                    continue
            else:
                raw_input = self.input_fn(
                    "Enter Batter Name (optional, press Enter to search against all batters): "
                ).strip()
                if not raw_input:
                    return None

            player = self.search_service.find_batter(raw_input)
            if not player:
                if required:
                    self.print_fn(
                        f"❌ Error: No batter found matching '{raw_input}'. "
                        "Please verify the spelling and re-enter."
                    )
                else:
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

    def prompt_batter_stance(self, has_batter: bool = True) -> str:
        """Prompt for batter stance.
        
        If a batter name was inputted (or in batter search), stance is 100% REQUIRED.
        If searching against all batters, stance defaults to 'both' if left empty.
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

    def prompt_count(self) -> Optional[str]:
        """Prompt user for ball-strike count filter (e.g. '0-0', '2-1', '3-2').
        
        Optional: user can press Enter to skip and query all counts (overall stats).
        
        Returns:
            Normalized count string ('B-S') or None if skipped/unspecified.
        """
        while True:
            prompt_text = "Enter Count filter (Balls-Strikes, e.g. 0-0, 2-1, 3-2) [default: all counts]: "
            raw_input = self.input_fn(prompt_text).strip()

            if not raw_input:
                self.print_fn("ℹ️ No count specified; using overall stats.")
                return None

            try:
                norm = normalize_count(raw_input)
                if not norm:
                    self.print_fn("ℹ️ No count specified; using overall stats.")
                    return None
                balls, strikes = norm.split("-")
                self.print_fn(f"✅ Selected Count: {norm} ({balls} Balls, {strikes} Strikes)")
                return norm
            except ValueError as e:
                self.print_fn(
                    f"❌ Error: {e} Please enter a valid count like '2-1' or press Enter to skip."
                )

    def prompt_season(self, default: Optional[int] = DEFAULT_SEASON) -> int:
        """Prompt user for MLB season / year with range and format validation.
        
        Args:
            default: Default year if user inputs empty string (defaults to DEFAULT_SEASON).
            
        Returns:
            Validated integer season year.
        """
        while True:
            if default is not None:
                prompt_text = f"Enter Season Year (e.g. 2024) [default: {default}]: "
            else:
                prompt_text = "Enter Season Year (e.g. 2024): "

            raw_input = self.input_fn(prompt_text).strip()

            if not raw_input:
                if default is not None:
                    self.print_fn(f"✅ Selected Season: {default}")
                    return default
                else:
                    self.print_fn("❌ Error: Season year is required. Please enter a valid 4-digit year.")
                    continue

            try:
                year = int(raw_input)
            except ValueError:
                self.print_fn(
                    f"❌ Error: Invalid year '{raw_input}'. Please enter a valid 4-digit numeric year "
                    f"(e.g., {MIN_STATCAST_SEASON}-{MAX_STATCAST_SEASON})."
                )
                continue

            if year < MIN_STATCAST_SEASON or year > MAX_STATCAST_SEASON:
                self.print_fn(
                    f"❌ Error: Invalid season {year}. Statcast data is available from "
                    f"{MIN_STATCAST_SEASON} to {MAX_STATCAST_SEASON}. Please re-enter."
                )
                continue

            self.print_fn(f"✅ Selected Season: {year}")
            return year

    # Alias prompt_year to prompt_season
    prompt_year = prompt_season

    def collect_pitcher_search_inputs(self) -> Dict[str, Any]:
        """Collect and validate inputs for Pitcher Search mode."""
        self.print_fn("\n" + "=" * 60)
        self.print_fn("⚾ Statcast Pitcher Search - Console Input")
        self.print_fn("=" * 60)

        # 1. Pitcher Name (Required 100%)
        raw_p_name, pitcher_info = self.prompt_pitcher_name(required=True)

        # 2. Pitcher Throwing Hand (Required 100%)
        pitcher_hand = self.prompt_pitcher_hand(has_pitcher=True)

        # 3. Batter Name (Optional)
        batter_info = self.prompt_batter_name(required=False)

        # 4. Batter Stance (Required if batter name provided, else defaults to both)
        has_batter = batter_info is not None
        batter_stance = self.prompt_batter_stance(has_batter=has_batter)

        # 5. Count Filter (Optional, before Season Year)
        count = self.prompt_count()

        # 6. Season Year (Last option, after count and rest of selections)
        season = self.prompt_season(default=DEFAULT_SEASON)

        self.print_fn("-" * 60)
        self.print_fn("📋 Pitcher Query Summary:")
        self.print_fn(f"  • Pitcher: {pitcher_info.full_name} (Throws: {pitcher_hand})")
        if batter_info:
            self.print_fn(f"  • Batter:  {batter_info.full_name} (Stance: {batter_stance})")
        else:
            self.print_fn(f"  • Batter:  All batters (Stance: {batter_stance})")
        self.print_fn(f"  • Count:   {count if count else 'All counts (Overall)'}")
        self.print_fn(f"  • Season:  {season}")
        self.print_fn("=" * 60 + "\n")

        return {
            "search_mode": "pitcher",
            "pitcher_name": pitcher_info.full_name,
            "pitcher_id": pitcher_info.player_id,
            "pitcher_info": pitcher_info,
            "pitcher_hand": pitcher_hand,
            "batter_name": batter_info.full_name if batter_info else None,
            "batter_id": batter_info.player_id if batter_info else None,
            "batter_info": batter_info,
            "batter_stance": batter_stance,
            "count": count,
            "season": season,
        }

    def collect_batter_search_inputs(self) -> Dict[str, Any]:
        """Collect and validate inputs for Batter Search mode."""
        self.print_fn("\n" + "=" * 60)
        self.print_fn("⚾ Statcast Batter Search - Console Input")
        self.print_fn("=" * 60)

        # 1. Batter Name (Required 100%)
        batter_info = self.prompt_batter_name(required=True)

        # 2. Batter Stance (Required 100%)
        batter_stance = self.prompt_batter_stance(has_batter=True)

        # 3. Pitcher Name (Optional)
        raw_p_name, pitcher_info = self.prompt_pitcher_name(required=False)

        # 4. Pitcher Throwing Hand (Required if pitcher provided, else defaults to both)
        has_pitcher = pitcher_info is not None
        pitcher_hand = self.prompt_pitcher_hand(has_pitcher=has_pitcher)

        # 5. Count Filter (Optional, before Season Year)
        count = self.prompt_count()

        # 6. Season Year (Last option, after count and rest of selections)
        season = self.prompt_season(default=DEFAULT_SEASON)

        self.print_fn("-" * 60)
        self.print_fn("📋 Batter Query Summary:")
        self.print_fn(f"  • Batter:  {batter_info.full_name} (Stance: {batter_stance})")
        if pitcher_info:
            self.print_fn(f"  • Pitcher: {pitcher_info.full_name} (Throws: {pitcher_hand})")
        else:
            self.print_fn(f"  • Pitcher: All pitchers (Throws: {pitcher_hand})")
        self.print_fn(f"  • Count:   {count if count else 'All counts (Overall)'}")
        self.print_fn(f"  • Season:  {season}")
        self.print_fn("=" * 60 + "\n")

        return {
            "search_mode": "batter",
            "batter_name": batter_info.full_name,
            "batter_id": batter_info.player_id,
            "batter_info": batter_info,
            "batter_stance": batter_stance,
            "pitcher_name": pitcher_info.full_name if pitcher_info else None,
            "pitcher_id": pitcher_info.player_id if pitcher_info else None,
            "pitcher_info": pitcher_info,
            "pitcher_hand": pitcher_hand,
            "count": count,
            "season": season,
        }

    def collect_all_inputs(self, search_mode: Optional[str] = None) -> Dict[str, Any]:
        """Run top-level search mode selection and route to pitcher or batter collection."""
        if search_mode is None:
            self.print_fn("\n" + "=" * 60)
            self.print_fn("⚾ Baseball Savant Statcast Search")
            self.print_fn("=" * 60)
            search_mode = self.prompt_search_mode()

        if search_mode == "batter":
            return self.collect_batter_search_inputs()
        else:
            return self.collect_pitcher_search_inputs()

    def prompt_confirm_sample_bet(self) -> bool:
        """Prompt user whether they want to run the Three-Source Model / sample a bet."""
        self.print_fn("\n" + "=" * 60)
        self.print_fn("🎯 Three-Source Velocity Model (Bet Evaluator)")
        self.print_fn("=" * 60)
        while True:
            raw = self.input_fn(
                "Would you like to sample a bet and run the Three-Source Model? (y/n) [default: y]: "
            ).strip().lower()
            if not raw or raw in ["y", "yes"]:
                return True
            elif raw in ["n", "no"]:
                return False
            else:
                self.print_fn("❌ Please enter 'y' to run the model or 'n' to exit.")

    def prompt_betting_velocity(self, default: float = 95.5) -> float:
        """Prompt user for betting velocity line in mph."""
        while True:
            raw = self.input_fn(
                f"Enter betting velocity line in mph (e.g. 95.5) [default: {default}]: "
            ).strip()
            if not raw:
                return float(default)
            try:
                val = float(raw)
                if val <= 0 or val > 125:
                    self.print_fn(
                        "❌ Error: Betting velocity must be a positive number (typically between 50 and 110 mph)."
                    )
                    continue
                return val
            except ValueError:
                self.print_fn("❌ Error: Please enter a valid numerical velocity (e.g. 95.5).")

    def collect_betting_inputs(
        self,
        pitcher_name: str,
        batter_name: str,
        odds_provider: Optional[BaseOddsProvider] = None,
        default_velocity: float = 95.5,
    ) -> Optional[Dict[str, Any]]:
        """Coordinate prompting for bet evaluation confirmation, velocity line, and odds.

        Args:
            pitcher_name: Name of the pitcher.
            batter_name: Name of the batter.
            odds_provider: Optional odds provider instance. Defaults to ManualConsoleOddsProvider.
            default_velocity: Default betting velocity threshold.

        Returns:
            Dictionary with bet_line, under_odds, over_odds, or None if user declined to run.
        """
        if not self.prompt_confirm_sample_bet():
            return None

        provider = odds_provider or ManualConsoleOddsProvider(
            input_fn=self.input_fn,
            print_fn=self.print_fn,
        )

        bet_line = self.prompt_betting_velocity(default=default_velocity)
        under_odds, over_odds = provider.get_odds(
            pitcher_name=pitcher_name,
            batter_name=batter_name,
            bet_line=bet_line,
        )

        return {
            "bet_line": bet_line,
            "under_odds": under_odds,
            "over_odds": over_odds,
        }
