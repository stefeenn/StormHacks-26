"""Unit and integration tests for the chained betting model evaluation flow."""

from unittest.mock import MagicMock, patch
import pytest

from main import handle_post_matchup_betting
from scraper.console import ConsoleInputHandler
from scraper.odds_provider import (
    ManualConsoleOddsProvider,
    normalize_american_odds,
)


def test_normalize_american_odds():
    assert normalize_american_odds("-110") == -110
    assert normalize_american_odds("+105") == 105
    assert normalize_american_odds("120") == 120
    assert normalize_american_odds("", default=-110) == -110
    assert normalize_american_odds("  -125  ") == -125

    with pytest.raises(ValueError, match="cannot be 0"):
        normalize_american_odds("0")

    with pytest.raises(ValueError, match="Invalid American odds"):
        normalize_american_odds("even")


def test_manual_console_odds_provider():
    inputs = ["-115", "+105"]
    provider = ManualConsoleOddsProvider(
        input_fn=lambda prompt: inputs.pop(0),
        print_fn=lambda *args: None,
    )
    under, over = provider.get_odds(
        pitcher_name="Tarik Skubal",
        batter_name="Matt Olson",
        bet_line=95.5,
    )
    assert under == -115
    assert over == 105


def test_manual_console_odds_provider_defaults():
    inputs = ["", ""]  # Press enter for both
    provider = ManualConsoleOddsProvider(
        input_fn=lambda prompt: inputs.pop(0),
        print_fn=lambda *args: None,
        default_under_odds=-110,
        default_over_odds=-110,
    )
    under, over = provider.get_odds(
        pitcher_name="Tarik Skubal",
        batter_name="Matt Olson",
        bet_line=95.5,
    )
    assert under == -110
    assert over == -110


def test_prompt_confirm_sample_bet_yes():
    handler = ConsoleInputHandler(
        input_fn=lambda prompt: "y",
        print_fn=lambda *args: None,
    )
    assert handler.prompt_confirm_sample_bet() is True

    handler_enter = ConsoleInputHandler(
        input_fn=lambda prompt: "",  # default enter
        print_fn=lambda *args: None,
    )
    assert handler_enter.prompt_confirm_sample_bet() is True


def test_prompt_confirm_sample_bet_no():
    handler = ConsoleInputHandler(
        input_fn=lambda prompt: "n",
        print_fn=lambda *args: None,
    )
    assert handler.prompt_confirm_sample_bet() is False


def test_prompt_betting_velocity():
    handler = ConsoleInputHandler(
        input_fn=lambda prompt: "97.5",
        print_fn=lambda *args: None,
    )
    assert handler.prompt_betting_velocity() == 97.5

    handler_default = ConsoleInputHandler(
        input_fn=lambda prompt: "",
        print_fn=lambda *args: None,
    )
    assert handler_default.prompt_betting_velocity(default=95.5) == 95.5


def test_collect_betting_inputs_user_declined():
    handler = ConsoleInputHandler(
        input_fn=lambda prompt: "n",
        print_fn=lambda *args: None,
    )
    result = handler.collect_betting_inputs("Tarik Skubal", "Matt Olson")
    assert result is None


def test_collect_betting_inputs_user_accepted():
    inputs = ["y", "96.0", "-115", "+100"]
    handler = ConsoleInputHandler(
        input_fn=lambda prompt: inputs.pop(0),
        print_fn=lambda *args: None,
    )
    result = handler.collect_betting_inputs("Tarik Skubal", "Matt Olson")
    assert result == {
        "bet_line": 96.0,
        "under_odds": -115,
        "over_odds": 100,
    }


def test_handle_post_matchup_betting_with_cli_args():
    args = MagicMock()
    args.no_model = False
    args.bet_line = 96.5
    args.under_odds = -115
    args.over_odds = 105

    with patch("dataModel.threeSourceModel.evaluate_and_report") as mock_eval:
        handle_post_matchup_betting(
            args=args,
            pitcher="Tarik Skubal",
            batter="Matt Olson",
        )
        mock_eval.assert_called_once_with(
            bet_line=96.5,
            under_odds=-115,
            over_odds=105,
        )


def test_handle_post_matchup_betting_no_model_flag():
    args = MagicMock()
    args.no_model = True
    args.bet_line = 96.5

    with patch("dataModel.threeSourceModel.evaluate_and_report") as mock_eval:
        handle_post_matchup_betting(
            args=args,
            pitcher="Tarik Skubal",
            batter="Matt Olson",
        )
        mock_eval.assert_not_called()


def test_handle_post_matchup_betting_interactive_declined():
    args = MagicMock()
    args.no_model = False
    args.bet_line = None
    args.run_model = True

    mock_handler = MagicMock()
    mock_handler.collect_betting_inputs.return_value = None

    with patch("dataModel.threeSourceModel.evaluate_and_report") as mock_eval:
        handle_post_matchup_betting(
            args=args,
            pitcher="Tarik Skubal",
            batter="Matt Olson",
            is_interactive=True,
            input_handler=mock_handler,
        )
        mock_eval.assert_not_called()


def test_handle_post_matchup_betting_interactive_accepted():
    args = MagicMock()
    args.no_model = False
    args.bet_line = None
    args.run_model = True

    mock_handler = MagicMock()
    mock_handler.collect_betting_inputs.return_value = {
        "bet_line": 95.0,
        "under_odds": -110,
        "over_odds": -110,
    }

    with patch("dataModel.threeSourceModel.evaluate_and_report") as mock_eval:
        handle_post_matchup_betting(
            args=args,
            pitcher="Tarik Skubal",
            batter="Matt Olson",
            is_interactive=True,
            input_handler=mock_handler,
        )
        mock_eval.assert_called_once_with(
            bet_line=95.0,
            under_odds=-110,
            over_odds=-110,
        )
