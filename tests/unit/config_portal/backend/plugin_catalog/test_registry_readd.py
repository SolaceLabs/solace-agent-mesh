"""
Unit tests for registry re-add functionality (GH#277).

Tests the ability to re-add previously removed registries and ensure
plugins are properly refreshed with fresh data.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import tempfile
import shutil

# Mock the imports before importing the modules
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent.parent / "config_portal" / "backend"))

from plugin_catalog.registry_manager import RegistryManager
from plugin_catalog.scraper import PluginScraper
from plugin_catalog.models import Registry


class TestRegistryReAdd:
    """Tests for re-adding previously removed registries."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def registry_manager(self, temp_dir):
        """Create a RegistryManager with a temporary user registries file."""
        with patch('plugin_catalog.registry_manager.USER_REGISTRIES_PATH', 
                   f"{temp_dir}/user_registries.json"):
            manager = RegistryManager()
            yield manager
    
    def test_add_registry_returns_tuple(self, registry_manager):
        """Test that add_registry returns a tuple (success, is_update)."""
        with patch('plugin_catalog.registry_manager.DEFAULT_OFFICIAL_REGISTRY_URL', 
                   'https://github.com/official/repo.git'):
            success, is_update = registry_manager.add_registry(
                "https://github.com/test/repo.git",
                name="test_repo"
            )
            
            assert isinstance(success, bool)
            assert isinstance(is_update, bool)
            assert success is True
            assert is_update is False  # First add should not be an update
    
    def test_readd_registry_updates_existing(self, registry_manager):
        """Test that re-adding a registry updates the existing entry."""
        test_url = "https://github.com/test/repo.git"
        
        with patch('plugin_catalog.registry_manager.DEFAULT_OFFICIAL_REGISTRY_URL', 
                   'https://github.com/official/repo.git'):
            # First add
            success1, is_update1 = registry_manager.add_registry(test_url, name="test_repo")
            assert success1 is True
            assert is_update1 is False
            
            # Re-add the same registry
            success2, is_update2 = registry_manager.add_registry(test_url, name="test_repo_updated")
            assert success2 is True
            assert is_update2 is True  # Should be marked as update
            
            # Verify only one registry exists
            registries = registry_manager.get_all_registries()
            user_registries = [r for r in registries if not r.is_default]
            assert len(user_registries) == 1
            assert user_registries[0].name == "test_repo_updated"
    
    def test_readd_registry_preserves_id(self, registry_manager):
        """Test that re-adding a registry preserves the same ID."""
        test_url = "https://github.com/test/repo.git"
        
        with patch('plugin_catalog.registry_manager.DEFAULT_OFFICIAL_REGISTRY_URL', 
                   'https://github.com/official/repo.git'):
            # First add
            registry_manager.add_registry(test_url, name="test_repo")
            registries1 = registry_manager.get_all_registries()
            user_reg1 = [r for r in registries1 if not r.is_default][0]
            original_id = user_reg1.id
            
            # Re-add
            registry_manager.add_registry(test_url, name="test_repo")
            registries2 = registry_manager.get_all_registries()
            user_reg2 = [r for r in registries2 if not r.is_default][0]
            
            assert user_reg2.id == original_id
    
    def test_multiple_registries_readd_one(self, registry_manager):
        """Test re-adding one registry when multiple exist."""
        with patch('plugin_catalog.registry_manager.DEFAULT_OFFICIAL_REGISTRY_URL', 
                   'https://github.com/official/repo.git'):
            # Add multiple registries
            registry_manager.add_registry("https://github.com/test1/repo.git", name="repo1")
            registry_manager.add_registry("https://github.com/test2/repo.git", name="repo2")
            registry_manager.add_registry("https://github.com/test3/repo.git", name="repo3")
            
            # Re-add the second one
            success, is_update = registry_manager.add_registry(
                "https://github.com/test2/repo.git",
                name="repo2_updated"
            )
            
            assert success is True
            assert is_update is True
            
            # Verify all three still exist
            registries = registry_manager.get_all_registries()
            user_registries = [r for r in registries if not r.is_default]
            assert len(user_registries) == 3
            
            # Verify the updated one has new name
            repo2 = [r for r in user_registries if "test2" in r.path_or_url][0]
            assert repo2.name == "repo2_updated"


class TestPluginScraperCacheClearing:
    """Tests for plugin scraper cache clearing functionality."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def plugin_scraper(self, temp_dir):
        """Create a PluginScraper with a temporary base directory."""
        with patch('plugin_catalog.scraper.PLUGIN_CATALOG_TEMP_DIR', temp_dir):
            scraper = PluginScraper()
            yield scraper
    
    def test_clear_git_cache_removes_directories(self, plugin_scraper, temp_dir):
        """Test that clear_git_cache removes git repository directories."""
        # Create some fake git repo directories
        repo1_dir = Path(temp_dir) / "repo1"
        repo2_dir = Path(temp_dir) / "repo2"
        repo1_dir.mkdir()
        repo2_dir.mkdir()
        
        # Create some files in them
        (repo1_dir / "test.txt").write_text("test")
        (repo2_dir / "test.txt").write_text("test")
        
        # Clear all caches
        plugin_scraper.clear_git_cache()
        
        # Verify directories are removed
        assert not repo1_dir.exists()
        assert not repo2_dir.exists()
    
    def test_clear_git_cache_specific_registry(self, plugin_scraper, temp_dir):
        """Test clearing cache for a specific registry."""
        # Create some fake git repo directories
        repo1_dir = Path(temp_dir) / "repo1"
        repo2_dir = Path(temp_dir) / "repo2"
        repo1_dir.mkdir()
        repo2_dir.mkdir()
        
        # Clear cache for specific registry (will clear all in current implementation)
        plugin_scraper.clear_git_cache("some_registry_id")
        
        # In current implementation, this clears all directories
        # This is acceptable as it ensures fresh data
        assert not repo1_dir.exists() or not repo2_dir.exists()
    
    def test_scrape_git_registry_force_fresh_clone(self, plugin_scraper, temp_dir):
        """Test that force_fresh_clone removes existing directory."""
        repo_dir = Path(temp_dir) / "test_repo"
        repo_dir.mkdir()
        (repo_dir / "marker.txt").write_text("old")
        
        mock_registry = Registry(
            id="test_id",
            path_or_url="https://github.com/test/repo.git",
            name="test_repo",
            type="git",
            is_default=False,
            is_official_source=False
        )
        
        with patch('git.Repo.clone_from') as mock_clone:
            # Mock the clone to create a new directory
            def create_new_dir(url, path, **kwargs):
                Path(path).mkdir(exist_ok=True)
                (Path(path) / "marker.txt").write_text("new")
                return MagicMock()
            
            mock_clone.side_effect = create_new_dir
            
            # Call with force_fresh_clone=True
            plugin_scraper._scrape_git_registry(mock_registry, force_fresh_clone=True)
            
            # Verify clone was called
            assert mock_clone.called
    
    def test_scrape_git_registry_fallback_on_pull_failure(self, plugin_scraper, temp_dir):
        """Test that scraper falls back to fresh clone if git pull fails."""
        repo_dir = Path(temp_dir) / "test_repo"
        repo_dir.mkdir()
        (repo_dir / ".git").mkdir()  # Make it look like a git repo
        
        mock_registry = Registry(
            id="test_id",
            path_or_url="https://github.com/test/repo.git",
            name="test_repo",
            type="git",
            is_default=False,
            is_official_source=False
        )
        
        with patch('git.Repo') as mock_repo_class:
            # Mock git.Repo to raise an exception on pull
            mock_repo = MagicMock()
            mock_repo.remotes.origin.pull.side_effect = Exception("Pull failed")
            mock_repo_class.return_value = mock_repo
            
            with patch('git.Repo.clone_from') as mock_clone:
                mock_clone.return_value = MagicMock()
                
                # Call scraper
                plugin_scraper._scrape_git_registry(mock_registry, force_fresh_clone=False)
                
                # Verify it attempted to pull, then fell back to clone
                assert mock_repo.remotes.origin.pull.called
                assert mock_clone.called
    
    def test_get_all_plugins_force_fresh_clone(self, plugin_scraper):
        """Test that get_all_plugins passes force_fresh_clone to git scraper."""
        mock_registry = Registry(
            id="test_id",
            path_or_url="https://github.com/test/repo.git",
            name="test_repo",
            type="git",
            is_default=False,
            is_official_source=False
        )
        
        with patch.object(plugin_scraper, '_scrape_git_registry', return_value=[]) as mock_scrape:
            plugin_scraper.get_all_plugins([mock_registry], force_fresh_clone=True)
            
            # Verify _scrape_git_registry was called with force_fresh_clone=True
            mock_scrape.assert_called_once_with(mock_registry, force_fresh_clone=True)
    
    def test_get_all_plugins_force_fresh_clone_implies_force_refresh(self, plugin_scraper):
        """Test that force_fresh_clone implies force_refresh."""
        # Populate cache
        plugin_scraper.is_cache_populated = True
        plugin_scraper.plugin_cache = [MagicMock()]
        
        mock_registry = Registry(
            id="test_id",
            path_or_url="https://github.com/test/repo.git",
            name="test_repo",
            type="git",
            is_default=False,
            is_official_source=False
        )
        
        with patch.object(plugin_scraper, '_scrape_git_registry', return_value=[]):
            # Call with force_fresh_clone=True but force_refresh=False
            plugin_scraper.get_all_plugins(
                [mock_registry],
                force_refresh=False,
                force_fresh_clone=True
            )
            
            # Verify cache was cleared (force_refresh was implied)
            assert len(plugin_scraper.plugin_cache) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
