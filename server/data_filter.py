"""Data filtering and engagement tracking for the feed generator."""

from datetime import timedelta, timezone
import threading
from typing import Optional
from atproto import Client, AtUri
from server.database import db, Post, get_utc_now
from server import config
from server.authors import author_manager
import logging

logger = logging.getLogger(__name__)
client = Client()


class AuthorEngagementTracker:
    """Tracks engagement metrics from seedlist users."""

    def __init__(self):
        """Initialize the engagement tracker with a lock."""
        self._lock = threading.Lock()

    def update_engagement(
        self, uri: str, engagement_type: str, author_did: str = None
    ) -> None:
        """
        Update engagement metrics for a post.

        Args:
            uri: Post URI to update
            engagement_type: Type of engagement ("like", "repost", or "reply")
            author_did: The DID of the engaging author
        """
        if not uri or not engagement_type:
            logger.error("Invalid parameters for update_engagement")
            return

        try:
            with db.atomic():
                # Get post with FOR UPDATE lock to handle concurrent updates
                post = Post.select().where(Post.uri == uri).for_update().first()

                if not post:
                    # Post doesn't exist - fetch and create in one transaction
                    post_data = self._fetch_post_content(uri)
                    if not post_data:
                        return

                    post = Post.create(
                        uri=post_data["uri"],
                        cid=post_data["cid"],
                        author_did=post_data["author_did"],
                        author_handle=post_data["author_handle"],
                        text=post_data["text"],
                        indexed_at=get_utc_now(),
                        engagement_score=0.0,
                        likes_count=0,
                        reposts_count=0,
                        replies_count=0,
                        engaged_authors=[],
                        interaction_timestamps=[],
                    )

                # Update all engagement fields in a single update query
                update_data = {}

                # Update engagement count
                if engagement_type == "like":
                    update_data["likes_count"] = Post.likes_count + 1
                elif engagement_type == "repost":
                    update_data["reposts_count"] = Post.reposts_count + 1
                elif engagement_type == "reply":
                    update_data["replies_count"] = Post.replies_count + 1

                # Update engagement tracking with UTC timestamp
                if author_did and author_did not in post.engaged_authors:
                    update_data["engaged_authors"] = post.engaged_authors + [author_did]

                    # Store timestamp as ISO format string for JSON serialization
                    current_time = get_utc_now().isoformat()
                    update_data["interaction_timestamps"] = (
                        post.interaction_timestamps + [current_time]
                    )

                if update_data:
                    Post.update(**update_data).where(Post.id == post.id).execute()

        except Exception as e:
            logger.error(f"Error in update_engagement for {uri}: {e}")

    def clean_old_posts(self) -> None:
        """Remove posts older than POST_LIFETIME_HOURS."""
        try:
            cutoff = get_utc_now() - timedelta(hours=config.POST_LIFETIME_HOURS)

            with db.atomic():
                Post.delete().where(Post.indexed_at < cutoff).execute()

        except Exception as e:
            logger.error(f"Error cleaning old posts: {e}")

    def _fetch_post_content(self, uri: str) -> Optional[dict]:
        """
        Fetch post content from the network.

        Args:
            uri: Post URI to fetch

        Returns:
            Dictionary containing post data or None if fetch fails
        """
        for attempt in range(3):  # Add retry logic for network operations
            try:
                at_uri = AtUri.from_str(uri)
                response = client.com.atproto.repo.get_record(
                    {
                        "repo": at_uri.hostname,
                        "collection": at_uri.collection,
                        "rkey": at_uri.rkey,
                    }
                )

                return {
                    "uri": uri,
                    "cid": response.cid,
                    "author_did": at_uri.hostname,
                    "author_handle": author_manager.resolve_did_to_handle(
                        at_uri.hostname
                    ),
                    "text": getattr(response.value, "text", ""),
                }
            except Exception as e:
                if attempt == 2:  # Last attempt
                    logger.error(f"Error fetching post content for {uri}: {e}")
                    return None
                logger.warning(f"Retry {attempt + 1} for {uri}: {e}")


# Initialize the global tracker instance
tracker = AuthorEngagementTracker()
