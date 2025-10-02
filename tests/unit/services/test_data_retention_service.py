"""
Unit tests for DataRetentionService.

Tests configuration validation, cleanup logic, and error handling
for the automatic data retention service that removes old tasks and feedback.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime, timedelta, timezone

from solace_agent_mesh.gateway.http_sse.services.data_retention_service import (
    DataRetentionService,
)
from solace_agent_mesh.gateway.http_sse.repository.task_repository import (
    TaskRepository,
)
from solace_agent_mesh.gateway.http_sse.repository.feedback_repository import (
    FeedbackRepository,
)
from solace_agent_mesh.gateway.http_sse.repository.models import (
    TaskModel,
    TaskEventModel,
    FeedbackModel,
)
from solace_agent_mesh.gateway.http_sse.shared import now_epoch_ms
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine


# Test classes will be added in subsequent phases
