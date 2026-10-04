"""Command Line Interface (CLI) and interactive console for Baseball Savant scraper."""

import argparse
import csv
import logging
import sys
from pathlib import Path
from typing import Optional

from scraper.config import DEFAULT_SEASON, normalize_batter_stance, normalize_pitcher_hand
from scraper.console import ConsoleInputHandler
from scraper.pipeline import ScraperPipeline
from scraper.utils import clear_output_directory

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("savant_cli")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Modular scraper for Baseball Savant (Statcast) data.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    # Pitcher / Batter Statcast arguments
    parser.add_argument(
        "--mode",
        "--search-type",
        dest="search_mode",
        choices=["pitcher", "batter"],
        default=None,
        help="Search mode: 'pitcher' or 'batter' (default prompts interactively)",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Force interactive console input mode for pitcher/batter queries",
    )
    parser.add_argument(
        "--pitcher",
        type=str,
        default=None,
        help="Pitcher name (e.g. 'Tarik Skubal') or MLB ID",
    )
    parser.add_argument(
        "--pitcher-hand",
        type=str,
        default=None,
        help="Pitcher throwing hand: 'L', 'R', or 'both'",
    )
    parser.add_argument(
        "--batter",
        type=str,
        default=None,
        help="Batter name (e.g. 'Matt Olson') or MLB ID for head-to-head matchup",
    )
    parser.add_argument(
        "--batter-stance",
        type=str,
        default=None,
        help="Batter stance: 'left', 'right', or 'both'",
    )

    # Legacy / Team scraper arguments
    parser.add_argument(
        "--team",
        default=None,
        help="MLB Team abbreviation (e.g. 'LAD', 'NYY') or team ID (e.g. 119)",
    )
    parser.add_argument(
        "--season",
        type=int,
        default=DEFAULT_SEASON,
        help="MLB season year to scrape (default: 2026)",
    )
    parser.add_argument(
        "--metrics",
        default="BA",
        help="Comma-separated list of metrics to extract for team scraping",
    )
    parser.add_argument(
        "--sort-by",
        default="BA",
        help="Metric or column to sort the team output by",
    )
    parser.add_argument(
        "--sort-order",
        choices=["desc", "asc"],
        default="desc",
        help="Sort direction for team output: descending or ascending",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Destination path for the exported CSV file",
    )
    parser.add_argument(
        "--include-totals",
        action="store_true",
        help="Include team and league aggregate summary rows in team output",
    )
    parser.add_argument(
        "--raw-headers",
        action="store_true",
        help="Use raw table header abbreviations instead of friendly names for team output",
    )
    parser.add_argument(
        "--clear-output",
        "--clean",
        action="store_true",
        help="Clear all files from the output folder and exit",
    )
    parser.add_argument(
        "--web",
        action="store_true",
        help="Launch the interactive modular local web interface",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5000,
        help="Port to run the local web server on (default: 5000)",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not automatically open default web browser when launching web interface",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose debug logging",
    )
    return parser.parse_args()


def display_csv_preview(csv_path: Path):
    """Print formatted preview table of CSV to terminal with dynamic column widths."""
    if not csv_path.exists():
        return

    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.reader(f)
        headers = next(reader, None)
        if not headers:
            print("CSV file is empty.")
            return
        rows = list(reader)

    # Calculate column widths
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, val in enumerate(row):
            if i < len(col_widths):
                col_widths[i] = max(col_widths[i], len(str(val)))

    sep_len = max(sum(col_widths) + 3 * (len(headers) - 1), 55)

    print("\n" + "=" * sep_len)
    print(f"📊 CSV PREVIEW: {csv_path.name}")
    print("=" * sep_len)

    header_str = " | ".join(
        f"{h:<{col_widths[i]}}" if i == 0 else f"{h:>{col_widths[i]}}"
        for i, h in enumerate(headers)
    )
    print(header_str)
    print("-" * len(header_str))

    for row in rows:
        print(
            " | ".join(
                f"{col:<{col_widths[i]}}" if i == 0 else f"{col:>{col_widths[i]}}"
                for i, col in enumerate(row)
            )
        )
    print("=" * sep_len)
    print(f"Total rows exported: {len(rows)}\n")


def run_pitch_scraper(args, pipeline: ScraperPipeline, inputs: Optional[dict] = None):
    """Run Statcast pitch scraper either via interactive console or CLI arguments."""
    if inputs is not None:
        pitcher = inputs["pitcher_name"]
        pitcher_hand = inputs["pitcher_hand"]
        batter = inputs.get("batter_name")
        batter_stance = inputs.get("batter_stance", "both")
        season = inputs.get("season", DEFAULT_SEASON)
    else:
        is_interactive = args.interactive or (args.pitcher is None and args.team is None and args.batter is None)

        if is_interactive:
            handler = ConsoleInputHandler(search_service=pipeline.player_search)
            inputs = handler.collect_pitcher_search_inputs()

            pitcher = inputs["pitcher_name"]
            pitcher_hand = inputs["pitcher_hand"]
            batter = inputs["batter_name"]
            batter_stance = inputs["batter_stance"]
            season = inputs["season"]
        else:
            pitcher = args.pitcher
            if not pitcher:
                print("❌ Error: Pitcher name is required via --pitcher. Exiting.")
                sys.exit(1)

            norm_hand = normalize_pitcher_hand(args.pitcher_hand)
            if not norm_hand:
                print("❌ Error: Valid pitcher throwing hand is required (--pitcher-hand 'L', 'R', or 'both').")
                sys.exit(1)
            pitcher_hand = norm_hand

            batter = args.batter
            if batter:
                norm_stance = normalize_batter_stance(args.batter_stance)
                if not norm_stance:
                    print("❌ Error: Batter stance is required when --batter is specified (--batter-stance 'left', 'right', or 'both').")
                    sys.exit(1)
                batter_stance = norm_stance
            else:
                batter_stance = normalize_batter_stance(args.batter_stance) or "both"

            season = args.season or DEFAULT_SEASON

    output_path = args.output
    if batter:
        try:
            matchup_res = pipeline.scrape_head_to_head_to_csv(
                mode="pitcher",
                pitcher=pitcher,
                pitcher_hand=pitcher_hand,
                batter=batter,
                batter_stance=batter_stance,
                season=season,
                output_path=output_path,
            )
            labels = [
                f"{matchup_res['player1']['name']} (Individual Pitch Arsenal)",
                f"{matchup_res['player2']['name']} (Individual Pitches Faced)",
                f"{matchup_res['matchup']['name']} (Head-to-Head)",
            ]
            for file_path, label in zip(matchup_res["files_in_order"], labels):
                print(f"\n✅ Scrape succeeded ({label})! Saved to: {file_path}")
                display_csv_preview(file_path)
        except Exception as e:
            logger.error(f"Scraper execution failed: {e}", exc_info=args.verbose)
            sys.exit(1)
    else:
        try:
            exported_file = pipeline.scrape_pitcher_arsenal_to_csv(
                pitcher=pitcher,
                pitcher_hand=pitcher_hand,
                batter=None,
                batter_stance=batter_stance,
                season=season,
                output_path=output_path,
            )
            print(f"\n✅ Scrape succeeded! Saved to: {exported_file}")
            display_csv_preview(exported_file)
        except Exception as e:
            logger.error(f"Scraper execution failed: {e}", exc_info=args.verbose)
            sys.exit(1)


def run_batter_scraper(args, pipeline: ScraperPipeline, inputs: Optional[dict] = None):
    """Run Statcast batter scraper either via interactive console or CLI arguments."""
    if inputs is not None:
        batter = inputs["batter_name"]
        batter_stance = inputs["batter_stance"]
        pitcher = inputs.get("pitcher_name")
        pitcher_hand = inputs.get("pitcher_hand", "both")
        season = inputs.get("season", DEFAULT_SEASON)
    else:
        is_interactive = args.interactive or (args.batter is None and args.pitcher is None and args.team is None)

        if is_interactive:
            handler = ConsoleInputHandler(search_service=pipeline.player_search)
            inputs = handler.collect_batter_search_inputs()

            batter = inputs["batter_name"]
            batter_stance = inputs["batter_stance"]
            pitcher = inputs["pitcher_name"]
            pitcher_hand = inputs["pitcher_hand"]
            season = inputs["season"]
        else:
            batter = args.batter
            if not batter:
                print("❌ Error: Batter name is required via --batter. Exiting.")
                sys.exit(1)

            norm_stance = normalize_batter_stance(args.batter_stance)
            if not norm_stance:
                print("❌ Error: Valid batter stance is required (--batter-stance 'left', 'right', or 'both').")
                sys.exit(1)
            batter_stance = norm_stance

            pitcher = args.pitcher
            if pitcher:
                norm_hand = normalize_pitcher_hand(args.pitcher_hand)
                if not norm_hand:
                    print("❌ Error: Pitcher throwing hand is required when --pitcher is specified (--pitcher-hand 'L', 'R', or 'both').")
                    sys.exit(1)
                pitcher_hand = norm_hand
            else:
                pitcher_hand = normalize_pitcher_hand(args.pitcher_hand) or "both"

            season = args.season or DEFAULT_SEASON

    output_path = args.output
    if pitcher:
        try:
            matchup_res = pipeline.scrape_head_to_head_to_csv(
                mode="batter",
                pitcher=pitcher,
                pitcher_hand=pitcher_hand,
                batter=batter,
                batter_stance=batter_stance,
                season=season,
                output_path=output_path,
            )
            labels = [
                f"{matchup_res['player1']['name']} (Individual Pitches Faced)",
                f"{matchup_res['player2']['name']} (Individual Pitch Arsenal)",
                f"{matchup_res['matchup']['name']} (Head-to-Head)",
            ]
            for file_path, label in zip(matchup_res["files_in_order"], labels):
                print(f"\n✅ Scrape succeeded ({label})! Saved to: {file_path}")
                display_csv_preview(file_path)
        except Exception as e:
            logger.error(f"Scraper execution failed: {e}", exc_info=args.verbose)
            sys.exit(1)
    else:
        try:
            exported_file = pipeline.scrape_batter_pitches_to_csv(
                batter=batter,
                batter_stance=batter_stance,
                pitcher=None,
                pitcher_hand=pitcher_hand,
                season=season,
                output_path=output_path,
            )
            print(f"\n✅ Scrape succeeded! Saved to: {exported_file}")
            display_csv_preview(exported_file)
        except Exception as e:
            logger.error(f"Scraper execution failed: {e}", exc_info=args.verbose)
            sys.exit(1)



def run_team_scraper(args, pipeline: ScraperPipeline):
    """Run team hitting scraper."""
    metrics_list = [m.strip() for m in args.metrics.split(",") if m.strip()]
    sort_descending = args.sort_order == "desc"
    use_friendly_headers = not args.raw_headers
    output_path = args.output or "output/dodgers_2026_batting_averages.csv"

    print("=" * 60)
    print("⚾ Baseball Savant Team Data Scraper")
    print(f"Team: {args.team} | Season: {args.season}")
    print(f"Metrics: {metrics_list} | Sort by: {args.sort_by} ({args.sort_order})")
    print(f"Output File: {output_path}")
    print("=" * 60)

    try:
        exported_file = pipeline.scrape_team_hitting_to_csv(
            team=args.team,
            season=args.season,
            metrics=metrics_list,
            sort_by=args.sort_by,
            sort_descending=sort_descending,
            exclude_aggregates=not args.include_totals,
            output_path=output_path,
            use_friendly_headers=use_friendly_headers,
        )
        print(f"\n✅ Scrape succeeded! Saved to: {exported_file}")
        display_csv_preview(exported_file)
    except Exception as e:
        logger.error(f"Scraper execution failed: {e}", exc_info=args.verbose)
        sys.exit(1)


def main():
    args = parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.clear_output:
        count = clear_output_directory("output")
        if count == 0:
            print("ℹ️ Output folder ('output/') is already empty.")
        else:
            print(f"🗑️ Successfully cleared {count} file(s) from 'output/'.")
        return

    if args.web:
        from web.app import run_server
        run_server(port=args.port, open_browser=not args.no_browser)
        return

    pipeline = ScraperPipeline()

    if args.team is not None:
        run_team_scraper(args, pipeline)
    elif args.pitcher and args.batter and not args.interactive:
        if args.search_mode == "batter":
            run_batter_scraper(args, pipeline)
        else:
            run_pitch_scraper(args, pipeline)
    elif args.search_mode == "batter" or (args.batter and not args.pitcher and not args.interactive):
        run_batter_scraper(args, pipeline)
    elif args.search_mode == "pitcher" or (args.pitcher and not args.batter and not args.interactive):
        run_pitch_scraper(args, pipeline)
    else:
        # Top-level interactive flow: prompt user to choose between Pitcher and Batter Search
        handler = ConsoleInputHandler(search_service=pipeline.player_search)
        inputs = handler.collect_all_inputs(search_mode=args.search_mode)
        if inputs["search_mode"] == "batter":
            run_batter_scraper(args, pipeline, inputs=inputs)
        else:
            run_pitch_scraper(args, pipeline, inputs=inputs)


if __name__ == "__main__":
    main()
