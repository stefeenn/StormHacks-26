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
