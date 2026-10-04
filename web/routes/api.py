"""REST API endpoints for the Baseball Savant web interface."""

import csv
import io
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import zipfile
from flask import Blueprint, current_app, jsonify, request, send_file

from scraper.config import DEFAULT_SEASON, normalize_batter_stance, normalize_count, normalize_pitcher_hand
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

            p1_payload = {
                **p1_data,
                "name": matchup_res["player1"]["name"],
                "role": "Pitcher",
                "display_name": f"{matchup_res['player1']['name']} (Pitcher Arsenal)",
            }
            p2_payload = {
                **p2_data,
                "name": matchup_res["player2"]["name"],
                "role": "Batter",
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
            }
            recent_searches_session[:] = [
                item for item in recent_searches_session if item["filename"] != h2h_file.name
            ]
            recent_searches_session.insert(0, entry)

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
            })
        else:
            # Single pitcher search
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
            query_name = f"{pitcher}{count_label} ({season})"

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

            p1_payload = {
                **p1_data,
                "name": matchup_res["player1"]["name"],
                "role": "Batter",
                "display_name": f"{matchup_res['player1']['name']} (Pitches Faced)",
            }
            p2_payload = {
                **p2_data,
                "name": matchup_res["player2"]["name"],
                "role": "Pitcher",
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
            }
            recent_searches_session[:] = [
                item for item in recent_searches_session if item["filename"] != h2h_file.name
            ]
            recent_searches_session.insert(0, entry)

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
            })
        else:
            # Single batter search
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
            query_name = f"{batter}{count_label} ({season})"

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
    }

    # Prepend to session storage (avoid duplicates)
    recent_searches_session[:] = [
        item for item in recent_searches_session if item["filename"] != exported_file.name
    ]
    recent_searches_session.insert(0, entry)

    return jsonify({
        "success": True,
        "is_matchup": False,
        "filename": exported_file.name,
        "query_name": query_name,
        "display_name": query_name,
        "search_mode": search_mode,
        "season": season,
        "count": count,
        "columns": csv_info["columns"],
        "rows": csv_info["rows"],
        "total_rows": csv_info["total_rows"],
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

