"""
Unit tests for WebUIBackendComponent._init_feature_checker().

Tests cover three behaviours:
- Community flags are loaded and the SamFeatureProvider is registered with OpenFeature.
- Enterprise flags are merged into the registry when the enterprise package is available.
- An absent enterprise package (ImportError) is handled gracefully; community flags
  continue to work normally.
"""

import sys
import types
from unittest.mock import MagicMock

import pytest
from openfeature import api as openfeature_api

from solace_agent_mesh.common.features.provider import SamFeatureProvider
from solace_agent_mesh.gateway.http_sse.component import WebUIBackendComponent


@pytest.fixture(autouse=True)
def _reset_openfeature():
    yield
    openfeature_api.clear_providers()


def _call_init_feature_checker():
    """Invoke _init_feature_checker on a minimal mock component instance."""
    mock_self = MagicMock()
    mock_self.log_identifier = "[test]"
    WebUIBackendComponent._init_feature_checker(mock_self)
    return mock_self


class TestInitFeatureCheckerCommunity:
    """Community flags are loaded and the provider is registered."""

    def test_community_flags_loaded_and_provider_registered(self):
        mock_self = _call_init_feature_checker()

        provider = openfeature_api.provider_registry.get_default_provider()
        assert isinstance(provider, SamFeatureProvider)


class TestInitFeatureCheckerEnterprise:
    """Enterprise extension is triggered correctly after the provider is set."""

    def test_enterprise_extension_invoked_when_package_available(self, monkeypatch):
        called = []

        fake_module = types.SimpleNamespace(
            _register_enterprise_feature_flags=lambda: called.append(True)
        )
        monkeypatch.setitem(
            sys.modules,
            "solace_agent_mesh_enterprise.init_enterprise",
            fake_module,
        )

        _call_init_feature_checker()

        assert called, "_register_enterprise_feature_flags was not called"

    def test_community_works_when_enterprise_not_installed(self, monkeypatch):
        monkeypatch.setitem(
            sys.modules, "solace_agent_mesh_enterprise.init_enterprise", None
        )

        _call_init_feature_checker()

        provider = openfeature_api.provider_registry.get_default_provider()
        assert isinstance(provider, SamFeatureProvider)

    def test_enterprise_extension_called_after_provider_is_set(self, monkeypatch):
        provider_at_call_time = []

        def _fake_register():
            provider_at_call_time.append(
                openfeature_api.provider_registry.get_default_provider()
            )

        fake_module = types.SimpleNamespace(
            _register_enterprise_feature_flags=_fake_register
        )
        monkeypatch.setitem(
            sys.modules,
            "solace_agent_mesh_enterprise.init_enterprise",
            fake_module,
        )

        _call_init_feature_checker()

        assert len(provider_at_call_time) == 1
        assert isinstance(provider_at_call_time[0], SamFeatureProvider)
