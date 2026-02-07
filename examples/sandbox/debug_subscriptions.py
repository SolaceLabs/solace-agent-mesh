#!/usr/bin/env python3
"""Quick debug script to check if sandbox response messages are being delivered."""

import json
import socket
import time

HOST = "localhost"
PORT = 55554

def send_cmd(sock, cmd):
    """Send a JSON command and receive the response."""
    msg = json.dumps(cmd) + "\n"
    sock.sendall(msg.encode())
    data = b""
    while b"\n" not in data:
        chunk = sock.recv(4096)
        if not chunk:
            break
        data += chunk
    return json.loads(data.decode().strip())


def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((HOST, PORT))

    # Connect as a test client subscribing to sandbox response topic
    resp = send_cmd(sock, {
        "cmd": "CONNECT",
        "client_id": "debug-sub-test",
        "queue_name": "debug-sub-test-q",
        "subscriptions": [
            "ed_test/a2a/v1/sandbox/response/SandboxTestAgent/>"
        ],
    })
    print(f"CONNECT response: {resp}")

    # Now publish a fake sandbox response to the SandboxTestAgent
    fake_topic = "ed_test/a2a/v1/sandbox/response/SandboxTestAgent/test-correlation-123"
    fake_payload = {
        "jsonrpc": "2.0",
        "id": "test-correlation-123",
        "result": {
            "tool_result": {"status": "success", "data": "debug test"},
            "execution_time_ms": 100,
            "timed_out": False,
            "created_artifacts": [],
        },
    }

    resp = send_cmd(sock, {
        "cmd": "PUBLISH",
        "topic": fake_topic,
        "payload": fake_payload,
        "user_properties": {},
    })
    print(f"PUBLISH response: {resp}")

    # Try to receive the message we just published
    # (should be routed back to us since we subscribed to matching topic)
    resp = send_cmd(sock, {
        "cmd": "RECEIVE",
        "timeout_ms": 3000,
    })
    print(f"RECEIVE response: {resp}")

    # Disconnect
    resp = send_cmd(sock, {"cmd": "DISCONNECT"})
    print(f"DISCONNECT response: {resp}")

    sock.close()


if __name__ == "__main__":
    main()
