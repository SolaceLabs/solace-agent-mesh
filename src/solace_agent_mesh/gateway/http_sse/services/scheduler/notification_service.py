"""
Notification service for scheduled task execution results.
Supports multiple notification channels: SSE, webhooks, email, and broker topics.
"""

import asyncio
import json
import logging
from typing import Any, Callable, Dict, List, Optional

import httpx
from sqlalchemy.orm import Session as DBSession

from ...repository.models import ScheduledTaskModel, ScheduledTaskExecutionModel
from ...sse_manager import SSEManager
from ...shared import now_epoch_ms

log = logging.getLogger(__name__)


class NotificationService:
    """
    Handles notification delivery for scheduled task execution results.
    Supports multiple channels: SSE, webhooks, email, and broker topics.
    """

    def __init__(
        self,
        session_factory: Callable[[], DBSession],
        sse_manager: Optional[SSEManager],
        publish_func: Callable,
        namespace: str,
        instance_id: str,
    ):
        """
        Initialize notification service.

        Args:
            session_factory: Factory function to create database sessions
            sse_manager: SSE manager for WebUI notifications
            publish_func: Function to publish messages to broker
            namespace: Namespace for broker topics
            instance_id: Scheduler instance ID
        """
        self.session_factory = session_factory
        self.sse_manager = sse_manager
        self.publish_func = publish_func
        self.namespace = namespace
        self.instance_id = instance_id
        self.log_prefix = f"[NotificationService:{instance_id}]"

        # HTTP client for webhooks
        self.http_client = httpx.AsyncClient(timeout=30.0)

        log.info(f"{self.log_prefix} Initialized")

    async def notify_execution_complete(
        self,
        execution: ScheduledTaskExecutionModel,
        task: ScheduledTaskModel,
    ):
        """
        Send notifications for completed task execution.

        Args:
            execution: Execution record
            task: Scheduled task definition
        """
        if not task.notification_config:
            log.debug(
                f"{self.log_prefix} No notification config for task {task.id}, skipping"
            )
            return

        config = task.notification_config

        # Check if we should notify based on status
        should_notify = (
            (execution.status == "completed" and config.get("on_success", True))
            or (execution.status in ["failed", "timeout"] and config.get("on_failure", True))
        )

        if not should_notify:
            log.debug(
                f"{self.log_prefix} Notification not configured for status {execution.status}"
            )
            return

        log.info(
            f"{self.log_prefix} Sending notifications for execution {execution.id} (status: {execution.status})"
        )

        # Prepare notification payload
        payload = self._prepare_notification_payload(execution, task, config)

        # Send to all configured channels
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
                    log.warning(
                        f"{self.log_prefix} Unknown notification channel type: {channel_type}"
                    )
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

        # Update execution record with notification status
        if notifications_sent:
            try:
                with self.session_factory() as session:
                    db_execution = session.get(ScheduledTaskExecutionModel, execution.id)
                    if db_execution:
                        db_execution.notifications_sent = notifications_sent
                        session.commit()
            except Exception as e:
                log.error(
                    f"{self.log_prefix} Failed to update notification status: {e}",
                    exc_info=True,
                )

    def _prepare_notification_payload(
        self,
        execution: ScheduledTaskExecutionModel,
        task: ScheduledTaskModel,
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Prepare notification payload.

        Args:
            execution: Execution record
            task: Scheduled task
            config: Notification configuration

        Returns:
            Notification payload dictionary
        """
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

        # Add error message if failed
        if execution.error_message:
            payload["error_message"] = execution.error_message

        # Add result summary if available
        if execution.result_summary:
            payload["result_summary"] = execution.result_summary

        # Add artifacts if configured
        if config.get("include_artifacts", False) and execution.artifacts:
            payload["artifacts"] = execution.artifacts

        return payload

    async def _send_sse_notification(
        self,
        config: Dict[str, Any],
        payload: Dict[str, Any],
        task: ScheduledTaskModel,
    ):
        """
        Send notification via SSE to WebUI.

        Args:
            config: Channel configuration
            payload: Notification payload
            task: Scheduled task
        """
        if not self.sse_manager:
            log.warning(f"{self.log_prefix} SSE manager not available")
            return

        # Send to user's active sessions if user-level task
        if task.user_id:
            try:
                # Create SSE event for scheduled task completion
                await self.sse_manager.send_event(
                    task_id=f"scheduled_{task.id}",
                    event_data=payload,
                    event_type="scheduled_task_complete",
                )
                log.info(
                    f"{self.log_prefix} Sent SSE notification for task {task.id}"
                )
            except Exception as e:
                log.error(
                    f"{self.log_prefix} Failed to send SSE notification: {e}",
                    exc_info=True,
                )
                raise

    async def _send_webhook_notification(
        self,
        config: Dict[str, Any],
        payload: Dict[str, Any],
        task: ScheduledTaskModel,
    ):
        """
        Send notification via webhook (Slack, Teams, generic HTTP).

        Args:
            config: Channel configuration with url, method, headers
            payload: Notification payload
            task: Scheduled task
        """
        url = config.get("url")
        if not url:
            raise ValueError("Webhook URL not configured")

        method = config.get("method", "POST").upper()
        headers = config.get("headers", {})

        # Ensure Content-Type is set
        if "Content-Type" not in headers:
            headers["Content-Type"] = "application/json"

        try:
            # Format payload for common webhook services
            webhook_payload = self._format_webhook_payload(payload, config)

            response = await self.http_client.request(
                method=method,
                url=url,
                json=webhook_payload,
                headers=headers,
            )
            response.raise_for_status()

            log.info(
                f"{self.log_prefix} Sent webhook notification to {url} (status: {response.status_code})"
            )

        except httpx.HTTPStatusError as e:
            log.error(
                f"{self.log_prefix} Webhook returned error status {e.response.status_code}: {e.response.text}"
            )
            raise
        except Exception as e:
            log.error(
                f"{self.log_prefix} Failed to send webhook notification: {e}",
                exc_info=True,
            )
            raise

    def _format_webhook_payload(
        self, payload: Dict[str, Any], config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Format payload for specific webhook services.

        Args:
            payload: Base notification payload
            config: Channel configuration

        Returns:
            Formatted webhook payload
        """
        webhook_type = config.get("webhook_type", "generic")

        if webhook_type == "slack":
            # Slack webhook format
            status_emoji = "✅" if payload["status"] == "completed" else "❌"
            return {
                "text": f"{status_emoji} Scheduled Task: {payload['task_name']}",
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*{status_emoji} Scheduled Task Execution*\n\n"
                            f"*Task:* {payload['task_name']}\n"
                            f"*Status:* {payload['status']}\n"
                            f"*Execution ID:* `{payload['execution_id']}`",
                        },
                    }
                ],
            }
        elif webhook_type == "teams":
            # Microsoft Teams webhook format
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
            # Generic webhook - send raw payload
            return payload

    async def _send_email_notification(
        self,
        config: Dict[str, Any],
        payload: Dict[str, Any],
        task: ScheduledTaskModel,
    ):
        """
        Send notification via email.

        Args:
            config: Channel configuration with SMTP settings
            payload: Notification payload
            task: Scheduled task
        """
        # Email implementation would require SMTP configuration
        # This is a placeholder for future implementation
        log.info(
            f"{self.log_prefix} Email notification requested for task {task.id} (not yet implemented)"
        )

        # TODO: Implement SMTP email sending
        # Would use aiosmtplib or similar library
        # Example:
        # import aiosmtplib
        # from email.message import EmailMessage
        #
        # message = EmailMessage()
        # message["From"] = config.get("from_address")
        # message["To"] = ", ".join(config.get("to", []))
        # message["Subject"] = self._format_email_subject(payload, config)
        # message.set_content(self._format_email_body(payload))
        #
        # await aiosmtplib.send(
        #     message,
        #     hostname=config.get("smtp_host"),
        #     port=config.get("smtp_port", 587),
        #     username=config.get("smtp_username"),
        #     password=config.get("smtp_password"),
        #     use_tls=True,
        # )

    async def _send_broker_notification(
        self,
        config: Dict[str, Any],
        payload: Dict[str, Any],
        task: ScheduledTaskModel,
    ):
        """
        Publish notification to Solace broker topic.

        Args:
            config: Channel configuration with topic
            payload: Notification payload
            task: Scheduled task
        """
        topic = config.get("topic")
        if not topic:
            raise ValueError("Broker topic not configured")

        # Optionally filter payload
        if not config.get("include_full_result", False):
            # Send summary only
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

        # Publish to broker
        user_properties = {
            "scheduled_task_id": task.id,
            "execution_id": payload["execution_id"],
            "status": payload["status"],
        }

        try:
            self.publish_func(topic, filtered_payload, user_properties)
            log.info(
                f"{self.log_prefix} Published notification to broker topic: {topic}"
            )
        except Exception as e:
            log.error(
                f"{self.log_prefix} Failed to publish to broker topic {topic}: {e}",
                exc_info=True,
            )
            raise

    async def cleanup(self):
        """Cleanup resources."""
        try:
            await self.http_client.aclose()
            log.info(f"{self.log_prefix} HTTP client closed")
        except Exception as e:
            log.error(f"{self.log_prefix} Error closing HTTP client: {e}")