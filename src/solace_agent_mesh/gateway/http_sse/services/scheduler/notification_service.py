"""
Notification service for scheduled task execution results.
Supports multiple notification channels: SSE, webhooks, email, and broker topics.
"""

import asyncio
import ipaddress
import json
import logging
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlparse

import httpx
from sqlalchemy.orm import Session as DBSession

from ...repository.models import ScheduledTaskModel, ScheduledTaskExecutionModel
from ...sse_manager import SSEManager
from ...shared import now_epoch_ms

log = logging.getLogger(__name__)

# SSRF protection: blocked IP ranges
_BLOCKED_IP_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),       # Loopback
    ipaddress.ip_network("10.0.0.0/8"),         # Private
    ipaddress.ip_network("172.16.0.0/12"),      # Private
    ipaddress.ip_network("192.168.0.0/16"),     # Private
    ipaddress.ip_network("169.254.0.0/16"),     # Link-local / cloud metadata
    ipaddress.ip_network("::1/128"),            # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),           # IPv6 unique local
    ipaddress.ip_network("fe80::/10"),          # IPv6 link-local
]

_ALLOWED_SCHEMES = {"http", "https"}


def _validate_webhook_url(url: str) -> None:
    """
    Validate a webhook URL to prevent SSRF attacks.

    Blocks:
    - Private IPs, loopback, link-local
    - Cloud metadata endpoints (169.254.169.254)
    - Non-http/https schemes

    Raises:
        ValueError: If URL is not safe
    """
    parsed = urlparse(url)

    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise ValueError(f"Unsupported URL scheme '{parsed.scheme}'. Only http and https are allowed.")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL must have a hostname")

    # Resolve hostname to IP and check against blocked ranges
    try:
        import socket
        resolved_ips = socket.getaddrinfo(hostname, None)
        for family, _type, _proto, _canonname, sockaddr in resolved_ips:
            ip = ipaddress.ip_address(sockaddr[0])
            for network in _BLOCKED_IP_NETWORKS:
                if ip in network:
                    raise ValueError(
                        f"Webhook URL resolves to blocked IP range ({ip}). "
                        "Private, loopback, and link-local addresses are not allowed."
                    )
    except socket.gaierror:
        raise ValueError(f"Could not resolve hostname: {hostname}")


class NotificationService:
    """
    Handles notification delivery for scheduled task execution results.
    """

    def __init__(
        self,
        session_factory: Callable[[], DBSession],
        sse_manager: Optional[SSEManager],
        publish_func: Callable,
        namespace: str,
        instance_id: str,
    ):
        self.session_factory = session_factory
        self.sse_manager = sse_manager
        self.publish_func = publish_func
        self.namespace = namespace
        self.instance_id = instance_id
        self.log_prefix = f"[NotificationService:{instance_id}]"
        self.http_client = httpx.AsyncClient(timeout=30.0)
        log.info(f"{self.log_prefix} Initialized")

    async def notify_execution_complete(
        self,
        execution: ScheduledTaskExecutionModel,
        task: ScheduledTaskModel,
    ):
        """Send notifications for completed task execution."""
        if not task.notification_config:
            return

        config = task.notification_config

        should_notify = (
            (execution.status == "completed" and config.get("on_success", True))
            or (execution.status in ["failed", "timeout"] and config.get("on_failure", True))
        )

        if not should_notify:
            return

        payload = self._prepare_notification_payload(execution, task, config)

        notifications_sent = []
        channels = config.get("channels", [])

        for channel in channels:
            channel_type = channel.get("type")
            channel_config = channel.get("config", {})

            try:
                if channel_type == "sse":
                    await self._send_sse_notification(channel_config, payload, task)
                elif channel_type == "webhook":
                    await self._send_webhook_notification(channel_config, payload, task)
                elif channel_type == "email":
                    await self._send_email_notification(channel_config, payload, task)
                elif channel_type == "broker_topic":
                    await self._send_broker_notification(channel_config, payload, task)
                else:
                    log.warning(f"{self.log_prefix} Unknown notification channel type: {channel_type}")
                    continue

                notifications_sent.append({
                    "type": channel_type,
                    "status": "sent",
                    "timestamp": now_epoch_ms(),
                })

            except Exception as e:
                log.error(
                    f"{self.log_prefix} Failed to send {channel_type} notification: {e}",
                    exc_info=True,
                )
                notifications_sent.append({
                    "type": channel_type,
                    "status": "failed",
                    "error": str(e),
                    "timestamp": now_epoch_ms(),
                })

        if notifications_sent:
            try:
                with self.session_factory() as session:
                    db_execution = session.get(ScheduledTaskExecutionModel, execution.id)
                    if db_execution:
                        db_execution.notifications_sent = notifications_sent
                        session.commit()
            except Exception as e:
                log.error(f"{self.log_prefix} Failed to update notification status: {e}", exc_info=True)

    def _prepare_notification_payload(
        self,
        execution: ScheduledTaskExecutionModel,
        task: ScheduledTaskModel,
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        payload = {
            "task_id": task.id,
            "task_name": task.name,
            "execution_id": execution.id,
            "status": execution.status,
            "scheduled_for": execution.scheduled_for,
            "started_at": execution.started_at,
            "completed_at": execution.completed_at,
            "namespace": task.namespace,
            "user_id": task.user_id,
        }

        if execution.error_message:
            payload["error_message"] = execution.error_message
        if execution.result_summary:
            payload["result_summary"] = execution.result_summary
        if config.get("include_artifacts", False) and execution.artifacts:
            payload["artifacts"] = execution.artifacts

        return payload

    async def _send_sse_notification(self, config, payload, task):
        if not self.sse_manager:
            return
        if task.user_id:
            try:
                await self.sse_manager.send_event(
                    task_id=f"scheduled_{task.id}",
                    event_data=payload,
                    event_type="scheduled_task_complete",
                )
            except Exception as e:
                log.error(f"{self.log_prefix} Failed to send SSE notification: {e}", exc_info=True)
                raise

    async def _send_webhook_notification(self, config, payload, task):
        url = config.get("url")
        if not url:
            raise ValueError("Webhook URL not configured")

        # SSRF protection
        _validate_webhook_url(url)

        method = config.get("method", "POST").upper()
        headers = config.get("headers", {})
        if "Content-Type" not in headers:
            headers["Content-Type"] = "application/json"

        webhook_payload = self._format_webhook_payload(payload, config)

        response = await self.http_client.request(
            method=method, url=url, json=webhook_payload, headers=headers,
        )
        response.raise_for_status()

    def _format_webhook_payload(self, payload, config):
        webhook_type = config.get("webhook_type", "generic")

        if webhook_type == "slack":
            status_emoji = "pass" if payload["status"] == "completed" else "fail"
            return {
                "text": f"Scheduled Task: {payload['task_name']} ({status_emoji})",
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": (
                                f"*Scheduled Task Execution*\n\n"
                                f"*Task:* {payload['task_name']}\n"
                                f"*Status:* {payload['status']}\n"
                                f"*Execution ID:* `{payload['execution_id']}`"
                            ),
                        },
                    }
                ],
            }
        elif webhook_type == "teams":
            status_color = "00FF00" if payload["status"] == "completed" else "FF0000"
            return {
                "@type": "MessageCard",
                "@context": "https://schema.org/extensions",
                "summary": f"Scheduled Task: {payload['task_name']}",
                "themeColor": status_color,
                "title": f"Scheduled Task Execution: {payload['status']}",
                "sections": [
                    {
                        "facts": [
                            {"name": "Task", "value": payload["task_name"]},
                            {"name": "Status", "value": payload["status"]},
                            {"name": "Execution ID", "value": payload["execution_id"]},
                        ]
                    }
                ],
            }
        else:
            return payload

    async def _send_email_notification(self, config, payload, task):
        log.info(f"{self.log_prefix} Email notification requested for task {task.id} (not yet implemented)")

    async def _send_broker_notification(self, config, payload, task):
        topic = config.get("topic")
        if not topic:
            raise ValueError("Broker topic not configured")

        if not config.get("include_full_result", False):
            filtered_payload = {
                "task_id": payload["task_id"],
                "task_name": payload["task_name"],
                "execution_id": payload["execution_id"],
                "status": payload["status"],
                "scheduled_for": payload["scheduled_for"],
                "completed_at": payload.get("completed_at"),
            }
            if "error_message" in payload:
                filtered_payload["error_message"] = payload["error_message"]
        else:
            filtered_payload = payload

        user_properties = {
            "scheduled_task_id": task.id,
            "execution_id": payload["execution_id"],
            "status": payload["status"],
        }

        self.publish_func(topic, filtered_payload, user_properties)

    async def cleanup(self):
        """Cleanup resources."""
        try:
            await self.http_client.aclose()
        except Exception as e:
            log.error(f"{self.log_prefix} Error closing HTTP client: {e}")
