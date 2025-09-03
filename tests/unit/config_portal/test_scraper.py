import pytest
from config_portal.backend.plugin_catalog.scraper import _sanitize_name_for_filesystem


class TestPluginCatalogScraper:
    """Tests for the PluginScraper functionality."""

    def test_sanitize_name_for_filesystem_with_spaces(self):
        """Test that registry names with spaces are properly sanitized."""
        # Test the main issue: spaces in registry names
        assert _sanitize_name_for_filesystem("Community Plugin") == "community_plugin"
        assert _sanitize_name_for_filesystem("My Test Registry") == "my_test_registry"
        assert _sanitize_name_for_filesystem("Official SAM Plugins") == "official_sam_plugins"

    def test_sanitize_name_for_filesystem_with_special_characters(self):
        """Test that various special characters are handled correctly."""
        # Test various separators are normalized
        assert _sanitize_name_for_filesystem("test-repo") == "test_repo"
        assert _sanitize_name_for_filesystem("test_repo") == "test_repo"
        assert _sanitize_name_for_filesystem("test repo") == "test_repo"
        assert _sanitize_name_for_filesystem("test--repo") == "test_repo"
        assert _sanitize_name_for_filesystem("test  repo") == "test_repo"
        assert _sanitize_name_for_filesystem("test___repo") == "test_repo"

    def test_sanitize_name_for_filesystem_with_camel_case(self):
        """Test that camelCase names are properly converted."""
        assert _sanitize_name_for_filesystem("CommunityPlugin") == "community_plugin"
        assert _sanitize_name_for_filesystem("myTestRegistry") == "my_test_registry"
        assert _sanitize_name_for_filesystem("APIRegistry") == "api_registry"

    def test_sanitize_name_for_filesystem_edge_cases(self):
        """Test edge cases for name sanitization."""
        # Empty string
        assert _sanitize_name_for_filesystem("") == "unnamed_registry"
        assert _sanitize_name_for_filesystem("   ") == "unnamed_registry"
        
        # Single word
        assert _sanitize_name_for_filesystem("plugin") == "plugin"
        assert _sanitize_name_for_filesystem("Plugin") == "plugin"
        
        # Mixed cases with various separators
        assert _sanitize_name_for_filesystem("My-Test_Plugin Repository") == "my_test_plugin_repository"

    def test_sanitize_name_for_filesystem_preserves_valid_names(self):
        """Test that already valid filesystem names are preserved."""
        assert _sanitize_name_for_filesystem("valid_name") == "valid_name"
        assert _sanitize_name_for_filesystem("another-valid-name") == "another_valid_name"
        assert _sanitize_name_for_filesystem("simple") == "simple"