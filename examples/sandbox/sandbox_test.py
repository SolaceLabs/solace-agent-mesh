#!/usr/bin/env python3
"""
Sandbox Test CLI - Test sandbox worker tools via DevBroker.

Starts a local DevBroker with a network server so the sandbox worker
container can connect, then sends tool invocation requests and displays
results and status updates in real-time.

Usage examples:

  # Echo tool test
  python sandbox_test.py echo "Hello from the sandbox!"

  # Execute Python code inline
  python sandbox_test.py exec "result = 2 + 2"

  # Execute Python code from a file
  python sandbox_test.py exec -f script.py

  # Invoke any tool by name (worker resolves from manifest)
  python sandbox_test.py invoke --tool compute_fibonacci --args '{"n": 20}'

  # Just listen for all messages on a topic pattern
  python sandbox_test.py listen "ed_test/a2a/v1/sam_remote_tool/>"

  # Use a different port or namespace
  python sandbox_test.py --port 55554 --namespace myns echo "test"

  # Wait for container to connect before sending
  python sandbox_test.py --wait-for-worker echo "test"
"""

import argparse
import json
import logging
import os
import queue
import signal
import sys
import textwrap
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

# ---------------------------------------------------------------------------
# Locate the repos so we can import from source even without `pip install -e`
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent
_SAM_ROOT = _SCRIPT_DIR.parent.parent
_SAC_ROOT = _SAM_ROOT.parent / "solace-ai-connector"

# Add source paths so imports work without editable installs
for _src in [_SAM_ROOT / "src", _SAC_ROOT / "src"]:
    _src_str = str(_src)
    if _src_str not in sys.path:
        sys.path.insert(0, _src_str)

# ---------------------------------------------------------------------------
# Imports from SAC / SAM
# ---------------------------------------------------------------------------
from solace_ai_connector.common.messaging.dev_broker_messaging import DevBroker
from solace_ai_connector.flow.flow import FlowKVStore, FlowLockManager

from solace_agent_mesh.common.a2a.protocol import (
    get_sam_remote_tool_invoke_topic,
    get_sam_remote_tool_response_topic,
    get_sam_remote_tool_status_topic,
)
from solace_agent_mesh.sandbox.protocol import (
    PreloadedArtifact,
    SandboxInvokeParams,
    SandboxToolInvocationRequest,
    SandboxToolInvocationResponse,
)

log = logging.getLogger("sandbox_test")

# ANSI colour helpers
_BOLD = "\033[1m"
_DIM = "\033[2m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_RED = "\033[31m"
_CYAN = "\033[36m"
_MAGENTA = "\033[35m"
_RESET = "\033[0m"


# ───────────────────────────────────────────────────────────────────────────
# DevBroker wrapper
# ───────────────────────────────────────────────────────────────────────────

class BrokerHarness:
    """Manages a DevBroker with network server for test invocations."""

    def __init__(self, namespace: str, port: int, agent_name: str = "sandbox-tester"):
        self.namespace = namespace
        self.port = port
        self.agent_name = agent_name

        self._lock_manager = FlowLockManager()
        self._kv_store = FlowKVStore()
        self._broker: Optional[DevBroker] = None
        self._queue_name = f"{namespace}/q/sandbox-test/{agent_name}"

    def start(self) -> int:
        """Start DevBroker with network server. Returns actual port."""
        response_sub = f"{self.namespace}/a2a/v1/sam_remote_tool/response/{self.agent_name}/>"
        status_sub = f"{self.namespace}/a2a/v1/sam_remote_tool/status/{self.agent_name}/>"

        broker_properties = {
            "broker_type": "dev_broker",
            "queue_name": self._queue_name,
            "subscriptions": [
                {"topic": response_sub},
                {"topic": status_sub},
            ],
            "dev_broker_network_enabled": True,
            "dev_broker_network_port": self.port,
        }

        self._broker = DevBroker(broker_properties, self._lock_manager, self._kv_store)
        self._broker.connect()

        # Retrieve the actual server port
        server = self._kv_store.get("dev_broker:network_server")
        if server:
            actual_port = server.port
        else:
            actual_port = self.port

        return actual_port

    def stop(self):
        """Disconnect the broker and stop the network server."""
        if self._broker:
            self._broker.disconnect()
        # Stop the network server so the process can exit cleanly
        server = self._kv_store.get("dev_broker:network_server")
        if server and hasattr(server, "_loop") and server._loop:
            import asyncio
            try:
                future = asyncio.run_coroutine_threadsafe(server.stop(), server._loop)
                future.result(timeout=3)  # Wait for stop() to complete
                # Give the loop a moment to process pending task cancellations
                time.sleep(0.2)
                server._loop.call_soon_threadsafe(server._loop.stop)
                time.sleep(0.1)
            except Exception:
                pass

    def publish(self, topic: str, payload: Any, user_properties: Dict = None):
        """Publish a message."""
        self._broker.send_message(topic, payload, user_properties)

    def receive(self, timeout_ms: int = 1000) -> Optional[Dict]:
        """Receive next message from our queue. Returns None on timeout."""
        return self._broker.receive_message(timeout_ms, self._queue_name)

    def subscribe(self, topic_pattern: str):
        """Add an additional subscription."""
        self._broker.add_topic_subscription(topic_pattern)


# ───────────────────────────────────────────────────────────────────────────
# Invocation helpers
# ───────────────────────────────────────────────────────────────────────────

def build_request(
    tool_name: str,
    args: Dict[str, Any],
    timeout_seconds: int = 300,
    sandbox_profile: str = "standard",
    tool_config: Optional[Dict] = None,
    preloaded_artifacts: Optional[Dict[str, PreloadedArtifact]] = None,
) -> tuple:
    """Build a SandboxToolInvocationRequest.

    Returns (request_dict, correlation_id).
    """
    correlation_id = str(uuid.uuid4())

    params = SandboxInvokeParams(
        task_id=correlation_id,
        tool_name=tool_name,
        args=args,
        tool_config=tool_config or {},
        app_name="sandbox-tester",
        user_id="tester",
        session_id="test-session",
        preloaded_artifacts=preloaded_artifacts or {},
        timeout_seconds=timeout_seconds,
        sandbox_profile=sandbox_profile,
    )

    request = SandboxToolInvocationRequest(
        id=correlation_id,
        params=params,
    )

    return request.model_dump(exclude_none=True), correlation_id


def invoke_tool(
    harness: BrokerHarness,
    tool_name: str,
    args: Dict[str, Any],
    timeout: int,
    sandbox_profile: str = "standard",
    tool_config: Optional[Dict] = None,
    preloaded_artifacts: Optional[Dict[str, PreloadedArtifact]] = None,
) -> Optional[SandboxToolInvocationResponse]:
    """Send a tool invocation and wait for the response."""

    request_payload, correlation_id = build_request(
        tool_name=tool_name,
        args=args,
        timeout_seconds=timeout,
        sandbox_profile=sandbox_profile,
        tool_config=tool_config,
        preloaded_artifacts=preloaded_artifacts,
    )

    request_topic = get_sam_remote_tool_invoke_topic(harness.namespace, tool_name)
    reply_to = get_sam_remote_tool_response_topic(harness.namespace, harness.agent_name, correlation_id)
    status_topic = get_sam_remote_tool_status_topic(harness.namespace, harness.agent_name, correlation_id)

    user_properties = {
        "replyTo": reply_to,
        "statusTo": status_topic,
        "clientId": harness.agent_name,
        "userId": "tester",
    }

    print(f"\n{_BOLD}Sending request{_RESET}")
    print(f"  {_DIM}correlation_id:{_RESET} {correlation_id}")
    print(f"  {_DIM}topic:{_RESET}          {request_topic}")
    print(f"  {_DIM}reply_to:{_RESET}       {reply_to}")
    print(f"  {_DIM}tool:{_RESET}           {tool_name}")
    print(f"  {_DIM}timeout:{_RESET}        {timeout}s")
    if args:
        args_preview = json.dumps(args, default=str)
        if len(args_preview) > 200:
            args_preview = args_preview[:200] + "..."
        print(f"  {_DIM}args:{_RESET}           {args_preview}")
    print()

    harness.publish(request_topic, request_payload, user_properties)

    # Wait for response, printing status updates as they arrive
    deadline = time.time() + timeout + 5  # small buffer for network
    response = None
    status_count = 0

    while time.time() < deadline:
        msg = harness.receive(timeout_ms=500)
        if msg is None:
            continue

        topic = msg.get("topic", "")
        payload = msg.get("payload", {})

        # Decode bytes payload if needed
        if isinstance(payload, (bytes, bytearray)):
            try:
                payload = json.loads(payload)
            except (json.JSONDecodeError, UnicodeDecodeError):
                payload = {"_raw": payload.decode("utf-8", errors="replace")}

        # Status update
        if "/sam_remote_tool/status/" in topic:
            status_count += 1
            # JSON-RPC 2.0 notification: status fields are in params
            params = payload.get("params", payload)
            status_text = params.get("status_text", params.get("status", str(payload)))
            ts = params.get("timestamp", "")
            print(f"  {_CYAN}[status {status_count}]{_RESET} {status_text}  {_DIM}{ts}{_RESET}")
            continue

        # Response
        if "/sam_remote_tool/response/" in topic:
            response = payload
            break

        # Unexpected message
        print(f"  {_YELLOW}[?]{_RESET} Unexpected message on {topic}")
        print(f"      {json.dumps(payload, default=str)[:300]}")

    return response


def display_response(payload: Optional[Dict]):
    """Pretty-print a sandbox response."""
    if payload is None:
        print(f"\n{_RED}{_BOLD}TIMEOUT{_RESET} - no response received")
        return False

    print(f"\n{_BOLD}Response received{_RESET}")

    try:
        resp = SandboxToolInvocationResponse.model_validate(payload)
    except Exception as e:
        print(f"  {_YELLOW}Warning: could not parse response model: {e}{_RESET}")
        print(f"  Raw payload: {json.dumps(payload, indent=2, default=str)[:2000]}")
        return False

    if resp.error:
        print(f"  {_RED}{_BOLD}ERROR{_RESET}")
        print(f"  {_DIM}code:{_RESET}    {resp.error.code}")
        print(f"  {_DIM}message:{_RESET} {resp.error.message}")
        if resp.error.data:
            print(f"  {_DIM}data:{_RESET}    {resp.error.data}")
        return False

    if resp.result:
        if resp.result.timed_out:
            print(f"  {_RED}{_BOLD}TIMED OUT{_RESET} in sandbox")
            return False

        print(f"  {_GREEN}{_BOLD}SUCCESS{_RESET}")
        print(f"  {_DIM}execution_time:{_RESET} {resp.result.execution_time_ms}ms")

        if resp.result.created_artifacts:
            print(f"  {_DIM}artifacts:{_RESET}      {len(resp.result.created_artifacts)}")
            for a in resp.result.created_artifacts:
                if hasattr(a, "filename"):
                    print(f"    - {a.filename} ({a.size_bytes} bytes)")
                else:
                    print(f"    - {a}")

        tool_result = resp.result.tool_result
        if tool_result:
            formatted = json.dumps(tool_result, indent=2, default=str)
            if len(formatted) > 3000:
                formatted = formatted[:3000] + "\n... (truncated)"
            print(f"  {_DIM}result:{_RESET}")
            for line in formatted.split("\n"):
                print(f"    {line}")

        return True

    print(f"  {_YELLOW}Empty response (no result, no error){_RESET}")
    return False


# ───────────────────────────────────────────────────────────────────────────
# Commands
# ───────────────────────────────────────────────────────────────────────────

def cmd_echo(harness: BrokerHarness, args: argparse.Namespace) -> bool:
    """echo command: send a message to echo_tool."""
    message = args.message
    resp = invoke_tool(
        harness,
        tool_name="echo_tool",
        args={"message": message},
        timeout=args.timeout,
    )
    return display_response(resp)


def cmd_exec(harness: BrokerHarness, args: argparse.Namespace) -> bool:
    """exec command: run Python code via execute_python."""
    if args.file:
        code_path = Path(args.file)
        if not code_path.exists():
            print(f"{_RED}Error: file not found: {args.file}{_RESET}")
            return False
        code = code_path.read_text()
        print(f"{_DIM}Read {len(code)} bytes from {args.file}{_RESET}")
    else:
        code = args.code
        if not code:
            print(f"{_RED}Error: provide --code or --file{_RESET}")
            return False

    tool_args = {"code": code}
    if args.artifacts:
        tool_args["artifacts"] = args.artifacts

    resp = invoke_tool(
        harness,
        tool_name="execute_python",
        args=tool_args,
        timeout=args.timeout,
    )
    return display_response(resp)


def cmd_invoke(harness: BrokerHarness, args: argparse.Namespace) -> bool:
    """invoke command: call any tool by name (worker resolves from manifest)."""
    tool_args = {}
    if args.args:
        try:
            tool_args = json.loads(args.args)
        except json.JSONDecodeError as e:
            print(f"{_RED}Error parsing --args JSON: {e}{_RESET}")
            return False

    tool_config = {}
    if args.tool_config:
        try:
            tool_config = json.loads(args.tool_config)
        except json.JSONDecodeError as e:
            print(f"{_RED}Error parsing --tool-config JSON: {e}{_RESET}")
            return False

    # Build preloaded artifacts from --artifact flags
    preloaded_artifacts = {}
    for spec in (args.artifact or []):
        if "=" not in spec:
            print(f"{_RED}Error: --artifact must be param_name=filepath (got '{spec}'){_RESET}")
            return False
        param_name, filepath = spec.split("=", 1)
        path = Path(filepath)
        if not path.exists():
            print(f"{_RED}Error: artifact file not found: {filepath}{_RESET}")
            return False
        content = path.read_text()
        preloaded_artifacts[param_name] = PreloadedArtifact(
            filename=path.name,
            content=content,
            version=0,
        )
        print(f"  {_DIM}artifact:{_RESET} {param_name} = {path.name} ({len(content)} bytes)")

    resp = invoke_tool(
        harness,
        tool_name=args.tool,
        args=tool_args,
        timeout=args.timeout,
        sandbox_profile=args.profile,
        tool_config=tool_config,
        preloaded_artifacts=preloaded_artifacts or None,
    )
    return display_response(resp)


def cmd_listen(harness: BrokerHarness, args: argparse.Namespace) -> bool:
    """listen command: subscribe to a topic pattern and display messages."""
    pattern = args.topic
    harness.subscribe(pattern)
    print(f"{_BOLD}Listening on:{_RESET} {pattern}")
    print(f"{_DIM}Press Ctrl+C to stop{_RESET}\n")

    count = 0
    try:
        while True:
            msg = harness.receive(timeout_ms=1000)
            if msg is None:
                continue
            count += 1
            topic = msg.get("topic", "?")
            payload = msg.get("payload", {})
            user_props = msg.get("user_properties", {})

            if isinstance(payload, (bytes, bytearray)):
                try:
                    payload = json.loads(payload)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    payload = {"_raw": payload.decode("utf-8", errors="replace")}

            ts = datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3]
            print(f"{_CYAN}[{ts}]{_RESET} {_BOLD}#{count}{_RESET} {_MAGENTA}{topic}{_RESET}")
            if user_props:
                print(f"  {_DIM}user_properties:{_RESET} {json.dumps(user_props, default=str)[:300]}")
            formatted = json.dumps(payload, indent=2, default=str)
            if len(formatted) > 2000:
                formatted = formatted[:2000] + "\n  ... (truncated)"
            for line in formatted.split("\n"):
                print(f"  {line}")
            print()
    except KeyboardInterrupt:
        print(f"\n{_DIM}Stopped after {count} message(s){_RESET}")
        return True


def cmd_wait(harness: BrokerHarness, args: argparse.Namespace) -> bool:
    """wait command: wait until the sandbox worker connects."""
    # We can detect the worker connecting by checking the DevBrokerServer's client list
    server = harness._kv_store.get("dev_broker:network_server")
    if not server:
        print(f"{_RED}Network server not running{_RESET}")
        return False

    print(f"{_BOLD}Waiting for sandbox worker to connect...{_RESET}")
    print(f"{_DIM}Press Ctrl+C to cancel{_RESET}")

    try:
        while True:
            # Check server's client count
            if hasattr(server, "_clients") and server._clients:
                client_ids = list(server._clients.keys())
                print(f"\n{_GREEN}{_BOLD}Worker connected!{_RESET}")
                for cid in client_ids:
                    print(f"  client_id: {cid}")
                return True
            time.sleep(0.5)
    except KeyboardInterrupt:
        print(f"\n{_DIM}Cancelled{_RESET}")
        return False


# ───────────────────────────────────────────────────────────────────────────
# Main
# ───────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Sandbox Test CLI - test sandbox worker tools via DevBroker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              %(prog)s echo "Hello!"
              %(prog)s exec "result = sum(range(100))"
              %(prog)s exec -f my_script.py
              %(prog)s invoke --tool compute_fibonacci --args '{"n": 20}'
              %(prog)s listen "ed_test/a2a/v1/sam_remote_tool/>"
              %(prog)s --port 55554 echo "test"
        """),
    )

    # Global options
    parser.add_argument(
        "--port", type=int,
        default=int(os.environ.get("DEV_BROKER_PORT", "55554")),
        help="DevBroker network server port (default: $DEV_BROKER_PORT or 55554)",
    )
    parser.add_argument(
        "--namespace", "-n",
        default=os.environ.get("NAMESPACE", "ed_test"),
        help="SAM namespace (default: $NAMESPACE or ed_test)",
    )
    parser.add_argument(
        "--timeout", "-t", type=int, default=30,
        help="Timeout in seconds (default: 30)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Enable verbose logging",
    )
    parser.add_argument(
        "--wait-for-worker", action="store_true",
        help="Wait for the sandbox worker to connect before executing command",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # --- echo ---
    p_echo = subparsers.add_parser("echo", help="Test echo_tool")
    p_echo.add_argument("message", help="Message to echo")

    # --- exec ---
    p_exec = subparsers.add_parser("exec", help="Execute Python code via execute_python")
    code_group = p_exec.add_mutually_exclusive_group()
    code_group.add_argument("code", nargs="?", help="Python code to execute")
    code_group.add_argument("--file", "-f", help="Read code from file")
    p_exec.add_argument(
        "--artifacts", "-a", nargs="*",
        help="Artifact parameter names to preload",
    )

    # --- invoke ---
    p_invoke = subparsers.add_parser("invoke", help="Invoke any tool by name (worker resolves from manifest)")
    p_invoke.add_argument("--tool", required=True, help="Tool name (must exist in worker's manifest)")
    p_invoke.add_argument("--args", help="Tool arguments as JSON string")
    p_invoke.add_argument("--tool-config", help="Tool config as JSON string")
    p_invoke.add_argument("--profile", default="standard", help="Sandbox profile (default: standard)")
    p_invoke.add_argument(
        "--artifact", action="append", metavar="PARAM=FILE",
        help="Preload artifact: param_name=filepath (can repeat)",
    )

    # --- listen ---
    p_listen = subparsers.add_parser("listen", help="Listen for messages on a topic pattern")
    p_listen.add_argument(
        "topic", nargs="?",
        help="Topic pattern to subscribe to (default: {namespace}/a2a/v1/sam_remote_tool/>)",
    )

    # --- wait ---
    subparsers.add_parser("wait", help="Wait for the sandbox worker to connect")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.WARNING
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(levelname)-5s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    # Always show our own INFO messages
    logging.getLogger("sandbox_test").setLevel(logging.DEBUG if args.verbose else logging.INFO)
    # Suppress noisy shutdown warnings from asyncio and dev broker server
    if not args.verbose:
        logging.getLogger("asyncio").setLevel(logging.CRITICAL)
        logging.getLogger("solace_ai_connector.common.messaging.dev_broker_server").setLevel(
            logging.CRITICAL
        )

    # Default listen topic
    if args.command == "listen" and not args.topic:
        args.topic = f"{args.namespace}/a2a/v1/sam_remote_tool/>"

    # Start the broker
    print(f"{_BOLD}Sandbox Test CLI{_RESET}")
    print(f"  {_DIM}namespace:{_RESET}  {args.namespace}")
    print(f"  {_DIM}port:{_RESET}       {args.port}")

    harness = BrokerHarness(
        namespace=args.namespace,
        port=args.port,
        agent_name="sandbox-tester",
    )

    # Handle Ctrl+C gracefully
    def signal_handler(sig, frame):
        print(f"\n{_DIM}Shutting down...{_RESET}")
        harness.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    try:
        actual_port = harness.start()
        print(f"  {_GREEN}DevBroker network server listening on port {actual_port}{_RESET}")
    except Exception as e:
        print(f"  {_RED}Failed to start DevBroker: {e}{_RESET}")
        sys.exit(1)

    # Optionally wait for worker
    if args.wait_for_worker:
        if not cmd_wait(harness, args):
            harness.stop()
            sys.exit(1)

    # Dispatch command
    success = False
    try:
        if args.command == "echo":
            success = cmd_echo(harness, args)
        elif args.command == "exec":
            success = cmd_exec(harness, args)
        elif args.command == "invoke":
            success = cmd_invoke(harness, args)
        elif args.command == "listen":
            success = cmd_listen(harness, args)
        elif args.command == "wait":
            success = cmd_wait(harness, args)
        else:
            parser.print_help()
    except KeyboardInterrupt:
        print(f"\n{_DIM}Interrupted{_RESET}")
    finally:
        harness.stop()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
