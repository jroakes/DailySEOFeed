# server/app.py
"""A Flask app for the Bluesky Feed Generator."""

from flask import Flask, jsonify, request, send_from_directory, render_template
from server.algos import algos
from server.database import Post
from server import config
from server.algos.daily_seo_feed import PostRanker

import logging

logger = logging.getLogger(__name__)

app = Flask(__name__, static_url_path="/public")

@app.route("/")
def index():
    """Home page route showing ranked posts."""
    try:
        ranker = PostRanker(config)
        posts, _ = ranker.get_posts(cursor=None, limit=20)

        if not posts:
            return render_template(
                "index.html",
                feed_name=config.DAILY_SEO_FEED_URI,
                posts=[],
                message="No posts available yet. Please wait while we gather data."
            )

        return render_template(
            "index.html",
            feed_name=config.DAILY_SEO_FEED_URI,
            posts=posts
        )
    except Exception as e:
        logger.error(f"Error generating index: {str(e)}")
        return render_template(
            "index.html",
            feed_name=config.DAILY_SEO_FEED_URI,
            posts=[],
            message="An error occurred while loading posts."
        )



@app.route("/.well-known/did.json", methods=["GET"])
def did_json():
    """DID document endpoint."""
    if not config.SERVICE_DID.endswith(config.FEEDGEN_HOSTNAME):
        return "", 404

    return jsonify(
        {
            "@context": ["https://www.w3.org/ns/did/v1"],
            "id": config.SERVICE_DID,
            "service": [
                {
                    "id": "#bsky_fg",
                    "type": "BskyFeedGenerator",
                    "serviceEndpoint": f"https://{config.FEEDGEN_HOSTNAME}",
                }
            ],
        }
    )

@app.route("/xrpc/app.bsky.feed.describeFeedGenerator", methods=["GET"])
def describe_feed_generator():
    """Feed generator description endpoint."""
    feeds = [{"uri": uri} for uri in algos.keys()]
    response = {
        "encoding": "application/json",
        "body": {"did": config.SERVICE_DID, "feeds": feeds},
    }
    return jsonify(response)

@app.route("/xrpc/app.bsky.feed.getFeedSkeleton", methods=["GET"])
def get_feed_skeleton():
    """Feed skeleton endpoint."""
    feed = request.args.get("feed", default=None, type=str)
    algo = algos.get(feed)
    if not algo:
        return "Unsupported algorithm", 400

    try:
        cursor = request.args.get("cursor", default=None, type=str)
        limit = request.args.get("limit", default=20, type=int)

        if limit < 1 or limit > 100:
            return "Invalid limit (must be between 1 and 100)", 400

        body = algo(cursor, limit)

    except ValueError as ve:
        logger.error(f"Validation error in getFeedSkeleton: {ve}")
        return "Malformed cursor", 400
    except Exception as e:
        logger.error(f"Error in getFeedSkeleton: {e}")
        return "Internal server error", 500

    return jsonify(body)

@app.route("/public/<path:filename>")
def serve_static(filename):
    """Serve static files."""
    return send_from_directory("public", filename)

@app.route("/health")
def health_check():
    """Health check endpoint."""
    try:
        recent_posts = Post.select().count()
        return jsonify(
            {
                "status": "healthy",
                "posts_count": recent_posts,
            }
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({"status": "unhealthy", "error": str(e)}), 500