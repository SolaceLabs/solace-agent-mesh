"""Unit tests for scheduled task DTO validation."""

import pytest
from unittest.mock import MagicMock
from pydantic import ValidationError

from solace_agent_mesh.gateway.http_sse.routers.dto.scheduled_task_dto import (
    CreateScheduledTaskRequest,
    ExecutionResponse,
    SchedulePreviewRequest,
)


def _valid_create_kwargs(**overrides):
    """Return a minimal valid keyword set for CreateScheduledTaskRequest."""
    base = {
        "name": "Daily report",
        "schedule_type": "cron",
        "schedule_expression": "0 9 * * *",
        "timezone": "UTC",
        "target_agent_name": "report-agent",
        "target_type": "agent",
        "task_message": [{"type": "text", "text": "Generate report"}],
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# TestCreateScheduledTaskRequest
# ---------------------------------------------------------------------------


class TestCreateScheduledTaskRequest:
    """Validate field-level rules on CreateScheduledTaskRequest."""

    def test_valid_cron_expression_accepted(self):
        """A standard five-field cron expression passes validation."""
        req = CreateScheduledTaskRequest(**_valid_create_kwargs(
            schedule_type="cron",
            schedule_expression="*/5 * * * *",
        ))
        assert req.schedule_expression == "*/5 * * * *"

    def test_invalid_cron_expression_rejected(self):
        """An invalid cron string raises a ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            CreateScheduledTaskRequest(**_valid_create_kwargs(
                schedule_type="cron",
                schedule_expression="not-a-cron",
            ))
        assert "cron" in str(exc_info.value).lower()

    @pytest.mark.parametrize("expr", ["30m", "1h", "1d"])
    def test_valid_interval_formats_accepted(self, expr):
        """Common interval shorthand (30m, 1h, 1d) passes validation."""
        req = CreateScheduledTaskRequest(**_valid_create_kwargs(
            schedule_type="interval",
            schedule_expression=expr,
        ))
        assert req.schedule_expression == expr

    def test_invalid_interval_format_rejected(self):
        """An interval missing a valid suffix is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            CreateScheduledTaskRequest(**_valid_create_kwargs(
                schedule_type="interval",
                schedule_expression="abc",
            ))
        assert "interval" in str(exc_info.value).lower()

    def test_valid_timezone_accepted(self):
        """A known IANA timezone passes validation."""
        req = CreateScheduledTaskRequest(**_valid_create_kwargs(timezone="America/New_York"))
        assert req.timezone == "America/New_York"

    def test_invalid_timezone_rejected(self):
        """An unknown timezone string is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            CreateScheduledTaskRequest(**_valid_create_kwargs(timezone="Mars/Olympus"))
        assert "timezone" in str(exc_info.value).lower()

    def test_valid_target_type_accepted(self):
        """'agent' and 'workflow' are the only valid target types."""
        for tt in ("agent", "workflow"):
            req = CreateScheduledTaskRequest(**_valid_create_kwargs(target_type=tt))
            assert req.target_type == tt

    def test_invalid_target_type_rejected(self):
        """An unsupported target_type is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            CreateScheduledTaskRequest(**_valid_create_kwargs(target_type="lambda"))
        assert "target_type" in str(exc_info.value).lower()

    def test_one_time_with_iso8601_accepted(self):
        """A one_time schedule with a valid ISO 8601 datetime passes."""
        req = CreateScheduledTaskRequest(**_valid_create_kwargs(
            schedule_type="one_time",
            schedule_expression="2025-12-31T23:59:00",
        ))
        assert req.schedule_type == "one_time"


# ---------------------------------------------------------------------------
# TestExecutionResponseFromOrm
# ---------------------------------------------------------------------------


class TestExecutionResponseFromOrm:
    """Validate the ``ExecutionResponse.from_orm`` classmethod."""

    def _mock_execution(self, **overrides):
        """Build a mock ORM execution object."""
        obj = MagicMock()
        obj.id = overrides.get("id", "exec-1")
        obj.scheduled_task_id = overrides.get("scheduled_task_id", "task-1")
        obj.status = overrides.get("status", "completed")
        obj.a2a_task_id = overrides.get("a2a_task_id", "a2a-1")
        obj.scheduled_for = overrides.get("scheduled_for", 1700000000000)
        obj.started_at = overrides.get("started_at", 1700000001000)
        obj.completed_at = overrides.get("completed_at", 1700000010000)
        obj.result_summary = overrides.get("result_summary", None)
        obj.error_message = overrides.get("error_message", None)
        obj.retry_count = overrides.get("retry_count", 0)
        obj.trigger_type = overrides.get("trigger_type", "scheduled")
        obj.triggered_by = overrides.get("triggered_by", None)
        obj.artifacts = overrides.get("artifacts", None)
        obj.notifications_sent = overrides.get("notifications_sent", None)
        return obj

    def test_calculates_duration_ms_when_both_timestamps_present(self):
        """duration_ms = completed_at - started_at when both are set."""
        obj = self._mock_execution(started_at=1000, completed_at=5000)
        resp = ExecutionResponse.from_orm(obj)
        assert resp.duration_ms == 4000

    def test_duration_ms_none_when_started_at_missing(self):
        """duration_ms is None when started_at is not set."""
        obj = self._mock_execution(started_at=None, completed_at=5000)
        resp = ExecutionResponse.from_orm(obj)
        assert resp.duration_ms is None

    def test_duration_ms_none_when_completed_at_missing(self):
        """duration_ms is None when completed_at is not set."""
        obj = self._mock_execution(started_at=1000, completed_at=None)
        resp = ExecutionResponse.from_orm(obj)
        assert resp.duration_ms is None


# ---------------------------------------------------------------------------
# TestSchedulePreviewRequest
# ---------------------------------------------------------------------------


class TestSchedulePreviewRequest:
    """Validate timezone validation on SchedulePreviewRequest."""

    def test_valid_timezone_accepted(self):
        """A known IANA timezone passes validation."""
        req = SchedulePreviewRequest(
            schedule_type="cron",
            schedule_expression="0 9 * * *",
            timezone="Europe/London",
        )
        assert req.timezone == "Europe/London"

    def test_invalid_timezone_rejected(self):
        """An unknown timezone string is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            SchedulePreviewRequest(
                schedule_type="cron",
                schedule_expression="0 9 * * *",
                timezone="Invalid/Zone",
            )
        assert "timezone" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# TestNameAndDescriptionStripping
# ---------------------------------------------------------------------------


class TestNameAndDescriptionStripping:
    """Tests that name/description trim whitespace so visual duplicates can't exist."""

    def test_create_strips_trailing_spaces_on_name(self):
        req = CreateScheduledTaskRequest(**_valid_create_kwargs(name="Daily report "))
        assert req.name == "Daily report"

    def test_create_strips_leading_and_trailing_spaces_on_name(self):
        req = CreateScheduledTaskRequest(**_valid_create_kwargs(name="  Daily report  "))
        assert req.name == "Daily report"

    def test_create_strips_surrounding_tabs_and_newlines(self):
        req = CreateScheduledTaskRequest(**_valid_create_kwargs(name="\tDaily report\n"))
        assert req.name == "Daily report"

    def test_create_preserves_interior_whitespace(self):
        req = CreateScheduledTaskRequest(**_valid_create_kwargs(name="  My  Daily  Report  "))
        assert req.name == "My  Daily  Report"

    def test_create_strips_description(self):
        req = CreateScheduledTaskRequest(**_valid_create_kwargs(description="  a summary  "))
        assert req.description == "a summary"

    def test_create_rejects_whitespace_only_name(self):
        """A name of only whitespace strips to "" and must fail min_length=1."""
        with pytest.raises(ValidationError):
            CreateScheduledTaskRequest(**_valid_create_kwargs(name="   "))

    def test_update_strips_name_when_provided(self):
        from solace_agent_mesh.gateway.http_sse.routers.dto.scheduled_task_dto import (
            UpdateScheduledTaskRequest,
        )
        req = UpdateScheduledTaskRequest(name="Renamed ")
        assert req.name == "Renamed"

    def test_update_leaves_name_untouched_when_omitted(self):
        from solace_agent_mesh.gateway.http_sse.routers.dto.scheduled_task_dto import (
            UpdateScheduledTaskRequest,
        )
        req = UpdateScheduledTaskRequest()
        assert req.name is None
