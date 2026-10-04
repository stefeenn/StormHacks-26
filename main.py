"""Command Line Interface (CLI) for Baseball Savant modular scraper."""

import argparse
import csv
import logging
import sys
from pathlib import Path

from scraper.pipeline import ScraperPipeline

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
    parser.add_argument(
        "--team",
        default="LAD",
        help="MLB Team abbreviation (e.g. 'LAD', 'NYY') or team ID (e.g. 119)",
    )
    parser.add_argument(
        "--season",
        type=int,
        default=2026,
        help="MLB season year to scrape",
    )
    parser.add_argument(
        "--metrics",
        default="BA",
        help="Comma-separated list of metrics to extract (e.g. 'BA', 'BA,HR,OBP,SLG', 'ExitVelocity')",
    )
    parser.add_argument(
        "--sort-by",
        default="BA",
        help="Metric or column to sort the output by",
    )
    parser.add_argument(
        "--sort-order",
        choices=["desc", "asc"],
        default="desc",
        help="Sort direction: descending (highest first) or ascending",
    )
    parser.add_argument(
        "--output",
        default="output/dodgers_2026_batting_averages.csv",
        help="Destination path for the exported CSV file",
    )
    parser.add_argument(
        "--include-totals",
        action="store_true",
        help="Include team and league aggregate summary rows in the output",
    )
    parser.add_argument(
        "--raw-headers",
        action="store_true",
        help="Use raw table header abbreviations (e.g. 'BA') instead of friendly names ('Batting Average')",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose debug logging",
    )
    return parser.parse_args()


def display_csv_preview(csv_path: Path):
    """Print formatted preview table of CSV to terminal."""
    if not csv_path.exists():
        return

    print("\n" + "=" * 55)
    print(f"📊 CSV PREVIEW: {csv_path.name}")
    print("=" * 55)

    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.reader(f)
        headers = next(reader, None)
        if not headers:
            print("CSV file is empty.")
            return

        header_str = " | ".join(f"{h:<25}" if i == 0 else f"{h:>18}" for i, h in enumerate(headers))
        print(header_str)
        print("-" * len(header_str))

        rows = list(reader)
        for row in rows:
            print(" | ".join(f"{col:<25}" if i == 0 else f"{col:>18}" for i, col in enumerate(row)))

    print("=" * 55)
    print(f"Total rows exported: {len(rows)}\n")


def main():
    args = parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    metrics_list = [m.strip() for m in args.metrics.split(",") if m.strip()]
    sort_descending = args.sort_order == "desc"
    use_friendly_headers = not args.raw_headers

    print("=" * 60)
    print("⚾ Baseball Savant Data Scraper")
    print(f"Team: {args.team} | Season: {args.season}")
    print(f"Metrics: {metrics_list} | Sort by: {args.sort_by} ({args.sort_order})")
    print(f"Output File: {args.output}")
    print("=" * 60)

    pipeline = ScraperPipeline()

    try:
        output_file = pipeline.scrape_team_hitting_to_csv(
            team=args.team,
            season=args.season,
            metrics=metrics_list,
            sort_by=args.sort_by,
            sort_descending=sort_descending,
            exclude_aggregates=not args.include_totals,
            output_path=args.output,
            use_friendly_headers=use_friendly_headers,
        )

        print(f"\n✅ Scrape succeeded! Saved to: {output_file}")
        display_csv_preview(output_file)

    except Exception as e:
        logger.error(f"Scraper execution failed: {e}", exc_info=args.verbose)
        sys.exit(1)


if __name__ == "__main__":
    main()
