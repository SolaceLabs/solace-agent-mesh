"""
Unit tests for the feature_flags config router helper logic.

Tests cover correct DTO field mapping, env-var override detection, and
registry behaviour. The FastAPI request machinery is exercised separately
in integration tests.
"""

import pytest
from openfeature import api as openfeature_api

from solace_agent_mesh.common.features import core as feature_flags
from solace_agent_mesh.common.features.checker import FeatureChecker
from solace_agent_mesh.common.features.registry import (
    FeatureDefinition,
    FeatureRegistry,
    ReleasePhase,
)
from solace_agent_mesh.gateway.http_sse.routers.dto.responses.feature_flag_responses import (
    FeatureFlagResponse,
)


def _defn(
    key: str,
    name: str = "",
    default: bool = False,
    release_phase: ReleasePhase = ReleasePhase.GENERAL_AVAILABILITY,
    description: str = "",
) -> FeatureDefinition:
    return FeatureDefinition(
        key=key,
        name=name or key.replace("_", " ").title(),
        release_phase=release_phase,
        default=default,
        jira="DATAGO-99999",
        description=description,
    )


def _checker(*flags: FeatureDefinition) -> FeatureChecker:
    reg = FeatureRegistry()
    for f in flags:
        reg.register(f)
    return FeatureChecker(registry=reg)


class TestHasEnvOverride:
    """Tests for FeatureChecker.has_env_override()."""

    def test_returns_false_when_no_env_var(self, monkeypatch):
        monkeypatch.delenv("SAM_FEATURE_F", raising=False)
        checker = _checker(_defn("f"))
        assert checker.has_env_override("f") is False

    def test_returns_true_when_env_var_set_true(self, monkeypatch):
        monkeypatch.setenv("SAM_FEATURE_F", "true")
        checker = _checker(_defn("f"))
        assert checker.has_env_override("f") is True

    def test_returns_true_when_env_var_set_false(self, monkeypatch):
        monkeypatch.setenv("SAM_FEATURE_F", "false")
        checker = _checker(_defn("f"))
        assert checker.has_env_override("f") is True

    def test_uses_upper_snake_case_key(self, monkeypatch):
        monkeypatch.setenv("SAM_FEATURE_MY_FLAG", "1")
        checker = _checker(_defn("my_flag"))
        assert checker.has_env_override("my_flag") is True

    def test_hyphen_key_normalised_to_underscore(self, monkeypatch):
        monkeypatch.setenv("SAM_FEATURE_MY_FLAG", "on")
        checker = _checker(_defn("my-flag"))
        assert checker.has_env_override("my-flag") is True

    def test_unknown_flag_returns_false_when_no_env_var(self, monkeypatch):
        monkeypatch.delenv("SAM_FEATURE_NOPE", raising=False)
        checker = _checker(_defn("f"))
        assert checker.has_env_override("nope") is False


class TestRegistryProperty:
    """Tests for FeatureChecker.registry property."""

    def test_returns_all_definitions_in_insertion_order(self, monkeypatch):
        for k in ("a", "b", "c"):
            monkeypatch.delenv(f"SAM_FEATURE_{k.upper()}", raising=False)
        checker = _checker(_defn("a"), _defn("b"), _defn("c"))
        keys = [d.key for d in checker.registry.all()]
        assert keys == ["a", "b", "c"]

    def test_empty_registry_returns_empty_list(self):
        checker = FeatureChecker(registry=FeatureRegistry())
        assert checker.registry.all() == []

    def test_returns_feature_definition_objects(self):
        defn = _defn("f")
        checker = _checker(defn)
        result = checker.registry.all()
        assert len(result) == 1
        assert result[0] is defn


class TestFeatureFlagResponseDto:
    """Tests for the FeatureFlagResponse Pydantic model."""

    def test_all_required_fields_accepted(self):
        dto = FeatureFlagResponse(
            key="my_flag",
            name="My Flag",
            release_phase="general_availability",
            resolved=True,
            has_env_override=False,
            registry_default=True,
            description="A description",
        )
        assert dto.key == "my_flag"
        assert dto.release_phase == "general_availability"
        assert dto.resolved is True
        assert dto.has_env_override is False
        assert dto.registry_default is True

    def test_description_can_be_empty_string(self):
        dto = FeatureFlagResponse(
            key="f",
            name="F",
            release_phase="beta",
            resolved=False,
            has_env_override=False,
            registry_default=False,
            description="",
        )
        assert dto.description == ""


class TestGetFeatureFlagsLogic:
    """Tests for the DTO-building logic used inside the config/features endpoint."""

    @pytest.fixture(autouse=True)
    def _reset(self):
        feature_flags._reset_for_testing()
        yield
        feature_flags._reset_for_testing()

    def _load_extra_flags(self, tmp_path, *defns: FeatureDefinition) -> None:
        lines = ["features:\n"]
        for d in defns:
            lines += [
                f"  - key: {d.key}\n",
                f"    name: {d.name}\n",
                f"    release_phase: {d.release_phase.value}\n",
                f"    default: {str(d.default).lower()}\n",
                f"    jira: {d.jira}\n",
            ]
            if d.description:
                lines.append(f"    description: {d.description}\n")
        yaml_file = tmp_path / "extra_flags.yaml"
        yaml_file.write_text("".join(lines))
        feature_flags.initialize()
        feature_flags.load_flags_from_yaml(str(yaml_file))

    def _build_dtos(self) -> list[FeatureFlagResponse]:
        client = openfeature_api.get_client()
        return [
            FeatureFlagResponse(
                key=d.key,
                name=d.name,
                release_phase=d.release_phase.value,
                resolved=client.get_boolean_value(d.key, False),
                has_env_override=feature_flags.has_env_override(d.key),
                registry_default=d.default,
                description=d.description,
            )
            for d in feature_flags.get_registry().all()
        ]

    def test_maps_definition_fields_to_dto(self, tmp_path, monkeypatch):
        monkeypatch.delenv("SAM_FEATURE_BG", raising=False)
        defn = _defn(
            "bg",
            name="Background Tasks",
            default=False,
            release_phase=ReleasePhase.GENERAL_AVAILABILITY,
            description="Run tasks in background",
        )
        self._load_extra_flags(tmp_path, defn)
        dtos = self._build_dtos()

        dto = next(d for d in dtos if d.key == "bg")
        assert dto.name == "Background Tasks"
        assert dto.release_phase == "general_availability"
        assert dto.resolved is False
        assert dto.has_env_override is False
        assert dto.registry_default is False
        assert dto.description == "Run tasks in background"

    def test_has_env_override_true_when_env_var_set(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SAM_FEATURE_F", "true")
        self._load_extra_flags(tmp_path, _defn("f", default=False))
        dtos = self._build_dtos()

        dto = next(d for d in dtos if d.key == "f")
        assert dto.resolved is True
        assert dto.has_env_override is True
        assert dto.registry_default is False

    def test_release_phase_serialised_as_string_value(self, tmp_path, monkeypatch):
        monkeypatch.delenv("SAM_FEATURE_F", raising=False)
        for phase, expected in [
            (ReleasePhase.EXPERIMENTAL, "experimental"),
            (ReleasePhase.EARLY_ACCESS, "early_access"),
            (ReleasePhase.BETA, "beta"),
            (ReleasePhase.CONTROLLED_AVAILABILITY, "controlled_availability"),
            (ReleasePhase.GENERAL_AVAILABILITY, "general_availability"),
            (ReleasePhase.DEPRECATED, "deprecated"),
        ]:
            feature_flags._reset_for_testing()
            self._load_extra_flags(tmp_path, _defn("f", release_phase=phase))
            dtos = self._build_dtos()
            dto = next(d for d in dtos if d.key == "f")
            assert dto.release_phase == expected

    def test_multiple_flags_all_included(self, tmp_path, monkeypatch):
        for k in ("a", "b", "c"):
            monkeypatch.delenv(f"SAM_FEATURE_{k.upper()}", raising=False)
        self._load_extra_flags(
            tmp_path,
            _defn("a", default=True),
            _defn("b", default=False),
            _defn("c", default=True),
        )
        dtos = self._build_dtos()
        keys = [d.key for d in dtos]
        assert "a" in keys
        assert "b" in keys
        assert "c" in keys
