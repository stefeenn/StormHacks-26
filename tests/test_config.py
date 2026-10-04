"""Unit tests for scraper configuration and team mapping."""

import pytest
from scraper.config import resolve_team_id, MLB_TEAM_IDS


def test_resolve_team_id_abbreviations():
    assert resolve_team_id("LAD") == 119
    assert resolve_team_id("lad") == 119
    assert resolve_team_id("NYY") == 147
    assert resolve_team_id("BOS") == 111


def test_resolve_team_id_names():
    assert resolve_team_id("Dodgers") == 119
    assert resolve_team_id("Los Angeles Dodgers") == 119
    assert resolve_team_id("Yankees") == 147


def test_resolve_team_id_integers_and_numeric_strings():
    assert resolve_team_id(119) == 119
    assert resolve_team_id("119") == 119


def test_resolve_team_id_invalid():
    with pytest.raises(ValueError, match="Unknown team identifier"):
        resolve_team_id("NONEXISTENT_TEAM")


def test_normalize_count_valid():
    from scraper.config import normalize_count
    assert normalize_count("0-0") == "0-0"
    assert normalize_count("2-1") == "2-1"
    assert normalize_count("3-2") == "3-2"
    assert normalize_count("2 1") == "2-1"
    assert normalize_count("21") == "2-1"
    assert normalize_count("full") == "3-2"
    assert normalize_count("full count") == "3-2"


def test_normalize_count_none_and_empty():
    from scraper.config import normalize_count
    assert normalize_count(None) is None
    assert normalize_count("") is None
    assert normalize_count("   ") is None
    assert normalize_count("all") is None
    assert normalize_count("any") is None


def test_normalize_count_invalid():
    from scraper.config import normalize_count
    with pytest.raises(ValueError, match="balls must be 0-3"):
        normalize_count("4-1")
    with pytest.raises(ValueError, match="strikes must be 0-2"):
        normalize_count("2-3")
    with pytest.raises(ValueError, match="Invalid count format"):
        normalize_count("abc")


def test_count_to_hfc():
    from scraper.config import count_to_hfc
    assert count_to_hfc("0-0") == "00|"
    assert count_to_hfc("2-1") == "21|"
    assert count_to_hfc("3-2") == "32|"
    assert count_to_hfc("full count") == "32|"
    assert count_to_hfc(None) is None
    assert count_to_hfc("") is None
    assert count_to_hfc("all") is None
