import os
from pathlib import Path

try:
    from cli.utils import get_sam_cli_home_dir

    SAM_HOME = get_sam_cli_home_dir()
except ImportError:
    print(
        "WARNING: Could not import 'get_sam_cli_home_dir' from 'cli.utils'. "
        "Falling back to legacy ~/.sam paths for Plugin Catalog. "
        "SAM_CLI_HOME environment variable will not be respected in this mode."
    )
    SAM_HOME = Path(os.path.expanduser("~/.sam"))
    SAM_HOME.mkdir(parents=True, exist_ok=True)

DEFAULT_OFFICIAL_REGISTRY_URL = (
    "https://github.com/SolaceLabs/solace-agent-mesh-core-plugins"
)
OFFICIAL_REGISTRY_GIT_BRANCH = "main"
IGNORE_OFFICIAL_FLAG_REPOS = []

PUBLISHED_OFFICIAL_PLUGINS_TO_PYPI = [
    "sam_bedrock_agent",
    "sam_event_mesh_gateway",
    "sam_event_mesh_tool",
    "sam_mcp_server_gateway_adapter",
    "sam_mongodb",
    "sam_nuclia_tool",
    "sam_rag",
    "sam_rest_gateway",
    "sam_ruleset_lookup_tool",
    "sam_slack_gateway_adapter",
    "sam_sql_database_tool",
]

USER_REGISTRIES_PATH = SAM_HOME / "plugin_catalog_registries.json"
PLUGIN_CATALOG_TEMP_DIR = SAM_HOME / "plugin_catalog_tmp"
