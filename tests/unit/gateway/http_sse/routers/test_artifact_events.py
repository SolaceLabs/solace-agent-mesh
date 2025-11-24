#!/usr/bin/env python3
"""
Unit tests for artifact creation event publishing.

Tests verify that artifact upload triggers proper event emission through the SAM event service,
following the same pattern as session deletion events.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone

from fastapi import UploadFile

from solace_agent_mesh.gateway.http_sse.routers.artifacts import (
    upload_artifact_with_session,
)
from solace_agent_mesh.gateway.http_sse.session_manager import SessionManager
from solace_agent_mesh.gateway.http_sse.services.session_service import SessionService
from sqlalchemy.orm import Session

try:
    from google.adk.artifacts import BaseArtifactService
except ImportError:
    class BaseArtifactService:
        pass


class TestArtifactCreatedEvent:
    """Test that artifact upload publishes artifact.created events."""

    @pytest.fixture
    def mock_dependencies(self):
        """Create mock dependencies for artifact upload with event publishing."""
        # Mock FastAPI Request
        mock_request = MagicMock()
        mock_request.headers = {}

        # Mock UploadFile with chunked reading simulation
        mock_upload_file = MagicMock(spec=UploadFile)
        mock_upload_file.filename = "test.txt"
        mock_upload_file.content_type = "text/plain"

        # Simulate chunked reading
        async def mock_read_chunks(size=-1):
            if not hasattr(mock_read_chunks, 'called'):
                mock_read_chunks.called = True
                return b"test content"
            return b""  # EOF

        mock_upload_file.read = mock_read_chunks
        mock_upload_file.close = AsyncMock()

        # Mock artifact service
        mock_artifact_service = MagicMock(spec=BaseArtifactService)

        # Mock session manager
        mock_session_manager = MagicMock(spec=SessionManager)
        mock_session_manager.create_new_session_id.return_value = "test-session-123"

        # Mock session service
        mock_session_service = MagicMock(spec=SessionService)
        mock_session_service.create_session = MagicMock()

        # Mock database session
        mock_db = MagicMock(spec=Session)
        mock_db.commit = MagicMock()
        mock_db.rollback = MagicMock()

        # Mock component with sam_events
        mock_component = MagicMock()
        def mock_get_config(key, default=None):
            if key == "name":
                return "TestApp"
            elif key == "gateway_max_upload_size_bytes":
                return 100 * 1024 * 1024  # 100MB
            return default
        mock_component.get_config.side_effect = mock_get_config
        mock_component.gateway_id = "test-gateway"

        # Mock sam_events service
        mock_sam_events = MagicMock()
        mock_sam_events.publish_artifact_created = MagicMock(return_value=True)
        mock_component.sam_events = mock_sam_events

        # Mock validation functions
        mock_validate_session = MagicMock(return_value=True)

        return {
            'request': mock_request,
            'upload_file': mock_upload_file,
            'artifact_service': mock_artifact_service,
            'session_manager': mock_session_manager,
            'session_service': mock_session_service,
            'db': mock_db,
            'component': mock_component,
            'validate_session': mock_validate_session,
            'user_id': 'test-user-123',
            'user_config': {'tool:artifact:create': True}
        }

    @pytest.mark.asyncio
    async def test_artifact_upload_publishes_event_when_enabled(self, mock_dependencies):
        """Test that artifact upload publishes artifact.created event when sam_events is available."""
        # Setup
        deps = mock_dependencies

        # Mock successful upload result
        with patch('solace_agent_mesh.gateway.http_sse.routers.artifacts.process_artifact_upload') as mock_process:
            mock_process.return_value = {
                'status': 'success',
                'artifact_uri': 'artifact://TestApp/test-user-123/test-session-123/test.txt?version=1',
                'version': 1
            }

            # Execute
            result = await upload_artifact_with_session(
                request=deps['request'],
                upload_file=deps['upload_file'],
                sessionId="test-session-123",
                filename="test.txt",
                metadata_json='{"description": "Test file"}',
                artifact_service=deps['artifact_service'],
                user_id=deps['user_id'],
                validate_session=deps['validate_session'],
                component=deps['component'],
                user_config=deps['user_config'],
                session_manager=deps['session_manager'],
                session_service=deps['session_service'],
                db=deps['db']
            )

            # Verify the event was published
            mock_sam_events = deps['component'].sam_events
            mock_sam_events.publish_artifact_created.assert_called_once()

            # Verify event parameters
            call_args = mock_sam_events.publish_artifact_created.call_args
            assert call_args.kwargs['session_id'] == "test-session-123"
            assert call_args.kwargs['user_id'] == "test-user-123"
            assert call_args.kwargs['filename'] == "test.txt"
            assert call_args.kwargs['size'] == 12  # len(b"test content")
            assert call_args.kwargs['mime_type'] == "text/plain"
            assert call_args.kwargs['artifact_uri'] == 'artifact://TestApp/test-user-123/test-session-123/test.txt?version=1'
            assert call_args.kwargs['version'] == 1

    @pytest.mark.asyncio
    async def test_artifact_upload_without_sam_events(self, mock_dependencies):
        """Test that artifact upload succeeds even when sam_events is not available."""
        # Setup
        deps = mock_dependencies
        # Remove sam_events to simulate it not being available
        delattr(deps['component'], 'sam_events')

        # Mock successful upload result
        with patch('solace_agent_mesh.gateway.http_sse.routers.artifacts.process_artifact_upload') as mock_process:
            mock_process.return_value = {
                'status': 'success',
                'artifact_uri': 'artifact://TestApp/test-user-123/test-session-123/test.txt?version=1',
                'version': 1
            }

            # Execute - should not raise exception
            result = await upload_artifact_with_session(
                request=deps['request'],
                upload_file=deps['upload_file'],
                sessionId="test-session-123",
                filename="test.txt",
                metadata_json=None,
                artifact_service=deps['artifact_service'],
                user_id=deps['user_id'],
                validate_session=deps['validate_session'],
                component=deps['component'],
                user_config=deps['user_config'],
                session_manager=deps['session_manager'],
                session_service=deps['session_service'],
                db=deps['db']
            )

            # Verify upload succeeded despite no event service
            assert result.session_id == "test-session-123"
            assert result.filename == "test.txt"

    @pytest.mark.asyncio
    async def test_artifact_upload_event_publish_failure_does_not_block(self, mock_dependencies):
        """Test that event publish failure does not prevent artifact upload."""
        # Setup
        deps = mock_dependencies
        # Make event publishing fail
        deps['component'].sam_events.publish_artifact_created.return_value = False

        # Mock successful upload result
        with patch('solace_agent_mesh.gateway.http_sse.routers.artifacts.process_artifact_upload') as mock_process:
            mock_process.return_value = {
                'status': 'success',
                'artifact_uri': 'artifact://TestApp/test-user-123/test-session-123/test.txt?version=1',
                'version': 1
            }

            # Execute - should not raise exception
            result = await upload_artifact_with_session(
                request=deps['request'],
                upload_file=deps['upload_file'],
                sessionId="test-session-123",
                filename="test.txt",
                metadata_json=None,
                artifact_service=deps['artifact_service'],
                user_id=deps['user_id'],
                validate_session=deps['validate_session'],
                component=deps['component'],
                user_config=deps['user_config'],
                session_manager=deps['session_manager'],
                session_service=deps['session_service'],
                db=deps['db']
            )

            # Verify upload still succeeded
            assert result.session_id == "test-session-123"
            assert result.filename == "test.txt"

            # Verify event publishing was attempted
            deps['component'].sam_events.publish_artifact_created.assert_called_once()

    @pytest.mark.asyncio
    async def test_artifact_upload_publishes_event_with_various_file_types(self, mock_dependencies):
        """Test that event is published correctly for various file types."""
        # Setup
        deps = mock_dependencies

        test_cases = [
            ("image.png", "image/png", b"\x89PNG\r\n\x1a\n" + b"x" * 100),
            ("document.pdf", "application/pdf", b"%PDF-1.4" + b"x" * 100),
            ("data.json", "application/json", b'{"key": "value"}'),
        ]

        for filename, mime_type, content in test_cases:
            # Reset mock
            deps['component'].sam_events.publish_artifact_created.reset_mock()

            deps['upload_file'].filename = filename
            deps['upload_file'].content_type = mime_type

            # Simulate chunked reading for each file type
            async def mock_read_file_chunks(size=-1, file_content=content):
                if not hasattr(mock_read_file_chunks, 'called'):
                    mock_read_file_chunks.called = True
                    return file_content
                return b""  # EOF

            deps['upload_file'].read = mock_read_file_chunks

            # Mock successful upload result
            with patch('solace_agent_mesh.gateway.http_sse.routers.artifacts.process_artifact_upload') as mock_process:
                mock_process.return_value = {
                    'status': 'success',
                    'artifact_uri': f'artifact://TestApp/test-user-123/test-session-123/{filename}?version=1',
                    'version': 1
                }

                # Execute
                result = await upload_artifact_with_session(
                    request=deps['request'],
                    upload_file=deps['upload_file'],
                    sessionId="test-session-123",
                    filename=filename,
                    metadata_json=None,
                    artifact_service=deps['artifact_service'],
                    user_id=deps['user_id'],
                    validate_session=deps['validate_session'],
                    component=deps['component'],
                    user_config=deps['user_config'],
                    session_manager=deps['session_manager'],
                    session_service=deps['session_service'],
                    db=deps['db']
                )

                # Verify event was published with correct mime type and size
                mock_sam_events = deps['component'].sam_events
                mock_sam_events.publish_artifact_created.assert_called_once()

                call_args = mock_sam_events.publish_artifact_created.call_args
                assert call_args.kwargs['filename'] == filename
                assert call_args.kwargs['mime_type'] == mime_type
                assert call_args.kwargs['size'] == len(content)

    @pytest.mark.asyncio
    async def test_artifact_upload_event_on_new_session_creation(self, mock_dependencies):
        """Test that event is published with correct session_id when new session is created."""
        # Setup
        deps = mock_dependencies

        # Mock successful upload result
        with patch('solace_agent_mesh.gateway.http_sse.routers.artifacts.process_artifact_upload') as mock_process:
            mock_process.return_value = {
                'status': 'success',
                'artifact_uri': 'artifact://TestApp/test-user-123/new-session-123/test.txt?version=1',
                'version': 1
            }

            # Mock session creation
            deps['session_manager'].create_new_session_id.return_value = "new-session-123"

            # Execute with no session ID (triggers new session creation)
            result = await upload_artifact_with_session(
                request=deps['request'],
                upload_file=deps['upload_file'],
                sessionId=None,  # No session ID provided
                filename="test.txt",
                metadata_json=None,
                artifact_service=deps['artifact_service'],
                user_id=deps['user_id'],
                validate_session=deps['validate_session'],
                component=deps['component'],
                user_config=deps['user_config'],
                session_manager=deps['session_manager'],
                session_service=deps['session_service'],
                db=deps['db']
            )

            # Verify event was published with the new session ID
            mock_sam_events = deps['component'].sam_events
            mock_sam_events.publish_artifact_created.assert_called_once()

            call_args = mock_sam_events.publish_artifact_created.call_args
            assert call_args.kwargs['session_id'] == "new-session-123"
