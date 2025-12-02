"""
Filesystem-based skill resource storage.

Stores skill bundled resources on the local filesystem.
"""

import asyncio
import json
import logging
import os
import shutil
from typing import Dict, List, Optional

from .base import BaseSkillResourceStorage, BundledResources

logger = logging.getLogger(__name__)


class FilesystemSkillResourceStorage(BaseSkillResourceStorage):
    """
    Skill resource storage using the local filesystem.
    
    Directory structure:
    {base_path}/skills/{skill_group_id}/{version_id}/
    ├── scripts/
    │   ├── main.py
    │   └── helpers.py
    └── resources/
        ├── template.json
        └── config.yaml
    """
    
    def __init__(self, base_path: str):
        """
        Initialize filesystem storage.
        
        Args:
            base_path: Root directory for skill resources
        """
        if not base_path:
            raise ValueError("base_path cannot be empty")
        
        self.base_path = os.path.abspath(base_path)
        
        # Ensure base directory exists
        try:
            os.makedirs(self.base_path, exist_ok=True)
            logger.info("FilesystemSkillResourceStorage initialized at: %s", self.base_path)
        except OSError as e:
            logger.error("Failed to create base directory '%s': %s", self.base_path, e)
            raise ValueError(f"Could not create base_path '{self.base_path}': {e}") from e
    
    def _get_version_dir(self, skill_group_id: str, version_id: str) -> str:
        """Get the directory path for a skill version's resources."""
        # Sanitize IDs to prevent path traversal
        safe_group_id = os.path.basename(skill_group_id)
        safe_version_id = os.path.basename(version_id)
        return os.path.join(self.base_path, "skills", safe_group_id, safe_version_id)
    
    def get_uri(self, skill_group_id: str, version_id: str) -> str:
        """Get the file:// URI for a skill version's resources."""
        version_dir = self._get_version_dir(skill_group_id, version_id)
        return f"file://{version_dir}/"
    
    async def save_resources(
        self,
        skill_group_id: str,
        version_id: str,
        resources: BundledResources,
    ) -> str:
        """Save bundled resources to filesystem."""
        log_prefix = f"[FSSkillStorage:Save:{skill_group_id}/{version_id}] "
        
        if resources.is_empty():
            logger.debug("%sNo resources to save", log_prefix)
            return ""
        
        version_dir = self._get_version_dir(skill_group_id, version_id)
        
        try:
            # Create directory structure
            scripts_dir = os.path.join(version_dir, "scripts")
            resources_dir = os.path.join(version_dir, "resources")
            
            await asyncio.to_thread(os.makedirs, scripts_dir, exist_ok=True)
            await asyncio.to_thread(os.makedirs, resources_dir, exist_ok=True)
            
            # Save scripts
            for filename, content in resources.scripts.items():
                file_path = os.path.join(scripts_dir, os.path.basename(filename))
                await self._write_file(file_path, content)
                logger.debug("%sSaved script: %s", log_prefix, filename)
            
            # Save resources
            for filename, content in resources.resources.items():
                file_path = os.path.join(resources_dir, os.path.basename(filename))
                await self._write_file(file_path, content)
                logger.debug("%sSaved resource: %s", log_prefix, filename)
            
            uri = self.get_uri(skill_group_id, version_id)
            logger.info(
                "%sSaved %d files (%d scripts, %d resources) to %s",
                log_prefix,
                resources.total_files(),
                len(resources.scripts),
                len(resources.resources),
                uri,
            )
            return uri
            
        except OSError as e:
            logger.error("%sFailed to save resources: %s", log_prefix, e)
            # Clean up on failure
            if await asyncio.to_thread(os.path.exists, version_dir):
                await asyncio.to_thread(shutil.rmtree, version_dir)
            raise OSError(f"Failed to save skill resources: {e}") from e
    
    async def load_resources(
        self,
        skill_group_id: str,
        version_id: str,
    ) -> Optional[BundledResources]:
        """Load bundled resources from filesystem."""
        log_prefix = f"[FSSkillStorage:Load:{skill_group_id}/{version_id}] "
        
        version_dir = self._get_version_dir(skill_group_id, version_id)
        
        if not await asyncio.to_thread(os.path.isdir, version_dir):
            logger.debug("%sVersion directory not found: %s", log_prefix, version_dir)
            return None
        
        try:
            scripts = {}
            resources = {}
            
            # Load scripts
            scripts_dir = os.path.join(version_dir, "scripts")
            if await asyncio.to_thread(os.path.isdir, scripts_dir):
                for filename in await asyncio.to_thread(os.listdir, scripts_dir):
                    file_path = os.path.join(scripts_dir, filename)
                    if await asyncio.to_thread(os.path.isfile, file_path):
                        scripts[filename] = await self._read_file(file_path)
            
            # Load resources
            resources_dir = os.path.join(version_dir, "resources")
            if await asyncio.to_thread(os.path.isdir, resources_dir):
                for filename in await asyncio.to_thread(os.listdir, resources_dir):
                    file_path = os.path.join(resources_dir, filename)
                    if await asyncio.to_thread(os.path.isfile, file_path):
                        resources[filename] = await self._read_file(file_path)
            
            result = BundledResources(scripts=scripts, resources=resources)
            logger.info(
                "%sLoaded %d files (%d scripts, %d resources)",
                log_prefix,
                result.total_files(),
                len(scripts),
                len(resources),
            )
            return result
            
        except OSError as e:
            logger.error("%sFailed to load resources: %s", log_prefix, e)
            return None
    
    async def load_file(
        self,
        skill_group_id: str,
        version_id: str,
        file_path: str,
    ) -> Optional[bytes]:
        """Load a single file from bundled resources."""
        log_prefix = f"[FSSkillStorage:LoadFile:{skill_group_id}/{version_id}] "
        
        version_dir = self._get_version_dir(skill_group_id, version_id)
        
        # Sanitize file path to prevent traversal
        safe_path = os.path.normpath(file_path)
        if safe_path.startswith("..") or os.path.isabs(safe_path):
            logger.warning("%sInvalid file path (traversal attempt): %s", log_prefix, file_path)
            return None
        
        full_path = os.path.join(version_dir, safe_path)
        
        # Ensure the resolved path is within version_dir
        if not os.path.abspath(full_path).startswith(os.path.abspath(version_dir)):
            logger.warning("%sPath traversal detected: %s", log_prefix, file_path)
            return None
        
        if not await asyncio.to_thread(os.path.isfile, full_path):
            logger.debug("%sFile not found: %s", log_prefix, file_path)
            return None
        
        try:
            content = await self._read_file(full_path)
            logger.debug("%sLoaded file: %s (%d bytes)", log_prefix, file_path, len(content))
            return content
        except OSError as e:
            logger.error("%sFailed to load file %s: %s", log_prefix, file_path, e)
            return None
    
    async def delete_resources(
        self,
        skill_group_id: str,
        version_id: str,
    ) -> bool:
        """Delete all bundled resources for a skill version."""
        log_prefix = f"[FSSkillStorage:Delete:{skill_group_id}/{version_id}] "
        
        version_dir = self._get_version_dir(skill_group_id, version_id)
        
        if not await asyncio.to_thread(os.path.isdir, version_dir):
            logger.debug("%sVersion directory not found: %s", log_prefix, version_dir)
            return False
        
        try:
            await asyncio.to_thread(shutil.rmtree, version_dir)
            logger.info("%sDeleted resources directory: %s", log_prefix, version_dir)
            
            # Clean up empty parent directories
            group_dir = os.path.dirname(version_dir)
            if await asyncio.to_thread(os.path.isdir, group_dir):
                if not await asyncio.to_thread(os.listdir, group_dir):
                    await asyncio.to_thread(os.rmdir, group_dir)
                    logger.debug("%sRemoved empty group directory: %s", log_prefix, group_dir)
            
            return True
        except OSError as e:
            logger.error("%sFailed to delete resources: %s", log_prefix, e)
            return False
    
    async def list_files(
        self,
        skill_group_id: str,
        version_id: str,
    ) -> Dict[str, List[str]]:
        """List all files in bundled resources."""
        log_prefix = f"[FSSkillStorage:List:{skill_group_id}/{version_id}] "
        
        version_dir = self._get_version_dir(skill_group_id, version_id)
        result = {"scripts": [], "resources": []}
        
        if not await asyncio.to_thread(os.path.isdir, version_dir):
            logger.debug("%sVersion directory not found: %s", log_prefix, version_dir)
            return result
        
        try:
            # List scripts
            scripts_dir = os.path.join(version_dir, "scripts")
            if await asyncio.to_thread(os.path.isdir, scripts_dir):
                for filename in await asyncio.to_thread(os.listdir, scripts_dir):
                    file_path = os.path.join(scripts_dir, filename)
                    if await asyncio.to_thread(os.path.isfile, file_path):
                        result["scripts"].append(filename)
            
            # List resources
            resources_dir = os.path.join(version_dir, "resources")
            if await asyncio.to_thread(os.path.isdir, resources_dir):
                for filename in await asyncio.to_thread(os.listdir, resources_dir):
                    file_path = os.path.join(resources_dir, filename)
                    if await asyncio.to_thread(os.path.isfile, file_path):
                        result["resources"].append(filename)
            
            result["scripts"].sort()
            result["resources"].sort()
            
            logger.debug(
                "%sFound %d scripts, %d resources",
                log_prefix,
                len(result["scripts"]),
                len(result["resources"]),
            )
            return result
            
        except OSError as e:
            logger.error("%sFailed to list files: %s", log_prefix, e)
            return result
    
    async def exists(
        self,
        skill_group_id: str,
        version_id: str,
    ) -> bool:
        """Check if bundled resources exist for a skill version."""
        version_dir = self._get_version_dir(skill_group_id, version_id)
        return await asyncio.to_thread(os.path.isdir, version_dir)
    
    async def _write_file(self, path: str, content: bytes) -> None:
        """Write content to a file with fsync."""
        def _write():
            with open(path, "wb") as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
        await asyncio.to_thread(_write)
    
    async def _read_file(self, path: str) -> bytes:
        """Read content from a file."""
        def _read():
            with open(path, "rb") as f:
                return f.read()
        return await asyncio.to_thread(_read)