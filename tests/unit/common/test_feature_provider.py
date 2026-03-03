"""
Unit tests for SamFeatureProvider.

Tests cover:
- Boolean flag resolution through the checker
- Handling of unregistered flags (returns default with DEFAULT reason)
- Error resilience during resolution
- Other flag types always return default (SAM only uses boolean flags)
- all_flags() delegation
- load_flags_from_yaml() merging
"""

import textwrap
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml

from openfeature import api as openfeature_api
from openfeature.flag_evaluation import Reason

from solace_agent_mesh.common.features.checker import FeatureChecker
from solace_agent_mesh.common.features.provider import SamFeatureProvider
from solace_agent_mesh.common.features.registry import (
    FeatureDefinition,
    FeatureRegistry,
    ReleasePhase,
)


def _make_checker(*flags: tuple[str, bool]) -> FeatureChecker:
    reg = FeatureRegistry()
    for key, default in flags:
        reg.register(
            FeatureDefinition(
                key=key,
                name=key.replace("_", " ").title(),
                release_phase=ReleasePhase.GA,
                default_enabled=default,
                jira_epic="DATAGO-99999",
            )
        )
    return FeatureChecker(registry=reg)


def _minimal_flag_yaml(**overrides) -> dict:
    base = {
        "key": "f",
        "name": "F",
        "release_phase": "ga",
        "default_enabled": False,
        "jira_epic": "DATAGO-99999",
    }
    base.update(overrides)
    return base


class TestResolveBooleanDetails:
    def test_returns_true_for_enabled_flag(self, monkeypatch):
        monkeypatch.delenv("SAM_FEATURE_F", raising=False)
        provider = SamFeatureProvider(_make_checker(("f", True)))
        result = provider.resolve_boolean_details("f", False)
        assert result.value is True
        assert result.reason == Reason.STATIC

    def test_returns_false_for_disabled_flag(self, monkeypatch):
        monkeypatch.delenv("SAM_FEATURE_F", raising=False)
        provider = SamFeatureProvider(_make_checker(("f", False)))
        result = provider.resolve_boolean_details("f", True)
        assert result.value is False
        assert result.reason == Reason.STATIC

    def test_env_var_override_reflected(self, monkeypatch):
        monkeypatch.setenv("SAM_FEATURE_F", "true")
        provider = SamFeatureProvider(_make_checker(("f", False)))
        result = provider.resolve_boolean_details("f", False)
        assert result.value is True
        assert result.reason == Reason.STATIC

    def test_unregistered_flag_returns_default_value(self, monkeypatch):
        monkeypatch.delenv("SAM_FEATURE_MISSING", raising=False)
        provider = SamFeatureProvider(_make_checker(("other", True)))
        result = provider.resolve_boolean_details("missing", True)
        assert result.value is True
        assert result.reason == Reason.DEFAULT

    def test_unregistered_flag_default_false(self, monkeypatch):
        monkeypatch.delenv("SAM_FEATURE_MISSING", raising=False)
        provider = SamFeatureProvider(_make_checker())
        result = provider.resolve_boolean_details("missing", False)
        assert result.value is False
        assert result.reason == Reason.DEFAULT

    def test_exception_during_resolution_returns_error(self, monkeypatch):
        monkeypatch.delenv("SAM_FEATURE_F", raising=False)
        checker = _make_checker(("f", True))
        checker.is_enabled = MagicMock(side_effect=RuntimeError("boom"))
        provider = SamFeatureProvider(checker)
        result = provider.resolve_boolean_details("f", False)
        assert result.value is False
        assert result.reason == Reason.ERROR


class TestOtherTypeResolution:
    def _provider(self):
        return SamFeatureProvider(_make_checker(("f", True)))

    def test_string_returns_default(self):
        result = self._provider().resolve_string_details("f", "default_str")
        assert result.value == "default_str"
        assert result.reason == Reason.DEFAULT

    def test_integer_returns_default(self):
        result = self._provider().resolve_integer_details("f", 42)
        assert result.value == 42
        assert result.reason == Reason.DEFAULT

    def test_float_returns_default(self):
        result = self._provider().resolve_float_details("f", 3.14)
        assert result.value == 3.14
        assert result.reason == Reason.DEFAULT

    def test_object_returns_default(self):
        result = self._provider().resolve_object_details("f", {"a": 1})
        assert result.value == {"a": 1}
        assert result.reason == Reason.DEFAULT


class TestAllFlags:
    def test_delegates_to_checker(self, monkeypatch):
        monkeypatch.delenv("SAM_FEATURE_A", raising=False)
        monkeypatch.delenv("SAM_FEATURE_B", raising=False)
        provider = SamFeatureProvider(_make_checker(("a", True), ("b", False)))
        assert provider.all_flags() == {"a": True, "b": False}


class TestLoadFlagsFromYaml:
    def test_merges_additional_flags(self, tmp_path):
        provider = SamFeatureProvider(_make_checker(("existing", True)))
        p = tmp_path / "extra.yaml"
        p.write_text(yaml.dump({"features": [_minimal_flag_yaml(key="new_flag", name="New Flag")]}))
        provider.load_flags_from_yaml(p)
        assert provider._checker.is_known_flag("new_flag") is True
        assert provider._checker.is_known_flag("existing") is True

    def test_later_yaml_overrides_existing_flag(self, tmp_path, monkeypatch):
        monkeypatch.delenv("SAM_FEATURE_F", raising=False)
        provider = SamFeatureProvider(_make_checker(("f", False)))
        p = tmp_path / "override.yaml"
        p.write_text(yaml.dump({"features": [_minimal_flag_yaml(name="F Override", default_enabled=True)]}))
        provider.load_flags_from_yaml(p)
        assert provider._checker.is_enabled("f") is True


class TestOpenFeatureIntegration:
    def test_registered_provider_is_used_by_api(self, monkeypatch):
        monkeypatch.delenv("SAM_FEATURE_F", raising=False)
        checker = _make_checker(("f", True))
        provider = SamFeatureProvider(checker)
        openfeature_api.set_provider(provider)

        client = openfeature_api.get_client()
        assert client.get_boolean_value("f", False) is True

    def test_unknown_flag_falls_back_to_api_default(self, monkeypatch):
        monkeypatch.delenv("SAM_FEATURE_NOPE", raising=False)
        provider = SamFeatureProvider(_make_checker())
        openfeature_api.set_provider(provider)

        client = openfeature_api.get_client()
        assert client.get_boolean_value("nope", True) is True
