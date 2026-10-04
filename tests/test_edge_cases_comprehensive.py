"""Comprehensive test suite covering edge cases, input normalization,
security boundaries, error handling, and end-to-end integration for Pitch Perfect.
"""

from pathlib import Path
import pytest

from web.app import create_app
from scraper.config import (
    normalize_count,
    normalize_batter_stance,
    normalize_pitcher_hand,
)
from dataModel.threeSourceModel import american_to_prob, american_profit
from web.routes.api import recent_searches_session


@pytest.fixture
def test_app(tmp_path: Path):
    """Create Flask test app with isolated output directory."""
    out_dir = tmp_path / "test_output"
    out_dir.mkdir(parents=True, exist_ok=True)
    app = create_app(output_dir=str(out_dir))
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(test_app):
    with test_app.test_client() as c:
        yield c


# ==============================================================================
# 1. WEBSITE TEMPLATE & BRANDING TESTS
# ==============================================================================

def test_website_index_template_elements(client):
    """Verify that Pitch Perfect branding, uppercase defaults, and no replay button exist."""
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)

    # 1. Project Title
    assert "<title>Pitch Perfect</title>" in html
    assert "Pitch Perfect" in html

    # 2. Header logo icon without replay button attributes
    assert 'id="btn-replay-intro"' not in html
    assert 'class="btn-replay-intro"' not in html
    assert 'title="Click to replay pitch intro"' not in html
    assert '<span class="header-logo-icon">⚾</span>' in html

    # 3. Uppercase default filled-in text for stance and hand filters
    assert 'id="input-batter-stance"' in html
    assert 'value="Both"' in html  # Uppercase
    assert 'data-value="Left"' in html
    assert 'data-value="Right"' in html
    assert 'data-value="Both"' in html

    assert 'id="input-batter-stance-bmode"' in html
    assert 'id="input-pitcher-hand"' in html
    assert 'value="Both"' in html

    # 4. Footer branding
    assert "Pitch Perfect • Statcast Pitch Arsenal Explorer • Outputs cleared on closure" in html


# ==============================================================================
# 2. INPUT NORMALIZATION & EDGE CASES
# ==============================================================================

def test_count_normalization_edge_cases():
    """Test full spectrum of valid, aliased, whitespace-padded, and invalid ball-strike counts."""
    # Standard counts
    assert normalize_count("0-0") == "0-0"
    assert normalize_count("3-2") == "3-2"
    assert normalize_count("1-2") == "1-2"

    # Whitespace and alternative separators
    assert normalize_count(" 2 - 1 ") == "2-1"
    assert normalize_count("3/2") == "3-2"
    assert normalize_count("0:0") == "0-0"
    assert normalize_count("1 1") == "1-1"

    # Aliases
    assert normalize_count("full") == "3-2"
    assert normalize_count("FULL COUNT") == "3-2"
    assert normalize_count("fullcount") == "3-2"

    # Empty / overall / wildcard values
    assert normalize_count(None) is None
    assert normalize_count("") is None
    assert normalize_count("   ") is None
    assert normalize_count("all") is None
    assert normalize_count("any") is None
    assert normalize_count("overall") is None

    # Invalid counts (out of baseball bounds) raise ValueError
    with pytest.raises(ValueError, match="balls must be 0-3"):
        normalize_count("4-2")
    with pytest.raises(ValueError, match="strikes must be 0-2"):
        normalize_count("2-3")
    with pytest.raises(ValueError):
        normalize_count("-1-2")
    with pytest.raises(ValueError, match="Invalid count format"):
        normalize_count("abc")
    with pytest.raises(ValueError):
        normalize_count("1-2-3")
    with pytest.raises(ValueError):
        normalize_count("99-99")


def test_batter_stance_normalization_edge_cases():
    """Test batter stance normalizer case-insensitivity, single-char abbreviations, and fallbacks."""
    # Case variants
    assert normalize_batter_stance("left") == "left"
    assert normalize_batter_stance("Left") == "left"
    assert normalize_batter_stance("LEFT") == "left"
    assert normalize_batter_stance("right") == "right"
    assert normalize_batter_stance("Right") == "right"
    assert normalize_batter_stance("RIGHT") == "right"
    assert normalize_batter_stance("both") == "both"
    assert normalize_batter_stance("Both") == "both"
    assert normalize_batter_stance("BOTH") == "both"

    # Abbreviations
    assert normalize_batter_stance("l") == "left"
    assert normalize_batter_stance("L") == "left"
    assert normalize_batter_stance("r") == "right"
    assert normalize_batter_stance("R") == "right"
    assert normalize_batter_stance("b") == "both"
    assert normalize_batter_stance("switch") == "both"
    assert normalize_batter_stance("s") == "both"

    # Whitespace
    assert normalize_batter_stance("  left  ") == "left"

    # Empty / None
    assert normalize_batter_stance(None) is None
    assert normalize_batter_stance("") is None

    # Invalid returns None
    assert normalize_batter_stance("invalid-stance") is None
    assert normalize_batter_stance("123") is None


def test_pitcher_hand_normalization_edge_cases():
    """Test pitcher hand normalizer variations."""
    assert normalize_pitcher_hand("L") == "L"
    assert normalize_pitcher_hand("l") == "L"
    assert normalize_pitcher_hand("left") == "L"
    assert normalize_pitcher_hand("LEFT") == "L"
    assert normalize_pitcher_hand("R") == "R"
    assert normalize_pitcher_hand("r") == "R"
    assert normalize_pitcher_hand("right") == "R"
    assert normalize_pitcher_hand("both") == "both"
    assert normalize_pitcher_hand("Both") == "both"
    assert normalize_pitcher_hand("switch") == "both"
    assert normalize_pitcher_hand("s") == "both"
    assert normalize_pitcher_hand("b") == "both"
    assert normalize_pitcher_hand(None) is None
    assert normalize_pitcher_hand("") is None
    assert normalize_pitcher_hand("invalid") is None


# ==============================================================================
# 3. WEB API ERROR HANDLING & SECURITY
# ==============================================================================

def test_api_scrape_missing_pitcher(client):
    """POST /api/scrape missing pitcher_name returns 400."""
    resp = client.post("/api/scrape", json={"search_mode": "pitcher", "pitcher_name": ""})
    assert resp.status_code == 400
    assert "Pitcher name is required" in resp.get_json()["error"]


def test_api_scrape_missing_batter(client):
    """POST /api/scrape missing batter_name in batter mode returns 400."""
    resp = client.post("/api/scrape", json={"search_mode": "batter", "batter_name": ""})
    assert resp.status_code == 400
    assert "Batter name is required" in resp.get_json()["error"]


def test_api_scrape_invalid_count(client):
    """POST /api/scrape with invalid ball-strike count returns 400."""
    payload = {
        "search_mode": "pitcher",
        "pitcher_name": "Tarik Skubal",
        "pitcher_hand": "L",
        "batter_stance": "Both",
        "count": "4-2",  # Invalid count
    }
    resp = client.post("/api/scrape", json=payload)
    assert resp.status_code == 400
    assert "balls must be 0-3" in resp.get_json()["error"]


def test_api_csv_data_security_boundary(client, tmp_path):
    """GET /api/csv-data blocks directory traversal attacks and missing params."""
    # Missing filename
    resp0 = client.get("/api/csv-data")
    assert resp0.status_code == 400
    assert "Filename is required" in resp0.get_json()["error"]

    # Attempt parent directory traversal
    resp1 = client.get("/api/csv-data?filename=../../etc/passwd")
    assert resp1.status_code == 400
    assert "Invalid filename" in resp1.get_json()["error"]

    # Attempt absolute path traversal
    resp2 = client.get("/api/csv-data?filename=/etc/passwd")
    assert resp2.status_code == 400
    assert "Invalid filename" in resp2.get_json()["error"]

    # Attempt missing file
    resp3 = client.get("/api/csv-data?filename=nonexistent.csv")
    assert resp3.status_code == 404
    assert "not found" in resp3.get_json()["error"].lower()


# ==============================================================================
# 4. THREE-SOURCE BETTING MODEL MATH & EDGE CASES
# ==============================================================================

def test_american_odds_parser():
    """Verify conversion of American odds to break-even probability and profit."""
    # -110 standard line
    prob_fav = american_to_prob(-110)
    profit_fav = american_profit(-110)
    assert round(prob_fav, 4) == round(110 / 210, 4)
    assert round(profit_fav, 4) == round(100 / 110, 4)

    # +150 underdog line
    prob_dog = american_to_prob(150)
    profit_dog = american_profit(150)
    assert round(prob_dog, 4) == round(100 / 250, 4)
    assert round(profit_dog, 4) == 1.5000

    # Invalid: 0 or inside (-100, 100)
    with pytest.raises(ValueError):
        american_to_prob(0)
    with pytest.raises(ValueError):
        american_to_prob(50)


def test_kelly_criterion_edge_cases():
    """Verify Kelly staking behavior under positive, zero, and negative edge."""
    # Profit ratio b for even money (+100) is 1.0
    b = american_profit(100)

    # Positive edge: win prob 60% -> (1.0 * 0.60 - 0.40) / 1.0 = 0.20
    p_win = 0.60
    p_lose = 1 - p_win
    kelly_pos = max(0.0, (b * p_win - p_lose) / b)
    assert round(kelly_pos, 4) == 0.2000

    # Negative edge: win prob 40% -> negative fraction clamped to 0
    p_win = 0.40
    p_lose = 1 - p_win
    kelly_neg = max(0.0, (b * p_win - p_lose) / b)
    assert kelly_neg == 0.0

    # Zero edge: win prob 50%
    p_win = 0.50
    p_lose = 0.50
    kelly_zero = max(0.0, (b * p_win - p_lose) / b)
    assert kelly_zero == 0.0

    # 100% win certainty
    p_win = 1.0
    p_lose = 0.0
    k_certain = max(0.0, (b * p_win - p_lose) / b)
    assert k_certain == 1.0


def test_model_run_api_validation(client):
    """POST /api/model/run input validation edge cases."""
    # Non-numeric bet_line
    resp1 = client.post("/api/model/run", json={"bet_line": "ninety-six", "under_odds": -110, "over_odds": -110})
    assert resp1.status_code == 400
    assert "betting velocity line" in resp1.get_json()["error"].lower()

    # Out of range bet_line (< 50 mph or > 125 mph)
    resp2 = client.post("/api/model/run", json={"bet_line": 25.0, "under_odds": -110, "over_odds": -110})
    assert resp2.status_code == 400
    assert "between 50 and 125 mph" in resp2.get_json()["error"]

    resp3 = client.post("/api/model/run", json={"bet_line": 150.0, "under_odds": -110, "over_odds": -110})
    assert resp3.status_code == 400
    assert "between 50 and 125 mph" in resp3.get_json()["error"]

    # Invalid Under odds (between -100 and 100)
    resp4 = client.post("/api/model/run", json={"bet_line": 95.5, "under_odds": 50, "over_odds": -110})
    assert resp4.status_code == 400
    assert "Invalid Under odds" in resp4.get_json()["error"]

    # Invalid Over odds (non-numeric string)
    resp5 = client.post("/api/model/run", json={"bet_line": 95.5, "under_odds": -110, "over_odds": "even"})
    assert resp5.status_code == 400
    assert "Invalid Over odds" in resp5.get_json()["error"]


# ==============================================================================
# 5. RECENT SEARCHES QUEUE & CAPACITY
# ==============================================================================

def test_recent_searches_cap_and_order(client, test_app):
    """Verify that recent searches maintain descending order and list active items."""
    recent_searches_session.clear()
    out_dir = Path(test_app.config["OUTPUT_DIR"])

    # Prepend 10 items directly to session and create matching files
    for i in range(10):
        fname = f"sample_{i}.csv"
        fpath = out_dir / fname
        fpath.write_text("Pitch Type,Velocity\nFastball,95.0\n", encoding="utf-8")
        recent_searches_session.insert(0, {
            "filename": fname,
            "query_name": f"Pitcher {i}",
            "display_name": f"Pitcher {i}",
            "search_mode": "pitcher",
            "season": 2026,
            "count": None,
            "timestamp": 1000 + i,
            "rows_count": 1,
            "is_matchup": False,
        })

    resp = client.get("/api/recent")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "recent" in data
    recent_items = data["recent"]

    assert len(recent_items) == 10
    # Most recent timestamp should be at the front
    assert "Pitcher 9" in recent_items[0]["display_name"]
