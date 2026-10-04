"""Modular odds provider interface and implementations for betting model integration."""

from abc import ABC, abstractmethod
from typing import Callable, Optional, Tuple


def normalize_american_odds(raw_val: str, default: int = -110) -> int:
    """Validate and parse American odds string into an integer.

    Examples:
        "-110" -> -110
        "+105" -> 105
        "105"  -> 105
        ""     -> default (when default is provided)
    """
    s = str(raw_val).strip()
    if not s:
        return default
    if s.startswith("+"):
        s = s[1:].strip()
    try:
        val = int(s)
    except ValueError as e:
        raise ValueError(
            f"Invalid American odds '{raw_val}'. Expected format like -110, +105, or -120."
        ) from e
    if val == 0:
        raise ValueError("American odds cannot be 0.")
    if -100 < val < 100:
        raise ValueError(f"American odds must be <= -100 or >= +100 (got {raw_val}).")
    return val


class BaseOddsProvider(ABC):
    """Abstract base class for fetching or collecting betting odds.

    Subclasses can implement manual console prompts, API integrations,
    or sports betting website scrapers.
    """

    @abstractmethod
    def get_odds(
        self,
        pitcher_name: str,
        batter_name: str,
        bet_line: float,
    ) -> Tuple[int, int]:
        """Retrieve under and over odds for a given matchup and bet line.

        Args:
            pitcher_name: Name of the pitcher.
            batter_name: Name of the batter.
            bet_line: Betting velocity line in mph (e.g. 95.5).

        Returns:
            Tuple of (under_odds, over_odds) as American odds integers.
        """
        pass


class ManualConsoleOddsProvider(BaseOddsProvider):
    """Prompts the user via console for sample under and over odds.

    This serves as a placeholder until an external sports betting website scraper is integrated.
    """

    def __init__(
        self,
        input_fn: Callable[[str], str] = input,
        print_fn: Callable[..., None] = print,
        default_under_odds: int = -110,
        default_over_odds: int = -110,
    ):
        self.input_fn = input_fn
        self.print_fn = print_fn
        self.default_under_odds = default_under_odds
        self.default_over_odds = default_over_odds

    def get_odds(
        self,
        pitcher_name: str,
        batter_name: str,
        bet_line: float,
    ) -> Tuple[int, int]:
        """Prompt user for under and over odds via console."""
        # 1. Sample bet odds for UNDER
        while True:
            raw_under = self.input_fn(
                f"Enter sample bet odds for UNDER (e.g. -110, +105) [default: {self.default_under_odds}]: "
            ).strip()
            if not raw_under:
                under_odds = self.default_under_odds
                break
            try:
                under_odds = normalize_american_odds(raw_under)
                break
            except ValueError as e:
                self.print_fn(f"❌ Error: {e}")

        # 2. Sample bet odds for OVER
        while True:
            raw_over = self.input_fn(
                f"Enter sample bet odds for OVER (e.g. -110, +100) [default: {self.default_over_odds}]: "
            ).strip()
            if not raw_over:
                over_odds = self.default_over_odds
                break
            try:
                over_odds = normalize_american_odds(raw_over)
                break
            except ValueError as e:
                self.print_fn(f"❌ Error: {e}")

        return under_odds, over_odds
