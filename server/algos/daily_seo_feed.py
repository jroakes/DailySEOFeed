# server/algos/daily_seo_feed.py

"""
Ranking algorithm for SEO expert curated content that prioritizes posts with:
- High engagement from trusted authors
- Recent interaction velocity
- Overall engagement metrics (likes, reposts, replies)
- Time decay to maintain freshness
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

# Feed and cache configuration
URI = config.DAILY_SEO_FEED_URI
CURSOR_EOF = "eof"
CACHE_DURATION = 300  
CACHE_SIZE = 500  
_last_cache_reset = time()

# Scoring configuration
VELOCITY_WINDOWS = [
    ("recent", timedelta(hours=1)),
    ("mid", timedelta(hours=6)),
    ("day", timedelta(hours=24)),
]
VELOCITY_WEIGHTS = [0.5, 0.3, 0.2]
SCORE_WEIGHTS = {
    "base_engagement": 0.4,
    "quorum": 0.6,
    "velocity": 0.3
}
DECAY_MIDPOINT = 12
DECAY_RATE = 4

def validate_min_author_engagement(post: Post) -> bool:
    engaged_authors = len(post.engaged_authors or [])
    return engaged_authors >= config.MIN_AUTHOR_ENGAGEMENT

def calculate_author_quorum_score(post: Post) -> float:
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
    try:
        now = get_utc_now()
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
    try:
        if not validate_min_author_engagement(post):
            return 0.0
    
        engagement_score = (
            post.likes_count * config.WEIGHT_LIKES +
            post.reposts_count * config.WEIGHT_REPOSTS +
            post.replies_count * config.WEIGHT_COMMENTS
        )
        base_score = math.log(max(engagement_score, 1), 10)
        
        quorum_score = calculate_author_quorum_score(post)
        velocity_score = calculate_velocity_score(post)
        
        age_hours = (get_utc_now() - post.indexed_at.replace(tzinfo=timezone.utc)).total_seconds() / 3600
        time_decay = 1 / (1 + math.exp((age_hours - DECAY_MIDPOINT) / DECAY_RATE))
        
        final_score = (
            base_score * SCORE_WEIGHTS["base_engagement"] +
            quorum_score * SCORE_WEIGHTS["quorum"] +
            velocity_score * SCORE_WEIGHTS["velocity"]
        ) * time_decay * config.WEIGHT_RECENCY
        
        return max(final_score, 0.0)
        
    except Exception as e:
        logger.error(f"Error calculating hotness score for {post.uri}: {e}")
        return 0.0

def get_ranked_posts(cursor: Optional[str], limit: int) -> Tuple[List[Post], str]:
    try:
        if not 1 <= limit <= 100:
            raise ValueError("Limit must be between 1 and 100")
            
        cutoff_time = get_utc_now() - timedelta(hours=config.POST_LIFETIME_HOURS)
        query = Post.select().where(Post.indexed_at >= cutoff_time)
        
        if cursor and cursor != CURSOR_EOF:
            try:
                score, post_id = cursor.split("::")
                query = query.where(Post.id < int(post_id))
            except ValueError:
                raise ValueError("Invalid cursor format")
                
        posts = list(query.limit(limit * 2))
        scored_posts = []
        
        for post in posts:
            score = calculate_hotness_score(post)
            if score >= config.MIN_ENGAGEMENT_SCORE:
                post.engagement_score = score
                scored_posts.append(post)
                
        scored_posts.sort(key=lambda x: (-x.engagement_score, -x.id))
        scored_posts = scored_posts[:limit]
        
        next_cursor = (
            f"{scored_posts[-1].engagement_score}::{scored_posts[-1].id}"
            if len(scored_posts) == limit else CURSOR_EOF
        )
        
        return scored_posts, next_cursor
        
    except Exception as e:
        logger.error(f"Error in get_ranked_posts: {e}", exc_info=True)
        return [], CURSOR_EOF

@lru_cache(maxsize=CACHE_SIZE)
def get_posts(cursor: Optional[str], limit: int) -> Tuple[List[Post], str]:
    global _last_cache_reset
    current_time = time()
    
    if current_time - _last_cache_reset > CACHE_DURATION:
        get_posts.cache_clear()
        _last_cache_reset = current_time
        
    return get_ranked_posts(cursor, limit)

def handler(cursor: Optional[str], limit: int) -> Dict[str, Any]:
    posts, next_cursor = get_posts(cursor, limit)
    feed = [{"post": post.uri} for post in posts]
    return {"cursor": next_cursor, "feed": feed}