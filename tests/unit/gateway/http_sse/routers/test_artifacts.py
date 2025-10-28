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
        # Mock FastAPI Request
        mock_request = MagicMock()
        mock_request.headers = {}
        
        # Mock UploadFile
        mock_upload_file = MagicMock(spec=UploadFile)
        mock_upload_file.filename = "test.txt"
        mock_upload_file.content_type = "text/plain"
        mock_upload_file.read = AsyncMock(return_value=b"test content")
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
        mock_component.get_config.return_value = "TestApp"
        
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
        large_content = b"x" * (10 * 1024 * 1024)  # 10MB file
        deps['upload_file'].read = AsyncMock(return_value=large_content)
        
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
            ("image.png", "image/png", b"\x89PNG\r\n\x1a\n"),
            ("document.pdf", "application/pdf", b"%PDF-1.4"),
            ("data.json", "application/json", b'{"key": "value"}'),
            ("script.py", "text/x-python", b"print('hello')"),
            ("unknown.xyz", "application/octet-stream", b"binary data")
        ]
        
        for filename, mime_type, content in file_types:
            deps['upload_file'].filename = filename
            deps['upload_file'].content_type = mime_type
            deps['upload_file'].read = AsyncMock(return_value=content)
            
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
        mock_component.get_config.return_value = "TestApp"
        
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
        mock_component.get_config.return_value = "TestApp"
        
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
        """Test artifact listing fails when session validation fails."""
        # Setup
        deps = mock_dependencies
        deps['validate_session'].return_value = False
        
        # Execute & Verify
        with pytest.raises(HTTPException) as exc_info:
            await list_artifacts(
                session_id="invalid-session",
                artifact_service=deps['artifact_service'],
                user_id=deps['user_id'],
                validate_session=deps['validate_session'],
                component=deps['component'],
                user_config=deps['user_config']
            )
        
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert "Session not found or access denied" in str(exc_info.value.detail)

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
        mock_component.get_config.return_value = "TestApp"
        
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


class TestIntegrationScenarios:
    """Test integration scenarios and edge cases."""

    @pytest.fixture
    def mock_full_stack(self):
        """Create full mock stack for integration tests."""
        # Mock all dependencies
        mock_request = MagicMock()
        mock_request.headers = {}
        
        mock_upload_file = MagicMock(spec=UploadFile)
        mock_upload_file.filename = "integration_test.txt"
        mock_upload_file.content_type = "text/plain"
        mock_upload_file.read = AsyncMock(return_value=b"integration test content")
        mock_upload_file.close = AsyncMock()
        
        mock_artifact_service = MagicMock(spec=BaseArtifactService)
        mock_artifact_service.load_artifact = AsyncMock()
        mock_artifact_service.list_versions = AsyncMock()
        mock_artifact_service.delete_artifact = AsyncMock()
        
        mock_session_manager = MagicMock(spec=SessionManager)
        mock_session_manager.create_new_session_id.return_value = "integration-session-123"
        
        mock_session_service = MagicMock(spec=SessionService)
        mock_session_service.create_session = MagicMock()
        
        mock_db = MagicMock(spec=Session)
        mock_db.commit = MagicMock()
        mock_db.rollback = MagicMock()
        
        mock_component = MagicMock()
        mock_component.get_config.return_value = "IntegrationTestApp"
        mock_component.enable_embed_resolution = False
        mock_component.get_shared_artifact_service.return_value = mock_artifact_service
        
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
            'user_id': 'integration-user-123',
            'user_config': {
                'tool:artifact:create': True,
                'tool:artifact:load': True,
                'tool:artifact:list': True,
                'tool:artifact:delete': True
            }
        }

    @pytest.mark.asyncio
    async def test_concurrent_upload_operations(self, mock_full_stack):
        """Test concurrent artifact upload operations."""
        # Setup
        deps = mock_full_stack
        
        # Create multiple upload files
        upload_files = []
        for i in range(3):
            mock_file = MagicMock(spec=UploadFile)
            mock_file.filename = f"concurrent_test_{i}.txt"
            mock_file.content_type = "text/plain"
            mock_file.read = AsyncMock(return_value=f"content {i}".encode())
            mock_file.close = AsyncMock()
            upload_files.append(mock_file)
        
        # Mock successful upload results
        with patch('solace_agent_mesh.gateway.http_sse.routers.artifacts.process_artifact_upload') as mock_process:
            mock_process.side_effect = [
                {
                    'status': 'success',
                    'artifact_uri': f'artifact://IntegrationTestApp/integration-user-123/test-session/concurrent_test_{i}.txt?version=1',
                    'version': 1
                }
                for i in range(3)
            ]
            
            # Execute concurrent uploads
            tasks = []
            for i, upload_file in enumerate(upload_files):
                task = upload_artifact_with_session(
                    request=deps['request'],
                    upload_file=upload_file,
                    sessionId="test-session",
                    filename=f"concurrent_test_{i}.txt",
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
                tasks.append(task)
            
            # Wait for all uploads to complete
            results = await asyncio.gather(*tasks)
            
            # Verify all uploads succeeded
            assert len(results) == 3
            for i, result in enumerate(results):
                assert isinstance(result, ArtifactUploadResponse)
                assert result.filename == f"concurrent_test_{i}.txt"

    @pytest.mark.asyncio
    async def test_artifact_storage_quota_limits(self, mock_full_stack):
        """Test artifact upload with storage quota limits."""
        # Setup
        deps = mock_full_stack
        
        # Mock storage quota exceeded
        with patch('solace_agent_mesh.gateway.http_sse.routers.artifacts.process_artifact_upload') as mock_process:
            mock_process.return_value = {
                'status': 'error',
                'message': 'Storage quota exceeded',
                'error': 'quota_exceeded'
            }
            
            # Execute & Verify
            with pytest.raises(HTTPException) as exc_info:
                await upload_artifact_with_session(
                    request=deps['request'],
                    upload_file=deps['upload_file'],
                    sessionId="test-session",
                    filename="large_file.bin",
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
            
            assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert "Storage quota exceeded" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_malformed_multipart_request_handling(self, mock_full_stack):
        """Test handling of malformed multipart requests."""
        # Setup
        deps = mock_full_stack
        
        # Mock file read error (simulating malformed multipart)
        deps['upload_file'].read = AsyncMock(side_effect=Exception("Malformed multipart data"))
        
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
        
        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Failed to store artifact due to an internal error" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_path_traversal_prevention(self, mock_full_stack):
        """Test prevention of path traversal attacks in filenames."""
        # Setup
        deps = mock_full_stack
        
        malicious_filenames = [
            "../../../etc/passwd",
            "..\\..\\windows\\system32\\config\\sam",
            "test/../../../sensitive.txt",
            "normal.txt/../../../etc/hosts"
        ]
        
        for malicious_filename in malicious_filenames:
            # Mock upload process to detect path traversal
            with patch('solace_agent_mesh.gateway.http_sse.routers.artifacts.process_artifact_upload') as mock_process:
                mock_process.return_value = {
                    'status': 'error',
                    'message': 'Invalid filename: path traversal detected',
                    'error': 'invalid_filename'
                }
                
                # Execute & Verify
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
                
                assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
                assert "Invalid filename" in str(exc_info.value.detail)


class TestFileHandlingAndValidation:
    """Test file handling and validation scenarios."""

    @pytest.fixture
    def mock_file_dependencies(self):
        """Create mock dependencies for file handling tests."""
        mock_request = MagicMock()
        mock_request.headers = {}
        
        mock_artifact_service = MagicMock(spec=BaseArtifactService)
        mock_session_manager = MagicMock(spec=SessionManager)
        mock_session_service = MagicMock(spec=SessionService)
        mock_db = MagicMock(spec=Session)
        mock_component = MagicMock()
        mock_component.get_config.return_value = "TestApp"
        mock_validate_session = MagicMock(return_value=True)
        
        return {
            'request': mock_request,
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
    async def test_file_corruption_detection(self, mock_file_dependencies):
        """Test detection and handling of corrupted files."""
        # Setup
        deps = mock_file_dependencies
        
        # Create mock corrupted file
        mock_upload_file = MagicMock(spec=UploadFile)
        mock_upload_file.filename = "corrupted.jpg"
        mock_upload_file.content_type = "image/jpeg"
        mock_upload_file.read = AsyncMock(return_value=b"corrupted data not a real jpeg")
        mock_upload_file.close = AsyncMock()
        
        # Mock corruption detection in upload process
        with patch('solace_agent_mesh.gateway.http_sse.routers.artifacts.process_artifact_upload') as mock_process:
            mock_process.return_value = {
                'status': 'error',
                'message': 'File appears to be corrupted',
                'error': 'corrupted_file'
            }
            
            # Execute & Verify
            with pytest.raises(HTTPException) as exc_info:
                await upload_artifact_with_session(
                    request=deps['request'],
                    upload_file=mock_upload_file,
                    sessionId="test-session",
                    filename="corrupted.jpg",
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
            
            assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert "File appears to be corrupted" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_invalid_mime_type_handling(self, mock_file_dependencies):
        """Test handling of invalid MIME types."""
        # Setup
        deps = mock_file_dependencies
        
        # Create mock file with invalid MIME type
        mock_upload_file = MagicMock(spec=UploadFile)
        mock_upload_file.filename = "test.txt"
        mock_upload_file.content_type = "invalid/mime-type"
        mock_upload_file.read = AsyncMock(return_value=b"test content")
        mock_upload_file.close = AsyncMock()
        
        # Mock successful upload (MIME type should be normalized)
        with patch('solace_agent_mesh.gateway.http_sse.routers.artifacts.process_artifact_upload') as mock_process:
            mock_process.return_value = {
                'status': 'success',
                'artifact_uri': 'artifact://TestApp/test-user-123/test-session/test.txt?version=1',
                'version': 1
            }
            
            # Execute
            result = await upload_artifact_with_session(
                request=deps['request'],
                upload_file=mock_upload_file,
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
            
            # Verify - should succeed with normalized MIME type
            assert isinstance(result, ArtifactUploadResponse)
            assert result.mime_type == "invalid/mime-type"  # Should preserve original

    @pytest.mark.asyncio
    async def test_empty_file_handling(self, mock_file_dependencies):
        """Test handling of empty files."""
        # Setup
        deps = mock_file_dependencies
        
        # Create mock empty file
        mock_upload_file = MagicMock(spec=UploadFile)
        mock_upload_file.filename = "empty.txt"
        mock_upload_file.content_type = "text/plain"
        mock_upload_file.read = AsyncMock(return_value=b"")  # Empty content
        mock_upload_file.close = AsyncMock()
        
        # Mock empty file detection
        with patch('solace_agent_mesh.gateway.http_sse.routers.artifacts.process_artifact_upload') as mock_process:
            mock_process.return_value = {
                'status': 'error',
                'message': 'Empty files are not allowed',
                'error': 'empty_file'
            }
            
            # Execute & Verify
            with pytest.raises(HTTPException) as exc_info:
                await upload_artifact_with_session(
                    request=deps['request'],
                    upload_file=mock_upload_file,
                    sessionId="test-session",
                    filename="empty.txt",
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
            assert "Empty files are not allowed" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_file_streaming_for_large_files(self, mock_file_dependencies):
        """Test file streaming for large files during retrieval."""
        # Setup
        deps = mock_file_dependencies
        
        # Create large file content (simulate streaming)
        large_content = b"x" * (50 * 1024 * 1024)  # 50MB
        
        mock_inline_data = MagicMock()
        mock_inline_data.data = large_content
        mock_inline_data.mime_type = "application/octet-stream"
        
        mock_artifact_part = MagicMock()
        mock_artifact_part.inline_data = mock_inline_data
        
        deps['artifact_service'].load_artifact = AsyncMock(return_value=mock_artifact_part)
        
        # Execute
        result = await get_latest_artifact(
            session_id="test-session",
            filename="large_file.bin",
            artifact_service=deps['artifact_service'],
            user_id=deps['user_id'],
            validate_session=deps['validate_session'],
            component=deps['component'],
            user_config={'tool:artifact:load': True}
        )
        
        # Verify streaming response
        assert isinstance(result, StreamingResponse)
        assert result.media_type == "application/octet-stream"