# server/authors.py
"""Authors module for the feed generator service."""

from typing import Set, Dict, Optional
from tqdm.auto import tqdm
from atproto import Client

import logging

logger = logging.getLogger(__name__)


class AuthorManager:

    def __init__(self):
        self._client = Client()
        self._handle_to_did: Dict[str, str] = {}
        self._did_to_handle: Dict[str, str] = {}
        self.author_dids: Set[str] = set()
        self._load_user_list()

    def _normalize_handle(self, handle: str) -> str:
        """Normalize a handle by removing '@' prefix."""
        return handle.strip().lower().lstrip("@")

    def _resolve_handle(self, handle: str) -> Optional[str]:
        """Resolve a handle to a DID, with proper error handling."""
        normalized_handle = self._normalize_handle(handle)
        if normalized_handle in self._handle_to_did:
            return self._handle_to_did[normalized_handle]

        retries = 3
        for attempt in range(retries):
            try:
                result = self._client.resolve_handle(normalized_handle)
                self._handle_to_did[normalized_handle] = result.did
                self._did_to_handle[result.did] = normalized_handle
                return result.did
            except Exception as e:
                if attempt == retries - 1:
                    logger.error(f"Failed to resolve handle {normalized_handle}: {e}")
                    return None
                logger.warning(
                    f"Retry {attempt + 1}/{retries} for handle {normalized_handle}: {e}"
                )

    def _resolve_did_to_handle(self, did: str) -> Optional[str]:
        """Resolve a DID to a handle, with proper error handling."""
        if did in self._did_to_handle:
            return self._did_to_handle[did]

        retries = 3
        for attempt in range(retries):
            try:
                profile = self._client.com.atproto.repo.describe_repo({"repo": did})
                handle = profile.handle
                self._did_to_handle[did] = handle
                self._handle_to_did[handle] = did
                return handle
            except Exception as e:
                if attempt == retries - 1:
                    logger.error(f"Failed to resolve DID {did}: {e}")
                    return None
                logger.warning(f"Retry {attempt + 1}/{retries} for DID {did}: {e}")

    def _load_user_list(self) -> None:
        """Load and resolve handles from user_list.txt."""
        try:
            with open("user_list.txt", "r", encoding="utf-8") as f:
                handles = {
                    self._normalize_handle(line.strip()) for line in f if line.strip()
                }

            new_dids = set()
            for handle in tqdm(handles, desc="Converting author handles"):
                did = self._resolve_handle(handle)
                if did:
                    new_dids.add(did)
                else:
                    logger.warning(f"Could not resolve handle: {handle}")

            if not new_dids:
                logger.warning("No valid DIDs found in user list")

            self.author_dids = new_dids
            logger.info(f"Loaded {len(self.author_dids)} author DIDs")

        except FileNotFoundError:
            logger.warning(
                "user_list.txt not found. Proceeding without author engagement tracking."
            )
            self.author_dids = set()
        except Exception as e:
            logger.error(f"Error loading user list: {e}")
            self.author_dids = set()

    def is_author(self, did: str) -> bool:
        """Check if a DID belongs to an author."""
        return did in self.author_dids

    def resolve_did_to_handle(self, did: str) -> Optional[str]:
        """Public method to resolve DID to handle."""
        return self._resolve_did_to_handle(did)


# Initialize a singleton instance of AuthorManager
author_manager = AuthorManager()
