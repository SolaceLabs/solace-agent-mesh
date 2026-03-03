#!/usr/bin/env python3
"""
Load test for concurrent SSE visualization streams.

This test simulates 50 concurrent SSE visualization streams to verify
the single-threaded consumer can handle the load without queue overflow.

Usage:
    # Run against local SAM instance
    python tests/load/test_concurrent_sse_streams.py --url http://localhost:5050
    
    # Run against staging (requires auth token)
    python tests/load/test_concurrent_sse_streams.py --url https://staging.example.com --token <jwt>
    
    # Custom number of streams
    python tests/load/test_concurrent_sse_streams.py --streams 100 --url http://localhost:5050

The test flow:
1. Create N visualization streams via POST /api/v1/visualization/subscribe
2. Connect to SSE endpoints for each stream
3. Optionally submit tasks to generate events
4. Monitor for queue full errors and event delivery
5. Cleanup streams via DELETE /api/v1/visualization/{stream_id}/unsubscribe
"""

import argparse
import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass
from typing import Optional

import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)


@dataclass
class StreamStats:
    """Statistics for a single SSE stream."""
    stream_id: str
    topic: str = ""
    events_received: int = 0
    errors: int = 0
    start_time: float = 0
    end_time: float = 0
    connected: bool = False
    subscribed: bool = False
    error_message: Optional[str] = None
    sse_endpoint_url: Optional[str] = None


async def create_visualization_subscription(
    client: httpx.AsyncClient,
    base_url: str,
    stream_id: str,
    abstract_targets: list[dict],
    stats: StreamStats,
    auth_token: Optional[str] = None,
) -> Optional[str]:
    """
    Create a visualization subscription via POST /api/v1/visualization/subscribe.
    
    Args:
        client: HTTP client
        base_url: Base URL of the SAM server
        stream_id: Unique identifier for this stream
        abstract_targets: List of abstract targets to subscribe to
        stats: Statistics object to update
        auth_token: Optional auth token
        
    Returns:
        SSE endpoint URL if successful, None otherwise
    """
    headers = {"Content-Type": "application/json"}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    
    url = f"{base_url}/api/v1/visualization/subscribe"
    
    payload = {
        "stream_id": stream_id,
        "abstract_targets": abstract_targets,
    }
    
    try:
        response = await client.post(url, json=payload, headers=headers)
        
        if response.status_code in (200, 201):
            data = response.json()
            stats.subscribed = True
            stats.sse_endpoint_url = data.get("sse_endpoint_url")
            log.info(f"[{stream_id}] Subscribed successfully: {stats.sse_endpoint_url}")
            return stats.sse_endpoint_url
        else:
            stats.error_message = f"Subscribe failed: HTTP {response.status_code} - {response.text}"
            stats.errors += 1
            log.error(f"[{stream_id}] {stats.error_message}")
            return None
            
    except Exception as e:
        stats.error_message = f"Subscribe error: {e}"
        stats.errors += 1
        log.error(f"[{stream_id}] {stats.error_message}")
        return None


async def connect_to_sse_stream(
    client: httpx.AsyncClient,
    sse_url: str,
    stream_id: str,
    duration_seconds: float,
    stats: StreamStats,
    auth_token: Optional[str] = None,
) -> None:
    """
    Connect to an SSE stream and collect events.
    
    Args:
        client: HTTP client
        sse_url: Full SSE endpoint URL
        stream_id: Unique identifier for this stream
        duration_seconds: How long to keep the stream open
        stats: Statistics object to update
        auth_token: Optional auth token
    """
    stats.start_time = time.time()
    
    headers = {}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    
    try:
        log.info(f"[{stream_id}] Connecting to SSE: {sse_url}")
        
        async with client.stream("GET", sse_url, headers=headers, timeout=None) as response:
            if response.status_code != 200:
                stats.error_message = f"SSE connect failed: HTTP {response.status_code}"
                stats.errors += 1
                log.error(f"[{stream_id}] {stats.error_message}")
                return
            
            stats.connected = True
            log.info(f"[{stream_id}] SSE connected successfully")
            
            deadline = time.time() + duration_seconds
            
            async for line in response.aiter_lines():
                if time.time() > deadline:
                    log.info(f"[{stream_id}] Duration reached, closing stream")
                    break
                
                if line.startswith("data:"):
                    stats.events_received += 1
                    if stats.events_received % 100 == 0:
                        log.info(f"[{stream_id}] Received {stats.events_received} events")
                elif line.startswith("event:"):
                    pass  # Event type line
                elif line == "":
                    pass  # Empty line (event separator)
                    
    except httpx.ReadTimeout:
        log.warning(f"[{stream_id}] Read timeout (expected for idle streams)")
    except httpx.ConnectError as e:
        log.error(f"[{stream_id}] Connection error: {e}")
        stats.error_message = str(e)
        stats.errors += 1
    except asyncio.CancelledError:
        log.info(f"[{stream_id}] Stream cancelled")
    except Exception as e:
        log.error(f"[{stream_id}] Unexpected error: {e}")
        stats.error_message = str(e)
        stats.errors += 1
    finally:
        stats.end_time = time.time()


async def unsubscribe_visualization_stream(
    client: httpx.AsyncClient,
    base_url: str,
    stream_id: str,
    auth_token: Optional[str] = None,
) -> bool:
    """
    Unsubscribe from a visualization stream.
    
    Args:
        client: HTTP client
        base_url: Base URL of the SAM server
        stream_id: Stream ID to unsubscribe
        auth_token: Optional auth token
        
    Returns:
        True if successful
    """
    headers = {}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    
    url = f"{base_url}/api/v1/visualization/{stream_id}/unsubscribe"
    
    try:
        response = await client.delete(url, headers=headers)
        if response.status_code in (200, 204):
            log.debug(f"[{stream_id}] Unsubscribed successfully")
            return True
        else:
            log.warning(f"[{stream_id}] Unsubscribe failed: HTTP {response.status_code}")
            return False
    except Exception as e:
        log.warning(f"[{stream_id}] Unsubscribe error: {e}")
        return False


async def submit_test_task(
    client: httpx.AsyncClient,
    base_url: str,
    message: str,
    auth_token: Optional[str] = None,
) -> Optional[str]:
    """
    Submit a test task to generate visualization events.
    
    Args:
        client: HTTP client
        base_url: Base URL of the SAM server
        message: Message to send
        auth_token: Auth token (required)
        
    Returns:
        Task ID if successful
    """
    if not auth_token:
        log.warning("Cannot submit task without auth token")
        return None
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}",
    }
    
    url = f"{base_url}/api/v1/tasks"
    
    # A2A message format
    payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "parts": [{"type": "text", "text": message}],
            }
        }
    }
    
    try:
        response = await client.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            data = response.json()
            task_id = data.get("result", {}).get("id")
            log.info(f"Task submitted: {task_id}")
            return task_id
        else:
            log.error(f"Task submission failed: HTTP {response.status_code}")
            return None
    except Exception as e:
        log.error(f"Task submission error: {e}")
        return None


async def run_single_stream(
    client: httpx.AsyncClient,
    base_url: str,
    stream_id: str,
    abstract_targets: list[dict],
    duration_seconds: float,
    stats: StreamStats,
    auth_token: Optional[str] = None,
) -> None:
    """
    Run a single visualization stream lifecycle.
    
    Args:
        client: HTTP client
        base_url: Base URL of the SAM server
        stream_id: Unique stream ID
        abstract_targets: Targets to subscribe to
        duration_seconds: How long to keep stream open
        stats: Statistics object
        auth_token: Optional auth token
    """
    # Step 1: Create subscription
    sse_url = await create_visualization_subscription(
        client=client,
        base_url=base_url,
        stream_id=stream_id,
        abstract_targets=abstract_targets,
        stats=stats,
        auth_token=auth_token,
    )
    
    if not sse_url:
        return
    
    # Step 2: Connect to SSE stream
    try:
        await connect_to_sse_stream(
            client=client,
            sse_url=sse_url,
            stream_id=stream_id,
            duration_seconds=duration_seconds,
            stats=stats,
            auth_token=auth_token,
        )
    finally:
        # Step 3: Cleanup - unsubscribe
        await unsubscribe_visualization_stream(
            client=client,
            base_url=base_url,
            stream_id=stream_id,
            auth_token=auth_token,
        )


async def run_load_test(
    base_url: str,
    num_streams: int,
    duration_seconds: float,
    auth_token: Optional[str] = None,
    submit_tasks: bool = False,
    tasks_per_stream: int = 1,
) -> dict:
    """
    Run the load test with concurrent SSE streams.
    
    Args:
        base_url: Base URL of the SAM server
        num_streams: Number of concurrent streams to create
        duration_seconds: How long to run the test
        auth_token: Optional auth token
        submit_tasks: Whether to submit tasks to generate events
        tasks_per_stream: Number of tasks to submit per stream
        
    Returns:
        Test results dictionary
    """
    log.info(f"Starting load test with {num_streams} concurrent streams for {duration_seconds}s")
    log.info(f"Target URL: {base_url}")
    
    # Generate unique stream IDs
    stream_ids = [f"load-test-{uuid.uuid4().hex[:8]}" for _ in range(num_streams)]
    
    # Create stats objects for each stream
    stats_list = [
        StreamStats(stream_id=stream_ids[i])
        for i in range(num_streams)
    ]
    
    # Abstract targets - subscribe to all agent events
    # Each stream subscribes to a unique "session" to simulate different users
    abstract_targets_list = [
        [
            {
                "type": "agent",
                "agent_name": "*",  # All agents
                "session_id": f"test-session-{i}",
            }
        ]
        for i in range(num_streams)
    ]
    
    # Create HTTP client with connection pooling
    limits = httpx.Limits(
        max_connections=num_streams * 2 + 10,
        max_keepalive_connections=num_streams + 10,
    )
    
    async with httpx.AsyncClient(limits=limits, timeout=httpx.Timeout(60.0)) as client:
        start_time = time.time()
        
        # Start all streams concurrently
        stream_tasks = [
            run_single_stream(
                client=client,
                base_url=base_url,
                stream_id=stream_ids[i],
                abstract_targets=abstract_targets_list[i],
                duration_seconds=duration_seconds,
                stats=stats_list[i],
                auth_token=auth_token,
            )
            for i in range(num_streams)
        ]
        
        # Optionally submit tasks to generate events
        task_submission_tasks = []
        if submit_tasks and auth_token:
            # Wait a bit for streams to connect
            await asyncio.sleep(2)
            
            for i in range(num_streams):
                for j in range(tasks_per_stream):
                    task_submission_tasks.append(
                        submit_test_task(
                            client=client,
                            base_url=base_url,
                            message=f"Test message {j} for stream {i}",
                            auth_token=auth_token,
                        )
                    )
        
        # Run all tasks
        all_tasks = stream_tasks + task_submission_tasks
        await asyncio.gather(*all_tasks, return_exceptions=True)
        
        end_time = time.time()
    
    # Calculate results
    total_events = sum(s.events_received for s in stats_list)
    total_errors = sum(s.errors for s in stats_list)
    connected_streams = sum(1 for s in stats_list if s.connected)
    subscribed_streams = sum(1 for s in stats_list if s.subscribed)
    
    results = {
        "num_streams": num_streams,
        "duration_seconds": duration_seconds,
        "actual_duration": end_time - start_time,
        "subscribed_streams": subscribed_streams,
        "connected_streams": connected_streams,
        "total_events_received": total_events,
        "total_errors": total_errors,
        "events_per_second": total_events / (end_time - start_time) if end_time > start_time else 0,
        "error_rate": total_errors / num_streams if num_streams > 0 else 0,
        "stream_stats": [
            {
                "stream_id": s.stream_id,
                "topic": s.topic,
                "events_received": s.events_received,
                "errors": s.errors,
                "subscribed": s.subscribed,
                "connected": s.connected,
                "error_message": s.error_message,
                "duration": s.end_time - s.start_time if s.end_time > 0 else 0,
            }
            for s in stats_list
        ],
    }
    
    return results


def print_results(results: dict) -> None:
    """Print test results in a readable format."""
    print("\n" + "=" * 60)
    print("LOAD TEST RESULTS")
    print("=" * 60)
    print(f"Streams requested:     {results['num_streams']}")
    print(f"Streams subscribed:    {results['subscribed_streams']}")
    print(f"Streams connected:     {results['connected_streams']}")
    print(f"Duration (requested):  {results['duration_seconds']:.1f}s")
    print(f"Duration (actual):     {results['actual_duration']:.1f}s")
    print(f"Total events received: {results['total_events_received']}")
    print(f"Events per second:     {results['events_per_second']:.1f}")
    print(f"Total errors:          {results['total_errors']}")
    print(f"Error rate:            {results['error_rate']:.1%}")
    print("=" * 60)
    
    # Show streams with errors
    error_streams = [s for s in results['stream_stats'] if s['errors'] > 0]
    if error_streams:
        print("\nStreams with errors:")
        for s in error_streams[:10]:  # Show first 10
            print(f"  {s['stream_id']}: {s['error_message']}")
        if len(error_streams) > 10:
            print(f"  ... and {len(error_streams) - 10} more")
    
    # Show streams that failed to subscribe
    failed_subscribe = [s for s in results['stream_stats'] if not s['subscribed']]
    if failed_subscribe:
        print(f"\nStreams that failed to subscribe: {len(failed_subscribe)}")
    
    # Show streams that failed to connect SSE
    failed_connect = [s for s in results['stream_stats'] if s['subscribed'] and not s['connected']]
    if failed_connect:
        print(f"Streams that failed SSE connect: {len(failed_connect)}")
    
    print()


async def main():
    parser = argparse.ArgumentParser(description="Load test for concurrent SSE visualization streams")
    parser.add_argument(
        "--url",
        default="http://localhost:5050",
        help="Base URL of the SAM server (default: http://localhost:5050)",
    )
    parser.add_argument(
        "--streams",
        type=int,
        default=50,
        help="Number of concurrent streams (default: 50)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=30.0,
        help="Duration in seconds to keep streams open (default: 30)",
    )
    parser.add_argument(
        "--token",
        default=None,
        help="Auth token for authenticated endpoints",
    )
    parser.add_argument(
        "--submit-tasks",
        action="store_true",
        help="Submit tasks to generate visualization events (requires --token)",
    )
    parser.add_argument(
        "--tasks-per-stream",
        type=int,
        default=1,
        help="Number of tasks to submit per stream (default: 1)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    if args.submit_tasks and not args.token:
        log.warning("--submit-tasks requires --token, tasks will not be submitted")
    
    results = await run_load_test(
        base_url=args.url,
        num_streams=args.streams,
        duration_seconds=args.duration,
        auth_token=args.token,
        submit_tasks=args.submit_tasks,
        tasks_per_stream=args.tasks_per_stream,
    )
    
    print_results(results)
    
    # Save results to file
    results_file = f"sse_load_test_results_{int(time.time())}.json"
    with open(results_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Results saved to: {results_file}")


if __name__ == "__main__":
    asyncio.run(main())
