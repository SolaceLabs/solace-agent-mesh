"""
Unit tests for artifact helper metadata version resolution.
Tests the fix for loading metadata with correct version when metadata and data files have different versions.
"""

import pytest
import json
from unittest.mock import Mock, AsyncMock, patch


class TestLoadArtifactMetadataVersionResolution:
    """Test the metadata version resolution in load_artifact_content_or_metadata function."""

    @pytest.fixture
    def mock_artifact_service(self):
        """Mock artifact service for testing."""
        service = Mock()
        return service

    @pytest.fixture
    def mock_component(self):
        """Mock component for testing."""
        component = Mock()
        component.get_config.return_value = 10000  # text_artifact_content_max_length
        return component

    @pytest.mark.asyncio
    async def test_load_metadata_uses_metadata_file_versions(self, mock_artifact_service):
        """Test that load_metadata_only=True resolves 'latest' using metadata file versions.
        
        This is important because updating metadata may create a new metadata version
        without creating a new data version (if the artifact service deduplicates content).
        """
        # Import here to avoid module-level import issues
        from solace_agent_mesh.agent.utils.artifact_helpers import load_artifact_content_or_metadata
        
        # Mock the artifact part with metadata
        metadata_dict = {"filename": "test.txt", "mime_type": "text/plain", "description": "Updated description"}
        metadata_json = json.dumps(metadata_dict)
        
        mock_part = Mock()
        mock_part.inline_data = Mock()
        mock_part.inline_data.mime_type = "application/json"
        mock_part.inline_data.data = metadata_json.encode("utf-8")
        
        mock_artifact_service.load_artifact = AsyncMock(return_value=mock_part)
        
        # Track which filename was used for list_versions
        list_versions_calls = []
        async def track_list_versions(**kwargs):
            list_versions_calls.append(kwargs.get("filename"))
            # Return different versions based on filename
            if kwargs.get("filename", "").endswith(".metadata.json"):
                return [1, 2]  # Metadata has 2 versions
            return [1]  # Data file has only 1 version
        
        mock_artifact_service.list_versions = AsyncMock(side_effect=track_list_versions)
        
        result = await load_artifact_content_or_metadata(
            artifact_service=mock_artifact_service,
            app_name="testapp",
            user_id="user123",
            session_id="session456",
            filename="test.txt",
            version="latest",
            load_metadata_only=True
        )
        
        assert result["status"] == "success"
        # Verify list_versions was called with metadata filename
        assert len(list_versions_calls) == 1
        assert list_versions_calls[0] == "test.txt.metadata.json"
        # Verify the latest metadata version (2) was loaded
        assert result["version"] == 2

    @pytest.mark.asyncio
    async def test_load_content_uses_data_file_versions(self, mock_artifact_service, mock_component):
        """Test that load_metadata_only=False resolves 'latest' using data file versions."""
        # Import here to avoid module-level import issues
        from solace_agent_mesh.agent.utils.artifact_helpers import load_artifact_content_or_metadata
        
        content = "Test content"
        
        mock_part = Mock()
        mock_part.inline_data = Mock()
        mock_part.inline_data.mime_type = "text/plain"
        mock_part.inline_data.data = content.encode("utf-8")
        
        mock_artifact_service.load_artifact = AsyncMock(return_value=mock_part)
        
        # Track which filename was used for list_versions
        list_versions_calls = []
        async def track_list_versions(**kwargs):
            list_versions_calls.append(kwargs.get("filename"))
            return [1, 2, 3]  # Data file has 3 versions
        
        mock_artifact_service.list_versions = AsyncMock(side_effect=track_list_versions)
        
        with patch('solace_agent_mesh.agent.utils.artifact_helpers.is_text_based_file', return_value=True):
            result = await load_artifact_content_or_metadata(
                artifact_service=mock_artifact_service,
                app_name="testapp",
                user_id="user123",
                session_id="session456",
                filename="test.txt",
                version="latest",
                load_metadata_only=False,
                component=mock_component
            )
        
        assert result["status"] == "success"
        # Verify list_versions was called with data filename (not metadata)
        assert len(list_versions_calls) == 1
        assert list_versions_calls[0] == "test.txt"
        # Verify the latest data version (3) was loaded
        assert result["version"] == 3

    @pytest.mark.asyncio
    async def test_metadata_version_mismatch_scenario(self, mock_artifact_service):
        """Test the real-world scenario where metadata is updated but data stays the same.
        
        Scenario:
        1. User uploads file -> data v1, metadata v1
        2. User edits description -> data v1 (unchanged), metadata v2
        3. Loading metadata with 'latest' should get v2 with updated description
        """
        # Import here to avoid module-level import issues
        from solace_agent_mesh.agent.utils.artifact_helpers import load_artifact_content_or_metadata
        
        # Metadata v2 has updated description
        metadata_v2 = {
            "filename": "document.pdf",
            "mime_type": "application/pdf",
            "description": "Updated description after edit",
            "size_bytes": 1024
        }
        metadata_json = json.dumps(metadata_v2)
        
        mock_part = Mock()
        mock_part.inline_data = Mock()
        mock_part.inline_data.mime_type = "application/json"
        mock_part.inline_data.data = metadata_json.encode("utf-8")
        
        # Track load_artifact calls to verify correct version is requested
        load_calls = []
        async def track_load(**kwargs):
            load_calls.append({
                "filename": kwargs.get("filename"),
                "version": kwargs.get("version")
            })
            return mock_part
        
        mock_artifact_service.load_artifact = AsyncMock(side_effect=track_load)
        
        # Simulate: data file has 1 version, metadata file has 2 versions
        async def version_lookup(**kwargs):
            filename = kwargs.get("filename", "")
            if filename.endswith(".metadata.json"):
                return [1, 2]  # Metadata was updated (v2)
            return [1]  # Data file unchanged (v1)
        
        mock_artifact_service.list_versions = AsyncMock(side_effect=version_lookup)
        
        result = await load_artifact_content_or_metadata(
            artifact_service=mock_artifact_service,
            app_name="testapp",
            user_id="user123",
            session_id="session456",
            filename="document.pdf",
            version="latest",
            load_metadata_only=True
        )
        
        assert result["status"] == "success"
        assert result["version"] == 2  # Should load metadata v2
        assert result["metadata"]["description"] == "Updated description after edit"
        
        # Verify load_artifact was called with metadata filename and version 2
        assert len(load_calls) == 1
        assert load_calls[0]["filename"] == "document.pdf.metadata.json"
        assert load_calls[0]["version"] == 2
