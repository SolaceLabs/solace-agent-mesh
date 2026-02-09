#!/usr/bin/env python3
"""
Test script for sandbox worker message round-trip.

Connects directly to the dev broker, sends a tool invocation request
to the sandbox worker, and waits for the response.

Usage:
    python examples/sandbox/test_sandbox_roundtrip.py

Requires:
    - SAM running with dev broker network server on port 55554
    - Sandbox worker container running and connected
"""

import json
import logging
import socket
import sys
import time
import uuid

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("sandbox_test")

# Dev broker connection
DEV_BROKER_HOST = "localhost"
DEV_BROKER_PORT = 55554
NAMESPACE = "ed_test/"
WORKER_ID = "sandbox-worker-001"


def send_cmd(sock, sock_file, cmd: dict) -> dict:
    """Send a command to the dev broker and return the response."""
    data = (json.dumps(cmd) + "\n").encode("utf-8")
    sock.sendall(data)
    response_line = sock_file.readline()
    if not response_line:
        raise ConnectionError("Connection closed by server")
    return json.loads(response_line.decode("utf-8"))


def main():
    correlation_id = str(uuid.uuid4())
    agent_name = "test-script"

    # Topics following A2A conventions
    request_topic = f"{NAMESPACE}a2a/v1/sandbox/request/{WORKER_ID}"
    reply_topic = f"{NAMESPACE}a2a/v1/sandbox/response/{agent_name}/{correlation_id}"
    status_topic = f"{NAMESPACE}a2a/v1/sandbox/status/{agent_name}/{correlation_id}"

    log.info("Connecting to dev broker at %s:%d...", DEV_BROKER_HOST, DEV_BROKER_PORT)

    # Connect to dev broker
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((DEV_BROKER_HOST, DEV_BROKER_PORT))
    sock_file = sock.makefile("rb")

    # Create a queue and subscribe to response + status topics
    queue_name = f"{NAMESPACE}q/test/{correlation_id}"
    response = send_cmd(sock, sock_file, {
        "cmd": "CONNECT",
        "client_id": f"test-{correlation_id[:8]}",
        "queue_name": queue_name,
        "subscriptions": [reply_topic, status_topic],
    })
    log.info("Connected: %s", response)

    # Build the tool invocation request
    request_payload = {
        "jsonrpc": "2.0",
        "id": correlation_id,
        "method": "sandbox/invoke",
        "params": {
            "task_id": correlation_id,
            "tool_name": "example_sandbox_tools.echo_tool",
            "module": "example_sandbox_tools",
            "function": "echo_tool",
            "args": {"message": "Hello from test script!"},
            "tool_config": {},
            "app_name": agent_name,
            "user_id": "test-user",
            "session_id": "test-session",
            "timeout_seconds": 30,
            "sandbox_profile": "standard",
        },
    }

    user_properties = {
        "replyTo": reply_topic,
        "statusTo": status_topic,
        "clientId": agent_name,
        "userId": "test-user",
    }

    log.info("Publishing request to topic: %s", request_topic)
    log.info("Request ID: %s", correlation_id)
    log.info("Reply topic: %s", reply_topic)

    response = send_cmd(sock, sock_file, {
        "cmd": "PUBLISH",
        "topic": request_topic,
        "payload": request_payload,
        "user_properties": user_properties,
    })
    log.info("Publish response: %s", response)

    # Wait for response(s)
    log.info("Waiting for response (timeout 15s)...")
    sock.settimeout(20)

    start = time.time()
    messages_received = 0

    while time.time() - start < 15:
        try:
            response = send_cmd(sock, sock_file, {
                "cmd": "RECEIVE",
                "timeout_ms": 3000,
            })

            if response.get("status") == "TIMEOUT":
                elapsed = time.time() - start
                log.info("  ... still waiting (%.1fs elapsed)", elapsed)
                continue

            if response.get("status") == "OK" and response.get("message"):
                msg = response["message"]
                topic = msg.get("topic", "")
                payload = msg.get("payload", {})
                messages_received += 1

                if "status" in topic:
                    log.info("STATUS UPDATE: %s", json.dumps(payload, indent=2))
                else:
                    log.info("RESPONSE received on topic: %s", topic)
                    log.info("RESPONSE payload:\n%s", json.dumps(payload, indent=2))

                    # Check for error
                    if payload.get("error"):
                        log.error("Tool execution failed: %s", payload["error"])
                    elif payload.get("result"):
                        result = payload["result"]
                        log.info(
                            "Tool result: %s (execution_time=%dms, timed_out=%s)",
                            json.dumps(result.get("tool_result", {})),
                            result.get("execution_time_ms", -1),
                            result.get("timed_out", False),
                        )
                    break  # Got the main response

        except socket.timeout:
            break
        except Exception as e:
            log.error("Error receiving: %s", e)
            break

    if messages_received == 0:
        log.warning("No messages received within timeout!")
    else:
        log.info("Total messages received: %d", messages_received)

    # Disconnect
    try:
        send_cmd(sock, sock_file, {"cmd": "DISCONNECT"})
    except Exception:
        pass
    sock.close()

    log.info("Done.")


if __name__ == "__main__":
    main()
