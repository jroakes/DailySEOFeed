"""
Feed algorithm for generating SEO expert curated content with improved ranking.

This module implements a sophisticated ranking algorithm that considers:
- Author engagement quorum (percentage of trusted authors engaging)
- Engagement velocity (rate of interactions over time)
- Base engagement metrics (likes, reposts, replies)
- Time decay using a sigmoid function

The algorithm prioritizes posts that receive quick engagement from multiple trusted authors
while maintaining relevance through time decay.
"""

from datetime import timedelta, timezone
from typing import Optional, Tuple, List, Dict, Any
from server import config
from datetime import datetime
from server.database import Post, get_utc_now
from server.logger import logger
from server.authors import author_manager
import math
from functools import lru_cache
from time import time

# Feed configuration
URI = config.DAILY_SEO_FEED_URI
CURSOR_EOF = "eof"

# Cache settings
CACHE_DURATION = 300  # 5 minutes in seconds
CACHE_SIZE = 500  # Maximum number of cached responses
_last_cache_reset = time()

# Velocity scoring windows
VELOCITY_WINDOWS = [
    ("recent", timedelta(hours=1)),  # Last hour
    ("mid", timedelta(hours=6)),  # Last 6 hours
    ("day", timedelta(hours=24)),  # Last 24 hours
]

# Scoring weights
VELOCITY_WEIGHTS = [0.5, 0.3, 0.2]  # Weights for recent, mid, day windows
SCORE_WEIGHTS = {"base_engagement": 0.4, "quorum": 0.6, "velocity": 0.3}

# Time decay settings
DECAY_MIDPOINT = 12  # Hours
DECAY_RATE = 4  # Controls how quickly score decays


def calculate_author_quorum_score(post: Post) -> float:
    """
    Calculate the percentage of trusted authors who have engaged with the post.

    Args:
        post: Post object containing engagement data

    Returns:
        float: Score between 0 and 1 representing author engagement percentage
    """
    try:
        total_authors = len(author_manager.author_dids)
        if not total_authors:
            return 0.0

        engaged_count = len(post.engaged_authors or [])
        return engaged_count / total_authors

    except Exception as e:
        logger.error(f"Error calculating quorum score for {post.uri}: {e}")
        return 0.0


def calculate_velocity_score(post: Post) -> float:
    """
    Calculate engagement velocity across multiple time windows.

    Uses three windows (1h, 4h, 24h) with higher weights for recent engagement.
    Normalizes interaction counts by window size.

    Args:
        post: Post object containing interaction timestamps

    Returns:
        float: Weighted velocity score
    """
    try:
        now = get_utc_now()
        # Parse ISO format strings to datetime objects
        timestamps = [
            datetime.fromisoformat(t)
            for t in (post.interaction_timestamps or [])
        ]
        velocity_scores = []

        for _, delta in VELOCITY_WINDOWS:
            cutoff = now - delta
            window_interactions = sum(1 for t in timestamps if t > cutoff)
            hours = delta.total_seconds() / 3600
            velocity = window_interactions / hours if hours else 0
            velocity_scores.append(velocity)

        return sum(v * w for v, w in zip(velocity_scores, VELOCITY_WEIGHTS))

    except Exception as e:
        logger.error(f"Error calculating velocity for {post.uri}: {e}")
        return 0.0


def calculate_hotness_score(post: Post) -> float:
    """
    Calculate the overall post score using multiple weighted factors.

    Combines:
    - Base engagement (weighted likes, reposts, replies)
    - Author quorum (percentage of trusted authors engaged)
    - Engagement velocity (rate of interactions)
    - Time decay (sigmoid function centered at DECAY_MIDPOINT hours)

    Args:
        post: Post object containing all engagement metrics

    Returns:
        float: Final weighted and time-decayed score
    """
    try:
        # Base engagement score
        engagement_score = (post.likes_count * config.WEIGHT_LIKES +
                            post.reposts_count * config.WEIGHT_REPOSTS +
                            post.replies_count * config.WEIGHT_COMMENTS)
        base_score = math.log(max(engagement_score, 1), 10)

        # Component scores
        quorum_score = calculate_author_quorum_score(post)
        velocity_score = calculate_velocity_score(post)

        # Time decay
        age_hours = (get_utc_now() - post.indexed_at.replace(
            tzinfo=timezone.utc)).total_seconds() / 3600
        time_decay = 1 / (1 + math.exp(
            (age_hours - DECAY_MIDPOINT) / DECAY_RATE))

        # Combine scores with weights
        final_score = (base_score * SCORE_WEIGHTS["base_engagement"] +
                       quorum_score * SCORE_WEIGHTS["quorum"] +
                       velocity_score * SCORE_WEIGHTS["velocity"]) * time_decay

        return max(final_score * config.WEIGHT_RECENCY, 0.0)

    except Exception as e:
        logger.error(f"Error calculating hotness score for {post.uri}: {e}")
        return 0.0


def get_ranked_posts(cursor: Optional[str],
                     limit: int) -> Tuple[List[Post], str]:
    """
    Get ranked posts ordered by hotness score.

    Args:
        cursor: Pagination cursor in format "score::id" or None
        limit: Maximum number of posts to return (1-100)

    Returns:
        Tuple[List[Post], str]: Ranked posts and next pagination cursor

    Raises:
        ValueError: If cursor format is invalid or limit is out of range
    """
    try:
        # Validate limit
        if not 1 <= limit <= 100:
            raise ValueError("Limit must be between 1 and 100")

        # Get active posts
        cutoff_time = get_utc_now() - timedelta(
            hours=config.POST_LIFETIME_HOURS)
        query = Post.select().where(Post.indexed_at >= cutoff_time)

        # Handle pagination
        if cursor and cursor != CURSOR_EOF:
            try:
                score, post_id = cursor.split("::")
                query = query.where(Post.id < int(post_id))
            except ValueError:
                raise ValueError("Invalid cursor format")

        # Score and filter posts
        posts = list(query.limit(limit * 2))
        scored_posts = []

        for post in posts:
            score = calculate_hotness_score(post)
            if score >= config.MIN_ENGAGEMENT_SCORE:
                post.engagement_score = score
                scored_posts.append(post)

        scored_posts.sort(key=lambda x: (-x.engagement_score, -x.id))
        scored_posts = scored_posts[:limit]

        # Set pagination cursor
        next_cursor = (
            f"{scored_posts[-1].engagement_score}::{scored_posts[-1].id}"
            if len(scored_posts) == limit else CURSOR_EOF)

        return scored_posts, next_cursor

    except Exception as e:
        logger.error(f"Error in get_ranked_posts: {e}", exc_info=True)
        return [], CURSOR_EOF


@lru_cache(maxsize=CACHE_SIZE)
def get_posts(cursor: Optional[str], limit: int) -> Tuple[List[Post], str]:
    """
    Cached wrapper for get_ranked_posts.

    Caches results for CACHE_DURATION seconds to reduce database load.
    Automatically clears cache when duration expires.

    Args:
        cursor: Pagination cursor
        limit: Maximum posts to return

    Returns:
        Tuple[List[Post], str]: Cached post results and cursor
    """
    global _last_cache_reset
    current_time = time()

    if current_time - _last_cache_reset > CACHE_DURATION:
        get_posts.cache_clear()
        _last_cache_reset = current_time

    return get_ranked_posts(cursor, limit)


def handler(cursor: Optional[str], limit: int) -> Dict[str, Any]:
    """
    Main feed handler that serves feed API requests.

    Args:
        cursor: Optional pagination cursor
        limit: Number of posts to return

    Returns:
        Dict containing feed items and next cursor
    """
    posts, next_cursor = get_posts(cursor, limit)
    feed = [{"post": post.uri} for post in posts]
    return {"cursor": next_cursor, "feed": feed}
