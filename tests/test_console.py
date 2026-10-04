"""Unit tests for ConsoleInputHandler input validation and re-prompting."""

from unittest.mock import MagicMock
import pytest

from scraper.console import ConsoleInputHandler
from scraper.player_search import PlayerInfo


def test_prompt_search_mode_validation():
    """Verify search mode selection prompts until valid input ('1', '2', 'pitcher', 'batter')."""
    inputs = ["invalid", "3", "1"]
    prints = []

    handler = ConsoleInputHandler(
        input_fn=lambda prompt="": inputs.pop(0),
        print_fn=lambda *args, **kwargs: prints.append(" ".join(str(a) for a in args)),
    )

    mode = handler.prompt_search_mode()
    assert mode == "pitcher"
    assert any("Invalid choice" in p for p in prints)


def test_prompt_search_mode_batter():
    """Verify selecting '2' returns 'batter'."""
    inputs = ["2"]
    handler = ConsoleInputHandler(
        input_fn=lambda prompt="": inputs.pop(0),
        print_fn=lambda *args, **kwargs: None,
    )
    assert handler.prompt_search_mode() == "batter"


def test_prompt_pitcher_name_reprompts_until_valid():
    """Verify pitcher name prompt fails on empty and not found, re-requesting until valid."""
    mock_search = MagicMock()
    mock_player = PlayerInfo(
        player_id=669373,
        full_name="Tarik Skubal",
        primary_position="P",
        is_pitcher=True,
        pitch_hand="L",
        bat_side="R",
        active=True,
    )
    mock_search.find_pitcher.side_effect = [None, mock_player]

    inputs = ["", "Unknown Pitcher", "Tarik Skubal"]
    prints = []

    def mock_input(prompt=""):
        return inputs.pop(0)

    def mock_print(*args, **kwargs):
        prints.append(" ".join(str(a) for a in args))

    handler = ConsoleInputHandler(
        search_service=mock_search,
        input_fn=mock_input,
        print_fn=mock_print,
    )

    name_str, player = handler.prompt_pitcher_name(required=True)
    assert name_str == "Tarik Skubal"
    assert player.player_id == 669373
    assert any("Pitcher name is required" in p for p in prints)
    assert any("No pitcher found matching" in p for p in prints)
    assert any("Selected Pitcher: Tarik Skubal" in p for p in prints)


def test_prompt_pitcher_name_optional_for_batter():
    """Verify pitcher name prompt can be skipped with enter in batter flow."""
    inputs = [""]
    handler = ConsoleInputHandler(
        input_fn=lambda prompt="": inputs.pop(0),
        print_fn=lambda *args, **kwargs: None,
    )
    name, player = handler.prompt_pitcher_name(required=False)
    assert name is None
    assert player is None


def test_prompt_pitcher_hand_reprompts_until_valid():
    """Verify pitcher throwing hand prompt rejects invalid input and accepts L/R/both."""
    inputs = ["", "XYZ", "left"]
    prints = []

    def mock_input(prompt=""):
        return inputs.pop(0)

    def mock_print(*args, **kwargs):
        prints.append(" ".join(str(a) for a in args))

    handler = ConsoleInputHandler(
        input_fn=mock_input,
        print_fn=mock_print,
    )

    hand = handler.prompt_pitcher_hand(has_pitcher=True)
    assert hand == "L"
    assert any("Must be 'L', 'R', or 'both'" in p for p in prints)


def test_prompt_pitcher_hand_defaults_to_both_when_no_pitcher():
    """Verify pitcher hand defaults to 'both' when no pitcher is specified."""
    inputs = [""]
    handler = ConsoleInputHandler(
        input_fn=lambda prompt="": inputs.pop(0),
        print_fn=lambda *args, **kwargs: None,
    )
    hand = handler.prompt_pitcher_hand(has_pitcher=False)
    assert hand == "both"


def test_prompt_batter_name_required_reprompts_until_valid():
    """Verify batter name is required in batter flow."""
    mock_search = MagicMock()
    b_player = PlayerInfo(621566, "Matt Olson", "1B", False, "R", "L", True)
    mock_search.find_batter.side_effect = [None, b_player]

    inputs = ["", "Unknown Batter", "Matt Olson"]
    prints = []

    handler = ConsoleInputHandler(
        search_service=mock_search,
        input_fn=lambda prompt="": inputs.pop(0),
        print_fn=lambda *args, **kwargs: prints.append(" ".join(str(a) for a in args)),
    )

    player = handler.prompt_batter_name(required=True)
    assert player.full_name == "Matt Olson"
    assert any("Batter name is required" in p for p in prints)
    assert any("No batter found matching" in p for p in prints)


def test_prompt_batter_stance_mandatory_when_batter_provided():
    """Verify batter stance is mandatory if batter name was provided."""
    inputs = ["", "invalid", "right"]
    prints = []

    def mock_input(prompt=""):
        return inputs.pop(0)

    def mock_print(*args, **kwargs):
        prints.append(" ".join(str(a) for a in args))

    handler = ConsoleInputHandler(
        input_fn=mock_input,
        print_fn=mock_print,
    )

    stance = handler.prompt_batter_stance(has_batter=True)
    assert stance == "right"
    assert any("Batter stance is required when a batter name is specified" in p for p in prints)


def test_prompt_batter_stance_defaults_to_both_when_no_batter():
    """Verify batter stance defaults to 'both' when no batter name was provided and user enters blank."""
    inputs = [""]
    prints = []

    def mock_input(prompt=""):
        return inputs.pop(0)

    def mock_print(*args, **kwargs):
        prints.append(" ".join(str(a) for a in args))

    handler = ConsoleInputHandler(
        input_fn=mock_input,
        print_fn=mock_print,
    )

    stance = handler.prompt_batter_stance(has_batter=False)
    assert stance == "both"


def test_collect_all_inputs_pitcher_flow():
    """Simulate complete interactive flow selecting Pitcher Search."""
    mock_search = MagicMock()
    p_player = PlayerInfo(669373, "Tarik Skubal", "P", True, "L", "R", True)
    b_player = PlayerInfo(621566, "Matt Olson", "1B", False, "R", "L", True)

    mock_search.find_pitcher.return_value = p_player
    mock_search.find_batter.return_value = b_player

    inputs = [
        "1",             # Search mode: Pitcher Search
        "Tarik Skubal",  # Pitcher name
        "L",             # Pitcher hand
        "Matt Olson",    # Batter name
        "left",          # Batter stance
    ]

    handler = ConsoleInputHandler(
        search_service=mock_search,
        input_fn=lambda prompt="": inputs.pop(0),
        print_fn=lambda *args, **kwargs: None,
    )

    result = handler.collect_all_inputs()
    assert result["search_mode"] == "pitcher"
    assert result["pitcher_name"] == "Tarik Skubal"
    assert result["pitcher_id"] == 669373
    assert result["pitcher_hand"] == "L"
    assert result["batter_name"] == "Matt Olson"
    assert result["batter_id"] == 621566
    assert result["batter_stance"] == "left"
    assert result["season"] == 2026


def test_collect_all_inputs_batter_flow():
    """Simulate complete interactive flow selecting Batter Search."""
    mock_search = MagicMock()
    p_player = PlayerInfo(669373, "Tarik Skubal", "P", True, "L", "R", True)
    b_player = PlayerInfo(621566, "Matt Olson", "1B", False, "R", "L", True)

    mock_search.find_batter.return_value = b_player
    mock_search.find_pitcher.return_value = p_player

    inputs = [
        "2",             # Search mode: Batter Search
        "Matt Olson",    # Batter name
        "left",          # Batter stance
        "Tarik Skubal",  # Pitcher name
        "L",             # Pitcher hand
    ]

    handler = ConsoleInputHandler(
        search_service=mock_search,
        input_fn=lambda prompt="": inputs.pop(0),
        print_fn=lambda *args, **kwargs: None,
    )

    result = handler.collect_all_inputs()
    assert result["search_mode"] == "batter"
    assert result["batter_name"] == "Matt Olson"
    assert result["batter_id"] == 621566
    assert result["batter_stance"] == "left"
    assert result["pitcher_name"] == "Tarik Skubal"
    assert result["pitcher_id"] == 669373
    assert result["pitcher_hand"] == "L"
    assert result["season"] == 2026
