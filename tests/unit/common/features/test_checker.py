"""Unit tests for FeatureChecker.

Tests that enabled flags return True and non-existent flags return False.
"""

from solace_agent_mesh.common.features.checker import FeatureChecker
from solace_agent_mesh.common.features.registry import (
    FeatureDefinition,
    FeatureRegistry,
    ReleasePhase,
)


class TestFeatureChecker:
    """Tests for FeatureChecker.is_enabled()."""

    def test_enabled_flag_returns_true(self):
        """Test that an enabled feature flag returns True."""
        registry = FeatureRegistry()
        registry.register(
            FeatureDefinition(
                key="enabled_flag",
                name="Enabled Flag",
                release_phase=ReleasePhase.GA,
                default_enabled=True,
                jira_epic="DATAGO-123",
            )
        )
        checker = FeatureChecker(registry=registry)

        assert checker.is_enabled("enabled_flag") is True

    def test_nonexistent_flag_returns_false(self):
        """Test that a non-existent feature flag returns False."""
        registry = FeatureRegistry()
        registry.register(
            FeatureDefinition(
                key="some_flag",
                name="Some Flag",
                release_phase=ReleasePhase.GA,
                default_enabled=True,
                jira_epic="DATAGO-123",
            )
        )
        checker = FeatureChecker(registry=registry)

        assert checker.is_enabled("nonexistent_flag") is False
