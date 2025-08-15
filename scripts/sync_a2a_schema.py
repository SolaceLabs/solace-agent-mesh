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


def download_and_save_schema(url: str, path: Path):
    """Downloads the schema from the URL and saves it to the specified path."""
    print(f"Downloading schema from: {url}")
    try:
        with httpx.Client() as client:
            response = client.get(url, follow_redirects=True)
            if response.status_code == 404:
                print(f"Error: Schema not found at {url} (HTTP 404).", file=sys.stderr)
                print(
                    "This likely means a Git tag for the installed SDK version does not exist in the A2A repository.",
                    file=sys.stderr,
                )
                sys.exit(1)
            response.raise_for_status()

            path.parent.mkdir(parents=True, exist_ok=True)

            with open(path, "w", encoding="utf-8") as f:
                f.write(response.text)
            print(f"Successfully saved schema to: {path}")

    except httpx.RequestError as e:
        print(f"Error downloading schema: {e}", file=sys.stderr)
        sys.exit(1)
    except IOError as e:
        print(f"Error saving schema file to {path}: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    """Main script execution."""
    print("--- Starting A2A Schema Synchronization ---")
    sdk_version = get_sdk_version()
    git_tag = construct_git_tag(sdk_version)
    types_py_path = find_sdk_types_file()
    base_url = parse_url_from_header(types_py_path)
    versioned_url = modify_url_with_tag(base_url, git_tag)
    download_and_save_schema(versioned_url, SCHEMA_PATH)
    print("--- A2A Schema Synchronization Complete ---")


if __name__ == "__main__":
    main()
