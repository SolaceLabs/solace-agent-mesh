"""Unit tests for NotificationService.

Tests the pure formatting logic for generic, Slack, and Teams webhook
payloads, SSRF protection, notification dispatch, payload preparation,
individual channel senders, and cleanup.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from solace_agent_mesh.gateway.http_sse.services.scheduler.notification_service import (
    NotificationService,
    _check_ip_blocked,
    _validate_webhook_url,
)


def _make_service():
    """Create a NotificationService with dummy dependencies (not used by the pure method)."""
    return NotificationService(
        session_factory=None,
        sse_manager=None,
        publish_func=None,
        namespace="test",
        instance_id="test-0",
    )


_SAMPLE_PAYLOAD = {
    "task_id": "t1",
    "task_name": "Daily Report",
    "execution_id": "e1",
    "status": "completed",
    "scheduled_for": 1700000000000,
    "started_at": 1700000001000,
    "completed_at": 1700000010000,
    "namespace": "default",
    "user_id": "u1",
}


class TestFormatWebhookPayload:
    """Tests for NotificationService._format_webhook_payload."""

    def test_generic_returns_payload_unchanged(self):
        svc = _make_service()
        result = svc._format_webhook_payload(_SAMPLE_PAYLOAD, {"webhook_type": "generic"})
        assert result is _SAMPLE_PAYLOAD

    def test_default_type_is_generic(self):
        svc = _make_service()
        result = svc._format_webhook_payload(_SAMPLE_PAYLOAD, {})
        assert result is _SAMPLE_PAYLOAD

    def test_slack_format_contains_blocks(self):
        svc = _make_service()
        result = svc._format_webhook_payload(_SAMPLE_PAYLOAD, {"webhook_type": "slack"})
        assert "text" in result
        assert "blocks" in result
        assert "Daily Report" in result["text"]
        assert result["blocks"][0]["type"] == "section"

    def test_slack_format_failed_status(self):
        svc = _make_service()
        payload = {**_SAMPLE_PAYLOAD, "status": "failed"}
        result = svc._format_webhook_payload(payload, {"webhook_type": "slack"})
        assert "fail" in result["text"]

    def test_teams_format_contains_sections(self):
        svc = _make_service()
        result = svc._format_webhook_payload(_SAMPLE_PAYLOAD, {"webhook_type": "teams"})
        assert result["@type"] == "MessageCard"
        assert "sections" in result
        assert result["themeColor"] == "00FF00"

    def test_teams_format_failed_uses_red(self):
        svc = _make_service()
        payload = {**_SAMPLE_PAYLOAD, "status": "failed"}
        result = svc._format_webhook_payload(payload, {"webhook_type": "teams"})
        assert result["themeColor"] == "FF0000"


# ---------------------------------------------------------------------------
# Helpers for building mock execution / task objects
# ---------------------------------------------------------------------------

def _make_execution(**overrides):
    """Return a MagicMock that behaves like ScheduledTaskExecutionModel."""
    defaults = {
        "id": "exec-1",
        "status": "completed",
        "scheduled_for": 1700000000000,
        "started_at": 1700000001000,
        "completed_at": 1700000010000,
        "error_message": None,
        "result_summary": None,
        "artifacts": None,
        "notifications_sent": None,
    }
    defaults.update(overrides)
    return MagicMock(**defaults)


def _make_task(**overrides):
    """Return a MagicMock that behaves like ScheduledTaskModel."""
    defaults = {
        "id": "task-1",
        "name": "Daily Report",
        "namespace": "default",
        "user_id": "u1",
        "notification_config": None,
    }
    defaults.update(overrides)
    return MagicMock(**defaults)


# ---------------------------------------------------------------------------
# 1. TestSSRFProtection
# ---------------------------------------------------------------------------

class TestSSRFProtection:
    """Tests for _check_ip_blocked and _validate_webhook_url."""

    # -- _check_ip_blocked --

    def test_blocks_loopback_ipv4(self):
        with pytest.raises(ValueError, match="blocked IP range"):
            _check_ip_blocked("127.0.0.1")

    def test_blocks_loopback_ipv4_non_standard(self):
        with pytest.raises(ValueError, match="blocked IP range"):
            _check_ip_blocked("127.0.0.2")

    def test_blocks_private_10(self):
        with pytest.raises(ValueError, match="blocked IP range"):
            _check_ip_blocked("10.0.0.1")

    def test_blocks_private_172_16(self):
        with pytest.raises(ValueError, match="blocked IP range"):
            _check_ip_blocked("172.16.0.1")

    def test_blocks_private_192_168(self):
        with pytest.raises(ValueError, match="blocked IP range"):
            _check_ip_blocked("192.168.1.1")

    def test_blocks_link_local(self):
        with pytest.raises(ValueError, match="blocked IP range"):
            _check_ip_blocked("169.254.169.254")

    def test_blocks_ipv6_loopback(self):
        with pytest.raises(ValueError, match="blocked IP range"):
            _check_ip_blocked("::1")

    def test_allows_public_ip(self):
        # Should not raise
        _check_ip_blocked("8.8.8.8")

    def test_allows_another_public_ip(self):
        _check_ip_blocked("93.184.216.34")

    # -- _validate_webhook_url --

    def test_rejects_ftp_scheme(self):
        with pytest.raises(ValueError, match="Unsupported URL scheme"):
            _validate_webhook_url("ftp://example.com/hook")

    def test_rejects_file_scheme(self):
        with pytest.raises(ValueError, match="Unsupported URL scheme"):
            _validate_webhook_url("file:///etc/passwd")

    def test_rejects_url_without_hostname(self):
        with pytest.raises(ValueError, match="must have a hostname"):
            _validate_webhook_url("http://")

    @patch("socket.getaddrinfo", side_effect=__import__("socket").gaierror("DNS fail"))
    def test_handles_dns_resolution_failure(self, _mock_dns):
        with pytest.raises(ValueError, match="Could not resolve hostname"):
            _validate_webhook_url("https://nonexistent.invalid/hook")

    @patch(
        "socket.getaddrinfo",
        return_value=[(2, 1, 6, "", ("93.184.216.34", 0))],
    )
    def test_allows_public_url(self, _mock_dns):
        # Should not raise
        _validate_webhook_url("https://example.com/hook")

    @patch(
        "socket.getaddrinfo",
        return_value=[(2, 1, 6, "", ("127.0.0.1", 0))],
    )
    def test_blocks_url_resolving_to_loopback(self, _mock_dns):
        with pytest.raises(ValueError, match="blocked IP range"):
            _validate_webhook_url("https://evil.example.com/hook")


# ---------------------------------------------------------------------------
# 2. TestNotifyExecutionComplete
# ---------------------------------------------------------------------------

class TestNotifyExecutionComplete:
    """Tests for NotificationService.notify_execution_complete."""

    @pytest.mark.asyncio
    async def test_returns_early_when_no_notification_config(self):
        svc = _make_service()
        task = _make_task(notification_config=None)
        execution = _make_execution()
        # Should return without error
        result = await svc.notify_execution_complete(execution, task)
        assert result is None

    @pytest.mark.asyncio
    async def test_respects_on_success_false(self):
        svc = _make_service()
        task = _make_task(notification_config={
            "on_success": False,
            "on_failure": True,
            "channels": [{"type": "sse", "config": {}}],
        })
        execution = _make_execution(status="completed")
        svc._send_sse_notification = AsyncMock()

        await svc.notify_execution_complete(execution, task)

        svc._send_sse_notification.assert_not_called()

    @pytest.mark.asyncio
    async def test_respects_on_failure_false(self):
        svc = _make_service()
        task = _make_task(notification_config={
            "on_success": True,
            "on_failure": False,
            "channels": [{"type": "sse", "config": {}}],
        })
        execution = _make_execution(status="failed")
        svc._send_sse_notification = AsyncMock()

        await svc.notify_execution_complete(execution, task)

        svc._send_sse_notification.assert_not_called()

    @pytest.mark.asyncio
    async def test_records_notifications_sent_on_execution(self):
        svc = _make_service()
        mock_session = MagicMock()
        mock_db_exec = MagicMock()
        mock_session.get.return_value = mock_db_exec
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        svc.session_factory = MagicMock(return_value=mock_session)

        task = _make_task(notification_config={
            "on_success": True,
            "channels": [{"type": "sse", "config": {}}],
        })
        execution = _make_execution(status="completed")
        svc._send_sse_notification = AsyncMock()

        await svc.notify_execution_complete(execution, task)

        mock_session.commit.assert_called_once()
        assert mock_db_exec.notifications_sent is not None
        assert len(mock_db_exec.notifications_sent) == 1
        assert mock_db_exec.notifications_sent[0]["type"] == "sse"
        assert mock_db_exec.notifications_sent[0]["status"] == "sent"

    @pytest.mark.asyncio
    async def test_channel_failure_isolation(self):
        """One channel failing should not stop other channels from being attempted."""
        svc = _make_service()
        mock_session = MagicMock()
        mock_db_exec = MagicMock()
        mock_session.get.return_value = mock_db_exec
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        svc.session_factory = MagicMock(return_value=mock_session)

        task = _make_task(notification_config={
            "on_success": True,
            "channels": [
                {"type": "webhook", "config": {}},
                {"type": "sse", "config": {}},
            ],
        })
        execution = _make_execution(status="completed")

        svc._send_webhook_notification = AsyncMock(side_effect=ValueError("no url"))
        svc._send_sse_notification = AsyncMock()

        await svc.notify_execution_complete(execution, task)

        # Both channels attempted
        svc._send_webhook_notification.assert_called_once()
        svc._send_sse_notification.assert_called_once()

        # Both recorded
        assert len(mock_db_exec.notifications_sent) == 2
        statuses = {n["type"]: n["status"] for n in mock_db_exec.notifications_sent}
        assert statuses["webhook"] == "failed"
        assert statuses["sse"] == "sent"


# ---------------------------------------------------------------------------
# 3. TestPrepareNotificationPayload
# ---------------------------------------------------------------------------

class TestPrepareNotificationPayload:
    """Tests for NotificationService._prepare_notification_payload."""

    def test_includes_error_message_when_present(self):
        svc = _make_service()
        execution = _make_execution(error_message="Something went wrong")
        task = _make_task()
        payload = svc._prepare_notification_payload(execution, task, {})
        assert payload["error_message"] == "Something went wrong"

    def test_excludes_error_message_when_none(self):
        svc = _make_service()
        execution = _make_execution(error_message=None)
        task = _make_task()
        payload = svc._prepare_notification_payload(execution, task, {})
        assert "error_message" not in payload

    def test_includes_result_summary_when_present(self):
        svc = _make_service()
        execution = _make_execution(result_summary="All good")
        task = _make_task()
        payload = svc._prepare_notification_payload(execution, task, {})
        assert payload["result_summary"] == "All good"

    def test_excludes_result_summary_when_none(self):
        svc = _make_service()
        execution = _make_execution(result_summary=None)
        task = _make_task()
        payload = svc._prepare_notification_payload(execution, task, {})
        assert "result_summary" not in payload

    def test_includes_artifacts_when_flag_true(self):
        svc = _make_service()
        execution = _make_execution(artifacts=[{"file": "report.pdf"}])
        task = _make_task()
        config = {"include_artifacts": True}
        payload = svc._prepare_notification_payload(execution, task, config)
        assert payload["artifacts"] == [{"file": "report.pdf"}]

    def test_excludes_artifacts_when_flag_false(self):
        svc = _make_service()
        execution = _make_execution(artifacts=[{"file": "report.pdf"}])
        task = _make_task()
        config = {"include_artifacts": False}
        payload = svc._prepare_notification_payload(execution, task, config)
        assert "artifacts" not in payload

    def test_excludes_artifacts_when_flag_missing(self):
        svc = _make_service()
        execution = _make_execution(artifacts=[{"file": "report.pdf"}])
        task = _make_task()
        payload = svc._prepare_notification_payload(execution, task, {})
        assert "artifacts" not in payload


# ---------------------------------------------------------------------------
# 4. TestSendBrokerNotification
# ---------------------------------------------------------------------------

class TestSendBrokerNotification:
    """Tests for NotificationService._send_broker_notification."""

    @pytest.mark.asyncio
    async def test_filters_payload_when_include_full_result_false(self):
        publish_func = MagicMock()
        svc = NotificationService(
            session_factory=None,
            sse_manager=None,
            publish_func=publish_func,
            namespace="test",
            instance_id="test-0",
        )
        config = {"topic": "scheduled-tasks/notifications/result", "include_full_result": False}
        payload = {**_SAMPLE_PAYLOAD, "result_summary": "lots of data", "artifacts": []}
        task = _make_task()

        await svc._send_broker_notification(config, payload, task)

        publish_func.assert_called_once()
        sent_payload = publish_func.call_args[0][1]
        assert "result_summary" not in sent_payload
        assert "artifacts" not in sent_payload
        assert sent_payload["task_id"] == "t1"
        assert sent_payload["status"] == "completed"

    @pytest.mark.asyncio
    async def test_passes_full_payload_when_include_full_result_true(self):
        publish_func = MagicMock()
        svc = NotificationService(
            session_factory=None,
            sse_manager=None,
            publish_func=publish_func,
            namespace="test",
            instance_id="test-0",
        )
        config = {"topic": "scheduled-tasks/notifications/result", "include_full_result": True}
        payload = {**_SAMPLE_PAYLOAD, "result_summary": "lots of data"}
        task = _make_task()

        await svc._send_broker_notification(config, payload, task)

        publish_func.assert_called_once()
        sent_payload = publish_func.call_args[0][1]
        assert sent_payload is payload

    @pytest.mark.asyncio
    async def test_raises_when_topic_not_configured(self):
        svc = _make_service()
        config = {}
        task = _make_task()

        with pytest.raises(ValueError, match="Broker topic not configured"):
            await svc._send_broker_notification(config, _SAMPLE_PAYLOAD, task)


# ---------------------------------------------------------------------------
# 5. TestSendSSENotification
# ---------------------------------------------------------------------------

class TestSendSSENotification:
    """Tests for NotificationService._send_sse_notification."""

    @pytest.mark.asyncio
    async def test_returns_early_when_no_sse_manager(self):
        svc = _make_service()
        assert svc.sse_manager is None
        # Should return without error
        await svc._send_sse_notification({}, _SAMPLE_PAYLOAD, _make_task())

    @pytest.mark.asyncio
    async def test_calls_sse_manager_with_correct_params(self):
        mock_sse = AsyncMock()
        svc = NotificationService(
            session_factory=None,
            sse_manager=mock_sse,
            publish_func=None,
            namespace="test",
            instance_id="test-0",
        )
        task = _make_task(id="task-42", user_id="u1")
        payload = {**_SAMPLE_PAYLOAD}

        await svc._send_sse_notification({}, payload, task)

        mock_sse.send_event.assert_called_once_with(
            task_id="scheduled_task-42",
            event_data=payload,
            event_type="scheduled_task_complete",
        )


# ---------------------------------------------------------------------------
# 6. TestSendWebhookNotification
# ---------------------------------------------------------------------------

class TestSendWebhookNotification:
    """Tests for NotificationService._send_webhook_notification."""

    @pytest.mark.asyncio
    async def test_raises_when_url_not_configured(self):
        svc = _make_service()
        config = {}
        task = _make_task()

        with pytest.raises(ValueError, match="Webhook URL not configured"):
            await svc._send_webhook_notification(config, _SAMPLE_PAYLOAD, task)

    @pytest.mark.asyncio
    @patch(
        "solace_agent_mesh.gateway.http_sse.services.scheduler.notification_service._validate_webhook_url"
    )
    async def test_adds_content_type_header_if_missing(self, mock_validate):
        svc = _make_service()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        svc.http_client = AsyncMock()
        svc.http_client.request = AsyncMock(return_value=mock_response)

        config = {"url": "https://example.com/hook", "headers": {}}
        task = _make_task()

        await svc._send_webhook_notification(config, _SAMPLE_PAYLOAD, task)

        call_kwargs = svc.http_client.request.call_args
        headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers")
        assert headers["Content-Type"] == "application/json"


# ---------------------------------------------------------------------------
# 7. TestCleanup
# ---------------------------------------------------------------------------

class TestCleanup:
    """Tests for NotificationService.cleanup."""

    @pytest.mark.asyncio
    async def test_cleanup_closes_http_client(self):
        svc = _make_service()
        svc.http_client = AsyncMock()

        await svc.cleanup()

        svc.http_client.aclose.assert_called_once()
