"""Flask application factory and server runner for Baseball Savant web interface."""

import atexit
import logging
import os
import signal
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Optional

from flask import Flask

from scraper.pipeline import ScraperPipeline
from scraper.player_search import PlayerSearchService
from scraper.utils import clear_output_directory
from web.routes.api import api_bp
from web.routes.views import views_bp

logger = logging.getLogger(__name__)


def create_app(
    output_dir: str = "output",
    scraper_pipeline: Optional[ScraperPipeline] = None,
    player_search_service: Optional[PlayerSearchService] = None,
) -> Flask:
    """Create and configure the Flask application instance."""
    template_folder = str(Path(__file__).parent / "templates")
    static_folder = str(Path(__file__).parent / "static")

    app = Flask(
        __name__,
        template_folder=template_folder,
        static_folder=static_folder,
        static_url_path="/static",
    )

    app.config["OUTPUT_DIR"] = output_dir
    app.config["SCRAPER_PIPELINE"] = scraper_pipeline or ScraperPipeline()
    app.config["PLAYER_SEARCH_SERVICE"] = player_search_service or PlayerSearchService()

    # Register blueprints
    app.register_blueprint(views_bp)
    app.register_blueprint(api_bp)

    return app


def register_cleanup_handlers(output_dir: str = "output"):
    """Register atexit and POSIX signal handlers to clear outputs upon server exit."""
    cleaned = False

    def do_cleanup():
        nonlocal cleaned
        if not cleaned:
            cleaned = True
            logger.info("Server exiting. Clearing all generated outputs...")
            count = clear_output_directory(output_dir)
            logger.info(f"Cleanup complete. Deleted {count} generated files.")

    atexit.register(do_cleanup)

    def signal_handler(signum, frame):
        do_cleanup()
        sys.exit(0)

    try:
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    except (ValueError, AttributeError):
        # In non-main threads or specific environments, signal assignment may be restricted
        pass


def run_server(
    host: str = "127.0.0.1",
    port: int = 5000,
    open_browser: bool = True,
    output_dir: str = "output",
):
    """Start local web server and open browser."""
    register_cleanup_handlers(output_dir=output_dir)
    app = create_app(output_dir=output_dir)

    url = f"http://{host}:{port}"
    print("\n" + "=" * 65)
    print("⚾ Pitch Perfect Web Interface")
    print(f"Server running locally at: {url}")
    print("Press Ctrl+C to stop the server (outputs will be automatically cleared).")
    print("=" * 65 + "\n")

    if open_browser:
        def _open():
            time.sleep(0.8)
            try:
                webbrowser.open(url)
            except Exception as e:
                logger.warning(f"Could not open browser automatically: {e}")

        threading.Thread(target=_open, daemon=True).start()

    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    run_server()
