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
    "sam-bedrock-agent",
    "sam-event-mesh-gateway",
    "sam-event-mesh-tool",
    "sam-mcp-server-gateway-adapter",
    "sam-mongodb",
    "sam-nuclia-tool",
    "sam-rag",
    "sam-rest-gateway",
    "sam-ruleset-lookup-tool",
    "sam-slack-gateway-adapter",
    "sam-sql-database-tool",
]

USER_REGISTRIES_PATH = SAM_HOME / "plugin_catalog_registries.json"
PLUGIN_CATALOG_TEMP_DIR = SAM_HOME / "plugin_catalog_tmp"
