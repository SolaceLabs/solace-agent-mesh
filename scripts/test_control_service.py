#!/usr/bin/env python3
"""
Integration test script for the Control Service.

Connects to a Solace broker and exercises all control plane CRUD operations
via JSON-RPC messages, verifying end-to-end functionality.

Usage:
    # With environment variables:
    SOLACE_BROKER_URL=tcp://localhost:55555 \\
    SOLACE_BROKER_VPN=default \\
    SOLACE_BROKER_USERNAME=admin \\
    SOLACE_BROKER_PASSWORD=admin \\
    python scripts/test_control_service.py

    # With CLI arguments:
    python scripts/test_control_service.py \\
        --broker-url tcp://localhost:55555 \\
        --vpn default \\
        --namespace sam

    # Verbose mode:
    python scripts/test_control_service.py -v
"""

import argparse
import json
import os
import sys
import threading
import time
import uuid

# ANSI color codes
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def _check_solace_sdk():
    """Check that the Solace PubSub+ SDK is available."""
    try:
        import solace.messaging  # noqa: F401

        return True
    except ImportError:
        return False


if not _check_solace_sdk():
    print(
        f"{RED}Error: solace-pubsubplus SDK not found.{RESET}\n"
        "Install it with: pip install solace-pubsubplus\n"
        "Or activate a virtualenv that has it installed."
    )
    sys.exit(1)

import certifi
from solace.messaging.messaging_service import MessagingService
from solace.messaging.resources.topic import Topic
from solace.messaging.resources.topic_subscription import TopicSubscription
from solace.messaging.resources.queue import Queue
from solace.messaging.publisher.persistent_message_publisher import (
    PersistentMessagePublisher,
)
from solace.messaging.receiver.persistent_message_receiver import (
    PersistentMessageReceiver,
)
from solace.messaging.config.retry_strategy import RetryStrategy
from solace.messaging.config.missing_resources_creation_configuration import (
    MissingResourcesCreationStrategy,
)


class ControlPlaneClient:
    """Client for sending JSON-RPC control plane requests over the Solace broker."""

    def __init__(self, broker_url, vpn, username, password, namespace, timeout=10):
        self.broker_url = broker_url
        self.vpn = vpn
        self.username = username
        self.password = password
        self.namespace = namespace.rstrip("/")
        self.timeout = timeout

        self._client_id = uuid.uuid4().hex[:12]
        self.reply_topic = f"_test/control-reply/{self._client_id}"
        self._queue_name = f"#test-control-{self._client_id}"

        # Response tracking
        self._pending = {}  # request_id -> threading.Event
        self._responses = {}  # request_id -> response dict
        self._lock = threading.Lock()

        self.service = None
        self.publisher = None
        self.receiver = None

    def connect(self):
        """Connect to the Solace broker."""
        broker_props = {
            "solace.messaging.transport.host": self.broker_url,
            "solace.messaging.service.vpn-name": self.vpn,
            "solace.messaging.authentication.scheme.basic.username": self.username,
            "solace.messaging.authentication.scheme.basic.password": self.password,
            "solace.messaging.tls.trust-store-path": os.path.dirname(certifi.where()),
        }

        self.service = (
            MessagingService.builder()
            .from_properties(broker_props)
            .with_reconnection_retry_strategy(
                RetryStrategy.parametrized_retry(3, 1000)
            )
            .build()
        )

        self.service.connect()

        # Publisher for sending requests
        self.publisher = (
            self.service.create_persistent_message_publisher_builder().build()
        )
        self.publisher.start()

        # Receiver on a temporary queue for replies
        queue = Queue.non_durable_exclusive_queue(self._queue_name)
        self.receiver = (
            self.service.create_persistent_message_receiver_builder()
            .with_missing_resources_creation_strategy(
                MissingResourcesCreationStrategy.CREATE_ON_START
            )
            .build(queue)
        )
        self.receiver.start()
        self.receiver.add_subscription(TopicSubscription.of(self.reply_topic))

        # Start background receive loop
        self._stop = threading.Event()
        self._recv_thread = threading.Thread(
            target=self._receive_loop, daemon=True, name="reply-receiver"
        )
        self._recv_thread.start()

    def _receive_loop(self):
        """Background loop to receive reply messages."""
        while not self._stop.is_set():
            try:
                msg = self.receiver.receive_message(timeout=500)
                if msg is None:
                    continue

                payload_str = msg.get_payload_as_string()
                if payload_str is None:
                    raw = msg.get_payload_as_bytes()
                    if raw:
                        payload_str = raw.decode("utf-8")

                if not payload_str:
                    continue

                try:
                    response = json.loads(payload_str)
                except json.JSONDecodeError:
                    continue

                req_id = response.get("id")
                with self._lock:
                    if req_id in self._pending:
                        self._responses[req_id] = response
                        self._pending[req_id].set()

                # Acknowledge the message
                self.receiver.ack(msg)

            except Exception:
                if not self._stop.is_set():
                    time.sleep(0.1)

    def disconnect(self):
        """Disconnect from the broker."""
        self._stop.set()
        if self._recv_thread:
            self._recv_thread.join(timeout=2)
        try:
            if self.receiver:
                self.receiver.terminate(0)
        except Exception:
            pass
        try:
            if self.publisher:
                self.publisher.terminate(0)
        except Exception:
            pass
        try:
            if self.service:
                self.service.disconnect()
        except Exception:
            pass

    def request(self, topic, method, body=None, timeout=None, raw_payload=None):
        """
        Send a JSON-RPC control request and wait for the response.

        Args:
            topic: The control topic to publish to.
            method: HTTP method (GET, POST, PATCH, DELETE).
            body: Request body dict (optional).
            timeout: Override default timeout.
            raw_payload: If set, send this as the raw payload instead of building JSON-RPC.

        Returns:
            The JSON-RPC response dict.

        Raises:
            TimeoutError: If no response is received within the timeout.
        """
        timeout = timeout or self.timeout
        req_id = str(uuid.uuid4())

        if raw_payload is not None:
            payload_str = (
                json.dumps(raw_payload)
                if isinstance(raw_payload, dict)
                else str(raw_payload)
            )
        else:
            payload = {
                "jsonrpc": "2.0",
                "id": req_id,
                "method": method,
                "params": {"body": body or {}},
            }
            payload_str = json.dumps(payload)

        event = threading.Event()
        with self._lock:
            self._pending[req_id] = event

        # Publish with reply_to_topic in user properties
        self.publisher.publish(
            message=bytearray(payload_str.encode("utf-8")),
            destination=Topic.of(topic),
            additional_message_properties={"reply_to_topic": self.reply_topic},
        )

        if event.wait(timeout):
            with self._lock:
                return self._responses.pop(req_id)
        else:
            with self._lock:
                self._pending.pop(req_id, None)
            raise TimeoutError(
                f"No response within {timeout}s for {method} {topic}"
            )

    # --- Convenience methods ---

    def _control_base(self):
        return f"{self.namespace}/sam/v1/control"

    def _control_topic(self, method, *path_parts):
        """Build a control topic: {ns}/sam/v1/control/{method}/{path_parts...}"""
        return f"{self._control_base()}/{method.lower()}/{'/'.join(path_parts)}"

    def list_apps(self):
        """GET /apps"""
        return self.request(self._control_topic("get", "apps"), "GET")

    def create_app(self, app_config):
        """POST /apps"""
        return self.request(self._control_topic("post", "apps"), "POST", body=app_config)

    def get_app(self, name):
        """GET /apps/{name}"""
        return self.request(self._control_topic("get", "apps", name), "GET")

    def patch_app(self, name, patch):
        """PATCH /apps/{name}"""
        return self.request(self._control_topic("patch", "apps", name), "PATCH", body=patch)

    def delete_app(self, name):
        """DELETE /apps/{name}"""
        return self.request(self._control_topic("delete", "apps", name), "DELETE")


# --- Test Runner ---


class TestResult:
    """Tracks a single test result."""

    def __init__(self, name, passed, detail="", response=None):
        self.name = name
        self.passed = passed
        self.detail = detail
        self.response = response


class ControlServiceTester:
    """Runs all control service integration tests."""

    def __init__(self, client, verbose=False):
        self.client = client
        self.verbose = verbose
        self.results = []
        self._test_app_name = f"_test_ctrl_{uuid.uuid4().hex[:8]}"

    def _log(self, msg):
        if self.verbose:
            print(f"  {DIM}{msg}{RESET}")

    def _record(self, name, passed, detail="", response=None):
        result = TestResult(name, passed, detail, response)
        self.results.append(result)
        status = f"{GREEN}PASS{RESET}" if passed else f"{RED}FAIL{RESET}"
        print(f"  {status}  {name}")
        if detail and (not passed or self.verbose):
            print(f"         {DIM}{detail}{RESET}")
        if response and self.verbose:
            print(f"         {DIM}Response: {json.dumps(response, indent=2)}{RESET}")
        return passed

    def run_all(self):
        """Run all test cases."""
        print(f"\n{BOLD}Control Service Integration Tests{RESET}")
        print(f"  Namespace: {self.client.namespace}")
        print(f"  Reply topic: {self.client.reply_topic}")
        print(f"  Test app name: {self._test_app_name}")
        print()

        # --- Happy path ---
        print(f"{CYAN}--- CRUD Operations ---{RESET}")
        self.test_list_apps()
        created = self.test_create_app()
        if created:
            self.test_get_app()
            self.test_patch_disable()
            self.test_patch_enable()
            self.test_delete_app()
        else:
            # Skip dependent tests
            for name in [
                "GET /apps/{name}",
                "PATCH disable",
                "PATCH enable",
                "DELETE /apps/{name}",
            ]:
                self._record(name, False, "Skipped — create failed")

        print()
        print(f"{CYAN}--- Error Cases ---{RESET}")
        self.test_get_not_found()
        self.test_delete_not_found()
        self.test_create_no_body()
        self.test_create_no_name()
        self.test_invalid_method_on_collection()

        # --- Summary ---
        print()
        passed = sum(1 for r in self.results if r.passed)
        failed = sum(1 for r in self.results if not r.passed)
        total = len(self.results)
        color = GREEN if failed == 0 else RED
        print(
            f"{BOLD}Results: {color}{passed}/{total} passed{RESET}"
            + (f", {RED}{failed} failed{RESET}" if failed else "")
        )
        print()
        return failed == 0

    # --- Individual Tests ---

    def test_list_apps(self):
        name = "GET /apps (list)"
        try:
            resp = self.client.list_apps()
            self._log(f"Response: {json.dumps(resp)}")

            if "error" in resp:
                return self._record(
                    name,
                    False,
                    f"Got error: {resp['error'].get('message')}",
                    resp,
                )

            result = resp.get("result", {})
            apps = result.get("apps")
            if not isinstance(apps, list):
                return self._record(
                    name, False, f"Expected 'apps' list, got: {type(apps)}", resp
                )

            return self._record(
                name, True, f"Found {len(apps)} app(s)", resp
            )
        except TimeoutError as e:
            return self._record(name, False, str(e))
        except Exception as e:
            return self._record(name, False, f"Exception: {e}")

    def test_create_app(self):
        name = "POST /apps (create)"
        try:
            config = {
                "name": self._test_app_name,
                "flows": [],
            }
            resp = self.client.create_app(config)
            self._log(f"Response: {json.dumps(resp)}")

            if "error" in resp:
                return self._record(
                    name,
                    False,
                    f"Got error: {resp['error'].get('message')}",
                    resp,
                )

            result = resp.get("result", {})
            if result.get("name") != self._test_app_name:
                return self._record(
                    name,
                    False,
                    f"Expected name '{self._test_app_name}', got '{result.get('name')}'",
                    resp,
                )

            return self._record(
                name, True, f"Created app '{self._test_app_name}'", resp
            )
        except TimeoutError as e:
            return self._record(name, False, str(e))
        except Exception as e:
            return self._record(name, False, f"Exception: {e}")

    def test_get_app(self):
        name = "GET /apps/{name}"
        try:
            resp = self.client.get_app(self._test_app_name)
            self._log(f"Response: {json.dumps(resp)}")

            if "error" in resp:
                return self._record(
                    name,
                    False,
                    f"Got error: {resp['error'].get('message')}",
                    resp,
                )

            result = resp.get("result", {})
            if result.get("name") != self._test_app_name:
                return self._record(
                    name,
                    False,
                    f"Expected name '{self._test_app_name}', got '{result.get('name')}'",
                    resp,
                )

            has_endpoints = "management_endpoints" in result
            return self._record(
                name,
                True,
                f"Got app info (management_endpoints: {has_endpoints})",
                resp,
            )
        except TimeoutError as e:
            return self._record(name, False, str(e))
        except Exception as e:
            return self._record(name, False, f"Exception: {e}")

    def test_patch_disable(self):
        name = "PATCH disable (enabled=false)"
        try:
            resp = self.client.patch_app(self._test_app_name, {"enabled": False})
            self._log(f"Response: {json.dumps(resp)}")

            if "error" in resp:
                return self._record(
                    name,
                    False,
                    f"Got error: {resp['error'].get('message')}",
                    resp,
                )

            result = resp.get("result", {})
            return self._record(
                name,
                True,
                f"status={result.get('status')}, enabled={result.get('enabled')}",
                resp,
            )
        except TimeoutError as e:
            return self._record(name, False, str(e))
        except Exception as e:
            return self._record(name, False, f"Exception: {e}")

    def test_patch_enable(self):
        name = "PATCH enable (enabled=true)"
        try:
            resp = self.client.patch_app(self._test_app_name, {"enabled": True})
            self._log(f"Response: {json.dumps(resp)}")

            if "error" in resp:
                return self._record(
                    name,
                    False,
                    f"Got error: {resp['error'].get('message')}",
                    resp,
                )

            result = resp.get("result", {})
            return self._record(
                name,
                True,
                f"status={result.get('status')}, enabled={result.get('enabled')}",
                resp,
            )
        except TimeoutError as e:
            return self._record(name, False, str(e))
        except Exception as e:
            return self._record(name, False, f"Exception: {e}")

    def test_delete_app(self):
        name = "DELETE /apps/{name}"
        try:
            resp = self.client.delete_app(self._test_app_name)
            self._log(f"Response: {json.dumps(resp)}")

            if "error" in resp:
                return self._record(
                    name,
                    False,
                    f"Got error: {resp['error'].get('message')}",
                    resp,
                )

            result = resp.get("result", {})
            if result.get("deleted") != self._test_app_name:
                return self._record(
                    name,
                    False,
                    f"Expected deleted='{self._test_app_name}', got '{result.get('deleted')}'",
                    resp,
                )

            return self._record(name, True, f"Deleted '{self._test_app_name}'", resp)
        except TimeoutError as e:
            return self._record(name, False, str(e))
        except Exception as e:
            return self._record(name, False, f"Exception: {e}")

    def test_get_not_found(self):
        name = "GET non-existent app -> -32001"
        try:
            resp = self.client.get_app("_nonexistent_app_xyz_000")
            self._log(f"Response: {json.dumps(resp)}")

            error = resp.get("error")
            if not error:
                return self._record(name, False, "Expected error, got success", resp)

            if error.get("code") != -32001:
                return self._record(
                    name,
                    False,
                    f"Expected code -32001, got {error.get('code')}",
                    resp,
                )

            return self._record(name, True, f"Got expected error: {error.get('message')}", resp)
        except TimeoutError as e:
            return self._record(name, False, str(e))
        except Exception as e:
            return self._record(name, False, f"Exception: {e}")

    def test_delete_not_found(self):
        name = "DELETE non-existent app -> -32001"
        try:
            resp = self.client.delete_app("_nonexistent_app_xyz_000")
            self._log(f"Response: {json.dumps(resp)}")

            error = resp.get("error")
            if not error:
                return self._record(name, False, "Expected error, got success", resp)

            if error.get("code") != -32001:
                return self._record(
                    name,
                    False,
                    f"Expected code -32001, got {error.get('code')}",
                    resp,
                )

            return self._record(name, True, f"Got expected error: {error.get('message')}", resp)
        except TimeoutError as e:
            return self._record(name, False, str(e))
        except Exception as e:
            return self._record(name, False, f"Exception: {e}")

    def test_create_no_body(self):
        name = "POST /apps empty body -> -32600"
        try:
            # Send with empty body (no name)
            resp = self.client.create_app({})
            self._log(f"Response: {json.dumps(resp)}")

            error = resp.get("error")
            if not error:
                return self._record(name, False, "Expected error, got success", resp)

            if error.get("code") != -32600:
                return self._record(
                    name,
                    False,
                    f"Expected code -32600, got {error.get('code')}",
                    resp,
                )

            return self._record(name, True, f"Got expected error: {error.get('message')}", resp)
        except TimeoutError as e:
            return self._record(name, False, str(e))
        except Exception as e:
            return self._record(name, False, f"Exception: {e}")

    def test_create_no_name(self):
        name = "POST /apps no name field -> -32600"
        try:
            resp = self.client.create_app({"flows": []})
            self._log(f"Response: {json.dumps(resp)}")

            error = resp.get("error")
            if not error:
                return self._record(name, False, "Expected error, got success", resp)

            if error.get("code") != -32600:
                return self._record(
                    name,
                    False,
                    f"Expected code -32600, got {error.get('code')}",
                    resp,
                )

            return self._record(name, True, f"Got expected error: {error.get('message')}", resp)
        except TimeoutError as e:
            return self._record(name, False, str(e))
        except Exception as e:
            return self._record(name, False, f"Exception: {e}")

    def test_invalid_method_on_collection(self):
        name = "DELETE /apps (collection) -> -32601"
        try:
            resp = self.client.request(
                self.client._control_topic("delete", "apps"), "DELETE"
            )
            self._log(f"Response: {json.dumps(resp)}")

            error = resp.get("error")
            if not error:
                return self._record(name, False, "Expected error, got success", resp)

            if error.get("code") != -32601:
                return self._record(
                    name,
                    False,
                    f"Expected code -32601, got {error.get('code')}",
                    resp,
                )

            return self._record(name, True, f"Got expected error: {error.get('message')}", resp)
        except TimeoutError as e:
            return self._record(name, False, str(e))
        except Exception as e:
            return self._record(name, False, f"Exception: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Integration test for the Control Service",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Environment variables (used as defaults for CLI arguments):
  SOLACE_BROKER_URL       Broker URL (e.g., tcp://localhost:55555)
  SOLACE_BROKER_VPN       Message VPN name
  SOLACE_BROKER_USERNAME  Broker username
  SOLACE_BROKER_PASSWORD  Broker password
  SAM_NAMESPACE           SAM namespace (default: sam)
""",
    )
    parser.add_argument(
        "--broker-url",
        default=os.environ.get("SOLACE_BROKER_URL", "tcp://localhost:55555"),
        help="Solace broker URL (default: $SOLACE_BROKER_URL or tcp://localhost:55555)",
    )
    parser.add_argument(
        "--vpn",
        default=os.environ.get("SOLACE_BROKER_VPN", "default"),
        help="Message VPN name (default: $SOLACE_BROKER_VPN or 'default')",
    )
    parser.add_argument(
        "--username",
        default=os.environ.get("SOLACE_BROKER_USERNAME", "default"),
        help="Broker username (default: $SOLACE_BROKER_USERNAME or 'default')",
    )
    parser.add_argument(
        "--password",
        default=os.environ.get("SOLACE_BROKER_PASSWORD", "default"),
        help="Broker password (default: $SOLACE_BROKER_PASSWORD or 'default')",
    )
    parser.add_argument(
        "--namespace",
        default=os.environ.get("SAM_NAMESPACE", "sam"),
        help="SAM namespace (default: $SAM_NAMESPACE or 'sam')",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=10,
        help="Response timeout in seconds (default: 10)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed output including full responses",
    )

    args = parser.parse_args()

    print(f"\n{BOLD}Connecting to broker...{RESET}")
    print(f"  URL:       {args.broker_url}")
    print(f"  VPN:       {args.vpn}")
    print(f"  Username:  {args.username}")
    print(f"  Namespace: {args.namespace}")

    client = ControlPlaneClient(
        broker_url=args.broker_url,
        vpn=args.vpn,
        username=args.username,
        password=args.password,
        namespace=args.namespace,
        timeout=args.timeout,
    )

    try:
        client.connect()
        print(f"  {GREEN}Connected.{RESET}")

        # Brief pause to let subscriptions propagate
        time.sleep(0.5)

        tester = ControlServiceTester(client, verbose=args.verbose)
        success = tester.run_all()

        sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        print(f"\n{YELLOW}Interrupted.{RESET}")
        sys.exit(130)
    except Exception as e:
        print(f"\n{RED}Error: {e}{RESET}")
        sys.exit(1)
    finally:
        print(f"{DIM}Disconnecting...{RESET}")
        client.disconnect()


if __name__ == "__main__":
    main()
