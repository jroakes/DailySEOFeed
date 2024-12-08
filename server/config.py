# server/config.py
"""Confiuration for the feed generator service."""

import os
from dotenv import load_dotenv

load_dotenv()

SERVICE_DID = os.environ.get("SERVICE_DID", None)
FEEDGEN_HOSTNAME = os.environ.get("FEEDGEN_HOSTNAME", None)

if FEEDGEN_HOSTNAME is None:
    raise RuntimeError('You should set "FEEDGEN_HOSTNAME" environment variable first.')

if SERVICE_DID is None:
    SERVICE_DID = f"did:web:{FEEDGEN_HOSTNAME}"

DAILY_SEO_FEED_URI = os.environ.get("DAILY_SEO_FEED_URI")
if DAILY_SEO_FEED_URI is None:
    raise RuntimeError(
        "Publish your feed first (run publish_feed.py) to obtain Feed URI. "
        'Set this URI to "DAILY_SEO_FEED_URI" environment variable.'
    )

# Database configuration
DATABASE_HOST = os.environ.get("DATABASE_HOST")
DATABASE_PORT = os.environ.get("DATABASE_PORT")
DATABASE_USER = os.environ.get("DATABASE_USER")
DATABASE_PASSWORD = os.environ.get("DATABASE_PASSWORD")
DATABASE_NAME = os.environ.get("DATABASE_NAME")
DATABASE_SSL_MODE = os.environ.get("DATABASE_SSL_MODE", "REQUIRED")

# Hosting
STAGE = os.environ.get("STAGE", "DEV")
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = os.environ.get("PORT", 8080)


# Core configuration settings
POST_LIFETIME_HOURS = int(os.environ.get("POST_LIFETIME_HOURS", 24))
CURSOR_EOF = "eof"

# Ranking configuration
rank_config = {
    # Engagement weights
    'WEIGHT_LIKES': float(os.environ.get("WEIGHT_LIKES", 2.0)),
    'WEIGHT_REPOSTS': float(os.environ.get("WEIGHT_REPOSTS", 3.0)),
    'WEIGHT_COMMENTS': float(os.environ.get("WEIGHT_COMMENTS", 1.0)),
    
    # Score component weights
    'SCORE_WEIGHTS': {
        'BASE_ENGAGEMENT': float(os.environ.get("BASE_ENGAGEMENT", 0.4)),
        'QUORUM': float(os.environ.get("QUORUM", 0.4)),
        'VELOCITY': float(os.environ.get("VELOCITY", 0.3))
    },
    
    # Time decay parameters
    'DECAY_MIDPOINT': int(os.environ.get("DECAY_MIDPOINT", 12)),  # hours
    'DECAY_RATE': int(os.environ.get("DECAY_RATE", 4)),

    # Velocity calculation parameters
    'RECENT_INTERACTION_WINDOW': int(os.environ.get("RECENT_INTERACTION_WINDOW", 4)),  # hours
    
    # Minimum thresholds
    'MIN_ENGAGEMENT_SCORE': float(os.environ.get("MIN_ENGAGEMENT_SCORE", 0.01)),
    'MIN_AUTHOR_ENGAGEMENT': int(os.environ.get("MIN_AUTHOR_ENGAGEMENT", 2)) 
}
