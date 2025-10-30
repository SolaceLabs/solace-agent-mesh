
"""
Unit tests for cli/commands/plugin_cmd/official_registry.py

Tests the official plugin registry functions including:
- Registry data fetching from GitHub
- Registry data fetching from local filesystem
- Plugin metadata parsing
- Error handling (network errors, invalid data)
"""

from unittest.mock import MagicMock, Mock
import httpx

from cli.commands.plugin_cmd.official_registry import (
    get_official_plugins,
    _is_github_url,
    _fetch_github_plugins,
    _fetch_local_plugins,
    is_official_plugin,
    get_official_plugin_url,
)


class TestIsGithubUrl:
    """Tests for _is_github_url function"""
    
    def test_https_github_url(self):
        """Test HTTPS GitHub URL"""
        assert _is_github_url("https://github.com/user/repo") is True
    
    def test_http_github_url(self):
        """Test HTTP GitHub URL"""
        assert _is_github_url("http://github.com/user/repo") is True
    
    def test_github_url_with_git_extension(self):
        """Test GitHub URL with .git extension"""
        assert _is_github_url("https://github.com/user/repo.git") is True
    
    def test_non_github_url(self):
        """Test non-GitHub URL"""
        assert _is_github_url("https://gitlab.com/user/repo") is False
    
    def test_local_path(self):
        """Test local filesystem path"""
        assert _is_github_url("/path/to/plugins") is False
    
    def test_empty_string(self):
        """Test empty string"""
        assert _is_github_url("") is False


class TestFetchGithubPlugins:
    """Tests for _fetch_github_plugins function"""
    
    def test_fetch_plugins_success(self, mock_httpx_client):
        """Test successful plugin fetching from GitHub"""
        github_url = "https://github.com/user/plugins"
        
        result = _fetch_github_plugins(github_url)
        
        assert "plugin1" in result
        assert "plugin2" in result
        assert result["plugin1"].startswith("git+")
        assert "#subdirectory=plugin1" in result["plugin1"]
    
    def test_fetch_plugins_with_branch(self, mocker):
        """Test fetching plugins with specific branch"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"type": "dir", "name": "plugin1"},
        ]
        
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        
        mocker.patch("httpx.Client", return_value=mock_client)
        
        result = _fetch_github_plugins("https://github.com/user/repo", branch="develop")
        
        assert "plugin1" in result
        assert "@develop" in result["plugin1"]
    
    def test_fetch_plugins_removes_git_extension(self, mock_httpx_client):
        """Test that .git extension is removed from URL"""
        github_url = "https://github.com/user/plugins.git"
        
        result = _fetch_github_plugins(github_url)
        
        # URLs should not contain .git in the middle
        for url in result.values():
            assert ".git#" not in url or url.endswith(".git")
    
    def test_fetch_plugins_filters_ignored_dirs(self, mocker):
        """Test that ignored directories are filtered out"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"type": "dir", "name": "plugin1"},
            {"type": "dir", "name": ".git"},
            {"type": "dir", "name": "__pycache__"},
            {"type": "dir", "name": "node_modules"},
            {"type": "file", "name": "README.md"},
        ]
        
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        
        mocker.patch("httpx.Client", return_value=mock_client)
        
        result = _fetch_github_plugins("https://github.com/user/repo")
        
        assert "plugin1" in result
        assert ".git" not in result
        assert "__pycache__" not in result
        assert "node_modules" not in result
        assert "README.md" not in result
    
    def test_fetch_plugins_invalid_url_format(self, mocker):
        """Test with invalid GitHub URL format"""
        mocker.patch("httpx.Client")
        
        result = _fetch_github_plugins("https://github.com/invalid")
        
        assert result == {}
    
    def test_fetch_plugins_network_error(self, mocker):
        """Test handling of network errors"""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.side_effect = httpx.RequestError("Network error")
        
        mocker.patch("httpx.Client", return_value=mock_client)
        
        result = _fetch_github_plugins("https://github.com/user/repo")
        
        assert result == {}
    
    def test_fetch_plugins_http_error(self, mocker):
        """Test handling of HTTP errors"""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not found", request=Mock(), response=mock_response
        )
        
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        
        mocker.patch("httpx.Client", return_value=mock_client)
        
        result = _fetch_github_plugins("https://github.com/user/repo")
        
        assert result == {}
    
    def test_fetch_plugins_unexpected_error(self, mocker):
        """Test handling of unexpected errors"""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.side_effect = Exception("Unexpected error")
        
        mocker.patch("httpx.Client", return_value=mock_client)
        
        result = _fetch_github_plugins("https://github.com/user/repo")
        
        assert result == {}


class TestFetchLocalPlugins:
    """Tests for _fetch_local_plugins function"""
    
    def test_fetch_local_plugins_success(self, tmp_path):
        """Test successful fetching from local directory"""
        # Create plugin directories
        (tmp_path / "plugin1").mkdir()
        (tmp_path / "plugin2").mkdir()
        (tmp_path / "README.md").touch()
        
        result = _fetch_local_plugins(str(tmp_path))
        
        assert "plugin1" in result
        assert "plugin2" in result
        assert str(tmp_path / "plugin1") == result["plugin1"]
        assert "README.md" not in result
    
    def test_fetch_local_plugins_filters_ignored(self, tmp_path):
        """Test that ignored directories are filtered"""
        (tmp_path / "plugin1").mkdir()
        (tmp_path / ".git").mkdir()
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "node_modules").mkdir()
        (tmp_path / ".vscode").mkdir()
        
        result = _fetch_local_plugins(str(tmp_path))
        
        assert "plugin1" in result
        assert ".git" not in result
        assert "__pycache__" not in result
        assert "node_modules" not in result
        assert ".vscode" not in result
    
    def test_fetch_local_plugins_nonexistent_path(self, tmp_path):
        """Test with nonexistent path"""
        nonexistent = tmp_path / "nonexistent"
        
        result = _fetch_local_plugins(str(nonexistent))
        
        assert result == {}
    
    def test_fetch_local_plugins_file_instead_of_dir(self, tmp_path):
        """Test with file path instead of directory"""
        file_path = tmp_path / "file.txt"
        file_path.touch()
        
        result = _fetch_local_plugins(str(file_path))
        
        assert result == {}
    
    def test_fetch_local_plugins_with_tilde(self, tmp_path, mocker):
        """Test path expansion with tilde"""
        # Mock expanduser to return our tmp_path
        mocker.patch("pathlib.Path.expanduser", return_value=tmp_path)
        
        (tmp_path / "plugin1").mkdir()
        
        result = _fetch_local_plugins("~/plugins")
        
        assert "plugin1" in result
    
    def test_fetch_local_plugins_permission_error(self, tmp_path, mocker):
        """Test handling of permission errors"""
        mocker.patch("pathlib.Path.iterdir", side_effect=PermissionError())
        
        result = _fetch_local_plugins(str(tmp_path))
        
        assert result == {}


class TestGetOfficialPlugins:
    """Tests for get_official_plugins function"""
    
    def test_get_official_plugins_github(self, mocker):
        """Test getting plugins from GitHub registry"""
        mocker.patch(
            "cli.commands.plugin_cmd.official_registry.DEFAULT_OFFICIAL_REGISTRY_URL",
            "https://github.com/user/plugins"
        )
        
        mock_fetch = mocker.patch(
            "cli.commands.plugin_cmd.official_registry._fetch_github_plugins",
            return_value={"plugin1": "url1", "plugin2": "url2"}
        )
        
        # Clear cache
        get_official_plugins.cache_clear()
        
        result = get_official_plugins()
        
        assert "plugin1" in result
        assert "plugin2" in result
        mock_fetch.assert_called_once()
    
    def test_get_official_plugins_local(self, tmp_path, mocker):
        """Test getting plugins from local registry"""
        mocker.patch(
            "cli.commands.plugin_cmd.official_registry.DEFAULT_OFFICIAL_REGISTRY_URL",
            str(tmp_path)
        )
        
        (tmp_path / "plugin1").mkdir()
        
        # Clear cache
        get_official_plugins.cache_clear()
        
        result = get_official_plugins()
        
        assert "plugin1" in result
    
    def test_get_official_plugins_cached(self, mocker):
        """Test that results are cached"""
        mocker.patch(
            "cli.commands.plugin_cmd.official_registry.DEFAULT_OFFICIAL_REGISTRY_URL",
            "https://github.com/user/plugins"
        )
        
        mock_fetch = mocker.patch(
            "cli.commands.plugin_cmd.official_registry._fetch_github_plugins",
            return_value={"plugin1": "url1"}
        )
        
        # Clear cache first
        get_official_plugins.cache_clear()
        
        # Call twice
        result1 = get_official_plugins()
        result2 = get_official_plugins()
        
        # Should only fetch once due to caching
        assert mock_fetch.call_count == 1
        assert result1 == result2


class TestIsOfficialPlugin:
    """Tests for is_official_plugin function"""
    
    def test_is_official_plugin_true(self, mocker):
        """Test with official plugin name"""
        mocker.patch(
            "cli.commands.plugin_cmd.official_registry.get_official_plugins",
            return_value={"official-plugin": "url"}
        )
        
        assert is_official_plugin("official-plugin") is True
    
    def test_is_official_plugin_false(self, mocker):
        """Test with non-official plugin name"""
        mocker.patch(
            "cli.commands.plugin_cmd.official_registry.get_official_plugins",
            return_value={"official-plugin": "url"}
        )
        
        assert is_official_plugin("custom-plugin") is False
    
    def test_is_official_plugin_empty_registry(self, mocker):
        """Test with empty registry"""
        mocker.patch(
            "cli.commands.plugin_cmd.official_registry.get_official_plugins",
            return_value={}
        )
        
        assert is_official_plugin("any-plugin") is False


class TestGetOfficialPluginUrl:
    """Tests for get_official_plugin_url function"""
    
    def test_get_official_plugin_url_success(self, mocker):
        """Test getting URL for official plugin"""
        mocker.patch(
            "cli.commands.plugin_cmd.official_registry.get_official_plugins",
            return_value={"official-plugin": "git+https://github.com/user/repo#subdirectory=official-plugin"}
        )
        
        result = get_official_plugin_url("official-plugin")
        
        assert result == "git+https://github.com/user/repo#subdirectory=official-plugin"
    
    def test_get_official_plugin_url_not_found(self, mocker):
        """Test getting URL for non-official plugin"""
        mocker.patch(
            "cli.commands.plugin_cmd.official_registry.get_official_plugins",
            return_value={"official-plugin": "url"}
        )
        
        result = get_official_plugin_url("custom-plugin")
        
        assert result is None
    
    def test_get_official_plugin_url_git_path(self, mocker):
        """Test that git+ paths are not considered official"""
        mocker.patch(
            "cli.commands.plugin_cmd.official_registry.get_official_plugins",
            return_value={}
        )
        
        result = get_official_plugin_url("git+https://github.com/user/repo")
        
        assert result is False
    
    def test_get_official_plugin_url_http_url(self, mocker):
        """Test that HTTP URLs are not considered official"""
        mocker.patch(
            "cli.commands.plugin_cmd.official_registry.get_official_plugins",
            return_value={}
        )
        
        result = get_official_plugin_url("https://github.com/user/repo")
        
        assert result is False
    
    def test_get_official_plugin_url_local_path(self, mocker):
        """Test that local paths are not considered official"""
        mocker.patch(
            "cli.commands.plugin_cmd.official_registry.get_official_plugins",
            return_value={}
        )
        
        result = get_official_plugin_url("/path/to/plugin")
        
        assert result is False
    
    def test_get_official_plugin_url_relative_path(self, mocker):
        """Test that relative paths are not considered official"""
        mocker.patch(
            "cli.commands.plugin_cmd.official_registry.get_official_plugins",
            return_value={}
        )
        
        result = get_official_plugin_url("./plugin")
        
        assert result is False
    
    def test_get_official_plugin_url_tilde_path(self, mocker):
        """Test that tilde paths are not considered official"""
        mocker.patch(
            "cli.commands.plugin_cmd.official_registry.get_official_plugins",
            return_value={}
        )
        
        result = get_official_plugin_url("~/plugin")
        
        assert result is False