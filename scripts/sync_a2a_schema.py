"""
This script synchronizes the local a2a.json schema with the version corresponding
to the installed a2a-sdk package. It fetches the schema from the official A2A
GitHub repository using a version-specific tag.
"""

import importlib.metadata
import importlib.util
import re
import sys
from pathlib import Path
from typing import Optional

import httpx


# Assuming this script is run from the project root
PROJECT_ROOT = Path(__file__).parent.parent
SCHEMA_DIR = PROJECT_ROOT / "src" / "solace_agent_mesh" / "common" / "a2a_spec"
SCHEMA_PATH = SCHEMA_DIR / "a2a.json"


def get_sdk_version() -> str:
    """Gets the installed version of a2a-sdk."""
    try:
        version = importlib.metadata.version("a2a-sdk")
        print(f"Found a2a-sdk version: {version}")
        return version
    except importlib.metadata.PackageNotFoundError:
        print("Error: 'a2a-sdk' package not found.", file=sys.stderr)
        print("Please ensure the project dependencies are installed.", file=sys.stderr)
        sys.exit(1)


def construct_git_tag(version: str) -> str:
    """Constructs a Git tag from a version string (e.g., '0.5.1' -> 'v0.5.1')."""
    return f"v{version}"


def find_sdk_types_file() -> Path:
    """Finds the path to the installed a2a/types.py file."""
    try:
        spec = importlib.util.find_spec("a2a.types")
        if spec and spec.origin:
            print(f"Found a2a.types at: {spec.origin}")
            return Path(spec.origin)
    except Exception as e:
        print(f"Error finding 'a2a.types' module: {e}", file=sys.stderr)
        sys.exit(1)

    print("Error: Could not find the installed 'a2a.types' module.", file=sys.stderr)
    sys.exit(1)


def parse_url_from_header(types_file_path: Path) -> str:
    """Parses the source URL from the header of the types.py file."""
    try:
        with open(types_file_path, "r", encoding="utf-8") as f:
            # Read the first few lines to find the filename URL
            for _ in range(5):
                line = f.readline()
                match = re.search(r"#\s*filename:\s*(https?://\S+)", line)
                if match:
                    url = match.group(1)
                    print(f"Found source URL in header: {url}")
                    return url
    except Exception as e:
        print(f"Error reading or parsing {types_file_path}: {e}", file=sys.stderr)
        sys.exit(1)

    print(
        f"Error: Could not find the source URL in the header of {types_file_path}.",
        file=sys.stderr,
    )
    sys.exit(1)


def modify_url_with_tag(url: str, tag: str) -> str:
    """Replaces the branch/commit part of the URL with a specific Git tag."""
    # This regex is designed to find a commit hash or a branch ref like 'refs/heads/main'
    modified_url, count = re.subn(r"/(?:[a-f0-9]{40}|refs/heads/\w+)/", f"/{tag}/", url)
    if count == 0:
        print(
            f"Warning: Could not substitute tag '{tag}' into URL '{url}'. The URL format may have changed.",
            file=sys.stderr,
        )
        # Fallback for a simpler structure if the main regex fails
        modified_url, count = re.subn(r"/main/", f"/{tag}/", url)
        if count == 0:
            print(
                "Error: Fallback URL modification also failed. Cannot proceed.",
                file=sys.stderr,
            )
            sys.exit(1)

    print(f"Modified URL for version tag '{tag}': {modified_url}")
    return modified_url


def parse_protocol_version_from_file(types_file_path: Path) -> Optional[str]:
    """
    Parses the default protocol_version from the AgentCard definition in the types.py file.
    """
    try:
        with open(types_file_path, "r", encoding="utf-8") as f:
            content = f.read()
            # Use a regex that is less sensitive to whitespace and type hint changes
            match = re.search(
                r"class AgentCard\(.*?protocol_version:.*?=\s*'([^']+)'",
                content,
                re.DOTALL,  # Allow . to match newlines
            )
            if match:
                version = match.group(1)
                print(f"Found protocol_version in AgentCard: {version}")
                return version
            print(
                "Warning: Could not find 'protocol_version' default in AgentCard definition.",
                file=sys.stderr,
            )
            return None
    except Exception as e:
        print(
            f"Error parsing protocol_version from {types_file_path}: {e}",
            file=sys.stderr,
        )
        return None


def download_schema_with_fallback(base_url: str, version: str, save_path: Path):
    """
    Attempts to download the schema for the given version, falling back to
    earlier patch versions if a tag is not found.
    """
    version_parts = version.split(".")
    if len(version_parts) < 3:
        print(
            f"Error: Could not parse version string '{version}'. Expected at least 'X.Y.Z'.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        major, minor, patch = map(int, version_parts[:3])
    except ValueError:
        print(
            f"Error: Could not parse major.minor.patch from version string '{version}'.",
            file=sys.stderr,
        )
        sys.exit(1)

    for p in range(patch, -1, -1):
        current_version = f"{major}.{minor}.{p}"
        current_tag = construct_git_tag(current_version)
        print(f"Attempting to find schema for tag: {current_tag}")

        versioned_url = modify_url_with_tag(base_url, current_tag)

        try:
            with httpx.Client() as client:
                response = client.get(versioned_url, follow_redirects=True)
                if response.status_code == 200:
                    print(f"Success: Found schema at {versioned_url}")
                    save_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(save_path, "w", encoding="utf-8") as f:
                        f.write(response.text)
                    print(f"Successfully saved schema to: {save_path}")
                    return  # Success, exit the function
                elif response.status_code == 404:
                    if p > 0:
                        print(
                            f"Info: Schema not found for tag {current_tag} (HTTP 404). Trying next patch version..."
                        )
                    else:
                        print(
                            f"Info: Schema not found for tag {current_tag} (HTTP 404). This was the last attempt."
                        )
                    continue  # Try next patch version
                else:
                    # For other errors (500, 403, etc.), fail fast.
                    print(
                        f"Error: Received unexpected status code {response.status_code} from {versioned_url}",
                        file=sys.stderr,
                    )
                    response.raise_for_status()
        except httpx.RequestError as e:
            print(f"Error downloading schema: {e}", file=sys.stderr)
            sys.exit(1)
        except IOError as e:
            print(f"Error saving schema file to {save_path}: {e}", file=sys.stderr)
            sys.exit(1)

    # If loop finishes without returning, no version was found
    print(
        f"Error: Could not find a valid schema for version {major}.{minor}.x (tried patches from {patch} down to 0).",
        file=sys.stderr,
    )
    sys.exit(1)


def main():
    """Main script execution."""
    print("--- Starting A2A Schema Synchronization ---")
    types_py_path = find_sdk_types_file()

    # Try to get the precise protocol version from the AgentCard model
    schema_version = parse_protocol_version_from_file(types_py_path)

    # Fallback to SDK package version if parsing fails
    if not schema_version:
        print("Warning: Falling back to a2a-sdk package version.", file=sys.stderr)
        schema_version = get_sdk_version()

    base_url = parse_url_from_header(types_py_path)
    download_schema_with_fallback(base_url, schema_version, SCHEMA_PATH)
    print("--- A2A Schema Synchronization Complete ---")


if __name__ == "__main__":
    main()
