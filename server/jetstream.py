"""WebSocket client implementation for the Bluesky Jetstream API."""

import websocket
import json
import logging
import socket
import time
from typing import Optional, List, Callable, Dict, Any

logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

JETSTREAM_HOSTS = {
    "us-east": ["jetstream1.us-east.bsky.network", "jetstream2.us-east.bsky.network"],
    "us-west": ["jetstream1.us-west.bsky.network", "jetstream2.us-west.bsky.network"],
}


def measure_latency(host: str) -> float:
    """Measure the latency to a host using TCP connection time."""
    try:
        start_time = time.time()
        sock = socket.create_connection((host, 443), timeout=5)
        latency = time.time() - start_time
        sock.close()
        return latency
    except Exception as e:
        logger.warning(f"Failed to measure latency for {host}: {e}")
        return float("inf")


def select_optimal_host() -> str:
    """Select the Jetstream host with the lowest latency."""
    best_host = "jetstream2.us-east.bsky.network"  # Default fallback
    best_latency = float("inf")

    for region, hosts in JETSTREAM_HOSTS.items():
        for host in hosts:
            latency = measure_latency(host)
            if latency < best_latency:
                best_latency = latency
                best_host = host

    if best_latency == float("inf"):
        logger.warning("Could not measure latency to any hosts, using default")
    else:
        logger.info(f"Selected {best_host} with latency of {best_latency*1000:.2f}ms")

    return best_host


class JetstreamClient:
    """Client for connecting to Bluesky's Jetstream API."""

    def __init__(
        self,
        wanted_collections: Optional[List[str]] = None,
        wanted_dids: Optional[List[str]] = None,
        cursor: Optional[int] = None,
        on_message_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        websocket_url: Optional[str] = None,
    ):
        """Initialize the Jetstream client."""
        self.websocket_url = (
            websocket_url
            if websocket_url
            else f"wss://{select_optimal_host()}/subscribe"
        )
        self.wanted_collections = wanted_collections or []
        self.wanted_dids = wanted_dids or []
        self.cursor = cursor
        self.on_message_callback = on_message_callback

        # Connection objects
        self.ws = None
        self.thread = None

    # Add cleanup method
    def __del__(self):
        """Ensure proper cleanup of WebSocket connection."""
        if self.ws:
            try:
                self.ws.close()
            except:
                pass

    def _build_url(self) -> str:
        """Build the websocket URL with query parameters."""
        params = []
        params.extend(f"wantedCollections={col}" for col in self.wanted_collections)
        params.extend(f"wantedDids={did}" for did in self.wanted_dids)
        if self.cursor is not None:
            params.append(f"cursor={self.cursor}")
        return f"{self.websocket_url}{'?' + '&'.join(params) if params else ''}"

    def on_message(self, ws, message):
        """Handle incoming websocket messages."""
        try:
            data = json.loads(message)
            if self.on_message_callback:
                self.on_message_callback(data)
        except Exception as e:
            logger.error(f"Failed to process message: {e}")

    def on_error(self, ws, error):
        """Handle websocket errors."""
        logger.error(f"WebSocket error: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        """Handle websocket connection closure."""
        logger.info(f"Connection closed: {close_status_code} - {close_msg}")

        # Add exponential backoff for reconnection
        for attempt in range(5):  # Limit retry attempts
            wait_time = 2**attempt  # Exponential backoff
            logger.info(f"Reconnecting in {wait_time} seconds...")
            time.sleep(wait_time)
            try:
                self.start()
                return
            except Exception as e:
                logger.error(f"Reconnection attempt {attempt + 1} failed: {e}")
        else:  # This executes if no successful return occurs in the for loop
            logger.critical("All reconnection attempts failed")
            raise ConnectionError("Failed to reconnect after 5 attempts")

    def on_open(self, ws):
        """Handle websocket connection opening."""
        logger.info("Connection established!")

    def start(self):
        """Start the Jetstream client."""
        url = self._build_url()
        logger.info(f"Connecting to: {url}")

        self.ws = websocket.WebSocketApp(
            url,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
            on_open=self.on_open,
        )

        self.ws.run_forever()
