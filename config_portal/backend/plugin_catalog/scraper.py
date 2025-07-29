import git
import toml
import yaml
import os
import shutil
from pathlib import Path
from typing import List, Optional, Tuple
import logging

from .models import (
    PluginScrapedInfo,
    PyProjectDetails,
    PyProjectAuthor,
    AgentCard,
    AgentCardSkill,
    Registry,
)
from .constants import (
    PLUGIN_CATALOG_TEMP_DIR,
    IGNORE_OFFICIAL_FLAG_REPOS,
    DEFAULT_OFFICIAL_REGISTRY_URL,
)

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


class PluginScraper:
    def __init__(self):
        self.temp_base_dir = Path(os.path.expanduser(PLUGIN_CATALOG_TEMP_DIR))
        self.temp_base_dir.mkdir(parents=True, exist_ok=True)
        self.plugin_cache: List[PluginScrapedInfo] = []
        self.is_cache_populated = False

    def _clear_temp_dir(self, specific_repo_dir: Optional[Path] = None):
        """Clears a specific repository's temporary directory."""
        if (
            specific_repo_dir
            and specific_repo_dir.exists()
            and specific_repo_dir.is_relative_to(self.temp_base_dir)
        ):
            try:
                shutil.rmtree(specific_repo_dir)
                logger.info("Cleared temporary directory: %s", specific_repo_dir)
            except Exception as e:
                logger.error(
                    "Error clearing temporary directory %s: %s", specific_repo_dir, e
                )
        elif specific_repo_dir:
            logger.warning(
                "Attempted to clear directory outside temp_base_dir or non-existent: %s",
                specific_repo_dir,
            )

    def _parse_pyproject(self, plugin_dir: Path) -> Optional[PyProjectDetails]:
        pyproject_path = plugin_dir / "pyproject.toml"
        if not pyproject_path.exists():
            logger.debug("pyproject.toml not found in %s", plugin_dir)
            return None
        try:
            data = toml.load(pyproject_path)
            project_data = data.get("project", {})

            authors_data = project_data.get("authors", [])
            authors_list: List[PyProjectAuthor] = []
            if isinstance(authors_data, list):
                for author_entry in authors_data:
                    if isinstance(author_entry, dict):
                        authors_list.append(
                            PyProjectAuthor(
                                name=author_entry.get("name"),
                                email=author_entry.get("email"),
                            )
                        )

            version = project_data.get("version", "0.0.0")
            if isinstance(version, dict) and version.get("from"):
                version_file_path = plugin_dir / version["from"]
                try:
                    if version_file_path.exists():
                        content = version_file_path.read_text()
                        import re

                        match = re.search(
                            r"__version__\s*=\s*[\"']([^\"']+)[\"']", content
                        )
                        if match:
                            version = match.group(1)
                        else:
                            logger.warning(
                                "Could not extract version from %s for %s, using pyproject.toml version or default.",
                                version_file_path,
                                plugin_dir.name,
                            )
                            version = project_data.get("version", "0.0.0")
                except Exception as e_ver:
                    logger.warning(
                        "Error reading version from %s for %s: %s. Using pyproject.toml version or default.",
                        version_file_path,
                        plugin_dir.name,
                        e_ver,
                    )
                    version = project_data.get("version", "0.0.0")

            project_name_for_tool_table = project_data.get("name", "").replace("-", "_")
            custom_metadata_dict = None
            plugin_type_str = "custom"

            if project_name_for_tool_table:
                tool_data = data.get("tool", {})
                plugin_specific_tool_data = tool_data.get(
                    project_name_for_tool_table, {}
                )
                if isinstance(plugin_specific_tool_data.get("metadata"), dict):
                    custom_metadata_dict = plugin_specific_tool_data["metadata"]
                    plugin_type_str = custom_metadata_dict.get("type", "custom")
                else:
                    logger.debug(
                        "No [tool.%s.metadata] table found or it's not a dictionary in %s",
                        project_name_for_tool_table,
                        pyproject_path,
                    )
            else:
                logger.debug(
                    "Project name not found in %s, cannot look for [tool.<plugin_name>.metadata]",
                    pyproject_path,
                )

            return PyProjectDetails(
                name=project_data.get("name", plugin_dir.name),
                version=str(version),
                description=project_data.get("description"),
                authors=authors_list if authors_list else None,
                plugin_type=plugin_type_str,
                custom_metadata=custom_metadata_dict,
            )
        except Exception as e:
            logger.error("Error parsing %s: %s", pyproject_path, e)
            return None

    def _parse_config_yaml(self, plugin_dir: Path) -> Optional[AgentCard]:
        config_yaml_path = plugin_dir / "config.yaml"
        if not config_yaml_path.exists():
            logger.debug("config.yaml not found in %s", plugin_dir)
            return None
        try:
            with open(config_yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if not data or not isinstance(data, dict):
                logger.warning(
                    "Config file %s is empty or not a dictionary.", config_yaml_path
                )
                return None

            agent_card_data = None

            if isinstance(data.get("agent_card"), dict):
                agent_card_data = data["agent_card"]
            elif isinstance(data.get("apps"), list) and len(data["apps"]) > 0:
                app_one = data["apps"][0]
                if isinstance(app_one, dict):
                    app_config = app_one.get("app_config")
                    if isinstance(app_config, dict) and isinstance(
                        app_config.get("agent_card"), dict
                    ):
                        agent_card_data = app_config["agent_card"]

            if not agent_card_data:
                logger.debug(
                    "No valid 'agent_card' section found in %s.", config_yaml_path
                )
                return None

            skills_data_raw = agent_card_data.get(
                "skills", agent_card_data.get("Skill", [])
            )
            skills_list: List[AgentCardSkill] = []
            if isinstance(skills_data_raw, list):
                for skill_item in skills_data_raw:
                    if isinstance(skill_item, dict):
                        skill_name = skill_item.get("name")
                        skill_description = skill_item.get("description")
                        if skill_name:
                            skills_list.append(
                                AgentCardSkill(
                                    name=skill_name, description=skill_description
                                )
                            )
                        else:
                            logger.warning(
                                "Skill item in %s missing 'name': %s",
                                config_yaml_path,
                                skill_item,
                            )

            display_name = agent_card_data.get("displayName")
            short_description = agent_card_data.get(
                "shortDescription", agent_card_data.get("description")
            )

            return AgentCard(
                displayName=display_name,
                shortDescription=short_description,
                Skill=skills_list if skills_list else None,
            )
        except yaml.YAMLError as ye:
            logger.error("YAML parsing error in %s: %s", config_yaml_path, ye)
            return None
        except Exception as e:
            logger.error("Error processing %s: %s", config_yaml_path, e)
            return None

    def _read_readme(self, plugin_dir: Path) -> Optional[str]:
        readme_path = plugin_dir / "README.md"
        if readme_path.exists():
            try:
                return readme_path.read_text(encoding="utf-8")
            except Exception as e:
                logger.error("Error reading %s: %s", readme_path, e)
        logger.debug("README.md not found in %s", plugin_dir)
        return None

    def _scrape_git_registry(self, registry: Registry) -> List[PluginScrapedInfo]:
        repo_identifier = (
            registry.name
            if registry.name
            else Path(registry.path_or_url).name.replace(".git", "")
        )
        repo_local_path = self.temp_base_dir / repo_identifier
        plugins_found: List[PluginScrapedInfo] = []

        try:
            if repo_local_path.exists():
                logger.info(
                    "Git registry %s already cloned. Pulling latest changes from %s.",
                    repo_identifier,
                    registry.path_or_url,
                )
                cloned_repo = git.Repo(repo_local_path)
                cloned_repo.remotes.origin.pull()
            else:
                logger.info(
                    "Cloning git registry: %s to %s",
                    registry.path_or_url,
                    repo_local_path,
                )
                kwargs = {}
                if registry.git_branch:
                    kwargs["branch"] = registry.git_branch
                git.Repo.clone_from(registry.path_or_url, repo_local_path, **kwargs)

            for item in repo_local_path.iterdir():
                if item.is_dir() and not item.name.startswith("."):
                    plugin_dir = item
                    if (
                        not (plugin_dir / "pyproject.toml").exists()
                        or not (plugin_dir / "config.yaml").exists()
                    ):
                        logger.debug(
                            "Skipping %s in %s, missing required pyproject.toml or config.yaml.",
                            plugin_dir.name,
                            repo_identifier,
                        )
                        continue

                    pyproject_details = self._parse_pyproject(plugin_dir)
                    if not pyproject_details:
                        logger.warning(
                            "Could not parse pyproject.toml for %s in %s",
                            plugin_dir.name,
                            registry.path_or_url,
                        )
                        continue

                    agent_card_details = self._parse_config_yaml(plugin_dir)
                    readme_content = self._read_readme(plugin_dir)

                    plugin_id = f"{registry.id}_{plugin_dir.name}"
                    plugin_subpath = plugin_dir.relative_to(repo_local_path).as_posix()

                    is_official_flag = (
                        registry.is_official_source
                        and plugin_dir.name not in IGNORE_OFFICIAL_FLAG_REPOS
                    )

                    plugins_found.append(
                        PluginScrapedInfo(
                            id=plugin_id,
                            pyproject=pyproject_details,
                            agent_card=agent_card_details,
                            readme_content=readme_content,
                            source_registry_name=registry.name,
                            source_registry_location=str(registry.path_or_url),
                            source_type="git",
                            plugin_subpath=plugin_subpath,
                            is_official=is_official_flag,
                        )
                    )
            logger.info(
                "Found %d plugins in git registry %s",
                len(plugins_found),
                registry.path_or_url,
            )
        except git.GitCommandError as e:
            logger.error("Git command error for %s: %s", registry.path_or_url, e)
        except Exception as e:
            logger.error(
                "Unexpected error scraping git registry %s: %s", registry.path_or_url, e
            )
        return plugins_found

    def _scrape_local_registry(self, registry: Registry) -> List[PluginScrapedInfo]:
        registry_path = Path(registry.path_or_url)
        plugins_found: List[PluginScrapedInfo] = []
        logger.info(
            "Scraping local registry: %s (Name: %s)", registry_path, registry.name
        )

        if not registry_path.exists() or not registry_path.is_dir():
            logger.error(
                "Local registry path does not exist or is not a directory: %s",
                registry_path,
            )
            return plugins_found

        for item in registry_path.iterdir():
            if item.is_dir() and not item.name.startswith("."):
                plugin_dir = item
                if (
                    not (plugin_dir / "pyproject.toml").exists()
                    or not (plugin_dir / "config.yaml").exists()
                ):
                    logger.debug(
                        "Skipping %s in local registry %s, missing required pyproject.toml or config.yaml.",
                        plugin_dir.name,
                        registry.name,
                    )
                    continue

                pyproject_details = self._parse_pyproject(plugin_dir)
                if not pyproject_details:
                    logger.warning(
                        "Could not parse pyproject.toml for %s in local registry %s",
                        plugin_dir.name,
                        registry.name,
                    )
                    continue

                agent_card_details = self._parse_config_yaml(plugin_dir)
                readme_content = self._read_readme(plugin_dir)

                plugin_id = f"{registry.id}_{plugin_dir.name}"
                plugin_subpath = plugin_dir.name

                is_official_flag = (
                    registry.is_official_source
                    and plugin_dir.name not in IGNORE_OFFICIAL_FLAG_REPOS
                )

                plugins_found.append(
                    PluginScrapedInfo(
                        id=plugin_id,
                        pyproject=pyproject_details,
                        agent_card=agent_card_details,
                        readme_content=readme_content,
                        source_registry_name=registry.name,
                        source_registry_location=str(registry.path_or_url),
                        source_type="local",
                        plugin_subpath=plugin_subpath,
                        is_official=is_official_flag,
                    )
                )
        logger.info(
            "Found %d plugins in local registry %s",
            len(plugins_found),
            registry.path_or_url,
        )
        return plugins_found

    def get_all_plugins(
        self, registries: List[Registry], force_refresh: bool = False
    ) -> List[PluginScrapedInfo]:
        if not force_refresh and self.is_cache_populated:
            logger.info("Returning cached plugins.")
            return self.plugin_cache

        logger.info("Refreshing plugin cache. Force refresh: %s", force_refresh)
        self.plugin_cache.clear()
        for reg_model in registries:
            if reg_model.type == "git":
                self.plugin_cache.extend(self._scrape_git_registry(reg_model))
            elif reg_model.type == "local":
                self.plugin_cache.extend(self._scrape_local_registry(reg_model))
            else:
                logger.warning(
                    "Unknown registry type '%s' for registry ID '%s'. Skipping.",
                    reg_model.type,
                    reg_model.id,
                )

        self.is_cache_populated = True
        logger.info(
            "Plugin cache refreshed. Total plugins found: %d", len(self.plugin_cache)
        )
        return self.plugin_cache

    def get_plugin_details(self, plugin_id: str) -> Optional[PluginScrapedInfo]:
        if not self.is_cache_populated:
            logger.warning(
                "Plugin cache was not populated when trying to get details. This might indicate an issue or a fresh start."
            )
        for plugin in self.plugin_cache:
            if plugin.id == plugin_id:
                return plugin
        logger.warning("Plugin with ID '%s' not found in cache.", plugin_id)
        return None

    def install_plugin_cli(
        self, plugin_info: PluginScrapedInfo, component_name: str
    ) -> Tuple[bool, str]:
        plugin_local_fs_path: Optional[Path] = None

        if plugin_info.source_type == "git":
            repo_identifier = (
                plugin_info.source_registry_name
                if plugin_info.source_registry_name
                else Path(plugin_info.source_registry_location).name.replace(".git", "")
            )
            repo_temp_path = self.temp_base_dir / repo_identifier

            try:
                temp_registry_for_git_op = Registry(
                    id="temp_install_op_id",
                    path_or_url=plugin_info.source_registry_location,
                    name=plugin_info.source_registry_name,
                    type="git",
                    is_default=(
                        plugin_info.source_registry_location
                        == DEFAULT_OFFICIAL_REGISTRY_URL
                    ),
                    is_official_source=plugin_info.is_official,
                )
                self._scrape_git_registry(temp_registry_for_git_op)
            except Exception as e_reg_create:
                logger.error(
                    "Could not prepare temporary registry for Git operation during install: %s",
                    e_reg_create,
                )
                return (
                    False,
                    f"Internal error preparing for Git operation: {e_reg_create}",
                )

            plugin_local_fs_path = repo_temp_path / plugin_info.plugin_subpath

        elif plugin_info.source_type == "local":
            plugin_local_fs_path = (
                Path(plugin_info.source_registry_location) / plugin_info.plugin_subpath
            )

        else:
            return False, f"Unknown plugin source type: {plugin_info.source_type}"

        if not plugin_local_fs_path or not plugin_local_fs_path.exists():
            return (
                False,
                f"Plugin source path {plugin_local_fs_path} not found or could not be determined.",
            )
        installer_command = os.environ.get("SAM_PLUGIN_INSTALL_COMMAND")
        command = [
            "sam",
            "plugin",
            "add",
            component_name,
            "--plugin",
            str(plugin_local_fs_path),
        ]
        if installer_command:
            command.extend(["--install-command", installer_command])

        logger.info("Executing install command: %s", " ".join(command))
        try:
            import subprocess

            result = subprocess.run(
                command, capture_output=True, text=True, check=False, encoding="utf-8"
            )

            if result.returncode == 0:
                msg = f"Plugin '{plugin_info.pyproject.name}' installed as '{component_name}' successfully."
                logger.info(msg)
                if result.stdout:
                    logger.info(result.stdout)
                return True, msg
            else:
                err_msg = f"Failed to install plugin '{plugin_info.pyproject.name}'. SAM CLI exit code: {result.returncode}"
                logger.error(err_msg)
                if result.stderr:
                    logger.error("Install STDERR: %s", result.stderr)
                if result.stdout:
                    logger.error("Install STDOUT: %s", result.stdout)
                return (
                    False,
                    f"{err_msg}\nDetails: {result.stderr or result.stdout}".strip(),
                )
        except FileNotFoundError:
            logger.error(
                "'sam' command not found. Ensure SAM CLI is installed and in PATH."
            )
            return (
                False,
                "'sam' command not found. Ensure SAM CLI is installed and in PATH.",
            )
        except Exception as e:
            logger.exception(
                "Exception during plugin installation command execution: %s", e
            )
            return False, f"An unexpected error occurred during installation: {e}"
