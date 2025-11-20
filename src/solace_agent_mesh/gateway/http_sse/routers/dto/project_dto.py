"""
Project export/import DTOs.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class ArtifactMetadata(BaseModel):
    """Metadata for an artifact in export"""
    filename: str
    mime_type: str = Field(alias="mimeType")
    size: int
    metadata: Dict[str, Any] = {}
    
    model_config = {"populate_by_name": True}


class ProjectExportMetadata(BaseModel):
    """Metadata for exported project"""
    original_created_at: int = Field(alias="originalCreatedAt")
    artifact_count: int = Field(alias="artifactCount")
    total_size_bytes: int = Field(alias="totalSizeBytes")
    
    model_config = {"populate_by_name": True}


class ProjectExportData(BaseModel):
    """Project data in export format"""
    name: str
    description: Optional[str] = None
    system_prompt: Optional[str] = Field(default=None, alias="systemPrompt")
    default_agent_id: Optional[str] = Field(default=None, alias="defaultAgentId")
    metadata: ProjectExportMetadata
    
    model_config = {"populate_by_name": True}


class ProjectExportFormat(BaseModel):
    """Complete export format"""
    version: str = "1.0"
    exported_at: int = Field(alias="exportedAt")
    project: ProjectExportData
    artifacts: List[ArtifactMetadata] = []
    
    model_config = {"populate_by_name": True}


class ProjectImportOptions(BaseModel):
    """Options for project import"""
    preserve_name: bool = Field(default=False, alias="preserveName")
    custom_name: Optional[str] = Field(default=None, alias="customName")
    
    model_config = {"populate_by_name": True}


class ProjectImportRequest(BaseModel):
    """Request for importing project"""
    options: ProjectImportOptions


class ProjectImportResponse(BaseModel):
    """Response after importing project"""
    project_id: str = Field(alias="projectId")
    name: str
    artifacts_imported: int = Field(alias="artifactsImported")
    warnings: List[str] = []
    
    model_config = {"populate_by_name": True}