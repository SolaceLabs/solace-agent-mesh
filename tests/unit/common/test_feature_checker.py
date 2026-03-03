"""
Unit tests for FeatureChecker.

Tests cover the two-tier evaluation chain:
  1. SAM_FEATURE_<KEY> environment variable (highest priority)
  2. Registry default
"""

import pytest

from solace_agent_mesh.common.features.checker import FeatureChecker
from solace_agent_mesh.common.features.registry import (
    FeatureDefinition,
    FeatureRegistry,
    ReleasePhase,
)


def _flag(key: str, default: bool) -> FeatureDefinition:
    return FeatureDefinition(
        key=key,
        name=key.replace("_", " ").title(),
        release_phase=ReleasePhase.GA,
        default_enabled=default,
        jira_epic="DATAGO-99999",
    )


def _registry(*flags: FeatureDefinition) -> FeatureRegistry:
    reg = FeatureRegistry()
    for f in flags:
        reg.register(f)
    return reg


class TestIsKnownFlag:
    def test_returns_true_for_registered_flag(self):
        checker = FeatureChecker(registry=_registry(_flag("f", True)))
        assert checker.is_known_flag("f") is True

    def test_returns_false_for_unknown_flag(self):
        checker = FeatureChecker(registry=_registry(_flag("f", True)))
        assert checker.is_known_flag("nope") is False


class TestIsEnabledRegistryDefault:
    def test_returns_registry_default_when_true(self, monkeypatch):
        monkeypatch.delenv("SAM_FEATURE_F", raising=False)
        checker = FeatureChecker(registry=_registry(_flag("f", True)))
        assert checker.is_enabled("f") is True

    def test_returns_registry_default_when_false(self, monkeypatch):
        monkeypatch.delenv("SAM_FEATURE_F", raising=False)
        checker = FeatureChecker(registry=_registry(_flag("f", False)))
        assert checker.is_enabled("f") is False

    def test_unknown_key_returns_false(self, monkeypatch):
        monkeypatch.delenv("SAM_FEATURE_UNKNOWN", raising=False)
        checker = FeatureChecker(registry=_registry(_flag("f", True)))
        assert checker.is_enabled("unknown") is False


class TestIsEnabledEnvVar:
    @pytest.mark.parametrize("raw", ["1", "true", "True", "TRUE"])
    def test_truthy_env_var_enables_flag(self, monkeypatch, raw):
        monkeypatch.setenv("SAM_FEATURE_F", raw)
        checker = FeatureChecker(registry=_registry(_flag("f", False)))
        assert checker.is_enabled("f") is True

    @pytest.mark.parametrize("raw", ["0", "false", "False", "no", "off", "yes", "on", "whatever"])
    def test_falsy_env_var_disables_flag(self, monkeypatch, raw):
        monkeypatch.setenv("SAM_FEATURE_F", raw)
        checker = FeatureChecker(registry=_registry(_flag("f", True)))
        assert checker.is_enabled("f") is False

    def test_env_var_takes_precedence_over_registry_default(self, monkeypatch):
        monkeypatch.setenv("SAM_FEATURE_F", "false")
        checker = FeatureChecker(registry=_registry(_flag("f", True)))
        assert checker.is_enabled("f") is False

    def test_env_var_key_uses_upper_snake_case(self, monkeypatch):
        monkeypatch.setenv("SAM_FEATURE_MY_FLAG", "true")
        checker = FeatureChecker(registry=_registry(_flag("my_flag", False)))
        assert checker.is_enabled("my_flag") is True

    def test_env_var_key_replaces_hyphens_with_underscores(self, monkeypatch):
        monkeypatch.setenv("SAM_FEATURE_MY_FLAG", "true")
        checker = FeatureChecker(registry=_registry(_flag("my-flag", False)))
        assert checker.is_enabled("my-flag") is True

    def test_absent_env_var_falls_through_to_registry(self, monkeypatch):
        monkeypatch.delenv("SAM_FEATURE_F", raising=False)
        checker = FeatureChecker(registry=_registry(_flag("f", True)))
        assert checker.is_enabled("f") is True


class TestAllFlags:
    def test_returns_dict_of_all_flags(self, monkeypatch):
        monkeypatch.delenv("SAM_FEATURE_A", raising=False)
        monkeypatch.delenv("SAM_FEATURE_B", raising=False)
        checker = FeatureChecker(
            registry=_registry(_flag("a", True), _flag("b", False))
        )
        result = checker.all_flags()
        assert result == {"a": True, "b": False}

    def test_env_var_reflects_in_all_flags(self, monkeypatch):
        monkeypatch.setenv("SAM_FEATURE_A", "false")
        monkeypatch.delenv("SAM_FEATURE_B", raising=False)
        checker = FeatureChecker(
            registry=_registry(_flag("a", True), _flag("b", False))
        )
        result = checker.all_flags()
        assert result == {"a": False, "b": False}

    def test_empty_registry_returns_empty_dict(self):
        checker = FeatureChecker(registry=FeatureRegistry())
        assert checker.all_flags() == {}
