"""REST API endpoints for the Baseball Savant web interface."""

import csv
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from flask import Blueprint, current_app, jsonify, request

from scraper.config import DEFAULT_SEASON, normalize_batter_stance, normalize_pitcher_hand
from scraper.pipeline import ScraperPipeline
from scraper.player_search import PlayerSearchService
from scraper.utils import clear_output_directory

logger = logging.getLogger(__name__)

api_bp = Blueprint("api", __name__, url_prefix="/api")

# In-memory recent search session storage for rich metadata
recent_searches_session: List[Dict[str, Any]] = []


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

    if search_mode == "pitcher":
        pitcher = data.get("pitcher_name")
        if not pitcher:
            return jsonify({"error": "Pitcher name is required"}), 400

        pitcher_hand = normalize_pitcher_hand(data.get("pitcher_hand")) or "both"
        batter = data.get("batter_name")
        batter_stance = normalize_batter_stance(data.get("batter_stance")) or "both"

        try:
            exported_file = pipeline.scrape_pitcher_arsenal_to_csv(
                pitcher=pitcher,
                pitcher_hand=pitcher_hand,
                batter=batter if batter else None,
                batter_stance=batter_stance,
                season=season,
            )
        except Exception as e:
            logger.error(f"Scraper execution error: {e}", exc_info=True)
            return jsonify({"error": str(e)}), 500

        query_name = f"{pitcher} vs {batter} ({season})" if batter else f"{pitcher} ({season})"

    elif search_mode == "batter":
        batter = data.get("batter_name")
        if not batter:
            return jsonify({"error": "Batter name is required"}), 400

        batter_stance = normalize_batter_stance(data.get("batter_stance")) or "both"
        pitcher = data.get("pitcher_name")
        pitcher_hand = normalize_pitcher_hand(data.get("pitcher_hand")) or "both"

        try:
            exported_file = pipeline.scrape_batter_pitches_to_csv(
                batter=batter,
                batter_stance=batter_stance,
                pitcher=pitcher if pitcher else None,
                pitcher_hand=pitcher_hand,
                season=season,
            )
        except Exception as e:
            logger.error(f"Scraper execution error: {e}", exc_info=True)
            return jsonify({"error": str(e)}), 500

        query_name = f"{batter} vs {pitcher} ({season})" if pitcher else f"{batter} ({season})"

    else:
        return jsonify({"error": f"Invalid search mode: {search_mode}"}), 400

    # Read generated CSV data to return directly
    csv_rows: List[Dict[str, str]] = []
    columns: List[str] = []
    if exported_file.exists():
        with open(exported_file, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            columns = reader.fieldnames or []
            csv_rows = list(reader)

    entry = {
        "filename": exported_file.name,
        "query_name": query_name,
        "display_name": query_name,
        "search_mode": search_mode,
        "season": season,
        "timestamp": exported_file.stat().st_mtime if exported_file.exists() else 0,
        "rows_count": len(csv_rows),
    }

    # Prepend to session storage (avoid duplicates)
    recent_searches_session[:] = [
        item for item in recent_searches_session if item["filename"] != exported_file.name
    ]
    recent_searches_session.insert(0, entry)

    return jsonify({
        "success": True,
        "filename": exported_file.name,
        "query_name": query_name,
        "search_mode": search_mode,
        "season": season,
        "columns": columns,
        "rows": csv_rows,
        "total_rows": len(csv_rows),
    })


@api_bp.route("/recent", methods=["GET"])
def get_recent_searches():
    """List recent searches from session and output directory."""
    output_dir = _get_output_dir()
    existing_files = {f.name: f for f in output_dir.glob("*.csv")}

    # Clean session memory for deleted files
    active_session = [
        item for item in recent_searches_session if item["filename"] in existing_files
    ]

    # Check for any CSV files in output folder not yet in session
    session_filenames = {item["filename"] for item in active_session}
    for fname, fpath in existing_files.items():
        if fname not in session_filenames:
            try:
                with open(fpath, mode="r", encoding="utf-8") as f:
                    r = csv.reader(f)
                    next(r, None)  # header
                    count = sum(1 for _ in r)
            except Exception:
                count = 0

            active_session.append({
                "filename": fname,
                "query_name": _format_display_name_from_filename(fname),
                "display_name": _format_display_name_from_filename(fname),
                "search_mode": "pitcher",
                "season": "",
                "timestamp": fpath.stat().st_mtime,
                "rows_count": count,
            })

    # Sort descending by timestamp
    active_session.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
    return jsonify({"recent": active_session})


@api_bp.route("/csv-data", methods=["GET"])
def get_csv_data():
    """Retrieve and parse CSV data for a specific output file."""
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
        with open(csv_file, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            columns = reader.fieldnames or []
            rows = list(reader)

        display_name = _format_display_name_from_filename(filename)
        # Check if we have richer name from session
        for item in recent_searches_session:
            if item["filename"] == filename:
                display_name = item.get("query_name", display_name)
                break

        return jsonify({
            "filename": filename,
            "display_name": display_name,
            "columns": columns,
            "rows": rows,
            "total_rows": len(rows),
        })
    except Exception as e:
        logger.error(f"Error reading CSV '{filename}': {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@api_bp.route("/clear-output", methods=["POST"])
def clear_output():
    """Clear all files from the output directory and wipe session history."""
    output_dir = _get_output_dir()
    count = clear_output_directory(output_dir)
    recent_searches_session.clear()
    logger.info(f"Cleared {count} files from '{output_dir}'.")
    return jsonify({"success": True, "cleared_count": count})
