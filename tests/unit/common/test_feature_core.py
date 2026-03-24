"""
Unit tests for the feature flag service module.

Each test class is isolated: the autouse fixture resets module state and
clears the OpenFeature global provider before and after every test so that
state never leaks between tests or test files.

Synthetic flag keys (never real production flag names) are used throughout
so that tests do not couple to specific feature flag definitions.
"""

import os
import threading
from unittest.mock import patch

import pytest
from openfeature import api as openfeature_api

from solace_agent_mesh.common.features.provider import SamFeatureProvider

from solace_agent_mesh.common.features.core import (
    _reset_for_testing,
    get_registry,
    has_env_override,
    initialize,
    is_known_flag,
    load_flags_from_yaml,
)
import solace_agent_mesh.common.features.core as feature_core_module


@pytest.fixture(autouse=True)
def _reset():
    _reset_for_testing()
    yield
    _reset_for_testing()


class TestLazyInitialization:
    """Module does not initialize on import; first use triggers init."""

    def test_not_initialized_at_start(self):
        assert feature_core_module._initialized is False
        assert feature_core_module._checker is None

    def test_is_known_flag_triggers_init(self):
        is_known_flag("any_key")
        assert feature_core_module._initialized is True

    def test_get_registry_triggers_init(self):
        get_registry()
        assert feature_core_module._initialized is True


class TestIdempotentInitialization:
    """initialize() is safe to call multiple times and from multiple threads."""

    def test_double_initialize_reuses_checker(self):
        initialize()
        checker_first = feature_core_module._checker
        initialize()
        assert feature_core_module._checker is checker_first

    def test_concurrent_initialization_no_errors(self):
        errors = []

        def _init():
            try:
                initialize()
            except Exception as exc:  # pylint: disable=broad-except
                errors.append(exc)

        threads = [threading.Thread(target=_init) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert feature_core_module._initialized is True

    def test_concurrent_init_produces_single_checker(self):
        checkers = []

        def _capture():
            initialize()
            checkers.append(feature_core_module._checker)

        threads = [threading.Thread(target=_capture) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert all(c is checkers[0] for c in checkers)


class TestCommunityYamlLoading:
    """Community features.yaml loads cleanly and produces a valid registry."""

    def test_community_yaml_loads_without_error(self):
        initialize()
        flags = get_registry().all()
        assert len(flags) > 0
        for defn in flags:
            assert defn.key != ""
            assert defn.jira != ""

    def test_unknown_flag_returns_false(self):
        initialize()
        assert openfeature_api.get_client().get_boolean_value("__nonexistent_flag_xyz__", False) is False


class TestLoadFlagsFromYaml:
    """load_flags_from_yaml() merges additional definitions without removing existing ones."""

    def test_extra_yaml_merged_preserves_community_flags(self, tmp_path):
        extra_yaml = tmp_path / "extra.yaml"
        extra_yaml.write_text(
            "features:\n"
            "  - key: test_alpha_flag\n"
            "    name: Test Alpha\n"
            "    release_phase: experimental\n"
            "    default: true\n"
            "    jira: DATAGO-99999\n"
        )

        initialize()
        community_count = len(get_registry().all())
        load_flags_from_yaml(str(extra_yaml))

        client = openfeature_api.get_client()
        assert is_known_flag("test_alpha_flag")
        assert client.get_boolean_value("test_alpha_flag", False) is True
        assert len(get_registry().all()) == community_count + 1

    def test_extra_yaml_with_multiple_flags(self, tmp_path):
        extra_yaml = tmp_path / "extra.yaml"
        extra_yaml.write_text(
            "features:\n"
            "  - key: test_beta_flag\n"
            "    name: Test Beta\n"
            "    release_phase: beta\n"
            "    default: false\n"
            "    jira: DATAGO-99999\n"
            "  - key: test_gamma_flag\n"
            "    name: Test Gamma\n"
            "    release_phase: early_access\n"
            "    default: true\n"
            "    jira: DATAGO-99999\n"
        )

        initialize()
        load_flags_from_yaml(str(extra_yaml))

        client = openfeature_api.get_client()
        assert is_known_flag("test_beta_flag")
        assert is_known_flag("test_gamma_flag")
        assert client.get_boolean_value("test_beta_flag", False) is False
        assert client.get_boolean_value("test_gamma_flag", False) is True


class TestOpenFeatureIntegration:
    """OpenFeature provider is correctly registered and evaluation goes through it."""

    def test_provider_is_sam_feature_provider_after_init(self):
        initialize()
        provider = openfeature_api.provider_registry.get_default_provider()
        assert isinstance(provider, SamFeatureProvider)

    def test_openfeature_client_evaluates_registered_flag(self, tmp_path):
        extra_yaml = tmp_path / "extra.yaml"
        extra_yaml.write_text(
            "features:\n"
            "  - key: test_of_flag\n"
            "    name: Test OF Flag\n"
            "    release_phase: general_availability\n"
            "    default: true\n"
            "    jira: DATAGO-99999\n"
        )
        initialize()
        load_flags_from_yaml(str(extra_yaml))

        assert openfeature_api.get_client().get_boolean_value("test_of_flag", False) is True


class TestEnvOverride:
    """has_env_override() and env var evaluation via the OpenFeature path."""

    @pytest.fixture()
    def _registered_key(self, tmp_path):
        yaml_path = tmp_path / "test_flags.yaml"
        yaml_path.write_text(
            "features:\n"
            "  - key: test_env_flag\n"
            "    name: Test Env Flag\n"
            "    release_phase: general_availability\n"
            "    default: false\n"
            "    jira: DATAGO-99999\n"
        )
        initialize()
        load_flags_from_yaml(str(yaml_path))
        return "test_env_flag"

    def test_no_env_var_returns_false(self, _registered_key):
        assert has_env_override(_registered_key) is False

    def test_env_var_present_returns_true(self, _registered_key):
        with patch.dict(os.environ, {"SAM_FEATURE_TEST_ENV_FLAG": "true"}):
            assert has_env_override(_registered_key) is True

    def test_env_var_overrides_default_to_enabled(self, _registered_key):
        client = openfeature_api.get_client()
        with patch.dict(os.environ, {"SAM_FEATURE_TEST_ENV_FLAG": "true"}):
            assert client.get_boolean_value(_registered_key, False) is True

    def test_flag_disabled_without_env_var(self, _registered_key):
        assert openfeature_api.get_client().get_boolean_value(_registered_key, False) is False


class TestEnterpriseIntegration:
    """initialize() loads enterprise flags when the enterprise package is available."""

    def test_enterprise_flags_loaded_during_initialize(self, monkeypatch, tmp_path):
        import sys
        import types

        yaml_path = tmp_path / "enterprise.yaml"
        yaml_path.write_text(
            "features:\n"
            "  - key: test_enterprise_flag\n"
            "    name: Test Enterprise Flag\n"
            "    release_phase: early_access\n"
            "    default: false\n"
            "    jira: DATAGO-99999\n"
        )

        def _fake_register():
            load_flags_from_yaml(str(yaml_path))

        fake_module = types.SimpleNamespace(
            _register_enterprise_feature_flags=_fake_register
        )
        monkeypatch.setitem(
            sys.modules,
            "solace_agent_mesh_enterprise.init_enterprise",
            fake_module,
        )

        initialize()

        assert is_known_flag("test_enterprise_flag")

    def test_enterprise_flags_registered_after_provider(self, monkeypatch, tmp_path):
        import sys
        import types
        from openfeature import api as openfeature_api
        from solace_agent_mesh.common.features.provider import SamFeatureProvider

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

        initialize()

        assert len(provider_at_call_time) == 1
        assert isinstance(provider_at_call_time[0], SamFeatureProvider)

    def test_initialize_succeeds_when_enterprise_not_installed(self, monkeypatch):
        import sys

        monkeypatch.setitem(
            sys.modules, "solace_agent_mesh_enterprise.init_enterprise", None
        )

        initialize()

        assert feature_core_module._initialized is True
        assert len(get_registry().all()) > 0


class TestResetForTesting:
    """_reset_for_testing() clears module state and allows full re-initialisation."""

    def test_reset_clears_state(self):
        initialize()
        _reset_for_testing()
        assert feature_core_module._initialized is False
        assert feature_core_module._checker is None

    def test_reset_clears_openfeature_provider(self):
        initialize()
        _reset_for_testing()
        provider = openfeature_api.provider_registry.get_default_provider()
        assert not isinstance(provider, SamFeatureProvider)

    def test_can_reinitialize_after_reset(self):
        initialize()
        _reset_for_testing()
        initialize()
        assert feature_core_module._initialized is True
        assert len(get_registry().all()) > 0
