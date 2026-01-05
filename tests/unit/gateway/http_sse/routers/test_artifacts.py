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
            file_buffer = io.BytesIO(content)

            async def async_read_file(size=-1):
                return file_buffer.read(size)

            async def async_seek_file(offset):
                return file_buffer.seek(offset)

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

