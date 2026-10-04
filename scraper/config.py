"""Configuration settings and team mappings for Baseball Savant scraper."""

from typing import Dict, Optional, Union

BASE_URL = "https://baseballsavant.mlb.com"

# Standard MLB team mappings (Abbreviation / Common Name -> MLB Team ID)
MLB_TEAM_IDS: Dict[str, int] = {
    "LAD": 119,
    "DODGERS": 119,
    "LOS ANGELES DODGERS": 119,
    "NYY": 147,
    "YANKEES": 147,
    "NEW YORK YANKEES": 147,
    "BOS": 111,
    "RED SOX": 111,
    "BOSTON RED SOX": 111,
    "HOU": 117,
    "ASTROS": 117,
    "HOUSTON ASTROS": 117,
    "ATL": 144,
    "BRAVES": 144,
    "ATLANTA BRAVES": 144,
    "SF": 137,
    "GIANTS": 137,
    "SAN FRANCISCO GIANTS": 137,
    "CHC": 112,
    "CUBS": 112,
    "CHICAGO CUBS": 112,
    "NYM": 121,
    "METS": 121,
    "NEW YORK METS": 121,
    "PHI": 143,
    "PHILLIES": 143,
    "PHILADELPHIA PHILLIES": 143,
    "SD": 135,
    "PADRES": 135,
    "SAN DIEGO PADRES": 135,
    "BAL": 110,
    "ORIOLES": 110,
    "BALTIMORE ORIOLES": 110,
    "TOR": 141,
    "BLUE JAYS": 141,
    "TORONTO BLUE JAYS": 141,
    "TB": 139,
    "RAYS": 139,
    "TAMPA BAY RAYS": 139,
    "TEX": 140,
    "RANGERS": 140,
    "TEXAS RANGERS": 140,
    "SEA": 136,
    "MARINERS": 136,
    "SEATTLE MARINERS": 136,
    "LAA": 108,
    "ANGELS": 108,
    "LOS ANGELES ANGELS": 108,
    "OAK": 133,
    "ATHLETICS": 133,
    "OAKLAND ATHLETICS": 133,
    "MIN": 142,
    "TWINS": 142,
    "MINNESOTA TWINS": 142,
    "CLE": 114,
    "GUARDIANS": 114,
    "CLEVELAND GUARDIANS": 114,
    "DET": 116,
    "TIGERS": 116,
    "DETROIT TIGERS": 116,
    "CWS": 145,
    "WHITE SOX": 145,
    "CHICAGO WHITE SOX": 145,
    "KC": 118,
    "ROYALS": 118,
    "KANSAS CITY ROYALS": 118,
    "MIL": 158,
    "BREWERS": 158,
    "MILWAUKEE BREWERS": 158,
    "STL": 138,
    "CARDINALS": 138,
    "ST. LOUIS CARDINALS": 138,
    "CIN": 113,
    "REDS": 113,
    "CINCINNATI REDS": 113,
    "PIT": 134,
    "PIRATES": 134,
    "PITTSBURGH PIRATES": 134,
    "AZ": 109,
    "DIAMONDBACKS": 109,
    "ARIZONA DIAMONDBACKS": 109,
    "COL": 115,
    "ROCKIES": 115,
    "COLORADO ROCKIES": 115,
    "MIA": 146,
    "MARLINS": 146,
    "MIAMI MARLINS": 146,
    "WSH": 120,
    "NATIONALS": 120,
    "WASHINGTON NATIONALS": 120,
}

# Default HTTP headers
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X-UA-Compatible; Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://baseballsavant.mlb.com/",
}

# Request configuration
DEFAULT_TIMEOUT = 20
DEFAULT_MAX_RETRIES = 3
DEFAULT_SEASON = 2026

# Common metric aliases mapping to table header labels
METRIC_ALIASES: Dict[str, str] = {
    "batting_average": "BA",
    "batting_avg": "BA",
    "ba": "BA",
    "avg": "BA",
    "on_base_percentage": "OBP",
    "obp": "OBP",
    "slugging": "SLG",
    "slugging_percentage": "SLG",
    "slg": "SLG",
    "home_runs": "HR",
    "hr": "HR",
    "hits": "H",
    "h": "H",
    "at_bats": "AB",
    "ab": "AB",
    "plate_appearances": "PA",
    "pa": "PA",
    "strikeouts": "SO",
    "so": "SO",
    "walks": "BB",
    "bb": "BB",
    "doubles": "2B",
    "2b": "2B",
    "triples": "3B",
    "3b": "3B",
    "woba": "wOBA",
    "wobacon": "wOBAcon",
    "pitches": "Pitches",
    "batted_balls": "BattedBalls",
    "barrels": "Barrels",
    "barrel_pct": "Barrel %",
    "barrel_percentage": "Barrel %",
    "hard_hit_pct": "Hard Hit %",
    "hard_hit_percentage": "Hard Hit %",
    "exit_velocity": "ExitVelocity",
    "launch_angle": "LaunchAngle",
    "expected_ba": "xBA",
    "xba": "xBA",
    "expected_slg": "xSLG",
    "xslg": "xSLG",
    "expected_woba": "xwOBA",
    "xwoba": "xwOBA",
}


def resolve_team_id(team_identifier: Union[str, int]) -> int:
    """Resolve a team abbreviation, name, or integer ID to an MLB team ID.
    
    Args:
        team_identifier: Team code (e.g. 'LAD'), name (e.g. 'Dodgers'), or ID (e.g. 119).
        
    Returns:
        The integer MLB team ID.
        
    Raises:
        ValueError: If team identifier cannot be recognized.
    """
    if isinstance(team_identifier, int):
        return team_identifier

    normalized = str(team_identifier).strip().upper()
    if normalized.isdigit():
        return int(normalized)

    if normalized in MLB_TEAM_IDS:
        return MLB_TEAM_IDS[normalized]

    raise ValueError(
        f"Unknown team identifier '{team_identifier}'. "
        f"Available teams: {', '.join(sorted(set(k for k in MLB_TEAM_IDS if len(k) <= 3)))}"
    )
