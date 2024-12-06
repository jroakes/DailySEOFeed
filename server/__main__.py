"""Main entry point for the feed generator service."""

import sys
import argparse
import logging
from server.app import app
from server import config
from server.data_stream import run_jetstream
from server.database import initialize_database
from server.logger import set_log_level

logger = logging.getLogger(__name__)


def main():
    """Main entry point."""
    try:
        parser = argparse.ArgumentParser(description="Feed Generator Service")
        parser.add_argument(
            "--rebuild_database",
            action="store_true",
            help="Rebuilds the database",
        )
        parser.add_argument(
            "--app_only", action="store_true", help="Only runs the app/api"
        )
        parser.add_argument(
            "--jetstream_only",
            action="store_true",
            help="Only runs the jetstream processing",
        )
        parser.add_argument("--debug", action="store_true", help="Enable debug mode")
        args = parser.parse_args()

        if args.app_only and args.jetstream_only:
            logger.error("Cannot set both --app_only and --jetstream_only")
            sys.exit(1)

        if args.debug:
            set_log_level(logging.INFO)
            logger.info("Debug mode enabled")

        # Initialize the database
        logger.info("Initializing database...")
        initialize_database(rebuild=args.rebuild_database)

        # Run the app based on mode
        if args.app_only:
            logger.info(f"Starting app only mode on port {config.PORT}...")
            app.run(host=config.HOST, port=config.PORT)
        elif args.jetstream_only:
            logger.info("Starting jetstream only mode...")
            run_jetstream()  # This will block as jetstream.py handles threading
        else:
            logger.info(f"Starting both app and jetstream on port {config.PORT}...")
            # Start jetstream processing

            # Start run_jetstream() in a separate thread
            import threading

            jetstream_thread = threading.Thread(target=run_jetstream, daemon=True)
            jetstream_thread.start()

            # Run the Flask app in the main thread
            app.run(host=config.HOST, port=config.PORT)

    except Exception as e:
        logger.error(f"Critical error in main: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
