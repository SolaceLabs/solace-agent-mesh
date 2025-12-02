"""
Skill resource storage services.

This module provides storage backends for skill bundled resources (scripts, data files).
Supports both local filesystem and S3-compatible object storage.
"""

from .base import (
    BaseSkillResourceStorage,
    BundledResources,
    ResourceFile,
)
from .filesystem_storage import FilesystemSkillResourceStorage
from .s3_storage import S3SkillResourceStorage
from .factory import create_skill_resource_storage

__all__ = [
    "BaseSkillResourceStorage",
    "BundledResources",
    "ResourceFile",
    "FilesystemSkillResourceStorage",
    "S3SkillResourceStorage",
    "create_skill_resource_storage",
]