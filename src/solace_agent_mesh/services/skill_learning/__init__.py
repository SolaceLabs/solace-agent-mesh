"""
SAM Skill Learning System.

This module provides the skill learning functionality for SAM,
including skill extraction, storage, search, and versioning.
"""

# Legacy entities (for backward compatibility)
from .entities import (
    Skill,
    SkillType,
    SkillScope,
    SkillFeedback,
    SkillShare,
    SkillUsage,
    LearningQueueItem,
    AgentChainNode,
    AgentToolStep,
    StepType,
    now_epoch_ms,
)

# Versioned entities
from .entities.versioned_entities import (
    SkillGroup,
    SkillVersion,
    SkillGroupUser,
    SkillGroupRole,
    CreateSkillGroupRequest,
    CreateVersionRequest,
)

# Legacy service (for backward compatibility)
from .services.skill_service import SkillService

# Versioned service
from .services.versioned_skill_service import VersionedSkillService

# Additional services
from .services.embedding_service import EmbeddingService
from .services.static_skill_loader import StaticSkillLoader

# Legacy repository
from .repository.skill_repository import SkillRepository

# Versioned repository
from .repository.versioned_repository import VersionedSkillRepository

# Skill extractor
from .extraction.skill_extractor import SkillExtractor

# Resource storage
from .storage import (
    BaseSkillResourceStorage,
    BundledResources,
    ResourceFile,
    FilesystemSkillResourceStorage,
    S3SkillResourceStorage,
    create_skill_resource_storage,
)

__all__ = [
    # Legacy entities
    "Skill",
    "SkillType",
    "SkillScope",
    "SkillFeedback",
    "SkillShare",
    "SkillUsage",
    "LearningQueueItem",
    "AgentChainNode",
    "AgentToolStep",
    "StepType",
    "now_epoch_ms",
    # Versioned entities
    "SkillGroup",
    "SkillVersion",
    "SkillGroupUser",
    "SkillGroupRole",
    "CreateSkillGroupRequest",
    "CreateVersionRequest",
    # Services
    "SkillService",
    "VersionedSkillService",
    "SkillExtractor",
    "EmbeddingService",
    "StaticSkillLoader",
    # Repositories
    "SkillRepository",
    "VersionedSkillRepository",
    # Resource storage
    "BaseSkillResourceStorage",
    "BundledResources",
    "ResourceFile",
    "FilesystemSkillResourceStorage",
    "S3SkillResourceStorage",
    "create_skill_resource_storage",
]