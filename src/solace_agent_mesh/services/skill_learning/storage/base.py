"""
Base interface for skill resource storage.

Defines the abstract interface that all storage backends must implement.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import mimetypes


@dataclass
class ResourceFile:
    """Represents a single resource file."""
    path: str  # Relative path within the skill (e.g., "scripts/main.py")
    content: bytes
    mime_type: str = "application/octet-stream"
    
    @classmethod
    def from_text(cls, path: str, content: str, encoding: str = "utf-8") -> "ResourceFile":
        """Create a ResourceFile from text content."""
        mime_type, _ = mimetypes.guess_type(path)
        return cls(
            path=path,
            content=content.encode(encoding),
            mime_type=mime_type or "text/plain",
        )
    
    def to_text(self, encoding: str = "utf-8") -> str:
        """Get content as text string."""
        return self.content.decode(encoding)


@dataclass
class BundledResources:
    """Collection of bundled resources for a skill version."""
    scripts: Dict[str, bytes] = field(default_factory=dict)  # filename -> content
    resources: Dict[str, bytes] = field(default_factory=dict)  # filename -> content
    
    def get_manifest(self) -> Dict[str, List[str]]:
        """Returns manifest of file names."""
        return {
            "scripts": sorted(self.scripts.keys()),
            "resources": sorted(self.resources.keys()),
        }
    
    def is_empty(self) -> bool:
        """Check if there are no bundled resources."""
        return not self.scripts and not self.resources
    
    def total_files(self) -> int:
        """Get total number of files."""
        return len(self.scripts) + len(self.resources)
    
    def total_size(self) -> int:
        """Get total size of all files in bytes."""
        return sum(len(c) for c in self.scripts.values()) + sum(len(c) for c in self.resources.values())
    
    @classmethod
    def from_text_dict(
        cls,
        scripts: Optional[Dict[str, str]] = None,
        resources: Optional[Dict[str, str]] = None,
        encoding: str = "utf-8",
    ) -> "BundledResources":
        """Create BundledResources from text dictionaries."""
        return cls(
            scripts={k: v.encode(encoding) for k, v in (scripts or {}).items()},
            resources={k: v.encode(encoding) if isinstance(v, str) else v for k, v in (resources or {}).items()},
        )
    
    def to_text_dict(self, encoding: str = "utf-8") -> Dict[str, Dict[str, str]]:
        """Convert to text dictionaries (for JSON serialization)."""
        return {
            "scripts": {k: v.decode(encoding) for k, v in self.scripts.items()},
            "resources": {k: self._decode_or_base64(v, encoding) for k, v in self.resources.items()},
        }
    
    def _decode_or_base64(self, content: bytes, encoding: str) -> str:
        """Try to decode as text, fall back to base64 for binary."""
        import base64
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            return base64.b64encode(content).decode("ascii")


class BaseSkillResourceStorage(ABC):
    """
    Abstract base class for skill resource storage.
    
    Implementations must provide storage for skill bundled resources
    (scripts, data files) that accompany skill definitions.
    """
    
    @abstractmethod
    async def save_resources(
        self,
        skill_group_id: str,
        version_id: str,
        resources: BundledResources,
    ) -> str:
        """
        Save bundled resources for a skill version.
        
        Args:
            skill_group_id: The skill group ID
            version_id: The skill version ID
            resources: The bundled resources to save
            
        Returns:
            URI reference to the stored resources (e.g., "s3://bucket/path/" or "file:///path/")
        """
        pass
    
    @abstractmethod
    async def load_resources(
        self,
        skill_group_id: str,
        version_id: str,
    ) -> Optional[BundledResources]:
        """
        Load bundled resources for a skill version.
        
        Args:
            skill_group_id: The skill group ID
            version_id: The skill version ID
            
        Returns:
            BundledResources if found, None otherwise
        """
        pass
    
    @abstractmethod
    async def load_file(
        self,
        skill_group_id: str,
        version_id: str,
        file_path: str,
    ) -> Optional[bytes]:
        """
        Load a single file from bundled resources.
        
        Args:
            skill_group_id: The skill group ID
            version_id: The skill version ID
            file_path: Relative path to the file (e.g., "scripts/main.py")
            
        Returns:
            File content as bytes if found, None otherwise
        """
        pass
    
    @abstractmethod
    async def delete_resources(
        self,
        skill_group_id: str,
        version_id: str,
    ) -> bool:
        """
        Delete all bundled resources for a skill version.
        
        Args:
            skill_group_id: The skill group ID
            version_id: The skill version ID
            
        Returns:
            True if resources were deleted, False if not found
        """
        pass
    
    @abstractmethod
    async def list_files(
        self,
        skill_group_id: str,
        version_id: str,
    ) -> Dict[str, List[str]]:
        """
        List all files in bundled resources.
        
        Args:
            skill_group_id: The skill group ID
            version_id: The skill version ID
            
        Returns:
            Dictionary with "scripts" and "resources" keys, each containing list of filenames
        """
        pass
    
    @abstractmethod
    async def exists(
        self,
        skill_group_id: str,
        version_id: str,
    ) -> bool:
        """
        Check if bundled resources exist for a skill version.
        
        Args:
            skill_group_id: The skill group ID
            version_id: The skill version ID
            
        Returns:
            True if resources exist, False otherwise
        """
        pass
    
    def get_uri(self, skill_group_id: str, version_id: str) -> str:
        """
        Get the URI for a skill version's resources.
        
        This is a helper method that subclasses can override.
        """
        raise NotImplementedError("Subclass must implement get_uri()")