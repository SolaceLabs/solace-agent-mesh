#!/usr/bin/env python3
"""
Manual E2E test script for per-request model override via A2A task metadata.

Submits an A2A SendMessageRequest directly to a running SAM agent via the
Solace broker, with a model_override in the message metadata. Listens for
the agent's response on a reply topic.

Usage:
    # With alias (production — resolved by platform service):
    python scripts/test_model_override.py \
        --agent-name my-agent \
        --namespace default \
        --model-alias my-claude-model \
        --prompt "What model are you? Reply in one sentence."

    # Without override (baseline):
    python scripts/test_model_override.py \
        --agent-name my-agent \
        --namespace default \
        --prompt "What model are you? Reply in one sentence."

Environment variables for broker connection (or pass via flags):
    SOLACE_BROKER_URL   - e.g. tcp://localhost:55555
    SOLACE_BROKER_VPN   - e.g. default
    SOLACE_BROKER_USER  - e.g. default
    SOLACE_BROKER_PASS  - e.g. default
"""

import argparse
import json
import logging
import os
import sys
import uuid

from solace.messaging.messaging_service import MessagingService
from solace.messaging.config.solace_properties import (
    transport_layer_properties as transport_props,
    service_properties,
    authentication_properties as auth_props,
)
from solace.messaging.publisher.direct_message_publisher import PublishFailureListener
from solace.messaging.resources.topic import Topic
from solace.messaging.resources.topic_subscription import TopicSubscription

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)


def build_a2a_payload(
    prompt: str,
    session_id: str,
    task_id: str,
    model_alias: str | None = None,
) -> dict:
    metadata = {}
    if model_alias:
        metadata["model_override"] = {"model_id": model_alias}

    return {
        "jsonrpc": "2.0",
        "id": task_id,
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "kind": "message",
                "parts": [{"kind": "text", "text": prompt}],
                "messageId": uuid.uuid4().hex,
                "contextId": session_id,
                "metadata": metadata or None,
            }
        },
    }


class LogPublishFailure(PublishFailureListener):
    def on_failed_publish(self, failed_publish_event):
        log.error("Publish failed: %s", failed_publish_event)


def connect_broker(broker_url: str, vpn: str, username: str, password: str):
    broker_props = {
        transport_props.HOST: broker_url,
        service_properties.VPN_NAME: vpn,
        auth_props.SCHEME_BASIC_USER_NAME: username,
        auth_props.SCHEME_BASIC_PASSWORD: password,
    }
    messaging_service = MessagingService.builder().from_properties(broker_props).build()
    messaging_service.connect()
    log.info("Connected to broker at %s (VPN: %s)", broker_url, vpn)
    return messaging_service


def extract_text_from_response(response: dict) -> str:
    """Extract text content from an A2A JSON-RPC response."""
    result = response.get("result", {})

    if "status" in result:
        message = result.get("status", {}).get("message", {})
        parts = message.get("parts", [])
        texts = [p.get("text", "") for p in parts if p.get("kind") == "text"]
        if texts:
            return "\n".join(texts)

    artifacts = result.get("artifacts", [])
    for artifact in artifacts:
        for part in artifact.get("parts", []):
            if part.get("kind") == "text":
                return part.get("text", "")

    return json.dumps(response, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Test per-request model override via A2A")
    parser.add_argument("--agent-name", required=True, help="Target agent name")
    parser.add_argument("--namespace", default="default", help="SAM namespace")
    parser.add_argument("--prompt", default="What model are you? Reply in one sentence.")
    parser.add_argument("--model-alias", type=str, default=None,
                        help="Model config alias (resolved by the platform service)")
    parser.add_argument("--timeout", type=int, default=60, help="Response timeout (seconds)")
    parser.add_argument("--broker-url", default=os.environ.get("SOLACE_BROKER_URL", "tcp://localhost:55555"))
    parser.add_argument("--broker-vpn", default=os.environ.get("SOLACE_BROKER_VPN", "default"))
    parser.add_argument("--broker-user", default=os.environ.get("SOLACE_BROKER_USER", "default"))
    parser.add_argument("--broker-pass", default=os.environ.get("SOLACE_BROKER_PASS", "default"))
    args = parser.parse_args()

    client_id = f"test-override-{uuid.uuid4().hex[:8]}"
    session_id = uuid.uuid4().hex
    task_id = f"task-{uuid.uuid4().hex}"

    namespace = args.namespace
    agent_name = args.agent_name
    request_topic = f"{namespace}/a2a/v1/agent/request/{agent_name}"
    reply_topic = f"{namespace}/a2a/v1/client/response/{client_id}"
    reply_sub = f"{namespace}/a2a/v1/client/response/{client_id}"

    payload = build_a2a_payload(
        prompt=args.prompt,
        session_id=session_id,
        task_id=task_id,
        model_alias=args.model_alias,
    )

    log.info("=== Test Configuration ===")
    log.info("Agent:         %s", agent_name)
    log.info("Task ID:       %s", task_id)
    log.info("Request topic: %s", request_topic)
    log.info("Reply topic:   %s", reply_topic)
    if args.model_alias:
        log.info("Model alias:   %s (resolved by platform service)", args.model_alias)
    else:
        log.info("Model override: None (using agent default)")
    log.info("Prompt:        %s", args.prompt)
    log.info("==========================")

    messaging_service = connect_broker(
        args.broker_url, args.broker_vpn, args.broker_user, args.broker_pass
    )

    publisher = None
    receiver = None
    try:
        receiver = messaging_service.create_direct_message_receiver_builder() \
            .with_subscriptions([TopicSubscription.of(reply_sub)]) \
            .build()
        receiver.start()
        log.info("Subscribed to reply topic: %s", reply_sub)

        publisher = messaging_service.create_direct_message_publisher_builder().build()
        publisher.start()
        publisher.set_publish_failure_listener(LogPublishFailure())

        user_properties = {
            "replyTo": reply_topic,
            "clientId": client_id,
            "userId": "test-user",
        }
        payload_bytes = bytearray(json.dumps(payload).encode("utf-8"))
        publisher.publish(
            message=payload_bytes,
            destination=Topic.of(request_topic),
            additional_message_properties=user_properties,
        )
        log.info("Published task request to %s", request_topic)

        log.info("Waiting for response (timeout: %ds)...", args.timeout)
        inbound = receiver.receive_message(args.timeout * 1000)

        if not inbound:
            log.error("No response received within %ds", args.timeout)
            sys.exit(1)

        payload_str = inbound.get_payload_as_string() or inbound.get_payload_as_bytes().decode("utf-8")
        response = json.loads(payload_str)
        log.info("=== Response ===")

        error = response.get("error")
        if error:
            log.error("Agent returned error: %s", json.dumps(error, indent=2))
            sys.exit(1)

        text = extract_text_from_response(response)
        print(f"\nAgent response:\n{text}\n")

        if args.model_alias:
            log.info(
                "Check agent logs for: 'Resolved model override alias '%s' to model=...'",
                args.model_alias,
            )

    finally:
        if publisher:
            publisher.terminate()
        if receiver:
            receiver.terminate()
        messaging_service.disconnect()
        log.info("Disconnected from broker")


if __name__ == "__main__":
    main()
