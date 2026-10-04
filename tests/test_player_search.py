"""Unit tests for PlayerSearchService."""

from unittest.mock import MagicMock
import pytest

from scraper.player_search import PlayerInfo, PlayerSearchService


def test_search_player_with_numeric_id():
    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "people": [
            {
                "id": 669373,
                "fullName": "Tarik Skubal",
                "primaryPosition": {"code": "1", "abbreviation": "P"},
                "pitchHand": {"code": "L"},
                "batSide": {"code": "R"},
                "active": True,
            }
        ]
    }
    mock_session.get.return_value = mock_resp

    service = PlayerSearchService(session=mock_session)
    results = service.search_player("669373")
    assert len(results) == 1
    assert results[0].player_id == 669373
    assert results[0].full_name == "Tarik Skubal"
    assert results[0].is_pitcher is True


def test_search_player_name_and_reorder():
    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "people": [
            {
                "id": 1,
                "fullName": "Will Smith (Catcher)",
                "primaryPosition": {"code": "2", "abbreviation": "C"},
                "pitchHand": {"code": "R"},
                "batSide": {"code": "R"},
                "active": True,
            },
            {
                "id": 2,
                "fullName": "Will Smith (Pitcher)",
                "primaryPosition": {"code": "1", "abbreviation": "P"},
                "pitchHand": {"code": "L"},
                "batSide": {"code": "R"},
                "active": True,
            },
        ]
    }
    mock_session.get.return_value = mock_resp

    service = PlayerSearchService(session=mock_session)
    pitchers = service.search_player("Will Smith", player_type="pitcher")
    assert pitchers[0].id == 2 if hasattr(pitchers[0], "id") else pitchers[0].player_id == 2
    assert pitchers[0].is_pitcher is True


def test_search_empty_query():
    service = PlayerSearchService()
    assert service.search_player("") == []
    assert service.search_player("   ") == []


def test_player_info_headshot_url():
    player = PlayerInfo(
        player_id=669373,
        full_name="Tarik Skubal",
        primary_position="P",
        is_pitcher=True,
        pitch_hand="L",
        bat_side="R",
        active=True,
    )
    assert player.headshot_url == "https://content.mlb.com/images/headshots/current/60x60/669373@3x.png"
    d = player.to_dict()
    assert d["headshot_url"] == "https://content.mlb.com/images/headshots/current/60x60/669373@3x.png"
    assert d["id"] == 669373

