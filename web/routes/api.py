"""REST API endpoints for the Baseball Savant web interface."""

import csv
import io
import json
import logging
from pathlib import Path
import time
from typing import Any, Dict, List, Optional
import zipfile
from flask import Blueprint, current_app, jsonify, make_response, request, send_file

from dataModel.threeSourceModel import evaluate_and_report, to_json
from scraper.config import DEFAULT_SEASON, normalize_batter_stance, normalize_count, normalize_pitcher_hand
from scraper.data_model_sync import DEFAULT_DATA_MODEL_DIR, DataModelSync
from scraper.odds_provider import normalize_american_odds
from scraper.pipeline import ScraperPipeline
from scraper.player_search import PlayerSearchService
from scraper.utils import clear_output_directory

logger = logging.getLogger(__name__)

api_bp = Blueprint("api", __name__, url_prefix="/api")

# In-memory recent search session storage for rich metadata
recent_searches_session: List[Dict[str, Any]] = []
RECENT_CACHE_FILE = ".recent_searches_cache.json"


def _clean_str(val: Any) -> Optional[str]:
    """Ensure value is a string, filtering out MagicMock or non-string objects."""
    return val if isinstance(val, str) else None


def _clean_id(val: Any) -> Optional[int]:
    """Ensure value is an integer or numeric string, filtering out MagicMocks."""
    if isinstance(val, int) and not isinstance(val, bool):
        return val
    if isinstance(val, str) and val.isdigit():
        return int(val)
    return None


def _save_recent_session():
    """Persist recent searches session to JSON cache in output directory."""
    try:
        cache_path = _get_output_dir() / RECENT_CACHE_FILE
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(recent_searches_session, f, indent=2)
    except Exception as e:
        logger.warning(f"Could not save recent searches cache: {e}")


def _load_recent_session():
    """Load recent searches session from JSON cache if session is currently empty."""
    global recent_searches_session
    if recent_searches_session:
        return
    try:
        cache_path = _get_output_dir() / RECENT_CACHE_FILE
        if cache_path.exists():
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    recent_searches_session[:] = data
    except Exception as e:
        logger.warning(f"Could not load recent searches cache: {e}")


def _format_display_name_from_filename(filename: str) -> str:
    """Convert snake_case filename into a clean display title."""
    stem = Path(filename).stem
    parts = stem.split("_")
    # Handle patterns like "chris_sale_2021_pitch_arsenal" or "shohei_ohtani_vs_chris_sale_2026"
    title_words = [p.capitalize() if not p.isdigit() else f"({p})" for p in parts]
    return " ".join(title_words)


def _get_output_dir() -> Path:
    """Resolve output directory from app config or default."""
    configured_dir = current_app.config.get("OUTPUT_DIR", "output")
    out_path = Path(configured_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    return out_path


@api_bp.route("/search/player", methods=["GET"])
def search_player():
    """Search for MLB player by name or ID."""
    query = request.args.get("query", "").strip()
    player_type = request.args.get("type", "").strip().lower() or None

    if not query:
        return jsonify({"query": "", "results": []})

    search_service: PlayerSearchService = current_app.config.get(
        "PLAYER_SEARCH_SERVICE"
    ) or PlayerSearchService()

    try:
        players = search_service.search_player(query, player_type=player_type)
        results = [p.to_dict() for p in players]
        return jsonify({"query": query, "results": results})
    except Exception as e:
        logger.error(f"Error in player search API: {e}", exc_info=True)
        return jsonify({"error": str(e), "results": []}), 500


def _read_csv_table(file_path: Path) -> Dict[str, Any]:
    """Helper to parse a CSV file into structured columns and row dictionaries."""
    if not isinstance(file_path, Path):
        file_path = Path(file_path)
    if not file_path.exists():
        return {
            "filename": file_path.name,
            "columns": [],
            "rows": [],
            "total_rows": 0,
        }
    with open(file_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        columns = reader.fieldnames or []
        rows = list(reader)
    return {
        "filename": file_path.name,
        "columns": columns,
        "rows": rows,
        "total_rows": len(rows),
    }


@api_bp.route("/scrape", methods=["POST"])
def run_scrape():
    """Execute Statcast pitch scrape for pitcher or batter."""
    data = request.get_json(silent=True) or {}
    search_mode = data.get("search_mode", "pitcher").lower()

    pipeline: ScraperPipeline = current_app.config.get(
        "SCRAPER_PIPELINE"
    ) or ScraperPipeline()
    output_dir = _get_output_dir()

    try:
        season = int(data.get("season", DEFAULT_SEASON))
    except (ValueError, TypeError):
        season = DEFAULT_SEASON

    raw_count = data.get("count")
    try:
        count = normalize_count(raw_count) if raw_count else None
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    if search_mode == "pitcher":
        pitcher = data.get("pitcher_name")
        if not pitcher:
            return jsonify({"error": "Pitcher name is required"}), 400

        pitcher_hand = normalize_pitcher_hand(data.get("pitcher_hand")) or "both"
        batter = data.get("batter_name")
        batter_stance = normalize_batter_stance(data.get("batter_stance")) or "both"

        if batter:
            # Head-to-Head matchup: generate 3 sets of data (Pitcher, Batter, H2H)
            try:
                matchup_res = pipeline.scrape_head_to_head_to_csv(
                    mode="pitcher",
                    pitcher=pitcher,
                    pitcher_hand=pitcher_hand,
                    batter=batter,
                    batter_stance=batter_stance,
                    season=season,
                    count=count,
                )
            except Exception as e:
                logger.error(f"Scraper execution error: {e}", exc_info=True)
                return jsonify({"error": str(e)}), 500

            p1_file = Path(matchup_res["player1"]["file"])
            p2_file = Path(matchup_res["player2"]["file"])
            h2h_file = Path(matchup_res["matchup"]["file"])

            p1_data = _read_csv_table(p1_file)
            p2_data = _read_csv_table(p2_file)
            h2h_data = _read_csv_table(h2h_file)

            p1_id = _clean_id(matchup_res["player1"].get("id"))
            p1_headshot = _clean_str(matchup_res["player1"].get("headshot_url")) or (
                f"https://content.mlb.com/images/headshots/current/60x60/{p1_id}@3x.png" if p1_id else None
            )
            p2_id = _clean_id(matchup_res["player2"].get("id"))
            p2_headshot = _clean_str(matchup_res["player2"].get("headshot_url")) or (
                f"https://content.mlb.com/images/headshots/current/60x60/{p2_id}@3x.png" if p2_id else None
            )

            p1_payload = {
                **p1_data,
                "name": matchup_res["player1"]["name"],
                "role": "Pitcher",
                "id": p1_id,
                "headshot_url": p1_headshot,
                "display_name": f"{matchup_res['player1']['name']} (Pitcher Arsenal)",
            }
            p2_payload = {
                **p2_data,
                "name": matchup_res["player2"]["name"],
                "role": "Batter",
                "id": p2_id,
                "headshot_url": p2_headshot,
                "display_name": f"{matchup_res['player2']['name']} (Pitches Faced)",
            }
            count_suffix = f" [Count: {count}]" if count else ""
            h2h_payload = {
                **h2h_data,
                "name": matchup_res["matchup"]["name"],
                "role": "Head-to-Head",
                "display_name": f"{matchup_res['matchup']['name']}{count_suffix} ({season})",
            }

            count_label = f" [Count: {count}]" if count else ""
            query_name = f"{pitcher} vs {batter}{count_label} ({season})"
            entry = {
                "filename": h2h_file.name,
                "query_name": query_name,
                "display_name": query_name,
                "search_mode": search_mode,
                "season": season,
                "count": count,
                "timestamp": h2h_file.stat().st_mtime if h2h_file.exists() else 0,
                "rows_count": h2h_data["total_rows"],
                "is_matchup": True,
                "player1_filename": p1_file.name,
                "player2_filename": p2_file.name,
                "player1_name": matchup_res["player1"]["name"],
                "player2_name": matchup_res["player2"]["name"],
                "player1_id": p1_id,
                "player2_id": p2_id,
                "player1_headshot_url": p1_headshot,
                "player2_headshot_url": p2_headshot,
            }
            recent_searches_session[:] = [
                item for item in recent_searches_session if item["filename"] != h2h_file.name
            ]
            recent_searches_session.insert(0, entry)
            _save_recent_session()

            return jsonify({
                "success": True,
                "is_matchup": True,
                "filename": h2h_file.name,
                "query_name": query_name,
                "display_name": query_name,
                "search_mode": search_mode,
                "season": season,
                "count": count,
                "columns": h2h_data["columns"],
                "rows": h2h_data["rows"],
                "total_rows": h2h_data["total_rows"],
                "player1": p1_payload,
                "player2": p2_payload,
                "matchup": h2h_payload,
                "data_model_synced": matchup_res.get("data_model_sync", {}).get("success", False),
                "data_model_info": matchup_res.get("data_model_sync"),
            })
        else:
            # Single pitcher search
            search_service = (
                current_app.config.get("PLAYER_SEARCH_SERVICE")
                or getattr(pipeline, "player_search", None)
                or PlayerSearchService()
            )
            p_info = None
            try:
                p_info = search_service.find_pitcher(pitcher)
            except Exception:
                pass
            single_player_id = _clean_id(getattr(p_info, "player_id", None))
            single_headshot_url = (
                f"https://content.mlb.com/images/headshots/current/60x60/{single_player_id}@3x.png"
                if single_player_id
                else None
            )
            single_player_name = _clean_str(getattr(p_info, "full_name", None)) or str(pitcher)

            try:
                exported_file = pipeline.scrape_pitcher_arsenal_to_csv(
                    pitcher=pitcher,
                    pitcher_hand=pitcher_hand,
                    batter=None,
                    batter_stance=batter_stance,
                    season=season,
                    count=count,
                )
            except Exception as e:
                logger.error(f"Scraper execution error: {e}", exc_info=True)
                return jsonify({"error": str(e)}), 500

            count_label = f" [Count: {count}]" if count else ""
            query_name = f"{single_player_name}{count_label} ({season})"

    elif search_mode == "batter":
        batter = data.get("batter_name")
        if not batter:
            return jsonify({"error": "Batter name is required"}), 400

        batter_stance = normalize_batter_stance(data.get("batter_stance")) or "both"
        pitcher = data.get("pitcher_name")
        pitcher_hand = normalize_pitcher_hand(data.get("pitcher_hand")) or "both"

        if pitcher:
            # Head-to-Head matchup: generate 3 sets of data (Batter, Pitcher, H2H)
            try:
                matchup_res = pipeline.scrape_head_to_head_to_csv(
                    mode="batter",
                    pitcher=pitcher,
                    pitcher_hand=pitcher_hand,
                    batter=batter,
                    batter_stance=batter_stance,
                    season=season,
                    count=count,
                )
            except Exception as e:
                logger.error(f"Scraper execution error: {e}", exc_info=True)
                return jsonify({"error": str(e)}), 500

            p1_file = Path(matchup_res["player1"]["file"])
            p2_file = Path(matchup_res["player2"]["file"])
            h2h_file = Path(matchup_res["matchup"]["file"])

            p1_data = _read_csv_table(p1_file)
            p2_data = _read_csv_table(p2_file)
            h2h_data = _read_csv_table(h2h_file)

            p1_id = _clean_id(matchup_res["player1"].get("id"))
            p1_headshot = _clean_str(matchup_res["player1"].get("headshot_url")) or (
                f"https://content.mlb.com/images/headshots/current/60x60/{p1_id}@3x.png" if p1_id else None
            )
            p2_id = _clean_id(matchup_res["player2"].get("id"))
            p2_headshot = _clean_str(matchup_res["player2"].get("headshot_url")) or (
                f"https://content.mlb.com/images/headshots/current/60x60/{p2_id}@3x.png" if p2_id else None
            )

            p1_payload = {
                **p1_data,
                "name": matchup_res["player1"]["name"],
                "role": "Batter",
                "id": p1_id,
                "headshot_url": p1_headshot,
                "display_name": f"{matchup_res['player1']['name']} (Pitches Faced)",
            }
            p2_payload = {
                **p2_data,
                "name": matchup_res["player2"]["name"],
                "role": "Pitcher",
                "id": p2_id,
                "headshot_url": p2_headshot,
                "display_name": f"{matchup_res['player2']['name']} (Pitcher Arsenal)",
            }
            count_suffix = f" [Count: {count}]" if count else ""
            h2h_payload = {
                **h2h_data,
                "name": matchup_res["matchup"]["name"],
                "role": "Head-to-Head",
                "display_name": f"{matchup_res['matchup']['name']}{count_suffix} ({season})",
            }

            count_label = f" [Count: {count}]" if count else ""
            query_name = f"{batter} vs {pitcher}{count_label} ({season})"
            entry = {
                "filename": h2h_file.name,
                "query_name": query_name,
                "display_name": query_name,
                "search_mode": search_mode,
                "season": season,
                "count": count,
                "timestamp": h2h_file.stat().st_mtime if h2h_file.exists() else 0,
                "rows_count": h2h_data["total_rows"],
                "is_matchup": True,
                "player1_filename": p1_file.name,
                "player2_filename": p2_file.name,
                "player1_name": matchup_res["player1"]["name"],
                "player2_name": matchup_res["player2"]["name"],
                "player1_id": p1_id,
                "player2_id": p2_id,
                "player1_headshot_url": p1_headshot,
                "player2_headshot_url": p2_headshot,
            }
            recent_searches_session[:] = [
                item for item in recent_searches_session if item["filename"] != h2h_file.name
            ]
            recent_searches_session.insert(0, entry)
            _save_recent_session()

            return jsonify({
                "success": True,
                "is_matchup": True,
                "filename": h2h_file.name,
                "query_name": query_name,
                "display_name": query_name,
                "search_mode": search_mode,
                "season": season,
                "count": count,
                "columns": h2h_data["columns"],
                "rows": h2h_data["rows"],
                "total_rows": h2h_data["total_rows"],
                "player1": p1_payload,
                "player2": p2_payload,
                "matchup": h2h_payload,
                "data_model_synced": matchup_res.get("data_model_sync", {}).get("success", False),
                "data_model_info": matchup_res.get("data_model_sync"),
            })
        else:
            # Single batter search
            search_service = (
                current_app.config.get("PLAYER_SEARCH_SERVICE")
                or getattr(pipeline, "player_search", None)
                or PlayerSearchService()
            )
            b_info = None
            try:
                b_info = search_service.find_batter(batter)
            except Exception:
                pass
            single_player_id = _clean_id(getattr(b_info, "player_id", None))
            single_headshot_url = (
                f"https://content.mlb.com/images/headshots/current/60x60/{single_player_id}@3x.png"
                if single_player_id
                else None
            )
            single_player_name = _clean_str(getattr(b_info, "full_name", None)) or str(batter)

            try:
                exported_file = pipeline.scrape_batter_pitches_to_csv(
                    batter=batter,
                    batter_stance=batter_stance,
                    pitcher=None,
                    pitcher_hand=pitcher_hand,
                    season=season,
                    count=count,
                )
            except Exception as e:
                logger.error(f"Scraper execution error: {e}", exc_info=True)
                return jsonify({"error": str(e)}), 500

            count_label = f" [Count: {count}]" if count else ""
            query_name = f"{single_player_name}{count_label} ({season})"

    else:
        return jsonify({"error": f"Invalid search mode: {search_mode}"}), 400

    # Read generated CSV data to return directly for single searches
    csv_info = _read_csv_table(exported_file)

    entry = {
        "filename": exported_file.name,
        "query_name": query_name,
        "display_name": query_name,
        "search_mode": search_mode,
        "season": season,
        "count": count,
        "timestamp": exported_file.stat().st_mtime if exported_file.exists() else 0,
        "rows_count": csv_info["total_rows"],
        "is_matchup": False,
        "player_id": single_player_id,
        "player_name": single_player_name,
        "headshot_url": single_headshot_url,
    }

    # Prepend to session storage (avoid duplicates)
    recent_searches_session[:] = [
        item for item in recent_searches_session if item["filename"] != exported_file.name
    ]
    recent_searches_session.insert(0, entry)
    _save_recent_session()

    return jsonify({
        "success": True,
        "is_matchup": False,
        "filename": exported_file.name,
        "query_name": query_name,
        "display_name": query_name,
        "search_mode": search_mode,
        "season": season,
        "count": count,
        "player_id": single_player_id,
        "player_name": single_player_name,
        "headshot_url": single_headshot_url,
        "columns": csv_info["columns"],
        "rows": csv_info["rows"],
        "total_rows": csv_info["total_rows"],
    })


@api_bp.route("/recent", methods=["GET"])
def get_recent_searches():
    """List recent searches from session and output directory."""
    _load_recent_session()
    output_dir = _get_output_dir()
    existing_files = {f.name: f for f in output_dir.glob("*.csv")}

    # Clean session memory for deleted files
    active_session = [
        item for item in recent_searches_session if item["filename"] in existing_files
    ]

    # Check for any CSV files in output folder not yet in session
    session_filenames = {item["filename"] for item in active_session}
    search_service: Optional[PlayerSearchService] = None

    for fname, fpath in existing_files.items():
        if fname not in session_filenames:
            try:
                with open(fpath, mode="r", encoding="utf-8") as f:
                    r = csv.reader(f)
                    next(r, None)  # header
                    count = sum(1 for _ in r)
            except Exception:
                count = 0

            if search_service is None:
                search_service = current_app.config.get("PLAYER_SEARCH_SERVICE") or PlayerSearchService()

            is_match = "_vs_" in fname
            stem = fpath.stem
            player1_id = None
            player1_name = None
            player1_headshot = None
            player2_id = None
            player2_name = None
            player2_headshot = None
            single_id = None
            single_name = None
            single_headshot = None

            if is_match:
                parts = stem.split("_vs_")
                p1_candidate = parts[0].replace("_", " ").title()
                p2_raw = parts[1] if len(parts) > 1 else ""
                p2_words = [w for w in p2_raw.split("_") if not w.isdigit() and w != "count"]
                p2_candidate = " ".join(p2_words).title()

                p1_info = search_service.find_pitcher(p1_candidate) or search_service.find_batter(p1_candidate)
                p2_info = search_service.find_batter(p2_candidate) or search_service.find_pitcher(p2_candidate)
                if p1_info:
                    player1_id = _clean_id(getattr(p1_info, "player_id", None))
                    p1_nm = _clean_str(getattr(p1_info, "full_name", None))
                    player1_name = p1_nm or p1_candidate
                    player1_headshot = (
                        f"https://content.mlb.com/images/headshots/current/60x60/{player1_id}@3x.png"
                        if player1_id
                        else None
                    )
                else:
                    player1_name = p1_candidate
                if p2_info:
                    player2_id = _clean_id(getattr(p2_info, "player_id", None))
                    p2_nm = _clean_str(getattr(p2_info, "full_name", None))
                    player2_name = p2_nm or p2_candidate
                    player2_headshot = (
                        f"https://content.mlb.com/images/headshots/current/60x60/{player2_id}@3x.png"
                        if player2_id
                        else None
                    )
                else:
                    player2_name = p2_candidate
            else:
                clean_name = stem.replace("_pitch_arsenal", "").replace("_pitches_faced", "")
                name_words = [w for w in clean_name.split("_") if not w.isdigit() and w != "count"]
                cand = " ".join(name_words).title()
                s_info = search_service.find_pitcher(cand) or search_service.find_batter(cand)
                if s_info:
                    single_id = _clean_id(getattr(s_info, "player_id", None))
                    s_nm = _clean_str(getattr(s_info, "full_name", None))
                    single_name = s_nm or cand
                    single_headshot = (
                        f"https://content.mlb.com/images/headshots/current/60x60/{single_id}@3x.png"
                        if single_id
                        else None
                    )
                else:
                    single_name = cand

            item = {
                "filename": fname,
                "query_name": _format_display_name_from_filename(fname),
                "display_name": _format_display_name_from_filename(fname),
                "search_mode": "pitcher",
                "season": "",
                "timestamp": fpath.stat().st_mtime,
                "rows_count": count,
                "is_matchup": is_match,
            }
            if is_match:
                item.update({
                    "player1_id": player1_id,
                    "player1_name": player1_name,
                    "player1_headshot_url": player1_headshot,
                    "player2_id": player2_id,
                    "player2_name": player2_name,
                    "player2_headshot_url": player2_headshot,
                })
            else:
                item.update({
                    "player_id": single_id,
                    "player_name": single_name,
                    "headshot_url": single_headshot,
                })

            active_session.append(item)
            recent_searches_session.append(item)

    if len(active_session) != len(recent_searches_session):
        recent_searches_session[:] = list(active_session)
    _save_recent_session()

    # Sort descending by timestamp
    active_session.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
    return jsonify({"recent": active_session})


@api_bp.route("/csv-data", methods=["GET"])
def get_csv_data():
    """Retrieve and parse CSV data for a specific output file, including matchup companion data."""
    filename = request.args.get("filename", "").strip()
    if not filename:
        return jsonify({"error": "Filename is required"}), 400

    # Prevent directory traversal
    if "/" in filename or "\\" in filename or ".." in filename:
        return jsonify({"error": "Invalid filename"}), 400

    output_dir = _get_output_dir()
    csv_file = output_dir / filename
    if not csv_file.exists() or not csv_file.is_file():
        return jsonify({"error": f"File '{filename}' not found"}), 404

    try:
        main_data = _read_csv_table(csv_file)
        display_name = _format_display_name_from_filename(filename)
        session_entry = next((item for item in recent_searches_session if item["filename"] == filename), None)
        if session_entry:
            display_name = session_entry.get("query_name", display_name)

        # Check if this is a matchup file
        is_matchup = False
        player1_payload = None
        player2_payload = None
        matchup_payload = None

        if session_entry and session_entry.get("is_matchup"):
            p1_fname = session_entry.get("player1_filename")
            p2_fname = session_entry.get("player2_filename")
            if p1_fname and p2_fname and (output_dir / p1_fname).exists() and (output_dir / p2_fname).exists():
                p1_data = _read_csv_table(output_dir / p1_fname)
                p2_data = _read_csv_table(output_dir / p2_fname)
                is_matchup = True
                p1_role = "Pitcher" if session_entry.get("search_mode") == "pitcher" else "Batter"
                p2_role = "Batter" if session_entry.get("search_mode") == "pitcher" else "Pitcher"
                player1_payload = {
                    **p1_data,
                    "name": session_entry.get("player1_name", _format_display_name_from_filename(p1_fname)),
                    "role": p1_role,
                    "display_name": f"{session_entry.get('player1_name', '')} ({'Pitcher Arsenal' if p1_role == 'Pitcher' else 'Pitches Faced'})",
                }
                player2_payload = {
                    **p2_data,
                    "name": session_entry.get("player2_name", _format_display_name_from_filename(p2_fname)),
                    "role": p2_role,
                    "display_name": f"{session_entry.get('player2_name', '')} ({'Pitcher Arsenal' if p2_role == 'Pitcher' else 'Pitches Faced'})",
                }
                matchup_payload = {
                    **main_data,
                    "name": display_name,
                    "role": "Head-to-Head",
                    "display_name": display_name,
                }
        elif "_vs_" in filename:
            # Fallback deduction from filename pattern: e.g. chris_sale_vs_shohei_ohtani_2024.csv
            parts = filename.replace(".csv", "").split("_vs_")
            if len(parts) == 2:
                p1_slug = parts[0]
                rest = parts[1].rsplit("_", 1)
                p2_slug = rest[0]
                season_str = rest[1] if len(rest) > 1 else ""

                p1_p_file = output_dir / f"{p1_slug}_{season_str}_pitch_arsenal.csv"
                p2_b_file = output_dir / f"{p2_slug}_{season_str}_pitches_faced.csv"
                p1_b_file = output_dir / f"{p1_slug}_{season_str}_pitches_faced.csv"
                p2_p_file = output_dir / f"{p2_slug}_{season_str}_pitch_arsenal.csv"

                if p1_p_file.exists() and p2_b_file.exists():
                    is_matchup = True
                    p1_data = _read_csv_table(p1_p_file)
                    p2_data = _read_csv_table(p2_b_file)
                    p1_name = _format_display_name_from_filename(p1_p_file.name).split("(")[0].strip()
                    p2_name = _format_display_name_from_filename(p2_b_file.name).split("(")[0].strip()
                    player1_payload = {
                        **p1_data,
                        "name": p1_name,
                        "role": "Pitcher",
                        "display_name": f"{p1_name} (Pitcher Arsenal)",
                    }
                    player2_payload = {
                        **p2_data,
                        "name": p2_name,
                        "role": "Batter",
                        "display_name": f"{p2_name} (Pitches Faced)",
                    }
                    matchup_payload = {
                        **main_data,
                        "name": display_name,
                        "role": "Head-to-Head",
                        "display_name": display_name,
                    }
                elif p1_b_file.exists() and p2_p_file.exists():
                    is_matchup = True
                    p1_data = _read_csv_table(p1_b_file)
                    p2_data = _read_csv_table(p2_p_file)
                    p1_name = _format_display_name_from_filename(p1_b_file.name).split("(")[0].strip()
                    p2_name = _format_display_name_from_filename(p2_p_file.name).split("(")[0].strip()
                    player1_payload = {
                        **p1_data,
                        "name": p1_name,
                        "role": "Batter",
                        "display_name": f"{p1_name} (Pitches Faced)",
                    }
                    player2_payload = {
                        **p2_data,
                        "name": p2_name,
                        "role": "Pitcher",
                        "display_name": f"{p2_name} (Pitcher Arsenal)",
                    }
                    matchup_payload = {
                        **main_data,
                        "name": display_name,
                        "role": "Head-to-Head",
                        "display_name": display_name,
                    }

        res = {
            "filename": filename,
            "display_name": display_name,
            "columns": main_data["columns"],
            "rows": main_data["rows"],
            "total_rows": main_data["total_rows"],
            "is_matchup": is_matchup,
        }
        if is_matchup:
            res["player1"] = player1_payload
            res["player2"] = player2_payload
            res["matchup"] = matchup_payload

        return jsonify(res)
    except Exception as e:
        logger.error(f"Error reading CSV '{filename}': {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500



@api_bp.route("/clear-output", methods=["POST"])
def clear_output():
    """Clear all files from the output directory and wipe session history."""
    output_dir = _get_output_dir()
    count = clear_output_directory(output_dir)
    recent_searches_session.clear()
    _save_recent_session()
    logger.info(f"Cleared {count} files from '{output_dir}'.")
    return jsonify({"success": True, "cleared_count": count})


@api_bp.route("/download-zip", methods=["GET"])
def download_zip():
    """Package requested CSV files from output directory into a single ZIP file."""
    raw_list = request.args.getlist("files") or request.args.getlist("files[]")
    if not raw_list:
        raw_val = request.args.get("files", "")
        raw_list = [raw_val] if raw_val else []

    filenames = []
    for item in raw_list:
        for f in item.split(","):
            f = f.strip()
            if f and f not in filenames:
                filenames.append(f)

    if not filenames:
        return jsonify({"error": "No files specified"}), 400

    output_dir = _get_output_dir()
    zip_buffer = io.BytesIO()

    zip_filename = request.args.get("zip_name", "statcast_matchup_data.zip").strip()
    if "/" in zip_filename or "\\" in zip_filename:
        zip_filename = "statcast_matchup_data.zip"
    if not zip_filename.endswith(".zip"):
        zip_filename += ".zip"

    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        added_count = 0
        for fname in filenames:
            if "/" in fname or "\\" in fname or ".." in fname:
                continue
            csv_path = output_dir / fname
            if csv_path.exists() and csv_path.is_file():
                zf.write(csv_path, arcname=csv_path.name)
                added_count += 1

    if added_count == 0:
        return jsonify({"error": "None of the requested files were found"}), 404

    zip_buffer.seek(0)
    return send_file(
        zip_buffer,
        mimetype="application/zip",
        as_attachment=True,
        download_name=zip_filename,
    )


# ==============================================================================
# THREE-SOURCE DATA MODEL INTEGRATION ENDPOINTS
# ==============================================================================

def _get_data_model_dir() -> Path:
    """Resolve dataModel directory from Flask app config or default."""
    configured = current_app.config.get("DATA_MODEL_DIR", DEFAULT_DATA_MODEL_DIR)
    path = Path(configured)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _resolve_matchup_trio_from_output(filename: str, output_dir: Path) -> Optional[Dict[str, Any]]:
    """Resolve pitcher, batter, and matchup CSV files for a given head-to-head filename."""
    h2h_file = output_dir / filename
    if not h2h_file.exists() or not h2h_file.is_file():
        return None

    # 1. First check in-memory recent searches session
    session_match = next((item for item in recent_searches_session if item["filename"] == filename), None)
    if session_match and session_match.get("is_matchup"):
        p1_fname = session_match.get("player1_filename")
        p2_fname = session_match.get("player2_filename")
        if p1_fname and p2_fname:
            p1_file = output_dir / p1_fname
            p2_file = output_dir / p2_fname
            if p1_file.exists() and p2_file.exists():
                is_p1_pitcher = session_match.get("search_mode", "pitcher") == "pitcher"
                return {
                    "player1": {
                        "name": session_match.get("player1_name", p1_fname),
                        "type": "pitcher" if is_p1_pitcher else "batter",
                        "role": "Pitcher" if is_p1_pitcher else "Batter",
                        "file": str(p1_file),
                    },
                    "player2": {
                        "name": session_match.get("player2_name", p2_fname),
                        "type": "batter" if is_p1_pitcher else "pitcher",
                        "role": "Batter" if is_p1_pitcher else "Pitcher",
                        "file": str(p2_file),
                    },
                    "matchup": {
                        "name": session_match.get("query_name", filename),
                        "role": "Head-to-Head",
                        "type": "matchup",
                        "file": str(h2h_file),
                    },
                    "season": session_match.get("season", DEFAULT_SEASON),
                    "count": session_match.get("count"),
                    "mode": session_match.get("search_mode", "pitcher"),
                }

    # 2. Heuristic discovery from filename: e.g. chris_sale_vs_shohei_ohtani_2026.csv or with count
    stem = h2h_file.stem
    if "_vs_" in stem:
        parts = stem.split("_vs_")
        if len(parts) == 2:
            p1_slug = parts[0]
            rest_str = parts[1]
            # Match potential season/count suffixes:
            # e.g. shohei_ohtani_2026 or shohei_ohtani_2026_count_0_2
            subparts = rest_str.split("_")
            season = DEFAULT_SEASON
            count = None
            if "count" in subparts:
                c_idx = subparts.index("count")
                if c_idx + 2 < len(subparts):
                    count = f"{subparts[c_idx + 1]}-{subparts[c_idx + 2]}"
                p2_slug = "_".join(subparts[:c_idx - 1])
                try:
                    season = int(subparts[c_idx - 1])
                except (ValueError, IndexError):
                    season = DEFAULT_SEASON
            else:
                p2_slug = "_".join(subparts[:-1]) if subparts[-1].isdigit() else rest_str
                try:
                    season = int(subparts[-1])
                except (ValueError, IndexError):
                    season = DEFAULT_SEASON

            count_tag = f"_count_{count.replace('-', '_')}" if count else ""
            # Check p1 as pitcher, p2 as batter
            cand_p1 = output_dir / f"{p1_slug}_{season}{count_tag}_pitch_arsenal.csv"
            cand_p2 = output_dir / f"{p2_slug}_{season}{count_tag}_pitches_faced.csv"
            if cand_p1.exists() and cand_p2.exists():
                p1_name = " ".join([w.capitalize() for w in p1_slug.split("_")])
                p2_name = " ".join([w.capitalize() for w in p2_slug.split("_")])
                return {
                    "player1": {"name": p1_name, "type": "pitcher", "role": "Pitcher", "file": str(cand_p1)},
                    "player2": {"name": p2_name, "type": "batter", "role": "Batter", "file": str(cand_p2)},
                    "matchup": {"name": f"{p1_name} vs {p2_name}", "role": "Head-to-Head", "type": "matchup", "file": str(h2h_file)},
                    "season": season,
                    "count": count,
                    "mode": "pitcher",
                }

            # Check p1 as batter, p2 as pitcher
            cand_b1 = output_dir / f"{p1_slug}_{season}{count_tag}_pitches_faced.csv"
            cand_p2 = output_dir / f"{p2_slug}_{season}{count_tag}_pitch_arsenal.csv"
            if cand_b1.exists() and cand_p2.exists():
                p1_name = " ".join([w.capitalize() for w in p1_slug.split("_")])
                p2_name = " ".join([w.capitalize() for w in p2_slug.split("_")])
                return {
                    "player1": {"name": p1_name, "type": "batter", "role": "Batter", "file": str(cand_b1)},
                    "player2": {"name": p2_name, "type": "pitcher", "role": "Pitcher", "file": str(cand_p2)},
                    "matchup": {"name": f"{p1_name} vs {p2_name}", "role": "Head-to-Head", "type": "matchup", "file": str(h2h_file)},
                    "season": season,
                    "count": count,
                    "mode": "batter",
                }

    return None


@api_bp.route("/model/status", methods=["GET"])
def get_model_status():
    """Retrieve the current dataModel synchronization status and latest run results."""
    data_dir = _get_data_model_dir()
    meta_path = data_dir / "run_meta.json"
    output_path = data_dir / "model_output.json"
    plot_path = data_dir / "model_plot.png"

    has_synced_data = False
    meta_data = None
    if meta_path.exists():
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta_data = json.load(f)
            # Verify input files exist
            p_file = data_dir / "inputPitcher.csv"
            b_file = data_dir / "inputBatter.csv"
            h_file = data_dir / "inputH2H.csv"
            has_synced_data = p_file.exists() and b_file.exists() and h_file.exists()
        except Exception as e:
            logger.warning(f"Could not load run_meta.json: {e}")

    has_output = False
    last_output = None
    if output_path.exists():
        try:
            with open(output_path, "r", encoding="utf-8") as f:
                last_output = json.load(f)
            has_output = True
        except Exception as e:
            logger.warning(f"Could not load model_output.json: {e}")

    return jsonify({
        "success": True,
        "has_synced_data": has_synced_data,
        "meta": meta_data,
        "has_output": has_output,
        "output": last_output,
        "has_plot": plot_path.exists(),
        "plot_url": f"/api/model/plot?t={int(time.time() * 1000)}" if plot_path.exists() else None,
    })


@api_bp.route("/model/samples", methods=["GET"])
def get_model_samples():
    """List all available matchup data samples from output folder and session history."""
    output_dir = _get_output_dir()
    data_dir = _get_data_model_dir()
    meta_path = data_dir / "run_meta.json"

    current_source = None
    if meta_path.exists():
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
                current_source = meta.get("matchup", {}).get("source_file")
        except Exception:
            pass

    samples = []
    seen_filenames = set()

    # 1. Collect from session
    for item in recent_searches_session:
        if item.get("is_matchup") or "_vs_" in item.get("filename", ""):
            fname = item["filename"]
            fpath = output_dir / fname
            if fpath.exists() and fname not in seen_filenames:
                seen_filenames.add(fname)
                p1_name = item.get("player1_name", "")
                p2_name = item.get("player2_name", "")
                samples.append({
                    "filename": fname,
                    "display_name": item.get("display_name") or item.get("query_name") or _format_display_name_from_filename(fname),
                    "pitcher_name": p1_name if item.get("search_mode") == "pitcher" else p2_name,
                    "batter_name": p2_name if item.get("search_mode") == "pitcher" else p1_name,
                    "season": item.get("season", DEFAULT_SEASON),
                    "count": item.get("count"),
                    "timestamp": item.get("timestamp", fpath.stat().st_mtime),
                    "is_active": (fname == current_source),
                })

    # 2. Collect from disk
    for fpath in sorted(output_dir.glob("*_vs_*.csv"), key=lambda p: p.stat().st_mtime, reverse=True):
        if fpath.name not in seen_filenames:
            seen_filenames.add(fpath.name)
            trio = _resolve_matchup_trio_from_output(fpath.name, output_dir)
            p_name = ""
            b_name = ""
            season = DEFAULT_SEASON
            count = None
            if trio:
                p_name = trio["player1"]["name"] if trio["player1"]["type"] == "pitcher" else trio["player2"]["name"]
                b_name = trio["player2"]["name"] if trio["player1"]["type"] == "pitcher" else trio["player1"]["name"]
                season = trio.get("season", DEFAULT_SEASON)
                count = trio.get("count")

            display_title = _format_display_name_from_filename(fpath.name)
            if p_name and b_name:
                count_str = f" [Count: {count}]" if count else ""
                display_title = f"{p_name} vs {b_name}{count_str} ({season})"

            samples.append({
                "filename": fpath.name,
                "display_name": display_title,
                "pitcher_name": p_name,
                "batter_name": b_name,
                "season": season,
                "count": count,
                "timestamp": fpath.stat().st_mtime,
                "is_active": (fpath.name == current_source),
            })

    # Sort descending by timestamp
    samples.sort(key=lambda s: s.get("timestamp", 0), reverse=True)
    return jsonify({"success": True, "samples": samples, "total_samples": len(samples)})


@api_bp.route("/model/load-sample", methods=["POST"])
def load_model_sample():
    """Load and synchronize a historical matchup sample into dataModel."""
    data = request.get_json(silent=True) or {}
    filename = data.get("filename", "").strip()
    if not filename:
        return jsonify({"error": "Filename is required"}), 400

    # Prevent traversal
    if "/" in filename or "\\" in filename or ".." in filename:
        return jsonify({"error": "Invalid filename"}), 400

    output_dir = _get_output_dir()
    trio = _resolve_matchup_trio_from_output(filename, output_dir)
    if not trio:
        return jsonify({"error": f"Matchup companion files for '{filename}' could not be resolved."}), 404

    data_dir = _get_data_model_dir()
    syncer = DataModelSync(data_model_dir=data_dir)

    pitcher_hand = data.get("pitcher_hand")
    batter_stance = data.get("batter_stance")

    try:
        sync_result = syncer.sync_matchup(
            matchup_result=trio,
            pitcher_hand=pitcher_hand,
            batter_stance=batter_stance,
        )
        return jsonify({
            "success": True,
            "filename": filename,
            "sync_result": sync_result,
        })
    except Exception as e:
        logger.error(f"Failed to load model sample '{filename}': {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@api_bp.route("/model/run", methods=["POST"])
def run_data_model():
    """Execute the Three-Source Velocity Model bet evaluation."""
    data = request.get_json(silent=True) or {}

    raw_line = data.get("bet_line", 95.5)
    try:
        bet_line = float(raw_line)
        if bet_line <= 0 or bet_line > 130:
            return jsonify({"error": "Betting velocity line must be between 50 and 125 mph."}), 400
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid numerical betting velocity line."}), 400

    try:
        under_odds = normalize_american_odds(data.get("under_odds", -110), default=-110)
    except ValueError as e:
        return jsonify({"error": f"Invalid Under odds: {e}"}), 400

    try:
        over_odds = normalize_american_odds(data.get("over_odds", -110), default=-110)
    except ValueError as e:
        return jsonify({"error": f"Invalid Over odds: {e}"}), 400

    overrides = {}
    if "stake" in data:
        try:
            overrides["stake"] = float(data["stake"])
        except (ValueError, TypeError):
            pass

    if "bankroll" in data:
        try:
            overrides["bankroll"] = float(data["bankroll"]) if data["bankroll"] is not None else None
        except (ValueError, TypeError):
            pass

    if "kelly_fraction" in data:
        try:
            overrides["kelly_fraction"] = float(data["kelly_fraction"])
        except (ValueError, TypeError):
            pass

    if "arsenal_column" in data and data["arsenal_column"]:
        overrides["arsenal_column"] = str(data["arsenal_column"])

    if "batter_column" in data and data["batter_column"]:
        overrides["batter_column"] = str(data["batter_column"])

    if "n_sims" in data:
        try:
            overrides["n_sims"] = max(100, min(20000, int(data["n_sims"])))
        except (ValueError, TypeError):
            pass

    # Ensure required input files exist in dataModel/
    data_dir = _get_data_model_dir()
    p_file = data_dir / "inputPitcher.csv"
    b_file = data_dir / "inputBatter.csv"
    h_file = data_dir / "inputH2H.csv"
    if not (p_file.exists() or h_file.exists()):
        return jsonify({
            "error": "No pitch speed data found in dataModel/. Please run a matchup scrape or load a previous sample first."
        }), 400

    plot_path = data_dir / "model_plot.png"
    json_path = data_dir / "model_output.json"

    try:
        result = evaluate_and_report(
            bet_line=bet_line,
            under_odds=under_odds,
            over_odds=over_odds,
            show_details_flag=False,
            show_plot_flag=True,
            save_plot_only=True,
            output_plot_path=str(plot_path),
            output_json_path=str(json_path),
            arsenal_csv=str(p_file) if p_file.exists() else "",
            batter_csv=str(b_file) if b_file.exists() else "",
            matchup_csv=str(h_file) if h_file.exists() else "",
            **overrides,
        )

        plot_url = f"/api/model/plot?t={int(time.time() * 1000)}" if plot_path.exists() else None

        return jsonify({
            "success": True,
            "result": to_json(result),
            "plot_url": plot_url,
        })
    except Exception as e:
        logger.error(f"Error executing data model: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@api_bp.route("/model/plot", methods=["GET"])
def get_model_plot():
    """Serve the generated model plot image."""
    data_dir = _get_data_model_dir()
    plot_file = data_dir / "model_plot.png"
    if not plot_file.exists() or not plot_file.is_file():
        return jsonify({"error": "No model plot generated yet."}), 404

    response = make_response(send_file(plot_file, mimetype="image/png"))
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


