"""Unit tests for HTML parsers."""

import pytest
from scraper.parsers.team_page import TeamPageParser

SAMPLE_HTML = """
<!DOCTYPE html>
<html>
<body>
<div id="statcastHitting">
    <table>
        <thead>
            <tr>
                <th colspan="2"></th>
                <th colspan="4">Standard Stats</th>
            </tr>
            <tr class="tr-component-row">
                <th>Player</th>
                <th>Season</th>
                <th>AB</th>
                <th>H</th>
                <th>HR</th>
                <th>BA</th>
            </tr>
        </thead>
        <tbody>
            <tr id="scg_518692">
                <td><span><a href="/savant-player/518692"><b>Freeman, Freddie</b></a></span></td>
                <td>2026</td>
                <td>579</td>
                <td>167</td>
                <td>16</td>
                <td>.288</td>
            </tr>
            <tr id="scg_660271">
                <td><span><a href="/savant-player/660271"><b>Ohtani, Shohei</b></a></span></td>
                <td>2026</td>
                <td>523</td>
                <td>144</td>
                <td>30</td>
                <td>.275</td>
            </tr>
            <tr>
                <td><span><b>Dodgers</b></span></td>
                <td>2026</td>
                <td>5,451</td>
                <td>1,399</td>
                <td>204</td>
                <td>.257</td>
            </tr>
        </tbody>
    </table>
</div>
</body>
</html>
"""


def test_team_page_parser_hitting():
    parser = TeamPageParser()
    dataset = parser.parse(SAMPLE_HTML, category="hitting", team_id=119, season=2026)

    assert dataset.category == "hitting"
    assert dataset.team_id == 119
    assert dataset.season == 2026
    assert "BA" in dataset.headers
    assert len(dataset.records) == 3

    roster = dataset.filter_roster_players()
    assert len(roster) == 2

    freeman = roster[0]
    assert freeman.name == "Freddie Freeman"
    assert freeman.player_id == "518692"
    assert freeman.get_metric("BA") == 0.288
    assert freeman.get_metric("HR") == 16
    assert freeman.get_metric("AB") == 579
    assert freeman.is_aggregate is False

    ohtani = roster[1]
    assert ohtani.name == "Shohei Ohtani"
    assert ohtani.get_metric("BA") == 0.275
    assert ohtani.get_metric("HR") == 30

    team_row = dataset.records[2]
    assert team_row.is_aggregate is True


def test_team_page_parser_missing_table():
    parser = TeamPageParser()
    with pytest.raises(ValueError, match="Could not find statistical table"):
        parser.parse("<html><body><div>No tables</div></body></html>", category="hitting")
