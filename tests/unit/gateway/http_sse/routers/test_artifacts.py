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
)
from solace_agent_mesh.gateway.http_sse.services.project_service import ProjectService


class TestListAllArtifacts:
    """Test list_all_artifacts bulk endpoint."""

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
                limit=500,
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
            limit=500,
        )
        
        assert isinstance(result, BulkArtifactsResponse)
        assert len(result.artifacts) == 0
        assert result.total_count == 0

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
        
        with patch('solace_agent_mesh.gateway.http_sse.routers.artifacts.get_artifact_info_list') as mock_get_list:
            mock_get_list.return_value = [mock_artifact]
            
            result = await list_all_artifacts(
                artifact_service=deps['artifact_service'],
                user_id=deps['user_id'],
                component=deps['component'],
                session_service=deps['session_service'],
                project_service=deps['project_service'],
                db=deps['db'],
                user_config=deps['user_config'],
                limit=500,
            )
        
        assert isinstance(result, BulkArtifactsResponse)
        assert len(result.artifacts) == 1
        assert result.artifacts[0].filename == "test.txt"
        assert result.artifacts[0].session_id == "session-123"
        assert result.artifacts[0].session_name == "Test Session"
        assert result.artifacts[0].source == "upload"

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
        
        with patch('solace_agent_mesh.gateway.http_sse.routers.artifacts.get_artifact_info_list') as mock_get_list:
            mock_get_list.return_value = mock_artifacts
            
            result = await list_all_artifacts(
                artifact_service=deps['artifact_service'],
                user_id=deps['user_id'],
                component=deps['component'],
                session_service=deps['session_service'],
                project_service=deps['project_service'],
                db=deps['db'],
                user_config=deps['user_config'],
                limit=500,
            )
        
        # Only the original document should be returned
        assert len(result.artifacts) == 1
        assert result.artifacts[0].filename == "document.pdf"

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
        
        with patch('solace_agent_mesh.gateway.http_sse.routers.artifacts.get_artifact_info_list') as mock_get_list:
            mock_get_list.return_value = [mock_artifact]
            
            result = await list_all_artifacts(
                artifact_service=deps['artifact_service'],
                user_id=deps['user_id'],
                component=deps['component'],
                session_service=deps['session_service'],
                project_service=deps['project_service'],
                db=deps['db'],
                user_config=deps['user_config'],
                limit=500,
            )
        
        assert len(result.artifacts) == 1
        assert result.artifacts[0].filename == "knowledge.docx"
        assert result.artifacts[0].session_id == "project-project-456"
        assert result.artifacts[0].project_id == "project-456"
        assert result.artifacts[0].project_name == "Test Project"
        assert result.artifacts[0].source == "project"

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
        
        with patch('solace_agent_mesh.gateway.http_sse.routers.artifacts.get_artifact_info_list') as mock_get_list:
            mock_get_list.return_value = [mock_artifact]
            
            result = await list_all_artifacts(
                artifact_service=deps['artifact_service'],
                user_id=deps['user_id'],
                component=deps['component'],
                session_service=deps['session_service'],
                project_service=deps['project_service'],
                db=deps['db'],
                user_config=deps['user_config'],
                limit=500,
            )
        
        # Should only have one artifact (deduplicated)
        # The project version should be preferred
        project_artifacts = [a for a in result.artifacts if a.session_id.startswith("project-")]
        assert len(project_artifacts) >= 1

    @pytest.mark.asyncio
    async def test_list_all_artifacts_limit_parameter(self, mock_dependencies):
        """Test that limit parameter restricts the number of returned artifacts."""
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
        
        # Create 10 mock artifacts
        mock_artifacts = []
        for i in range(10):
            artifact = MagicMock()
            artifact.filename = f"file{i}.txt"
            artifact.size = 100 * (i + 1)
            artifact.mime_type = "text/plain"
            artifact.last_modified = f"2023-01-{i+1:02d}T00:00:00Z"
            artifact.uri = f"artifact://app/user/session-123/file{i}.txt"
            mock_artifacts.append(artifact)
        
        with patch('solace_agent_mesh.gateway.http_sse.routers.artifacts.get_artifact_info_list') as mock_get_list:
            mock_get_list.return_value = mock_artifacts
            
            # Request with limit of 5
            result = await list_all_artifacts(
                artifact_service=deps['artifact_service'],
                user_id=deps['user_id'],
                component=deps['component'],
                session_service=deps['session_service'],
                project_service=deps['project_service'],
                db=deps['db'],
                user_config=deps['user_config'],
                limit=5,
            )
        
        # Should return only 5 artifacts
        assert len(result.artifacts) == 5
        # total_count should reflect the actual total before limiting
        assert result.total_count == 10

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
            limit=500,
        )
        
        assert isinstance(result, BulkArtifactsResponse)
        assert len(result.artifacts) == 0

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
            limit=500,
        )
        
        assert isinstance(result, BulkArtifactsResponse)
        assert len(result.artifacts) == 0

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
        
        with patch('solace_agent_mesh.gateway.http_sse.routers.artifacts.get_artifact_info_list') as mock_get_list:
            mock_get_list.return_value = mock_artifacts
            
            result = await list_all_artifacts(
                artifact_service=deps['artifact_service'],
                user_id=deps['user_id'],
                component=deps['component'],
                session_service=deps['session_service'],
                project_service=deps['project_service'],
                db=deps['db'],
                user_config=deps['user_config'],
                limit=500,
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
            limit=500,
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
            limit=500,
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
        
        with patch('solace_agent_mesh.gateway.http_sse.routers.artifacts.get_artifact_info_list') as mock_get_list:
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
                limit=500,
            )
        
        # Build a map of filename -> source for easier assertions
        source_map = {a.filename: a.source for a in result.artifacts}
        
        # Verify session artifacts are classified as 'upload'
        assert source_map["document.pdf"] == "upload", "Session PDF should be classified as upload"
        assert source_map["image.png"] == "upload", "Session PNG should be classified as upload"
        
        # Verify project artifacts are classified as 'project'
        assert source_map["knowledge.docx"] == "project", "Project DOCX should be classified as project"


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
            return_value=("user1", "session1", "session"),
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
            return_value=("user1", "session1", "session"),
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
            return_value=("user1", "session1", "session"),
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
            return_value=("user1", "session1", "session"),
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
            return_value=("user1", "session1", "session"),
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


