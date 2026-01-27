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

        # Both path and filename are required
        config = DefaultArtifactConfig(path="/path/to/file.txt", filename="file.txt")
        assert config.path == "/path/to/file.txt"
        assert config.filename == "file.txt"
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

    def test_default_artifact_config_missing_required_fields(self):
        """Test that missing required fields raise validation error."""
        from solace_agent_mesh.agent.sac.app import DefaultArtifactConfig
        from pydantic import ValidationError

        # Missing filename should raise error
        with pytest.raises(ValidationError):
            DefaultArtifactConfig(path="/path/to/file.txt")

        # Missing path should raise error
        with pytest.raises(ValidationError):
            DefaultArtifactConfig(filename="file.txt")


class TestScopedArtifactServiceWrapper:
    """Tests for the ScopedArtifactServiceWrapper with default artifacts support."""

    @pytest.fixture
    def mock_wrapped_service(self):
        """Create a mock wrapped artifact service."""
        service = AsyncMock()
        service.save_artifact = AsyncMock(return_value=1)
        service.load_artifact = AsyncMock(return_value=None)
        service.list_artifact_keys = AsyncMock(return_value=[])
        service.delete_artifact = AsyncMock(return_value=None)
        service.list_versions = AsyncMock(return_value=[])
        return service

    @pytest.fixture
    def mock_component(self):
        """Create a mock component."""
        component = MagicMock()
        component.agent_name = "test_agent"
        component.namespace = "test_namespace"
        component.log_identifier = "[TestAgent]"
        component.get_config = MagicMock(side_effect=lambda key, default=None: {
            "default_artifacts": [],
            "artifact_scope": "namespace",
            "agent_name": "test_agent",
        }.get(key, default))
        return component

    @pytest.mark.asyncio
    async def test_load_artifact_fallback_to_defaults(self, mock_wrapped_service, mock_component):
        """Test that load_artifact falls back to agent defaults when user artifact not found."""
        from solace_agent_mesh.agent.adk.services import (
            ScopedArtifactServiceWrapper,
            AGENT_DEFAULTS_USER_ID,
        )

        # Configure default artifacts
        mock_component.get_config = MagicMock(side_effect=lambda key, default=None: {
            "default_artifacts": [{"path": "/test/file.txt", "filename": "test.txt"}],
            "artifact_scope": "namespace",
            "agent_name": "test_agent",
        }.get(key, default))

        # Create wrapper with new API
        wrapper = ScopedArtifactServiceWrapper(
            wrapped_service=mock_wrapped_service,
            component=mock_component,
        )

        # Mock: user artifact not found, but default exists
        default_artifact = adk_types.Part.from_text(text="default content")
        mock_wrapped_service.load_artifact = AsyncMock(
            side_effect=[None, default_artifact]  # First call (user) returns None, second (default) returns artifact
        )

        # Load artifact
        result = await wrapper.load_artifact(
            app_name="test_agent",
            user_id="user123",
            session_id="session456",
            filename="test.txt",
        )

        # Verify fallback was used
        assert result == default_artifact
        assert mock_wrapped_service.load_artifact.call_count == 2

        # Verify first call was for user
        first_call = mock_wrapped_service.load_artifact.call_args_list[0]
        assert first_call.kwargs["user_id"] == "user123"

        # Verify second call was for defaults
        second_call = mock_wrapped_service.load_artifact.call_args_list[1]
        assert second_call.kwargs["user_id"] == AGENT_DEFAULTS_USER_ID

    @pytest.mark.asyncio
    async def test_load_artifact_user_takes_precedence(self, mock_wrapped_service, mock_component):
        """Test that user's artifact takes precedence over default."""
        from solace_agent_mesh.agent.adk.services import ScopedArtifactServiceWrapper

        # Configure default artifacts
        mock_component.get_config = MagicMock(side_effect=lambda key, default=None: {
            "default_artifacts": [{"path": "/test/file.txt", "filename": "test.txt"}],
            "artifact_scope": "namespace",
            "agent_name": "test_agent",
        }.get(key, default))

        wrapper = ScopedArtifactServiceWrapper(
            wrapped_service=mock_wrapped_service,
            component=mock_component,
        )

        # Mock: user artifact exists
        user_artifact = adk_types.Part.from_text(text="user content")
        mock_wrapped_service.load_artifact = AsyncMock(return_value=user_artifact)

        # Load artifact
        result = await wrapper.load_artifact(
            app_name="test_agent",
            user_id="user123",
            session_id="session456",
            filename="test.txt",
        )

        # Verify user artifact was returned
        assert result == user_artifact
        # Should only call once (no fallback needed)
        assert mock_wrapped_service.load_artifact.call_count == 1

    @pytest.mark.asyncio
    async def test_list_artifact_keys_merges_defaults(self, mock_wrapped_service, mock_component):
        """Test that list_artifact_keys includes both user and default artifacts."""
        from solace_agent_mesh.agent.adk.services import (
            ScopedArtifactServiceWrapper,
            AGENT_DEFAULTS_USER_ID,
        )

        # Configure default artifacts
        mock_component.get_config = MagicMock(side_effect=lambda key, default=None: {
            "default_artifacts": [
                {"path": "/test/default1.txt", "filename": "default1.txt"},
                {"path": "/test/default2.txt", "filename": "default2.txt"},
            ],
            "artifact_scope": "namespace",
            "agent_name": "test_agent",
        }.get(key, default))

        wrapper = ScopedArtifactServiceWrapper(
            wrapped_service=mock_wrapped_service,
            component=mock_component,
        )

        # Mock: user has one artifact, defaults have two
        mock_wrapped_service.list_artifact_keys = AsyncMock(
            side_effect=[
                ["user_file.txt"],  # User artifacts
                ["default1.txt", "default2.txt"],  # Default artifacts
            ]
        )

        # List artifacts
        result = await wrapper.list_artifact_keys(
            app_name="test_agent",
            user_id="user123",
            session_id="session456",
        )

        # Verify merged list (unique keys)
        assert set(result) == {"user_file.txt", "default1.txt", "default2.txt"}

    @pytest.mark.asyncio
    async def test_delete_artifact_prevents_default_deletion(self, mock_wrapped_service, mock_component):
        """Test that deleting a default artifact raises PermissionError."""
        from solace_agent_mesh.agent.adk.services import ScopedArtifactServiceWrapper

        # Configure default artifacts
        mock_component.get_config = MagicMock(side_effect=lambda key, default=None: {
            "default_artifacts": [{"path": "/test/protected.txt", "filename": "protected.txt"}],
            "artifact_scope": "namespace",
            "agent_name": "test_agent",
        }.get(key, default))

        wrapper = ScopedArtifactServiceWrapper(
            wrapped_service=mock_wrapped_service,
            component=mock_component,
        )

        # Mock: user doesn't have this artifact (it's a default)
        mock_wrapped_service.load_artifact = AsyncMock(return_value=None)

        # Attempt to delete default artifact should raise PermissionError
        with pytest.raises(PermissionError, match="Cannot delete default artifact"):
            await wrapper.delete_artifact(
                app_name="test_agent",
                user_id="user123",
                session_id="session456",
                filename="protected.txt",
            )

    @pytest.mark.asyncio
    async def test_save_artifact_allows_shadowing(self, mock_wrapped_service, mock_component):
        """Test that users can save their own version of a default artifact (shadowing)."""
        from solace_agent_mesh.agent.adk.services import ScopedArtifactServiceWrapper

        # Configure default artifacts
        mock_component.get_config = MagicMock(side_effect=lambda key, default=None: {
            "default_artifacts": [{"path": "/test/file.txt", "filename": "file.txt"}],
            "artifact_scope": "namespace",
            "agent_name": "test_agent",
        }.get(key, default))

        wrapper = ScopedArtifactServiceWrapper(
            wrapped_service=mock_wrapped_service,
            component=mock_component,
        )

        # Save user's version of the artifact
        user_artifact = adk_types.Part.from_text(text="user's version")
        mock_wrapped_service.save_artifact = AsyncMock(return_value=1)

        result = await wrapper.save_artifact(
            app_name="test_agent",
            user_id="user123",
            session_id="session456",
            filename="file.txt",
            artifact=user_artifact,
        )

        # Verify save was called with user's credentials
        assert result == 1
        mock_wrapped_service.save_artifact.assert_called_once()
        call_kwargs = mock_wrapped_service.save_artifact.call_args.kwargs
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
            mock_component.namespace = "test_namespace"
            mock_component.log_identifier = "[TestAgent]"
            mock_component.artifact_service = AsyncMock()
            
            # Mock list_versions to return empty (artifact doesn't exist yet)
            mock_component.artifact_service.list_versions = AsyncMock(return_value=[])
            
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
                    "artifact_scope": "namespace",
                }.get(key, default)
            )

            # Import and call the method
            from solace_agent_mesh.agent.sac.component import SamAgentComponent

            # Mock save_artifact_with_metadata - patch where it's used (in component module)
            with patch('solace_agent_mesh.agent.utils.artifact_helpers.save_artifact_with_metadata', new_callable=AsyncMock) as mock_save:
                mock_save.return_value = {"status": "success", "version": 0}
                
                # Call the method directly (we need to bind it to our mock)
                await SamAgentComponent._load_default_artifacts(mock_component)

                # Verify save_artifact_with_metadata was called
                mock_save.assert_called_once()
                call_kwargs = mock_save.call_args.kwargs
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
        mock_component.namespace = "test_namespace"
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
        mock_component.namespace = "test_namespace"
        mock_component.log_identifier = "[TestAgent]"
        mock_component.artifact_service = AsyncMock()
        mock_component.get_config = MagicMock(return_value=[])

        from solace_agent_mesh.agent.sac.component import SamAgentComponent

        await SamAgentComponent._load_default_artifacts(mock_component)

        # Verify save was NOT called
        mock_component.artifact_service.save_artifact.assert_not_called()

    @pytest.mark.asyncio
    async def test_load_default_artifacts_skips_existing(self):
        """Test that existing artifacts are not re-loaded."""
        from solace_agent_mesh.agent.adk.services import AGENT_DEFAULTS_USER_ID

        # Create a temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Test content for default artifact")
            temp_file_path = f.name

        try:
            mock_component = MagicMock()
            mock_component.agent_name = "test_agent"
            mock_component.namespace = "test_namespace"
            mock_component.log_identifier = "[TestAgent]"
            mock_component.artifact_service = AsyncMock()
            
            # Mock list_versions to return existing version (artifact already exists)
            mock_component.artifact_service.list_versions = AsyncMock(return_value=[0])
            
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
                    "artifact_scope": "namespace",
                }.get(key, default)
            )

            from solace_agent_mesh.agent.sac.component import SamAgentComponent

            # Mock save_artifact_with_metadata - patch where it's used (in artifact_helpers module)
            with patch('solace_agent_mesh.agent.utils.artifact_helpers.save_artifact_with_metadata', new_callable=AsyncMock) as mock_save:
                mock_save.return_value = {"status": "success", "version": 0}
                
                await SamAgentComponent._load_default_artifacts(mock_component)

                # Verify save_artifact_with_metadata was NOT called (artifact already exists)
                mock_save.assert_not_called()

        finally:
            os.unlink(temp_file_path)


class TestAgentDefaultsUserIdConstant:
    """Tests for the AGENT_DEFAULTS_USER_ID constant."""

    def test_constant_value(self):
        """Test that the constant has the expected value."""
        from solace_agent_mesh.agent.adk.services import AGENT_DEFAULTS_USER_ID

        assert AGENT_DEFAULTS_USER_ID == "__agent_defaults__"
        # Ensure it's a string that won't conflict with real user IDs
        assert AGENT_DEFAULTS_USER_ID.startswith("__")
        assert AGENT_DEFAULTS_USER_ID.endswith("__")
