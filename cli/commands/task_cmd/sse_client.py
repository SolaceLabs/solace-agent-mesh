"""
SSE client using httpx for streaming Server-Sent Events.
"""
import asyncio
import json
import time
from typing import AsyncGenerator, Dict, Any, Optional, Callable
from dataclasses import dataclass

import click
import httpx


@dataclass
class SSEEvent:
    """Represents a single SSE event."""

    event_type: str
    data: Dict[str, Any]
    raw_data: str
    timestamp: float


class SSEClient:
    """
    Client for consuming Server-Sent Events using httpx.
    """

    def __init__(
        self,
        base_url: str,
        timeout: int = 300,
        token: Optional[str] = None,
        debug: bool = False,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.token = token
        self.debug = debug

    def _debug(self, msg: str):
        """Print debug message if debug mode is enabled."""
        if self.debug:
            click.echo(click.style(f"[DEBUG] {msg}", fg="yellow"), err=True)

    async def subscribe(
        self,
        task_id: str,
    ) -> AsyncGenerator[SSEEvent, None]:
        """
        Subscribe to SSE events for a task.

        Args:
            task_id: The task ID to subscribe to

        Yields:
            SSEEvent objects as they arrive
        """
        url = f"{self.base_url}/api/v1/sse/subscribe/{task_id}"

        # Add token as query parameter if provided
        if self.token:
            url = f"{url}?token={self.token}"

        self._debug(f"Connecting to SSE endpoint: {url}")

        # Use a longer timeout for the connection, but we'll handle read timeouts ourselves
        client_timeout = httpx.Timeout(
            connect=30.0,
            read=60.0,  # Read timeout for individual chunks
            write=30.0,
            pool=30.0,
        )

        start_time = time.time()

        async with httpx.AsyncClient(timeout=client_timeout) as client:
            self._debug("Opening SSE stream...")
            async with client.stream("GET", url) as response:
                self._debug(f"SSE connection established, status: {response.status_code}")
                response.raise_for_status()

                async for event in self._parse_sse_stream(response, start_time):
                    yield event

    async def _parse_sse_stream(
        self,
        response: httpx.Response,
        start_time: float,
    ) -> AsyncGenerator[SSEEvent, None]:
        """Parse SSE stream from httpx response."""
        buffer = ""
        event_type = "message"
        event_count = 0

        self._debug("Starting to read SSE events...")

        try:
            async for chunk in response.aiter_text():
                # Check overall timeout
                elapsed = time.time() - start_time
                if elapsed > self.timeout:
                    self._debug(f"Overall timeout reached ({self.timeout}s)")
                    raise asyncio.TimeoutError(f"SSE stream timeout after {self.timeout}s")

                buffer += chunk
                self._debug(f"Received chunk ({len(chunk)} bytes), buffer size: {len(buffer)}")

                # Normalize line endings: convert \r\n to \n
                buffer = buffer.replace("\r\n", "\n")

                # SSE events are separated by double newlines
                while "\n\n" in buffer:
                    event_block, buffer = buffer.split("\n\n", 1)

                    data_lines = []
                    for line in event_block.split("\n"):
                        line = line.strip()
                        if line.startswith("event:"):
                            event_type = line[6:].strip()
                        elif line.startswith("data:"):
                            data_lines.append(line[5:].strip())
                        elif line.startswith(":"):
                            # Comment/keepalive line, skip
                            self._debug("Received keepalive")
                            continue

                    if data_lines:
                        raw_data = "\n".join(data_lines)
                        event_count += 1

                        try:
                            data = json.loads(raw_data)
                        except json.JSONDecodeError as e:
                            self._debug(f"JSON decode error: {e}")
                            data = {"raw": raw_data}

                        self._debug(f"Event #{event_count}: type={event_type}, data keys={list(data.keys()) if isinstance(data, dict) else 'not dict'}")

                        yield SSEEvent(
                            event_type=event_type,
                            data=data,
                            raw_data=raw_data,
                            timestamp=time.time(),
                        )

                        event_type = "message"  # Reset for next event

        except httpx.ReadTimeout:
            self._debug("Read timeout - no data received for 60s")
            raise
        except Exception as e:
            self._debug(f"Stream error: {type(e).__name__}: {e}")
            raise

        self._debug(f"SSE stream ended, received {event_count} events")
