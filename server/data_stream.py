# In data_stream.py

from typing import Dict, Any, Set
from server.authors import author_manager
from server.database import SubscriptionState, db
from server.jetstream import JetstreamClient
from server.data_filter import tracker
import logging

logger = logging.getLogger(__name__)

# Define constants at module level for performance
INTERESTED_COLLECTIONS: Set[str] = {
    "app.bsky.feed.like",
    "app.bsky.feed.post",
    "app.bsky.feed.repost",
}


def process_event(event: Dict[str, Any]) -> None:
    """
    Process a single event from the Jetstream service.
    Optimized to minimize dictionary operations and memory allocations.
    """
    try:
        # Early return conditions
        if event.get("kind") != "commit":
            return

        commit = event.get("commit")
        if not commit:
            logger.warning("Received commit event without commit data")
            return

        did = event.get("did")
        if not author_manager.is_author(did):
            logger.warning(f"Received commit event from non-author DID: {did}")
            return

        collection = commit.get("collection")
        if collection not in INTERESTED_COLLECTIONS:
            logger.warning(
                f"Received commit event for uninterested collection: {collection}"
            )
            return

        # Process the commit
        operation = commit.get("operation")
        if operation != "create":  # We only handle creates for now
            logger.warning(
                f"Received commit event with unhandled operation: {operation}"
            )
            return

        record = commit.get("record", {})
        record_type = record.get("$type")
        if record_type != collection:  # Verify record type matches collection
            logger.warning(
                f"Received commit event with mismatched record type: {record_type}"
            )
            return

        # Get the subject URI based on collection type
        subject_uri = None
        if collection == "app.bsky.feed.like":
            subject_uri = record.get("subject", {}).get("uri")
        elif collection == "app.bsky.feed.repost":
            subject_uri = record.get("subject", {}).get("uri")
        elif collection == "app.bsky.feed.post" and "reply" in record:
            subject_uri = record.get("reply", {}).get("parent", {}).get("uri")

        if subject_uri:
            # Update engagement metrics in a single database transaction
            with db.atomic():
                engagement_type = {
                    "app.bsky.feed.like": "like",
                    "app.bsky.feed.repost": "repost",
                    "app.bsky.feed.post": "reply",
                }[collection]

                tracker.update_engagement(subject_uri, engagement_type, author_did=did)

            logger.info(f"Processed {engagement_type} for {subject_uri}")

    except Exception as e:
        logger.error(f"Error processing event: {e}", exc_info=True)


def on_message_handler(event):
    """Handle incoming messages efficiently."""
    logger.info("Received new message")

    # Update cursor if present
    time_us = event.get("time_us")
    if time_us:
        try:
            with db.atomic():
                SubscriptionState.update(cursor=time_us).where(
                    SubscriptionState.service == "jetstream"
                ).execute()
        except Exception as e:
            logger.error(f"Failed to update cursor: {e}")

    # Process the event
    process_event(event)


def run_jetstream():
    """Main run loop for the Jetstream service."""
    try:
        # Get the last cursor position if any
        state = SubscriptionState.get_or_none(SubscriptionState.service == "jetstream")
        cursor = state.cursor if state and state.cursor is not None else None

        # Start the Jetstream client
        client = JetstreamClient(
            wanted_collections=list(INTERESTED_COLLECTIONS),
            wanted_dids=list(author_manager.author_dids),
            cursor=cursor,
            on_message_callback=on_message_handler,
        )

        client.start()

    except Exception as e:
        logger.error(f"Error in jetstream service: {e}")
        raise
