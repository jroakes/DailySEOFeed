#!/usr/bin/env python3
# YOU MUST INSTALL ATPROTO SDK
# pip3 install atproto

import os
from atproto import Client, models
from dotenv import load_dotenv

load_dotenv()

# YOUR bluesky handle
# Ex: user.bsky.social
HANDLE: str = os.getenv("BSKY_HANDLE", "user.bsky.social")

# YOUR bluesky password, or preferably an App Password (found in your client settings)
# Ex: abcd-1234-efgh-5678
PASSWORD: str = os.getenv("BSKY_PASSWORD", "abcd-1234-efgh-5678")

# The hostname of the server where feed server will be hosted
# Ex: feed.bsky.dev
HOSTNAME: str = "dailyseo.io"

# A short name for the record that will show in urls
# Lowercase with no spaces.
RECORD_NAME: str = "daily-seo"

# A display name for your feed
DISPLAY_NAME: str = "Daily SEO"

# A description of your feed
DESCRIPTION: str = (
    "Trending SEO content from top industry experts - featuring posts, likes, and shares from the last 48 hours"
)

# Path to avatar image
AVATAR_PATH: str = "server/public/avatar.jpg"

# Service DID (optional)
SERVICE_DID: str = ""

# -------------------------------------
# NO NEED TO TOUCH ANYTHING BELOW HERE
# -------------------------------------


def main():
    client = Client()
    client.login(HANDLE, PASSWORD)

    feed_did = SERVICE_DID
    if not feed_did:
        feed_did = f"did:web:{HOSTNAME}"

    avatar_blob = None
    if AVATAR_PATH:
        with open(AVATAR_PATH, "rb") as f:
            avatar_data = f.read()
            avatar_blob = client.upload_blob(avatar_data).blob

    response = client.com.atproto.repo.put_record(
        models.ComAtprotoRepoPutRecord.Data(
            repo=client.me.did,
            collection=models.ids.AppBskyFeedGenerator,
            rkey=RECORD_NAME,
            record=models.AppBskyFeedGenerator.Record(
                did=feed_did,
                display_name=DISPLAY_NAME,
                description=DESCRIPTION,
                avatar=avatar_blob,
                created_at=client.get_current_time_iso(),
            ),
        )
    )

    print("Successfully published!")
    print('Feed URI (put in "DAILY_SEO_FEED_URI" env var):', response.uri)


if __name__ == "__main__":
    main()
