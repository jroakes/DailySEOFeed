"""Database models for the feed generator service."""

from datetime import datetime, timezone
from playhouse.mysql_ext import JSONField
from peewee import (
    Model,
    CharField,
    IntegerField,
    FloatField,
    DateTimeField,
    TextField,
    MySQLDatabase,
)
from server import config

import logging

logger = logging.getLogger(__name__)


def get_utc_now():
    """Helper function to get current UTC time"""
    return datetime.now(timezone.utc)


# Environment-specific table names
ENV_PREFIX = "dev_" if config.STAGE == "DEV" else ""

# Initialize database connection
try:
    db = MySQLDatabase(
        config.DATABASE_NAME,
        user=config.DATABASE_USER,
        password=config.DATABASE_PASSWORD,
        host=config.DATABASE_HOST,
        port=int(config.DATABASE_PORT),
        ssl={"ssl_mode": config.DATABASE_SSL_MODE},
        connect_timeout=30,
        read_timeout=30,
        write_timeout=30,
    )
    db.connect()
    logger.info(f"Database connected successfully (Environment: {config.STAGE})")
except Exception as e:
    logger.error(f"Database connection failed: {e}")
    raise


class BaseModel(Model):
    class Meta:
        database = db


class Post(BaseModel):
    class Meta:
        table_name = f"{ENV_PREFIX}posts"

    uri = CharField(unique=True)
    cid = CharField()
    author_did = CharField()
    author_handle = CharField()
    text = TextField()
    engagement_score = FloatField(default=0.0)
    likes_count = IntegerField(default=0)
    reposts_count = IntegerField(default=0)
    replies_count = IntegerField(default=0)
    indexed_at = DateTimeField(default=get_utc_now)

    # Store arrays directly as JSON
    engaged_authors = JSONField(null=True, default=list)
    interaction_timestamps = JSONField(null=True, default=list)

    def save(self, *args, **kwargs):
        if self.indexed_at and self.indexed_at.tzinfo is None:
            self.indexed_at = self.indexed_at.replace(tzinfo=timezone.utc)

        # Ensure we have lists even if None
        if self.engaged_authors is None:
            self.engaged_authors = []
        if self.interaction_timestamps is None:
            self.interaction_timestamps = []

        return super().save(*args, **kwargs)


class SubscriptionState(BaseModel):
    class Meta:
        table_name = f"{ENV_PREFIX}subscription_state"

    service = CharField(unique=True)
    cursor = IntegerField(null=True, default=None)


def get_table_names():
    """Get the current environment's table names for logging/debugging"""
    return {
        "posts": Post._meta.table_name,
        "subscription_state": SubscriptionState._meta.table_name,
    }


def initialize_database(rebuild=False):
    """Initialize the database, optionally rebuilding it."""
    table_names = get_table_names()
    logger.info(
        f"Initializing database tables for environment {config.STAGE}: {table_names}"
    )

    with db:
        if rebuild:
            logger.warning(f"Rebuilding tables: {table_names}")
            db.drop_tables([Post, SubscriptionState])
        db.create_tables([Post, SubscriptionState])

        logger.info("Database initialization complete")
