"""
Unit tests for the default artifacts feature.

This module tests the ability to configure default artifacts for agents
that are automatically available to all users without requiring upload.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import os
import tempfile

from google.genai import types as adk_types


class TestDefaultArtifactConfig:
    """Tests for the DefaultArtifactConfig schema."""

    def test_default_artifact_config_minimal(self):
        """Test creating a DefaultArtifactConfig with only required fields."""
        from solace_agent_mesh.agent.sac.app import DefaultArtifactConfig

        config = DefaultArtifactConfig(path="/path/to/file.txt")
        assert config.path == "/path/to/file.txt"
        assert config.filename is None
        assert config.mime_type is None
        assert config.description is None

    def test_default_artifact_config_full(self):
        """Test creating a DefaultArtifactConfig with all fields."""
        from solace_agent_mesh.agent.sac.app import DefaultArtifactConfig

        config = DefaultArtifactConfig(
            path="/path/to/file.txt",
            filename="custom_name.txt",
            mime_type="text/plain",
            description="A test file",
        )
        assert config.path == "/path/to/file.txt"
        assert config.filename == "custom_name.txt"
        assert config.mime_type == "text/plain"
        assert config.description == "A test file"


class TestScopedArtifactServiceWrapper:
    """Tests for the ScopedArtifactServiceWrapper with default artifacts support."""

    @pytest.fixture
    def mock_base_service(self):
        """Create a mock base artifact service."""
        service = AsyncMock()
        service.save_artifact = AsyncMock(return_value=1)
        service.load_artifact = AsyncMock(return_value=None)
        service.list_artifact_keys = AsyncMock(return_value=[])
        service.delete_artifact = AsyncMock(return_value=None)
        return service

    @pytest.fixture
    def mock_host_component(self):
        """Create a mock host component."""
        component = MagicMock()
        component.agent_name = "test_agent"
        component.log_identifier = "[TestAgent]"
        component.get_config = MagicMock(return_value=[])
        return component

    @pytest.mark.asyncio
    async def test_load_artifact_fallback_to_defaults(self, mock_base_service, mock_host_component):
        """Test that load_artifact falls back to agent defaults when user artifact not found."""
        from solace_agent_mesh.agent.adk.services import (
            ScopedArtifactServiceWrapper,
            AGENT_DEFAULTS_USER_ID,
        )

        # Configure default artifacts
        mock_host_component.get_config = MagicMock(
            return_value=[{"path": "/test/file.txt", "filename": "test.txt"}]
        )

        # Create wrapper
        wrapper = ScopedArtifactServiceWrapper(
            base_service=mock_base_service,
            app_name="test_agent",
            user_id="user123",
            session_id="session456",
            host_component=mock_host_component,
        )

        # Mock: user artifact not found, but default exists
        default_artifact = adk_types.Part.from_text(text="default content")
        mock_base_service.load_artifact = AsyncMock(
            side_effect=[None, default_artifact]  # First call (user) returns None, second (default) returns artifact
        )

        # Load artifact
        result = await wrapper.load_artifact(filename="test.txt")

        # Verify fallback was used
        assert result == default_artifact
        assert mock_base_service.load_artifact.call_count == 2

        # Verify first call was for user
        first_call = mock_base_service.load_artifact.call_args_list[0]
        assert first_call.kwargs["user_id"] == "user123"

        # Verify second call was for defaults
        second_call = mock_base_service.load_artifact.call_args_list[1]
        assert second_call.kwargs["user_id"] == AGENT_DEFAULTS_USER_ID

    @pytest.mark.asyncio
    async def test_load_artifact_user_takes_precedence(self, mock_base_service, mock_host_component):
        """Test that user's artifact takes precedence over default."""
        from solace_agent_mesh.agent.adk.services import ScopedArtifactServiceWrapper

        # Configure default artifacts
        mock_host_component.get_config = MagicMock(
            return_value=[{"path": "/test/file.txt", "filename": "test.txt"}]
        )

        wrapper = ScopedArtifactServiceWrapper(
            base_service=mock_base_service,
            app_name="test_agent",
            user_id="user123",
            session_id="session456",
            host_component=mock_host_component,
        )

        # Mock: user artifact exists
        user_artifact = adk_types.Part.from_text(text="user content")
        mock_base_service.load_artifact = AsyncMock(return_value=user_artifact)

        # Load artifact
        result = await wrapper.load_artifact(filename="test.txt")

        # Verify user artifact was returned
        assert result == user_artifact
        # Should only call once (no fallback needed)
        assert mock_base_service.load_artifact.call_count == 1

    @pytest.mark.asyncio
    async def test_list_artifact_keys_merges_defaults(self, mock_base_service, mock_host_component):
        """Test that list_artifact_keys includes both user and default artifacts."""
        from solace_agent_mesh.agent.adk.services import (
            ScopedArtifactServiceWrapper,
            AGENT_DEFAULTS_USER_ID,
        )

        # Configure default artifacts
        mock_host_component.get_config = MagicMock(
            return_value=[
                {"path": "/test/default1.txt", "filename": "default1.txt"},
                {"path": "/test/default2.txt", "filename": "default2.txt"},
            ]
        )

        wrapper = ScopedArtifactServiceWrapper(
            base_service=mock_base_service,
            app_name="test_agent",
            user_id="user123",
            session_id="session456",
            host_component=mock_host_component,
        )

        # Mock: user has one artifact, defaults have two
        mock_base_service.list_artifact_keys = AsyncMock(
            side_effect=[
                ["user_file.txt"],  # User artifacts
                ["default1.txt", "default2.txt"],  # Default artifacts
            ]
        )

        # List artifacts
        result = await wrapper.list_artifact_keys()

        # Verify merged list (unique keys)
        assert set(result) == {"user_file.txt", "default1.txt", "default2.txt"}

    @pytest.mark.asyncio
    async def test_delete_artifact_prevents_default_deletion(self, mock_base_service, mock_host_component):
        """Test that deleting a default artifact raises PermissionError."""
        from solace_agent_mesh.agent.adk.services import ScopedArtifactServiceWrapper

        # Configure default artifacts
        mock_host_component.get_config = MagicMock(
            return_value=[{"path": "/test/protected.txt", "filename": "protected.txt"}]
        )

        wrapper = ScopedArtifactServiceWrapper(
            base_service=mock_base_service,
            app_name="test_agent",
            user_id="user123",
            session_id="session456",
            host_component=mock_host_component,
        )

        # Mock: user doesn't have this artifact (it's a default)
        mock_base_service.list_artifact_keys = AsyncMock(return_value=[])

        # Attempt to delete default artifact should raise PermissionError
        with pytest.raises(PermissionError, match="Cannot delete default artifact"):
            await wrapper.delete_artifact(filename="protected.txt")

    @pytest.mark.asyncio
    async def test_save_artifact_allows_shadowing(self, mock_base_service, mock_host_component):
        """Test that users can save their own version of a default artifact (shadowing)."""
        from solace_agent_mesh.agent.adk.services import ScopedArtifactServiceWrapper

        # Configure default artifacts
        mock_host_component.get_config = MagicMock(
            return_value=[{"path": "/test/file.txt", "filename": "file.txt"}]
        )

        wrapper = ScopedArtifactServiceWrapper(
            base_service=mock_base_service,
            app_name="test_agent",
            user_id="user123",
            session_id="session456",
            host_component=mock_host_component,
        )

        # Save user's version of the artifact
        user_artifact = adk_types.Part.from_text(text="user's version")
        mock_base_service.save_artifact = AsyncMock(return_value=1)

        result = await wrapper.save_artifact(filename="file.txt", artifact=user_artifact)

        # Verify save was called with user's credentials
        assert result == 1
        mock_base_service.save_artifact.assert_called_once()
        call_kwargs = mock_base_service.save_artifact.call_args.kwargs
        assert call_kwargs["user_id"] == "user123"


class TestLoadDefaultArtifacts:
    """Tests for the _load_default_artifacts method in SamAgentComponent."""

    @pytest.mark.asyncio
    async def test_load_default_artifacts_from_file(self):
        """Test loading default artifacts from actual files."""
        from solace_agent_mesh.agent.adk.services import AGENT_DEFAULTS_USER_ID

        # Create a temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Test content for default artifact")
            temp_file_path = f.name

        try:
            # Create mock component
            mock_component = MagicMock()
            mock_component.agent_name = "test_agent"
            mock_component.log_identifier = "[TestAgent]"
            mock_component.artifact_service = AsyncMock()
            mock_component.artifact_service.save_artifact = AsyncMock(return_value=1)
            mock_component.get_config = MagicMock(
                side_effect=lambda key, default=None: {
                    "default_artifacts": [
                        {
                            "path": temp_file_path,
                            "filename": "test_default.txt",
                            "mime_type": "text/plain",
                            "description": "A test default artifact",
                        }
                    ],
                    "base_path": ".",
                }.get(key, default)
            )

            # Import and call the method
            from solace_agent_mesh.agent.sac.component import SamAgentComponent

            # Call the method directly (we need to bind it to our mock)
            await SamAgentComponent._load_default_artifacts(mock_component)

            # Verify artifact was saved with correct parameters
            mock_component.artifact_service.save_artifact.assert_called_once()
            call_kwargs = mock_component.artifact_service.save_artifact.call_args.kwargs
            assert call_kwargs["app_name"] == "test_agent"
            assert call_kwargs["user_id"] == AGENT_DEFAULTS_USER_ID
            assert call_kwargs["filename"] == "test_default.txt"

        finally:
            # Cleanup
            os.unlink(temp_file_path)

    @pytest.mark.asyncio
    async def test_load_default_artifacts_handles_missing_file(self):
        """Test that missing files are handled gracefully."""
        mock_component = MagicMock()
        mock_component.agent_name = "test_agent"
        mock_component.log_identifier = "[TestAgent]"
        mock_component.artifact_service = AsyncMock()
        mock_component.get_config = MagicMock(
            side_effect=lambda key, default=None: {
                "default_artifacts": [
                    {"path": "/nonexistent/file.txt", "filename": "missing.txt"}
                ],
                "base_path": ".",
            }.get(key, default)
        )

        from solace_agent_mesh.agent.sac.component import SamAgentComponent

        # Should not raise, just log error
        await SamAgentComponent._load_default_artifacts(mock_component)

        # Verify save was NOT called (file doesn't exist)
        mock_component.artifact_service.save_artifact.assert_not_called()

    @pytest.mark.asyncio
    async def test_load_default_artifacts_no_config(self):
        """Test that no action is taken when no default artifacts are configured."""
        mock_component = MagicMock()
        mock_component.agent_name = "test_agent"
        mock_component.log_identifier = "[TestAgent]"
        mock_component.artifact_service = AsyncMock()
        mock_component.get_config = MagicMock(return_value=[])

        from solace_agent_mesh.agent.sac.component import SamAgentComponent

        await SamAgentComponent._load_default_artifacts(mock_component)

        # Verify save was NOT called
        mock_component.artifact_service.save_artifact.assert_not_called()


class TestAgentDefaultsUserIdConstant:
    """Tests for the AGENT_DEFAULTS_USER_ID constant."""

    def test_constant_value(self):
        """Test that the constant has the expected value."""
        from solace_agent_mesh.agent.adk.services import AGENT_DEFAULTS_USER_ID

        assert AGENT_DEFAULTS_USER_ID == "__agent_defaults__"
        # Ensure it's a string that won't conflict with real user IDs
        assert AGENT_DEFAULTS_USER_ID.startswith("__")
        assert AGENT_DEFAULTS_USER_ID.endswith("__")
