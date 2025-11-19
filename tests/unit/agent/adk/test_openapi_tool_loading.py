"""Tests for OpenAPI tool loading in setup.py."""
import sys
import pytest
from unittest.mock import Mock, patch
from solace_agent_mesh.agent.adk.setup import _load_openapi_tool


# Create a mock enterprise module for testing
class MockEnterpriseModule:
    """Mock enterprise module for testing delegation."""
    class MockAuth:
        class MockToolConfigurator:
            @staticmethod
            def configure_openapi_tool(tool_type, tool_config):
                raise NotImplementedError("This should be mocked in tests")

        tool_configurator = MockToolConfigurator()

    auth = MockAuth()


@pytest.fixture
def mock_component():
    """Mock SamAgentComponent for testing."""
    component = Mock()
    component.log_identifier = "[TestAgent]"
    return component


@pytest.fixture
def mock_enterprise_modules():
    """Create mock enterprise modules for testing."""
    mock_enterprise = MockEnterpriseModule()
    modules = {
        'solace_agent_mesh_enterprise': mock_enterprise,
        'solace_agent_mesh_enterprise.auth': mock_enterprise.auth,
        'solace_agent_mesh_enterprise.auth.tool_configurator': mock_enterprise.auth.tool_configurator
    }
    return mock_enterprise, modules


class TestOpenApiToolDelegation:
    """Test that _load_openapi_tool correctly delegates to enterprise."""

    @pytest.mark.asyncio
    async def test_successful_delegation(self, mock_component, mock_enterprise_modules):
        """Test that successful tool creation returns the toolset with origin set."""
        mock_enterprise, modules = mock_enterprise_modules
        mock_toolset = Mock(origin=None)
        mock_configurator = Mock(return_value=mock_toolset)
        mock_enterprise.auth.tool_configurator.configure_openapi_tool = mock_configurator

        tool_config = {
            "tool_type": "openapi",
            "specification": '{"openapi": "3.0.0"}'
        }

        with patch.dict('sys.modules', modules):
            result = await _load_openapi_tool(mock_component, tool_config)

        # Verify result structure
        assert len(result) == 3  # tools, builtins, cleanups
        assert len(result[0]) == 1  # one toolset
        assert result[0][0] is mock_toolset
        assert result[0][0].origin == "openapi"
        assert result[1] == []  # no builtins
        assert result[2] == []  # no cleanups

        # Verify configurator was called correctly
        mock_configurator.assert_called_once_with(
            tool_type="openapi",
            tool_config=tool_config
        )

    @pytest.mark.asyncio
    async def test_enterprise_validation_error(self, mock_component, mock_enterprise_modules):
        """Test that validation errors from enterprise are propagated."""
        mock_enterprise, modules = mock_enterprise_modules
        mock_configurator = Mock(side_effect=ValueError("Invalid configuration"))
        mock_enterprise.auth.tool_configurator.configure_openapi_tool = mock_configurator

        tool_config = {
            "tool_type": "openapi",
            "specification": '{"invalid": "spec"}'
        }

        with patch.dict('sys.modules', modules):
            with pytest.raises(ValueError, match="Invalid configuration"):
                await _load_openapi_tool(mock_component, tool_config)

    @pytest.mark.asyncio
    async def test_enterprise_not_available(self, mock_component):
        """Test graceful handling when enterprise package is not installed."""
        tool_config = {
            "tool_type": "openapi",
            "specification": '{"openapi": "3.0.0"}'
        }

        # Block import of enterprise module
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if 'solace_agent_mesh_enterprise' in name:
                raise ImportError(f"No module named '{name}'")
            return real_import(name, *args, **kwargs)

        with patch('builtins.__import__', side_effect=mock_import):
            result = await _load_openapi_tool(mock_component, tool_config)

        # Should return empty result and log warning
        assert result == ([], [], [])

    @pytest.mark.asyncio
    async def test_config_validation_with_allow_list(self, mock_component, mock_enterprise_modules):
        """Test that configs with allow_list pass validation."""
        mock_enterprise, modules = mock_enterprise_modules
        mock_toolset = Mock(origin=None)
        mock_configurator = Mock(return_value=mock_toolset)
        mock_enterprise.auth.tool_configurator.configure_openapi_tool = mock_configurator

        tool_config = {
            "tool_type": "openapi",
            "specification": '{"openapi": "3.0.0"}',
            "allow_list": ["getPet", "createPet"]
        }

        with patch.dict('sys.modules', modules):
            result = await _load_openapi_tool(mock_component, tool_config)

        # Should succeed and pass config to enterprise
        assert len(result[0]) == 1
        mock_configurator.assert_called_once_with(
            tool_type="openapi",
            tool_config=tool_config
        )

    @pytest.mark.asyncio
    async def test_config_validation_with_deny_list(self, mock_component, mock_enterprise_modules):
        """Test that configs with deny_list pass validation."""
        mock_enterprise, modules = mock_enterprise_modules
        mock_toolset = Mock(origin=None)
        mock_configurator = Mock(return_value=mock_toolset)
        mock_enterprise.auth.tool_configurator.configure_openapi_tool = mock_configurator

        tool_config = {
            "tool_type": "openapi",
            "specification": '{"openapi": "3.0.0"}',
            "deny_list": ["deletePet"]
        }

        with patch.dict('sys.modules', modules):
            result = await _load_openapi_tool(mock_component, tool_config)

        # Should succeed and pass config to enterprise
        assert len(result[0]) == 1
        mock_configurator.assert_called_once_with(
            tool_type="openapi",
            tool_config=tool_config
        )

    @pytest.mark.asyncio
    async def test_config_validation_mutual_exclusivity_fails(self, mock_component, mock_enterprise_modules):
        """Test that configs with both allow_list and deny_list fail validation."""
        _, modules = mock_enterprise_modules

        tool_config = {
            "tool_type": "openapi",
            "specification": '{"openapi": "3.0.0"}',
            "allow_list": ["getPet"],
            "deny_list": ["deletePet"]
        }

        with patch.dict('sys.modules', modules):
            # Should raise validation error before calling enterprise
            with pytest.raises(Exception) as exc_info:
                await _load_openapi_tool(mock_component, tool_config)

            # Verify it's a validation error about mutual exclusivity
            error_msg = str(exc_info.value).lower()
            assert "allow_list" in error_msg or "deny_list" in error_msg

    @pytest.mark.asyncio
    async def test_invalid_config_fails_validation(self, mock_component):
        """Test that invalid config structure fails validation before enterprise call."""
        tool_config = {
            "tool_type": "wrong_type",  # Invalid tool_type
            "specification": '{"openapi": "3.0.0"}'
        }

        # Block import of enterprise module to ensure we're testing validation, not enterprise
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if 'solace_agent_mesh_enterprise' in name:
                raise ImportError(f"No module named '{name}'")
            return real_import(name, *args, **kwargs)

        # Should raise validation error before even trying to import enterprise
        with patch('builtins.__import__', side_effect=mock_import):
            with pytest.raises(Exception):
                await _load_openapi_tool(mock_component, tool_config)
