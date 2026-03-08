"""
Async SSE client for stress testing SSE connections.

Provides a client that can subscribe to SSE endpoints with automatic metrics collection.
"""

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import AsyncIterator, Optional, List, Any, TYPE_CHECKING
import logging

import httpx

if TYPE_CHECKING:
    from ..metrics.collector import MetricsCollector

logger = logging.getLogger(__name__)


@dataclass
class SSEEvent:
    """Parsed SSE event."""

    event_type: str
    data: str
    timestamp: float
    parsed_data: Optional[dict] = None
    id: Optional[str] = None
    retry: Optional[int] = None

    @property
    def is_close_signal(self) -> bool:
        """Check if this is a close signal (None data)."""
        return self.data is None


class StressSSEClient:
    """
    Async SSE client with metrics collection for stress testing.

    Connects to SSE endpoints, parses events, and records latency metrics.

    Usage:
        client = StressSSEClient(
            base_url="http://localhost:8000",
            client_id="test-1",
            metrics_collector=collector,
        )

        async for event in client.subscribe_to_task(task_id):
            print(f"Received: {event.event_type}")
    """

    def __init__(
        self,
        base_url: str,
        client_id: str,
        metrics_collector: "MetricsCollector",
        timeout_seconds: float = 120.0,
        sse_path_template: str = "/api/v1/sse/subscribe/{task_id}",
    ):
        """
        Initialize the SSE client.

        Args:
            base_url: Base URL of the server (e.g., "http://localhost:8000")
            client_id: Unique identifier for this client (for logging/metrics)
            metrics_collector: MetricsCollector instance for recording metrics
            timeout_seconds: Timeout for SSE connection
            sse_path_template: URL template for SSE endpoint
        """
        self.base_url = base_url.rstrip("/")
        self.client_id = client_id
        self.metrics = metrics_collector
        self.timeout = timeout_seconds
        self.sse_path_template = sse_path_template

        self._received_events: List[SSEEvent] = []
        self._connected = False
        self._connection_start: Optional[float] = None
        self._current_event_type: str = "message"
        self._current_event_id: Optional[str] = None

    async def subscribe_to_task(
        self,
        task_id: str,
        reconnect: bool = False,
        last_event_timestamp: int = 0,
        max_events: Optional[int] = None,
        headers: Optional[dict] = None,
    ) -> AsyncIterator[SSEEvent]:
        """
        Subscribe to SSE events for a task.

        Args:
            task_id: Task ID to subscribe to
            reconnect: Whether this is a reconnection attempt
            last_event_timestamp: Timestamp of last received event (for replay)
            max_events: Maximum events to receive before returning
            headers: Additional headers to send

        Yields:
            SSEEvent objects as they arrive
        """
        path = self.sse_path_template.format(task_id=task_id)
        url = f"{self.base_url}{path}"

        params = {}
        if reconnect:
            params["reconnect"] = "true"
            params["last_event_timestamp"] = str(last_event_timestamp)

        self._connection_start = time.monotonic()
        events_received = 0

        request_headers = headers or {}

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout, connect=30.0)
            ) as client:
                async with client.stream(
                    "GET", url, params=params, headers=request_headers
                ) as response:
                    if response.status_code != 200:
                        await self.metrics.record_error(
                            "sse_connect",
                            Exception(f"HTTP {response.status_code}"),
                            {"task_id": task_id, "client_id": self.client_id},
                        )
                        raise httpx.HTTPStatusError(
                            f"SSE connection failed with status {response.status_code}",
                            request=response.request,
                            response=response,
                        )

                    self._connected = True
                    connection_latency = (
                        time.monotonic() - self._connection_start
                    ) * 1000
                    await self.metrics.record_latency("sse_connect", connection_latency)
                    await self.metrics.increment_counter("sse_connections_established")

                    logger.debug(
                        f"[{self.client_id}] SSE connected to {task_id} "
                        f"in {connection_latency:.1f}ms"
                    )

                    # Parse SSE stream
                    buffer = ""
                    async for chunk in response.aiter_text():
                        buffer += chunk

                        # Process complete lines
                        while "\n" in buffer:
                            line, buffer = buffer.split("\n", 1)
                            line = line.rstrip("\r")

                            event = self._parse_sse_line(line)
                            if event:
                                event_latency = (
                                    time.monotonic() - self._connection_start
                                ) * 1000
                                await self.metrics.record_latency(
                                    "sse_event_received", event_latency
                                )
                                await self.metrics.increment_counter(
                                    "sse_events_received"
                                )
                                await self.metrics.increment_counter(
                                    f"sse_events_{event.event_type}"
                                )

                                self._received_events.append(event)
                                events_received += 1

                                yield event

                                if max_events and events_received >= max_events:
                                    return

        except httpx.TimeoutException as e:
            await self.metrics.record_error(
                "sse_subscribe",
                e,
                {"task_id": task_id, "client_id": self.client_id, "type": "timeout"},
            )
            raise
        except httpx.HTTPStatusError:
            raise
        except Exception as e:
            await self.metrics.record_error(
                "sse_subscribe",
                e,
                {"task_id": task_id, "client_id": self.client_id},
            )
            raise
        finally:
            self._connected = False
            await self.metrics.increment_counter("sse_connections_closed")
            logger.debug(
                f"[{self.client_id}] SSE disconnected from {task_id}, "
                f"received {events_received} events"
            )

    def _parse_sse_line(self, line: str) -> Optional[SSEEvent]:
        """
        Parse an SSE line into an event.

        SSE format:
            event: <event_type>
            data: <data>
            id: <id>
            retry: <retry_ms>
            (blank line ends event)

        Args:
            line: Single line from SSE stream

        Returns:
            SSEEvent if this line completes an event, None otherwise
        """
        if not line:
            # Blank line - event boundary, but we emit on data: line
            return None

        if line.startswith(":"):
            # Comment line, ignore
            return None

        if line.startswith("event:"):
            self._current_event_type = line[6:].strip()
            return None

        if line.startswith("id:"):
            self._current_event_id = line[3:].strip()
            return None

        if line.startswith("retry:"):
            # Ignore retry directive for now
            return None

        if line.startswith("data:"):
            data = line[5:].strip() if len(line) > 5 else ""

            event = SSEEvent(
                event_type=self._current_event_type,
                data=data,
                timestamp=time.monotonic(),
                id=self._current_event_id,
            )

            # Try to parse as JSON
            if data:
                try:
                    event.parsed_data = json.loads(data)
                except json.JSONDecodeError:
                    pass

            # Reset for next event
            self._current_event_type = "message"
            self._current_event_id = None

            return event

        return None

    @property
    def received_events(self) -> List[SSEEvent]:
        """Get list of all received events."""
        return self._received_events.copy()

    @property
    def is_connected(self) -> bool:
        """Check if currently connected."""
        return self._connected

    @property
    def event_count(self) -> int:
        """Get count of received events."""
        return len(self._received_events)

    def clear_events(self):
        """Clear received events list."""
        self._received_events.clear()


class SSEClientPool:
    """
    Pool of SSE clients for concurrent connection testing.

    Manages multiple SSE clients and provides aggregate metrics.
    """

    def __init__(
        self,
        base_url: str,
        metrics_collector: "MetricsCollector",
        pool_size: int = 10,
        timeout_seconds: float = 120.0,
    ):
        """
        Initialize the client pool.

        Args:
            base_url: Base URL of the server
            metrics_collector: Shared metrics collector
            pool_size: Number of clients in the pool
            timeout_seconds: Timeout for each client
        """
        self.base_url = base_url
        self.metrics = metrics_collector
        self.pool_size = pool_size
        self.timeout = timeout_seconds

        self.clients: List[StressSSEClient] = []
        for i in range(pool_size):
            self.clients.append(
                StressSSEClient(
                    base_url=base_url,
                    client_id=f"pool-client-{i}",
                    metrics_collector=metrics_collector,
                    timeout_seconds=timeout_seconds,
                )
            )

    async def subscribe_all(
        self,
        task_ids: List[str],
        max_events_per_client: int = 10,
    ) -> List[List[SSEEvent]]:
        """
        Subscribe all clients to their respective tasks concurrently.

        Args:
            task_ids: List of task IDs (one per client)
            max_events_per_client: Maximum events to receive per client

        Returns:
            List of event lists, one per client
        """
        if len(task_ids) != len(self.clients):
            raise ValueError(
                f"Expected {len(self.clients)} task_ids, got {len(task_ids)}"
            )

        async def collect_events(
            client: StressSSEClient, task_id: str
        ) -> List[SSEEvent]:
            events = []
            try:
                async for event in client.subscribe_to_task(
                    task_id, max_events=max_events_per_client
                ):
                    events.append(event)
            except Exception as e:
                logger.warning(f"Client {client.client_id} error: {e}")
            return events

        tasks = [
            asyncio.create_task(collect_events(client, task_id))
            for client, task_id in zip(self.clients, task_ids)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to empty lists
        return [r if isinstance(r, list) else [] for r in results]

    @property
    def total_events_received(self) -> int:
        """Get total events received across all clients."""
        return sum(client.event_count for client in self.clients)

    @property
    def connected_count(self) -> int:
        """Get count of currently connected clients."""
        return sum(1 for client in self.clients if client.is_connected)
