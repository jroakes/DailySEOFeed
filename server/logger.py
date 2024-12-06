# server/logger.py
"""Loggers for the feed generator service."""

import logging

# Create a logger for the server package
logger = logging.getLogger(__name__)

# Set up basic configuration
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("feed_generator.log")],
)

# Set the level for all loggers in the server package
server_logger = logging.getLogger("server")
server_logger.setLevel(logging.WARNING)  # Default level, can be overridden


# Function to update log levels across all server loggers
def set_log_level(level):
    """Set logging level for all loggers in the server package"""
    server_logger = logging.getLogger("server")
    server_logger.setLevel(level)

    # Also update all child loggers
    for name in logging.root.manager.loggerDict:
        if name.startswith("server."):
            logging.getLogger(name).setLevel(level)
