"""
Async HTTP client for stress testing REST endpoints.

Provides an HTTP client with automatic metrics collection for all requests.
"""

import asyncio
import time
from typing import Any, Dict, Optional, Union, TYPE_CHECKING
import logging

import httpx

if TYPE_CHECKING:
    from ..metrics.collector import MetricsCollector

logger = logging.getLogger(__name__)


class StressHTTPClient:
    """
    Async HTTP client with automatic metrics collection.

    Wraps httpx.AsyncClient to automatically record latency and error metrics
    for all requests.

    Usage:
        client = StressHTTPClient(
            base_url="http://localhost:8000",
            metrics_collector=collector,
        )

        response = await client.get("/api/v1/config", "config_fetch")
        response = await client.post("/api/v1/sessions", "session_create", json={...})
    """

    def __init__(
        self,
        base_url: str,
        metrics_collector: "MetricsCollector",
        default_headers: Optional[Dict[str, str]] = None,
        timeout_seconds: float = 30.0,
    ):
        """
        Initialize the HTTP client.

        Args:
            base_url: Base URL for all requests
            metrics_collector: MetricsCollector for recording metrics
            default_headers: Headers to include in all requests
            timeout_seconds: Default timeout for requests
        """
        self.base_url = base_url.rstrip("/")
        self.metrics = metrics_collector
        self.default_headers = default_headers or {}
        self.timeout = timeout_seconds

    async def request(
        self,
        method: str,
        path: str,
        operation_name: str,
        **kwargs,
    ) -> httpx.Response:
        """
        Make an HTTP request with automatic metrics collection.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE, etc.)
            path: URL path (will be appended to base_url)
            operation_name: Name for metrics tracking
            **kwargs: Additional arguments passed to httpx

        Returns:
            httpx.Response object

        Raises:
            httpx.HTTPError: On request failure
        """
        url = f"{self.base_url}{path}"
        headers = {**self.default_headers, **kwargs.pop("headers", {})}
        timeout = kwargs.pop("timeout", self.timeout)

        start = time.monotonic()
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(timeout)
            ) as client:
                response = await client.request(
                    method, url, headers=headers, **kwargs
                )

            latency_ms = (time.monotonic() - start) * 1000
            await self.metrics.record_latency(operation_name, latency_ms)
            await self.metrics.increment_counter(f"{operation_name}_total")
            await self.metrics.increment_counter(
                f"{operation_name}_status_{response.status_code}"
            )

            if response.status_code >= 400:
                await self.metrics.increment_counter(f"{operation_name}_errors")
                await self.metrics.increment_counter(
                    f"{operation_name}_error_{response.status_code}"
                )

            logger.debug(
                f"[{operation_name}] {method} {path} -> {response.status_code} "
                f"in {latency_ms:.1f}ms"
            )

            return response

        except httpx.TimeoutException as e:
            latency_ms = (time.monotonic() - start) * 1000
            await self.metrics.record_latency(operation_name, latency_ms)
            await self.metrics.record_error(
                operation_name, e, {"path": path, "type": "timeout"}
            )
            raise

        except Exception as e:
            latency_ms = (time.monotonic() - start) * 1000
            await self.metrics.record_latency(operation_name, latency_ms)
            await self.metrics.record_error(operation_name, e, {"path": path})
            raise

    async def get(
        self, path: str, operation_name: str, **kwargs
    ) -> httpx.Response:
        """Make a GET request."""
        return await self.request("GET", path, operation_name, **kwargs)

    async def post(
        self, path: str, operation_name: str, **kwargs
    ) -> httpx.Response:
        """Make a POST request."""
        return await self.request("POST", path, operation_name, **kwargs)

    async def put(
        self, path: str, operation_name: str, **kwargs
    ) -> httpx.Response:
        """Make a PUT request."""
        return await self.request("PUT", path, operation_name, **kwargs)

    async def delete(
        self, path: str, operation_name: str, **kwargs
    ) -> httpx.Response:
        """Make a DELETE request."""
        return await self.request("DELETE", path, operation_name, **kwargs)

    async def upload_artifact(
        self,
        session_id: str,
        filename: str,
        content: bytes,
        mime_type: str = "application/octet-stream",
        metadata_json: Optional[str] = None,
    ) -> httpx.Response:
        """
        Upload an artifact with metrics.

        Args:
            session_id: Session ID for the artifact
            filename: Filename for the artifact
            content: File content as bytes
            mime_type: MIME type of the content
            metadata_json: Optional JSON metadata string

        Returns:
            httpx.Response object
        """
        files = {"upload_file": (filename, content, mime_type)}
        data = {
            "sessionId": session_id,
            "filename": filename,
        }
        if metadata_json:
            data["metadata_json"] = metadata_json

        return await self.post(
            "/api/v1/artifacts/upload",
            "artifact_upload",
            files=files,
            data=data,
        )

    async def download_artifact(
        self,
        session_id: str,
        filename: str,
    ) -> httpx.Response:
        """
        Download an artifact with metrics.

        Args:
            session_id: Session ID for the artifact
            filename: Filename to download

        Returns:
            httpx.Response object with content
        """
        return await self.get(
            f"/api/v1/artifacts/{session_id}/{filename}",
            "artifact_download",
        )

    async def create_session(
        self,
        name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> httpx.Response:
        """
        Create a new session.

        Args:
            name: Optional session name
            metadata: Optional metadata dictionary

        Returns:
            httpx.Response object
        """
        json_body = {}
        if name:
            json_body["name"] = name
        if metadata:
            json_body["metadata"] = metadata

        return await self.post(
            "/api/v1/sessions",
            "session_create",
            json=json_body if json_body else None,
        )

    async def get_sessions(self) -> httpx.Response:
        """Get list of sessions."""
        return await self.get("/api/v1/sessions", "session_list")

    async def get_config(self) -> httpx.Response:
        """Get server configuration."""
        return await self.get("/api/v1/config", "config_fetch")

    async def get_agent_cards(self) -> httpx.Response:
        """Get list of agent cards."""
        return await self.get("/api/v1/agent-cards", "agent_cards_fetch")

    async def submit_message(
        self,
        message: str,
        context_id: Optional[str] = None,
        target_agent: Optional[str] = None,
        streaming: bool = True,
    ) -> httpx.Response:
        """
        Submit a message/task.

        Args:
            message: Message content
            context_id: Session/context ID
            target_agent: Target agent name
            streaming: Whether to use streaming endpoint

        Returns:
            httpx.Response object
        """
        endpoint = "/api/v1/message:stream" if streaming else "/api/v1/message:send"
        operation = "message_stream" if streaming else "message_send"

        json_body = {
            "message": {"role": "user", "parts": [{"type": "text", "text": message}]}
        }
        if context_id:
            json_body["contextId"] = context_id
        if target_agent:
            json_body["targetAgent"] = target_agent

        return await self.post(endpoint, operation, json=json_body)

    async def health_check(self) -> httpx.Response:
        """Check server health."""
        return await self.get("/health", "health_check")


class HTTPClientPool:
    """
    Pool of HTTP clients for concurrent request testing.

    Each client can make independent requests with shared metrics.
    """

    def __init__(
        self,
        base_url: str,
        metrics_collector: "MetricsCollector",
        pool_size: int = 10,
        timeout_seconds: float = 30.0,
    ):
        """
        Initialize the client pool.

        Args:
            base_url: Base URL for all clients
            metrics_collector: Shared metrics collector
            pool_size: Number of clients in the pool
            timeout_seconds: Timeout for requests
        """
        self.base_url = base_url
        self.metrics = metrics_collector
        self.pool_size = pool_size

        self.clients = [
            StressHTTPClient(
                base_url=base_url,
                metrics_collector=metrics_collector,
                timeout_seconds=timeout_seconds,
            )
            for _ in range(pool_size)
        ]

    async def parallel_requests(
        self,
        method: str,
        path: str,
        operation_name: str,
        count: Optional[int] = None,
        **kwargs,
    ) -> list[Union[httpx.Response, Exception]]:
        """
        Make parallel requests from all clients.

        Args:
            method: HTTP method
            path: URL path
            operation_name: Operation name for metrics
            count: Number of requests (defaults to pool_size)
            **kwargs: Additional request arguments

        Returns:
            List of responses or exceptions
        """
        count = count or self.pool_size

        async def make_request(client_idx: int):
            client = self.clients[client_idx % len(self.clients)]
            return await client.request(method, path, operation_name, **kwargs)

        tasks = [
            asyncio.create_task(make_request(i)) for i in range(count)
        ]

        return await asyncio.gather(*tasks, return_exceptions=True)

    async def sustained_load(
        self,
        method: str,
        path: str,
        operation_name: str,
        requests_per_second: float,
        duration_seconds: float,
        **kwargs,
    ) -> int:
        """
        Generate sustained load at a target rate.

        Args:
            method: HTTP method
            path: URL path
            operation_name: Operation name for metrics
            requests_per_second: Target request rate
            duration_seconds: Duration to run
            **kwargs: Additional request arguments

        Returns:
            Total number of requests made
        """
        interval = 1.0 / requests_per_second
        end_time = asyncio.get_event_loop().time() + duration_seconds
        request_count = 0
        client_idx = 0

        while asyncio.get_event_loop().time() < end_time:
            client = self.clients[client_idx % len(self.clients)]
            client_idx += 1

            # Fire and forget - don't wait for response
            asyncio.create_task(
                client.request(method, path, operation_name, **kwargs)
            )

            request_count += 1
            await asyncio.sleep(interval)

        # Brief pause to let in-flight requests complete
        await asyncio.sleep(0.5)

        return request_count
