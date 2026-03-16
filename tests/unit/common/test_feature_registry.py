"""
Unit tests for FeatureRegistry and FeatureDefinition.

Tests cover:
- Programmatic registration
- YAML loading and field validation
- Merge behaviour (later definitions win)
- Error handling for invalid YAML entries
"""

import textwrap
from pathlib import Path

import pytest
import yaml

from solace_agent_mesh.common.features.registry import (
    FeatureDefinition,
    FeatureRegistry,
    ReleasePhase,
)


def _write_yaml(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "features.yaml"
    p.write_text(textwrap.dedent(content))
    return p


def _minimal_flag(**overrides) -> dict:
    base = {
        "key": "f",
        "name": "F",
        "release_phase": "ga",
        "default_enabled": False,
        "jira_epic": "DATAGO-99999",
    }
    base.update(overrides)
    return base


def _minimal_yaml(tmp_path: Path, flags: list[dict]) -> Path:
    data = {"features": flags}
    p = tmp_path / "features.yaml"
    p.write_text(yaml.dump(data))
    return p


class TestFeatureRegistryRegister:
    def _defn(self, key: str, default: bool = False, **kwargs) -> FeatureDefinition:
        return FeatureDefinition(
            key=key,
            name=key,
            release_phase=ReleasePhase.GA,
            default_enabled=default,
            jira_epic="DATAGO-99999",
            **kwargs,
        )

    def test_register_and_retrieve(self):
        reg = FeatureRegistry()
        defn = self._defn("my_flag")
        reg.register(defn)
        assert reg.get("my_flag") is defn

    def test_get_unknown_key_returns_none(self):
        reg = FeatureRegistry()
        assert reg.get("nope") is None

    def test_all_returns_insertion_order(self):
        reg = FeatureRegistry()
        for k in ("a", "b", "c"):
            reg.register(self._defn(k))
        assert [d.key for d in reg.all()] == ["a", "b", "c"]

    def test_keys_mirrors_insertion_order(self):
        reg = FeatureRegistry()
        for k in ("x", "y"):
            reg.register(self._defn(k))
        assert reg.keys() == ["x", "y"]

    def test_later_registration_wins(self):
        reg = FeatureRegistry()
        reg.register(self._defn("f", default=False))
        reg.register(
            FeatureDefinition(
                key="f",
                name="F v2",
                release_phase=ReleasePhase.GA,
                default_enabled=True,
                jira_epic="DATAGO-99999",
            )
        )
        assert reg.get("f").default_enabled is True
        assert reg.get("f").name == "F v2"


class TestFeatureRegistryYamlLoad:
    def test_loads_minimal_flag(self, tmp_path):
        p = _minimal_yaml(tmp_path, [_minimal_flag()])
        reg = FeatureRegistry()
        reg.load_from_yaml(p)
        defn = reg.get("f")
        assert defn is not None
        assert defn.key == "f"
        assert defn.release_phase == ReleasePhase.GA
        assert defn.default_enabled is False
        assert defn.jira_epic == "DATAGO-99999"

    def test_loads_all_release_phases(self, tmp_path):
        flags = [
            _minimal_flag(key=k, release_phase=phase)
            for k, phase in [
                ("a", "early_access"),
                ("b", "beta"),
                ("c", "experimental"),
                ("d", "ga"),
            ]
        ]
        p = _minimal_yaml(tmp_path, flags)
        reg = FeatureRegistry()
        reg.load_from_yaml(p)
        assert reg.get("a").release_phase == ReleasePhase.EARLY_ACCESS
        assert reg.get("b").release_phase == ReleasePhase.BETA
        assert reg.get("c").release_phase == ReleasePhase.EXPERIMENTAL
        assert reg.get("d").release_phase == ReleasePhase.GA

    def test_loads_optional_description(self, tmp_path):
        p = _minimal_yaml(tmp_path, [_minimal_flag(description="hello")])
        reg = FeatureRegistry()
        reg.load_from_yaml(p)
        assert reg.get("f").description == "hello"

    def test_description_defaults_to_empty_string(self, tmp_path):
        p = _minimal_yaml(tmp_path, [_minimal_flag()])
        reg = FeatureRegistry()
        reg.load_from_yaml(p)
        assert reg.get("f").description == ""

    def test_later_yaml_load_overwrites_same_key(self, tmp_path):
        p1 = tmp_path / "a" / "f.yaml"
        p1.parent.mkdir(parents=True)
        p1.write_text(yaml.dump({"features": [_minimal_flag(name="F", default_enabled=False)]}))

        p2 = tmp_path / "b" / "f.yaml"
        p2.parent.mkdir(parents=True)
        p2.write_text(yaml.dump({"features": [_minimal_flag(name="F v2", default_enabled=True)]}))

        reg = FeatureRegistry()
        reg.load_from_yaml(p1)
        reg.load_from_yaml(p2)
        assert reg.get("f").default_enabled is True
        assert reg.get("f").name == "F v2"

    def test_load_raises_for_missing_file(self):
        reg = FeatureRegistry()
        with pytest.raises(FileNotFoundError):
            reg.load_from_yaml("/nonexistent/features.yaml")

    def test_empty_features_list_is_valid(self, tmp_path):
        p = _write_yaml(tmp_path, "features: []\n")
        reg = FeatureRegistry()
        reg.load_from_yaml(p)
        assert reg.all() == []

    def test_load_raises_for_missing_default_enabled(self, tmp_path):
        flag = _minimal_flag()
        del flag["default_enabled"]
        p = _minimal_yaml(tmp_path, [flag])
        reg = FeatureRegistry()
        with pytest.raises(ValueError, match="default_enabled"):
            reg.load_from_yaml(p)

    def test_load_raises_for_missing_jira_epic(self, tmp_path):
        flag = _minimal_flag()
        del flag["jira_epic"]
        p = _minimal_yaml(tmp_path, [flag])
        reg = FeatureRegistry()
        with pytest.raises(ValueError, match="jira_epic"):
            reg.load_from_yaml(p)

    def test_load_raises_for_invalid_release_phase(self, tmp_path):
        p = _minimal_yaml(tmp_path, [_minimal_flag(release_phase="invalid_phase")])
        reg = FeatureRegistry()
        with pytest.raises(ValueError, match="release_phase"):
            reg.load_from_yaml(p)

    def test_load_raises_when_features_not_a_list(self, tmp_path):
        p = _write_yaml(tmp_path, "features:\n  key: bad\n")
        reg = FeatureRegistry()
        with pytest.raises(ValueError, match="list"):
            reg.load_from_yaml(p)

    def test_load_real_community_yaml(self):
        """The bundled community features.yaml must load without error."""
        community_yaml = (
            Path(__file__).parent.parent.parent.parent
            / "src"
            / "solace_agent_mesh"
            / "common"
            / "features"
            / "features.yaml"
        )
        reg = FeatureRegistry()
        reg.load_from_yaml(community_yaml)
        flags = reg.all()
        for defn in flags:
            assert defn.key != ""
            assert defn.jira_epic != ""
