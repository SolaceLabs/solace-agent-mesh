import httpx
from pathlib import Path
from functools import lru_cache
from typing import Dict, Optional
import click
from config_portal.backend.plugin_catalog.constants import (
    DEFAULT_OFFICIAL_REGISTRY_URL,
    OFFICIAL_REGISTRY_GIT_BRANCH,
)

IGNORE_SUB_DIRS = [".git", "__pycache__", ".venv", "node_modules", ".vscode", ".github"]


@lru_cache(maxsize=1)
def get_official_plugins() -> Dict[str, str]:
    """
    Fetches the list of official plugins from the default registry.

    Returns:
        Dict[str, str]: A mapping of plugin names to their full URLs/paths
    """
    registry_url = DEFAULT_OFFICIAL_REGISTRY_URL

    if _is_github_url(registry_url):
        return _fetch_github_plugins(registry_url, branch=OFFICIAL_REGISTRY_GIT_BRANCH)
    else:
        return _fetch_local_plugins(registry_url)


def _is_github_url(url: str) -> bool:
    """Check if the URL is a GitHub repository URL."""
    return url.startswith("https://github.com/") or url.startswith("http://github.com/")


def _fetch_github_plugins(github_url: str, branch: str = None) -> Dict[str, str]:
    """
    Fetch plugin list from GitHub repository using the GitHub API.

    Args:
        github_url: GitHub repository URL
        branch: Optional branch name to fetch plugins from

    Returns:
        Dict[str, str]: Mapping of plugin names to their full GitHub URLs
    """
    try:
        if github_url.endswith(".git"):
            github_url = github_url[:-4]

        parts = (
            github_url.replace("https://github.com/", "")
            .replace("http://github.com/", "")
            .split("/")
        )
        if len(parts) < 2:
            click.echo(
                click.style(f"Error: Invalid GitHub URL format: {github_url}", fg="red")
            )
            return {}

        owner, repo = parts[0], parts[1]
        api_url = f"https://api.github.com/repos/{owner}/{repo}/contents"
        if branch:
            api_url += f"?ref={branch}"

        with httpx.Client() as client:
            response = client.get(api_url, timeout=10.0)
            response.raise_for_status()

        contents = response.json()

        plugins = {}
        for item in contents:
            if item.get("type") == "dir" and item["name"] not in IGNORE_SUB_DIRS:
                plugin_name = item["name"]
                plugin_url = f"git+{github_url}"
                if branch:
                    plugin_url += f"@{branch}"
                plugin_url += f"#subdirectory={plugin_name}"
                plugins[plugin_name] = plugin_url

        return plugins

    except httpx.RequestError as e:
        click.echo(click.style(f"Error fetching plugins from GitHub: {e}", fg="red"))
        return {}
    except httpx.HTTPStatusError as e:
        click.echo(
            click.style(f"HTTP error fetching plugins from GitHub: {e}", fg="red")
        )
        return {}
    except Exception as e:
        click.echo(
            click.style(f"Unexpected error fetching plugins from GitHub: {e}", fg="red")
        )
        return {}


def _fetch_local_plugins(local_path: str) -> Dict[str, str]:
    """
    Fetch plugin list from local filesystem.

    Args:
        local_path: Local directory path

    Returns:
        Dict[str, str]: Mapping of plugin names to their full local paths
    """
    try:
        path = Path(local_path).expanduser().resolve()

        if not path.exists():
            click.echo(
                click.style(
                    f"Error: Local plugin registry path does not exist: {path}",
                    fg="red",
                )
            )
            return {}

        if not path.is_dir():
            click.echo(
                click.style(
                    f"Error: Local plugin registry path is not a directory: {path}",
                    fg="red",
                )
            )
            return {}

        plugins = {}
        for item in path.iterdir():
            if item.is_dir() and item.name not in IGNORE_SUB_DIRS:
                plugin_name = item.name
                plugins[plugin_name] = str(item)

        return plugins

    except Exception as e:
        click.echo(
            click.style(f"Error fetching plugins from local path: {e}", fg="red")
        )
        return {}


def is_official_plugin(plugin_name: str) -> bool:
    """
    Check if a plugin name is an official plugin.

    Args:
        plugin_name: Name of the plugin to check

    Returns:
        bool: True if the plugin is official, False otherwise
    """
    official_plugins = get_official_plugins()
    return plugin_name in official_plugins


def get_official_plugin_url(plugin_name: str) -> Optional[str]:
    """
    Get the full URL/path for an official plugin.

    Args:
        plugin_name: Name of the official plugin

    Returns:
        Optional[str]: Full URL/path if plugin is official, None otherwise
    """
    # if the plugin_name is a git path, url, or a local path, it can't be an official plugin
    if plugin_name.startswith(
        ("git+", "http://", "https://", "file://", "/", "./", "../", "~/")
    ):
        return False
    official_plugins = get_official_plugins()
    return official_plugins.get(plugin_name)
