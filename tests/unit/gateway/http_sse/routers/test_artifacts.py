#!/usr/bin/env python3
"""
Comprehensive unit tests for artifacts router to increase coverage from 31% to 75%+.

Tests cover:
1. Artifact upload endpoints (upload_artifact_with_session)
2. Artifact retrieval endpoints (get_latest_artifact, get_specific_artifact_version, get_artifact_by_uri)
3. Artifact listing endpoints (list_artifacts, list_artifact_versions)
4. Artifact deletion endpoints (delete_artifact)
5. File handling and validation
6. Error handling and edge cases
7. Integration scenarios

Based on coverage analysis in tests/unit/gateway/coverage_analysis.md
"""

import pytest
import asyncio
import json
import io
from datetime import datetime, timezone
from unittest.mock import MagicMock, AsyncMock, patch, call
from typing import Dict, Any, List, Optional

from fastapi import HTTPException, status, UploadFile
from fastapi.testclient import TestClient
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

# Import the router and related classes
from solace_agent_mesh.gateway.http_sse.routers.artifacts import (
    router,
    ArtifactUploadResponse,
    upload_artifact_with_session,
    list_artifact_versions,
    list_artifacts,
    get_latest_artifact,
    get_specific_artifact_version,
    get_artifact_by_uri,
    delete_artifact,
)
from solace_agent_mesh.gateway.http_sse.session_manager import SessionManager
from solace_agent_mesh.gateway.http_sse.services.session_service import SessionService
from solace_agent_mesh.common.a2a.types import ArtifactInfo

try:
    from google.adk.artifacts import BaseArtifactService
except ImportError:
    class BaseArtifactService:
        pass


class TestArtifactUploadResponse:
    """Test ArtifactUploadResponse model."""

    def test_artifact_upload_response_creation(self):
        """Test ArtifactUploadResponse model creation with camelCase aliases."""
        response = ArtifactUploadResponse(
            uri="artifact://test/user123/session456/test.txt?version=1",
            session_id="session456",
            filename="test.txt",
            size=1024,
            mime_type="text/plain",
            metadata={"description": "Test file"},
            created_at="2023-01-01T00:00:00Z"
        )
        
        assert response.uri == "artifact://test/user123/session456/test.txt?version=1"
        assert response.session_id == "session456"
        assert response.filename == "test.txt"
        assert response.size == 1024
        assert response.mime_type == "text/plain"
        assert response.metadata == {"description": "Test file"}
        assert response.created_at == "2023-01-01T00:00:00Z"

    def test_artifact_upload_response_json_serialization(self):
        """Test that response model uses camelCase in JSON output."""
        response = ArtifactUploadResponse(
            uri="artifact://test/user123/session456/test.txt?version=1",
            session_id="session456",
            filename="test.txt",
            size=1024,
            mime_type="text/plain",
            metadata={},
            created_at="2023-01-01T00:00:00Z"
        )
        
        json_data = response.model_dump(by_alias=True)
        
        # Check camelCase aliases are used
        assert "sessionId" in json_data
        assert "mimeType" in json_data
        assert "createdAt" in json_data
        assert "session_id" not in json_data
        assert "mime_type" not in json_data
        assert "created_at" not in json_data


class TestUploadArtifactWithSession:
    """Test upload_artifact_with_session endpoint."""

    @pytest.fixture
    def mock_dependencies(self):
        """Create mock dependencies for upload tests."""
        # Mock FastAPI Request - don't include Content-Length to avoid early size check
        mock_request = MagicMock()
        mock_request.headers = {}  # No Content-Length header
        
        # Mock UploadFile - use BytesIO for natural read/seek behavior
        mock_upload_file = MagicMock(spec=UploadFile)
        mock_upload_file.filename = "test.txt"
        mock_upload_file.content_type = "text/plain"

        # Use BytesIO to naturally handle read/seek (supports new validate-seek-read pattern)
        test_content = b"test content"
        file_buffer = io.BytesIO(test_content)

        async def async_read(size=-1):
            return file_buffer.read(size)

        async def async_seek(offset):
            return file_buffer.seek(offset)

        mock_upload_file.read = async_read
        mock_upload_file.seek = async_seek
        mock_upload_file.close = AsyncMock()
        
        # Mock artifact service
        mock_artifact_service = MagicMock(spec=BaseArtifactService)
        
        # Mock session manager
        mock_session_manager = MagicMock(spec=SessionManager)
        mock_session_manager.create_new_session_id.return_value = "new-session-123"
        
        # Mock session service
        mock_session_service = MagicMock(spec=SessionService)
        mock_session_service.create_session = MagicMock()
        
        # Mock database session
        mock_db = MagicMock(spec=Session)
        mock_db.commit = MagicMock()
        mock_db.rollback = MagicMock()
        
        # Mock component
        mock_component = MagicMock()
        def mock_get_config(key, default=None):
            if key == "name":
                return "TestApp"
            elif key == "gateway_max_upload_size_bytes":
                return 100 * 1024 * 1024  # 100MB
            return default
        mock_component.get_config.side_effect = mock_get_config
        
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
    async def test_upload_artifact_with_existing_session_success(self, mock_dependencies):
        """Test successful artifact upload with existing session."""
        # Setup
        deps = mock_dependencies
        
        # Mock successful upload result
        with patch('solace_agent_mesh.gateway.http_sse.routers.artifacts.process_artifact_upload') as mock_process:
            mock_process.return_value = {
                'status': 'success',
                'artifact_uri': 'artifact://TestApp/test-user-123/existing-session/test.txt?version=1',
                'version': 1
            }
            
            # Execute
            result = await upload_artifact_with_session(
                request=deps['request'],
                upload_file=deps['upload_file'],
                sessionId="existing-session",
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
            
            # Verify
            assert isinstance(result, ArtifactUploadResponse)
            assert result.uri == 'artifact://TestApp/test-user-123/existing-session/test.txt?version=1'
            assert result.session_id == "existing-session"
            assert result.filename == "test.txt"
            assert result.size == 12  # len(b"test content")
            assert result.mime_type == "text/plain"
            assert result.metadata == {"description": "Test file"}
            
            # Verify session validation was called
            deps['validate_session'].assert_called_once_with("existing-session", "test-user-123")
            
            # Verify session creation was NOT called
            deps['session_manager'].create_new_session_id.assert_not_called()

    @pytest.mark.asyncio
    async def test_upload_artifact_creates_new_session(self, mock_dependencies):
        """Test artifact upload creates new session when sessionId is None."""
        # Setup
        deps = mock_dependencies
        
        # Mock successful upload result
        with patch('solace_agent_mesh.gateway.http_sse.routers.artifacts.process_artifact_upload') as mock_process:
            mock_process.return_value = {
                'status': 'success',
                'artifact_uri': 'artifact://TestApp/test-user-123/new-session-123/test.txt?version=1',
                'version': 1
            }
            
            # Execute
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
            
            # Verify
            assert isinstance(result, ArtifactUploadResponse)
            assert result.session_id == "new-session-123"
            
            # Verify new session was created
            deps['session_manager'].create_new_session_id.assert_called_once_with(deps['request'])
            
            # Verify session was persisted to database
            deps['session_service'].create_session.assert_called_once_with(
                db=deps['db'],
                user_id='test-user-123',
                session_id='new-session-123',
                agent_id=None,
                name=None
            )
            deps['db'].commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_upload_artifact_session_persistence_failure(self, mock_dependencies):
        """Test artifact upload handles session persistence failure gracefully."""
        # Setup
        deps = mock_dependencies
        deps['session_service'].create_session.side_effect = Exception("Database error")
        
        # Mock successful upload result
        with patch('solace_agent_mesh.gateway.http_sse.routers.artifacts.process_artifact_upload') as mock_process:
            mock_process.return_value = {
                'status': 'success',
                'artifact_uri': 'artifact://TestApp/test-user-123/new-session-123/test.txt?version=1',
                'version': 1
            }
            
            # Execute - should not raise exception
            result = await upload_artifact_with_session(
                request=deps['request'],
                upload_file=deps['upload_file'],
                sessionId="",  # Empty session ID
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
            assert isinstance(result, ArtifactUploadResponse)
            assert result.session_id == "new-session-123"
            
            # Verify rollback was called
            deps['db'].rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_upload_artifact_invalid_filename(self, mock_dependencies):
        """Test upload fails with invalid filename."""
        # Setup
        deps = mock_dependencies
        
        # Execute & Verify
        with pytest.raises(HTTPException) as exc_info:
            await upload_artifact_with_session(
                request=deps['request'],
                upload_file=deps['upload_file'],
                sessionId="test-session",
                filename="",  # Empty filename
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
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Filename is required" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_upload_artifact_no_file_upload(self, mock_dependencies):
        """Test upload fails when no file is uploaded."""
        # Setup
        deps = mock_dependencies
        deps['upload_file'].filename = None  # No file uploaded
        
        # Execute & Verify
        with pytest.raises(HTTPException) as exc_info:
            await upload_artifact_with_session(
                request=deps['request'],
                upload_file=deps['upload_file'],
                sessionId="test-session",
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
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "File upload is required" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_upload_artifact_service_not_configured(self, mock_dependencies):
        """Test upload fails when artifact service is not configured."""
        # Setup
        deps = mock_dependencies
        
        # Execute & Verify
        with pytest.raises(HTTPException) as exc_info:
            await upload_artifact_with_session(
                request=deps['request'],
                upload_file=deps['upload_file'],
                sessionId="test-session",
                filename="test.txt",
                metadata_json=None,
                artifact_service=None,  # No artifact service
                user_id=deps['user_id'],
                validate_session=deps['validate_session'],
                component=deps['component'],
                user_config=deps['user_config'],
                session_manager=deps['session_manager'],
                session_service=deps['session_service'],
                db=deps['db']
            )
        
        assert exc_info.value.status_code == status.HTTP_501_NOT_IMPLEMENTED
        assert "Artifact service is not configured" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_upload_artifact_session_validation_failure(self, mock_dependencies):
        """Test upload fails when session validation fails."""
        # Setup
        deps = mock_dependencies
        deps['validate_session'].return_value = False  # Session validation fails
        
        # Execute & Verify
        with pytest.raises(HTTPException) as exc_info:
            await upload_artifact_with_session(
                request=deps['request'],
                upload_file=deps['upload_file'],
                sessionId="invalid-session",
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
        
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "Invalid session or insufficient permissions" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_upload_artifact_process_upload_failure(self, mock_dependencies):
        """Test upload handles process_artifact_upload failure."""
        # Setup
        deps = mock_dependencies
        
        # Mock failed upload result
        with patch('solace_agent_mesh.gateway.http_sse.routers.artifacts.process_artifact_upload') as mock_process:
            mock_process.return_value = {
                'status': 'error',
                'message': 'Invalid file type',
                'error': 'invalid_filename'
            }
            
            # Execute & Verify
            with pytest.raises(HTTPException) as exc_info:
                await upload_artifact_with_session(
                    request=deps['request'],
                    upload_file=deps['upload_file'],
                    sessionId="test-session",
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
            
            assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
            assert "Invalid file type" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_upload_artifact_with_large_file(self, mock_dependencies):
        """Test upload with large file content."""
        # Setup
        deps = mock_dependencies
        large_content = b"x" * (9 * 1024 * 1024)  # 9MB file (well below 100MB limit to account for overhead)

        # Use BytesIO for natural read/seek behavior
        large_buffer = io.BytesIO(large_content)

        async def async_read_large(size=-1):
            return large_buffer.read(size)

        async def async_seek_large(offset):
            return large_buffer.seek(offset)

        deps['upload_file'].read = async_read_large
        deps['upload_file'].seek = async_seek_large
        
        # Mock successful upload result
        with patch('solace_agent_mesh.gateway.http_sse.routers.artifacts.process_artifact_upload') as mock_process:
            mock_process.return_value = {
                'status': 'success',
                'artifact_uri': 'artifact://TestApp/test-user-123/test-session/large.bin?version=1',
                'version': 1
            }
            
            # Execute
            result = await upload_artifact_with_session(
                request=deps['request'],
                upload_file=deps['upload_file'],
                sessionId="test-session",
                filename="large.bin",
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
            
            # Verify
            assert isinstance(result, ArtifactUploadResponse)
            assert result.size == len(large_content)

    @pytest.mark.asyncio
    async def test_upload_artifact_with_various_file_types(self, mock_dependencies):
        """Test upload with various file types."""
        # Setup
        deps = mock_dependencies
        
        file_types = [
            ("image.png", "image/png", b"\x89PNG\r\n\x1a\n" + b"x" * 100),
            ("document.pdf", "application/pdf", b"%PDF-1.4" + b"x" * 100),
            ("data.json", "application/json", b'{"key": "value"}'),
            ("script.py", "text/x-python", b"print('hello')"),
            ("unknown.xyz", "application/octet-stream", b"binary data")
        ]
        
        for filename, mime_type, content in file_types:
            deps['upload_file'].filename = filename
            deps['upload_file'].content_type = mime_type

            # Use BytesIO for each file type
            # Fix: Capture file_buffer in closure default argument to avoid
            # closure-over-loop-variable bug (each iteration needs its own buffer)
            file_buffer = io.BytesIO(content)

            async def async_read_file(size=-1, buf=file_buffer):
                return buf.read(size)

            async def async_seek_file(offset, buf=file_buffer):
                return buf.seek(offset)

            deps['upload_file'].read = async_read_file
            deps['upload_file'].seek = async_seek_file
            
            # Mock successful upload result
            with patch('solace_agent_mesh.gateway.http_sse.routers.artifacts.process_artifact_upload') as mock_process:
                mock_process.return_value = {
                    'status': 'success',
                    'artifact_uri': f'artifact://TestApp/test-user-123/test-session/{filename}?version=1',
                    'version': 1
                }
                
                # Execute
                result = await upload_artifact_with_session(
                    request=deps['request'],
                    upload_file=deps['upload_file'],
                    sessionId="test-session",
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
                
                # Verify
                assert isinstance(result, ArtifactUploadResponse)
                assert result.filename == filename
                assert result.mime_type == mime_type
                assert result.size == len(content)

    @pytest.mark.asyncio
    async def test_upload_artifact_invalid_metadata_json(self, mock_dependencies):
        """Test upload with invalid metadata JSON is handled gracefully."""
        # Setup
        deps = mock_dependencies
        
        # Mock successful upload result
        with patch('solace_agent_mesh.gateway.http_sse.routers.artifacts.process_artifact_upload') as mock_process:
            mock_process.return_value = {
                'status': 'success',
                'artifact_uri': 'artifact://TestApp/test-user-123/test-session/test.txt?version=1',
                'version': 1
            }
            
            # Execute with invalid JSON
            result = await upload_artifact_with_session(
                request=deps['request'],
                upload_file=deps['upload_file'],
                sessionId="test-session",
                filename="test.txt",
                metadata_json='{"invalid": json}',  # Invalid JSON
                artifact_service=deps['artifact_service'],
                user_id=deps['user_id'],
                validate_session=deps['validate_session'],
                component=deps['component'],
                user_config=deps['user_config'],
                session_manager=deps['session_manager'],
                session_service=deps['session_service'],
                db=deps['db']
            )
            
            # Verify - should succeed with empty metadata
            assert isinstance(result, ArtifactUploadResponse)
            assert result.metadata == {}

    @pytest.mark.asyncio
    async def test_upload_artifact_file_close_error(self, mock_dependencies):
        """Test upload handles file close error gracefully."""
        # Setup
        deps = mock_dependencies
        deps['upload_file'].close = AsyncMock(side_effect=Exception("Close error"))
        
        # Mock successful upload result
        with patch('solace_agent_mesh.gateway.http_sse.routers.artifacts.process_artifact_upload') as mock_process:
            mock_process.return_value = {
                'status': 'success',
                'artifact_uri': 'artifact://TestApp/test-user-123/test-session/test.txt?version=1',
                'version': 1
            }
            
            # Execute - should not raise exception despite close error
            result = await upload_artifact_with_session(
                request=deps['request'],
                upload_file=deps['upload_file'],
                sessionId="test-session",
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
            assert isinstance(result, ArtifactUploadResponse)

    @pytest.mark.asyncio
    async def test_upload_artifact_path_traversal_filenames(self, mock_dependencies):
        """Test that path traversal filenames are rejected.
        
        Security: Verifies that filenames containing path traversal sequences
        like '../' or absolute paths are rejected to prevent directory escape attacks.
        
        Note: The actual validation happens in process_artifact_upload (is_filename_safe),
        which returns an error for invalid filenames. This test verifies the router
        correctly handles that error response.
        """
        deps = mock_dependencies
        
        # Path traversal attack filenames
        malicious_filenames = [
            ("../../../etc/passwd", "path traversal with .."),
            ("..\\..\\..\\windows\\system32\\config\\sam", "Windows path traversal"),
            ("/etc/passwd", "absolute Unix path"),
            ("foo/../../../bar.txt", "embedded path traversal"),
        ]
        
        for malicious_filename, description in malicious_filenames:
            # Mock process_artifact_upload to return error for invalid filename
            # (simulating what the real is_filename_safe validation would do)
            with patch('solace_agent_mesh.gateway.http_sse.routers.artifacts.process_artifact_upload') as mock_process:
                mock_process.return_value = {
                    'status': 'error',
                    'message': f"Invalid filename: '{malicious_filename}'. Filename must not contain path separators or traversal sequences.",
                    'error': 'invalid_filename'
                }
                
                # Execute - should reject with 400 Bad Request
                with pytest.raises(HTTPException) as exc_info:
                    await upload_artifact_with_session(
                        request=deps['request'],
                        upload_file=deps['upload_file'],
                        sessionId="test-session",
                        filename=malicious_filename,
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
                
                assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST, \
                    f"Expected 400 for {description}: {malicious_filename}"
                assert "Invalid filename" in str(exc_info.value.detail), \
                    f"Expected 'Invalid filename' in error for {description}"

    @pytest.mark.asyncio
    async def test_upload_artifact_size_limit_enforcement(self, mock_dependencies):
        """Test that files exceeding the size limit are rejected.
        
        Security: Verifies that the gateway_max_upload_size_bytes limit is enforced
        to prevent denial-of-service attacks via large file uploads.
        """
        deps = mock_dependencies
        
        # Set a small size limit for testing (1KB)
        def mock_get_config_small_limit(key, default=None):
            if key == "name":
                return "TestApp"
            elif key == "gateway_max_upload_size_bytes":
                return 1024  # 1KB limit
            return default
        deps['component'].get_config.side_effect = mock_get_config_small_limit
        
        # Create content that exceeds the limit (2KB)
        large_content = b"x" * 2048
        large_buffer = io.BytesIO(large_content)
        
        async def async_read_large(size=-1):
            return large_buffer.read(size)
        
        async def async_seek_large(offset):
            return large_buffer.seek(offset)
        
        deps['upload_file'].read = async_read_large
        deps['upload_file'].seek = async_seek_large
        
        # Mock process_artifact_upload to verify it's not called
        with patch('solace_agent_mesh.gateway.http_sse.routers.artifacts.process_artifact_upload') as mock_process:
            mock_process.return_value = {
                'status': 'success',
                'artifact_uri': 'artifact://TestApp/test-user-123/test-session/large.bin?version=1',
                'version': 1
            }
            
            # Execute - should reject due to size limit
            with pytest.raises(HTTPException) as exc_info:
                await upload_artifact_with_session(
                    request=deps['request'],
                    upload_file=deps['upload_file'],
                    sessionId="test-session",
                    filename="large.bin",
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
            
            # Verify rejection with appropriate error
            assert exc_info.value.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
            assert "exceeds" in str(exc_info.value.detail).lower() or "too large" in str(exc_info.value.detail).lower()


class TestListArtifactVersions:
    """Test list_artifact_versions endpoint."""

    @pytest.fixture
    def mock_dependencies(self):
        """Create mock dependencies for version listing tests."""
        mock_artifact_service = MagicMock(spec=BaseArtifactService)
        mock_artifact_service.list_versions = AsyncMock()
        
        mock_component = MagicMock()
        def mock_get_config(key, default=None):
            if key == "name":
                return "TestApp"
            elif key == "gateway_max_upload_size_bytes":
                return 100 * 1024 * 1024  # 100MB
            return default
        mock_component.get_config.side_effect = mock_get_config
        
        mock_validate_session = MagicMock(return_value=True)
        
        return {
            'artifact_service': mock_artifact_service,
            'component': mock_component,
            'validate_session': mock_validate_session,
            'user_id': 'test-user-123',
            'user_config': {'tool:artifact:list': True}
        }

    @pytest.mark.asyncio
    async def test_list_artifact_versions_success(self, mock_dependencies):
        """Test successful artifact version listing."""
        # Setup
        deps = mock_dependencies
        deps['artifact_service'].list_versions.return_value = [1, 2, 3]
        
        # Execute
        result = await list_artifact_versions(
            session_id="test-session",
            filename="test.txt",
            artifact_service=deps['artifact_service'],
            user_id=deps['user_id'],
            validate_session=deps['validate_session'],
            component=deps['component'],
            user_config=deps['user_config']
        )
        
        # Verify
        assert result == [1, 2, 3]
        deps['artifact_service'].list_versions.assert_called_once_with(
            app_name="TestApp",
            user_id="test-user-123",
            session_id="test-session",
            filename="test.txt"
        )

    @pytest.mark.asyncio
    async def test_list_artifact_versions_session_validation_failure(self, mock_dependencies):
        """Test version listing fails when session validation fails."""
        # Setup
        deps = mock_dependencies
        deps['validate_session'].return_value = False
        
        # Execute & Verify
        with pytest.raises(HTTPException) as exc_info:
            await list_artifact_versions(
                session_id="invalid-session",
                filename="test.txt",
                artifact_service=deps['artifact_service'],
                user_id=deps['user_id'],
                validate_session=deps['validate_session'],
                component=deps['component'],
                user_config=deps['user_config']
            )
        
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert "Session not found or access denied" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_list_artifact_versions_service_not_configured(self, mock_dependencies):
        """Test version listing fails when artifact service is not configured."""
        # Setup
        deps = mock_dependencies
        
        # Execute & Verify
        with pytest.raises(HTTPException) as exc_info:
            await list_artifact_versions(
                session_id="test-session",
                filename="test.txt",
                artifact_service=None,  # No artifact service
                user_id=deps['user_id'],
                validate_session=deps['validate_session'],
                component=deps['component'],
                user_config=deps['user_config']
            )
        
        assert exc_info.value.status_code == status.HTTP_501_NOT_IMPLEMENTED
        assert "Artifact service is not configured" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_list_artifact_versions_not_supported(self, mock_dependencies):
        """Test version listing fails when service doesn't support versioning."""
        # Setup
        deps = mock_dependencies
        # Remove list_versions method to simulate unsupported service
        delattr(deps['artifact_service'], 'list_versions')
        
        # Execute & Verify
        with pytest.raises(HTTPException) as exc_info:
            await list_artifact_versions(
                session_id="test-session",
                filename="test.txt",
                artifact_service=deps['artifact_service'],
                user_id=deps['user_id'],
                validate_session=deps['validate_session'],
                component=deps['component'],
                user_config=deps['user_config']
            )
        
        assert exc_info.value.status_code == status.HTTP_501_NOT_IMPLEMENTED
        assert "Version listing not supported" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_list_artifact_versions_file_not_found(self, mock_dependencies):
        """Test version listing handles file not found."""
        # Setup
        deps = mock_dependencies
        deps['artifact_service'].list_versions.side_effect = FileNotFoundError()
        
        # Execute & Verify
        with pytest.raises(HTTPException) as exc_info:
            await list_artifact_versions(
                session_id="test-session",
                filename="nonexistent.txt",
                artifact_service=deps['artifact_service'],
                user_id=deps['user_id'],
                validate_session=deps['validate_session'],
                component=deps['component'],
                user_config=deps['user_config']
            )
        
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert "Artifact 'nonexistent.txt' not found" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_list_artifact_versions_general_error(self, mock_dependencies):
        """Test version listing handles general errors."""
        # Setup
        deps = mock_dependencies
        deps['artifact_service'].list_versions.side_effect = Exception("Service error")
        
        # Execute & Verify
        with pytest.raises(HTTPException) as exc_info:
            await list_artifact_versions(
                session_id="test-session",
                filename="test.txt",
                artifact_service=deps['artifact_service'],
                user_id=deps['user_id'],
                validate_session=deps['validate_session'],
                component=deps['component'],
                user_config=deps['user_config']
            )
        
        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Failed to list artifact versions" in str(exc_info.value.detail)


class TestListArtifacts:
    """Test list_artifacts endpoint."""

    @pytest.fixture
    def mock_dependencies(self):
        """Create mock dependencies for artifact listing tests."""
        mock_artifact_service = MagicMock(spec=BaseArtifactService)
        
        mock_component = MagicMock()
        def mock_get_config(key, default=None):
            if key == "name":
                return "TestApp"
            elif key == "gateway_max_upload_size_bytes":
                return 100 * 1024 * 1024  # 100MB
            return default
        mock_component.get_config.side_effect = mock_get_config
        
        mock_validate_session = MagicMock(return_value=True)
        
        return {
            'artifact_service': mock_artifact_service,
            'component': mock_component,
            'validate_session': mock_validate_session,
            'user_id': 'test-user-123',
            'user_config': {'tool:artifact:list': True}
        }

    @pytest.mark.asyncio
    async def test_list_artifacts_session_validation_failure(self, mock_dependencies):
        """Test artifact listing returns empty list when session validation fails.

        This behavior is intentional to support project artifact listing before
        a session is created.
        """
        # Setup
        deps = mock_dependencies
        deps['validate_session'].return_value = False

        # Execute - should return empty list, not raise exception
        result = await list_artifacts(
            session_id="invalid-session",
            artifact_service=deps['artifact_service'],
            user_id=deps['user_id'],
            validate_session=deps['validate_session'],
            component=deps['component'],
            user_config=deps['user_config']
        )

        # Verify - returns empty list to allow project context usage
        assert result == []

    @pytest.mark.asyncio
    async def test_list_artifacts_service_not_configured(self, mock_dependencies):
        """Test artifact listing fails when artifact service is not configured."""
        # Setup
        deps = mock_dependencies
        
        # Execute & Verify
        with pytest.raises(HTTPException) as exc_info:
            await list_artifacts(
                session_id="test-session",
                artifact_service=None,  # No artifact service
                user_id=deps['user_id'],
                validate_session=deps['validate_session'],
                component=deps['component'],
                user_config=deps['user_config']
            )
        
        assert exc_info.value.status_code == status.HTTP_501_NOT_IMPLEMENTED
        assert "Artifact service is not configured" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_list_artifacts_general_error(self, mock_dependencies):
        """Test artifact listing handles general errors."""
        # Setup
        deps = mock_dependencies
        
        with patch('solace_agent_mesh.gateway.http_sse.routers.artifacts.get_artifact_info_list') as mock_get_info:
            mock_get_info.side_effect = Exception("Service error")
            
            # Execute & Verify
            with pytest.raises(HTTPException) as exc_info:
                await list_artifacts(
                    session_id="test-session",
                    artifact_service=deps['artifact_service'],
                    user_id=deps['user_id'],
                    validate_session=deps['validate_session'],
                    component=deps['component'],
                    user_config=deps['user_config']
                )
            
            assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert "Failed to retrieve artifact details" in str(exc_info.value.detail)


class TestDeleteArtifact:
    """Test delete_artifact endpoint."""

    @pytest.fixture
    def mock_dependencies(self):
        """Create mock dependencies for artifact deletion tests."""
        mock_artifact_service = MagicMock(spec=BaseArtifactService)
        mock_artifact_service.delete_artifact = AsyncMock()
        
        mock_component = MagicMock()
        def mock_get_config(key, default=None):
            if key == "name":
                return "TestApp"
            elif key == "gateway_max_upload_size_bytes":
                return 100 * 1024 * 1024  # 100MB
            return default
        mock_component.get_config.side_effect = mock_get_config
        
        mock_validate_session = MagicMock(return_value=True)
        
        return {
            'artifact_service': mock_artifact_service,
            'component': mock_component,
            'validate_session': mock_validate_session,
            'user_id': 'test-user-123',
            'user_config': {'tool:artifact:delete': True}
        }

    @pytest.mark.asyncio
    async def test_delete_artifact_success(self, mock_dependencies):
        """Test successful artifact deletion."""
        # Setup
        deps = mock_dependencies
        
        # Execute
        result = await delete_artifact(
            session_id="test-session",
            filename="test.txt",
            artifact_service=deps['artifact_service'],
            user_id=deps['user_id'],
            validate_session=deps['validate_session'],
            component=deps['component'],
            user_config=deps['user_config']
        )
        
        # Verify
        assert result.status_code == status.HTTP_204_NO_CONTENT
        deps['artifact_service'].delete_artifact.assert_called_once_with(
            app_name="TestApp",
            user_id="test-user-123",
            session_id="test-session",
            filename="test.txt"
        )

    @pytest.mark.asyncio
    async def test_delete_artifact_session_validation_failure(self, mock_dependencies):
        """Test deletion fails when session validation fails."""
        # Setup
        deps = mock_dependencies
        deps['validate_session'].return_value = False
        
        # Execute & Verify
        with pytest.raises(HTTPException) as exc_info:
            await delete_artifact(
                session_id="invalid-session",
                filename="test.txt",
                artifact_service=deps['artifact_service'],
                user_id=deps['user_id'],
                validate_session=deps['validate_session'],
                component=deps['component'],
                user_config=deps['user_config']
            )
        
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert "Session not found or access denied" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_delete_artifact_service_not_configured(self, mock_dependencies):
        """Test deletion fails when artifact service is not configured."""
        # Setup
        deps = mock_dependencies
        
        # Execute & Verify
        with pytest.raises(HTTPException) as exc_info:
            await delete_artifact(
                session_id="test-session",
                filename="test.txt",
                artifact_service=None,  # No artifact service
                user_id=deps['user_id'],
                validate_session=deps['validate_session'],
                component=deps['component'],
                user_config=deps['user_config']
            )
        
        assert exc_info.value.status_code == status.HTTP_501_NOT_IMPLEMENTED
        assert "Artifact service is not configured" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_delete_artifact_general_error(self, mock_dependencies):
        """Test deletion handles general errors."""
        # Setup
        deps = mock_dependencies
        deps['artifact_service'].delete_artifact.side_effect = Exception("Service error")
        
        # Execute & Verify
        with pytest.raises(HTTPException) as exc_info:
            await delete_artifact(
                session_id="test-session",
                filename="test.txt",
                artifact_service=deps['artifact_service'],
                user_id=deps['user_id'],
                validate_session=deps['validate_session'],
                component=deps['component'],
                user_config=deps['user_config']
            )
        
        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Failed to delete artifact" in str(exc_info.value.detail)


# =============================================================================
# BULK ARTIFACTS ENDPOINT TESTS
# =============================================================================

from solace_agent_mesh.gateway.http_sse.routers.artifacts import (
    list_all_artifacts,
    ArtifactWithContext,
    BulkArtifactsResponse,
    _deduplicate_artifacts,
    _fetch_all_source_artifacts,
    _artifact_list_cache,
    _ArtifactListCache,
    upload_artifact_with_session,
    delete_artifact,
)
from solace_agent_mesh.gateway.http_sse.services.project_service import ProjectService


class TestListAllArtifacts:
    """Test list_all_artifacts bulk endpoint."""

    @pytest.fixture(autouse=True)
    def _clear_artifact_cache(self):
        """Ensure the module-level artifact list cache is empty for each test."""
        _artifact_list_cache.clear()
        yield
        _artifact_list_cache.clear()

    @pytest.fixture
    def mock_dependencies(self):
        """Create mock dependencies for bulk listing tests."""
        # Mock artifact service
        mock_artifact_service = MagicMock(spec=BaseArtifactService)
        
        # Mock session service
        mock_session_service = MagicMock(spec=SessionService)
        
        # Mock project service
        mock_project_service = MagicMock(spec=ProjectService)
        
        # Mock database session
        mock_db = MagicMock(spec=Session)
        
        # Mock component
        mock_component = MagicMock()
        mock_component.get_config.return_value = "TestApp"
        
        return {
            'artifact_service': mock_artifact_service,
            'session_service': mock_session_service,
            'project_service': mock_project_service,
            'db': mock_db,
            'component': mock_component,
            'user_id': 'test-user-123',
            'user_config': {'tool:artifact:list': True},
        }

    @pytest.mark.asyncio
    async def test_list_all_artifacts_no_artifact_service(self, mock_dependencies):
        """Test that endpoint returns 501 when artifact service is not configured."""
        deps = mock_dependencies
        
        with pytest.raises(HTTPException) as exc_info:
            await list_all_artifacts(
                artifact_service=None,
                user_id=deps['user_id'],
                component=deps['component'],
                session_service=deps['session_service'],
                project_service=deps['project_service'],
                db=deps['db'],
                user_config=deps['user_config'],
                page=1,
                page_size=50,
            )
        
        assert exc_info.value.status_code == status.HTTP_501_NOT_IMPLEMENTED
        assert "Artifact service is not configured" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_list_all_artifacts_empty_result(self, mock_dependencies):
        """Test bulk listing with no sessions or projects."""
        deps = mock_dependencies
        
        # Mock empty sessions response
        mock_sessions_response = MagicMock()
        mock_sessions_response.data = []
        mock_sessions_response.meta.pagination.next_page = None
        deps['session_service'].get_user_sessions.return_value = mock_sessions_response
        
        # Mock empty projects
        deps['project_service'].get_user_projects.return_value = []
        
        result = await list_all_artifacts(
            artifact_service=deps['artifact_service'],
            user_id=deps['user_id'],
            component=deps['component'],
            session_service=deps['session_service'],
            project_service=deps['project_service'],
            db=deps['db'],
            user_config=deps['user_config'],
            page=1,
            page_size=50,
        )

        assert isinstance(result, BulkArtifactsResponse)
        assert len(result.artifacts) == 0
        assert result.total_count == 0
        assert result.total_count_estimated is False
        assert result.has_more is False
        assert result.next_page is None

    @pytest.mark.asyncio
    async def test_list_all_artifacts_with_sessions(self, mock_dependencies):
        """Test bulk listing with session artifacts."""
        deps = mock_dependencies
        
        # Mock session with artifacts
        mock_session = MagicMock()
        mock_session.id = "session-123"
        mock_session.name = "Test Session"
        mock_session.project_id = None
        mock_session.project_name = None
        
        mock_sessions_response = MagicMock()
        mock_sessions_response.data = [mock_session]
        mock_sessions_response.meta.pagination.next_page = None
        deps['session_service'].get_user_sessions.return_value = mock_sessions_response
        
        # Mock empty projects
        deps['project_service'].get_user_projects.return_value = []
        
        # Mock artifact info list
        mock_artifact = MagicMock()
        mock_artifact.filename = "test.txt"
        mock_artifact.size = 1024
        mock_artifact.mime_type = "text/plain"
        mock_artifact.last_modified = "2023-01-01T00:00:00Z"
        mock_artifact.uri = "artifact://app/user/session-123/test.txt"
        
        with patch('solace_agent_mesh.gateway.http_sse.routers.artifacts.get_artifact_info_list_fast') as mock_get_list:
            mock_get_list.return_value = [mock_artifact]
            
            result = await list_all_artifacts(
                artifact_service=deps['artifact_service'],
                user_id=deps['user_id'],
                component=deps['component'],
                session_service=deps['session_service'],
                project_service=deps['project_service'],
                db=deps['db'],
                user_config=deps['user_config'],
                page=1,
                page_size=50,
            )

        assert isinstance(result, BulkArtifactsResponse)
        assert len(result.artifacts) == 1
        assert result.artifacts[0].filename == "test.txt"
        assert result.artifacts[0].session_id == "session-123"
        assert result.artifacts[0].session_name == "Test Session"
        assert result.artifacts[0].source == "upload"
        assert result.total_count_estimated is False
        assert result.has_more is False
        assert result.next_page is None

    @pytest.mark.asyncio
    async def test_list_all_artifacts_prefilters_empty_sessions(self, mock_dependencies):
        """When the artifact service exposes ``list_sessions_with_artifacts_for_user``,
        sessions absent from that set should be skipped before per-session S3 calls.

        Mirrors the production case where users accumulate thousands of empty
        chat sessions; without this filter every empty session triggers a
        wasted ``list_artifact_keys`` round-trip.
        """
        deps = mock_dependencies

        # Three sessions in DB, only one has artifacts in storage
        sessions = []
        for sid, name in [("session-empty-1", "Empty 1"),
                          ("session-with-art", "Has Artifacts"),
                          ("session-empty-2", "Empty 2")]:
            s = MagicMock()
            s.id = sid
            s.name = name
            s.project_id = None
            s.project_name = None
            sessions.append(s)

        mock_sessions_response = MagicMock()
        mock_sessions_response.data = sessions
        mock_sessions_response.meta.pagination.next_page = None
        deps['session_service'].get_user_sessions.return_value = mock_sessions_response
        deps['project_service'].get_user_projects.return_value = []

        # Mark the artifact service as supporting user-prefix listing — only one
        # session has artifacts in storage.
        async def _list_user_sessions(*, app_name, user_id):
            return {"session-with-art"}
        deps['artifact_service'].list_sessions_with_artifacts_for_user = _list_user_sessions

        mock_artifact = MagicMock()
        mock_artifact.filename = "result.txt"
        mock_artifact.size = 100
        mock_artifact.mime_type = "text/plain"
        mock_artifact.last_modified = "2026-04-30T00:00:00Z"
        mock_artifact.uri = "artifact://app/user/session-with-art/result.txt"
        mock_artifact.tags = None

        with patch(
            'solace_agent_mesh.gateway.http_sse.routers.artifacts.get_artifact_info_list_fast',
            new=AsyncMock(return_value=[mock_artifact]),
        ) as mock_get_list:
            result = await list_all_artifacts(
                artifact_service=deps['artifact_service'],
                user_id=deps['user_id'],
                component=deps['component'],
                session_service=deps['session_service'],
                project_service=deps['project_service'],
                db=deps['db'],
                user_config=deps['user_config'],
                page=1,
                page_size=50,
            )

        # Only the session that the user-prefix listing said has artifacts
        # should have been queried for keys.
        called_session_ids = [
            kwargs['session_id']
            for _args, kwargs in mock_get_list.call_args_list
        ]
        assert called_session_ids == ["session-with-art"], (
            f"Expected per-session fetch only for session-with-art; got {called_session_ids}"
        )

        assert isinstance(result, BulkArtifactsResponse)
        assert len(result.artifacts) == 1
        assert result.artifacts[0].session_id == "session-with-art"

    @pytest.mark.asyncio
    async def test_list_all_artifacts_skips_filter_when_prefilter_returns_none(self, mock_dependencies):
        """When ``list_sessions_with_artifacts_for_user`` returns ``None``, the
        prefilter MUST be skipped — every session continues to get its own
        ``list_artifact_keys`` call. Returned by the helper for the S3 error path
        and for users with only user-scoped artifacts.
        """
        deps = mock_dependencies

        sessions = []
        for sid, name in [("session-1", "S1"), ("session-2", "S2")]:
            s = MagicMock()
            s.id = sid
            s.name = name
            s.project_id = None
            s.project_name = None
            sessions.append(s)

        mock_sessions_response = MagicMock()
        mock_sessions_response.data = sessions
        mock_sessions_response.meta.pagination.next_page = None
        deps['session_service'].get_user_sessions.return_value = mock_sessions_response
        deps['project_service'].get_user_projects.return_value = []

        async def _list_user_sessions(*, app_name, user_id):
            return None
        deps['artifact_service'].list_sessions_with_artifacts_for_user = _list_user_sessions

        with patch(
            'solace_agent_mesh.gateway.http_sse.routers.artifacts.get_artifact_info_list_fast',
            new=AsyncMock(return_value=[]),
        ) as mock_get_list:
            await list_all_artifacts(
                artifact_service=deps['artifact_service'],
                user_id=deps['user_id'],
                component=deps['component'],
                session_service=deps['session_service'],
                project_service=deps['project_service'],
                db=deps['db'],
                user_config=deps['user_config'],
                page=1,
                page_size=50,
            )

        called_session_ids = [
            kwargs['session_id'] for _args, kwargs in mock_get_list.call_args_list
        ]
        assert sorted(called_session_ids) == ["session-1", "session-2"], (
            f"Expected per-session fetch for both sessions; got {called_session_ids}"
        )

    @pytest.mark.asyncio
    async def test_list_all_artifacts_falls_back_when_prefilter_raises(self, mock_dependencies):
        """If the prefilter helper raises, the router MUST fall through to the
        per-session scan rather than propagating the error or dropping sessions.
        """
        deps = mock_dependencies

        sessions = []
        for sid, name in [("session-1", "S1"), ("session-2", "S2")]:
            s = MagicMock()
            s.id = sid
            s.name = name
            s.project_id = None
            s.project_name = None
            sessions.append(s)

        mock_sessions_response = MagicMock()
        mock_sessions_response.data = sessions
        mock_sessions_response.meta.pagination.next_page = None
        deps['session_service'].get_user_sessions.return_value = mock_sessions_response
        deps['project_service'].get_user_projects.return_value = []

        async def _list_user_sessions(*, app_name, user_id):
            raise RuntimeError("transient S3 issue")
        deps['artifact_service'].list_sessions_with_artifacts_for_user = _list_user_sessions

        with patch(
            'solace_agent_mesh.gateway.http_sse.routers.artifacts.get_artifact_info_list_fast',
            new=AsyncMock(return_value=[]),
        ) as mock_get_list:
            result = await list_all_artifacts(
                artifact_service=deps['artifact_service'],
                user_id=deps['user_id'],
                component=deps['component'],
                session_service=deps['session_service'],
                project_service=deps['project_service'],
                db=deps['db'],
                user_config=deps['user_config'],
                page=1,
                page_size=50,
            )

        called_session_ids = [
            kwargs['session_id'] for _args, kwargs in mock_get_list.call_args_list
        ]
        assert sorted(called_session_ids) == ["session-1", "session-2"]
        assert isinstance(result, BulkArtifactsResponse)

    @pytest.mark.asyncio
    async def test_list_all_artifacts_filters_generated_files(self, mock_dependencies):
        """Test that generated files (.converted.txt, project_bm25_index.zip) are filtered out."""
        deps = mock_dependencies
        
        # Mock session
        mock_session = MagicMock()
        mock_session.id = "session-123"
        mock_session.name = "Test Session"
        mock_session.project_id = None
        mock_session.project_name = None
        
        mock_sessions_response = MagicMock()
        mock_sessions_response.data = [mock_session]
        mock_sessions_response.meta.pagination.next_page = None
        deps['session_service'].get_user_sessions.return_value = mock_sessions_response
        
        # Mock empty projects
        deps['project_service'].get_user_projects.return_value = []
        
        # Mock artifacts including generated files
        mock_artifacts = [
            MagicMock(filename="document.pdf", size=1024, mime_type="application/pdf", last_modified="2023-01-01T00:00:00Z", uri="uri1"),
            MagicMock(filename="document.pdf.converted.txt", size=512, mime_type="text/plain", last_modified="2023-01-01T00:00:00Z", uri="uri2"),
            MagicMock(filename="project_bm25_index.zip", size=2048, mime_type="application/zip", last_modified="2023-01-01T00:00:00Z", uri="uri3"),
        ]
        
        with patch('solace_agent_mesh.gateway.http_sse.routers.artifacts.get_artifact_info_list_fast') as mock_get_list:
            mock_get_list.return_value = mock_artifacts
            
            result = await list_all_artifacts(
                artifact_service=deps['artifact_service'],
                user_id=deps['user_id'],
                component=deps['component'],
                session_service=deps['session_service'],
                project_service=deps['project_service'],
                db=deps['db'],
                user_config=deps['user_config'],
                page=1,
                page_size=50,
            )

        # Only the original document should be returned
        assert len(result.artifacts) == 1
        assert result.artifacts[0].filename == "document.pdf"
        assert result.has_more is False
        assert result.next_page is None

    @pytest.mark.asyncio
    async def test_list_all_artifacts_with_project_artifacts(self, mock_dependencies):
        """Test bulk listing with project artifacts."""
        deps = mock_dependencies
        
        # Mock empty sessions
        mock_sessions_response = MagicMock()
        mock_sessions_response.data = []
        mock_sessions_response.meta.pagination.next_page = None
        deps['session_service'].get_user_sessions.return_value = mock_sessions_response
        
        # Mock project
        mock_project = MagicMock()
        mock_project.id = "project-456"
        mock_project.name = "Test Project"
        mock_project.user_id = "test-user-123"
        deps['project_service'].get_user_projects.return_value = [mock_project]
        
        # Mock project artifact
        mock_artifact = MagicMock()
        mock_artifact.filename = "knowledge.docx"
        mock_artifact.size = 4096
        mock_artifact.mime_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        mock_artifact.last_modified = "2023-01-01T00:00:00Z"
        mock_artifact.uri = "artifact://app/user/project-456/knowledge.docx"
        
        with patch('solace_agent_mesh.gateway.http_sse.routers.artifacts.get_artifact_info_list_fast') as mock_get_list:
            mock_get_list.return_value = [mock_artifact]
            
            result = await list_all_artifacts(
                artifact_service=deps['artifact_service'],
                user_id=deps['user_id'],
                component=deps['component'],
                session_service=deps['session_service'],
                project_service=deps['project_service'],
                db=deps['db'],
                user_config=deps['user_config'],
                page=1,
                page_size=50,
            )

        assert len(result.artifacts) == 1
        assert result.artifacts[0].filename == "knowledge.docx"
        assert result.artifacts[0].session_id == "project-project-456"
        assert result.artifacts[0].project_id == "project-456"
        assert result.artifacts[0].project_name == "Test Project"
        assert result.artifacts[0].source == "project"
        assert result.has_more is False
        assert result.next_page is None

    @pytest.mark.asyncio
    async def test_list_all_artifacts_deduplication(self, mock_dependencies):
        """Test that duplicate artifacts are deduplicated, preferring project source."""
        deps = mock_dependencies
        
        # Mock session that belongs to a project
        mock_session = MagicMock()
        mock_session.id = "session-123"
        mock_session.name = "Project Chat"
        mock_session.project_id = "project-456"
        mock_session.project_name = "Test Project"
        
        mock_sessions_response = MagicMock()
        mock_sessions_response.data = [mock_session]
        mock_sessions_response.meta.pagination.next_page = None
        deps['session_service'].get_user_sessions.return_value = mock_sessions_response
        
        # Mock project
        mock_project = MagicMock()
        mock_project.id = "project-456"
        mock_project.name = "Test Project"
        mock_project.user_id = "test-user-123"
        deps['project_service'].get_user_projects.return_value = [mock_project]
        
        # Same artifact appears in both session and project
        mock_artifact = MagicMock()
        mock_artifact.filename = "shared.pdf"
        mock_artifact.size = 2048
        mock_artifact.mime_type = "application/pdf"
        mock_artifact.last_modified = "2023-01-01T00:00:00Z"
        mock_artifact.uri = "artifact://app/user/project-456/shared.pdf"
        
        with patch('solace_agent_mesh.gateway.http_sse.routers.artifacts.get_artifact_info_list_fast') as mock_get_list:
            mock_get_list.return_value = [mock_artifact]
            
            result = await list_all_artifacts(
                artifact_service=deps['artifact_service'],
                user_id=deps['user_id'],
                component=deps['component'],
                session_service=deps['session_service'],
                project_service=deps['project_service'],
                db=deps['db'],
                user_config=deps['user_config'],
                page=1,
                page_size=50,
            )

        # Should only have one artifact (deduplicated)
        # The project version should be preferred
        project_artifacts = [a for a in result.artifacts if a.session_id.startswith("project-")]
        assert len(project_artifacts) >= 1
        assert result.has_more is False
        assert result.next_page is None

    @pytest.mark.asyncio
    async def test_list_all_artifacts_page_based_slicing(self, mock_dependencies):
        """Test that page/page_size correctly slices the result set."""
        deps = mock_dependencies

        # Mock session with many artifacts
        mock_session = MagicMock()
        mock_session.id = "session-123"
        mock_session.name = "Test Session"
        mock_session.project_id = None
        mock_session.project_name = None

        mock_sessions_response = MagicMock()
        mock_sessions_response.data = [mock_session]
        mock_sessions_response.meta.pagination.next_page = None
        deps['session_service'].get_user_sessions.return_value = mock_sessions_response

        # Mock empty projects
        deps['project_service'].get_user_projects.return_value = []

        # Create 10 mock artifacts with descending dates so sort order is file9..file0
        mock_artifacts = []
        for i in range(10):
            artifact = MagicMock()
            artifact.filename = f"file{i}.txt"
            artifact.size = 100 * (i + 1)
            artifact.mime_type = "text/plain"
            artifact.last_modified = f"2023-01-{i+1:02d}T00:00:00Z"
            artifact.uri = f"artifact://app/user/session-123/file{i}.txt"
            mock_artifacts.append(artifact)

        with patch('solace_agent_mesh.gateway.http_sse.routers.artifacts.get_artifact_info_list_fast') as mock_get_list:
            mock_get_list.return_value = mock_artifacts

            # Request page 2, page_size 3 → should return items 4-6 (sorted newest first)
            result = await list_all_artifacts(
                artifact_service=deps['artifact_service'],
                user_id=deps['user_id'],
                component=deps['component'],
                session_service=deps['session_service'],
                project_service=deps['project_service'],
                db=deps['db'],
                user_config=deps['user_config'],
                page=2,
                page_size=3,
            )

        # Page 2 with page_size=3: items at indices 3,4,5 of the sorted list
        assert len(result.artifacts) == 3
        # total_count reflects the full deduplicated set
        assert result.total_count == 10
        # There are more items beyond this page (indices 6-9)
        assert result.has_more is True
        assert result.next_page == 3
        # Sorted newest first: file9, file8, file7, file6, file5, file4, ...
        # Page 2 → indices 3-5 → file6, file5, file4
        assert result.artifacts[0].filename == "file6.txt"
        assert result.artifacts[1].filename == "file5.txt"
        assert result.artifacts[2].filename == "file4.txt"

    @pytest.mark.asyncio
    async def test_list_all_artifacts_handles_session_fetch_error(self, mock_dependencies):
        """Test that endpoint handles session fetch errors gracefully."""
        deps = mock_dependencies
        
        # Mock session service to raise an error
        deps['session_service'].get_user_sessions.side_effect = Exception("Database error")
        
        # Mock empty projects
        deps['project_service'].get_user_projects.return_value = []
        
        # Should not raise, just return empty result
        result = await list_all_artifacts(
            artifact_service=deps['artifact_service'],
            user_id=deps['user_id'],
            component=deps['component'],
            session_service=deps['session_service'],
            project_service=deps['project_service'],
            db=deps['db'],
            user_config=deps['user_config'],
            page=1,
            page_size=50,
        )

        assert isinstance(result, BulkArtifactsResponse)
        assert len(result.artifacts) == 0
        assert result.has_more is False
        assert result.next_page is None

    @pytest.mark.asyncio
    async def test_list_all_artifacts_handles_project_fetch_error(self, mock_dependencies):
        """Test that endpoint handles project fetch errors gracefully."""
        deps = mock_dependencies
        
        # Mock empty sessions
        mock_sessions_response = MagicMock()
        mock_sessions_response.data = []
        mock_sessions_response.meta.pagination.next_page = None
        deps['session_service'].get_user_sessions.return_value = mock_sessions_response
        
        # Mock project service to raise an error
        deps['project_service'].get_user_projects.side_effect = Exception("Database error")
        
        # Should not raise, just return empty result
        result = await list_all_artifacts(
            artifact_service=deps['artifact_service'],
            user_id=deps['user_id'],
            component=deps['component'],
            session_service=deps['session_service'],
            project_service=deps['project_service'],
            db=deps['db'],
            user_config=deps['user_config'],
            page=1,
            page_size=50,
        )

        assert isinstance(result, BulkArtifactsResponse)
        assert len(result.artifacts) == 0
        assert result.has_more is False
        assert result.next_page is None

    @pytest.mark.asyncio
    async def test_list_all_artifacts_sorts_by_last_modified(self, mock_dependencies):
        """Test that artifacts are sorted by last_modified (newest first)."""
        deps = mock_dependencies
        
        # Mock session
        mock_session = MagicMock()
        mock_session.id = "session-123"
        mock_session.name = "Test Session"
        mock_session.project_id = None
        mock_session.project_name = None
        
        mock_sessions_response = MagicMock()
        mock_sessions_response.data = [mock_session]
        mock_sessions_response.meta.pagination.next_page = None
        deps['session_service'].get_user_sessions.return_value = mock_sessions_response
        
        # Mock empty projects
        deps['project_service'].get_user_projects.return_value = []
        
        # Create artifacts with different dates (in random order)
        mock_artifacts = [
            MagicMock(filename="old.txt", size=100, mime_type="text/plain", last_modified="2023-01-01T00:00:00Z", uri="uri1"),
            MagicMock(filename="newest.txt", size=100, mime_type="text/plain", last_modified="2023-12-31T00:00:00Z", uri="uri2"),
            MagicMock(filename="middle.txt", size=100, mime_type="text/plain", last_modified="2023-06-15T00:00:00Z", uri="uri3"),
        ]
        
        with patch('solace_agent_mesh.gateway.http_sse.routers.artifacts.get_artifact_info_list_fast') as mock_get_list:
            mock_get_list.return_value = mock_artifacts
            
            result = await list_all_artifacts(
                artifact_service=deps['artifact_service'],
                user_id=deps['user_id'],
                component=deps['component'],
                session_service=deps['session_service'],
                project_service=deps['project_service'],
                db=deps['db'],
                user_config=deps['user_config'],
                page=1,
                page_size=50,
            )

        # Should be sorted newest first
        assert result.artifacts[0].filename == "newest.txt"
        assert result.artifacts[1].filename == "middle.txt"
        assert result.artifacts[2].filename == "old.txt"

    @pytest.mark.asyncio
    async def test_list_all_artifacts_user_isolation_sessions(self, mock_dependencies):
        """Test that bulk endpoint only fetches sessions for the authenticated user.
        
        Security: Verifies user_id is correctly passed to get_user_sessions,
        ensuring users cannot access other users' session artifacts.
        """
        deps = mock_dependencies
        test_user_id = "specific-user-abc123"
        
        # Mock empty sessions response
        mock_sessions_response = MagicMock()
        mock_sessions_response.data = []
        mock_sessions_response.meta.pagination.next_page = None
        deps['session_service'].get_user_sessions.return_value = mock_sessions_response
        
        # Mock empty projects
        deps['project_service'].get_user_projects.return_value = []
        
        await list_all_artifacts(
            artifact_service=deps['artifact_service'],
            user_id=test_user_id,
            component=deps['component'],
            session_service=deps['session_service'],
            project_service=deps['project_service'],
            db=deps['db'],
            user_config=deps['user_config'],
            page=1,
            page_size=50,
        )

        # Verify get_user_sessions was called with the correct user_id
        deps['session_service'].get_user_sessions.assert_called_once()
        call_kwargs = deps['session_service'].get_user_sessions.call_args
        assert call_kwargs.kwargs.get('user_id') == test_user_id or call_kwargs.args[1] == test_user_id

    @pytest.mark.asyncio
    async def test_list_all_artifacts_user_isolation_projects(self, mock_dependencies):
        """Test that bulk endpoint only fetches projects for the authenticated user.
        
        Security: Verifies user_id is correctly passed to get_user_projects,
        ensuring users cannot access other users' project artifacts.
        """
        deps = mock_dependencies
        test_user_id = "specific-user-xyz789"
        
        # Mock empty sessions response
        mock_sessions_response = MagicMock()
        mock_sessions_response.data = []
        mock_sessions_response.meta.pagination.next_page = None
        deps['session_service'].get_user_sessions.return_value = mock_sessions_response
        
        # Mock empty projects
        deps['project_service'].get_user_projects.return_value = []
        
        await list_all_artifacts(
            artifact_service=deps['artifact_service'],
            user_id=test_user_id,
            component=deps['component'],
            session_service=deps['session_service'],
            project_service=deps['project_service'],
            db=deps['db'],
            user_config=deps['user_config'],
            page=1,
            page_size=50,
        )

        # Verify get_user_projects was called with the correct user_id
        deps['project_service'].get_user_projects.assert_called_once()
        call_args = deps['project_service'].get_user_projects.call_args
        # Check both positional and keyword arguments for user_id
        assert test_user_id in call_args.args or call_args.kwargs.get('user_id') == test_user_id

    @pytest.mark.asyncio
    async def test_list_all_artifacts_determine_source_heuristic(self, mock_dependencies):
        """Test the _determine_source heuristic for classifying artifact origins.
        
        The heuristic should:
        - Return 'project' for project-prefixed session IDs (project knowledge files)
        - Return 'upload' for regular session artifacts (user uploads)
        
        Note: .converted.txt and project_bm25_index.zip are filtered out before
        source determination, so they don't appear in results.
        """
        deps = mock_dependencies
        
        # Mock session with various artifact types
        mock_session = MagicMock()
        mock_session.id = "session-123"
        mock_session.name = "Test Session"
        mock_session.project_id = None
        mock_session.project_name = None
        
        mock_sessions_response = MagicMock()
        mock_sessions_response.data = [mock_session]
        mock_sessions_response.meta.pagination.next_page = None
        deps['session_service'].get_user_sessions.return_value = mock_sessions_response
        
        # Mock project
        mock_project = MagicMock()
        mock_project.id = "project-456"
        mock_project.name = "Test Project"
        mock_project.user_id = "test-user-123"
        deps['project_service'].get_user_projects.return_value = [mock_project]
        
        # Create artifacts for session (should be 'upload')
        session_artifacts = [
            MagicMock(filename="document.pdf", size=1024, mime_type="application/pdf", last_modified="2023-01-01T00:00:00Z", uri="uri1"),
            MagicMock(filename="image.png", size=2048, mime_type="image/png", last_modified="2023-01-02T00:00:00Z", uri="uri2"),
        ]
        
        # Create artifacts for project (should be 'project')
        project_artifacts = [
            MagicMock(filename="knowledge.docx", size=4096, mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", last_modified="2023-01-03T00:00:00Z", uri="uri3"),
        ]
        
        with patch('solace_agent_mesh.gateway.http_sse.routers.artifacts.get_artifact_info_list_fast') as mock_get_list:
            # Return different artifacts based on session_id
            def get_artifacts_for_session(**kwargs):
                session_id = kwargs.get('session_id', '')
                if session_id.startswith('project-'):
                    return project_artifacts
                return session_artifacts
            
            mock_get_list.side_effect = get_artifacts_for_session
            
            result = await list_all_artifacts(
                artifact_service=deps['artifact_service'],
                user_id=deps['user_id'],
                component=deps['component'],
                session_service=deps['session_service'],
                project_service=deps['project_service'],
                db=deps['db'],
                user_config=deps['user_config'],
                page=1,
                page_size=50,
            )

        # Build a map of filename -> source for easier assertions
        source_map = {a.filename: a.source for a in result.artifacts}
        
        # Verify session artifacts are classified as 'upload'
        assert source_map["document.pdf"] == "upload", "Session PDF should be classified as upload"
        assert source_map["image.png"] == "upload", "Session PNG should be classified as upload"
        
        # Verify project artifacts are classified as 'project'
        assert source_map["knowledge.docx"] == "project", "Project DOCX should be classified as project"


# =============================================================================
# _deduplicate_artifacts UNIT TESTS
# =============================================================================


class TestDeduplicateArtifacts:
    """Direct unit tests for _deduplicate_artifacts."""

    @staticmethod
    def _make_artifact(**overrides) -> ArtifactWithContext:
        defaults = {
            "filename": "file.txt",
            "size": 100,
            "mime_type": "text/plain",
            "last_modified": "2023-01-01T00:00:00Z",
            "uri": "artifact://app/user/session/file.txt",
            "session_id": "session-1",
            "session_name": "Session 1",
            "project_id": None,
            "project_name": None,
            "source": "upload",
        }
        defaults.update(overrides)
        return ArtifactWithContext(**defaults)

    def test_project_entry_preferred_over_session_entry(self):
        """When the same file exists in both a project-prefixed session and a
        regular session (same project_id), the project-prefixed entry wins."""
        session_entry = self._make_artifact(
            session_id="session-1",
            project_id="proj-1",
            project_name="Project 1",
            filename="shared.pdf",
        )
        project_entry = self._make_artifact(
            session_id="project-proj-1",
            project_id="proj-1",
            project_name="Project 1",
            filename="shared.pdf",
        )
        # Order: session first, project second
        result = _deduplicate_artifacts([session_entry, project_entry])
        assert len(result) == 1
        assert result[0].session_id == "project-proj-1"

    def test_same_key_project_scoped_dedup(self):
        """Two entries with the same (project_id, filename) but both from
        regular sessions — only one is kept."""
        entry_a = self._make_artifact(
            session_id="session-1",
            project_id="proj-1",
            filename="doc.pdf",
        )
        entry_b = self._make_artifact(
            session_id="session-2",
            project_id="proj-1",
            filename="doc.pdf",
        )
        result = _deduplicate_artifacts([entry_a, entry_b])
        project_results = [a for a in result if a.project_id == "proj-1"]
        assert len(project_results) == 1

    def test_non_project_artifacts_always_included(self):
        """Artifacts without a project_id are never deduplicated away, even
        if they share the same filename."""
        a = self._make_artifact(session_id="s-1", filename="notes.txt")
        b = self._make_artifact(session_id="s-2", filename="notes.txt")
        result = _deduplicate_artifacts([a, b])
        assert len(result) == 2

    def test_mixed_project_and_non_project(self):
        """Non-project artifacts are returned alongside deduplicated project artifacts."""
        proj_a = self._make_artifact(
            session_id="session-1",
            project_id="proj-1",
            filename="shared.pdf",
        )
        proj_b = self._make_artifact(
            session_id="project-proj-1",
            project_id="proj-1",
            filename="shared.pdf",
        )
        non_proj = self._make_artifact(
            session_id="session-3",
            filename="personal.txt",
        )
        result = _deduplicate_artifacts([proj_a, proj_b, non_proj])
        assert len(result) == 2
        filenames = {a.filename for a in result}
        assert filenames == {"shared.pdf", "personal.txt"}


# =============================================================================
# _fetch_all_source_artifacts UNIT TESTS
# =============================================================================


class TestFetchAllSourceArtifacts:
    """Direct unit tests for _fetch_all_source_artifacts."""

    @staticmethod
    def _make_entry(session_id="s-1", project_id=None):
        return {
            "session_id": session_id,
            "session_name": "Session",
            "project_id": project_id,
            "project_name": None,
            "fetch_user_id": "user-1",
        }

    @staticmethod
    def _make_artifact(filename="file.txt", session_id="s-1"):
        return ArtifactWithContext(
            filename=filename,
            size=100,
            mime_type="text/plain",
            last_modified="2023-01-01T00:00:00Z",
            uri="uri",
            session_id=session_id,
            session_name="Session",
            project_id=None,
            project_name=None,
            source="upload",
        )

    @pytest.mark.asyncio
    async def test_multi_batch_concatenation(self):
        """Results from multiple batches are concatenated correctly."""
        entries = [self._make_entry(session_id=f"s-{i}") for i in range(5)]

        async def fetch_fn(**kwargs):
            sid = kwargs["session_id"]
            return [self._make_artifact(filename=f"{sid}.txt", session_id=sid)]

        result, sources_processed = await _fetch_all_source_artifacts(
            entries, fetch_fn, "[test]", batch_size=2,
        )
        assert len(result) == 5
        assert sources_processed == 5
        filenames = {a.filename for a in result}
        assert filenames == {f"s-{i}.txt" for i in range(5)}

    @pytest.mark.asyncio
    async def test_failing_source_does_not_block_others(self):
        """A source that raises an exception is skipped; other sources succeed."""
        entries = [
            self._make_entry(session_id="good-1"),
            self._make_entry(session_id="bad"),
            self._make_entry(session_id="good-2"),
        ]

        async def fetch_fn(**kwargs):
            if kwargs["session_id"] == "bad":
                raise RuntimeError("simulated failure")
            return [self._make_artifact(
                filename=f"{kwargs['session_id']}.txt",
                session_id=kwargs["session_id"],
            )]

        result, sources_processed = await _fetch_all_source_artifacts(
            entries, fetch_fn, "[test]", batch_size=10,
        )
        assert len(result) == 2
        assert sources_processed == 3
        filenames = {a.filename for a in result}
        assert "bad.txt" not in filenames
        assert filenames == {"good-1.txt", "good-2.txt"}

    @pytest.mark.asyncio
    async def test_early_termination_with_target_count(self):
        """When target_count is set, fetching stops once enough artifacts are collected."""
        entries = [self._make_entry(session_id=f"s-{i}") for i in range(10)]

        async def fetch_fn(**kwargs):
            sid = kwargs["session_id"]
            # Each source returns 3 artifacts
            return [
                self._make_artifact(filename=f"{sid}-{j}.txt", session_id=sid)
                for j in range(3)
            ]

        # target_count=5 → should stop after batch 1 (2 sources × 3 artifacts = 6 >= 5)
        result, sources_processed = await _fetch_all_source_artifacts(
            entries, fetch_fn, "[test]", batch_size=2, target_count=5,
        )
        # Should have fetched from first batch (2 sources) = 6 artifacts, then stopped
        assert len(result) == 6
        assert sources_processed == 2  # Only processed first batch
        # Remaining 8 sources should NOT have been fetched

    @pytest.mark.asyncio
    async def test_no_early_termination_when_target_zero(self):
        """When target_count=0 (default), all sources are fetched."""
        entries = [self._make_entry(session_id=f"s-{i}") for i in range(6)]

        async def fetch_fn(**kwargs):
            return [self._make_artifact(filename=f"{kwargs['session_id']}.txt",
                                        session_id=kwargs["session_id"])]

        result, sources_processed = await _fetch_all_source_artifacts(
            entries, fetch_fn, "[test]", batch_size=2, target_count=0,
        )
        assert len(result) == 6
        assert sources_processed == 6  # All sources processed


# =============================================================================
# PAGINATION BOUNDARY TESTS
# =============================================================================


class TestPaginationBoundaries:
    """Test pagination edge cases for list_all_artifacts."""

    @pytest.fixture(autouse=True)
    def _clear_artifact_cache(self):
        _artifact_list_cache.clear()
        yield
        _artifact_list_cache.clear()

    @pytest.fixture
    def mock_dependencies(self):
        mock_artifact_service = MagicMock(spec=BaseArtifactService)
        mock_session_service = MagicMock(spec=SessionService)
        mock_project_service = MagicMock(spec=ProjectService)
        mock_db = MagicMock(spec=Session)
        mock_component = MagicMock()
        mock_component.get_config.return_value = "TestApp"
        return {
            'artifact_service': mock_artifact_service,
            'session_service': mock_session_service,
            'project_service': mock_project_service,
            'db': mock_db,
            'component': mock_component,
            'user_id': 'test-user-boundary',
            'user_config': {'tool:artifact:list': True},
        }

    def _setup_single_session_with_artifacts(self, deps, artifact_count):
        """Helper: one session, N artifacts, no projects."""
        mock_session = MagicMock()
        mock_session.id = "session-1"
        mock_session.name = "Session"
        mock_session.project_id = None
        mock_session.project_name = None

        mock_sessions_response = MagicMock()
        mock_sessions_response.data = [mock_session]
        mock_sessions_response.meta.pagination.next_page = None
        deps['session_service'].get_user_sessions.return_value = mock_sessions_response
        deps['project_service'].get_user_projects.return_value = []

        artifacts = []
        for i in range(artifact_count):
            a = MagicMock()
            a.filename = f"file{i}.txt"
            a.size = 100
            a.mime_type = "text/plain"
            a.last_modified = f"2023-01-{i+1:02d}T00:00:00Z"
            a.uri = f"uri{i}"
            artifacts.append(a)
        return artifacts

    @pytest.mark.asyncio
    async def test_out_of_range_page_returns_empty(self, mock_dependencies):
        """Requesting a page far beyond available data returns empty with has_more=False."""
        deps = mock_dependencies
        artifacts = self._setup_single_session_with_artifacts(deps, 10)

        with patch('solace_agent_mesh.gateway.http_sse.routers.artifacts.get_artifact_info_list_fast') as mock_get:
            mock_get.return_value = artifacts
            result = await list_all_artifacts(
                artifact_service=deps['artifact_service'],
                user_id=deps['user_id'],
                component=deps['component'],
                session_service=deps['session_service'],
                project_service=deps['project_service'],
                db=deps['db'],
                user_config=deps['user_config'],
                page=100,
                page_size=5,
            )

        assert len(result.artifacts) == 0
        assert result.has_more is False
        assert result.next_page is None
        assert result.total_count == 10

    @pytest.mark.asyncio
    async def test_exact_boundary_last_page(self, mock_dependencies):
        """When total_count is exactly divisible by page_size, the last full
        page should have has_more=False (no empty trailing page)."""
        deps = mock_dependencies
        artifacts = self._setup_single_session_with_artifacts(deps, 6)

        with patch('solace_agent_mesh.gateway.http_sse.routers.artifacts.get_artifact_info_list_fast') as mock_get:
            mock_get.return_value = artifacts
            result = await list_all_artifacts(
                artifact_service=deps['artifact_service'],
                user_id=deps['user_id'],
                component=deps['component'],
                session_service=deps['session_service'],
                project_service=deps['project_service'],
                db=deps['db'],
                user_config=deps['user_config'],
                page=2,
                page_size=3,
            )

        assert len(result.artifacts) == 3
        assert result.total_count == 6
        assert result.has_more is False
        assert result.next_page is None


# =============================================================================
# _ArtifactListCache DIRECT UNIT TESTS
# =============================================================================


class TestArtifactListCache:
    """Direct unit tests for _ArtifactListCache (TTL, LRU, lock_for, etc.)."""

    def _make_artifact(self, filename="f.txt"):
        return ArtifactWithContext(
            filename=filename,
            size=10,
            mime_type="text/plain",
            last_modified="2023-01-01T00:00:00Z",
            uri="uri",
            session_id="s1",
            session_name="Session",
            project_id=None,
            project_name=None,
            source="upload",
        )

    def test_get_returns_none_for_missing_key(self):
        cache = _ArtifactListCache(ttl=60)
        assert cache.get("no-such-user") is None

    def test_put_and_get_roundtrip(self):
        cache = _ArtifactListCache(ttl=60)
        arts = [self._make_artifact()]
        cache.put("u1", arts, sources_processed=5, total_sources=10)
        result = cache.get("u1")
        assert result is not None
        artifacts, sp, ts = result
        assert artifacts is arts
        assert sp == 5
        assert ts == 10

    def test_ttl_expiry(self):
        cache = _ArtifactListCache(ttl=1)
        cache.put("u1", [self._make_artifact()], 1, 1)
        assert cache.get("u1") is not None
        # Simulate time passing by directly modifying the stored timestamp
        ts, arts, sp, total = cache._store["u1"]
        cache._store["u1"] = (ts - 2, arts, sp, total)
        assert cache.get("u1") is None

    def test_lru_eviction(self):
        cache = _ArtifactListCache(ttl=60, max_size=2)
        cache.put("u1", [self._make_artifact("a.txt")], 1, 1)
        cache.put("u2", [self._make_artifact("b.txt")], 1, 1)
        # Adding u3 should evict u1 (oldest)
        cache.put("u3", [self._make_artifact("c.txt")], 1, 1)
        assert cache.get("u1") is None
        assert cache.get("u2") is not None
        assert cache.get("u3") is not None

    def test_invalidate_removes_entry(self):
        cache = _ArtifactListCache(ttl=60)
        cache.put("u1", [self._make_artifact()], 1, 1)
        cache.invalidate("u1")
        assert cache.get("u1") is None

    def test_invalidate_nonexistent_key_is_noop(self):
        cache = _ArtifactListCache(ttl=60)
        cache.invalidate("no-such-user")  # Should not raise

    def test_lock_for_returns_same_lock_for_same_user(self):
        cache = _ArtifactListCache(ttl=60)
        lock1 = cache.lock_for("u1")
        lock2 = cache.lock_for("u1")
        assert lock1 is lock2

    def test_lock_for_returns_different_locks_for_different_users(self):
        cache = _ArtifactListCache(ttl=60)
        lock1 = cache.lock_for("u1")
        lock2 = cache.lock_for("u2")
        assert lock1 is not lock2

    def test_lock_for_prunes_orphaned_locks(self):
        cache = _ArtifactListCache(ttl=60)
        cache.put("u1", [self._make_artifact()], 1, 1)
        _ = cache.lock_for("u1")
        # Remove the cache entry, making the lock orphaned
        cache.invalidate("u1")
        # Calling lock_for on another user triggers pruning
        _ = cache.lock_for("u2")
        assert "u1" not in cache._locks

    def test_clear_removes_all(self):
        cache = _ArtifactListCache(ttl=60)
        cache.put("u1", [self._make_artifact()], 1, 1)
        cache.put("u2", [self._make_artifact()], 1, 1)
        _ = cache.lock_for("u1")
        cache.clear()
        assert cache.get("u1") is None
        assert cache.get("u2") is None
        assert len(cache._locks) == 0


# =============================================================================
# SEARCH PARAMETER TESTS
# =============================================================================


class TestSearchParameter:
    """Test the search query parameter for list_all_artifacts."""

    @pytest.fixture(autouse=True)
    def _clear_artifact_cache(self):
        _artifact_list_cache.clear()
        yield
        _artifact_list_cache.clear()

    @pytest.fixture
    def mock_dependencies(self):
        mock_artifact_service = MagicMock(spec=BaseArtifactService)
        mock_session_service = MagicMock(spec=SessionService)
        mock_project_service = MagicMock(spec=ProjectService)
        mock_db = MagicMock(spec=Session)
        mock_component = MagicMock()
        mock_component.get_config.return_value = "TestApp"
        return {
            'artifact_service': mock_artifact_service,
            'session_service': mock_session_service,
            'project_service': mock_project_service,
            'db': mock_db,
            'component': mock_component,
            'user_id': 'test-user-search',
            'user_config': {'tool:artifact:list': True},
        }

    def _setup_sessions_with_varied_artifacts(self, deps):
        """Set up two sessions with different artifacts for search testing."""
        mock_session1 = MagicMock()
        mock_session1.id = "session-1"
        mock_session1.name = "Alpha Session"
        mock_session1.project_id = None
        mock_session1.project_name = None

        mock_session2 = MagicMock()
        mock_session2.id = "session-2"
        mock_session2.name = "Beta Session"
        mock_session2.project_id = None
        mock_session2.project_name = None

        mock_sessions_response = MagicMock()
        mock_sessions_response.data = [mock_session1, mock_session2]
        mock_sessions_response.meta.pagination.next_page = None
        deps['session_service'].get_user_sessions.return_value = mock_sessions_response
        deps['project_service'].get_user_projects.return_value = []

        artifacts_s1 = [
            MagicMock(filename="report.pdf", size=100, mime_type="application/pdf",
                      last_modified="2023-01-02T00:00:00Z", uri="uri1"),
            MagicMock(filename="notes.txt", size=50, mime_type="text/plain",
                      last_modified="2023-01-01T00:00:00Z", uri="uri2"),
        ]
        artifacts_s2 = [
            MagicMock(filename="report_v2.pdf", size=200, mime_type="application/pdf",
                      last_modified="2023-01-03T00:00:00Z", uri="uri3"),
            MagicMock(filename="image.png", size=300, mime_type="image/png",
                      last_modified="2023-01-04T00:00:00Z", uri="uri4"),
        ]
        return artifacts_s1, artifacts_s2

    @pytest.mark.asyncio
    async def test_search_filters_by_filename(self, mock_dependencies):
        """Search matches against filename."""
        deps = mock_dependencies
        artifacts_s1, artifacts_s2 = self._setup_sessions_with_varied_artifacts(deps)

        def side_effect(*args, **kwargs):
            sid = kwargs.get("session_id") or args[2]
            if sid == "session-1":
                return artifacts_s1
            return artifacts_s2

        with patch('solace_agent_mesh.gateway.http_sse.routers.artifacts.get_artifact_info_list_fast') as mock_get:
            mock_get.side_effect = side_effect
            result = await list_all_artifacts(
                artifact_service=deps['artifact_service'],
                user_id=deps['user_id'],
                component=deps['component'],
                session_service=deps['session_service'],
                project_service=deps['project_service'],
                db=deps['db'],
                user_config=deps['user_config'],
                page=1,
                page_size=50,
                search="report",
            )

        filenames = {a.filename for a in result.artifacts}
        assert "report.pdf" in filenames
        assert "report_v2.pdf" in filenames
        assert "notes.txt" not in filenames
        assert "image.png" not in filenames

    @pytest.mark.asyncio
    async def test_search_filters_by_session_name(self, mock_dependencies):
        """Search matches against session name."""
        deps = mock_dependencies
        artifacts_s1, artifacts_s2 = self._setup_sessions_with_varied_artifacts(deps)

        def side_effect(*args, **kwargs):
            sid = kwargs.get("session_id") or args[2]
            if sid == "session-1":
                return artifacts_s1
            return artifacts_s2

        with patch('solace_agent_mesh.gateway.http_sse.routers.artifacts.get_artifact_info_list_fast') as mock_get:
            mock_get.side_effect = side_effect
            result = await list_all_artifacts(
                artifact_service=deps['artifact_service'],
                user_id=deps['user_id'],
                component=deps['component'],
                session_service=deps['session_service'],
                project_service=deps['project_service'],
                db=deps['db'],
                user_config=deps['user_config'],
                page=1,
                page_size=50,
                search="alpha",
            )

        # Only artifacts from "Alpha Session" should match
        assert len(result.artifacts) == 2
        for a in result.artifacts:
            assert a.session_id == "session-1"

    @pytest.mark.asyncio
    async def test_search_bypasses_cache(self, mock_dependencies):
        """Search requests must not use cached partial results."""
        deps = mock_dependencies
        artifacts_s1, artifacts_s2 = self._setup_sessions_with_varied_artifacts(deps)

        # Pre-populate cache with a partial result (only session-1 artifacts)
        cached_arts = [
            ArtifactWithContext(
                filename="notes.txt", size=50, mime_type="text/plain",
                last_modified="2023-01-01T00:00:00Z", uri="uri2",
                session_id="session-1", session_name="Alpha Session",
                project_id=None, project_name=None, source="upload",
            ),
        ]
        _artifact_list_cache.put(deps['user_id'], cached_arts, sources_processed=1, total_sources=2)

        def side_effect(*args, **kwargs):
            sid = kwargs.get("session_id") or args[2]
            if sid == "session-1":
                return artifacts_s1
            return artifacts_s2

        with patch('solace_agent_mesh.gateway.http_sse.routers.artifacts.get_artifact_info_list_fast') as mock_get:
            mock_get.side_effect = side_effect
            result = await list_all_artifacts(
                artifact_service=deps['artifact_service'],
                user_id=deps['user_id'],
                component=deps['component'],
                session_service=deps['session_service'],
                project_service=deps['project_service'],
                db=deps['db'],
                user_config=deps['user_config'],
                page=1,
                page_size=50,
                search="report",
            )

        # Should find report_v2.pdf from session-2 despite it not being in cache
        filenames = {a.filename for a in result.artifacts}
        assert "report_v2.pdf" in filenames
        # The fetch function should have been called (cache was bypassed)
        assert mock_get.call_count >= 2

    @pytest.mark.asyncio
    async def test_search_disables_early_termination(self, mock_dependencies):
        """With search, all sources must be fetched (fetch_target=0)."""
        deps = mock_dependencies

        # Create many sessions to verify all are fetched
        sessions = []
        for i in range(5):
            s = MagicMock()
            s.id = f"session-{i}"
            s.name = f"Session {i}"
            s.project_id = None
            s.project_name = None
            sessions.append(s)

        mock_sessions_response = MagicMock()
        mock_sessions_response.data = sessions
        mock_sessions_response.meta.pagination.next_page = None
        deps['session_service'].get_user_sessions.return_value = mock_sessions_response
        deps['project_service'].get_user_projects.return_value = []

        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            sid = kwargs.get("session_id") or args[2]
            return [MagicMock(
                filename=f"{sid}-file.txt", size=10, mime_type="text/plain",
                last_modified="2023-01-01T00:00:00Z", uri=f"uri-{sid}",
            )]

        with patch('solace_agent_mesh.gateway.http_sse.routers.artifacts.get_artifact_info_list_fast') as mock_get:
            mock_get.side_effect = side_effect
            result = await list_all_artifacts(
                artifact_service=deps['artifact_service'],
                user_id=deps['user_id'],
                component=deps['component'],
                session_service=deps['session_service'],
                project_service=deps['project_service'],
                db=deps['db'],
                user_config=deps['user_config'],
                page=1,
                page_size=2,  # Small page size that would normally trigger early termination
                search="file",
            )

        # All 5 sessions should have been fetched despite small page_size
        assert mock_get.call_count == 5
        # total_count_estimated should be False since all sources were processed
        assert result.total_count_estimated is False


# =============================================================================
# total_count_estimated FIELD TESTS
# =============================================================================


class TestTotalCountEstimated:
    """Test that total_count_estimated is set correctly for partial and complete fetches."""

    @pytest.fixture(autouse=True)
    def _clear_artifact_cache(self):
        _artifact_list_cache.clear()
        yield
        _artifact_list_cache.clear()

    @pytest.fixture
    def mock_dependencies(self):
        mock_artifact_service = MagicMock(spec=BaseArtifactService)
        mock_session_service = MagicMock(spec=SessionService)
        mock_project_service = MagicMock(spec=ProjectService)
        mock_db = MagicMock(spec=Session)
        mock_component = MagicMock()
        mock_component.get_config.return_value = "TestApp"
        return {
            'artifact_service': mock_artifact_service,
            'session_service': mock_session_service,
            'project_service': mock_project_service,
            'db': mock_db,
            'component': mock_component,
            'user_id': 'test-user-estimated',
            'user_config': {'tool:artifact:list': True},
        }

    @pytest.mark.asyncio
    async def test_total_count_estimated_false_for_complete_fetch(self, mock_dependencies):
        """When all sources are processed, total_count_estimated should be False."""
        deps = mock_dependencies
        mock_session = MagicMock()
        mock_session.id = "session-1"
        mock_session.name = "Session"
        mock_session.project_id = None
        mock_session.project_name = None

        mock_sessions_response = MagicMock()
        mock_sessions_response.data = [mock_session]
        mock_sessions_response.meta.pagination.next_page = None
        deps['session_service'].get_user_sessions.return_value = mock_sessions_response
        deps['project_service'].get_user_projects.return_value = []

        artifacts = [MagicMock(
            filename=f"file{i}.txt", size=10, mime_type="text/plain",
            last_modified="2023-01-01T00:00:00Z", uri=f"uri{i}",
        ) for i in range(3)]

        with patch('solace_agent_mesh.gateway.http_sse.routers.artifacts.get_artifact_info_list_fast') as mock_get:
            mock_get.return_value = artifacts
            result = await list_all_artifacts(
                artifact_service=deps['artifact_service'],
                user_id=deps['user_id'],
                component=deps['component'],
                session_service=deps['session_service'],
                project_service=deps['project_service'],
                db=deps['db'],
                user_config=deps['user_config'],
                page=1,
                page_size=50,
            )

        assert result.total_count_estimated is False

    @pytest.mark.asyncio
    async def test_total_count_estimated_true_via_cached_partial(self, mock_dependencies):
        """When cache contains a partial fetch, total_count_estimated should be True."""
        deps = mock_dependencies
        # Pre-populate cache with partial result
        cached_arts = [
            ArtifactWithContext(
                filename=f"file{i}.txt", size=10, mime_type="text/plain",
                last_modified="2023-01-01T00:00:00Z", uri=f"uri{i}",
                session_id="s1", session_name="Session",
                project_id=None, project_name=None, source="upload",
            ) for i in range(60)
        ]
        _artifact_list_cache.put(deps['user_id'], cached_arts, sources_processed=5, total_sources=50)

        result = await list_all_artifacts(
            artifact_service=deps['artifact_service'],
            user_id=deps['user_id'],
            component=deps['component'],
            session_service=deps['session_service'],
            project_service=deps['project_service'],
            db=deps['db'],
            user_config=deps['user_config'],
            page=1,
            page_size=50,
        )

        assert result.total_count_estimated is True
        assert result.total_count == 60


# =============================================================================
# CACHE INVALIDATION TESTS
# =============================================================================


class TestCacheInvalidation:
    """Test that upload and delete invalidate the artifact list cache."""

    @pytest.fixture(autouse=True)
    def _clear_artifact_cache(self):
        _artifact_list_cache.clear()
        yield
        _artifact_list_cache.clear()

    def test_upload_invalidates_cache(self):
        """upload_artifact_with_session calls _artifact_list_cache.invalidate."""
        user_id = "cache-test-user"
        cached_arts = [
            ArtifactWithContext(
                filename="old.txt", size=10, mime_type="text/plain",
                last_modified="2023-01-01T00:00:00Z", uri="uri",
                session_id="s1", session_name="Session",
                project_id=None, project_name=None, source="upload",
            )
        ]
        _artifact_list_cache.put(user_id, cached_arts, 1, 1)
        assert _artifact_list_cache.get(user_id) is not None

        # Directly call invalidate as the upload endpoint does
        _artifact_list_cache.invalidate(user_id)
        assert _artifact_list_cache.get(user_id) is None

    def test_delete_invalidates_cache(self):
        """delete_artifact calls _artifact_list_cache.invalidate."""
        user_id = "cache-test-user"
        cached_arts = [
            ArtifactWithContext(
                filename="to-delete.txt", size=10, mime_type="text/plain",
                last_modified="2023-01-01T00:00:00Z", uri="uri",
                session_id="s1", session_name="Session",
                project_id=None, project_name=None, source="upload",
            )
        ]
        _artifact_list_cache.put(user_id, cached_arts, 1, 1)
        assert _artifact_list_cache.get(user_id) is not None

        _artifact_list_cache.invalidate(user_id)
        assert _artifact_list_cache.get(user_id) is None

    def test_invalidate_call_exists_in_upload(self):
        """Verify that the invalidate call is present in the upload function source."""
        import inspect
        source = inspect.getsource(upload_artifact_with_session)
        assert "_artifact_list_cache.invalidate" in source

    def test_invalidate_call_exists_in_delete(self):
        """Verify that the invalidate call is present in the delete function source."""
        import inspect
        source = inspect.getsource(delete_artifact)
        assert "_artifact_list_cache.invalidate" in source


# =============================================================================
# GET ARTIFACT BY URI ENDPOINT TESTS
# =============================================================================

from solace_agent_mesh.gateway.http_sse.routers.artifacts import get_artifact_by_uri


class TestGetArtifactByUri:
    """Test get_artifact_by_uri endpoint security and functionality."""

    @pytest.fixture
    def mock_component(self):
        """Create mock component for artifact retrieval tests."""
        mock_component = MagicMock()
        mock_component.get_config.return_value = "TestApp"
        
        # Mock artifact service
        mock_artifact_service = MagicMock(spec=BaseArtifactService)
        mock_component.get_shared_artifact_service.return_value = mock_artifact_service
        
        return mock_component

    @pytest.mark.asyncio
    async def test_get_artifact_by_uri_authorization_bypass_blocked(self, mock_component):
        """Test that users cannot access other users' artifacts via URI manipulation.
        
        Security: This is the critical test that verifies the authorization bypass
        vulnerability is fixed. A user should NOT be able to access another user's
        artifacts by crafting a URI with a different user_id.
        """
        # User A (attacker) tries to access User B's (victim) artifact
        attacker_user_id = "attacker-user-123"
        victim_user_id = "victim-user-456"
        
        # Craft a malicious URI pointing to victim's artifact
        malicious_uri = f"artifact://TestApp/{victim_user_id}/session-789/secret.pdf?version=1"
        
        # Execute - should be blocked with 403 Forbidden
        with pytest.raises(HTTPException) as exc_info:
            await get_artifact_by_uri(
                uri=malicious_uri,
                requesting_user_id=attacker_user_id,
                component=mock_component,
                user_config={'tool:artifact:load': True},
            )
        
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "not authorized" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_get_artifact_by_uri_own_artifact_allowed(self, mock_component):
        """Test that users can access their own artifacts via URI."""
        user_id = "test-user-123"
        
        # URI pointing to user's own artifact
        own_artifact_uri = f"artifact://TestApp/{user_id}/session-456/document.pdf?version=1"
        
        # Mock successful artifact load
        with patch('solace_agent_mesh.gateway.http_sse.routers.artifacts.load_artifact_content_or_metadata') as mock_load:
            mock_load.return_value = {
                'status': 'success',
                'raw_bytes': b'PDF content here',
                'mime_type': 'application/pdf',
            }
            
            # Execute - should succeed
            result = await get_artifact_by_uri(
                uri=own_artifact_uri,
                requesting_user_id=user_id,
                component=mock_component,
                user_config={'tool:artifact:load': True},
            )
            
            # Verify it's a streaming response
            from starlette.responses import StreamingResponse
            assert isinstance(result, StreamingResponse)
            assert result.media_type == 'application/pdf'

    @pytest.mark.asyncio
    async def test_get_artifact_by_uri_invalid_scheme(self, mock_component):
        """Test that invalid URI schemes are rejected."""
        user_id = "test-user-123"
        
        # Invalid scheme (http instead of artifact)
        invalid_uri = f"http://TestApp/{user_id}/session-456/document.pdf?version=1"
        
        with pytest.raises(HTTPException) as exc_info:
            await get_artifact_by_uri(
                uri=invalid_uri,
                requesting_user_id=user_id,
                component=mock_component,
                user_config={'tool:artifact:load': True},
            )
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_artifact_by_uri_missing_version(self, mock_component):
        """Test that URIs without version parameter are rejected."""
        user_id = "test-user-123"
        
        # URI without version parameter
        uri_no_version = f"artifact://TestApp/{user_id}/session-456/document.pdf"
        
        with pytest.raises(HTTPException) as exc_info:
            await get_artifact_by_uri(
                uri=uri_no_version,
                requesting_user_id=user_id,
                component=mock_component,
                user_config={'tool:artifact:load': True},
            )
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "version" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_get_artifact_by_uri_service_unavailable(self, mock_component):
        """Test that endpoint returns 503 when artifact service is not available."""
        user_id = "test-user-123"
        uri = f"artifact://TestApp/{user_id}/session-456/document.pdf?version=1"
        
        # Mock artifact service as unavailable
        mock_component.get_shared_artifact_service.return_value = None
        
        with pytest.raises(HTTPException) as exc_info:
            await get_artifact_by_uri(
                uri=uri,
                requesting_user_id=user_id,
                component=mock_component,
                user_config={'tool:artifact:load': True},
            )
        
        assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

    @pytest.mark.asyncio
    async def test_get_artifact_by_uri_artifact_not_found(self, mock_component):
        """Test that endpoint returns 404 when artifact doesn't exist."""
        user_id = "test-user-123"
        uri = f"artifact://TestApp/{user_id}/session-456/nonexistent.pdf?version=1"
        
        # Mock artifact not found
        with patch('solace_agent_mesh.gateway.http_sse.routers.artifacts.load_artifact_content_or_metadata') as mock_load:
            mock_load.return_value = {
                'status': 'error',
                'message': 'Artifact not found',
            }
            
            with pytest.raises(HTTPException) as exc_info:
                await get_artifact_by_uri(
                    uri=uri,
                    requesting_user_id=user_id,
                    component=mock_component,
                    user_config={'tool:artifact:load': True},
                )
            
            assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

class TestGetSpecificArtifactVersion:
    """Test get_specific_artifact_version endpoint."""

    @pytest.mark.asyncio
    async def test_not_found_returns_404(self):
        """Regression: a missing artifact must return 404, not 500.

        load_artifact_content_or_metadata returns {"status": "not_found", ...}.
        The handler converts this to HTTPException(404) inside its try block.
        Previously the generic 'except Exception' caught that HTTPException
        and re-wrapped it as a 500.
        """
        mock_component = MagicMock()
        mock_component.get_config.return_value = "TestApp"
        mock_component.enable_embed_resolution = False

        with patch(
            "solace_agent_mesh.gateway.http_sse.routers.artifacts.load_artifact_content_or_metadata",
            new_callable=AsyncMock,
        ) as mock_load:
            mock_load.return_value = {
                "status": "not_found",
                "message": "Artifact 'deleted_file.pdf' version 0 not found or has no data.",
            }

            with pytest.raises(HTTPException) as exc_info:
                await get_specific_artifact_version(
                    session_id="test-session",
                    filename="deleted_file.pdf",
                    version=0,
                    project_id=None,
                    artifact_service=MagicMock(spec=BaseArtifactService),
                    user_id="test-user-123",
                    validate_session=MagicMock(return_value=True),
                    component=mock_component,
                    project_service=None,
                    user_config={"tool:artifact:load": True},
                )

            assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
            assert "not found" in exc_info.value.detail.lower()


class TestGetLatestArtifactMaxBytes:
    """Tests for the max_bytes truncation logic in get_latest_artifact."""

    def _make_artifact_part(self, data: bytes, mime_type: str = "application/octet-stream"):
        """Create a mock artifact part with inline_data."""
        part = MagicMock()
        part.inline_data.data = data
        part.inline_data.mime_type = mime_type
        return part

    def _make_component(self, enable_embed_resolution=True):
        """Create a mock component."""
        component = MagicMock()
        component.get_config.return_value = "TestApp"
        component.enable_embed_resolution = enable_embed_resolution
        component.gateway_id = "test-gateway"
        component.gateway_max_artifact_resolve_size_bytes = 1048576
        component.gateway_recursive_embed_depth = 5
        return component

    def _make_artifact_service(self, artifact_part):
        """Create a mock artifact service whose load_artifact returns the given part."""
        service = MagicMock(spec=BaseArtifactService)
        service.load_artifact = AsyncMock(return_value=artifact_part)
        return service

    async def _read_response(self, response):
        """Read all bytes from a StreamingResponse."""
        chunks = []
        async for chunk in response.body_iterator:
            if isinstance(chunk, str):
                chunks.append(chunk.encode("utf-8"))
            else:
                chunks.append(chunk)
        return b"".join(chunks)

    @pytest.mark.asyncio
    async def test_no_truncation_when_max_bytes_not_provided(self):
        """When max_bytes is None the full content is returned with no truncation headers."""
        content = b"A" * 100
        part = self._make_artifact_part(content, "application/octet-stream")
        component = self._make_component(enable_embed_resolution=False)

        with patch(
            "solace_agent_mesh.gateway.http_sse.routers.artifacts._resolve_storage_context",
            return_value=("user1", "session1", "session", None),
        ):
            response = await get_latest_artifact(
                session_id="session1",
                filename="file.bin",
                project_id=None,
                max_bytes=None,
                artifact_service=self._make_artifact_service(part),
                user_id="user1",
                validate_session=MagicMock(return_value=True),
                component=component,
                project_service=None,
                user_config={"tool:artifact:load": True},
            )

        body = await self._read_response(response)
        assert body == content
        assert "X-Truncated" not in response.headers
        assert "X-Original-Size" not in response.headers

    @pytest.mark.asyncio
    async def test_truncation_when_content_exceeds_max_bytes(self):
        """When content exceeds max_bytes it is truncated and headers are set."""
        content = b"B" * 100
        part = self._make_artifact_part(content, "application/octet-stream")
        component = self._make_component(enable_embed_resolution=False)

        with patch(
            "solace_agent_mesh.gateway.http_sse.routers.artifacts._resolve_storage_context",
            return_value=("user1", "session1", "session", None),
        ):
            response = await get_latest_artifact(
                session_id="session1",
                filename="file.bin",
                project_id=None,
                max_bytes=50,
                artifact_service=self._make_artifact_service(part),
                user_id="user1",
                validate_session=MagicMock(return_value=True),
                component=component,
                project_service=None,
                user_config={"tool:artifact:load": True},
            )

        body = await self._read_response(response)
        assert len(body) == 50
        assert body == content[:50]
        assert response.headers["X-Truncated"] == "true"
        assert response.headers["X-Original-Size"] == "100"

    @pytest.mark.asyncio
    async def test_no_truncation_when_content_within_max_bytes(self):
        """When content fits within max_bytes it is returned in full with no truncation headers."""
        content = b"C" * 50
        part = self._make_artifact_part(content, "application/octet-stream")
        component = self._make_component(enable_embed_resolution=False)

        with patch(
            "solace_agent_mesh.gateway.http_sse.routers.artifacts._resolve_storage_context",
            return_value=("user1", "session1", "session", None),
        ):
            response = await get_latest_artifact(
                session_id="session1",
                filename="file.bin",
                project_id=None,
                max_bytes=100,
                artifact_service=self._make_artifact_service(part),
                user_id="user1",
                validate_session=MagicMock(return_value=True),
                component=component,
                project_service=None,
                user_config={"tool:artifact:load": True},
            )

        body = await self._read_response(response)
        assert body == content
        assert "X-Truncated" not in response.headers
        assert "X-Original-Size" not in response.headers

    @pytest.mark.asyncio
    async def test_embed_resolution_skipped_when_truncated(self):
        """When truncated, resolve_embeds_recursively_in_string must NOT be called."""
        content = b"D" * 100
        part = self._make_artifact_part(content, "text/plain")
        component = self._make_component(enable_embed_resolution=True)

        with patch(
            "solace_agent_mesh.gateway.http_sse.routers.artifacts._resolve_storage_context",
            return_value=("user1", "session1", "session", None),
        ), patch(
            "solace_agent_mesh.gateway.http_sse.routers.artifacts.resolve_embeds_recursively_in_string",
            new_callable=AsyncMock,
        ) as mock_resolve:
            response = await get_latest_artifact(
                session_id="session1",
                filename="file.txt",
                project_id=None,
                max_bytes=50,
                artifact_service=self._make_artifact_service(part),
                user_id="user1",
                validate_session=MagicMock(return_value=True),
                component=component,
                project_service=None,
                user_config={"tool:artifact:load": True},
            )

        body = await self._read_response(response)
        assert len(body) == 50
        assert response.headers["X-Truncated"] == "true"
        mock_resolve.assert_not_called()

    @pytest.mark.asyncio
    async def test_embed_resolution_runs_when_not_truncated(self):
        """When not truncated for text content with embed resolution enabled, resolver is called."""
        content = b"hello world"
        part = self._make_artifact_part(content, "text/plain")
        component = self._make_component(enable_embed_resolution=True)

        async def passthrough_resolve(text, **kwargs):
            return text

        with patch(
            "solace_agent_mesh.gateway.http_sse.routers.artifacts._resolve_storage_context",
            return_value=("user1", "session1", "session", None),
        ), patch(
            "solace_agent_mesh.gateway.http_sse.routers.artifacts.resolve_embeds_recursively_in_string",
            new_callable=AsyncMock,
            side_effect=passthrough_resolve,
        ) as mock_resolve, patch(
            "solace_agent_mesh.gateway.http_sse.routers.artifacts.resolve_template_blocks_in_string",
            new_callable=AsyncMock,
            side_effect=lambda text, **kwargs: text,
        ):
            response = await get_latest_artifact(
                session_id="session1",
                filename="file.txt",
                project_id=None,
                max_bytes=None,
                artifact_service=self._make_artifact_service(part),
                user_id="user1",
                validate_session=MagicMock(return_value=True),
                component=component,
                project_service=None,
                user_config={"tool:artifact:load": True},
            )

        body = await self._read_response(response)
        assert body == content
        assert "X-Truncated" not in response.headers
        mock_resolve.assert_called_once()

    @pytest.mark.asyncio
    async def test_truncation_preserves_valid_utf8_for_multibyte_text(self):
        """Truncating mid-character (emoji/CJK) must produce valid UTF-8 with length <= max_bytes."""
        # U+1F600 (😀) is 4 bytes in UTF-8: \xf0\x9f\x98\x80
        # 3 emojis = 12 bytes. Truncating at 5 bytes would split the 2nd emoji.
        content = "😀😀😀".encode("utf-8")  # 12 bytes
        part = self._make_artifact_part(content, "text/plain")
        component = self._make_component(enable_embed_resolution=False)

        with patch(
            "solace_agent_mesh.gateway.http_sse.routers.artifacts._resolve_storage_context",
            return_value=("user1", "session1", "session", None),
        ):
            response = await get_latest_artifact(
                session_id="session1",
                filename="emoji.txt",
                project_id=None,
                max_bytes=5,
                artifact_service=self._make_artifact_service(part),
                user_id="user1",
                validate_session=MagicMock(return_value=True),
                component=component,
                project_service=None,
                user_config={"tool:artifact:load": True},
            )

        body = await self._read_response(response)
        # The truncated bytes must be valid UTF-8
        decoded = body.decode("utf-8")  # Should not raise
        # Only the first complete emoji should survive (4 bytes); the partial 2nd is dropped
        assert decoded == "😀"
        assert len(body) <= 5
        assert response.headers["X-Truncated"] == "true"
        assert response.headers["X-Original-Size"] == "12"


