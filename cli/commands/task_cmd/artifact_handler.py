"""
Handles downloading and saving artifacts from the webui gateway.
"""
import httpx
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import logging

log = logging.getLogger(__name__)


@dataclass
class ArtifactInfo:
    """Information about a downloaded artifact."""

    filename: str
    size: int
    mime_type: str
    local_path: Path


class ArtifactHandler:
    """
    Downloads and saves artifacts from the gateway.
    """

    def __init__(
        self,
        base_url: str,
        session_id: str,
        output_dir: Path,
        token: Optional[str] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.session_id = session_id
        self.output_dir = output_dir
        self.token = token

        # Create artifacts subdirectory
        self.artifacts_dir = output_dir / "artifacts"
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

    def _get_headers(self) -> Dict[str, str]:
        """Build request headers with optional authentication."""
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def download_artifact(
        self,
        filename: str,
        version: Optional[int] = None,
    ) -> ArtifactInfo:
        """
        Download a specific artifact.

        Args:
            filename: The artifact filename
            version: Optional specific version (latest if not specified)

        Returns:
            ArtifactInfo with download details
        """
        if version is not None:
            url = f"{self.base_url}/api/v1/artifacts/{self.session_id}/{filename}/versions/{version}"
        else:
            url = f"{self.base_url}/api/v1/artifacts/{self.session_id}/{filename}"

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(url, headers=self._get_headers())
            response.raise_for_status()

            content = response.content
            mime_type = response.headers.get("content-type", "application/octet-stream")

            local_path = self.artifacts_dir / filename
            with open(local_path, "wb") as f:
                f.write(content)

            return ArtifactInfo(
                filename=filename,
                size=len(content),
                mime_type=mime_type,
                local_path=local_path,
            )

    async def list_artifacts(self) -> List[Dict[str, Any]]:
        """List all artifacts for the session."""
        url = f"{self.base_url}/api/v1/artifacts/{self.session_id}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=self._get_headers())
            response.raise_for_status()
            return response.json()

    async def download_all_artifacts(self) -> List[ArtifactInfo]:
        """Download all artifacts for the session."""
        try:
            artifacts = await self.list_artifacts()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                log.debug("No artifacts found for session %s", self.session_id)
                return []
            raise

        downloaded = []

        for artifact in artifacts:
            filename = artifact.get("filename")
            if filename:
                try:
                    info = await self.download_artifact(filename)
                    downloaded.append(info)
                    log.debug("Downloaded artifact: %s (%d bytes)", filename, info.size)
                except Exception as e:
                    log.warning("Failed to download artifact %s: %s", filename, e)

        return downloaded
