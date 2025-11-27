"""
API Router for providing version information about installed SAM products.
"""

import json
import logging
from importlib.metadata import version, PackageNotFoundError
from pathlib import Path

from fastapi import APIRouter, HTTPException, status

from .dto.responses.version_responses import ProductInfo, VersionResponse

log = logging.getLogger(__name__)

router = APIRouter()

# Constants
NOT_INSTALLED = "not-installed"
UNKNOWN_VERSION = "unknown"
UI_VERSION_RELATIVE_PATH = Path("client") / "webui" / "frontend" / "static" / "ui-version.json"


@router.get("/version", response_model=VersionResponse)
async def get_version():
    """
    Returns version information for all installed SAM products and dependencies.

    Detects and returns information only for products that are actually installed.
    """
    log_prefix = "[GET /api/v1/version] "
    log.debug("%sRequest received.", log_prefix)

    try:
        products = []

        # Add base solace-agent-mesh product
        base_product = _get_base_product_info(log_prefix)
        if base_product:
            products.append(base_product)

        # Add UI product
        ui_product = _get_ui_product_info(log_prefix)
        if ui_product:
            products.append(ui_product)

        # Add enterprise product if installed
        enterprise_product = _get_enterprise_product_info(log_prefix)
        if enterprise_product:
            products.append(enterprise_product)

        # Add solace-chat product if installed
        chat_product = _get_solace_chat_product_info(log_prefix)
        if chat_product:
            products.append(chat_product)

        log.debug(
            "%sReturning version information for %d products",
            log_prefix,
            len(products),
        )
        return VersionResponse(products=products)

    except Exception as e:
        log.exception("%sError retrieving version information: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve version information",
        ) from e


def _get_base_product_info(log_prefix: str) -> ProductInfo:
    """
    Get version information for the base solace-agent-mesh product.

    Args:
        log_prefix: Logging prefix for consistent log formatting

    Returns:
        ProductInfo with product information including key dependencies
    """
    base_version = _get_package_version("solace-agent-mesh", log_prefix)

    # Collect dependencies and filter out those not installed
    dependencies = {
        "a2a-sdk": _get_package_version("a2a-sdk", log_prefix),
        "google-adk": _get_package_version("google-adk", log_prefix),
    }
    # Filter out packages that are not installed
    dependencies = {k: v for k, v in dependencies.items() if v != NOT_INSTALLED}

    return ProductInfo(
        id="solace-agent-mesh",
        name="Solace Agent Mesh",
        description="Open-source framework for event-driven, multi-agent AI systems",
        version=base_version,
        dependencies=dependencies if dependencies else None,
    )


def _get_ui_product_info(log_prefix: str) -> ProductInfo | None:
    """
    Get version information for the UI product.

    Checks multiple locations for ui-version.json (enterprise, installed, dev)
    and returns the first one found.

    Args:
        log_prefix: Logging prefix for consistent log formatting

    Returns:
        ProductInfo with UI product information, or None if not found
    """
    # Define all possible UI version file paths to check
    ui_version_paths = [
        _get_enterprise_ui_version_path(log_prefix),
        _get_installed_ui_version_path(),
        _get_dev_ui_version_path(),
    ]

    # Try each path in order until we find one that exists
    for path in ui_version_paths:
        if path is None:
            continue

        ui_metadata = _read_ui_version_file(path, log_prefix)
        if ui_metadata:
            try:
                return ProductInfo(**ui_metadata)
            except Exception as e:
                log.warning(
                    "%sInvalid ui-version.json format at %s: %s",
                    log_prefix,
                    path,
                    e
                )
                # Continue to next path

    # No UI version file found, return default info
    log.debug("%sui-version.json not found in expected locations", log_prefix)
    return _get_default_ui_product_info()


def _get_enterprise_ui_version_path(log_prefix: str) -> Path | None:
    """
    Get the path to the enterprise UI version file if enterprise is installed.

    Args:
        log_prefix: Logging prefix for consistent log formatting

    Returns:
        Path to enterprise UI version file, or None if enterprise is not installed
    """
    enterprise_version = _get_package_version("solace-agent-mesh-enterprise", log_prefix)
    if enterprise_version == NOT_INSTALLED:
        return None

    try:
        import solace_agent_mesh_enterprise
        enterprise_package_path = Path(solace_agent_mesh_enterprise.__file__).parent
        ui_version_path = enterprise_package_path / UI_VERSION_RELATIVE_PATH
        return ui_version_path
    except ImportError as e:
        log.debug("%sEnterprise package import failed: %s", log_prefix, e)
        return None
    except AttributeError as e:
        log.warning("%sEnterprise package missing __file__ attribute: %s", log_prefix, e)
        return None
    except Exception as e:
        log.warning("%sCould not locate enterprise UI version path: %s", log_prefix, e)
        return None


def _get_installed_ui_version_path() -> Path:
    """
    Get the path to the UI version file in the installed package location.

    Returns:
        Path to installed UI version file
    """
    # Path: routers -> http_sse -> gateway -> solace_agent_mesh (4 levels up)
    current_file = Path(__file__)
    base_package_path = current_file.parent.parent.parent.parent
    ui_version_path = base_package_path / UI_VERSION_RELATIVE_PATH
    return ui_version_path


def _get_dev_ui_version_path() -> Path:
    """
    Get the path to the UI version file in the development location.

    Returns:
        Path to dev UI version file
    """
    # Path: src/solace_agent_mesh/... -> root/client/webui/frontend/static (6 levels up)
    current_file = Path(__file__)
    repo_root = current_file.parent.parent.parent.parent.parent.parent
    ui_version_path = repo_root / UI_VERSION_RELATIVE_PATH
    return ui_version_path


def _read_ui_version_file(path: Path, log_prefix: str) -> dict | None:
    """
    Read and parse a UI version JSON file.

    Args:
        path: Path to the ui-version.json file
        log_prefix: Logging prefix for consistent log formatting

    Returns:
        Parsed JSON metadata dict, or None if file doesn't exist or can't be read
    """
    if not path.exists():
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            ui_metadata = json.load(f)
            log.debug(
                "%sUI version from %s: %s",
                log_prefix,
                path,
                ui_metadata.get("version"),
            )
            return ui_metadata
    except FileNotFoundError:
        # File disappeared between exists() check and open() - rare race condition
        log.debug("%sUI version file not found at %s", log_prefix, path)
        return None
    except PermissionError as e:
        log.warning("%sPermission denied reading %s: %s", log_prefix, path, e)
        return None
    except json.JSONDecodeError as e:
        log.error("%sInvalid JSON in %s: %s", log_prefix, path, e)
        return None
    except Exception as e:
        log.warning("%sCould not read %s: %s", log_prefix, path, e)
        return None


def _get_default_ui_product_info() -> ProductInfo:
    """
    Get default UI product information when version file is not found.

    Returns:
        ProductInfo with default values
    """
    return ProductInfo(
        id="@SolaceLabs/solace-agent-mesh-ui",
        name="Solace Agent Mesh UI",
        description="React UI components for Solace Agent Mesh",
        version=UNKNOWN_VERSION,
    )


def _get_enterprise_product_info(log_prefix: str) -> ProductInfo | None:
    """
    Get version information for the enterprise product if installed.

    Args:
        log_prefix: Logging prefix for consistent log formatting

    Returns:
        ProductInfo with enterprise product information, or None if not installed
    """
    # Check if enterprise package is installed
    enterprise_version = _get_package_version("solace-agent-mesh-enterprise", log_prefix)
    if enterprise_version == NOT_INSTALLED:
        log.debug("%sEnterprise package not installed", log_prefix)
        return None

    product_info = ProductInfo(
        id="solace-agent-mesh-enterprise",
        name="Solace Agent Mesh Enterprise",
        description="Enterprise extensions with authorization and enterprise features",
        version=enterprise_version,
    )

    log.debug("%sEnterprise package detected: %s", log_prefix, enterprise_version)
    return product_info


def _get_solace_chat_product_info(log_prefix: str) -> ProductInfo | None:
    """
    Get version information for the solace-chat product if installed.

    Args:
        log_prefix: Logging prefix for consistent log formatting

    Returns:
        ProductInfo with solace-chat product information, or None if not installed
    """
    # Check if solace-chat package is installed
    chat_version = _get_package_version("solace-chat", log_prefix)
    if chat_version == NOT_INSTALLED:
        log.debug("%ssolace-chat package not installed", log_prefix)
        return None

    # solace-chat is installed, gather its information
    # Collect dependencies and filter out those not installed
    dependencies = {
        "sam-bamboohr": _get_package_version("sam-bamboohr", log_prefix),
        "sam-confluence": _get_package_version("sam-confluence", log_prefix),
        "sam-jira": _get_package_version("sam-jira", log_prefix),
        "sam-litellm": _get_package_version("sam-litellm", log_prefix),
        "sam-rest-gateway": _get_package_version("sam-rest-gateway", log_prefix),
        "sam-rt-sf": _get_package_version("sam-rt-sf", log_prefix),
        "sam-s3-hosting": _get_package_version("sam-s3-hosting", log_prefix),
        "sam-slack": _get_package_version("sam-slack", log_prefix),
        "sam-sql-database": _get_package_version("sam-sql-database", log_prefix),
        "sam-teams-gateway": _get_package_version("sam-teams-gateway", log_prefix),
    }
    # Filter out packages that are not installed
    dependencies = {k: v for k, v in dependencies.items() if v != NOT_INSTALLED}

    product_info = ProductInfo(
        id="solace-chat",
        name="Solace Chat",
        description="Solace Chat Agent for agent-to-agent communication",
        version=chat_version,
        dependencies=dependencies if dependencies else None,
    )

    log.debug("%ssolace-chat package detected: %s", log_prefix, chat_version)
    return product_info


def _get_package_version(package_name: str, log_prefix: str) -> str:
    """
    Get the version of an installed package.

    Args:
        package_name: Name of the package to query
        log_prefix: Logging prefix for consistent log formatting

    Returns:
        Version string, or "not-installed" if package is not found
    """
    try:
        return version(package_name)
    except PackageNotFoundError:
        log.debug("%sPackage '%s' not found in installed packages", log_prefix, package_name)
        return NOT_INSTALLED
