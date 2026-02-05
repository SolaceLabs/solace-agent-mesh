"""
Common utilities shared between task send and task run commands.
"""
import base64
import mimetypes
from pathlib import Path
from typing import Optional, List, Dict, Any

import httpx

from cli.utils import error_exit


async def fetch_available_agents(url: str, token: Optional[str] = None) -> List[Dict[str, Any]]:
    """Fetch available agents from the gateway."""
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(f"{url}/api/v1/agentCards", headers=headers)
        response.raise_for_status()
        return response.json()


def get_agent_name_from_cards(agent_cards: List[Dict[str, Any]], preferred_name: str) -> Optional[str]:
    """
    Find a matching agent name from available cards.
    Tries exact match first, then case-insensitive, then partial match.
    Returns the exact name if found, or None if not found.
    """
    preferred_lower = preferred_name.lower()

    # Try exact match first
    for card in agent_cards:
        name = card.get("name", "")
        if name == preferred_name:
            return name

    # Try case-insensitive exact match
    for card in agent_cards:
        name = card.get("name", "")
        if name.lower() == preferred_lower:
            return name

    # Try partial match (name contains preferred, or preferred contains name)
    for card in agent_cards:
        name = card.get("name", "")
        name_lower = name.lower()
        if preferred_lower in name_lower or name_lower in preferred_lower:
            return name

    return None


def get_default_agent(agent_cards: List[Dict[str, Any]]) -> Optional[str]:
    """Get the first available agent name."""
    if agent_cards:
        return agent_cards[0].get("name")
    return None


def get_mime_type(file_path: Path) -> str:
    """Determine MIME type for a file."""
    mime_type, _ = mimetypes.guess_type(str(file_path))
    return mime_type or "application/octet-stream"


def read_file_as_base64(file_path: Path) -> str:
    """Read a file and return its content as base64."""
    with open(file_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def build_file_parts(file_paths: List[str]) -> List[dict]:
    """Build FilePart objects for the given file paths."""
    parts = []
    for file_path_str in file_paths:
        file_path = Path(file_path_str).resolve()
        if not file_path.exists():
            error_exit(f"File not found: {file_path}")
        if not file_path.is_file():
            error_exit(f"Not a file: {file_path}")

        mime_type = get_mime_type(file_path)
        base64_content = read_file_as_base64(file_path)

        parts.append({
            "kind": "file",
            "file": {
                "bytes": base64_content,
                "name": file_path.name,
                "mimeType": mime_type,
            },
        })

    return parts


async def download_stim_file(
    url: str, task_id: str, output_dir: Path, headers: dict
):
    """Download the STIM file for the task."""
    stim_url = f"{url}/api/v1/tasks/{task_id}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(stim_url, headers=headers)
        response.raise_for_status()

        stim_path = output_dir / f"{task_id}.stim"
        with open(stim_path, "wb") as f:
            f.write(response.content)
