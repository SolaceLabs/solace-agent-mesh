
"""
API Router for versioned skill management.

Provides endpoints for:
- Listing and searching skill groups
- Getting skill group details with versions
- Creating new skills (group + initial version)
- Creating new versions
- Rollback to previous versions
- Managing skill sharing
- Import/Export skills
"""

import logging
import re
import yaml
import json
import zipfile
import base64
from io import BytesIO
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File
from fastapi import Request as FastAPIRequest
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DBSession

from ..dependencies import get_db, get_user_id
from ..shared.types import UserId

log = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# Request/Response DTOs
# ============================================================================

class SkillStepDTO(BaseModel):
    """A step in a skill procedure."""
    step_number: int
    description: str
    tool_name: Optional[str] = None
    tool_parameters: Optional[dict] = None
    agent_name: Optional[str] = None


class AgentChainNodeDTO(BaseModel):
    """A node in the agent chain."""
    agent_name: str
    order: int
    role: Optional[str] = None
    tools_used: List[str] = Field(default_factory=list)


class SkillVersionDTO(BaseModel):
    """Skill version response."""
    id: str
    group_id: str
    version: int
    description: str
    markdown_content: Optional[str] = None
    summary: Optional[str] = None
    steps: List[SkillStepDTO] = Field(default_factory=list)
    agent_chain: List[AgentChainNodeDTO] = Field(default_factory=list)
    source_task_id: Optional[str] = None
    related_task_ids: List[str] = Field(default_factory=list)
    involved_agents: List[str] = Field(default_factory=list)
    complexity_score: int = 0
    created_by_user_id: Optional[str] = None
    creation_reason: Optional[str] = None
    created_at: str
    # Bundled resources info
    bundled_resources_uri: Optional[str] = None
    bundled_resources_manifest: Optional[Dict[str, List[str]]] = None


class SkillGroupDTO(BaseModel):
    """Skill group response."""
    id: str
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    type: str
    scope: str
    owner_agent_name: Optional[str] = None
    owner_user_id: Optional[str] = None
    is_archived: bool = False
    version_count: int = 0
    success_rate: Optional[float] = None
    created_at: str
    updated_at: str
    production_version: Optional[SkillVersionDTO] = None


class SkillGroupSummaryDTO(BaseModel):
    """Skill group summary for listing."""
    id: str
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    type: str
    scope: str
    owner_agent_name: Optional[str] = None
    is_archived: bool = False
    version_count: int = 0
    success_rate: Optional[float] = None
    production_version_id: Optional[str] = None


class SkillGroupListResponse(BaseModel):
    """List response for skill groups."""
    skills: List[SkillGroupSummaryDTO]
    total: int
    page: int
    page_size: int


class CreateSkillRequest(BaseModel):
    """Request to create a new skill."""
    name: str
    description: str
    scope: str = "user"  # user, shared, global, agent
    category: Optional[str] = None
    owner_agent: Optional[str] = None
    markdown_content: Optional[str] = None
    summary: Optional[str] = None
    steps: List[SkillStepDTO] = Field(default_factory=list)
    agent_chain: List[AgentChainNodeDTO] = Field(default_factory=list)


class CreateVersionRequest(BaseModel):
    """Request to create a new version."""
    description: str
    creation_reason: str
    markdown_content: Optional[str] = None
    summary: Optional[str] = None
    steps: List[SkillStepDTO] = Field(default_factory=list)
    agent_chain: List[AgentChainNodeDTO] = Field(default_factory=list)
    set_as_production: bool = True


class RollbackRequest(BaseModel):
    """Request to rollback to a version."""
    version_id: str


class ShareSkillRequest(BaseModel):
    """Request to share a skill."""
    target_user_id: str
    role: str = "viewer"  # viewer, editor


class SkillImportRequest(BaseModel):
    """Request to import a skill from markdown content."""
    markdown_content: str
    scope: str = "user"  # user, shared, global, agent
    owner_agent: Optional[str] = None


class SkillImportResponse(BaseModel):
    """Response after importing a skill."""
    skill_id: str
    name: str
    message: str
    warnings: List[str] = Field(default_factory=list)
    references_count: int = 0
    scripts_count: int = 0
    assets_count: int = 0


# ============================================================================
# Helper Functions
# ============================================================================

def get_versioned_skill_service():
    """Get the versioned skill service instance."""
    from ..dependencies import get_versioned_skill_service as _get_service
    return _get_service()


def get_skill_resource_storage():
    """Get the skill resource storage instance."""
    from ..dependencies import get_skill_resource_storage as _get_storage
    return _get_storage()


def _epoch_to_iso(epoch_ms: int) -> str:
    """Convert epoch milliseconds to ISO string."""
    if not epoch_ms:
        return ""
    return datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc).isoformat()


def _version_to_dto(version) -> SkillVersionDTO:
    """Convert a SkillVersion entity to DTO."""
    steps = []
    if version.tool_steps:
        for i, step in enumerate(version.tool_steps):
            steps.append(SkillStepDTO(
                step_number=step.sequence_number if hasattr(step, 'sequence_number') else i + 1,
                description=step.action if hasattr(step, 'action') else "",
                tool_name=step.tool_name if hasattr(step, 'tool_name') else None,
                tool_parameters=step.parameters_template if hasattr(step, 'parameters_template') else None,
                agent_name=step.agent_name if hasattr(step, 'agent_name') else None,
            ))
    
    agent_chain = []
    if version.agent_chain:
        for i, node in enumerate(version.agent_chain):
            agent_chain.append(AgentChainNodeDTO(
                agent_name=node.agent_name,
                order=i + 1,
                role=node.role if hasattr(node, 'role') else None,
                tools_used=node.tools_used or [],
            ))
    
    return SkillVersionDTO(
        id=version.id,
        group_id=version.group_id,
        version=version.version,
        description=version.description,
        markdown_content=version.markdown_content,
        summary=version.summary,
        steps=steps,
        agent_chain=agent_chain,
        source_task_id=version.source_task_id,
        related_task_ids=version.related_task_ids or [],
        involved_agents=version.involved_agents or [],
        complexity_score=version.complexity_score or 0,
        created_by_user_id=version.created_by_user_id,
        creation_reason=version.creation_reason,
        created_at=_epoch_to_iso(version.created_at),
        bundled_resources_uri=getattr(version, 'bundled_resources_uri', None),
        bundled_resources_manifest=getattr(version, 'bundled_resources_manifest', None),
    )


def _group_to_dto(group, include_production: bool = True) -> SkillGroupDTO:
    """Convert a SkillGroup entity to DTO."""
    production_version = None
    if include_production and group.production_version:
        production_version = _version_to_dto(group.production_version)
    
    return SkillGroupDTO(
        id=group.id,
        name=group.name,
        description=group.description,
        category=group.category,
        type=group.type.value if hasattr(group.type, 'value') else str(group.type),
        scope=group.scope.value if hasattr(group.scope, 'value') else str(group.scope),
        owner_agent_name=group.owner_agent_name,
        owner_user_id=group.owner_user_id,
        is_archived=group.is_archived,
        version_count=group.version_count,
        success_rate=group.get_success_rate() if hasattr(group, 'get_success_rate') else None,
        created_at=_epoch_to_iso(group.created_at),
        updated_at=_epoch_to_iso(group.updated_at),
        production_version=production_version,
    )


def _group_to_summary(group) -> SkillGroupSummaryDTO:
    """Convert a SkillGroup entity to summary DTO."""
    return SkillGroupSummaryDTO(
        id=group.id,
        name=group.name,
        description=group.description,
        category=group.category,
        type=group.type.value if hasattr(group.type, 'value') else str(group.type),
        scope=group.scope.value if hasattr(group.scope, 'value') else str(group.scope),
        owner_agent_name=group.owner_agent_name,
        is_archived=group.is_archived,
        version_count=group.version_count,
        success_rate=group.get_success_rate() if hasattr(group, 'get_success_rate') else None,
        production_version_id=group.production_version_id,
    )


# ============================================================================
# Endpoints
# ============================================================================

# NOTE: Routes with literal path segments (like /skills/agent/{agent_name} and
# /skills/search/semantic) MUST be defined BEFORE routes with path parameters
# (like /skills/{group_id}) to ensure correct route matching in FastAPI.

# ============================================================================
# Agent-specific Endpoints (must be before /skills/{group_id})
# ============================================================================

@router.get("/skills/agent/{agent_name}", response_model=SkillGroupListResponse, tags=["Skills"])
async def get_agent_skills(
    agent_name: str,
    request: FastAPIRequest,
    include_global: bool = Query(True, description="Include global skills"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    db: DBSession = Depends(get_db),
    user_id: UserId = Depends(get_user_id),
):
    """
    Get skills available to a specific agent.
    
    Returns agent-specific skills and optionally global skills.
    
    Note: Returns empty list if skill learning service is not configured.
    """
    log_prefix = f"[GET /api/v1/skills/agent/{agent_name}] "
    log.info("%sRequest from user %s", log_prefix, user_id)
    
    try:
        service = get_versioned_skill_service()
        if service is None:
            # Return empty results when skill service is not configured
            log.debug("%sSkill service not configured, returning empty results", log_prefix)
            return SkillGroupListResponse(
                skills=[],
                total=0,
                page=page,
                page_size=page_size,
            )
        
        groups = service.get_skills_for_agent(
            agent_name=agent_name,
            user_id=user_id,
            include_global=include_global,
            limit=page_size,
        )
        
        return SkillGroupListResponse(
            skills=[_group_to_summary(g) for g in groups],
            total=len(groups),
            page=page,
            page_size=page_size,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        log.exception("%sError getting agent skills: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while getting agent skills.",
        )


# ============================================================================
# Search Endpoints (must be before /skills/{group_id})
# ============================================================================

@router.get("/skills/search/semantic", response_model=SkillGroupListResponse, tags=["Skills"])
async def semantic_search_skills(
    request: FastAPIRequest,
    query: str = Query(..., description="Search query"),
    agent: Optional[str] = Query(None, description="Filter by agent name"),
    limit: int = Query(10, ge=1, le=50, description="Maximum results"),
    db: DBSession = Depends(get_db),
    user_id: UserId = Depends(get_user_id),
):
    """
    Semantic search for skills using embeddings.
    
    Uses vector similarity to find skills that match the query semantically.
    
    Note: Returns empty list if skill learning service is not configured.
    """
    log_prefix = "[GET /api/v1/skills/search/semantic] "
    log.info("%sRequest from user %s, query: %s", log_prefix, user_id, query)
    
    try:
        service = get_versioned_skill_service()
        if service is None:
            # Return empty results when skill service is not configured
            log.debug("%sSkill service not configured, returning empty results", log_prefix)
            return SkillGroupListResponse(
                skills=[],
                total=0,
                page=1,
                page_size=limit,
            )
        
        results = service.semantic_search(
            query=query,
            agent_name=agent,
            user_id=user_id,
            limit=limit,
        )
        
        groups = [group for group, _ in results]
        
        return SkillGroupListResponse(
            skills=[_group_to_summary(g) for g in groups],
            total=len(groups),
            page=1,
            page_size=limit,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        log.exception("%sError in semantic search: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during semantic search.",
        )


# ============================================================================
# Import Endpoints (must be before /skills/{group_id})
# ============================================================================

def _parse_skill_markdown(content: str) -> dict:
    """
    Parse a .SKILL.md file content into skill data.
    
    Expected format:
    ---
    name: skill-name
    description: Skill description
    summary: Short summary
    involved_agents:
      - Agent1
      - Agent2
    complexity_score: 30
    ---
    
    # Skill Title
    
    Markdown content...
    """
    # Split frontmatter from content
    import re as re_module
    frontmatter_match = re_module.match(r'^---\s*\n(.*?)\n---\s*\n(.*)$', content, re_module.DOTALL)
    
    if not frontmatter_match:
        raise ValueError("Invalid skill format: missing YAML frontmatter (---)")
    
    frontmatter_str = frontmatter_match.group(1)
    markdown_body = frontmatter_match.group(2).strip()
    
    try:
        frontmatter = yaml.safe_load(frontmatter_str)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML frontmatter: {e}")
    
    if not isinstance(frontmatter, dict):
        raise ValueError("Invalid frontmatter: expected a YAML dictionary")
    
    # Validate required fields
    if not frontmatter.get("name"):
        raise ValueError("Missing required field: name")
    if not frontmatter.get("description"):
        raise ValueError("Missing required field: description")
    
    return {
        "name": frontmatter.get("name"),
        "description": frontmatter.get("description"),
        "summary": frontmatter.get("summary"),
        "involved_agents": frontmatter.get("involved_agents", []),
        "complexity_score": frontmatter.get("complexity_score"),
        "markdown_content": markdown_body,
        "metadata": {
            k: v for k, v in frontmatter.items()
            if k not in ["name", "description", "summary", "involved_agents", "complexity_score"]
        }
    }


def _parse_skill_zip(zip_buffer: BytesIO) -> Dict[str, Any]:
    """
    Parse a Skill Package ZIP file.
    
    A skill package is a folder containing:
    - SKILL.md: Main skill file with YAML frontmatter for metadata and instructions
    - scripts/: Executable code (Python scripts, shell scripts, etc.)
    - resources/: Data files, templates, and other supporting files
    
    Expected structure:
    skill-name/
    ├── SKILL.md              (required - instructions with YAML frontmatter)
    ├── scripts/              (optional - executable code)
    │   └── *.py, *.sh files
    └── resources/            (optional - data files, templates)
        └── any files
    
    Also supports legacy 'references/' and 'assets/' directories.
    
    Returns dict with:
    - skill_data: parsed SKILL.md data
    - scripts: dict of filename -> content
    - resources: dict of filename -> content (text) or base64 (binary)
    """
    try:
        with zipfile.ZipFile(zip_buffer, 'r') as zip_ref:
            namelist = zip_ref.namelist()
            
            # Find SKILL.md - could be at root or in a subdirectory
            skill_md_path = None
            base_dir = ""
            
            for name in namelist:
                if name.endswith('SKILL.md'):
                    skill_md_path = name
                    # Get base directory (everything before SKILL.md)
                    base_dir = name.rsplit('SKILL.md', 1)[0]
                    break
            
            if not skill_md_path:
                raise ValueError("Invalid skill ZIP: missing SKILL.md file")
            
            # Read and parse SKILL.md
            skill_md_content = zip_ref.read(skill_md_path).decode('utf-8')
            skill_data = _parse_skill_markdown(skill_md_content)
            
            # Read bundled resources
            scripts = {}
            resources = {}
            
            for name in namelist:
                # Skip directories and SKILL.md itself
                if name.endswith('/') or name == skill_md_path:
                    continue
                
                # Get relative path from base directory
                if base_dir and name.startswith(base_dir):
                    rel_path = name[len(base_dir):]
                else:
                    rel_path = name
                
                # Categorize by directory
                # Support both 'scripts/' and legacy naming
                if rel_path.startswith('scripts/'):
                    filename = rel_path[len('scripts/'):]
                    if filename:
                        try:
                            scripts[filename] = zip_ref.read(name).decode('utf-8')
                        except UnicodeDecodeError:
                            log.warning(f"Skipping non-text script file: {filename}")
                
                # Support 'resources/', 'references/', and 'assets/' directories
                elif rel_path.startswith('resources/') or rel_path.startswith('references/') or rel_path.startswith('assets/'):
                    # Extract directory prefix
                    dir_prefix = rel_path.split('/')[0] + '/'
                    filename = rel_path[len(dir_prefix):]
                    if filename:
                        try:
                            resources[filename] = zip_ref.read(name).decode('utf-8')
                        except UnicodeDecodeError:
                            # Binary files stored as base64
                            resources[filename] = base64.b64encode(zip_ref.read(name)).decode('ascii')
            
            return {
                "skill_data": skill_data,
                "scripts": scripts,
                "resources": resources,
            }
            
    except zipfile.BadZipFile:
        raise ValueError("Invalid ZIP file")


@router.post("/skills/import", response_model=SkillImportResponse, tags=["Skills"])
async def import_skill(
    request: FastAPIRequest,
    payload: SkillImportRequest,
    db: DBSession = Depends(get_db),
    user_id: UserId = Depends(get_user_id),
):
    """
    Import a skill from markdown content.
    
    Accepts .SKILL.md format with YAML frontmatter.
    """
    log_prefix = "[POST /api/v1/skills/import] "
    log.info("%sRequest from user %s", log_prefix, user_id)
    
    try:
        service = get_versioned_skill_service()
        if service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Skill learning service is not available",
            )
        
        # Parse the markdown content
        try:
            skill_data = _parse_skill_markdown(payload.markdown_content)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )
        
        from ....services.skill_learning import SkillType, SkillScope
        
        # Map scope string to enum
        scope_map = {
            "user": SkillScope.USER,
            "shared": SkillScope.SHARED,
            "global": SkillScope.GLOBAL,
            "agent": SkillScope.AGENT,
        }
        scope = scope_map.get(payload.scope, SkillScope.USER)
        
        warnings = []
        
        # Create the skill
        created_group = service.create_skill(
            name=skill_data["name"],
            description=skill_data["description"],
            skill_type=SkillType.AUTHORED,
            scope=scope,
            owner_agent_name=payload.owner_agent or (skill_data["involved_agents"][0] if skill_data["involved_agents"] else None),
            owner_user_id=user_id,
            markdown_content=skill_data["markdown_content"],
            summary=skill_data.get("summary"),
            created_by_user_id=user_id,
        )
        
        return SkillImportResponse(
            skill_id=created_group.id,
            name=created_group.name,
            message="Skill imported successfully",
            warnings=warnings,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        log.exception("%sError importing skill: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while importing the skill.",
        )


@router.post("/skills/import/file", response_model=SkillImportResponse, tags=["Skills"])
async def import_skill_file(
    request: FastAPIRequest,
    file: UploadFile = File(..., description="Skill file (.zip, .SKILL.md, or .json)"),
    scope: str = Query("user", description="Skill scope: user, shared, global, agent"),
    owner_agent: Optional[str] = Query(None, description="Owner agent name"),
    db: DBSession = Depends(get_db),
    user_id: UserId = Depends(get_user_id),
):
    """
    Import a skill from an uploaded file.
    
    Accepts:
    - .zip files (skill package with SKILL.md + scripts/ + resources/)
    - .SKILL.md files (single skill file)
    - .json files (exported skill format)
    """
    log_prefix = "[POST /api/v1/skills/import/file] "
    log.info("%sRequest from user %s, filename: %s", log_prefix, user_id, file.filename)
    
    try:
        service = get_versioned_skill_service()
        if service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Skill learning service is not available",
            )
        
        # Read file content
        content = await file.read()
        
        # Determine file type
        filename = file.filename or ""
        is_zip = filename.endswith(".zip")
        is_markdown = filename.endswith(".SKILL.md") or filename.endswith(".md")
        is_json = filename.endswith(".json")
        
        if not is_zip and not is_markdown and not is_json:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported file type. Please upload a .zip, .SKILL.md, or .json file.",
            )
        
        from ....services.skill_learning import SkillType, SkillScope
        
        # Map scope string to enum
        scope_map = {
            "user": SkillScope.USER,
            "shared": SkillScope.SHARED,
            "global": SkillScope.GLOBAL,
            "agent": SkillScope.AGENT,
        }
        scope_enum = scope_map.get(scope, SkillScope.USER)
        
        warnings = []
        references_count = 0
        scripts_count = 0
        assets_count = 0
        
        if is_zip:
            # Parse ZIP file (skill package format)
            try:
                zip_data = _parse_skill_zip(BytesIO(content))
                skill_data = zip_data["skill_data"]
                scripts = zip_data.get("scripts", {})
                resources = zip_data.get("resources", {})
                
                scripts_count = len(scripts)
                references_count = len(resources)
                
            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(e),
                )
            
            # Create the skill
            created_group = service.create_skill(
                name=skill_data["name"],
                description=skill_data["description"],
                skill_type=SkillType.AUTHORED,
                scope=scope_enum,
                owner_agent_name=owner_agent or (skill_data["involved_agents"][0] if skill_data.get("involved_agents") else None),
                owner_user_id=user_id,
                markdown_content=skill_data["markdown_content"],
                summary=skill_data.get("summary"),
                created_by_user_id=user_id,
            )
            
            # Store bundled resources if present
            if scripts or resources:
                resource_storage = get_skill_resource_storage()
                if resource_storage:
                    try:
                        from ....services.skill_learning import BundledResources
                        
                        bundled = BundledResources.from_text_dict(
                            scripts=scripts,
                            resources=resources,
                        )
                        
                        # Save resources to storage
                        resource_uri = await resource_storage.save_resources(
                            skill_group_id=created_group.id,
                            version_id=created_group.production_version_id,
                            resources=bundled,
                        )
                        
                        # Update version with resource reference
                        if resource_uri:
                            service.update_version_resources(
                                version_id=created_group.production_version_id,
                                bundled_resources_uri=resource_uri,
                                bundled_resources_manifest=bundled.get_manifest(),
                            )
                            log.info(
                                "%sStored bundled resources at %s",
                                log_prefix,
                                resource_uri,
                            )
                    except Exception as e:
                        log.warning(
                            "%sFailed to store bundled resources: %s",
                            log_prefix,
                            e,
                        )
                        warnings.append(f"Warning: Failed to store bundled resources: {e}")
                else:
                    warnings.append("Warning: Resource storage not configured, bundled resources not saved")
            
            if scripts_count > 0:
                warnings.append(f"Imported {scripts_count} script file(s)")
            if references_count > 0:
                warnings.append(f"Imported {references_count} resource file(s)")
                
        elif is_markdown:
            content_str = content.decode("utf-8")
            # Parse markdown content
            try:
                skill_data = _parse_skill_markdown(content_str)
            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(e),
                )
            
            # Create the skill
            created_group = service.create_skill(
                name=skill_data["name"],
                description=skill_data["description"],
                skill_type=SkillType.AUTHORED,
                scope=scope_enum,
                owner_agent_name=owner_agent or (skill_data["involved_agents"][0] if skill_data.get("involved_agents") else None),
                owner_user_id=user_id,
                markdown_content=skill_data["markdown_content"],
                summary=skill_data.get("summary"),
                created_by_user_id=user_id,
            )
        else:
            content_str = content.decode("utf-8")
            # Parse JSON content
            try:
                json_data = json.loads(content_str)
            except json.JSONDecodeError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid JSON: {e}",
                )
            
            # Validate JSON format
            if "skill" not in json_data:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid export format: missing 'skill' field",
                )
            
            skill_json = json_data["skill"]
            
            # Get markdown content from production_version if available
            markdown_content = None
            if "production_version" in json_data and json_data["production_version"]:
                markdown_content = json_data["production_version"].get("markdown_content")
            
            # Create the skill from JSON data
            created_group = service.create_skill(
                name=skill_json.get("name"),
                description=skill_json.get("description") or (json_data.get("production_version", {}).get("description")),
                skill_type=SkillType.AUTHORED,
                scope=scope_enum,
                owner_agent_name=owner_agent or skill_json.get("owner_agent_name"),
                owner_user_id=user_id,
                markdown_content=markdown_content,
                created_by_user_id=user_id,
            )
        
        return SkillImportResponse(
            skill_id=created_group.id,
            name=created_group.name,
            message="Skill imported successfully",
            warnings=warnings,
            references_count=references_count,
            scripts_count=scripts_count,
            assets_count=assets_count,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        log.exception("%sError importing skill file: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while importing the skill file.",
        )


# ============================================================================
# Main Skill Endpoints
# ============================================================================

@router.get("/skills", response_model=SkillGroupListResponse, tags=["Skills"])
async def list_skills(
    request: FastAPIRequest,
    query: Optional[str] = Query(None, description="Search query"),
    scope: Optional[str] = Query(None, description="Filter by scope"),
    agent: Optional[str] = Query(None, description="Filter by agent name"),
    type: Optional[str] = Query(None, description="Filter by type"),
    include_archived: bool = Query(False, description="Include archived skills"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    db: DBSession = Depends(get_db),
    user_id: UserId = Depends(get_user_id),
):
    """
    List skill groups with optional filters.
    
    Returns skill groups (not individual versions) accessible to the current user.
    
    Note: Returns empty list if skill learning service is not configured.
    """
    log_prefix = "[GET /api/v1/skills] "
    log.info("%sRequest from user %s", log_prefix, user_id)
    
    try:
        service = get_versioned_skill_service()
        if service is None:
            # Return empty results when skill service is not configured
            log.debug("%sSkill service not configured, returning empty results", log_prefix)
            return SkillGroupListResponse(
                skills=[],
                total=0,
                page=page,
                page_size=page_size,
            )
        
        from ....services.skill_learning import SkillScope, SkillType
        
        # Map scope string to enum
        scope_enum = None
        if scope:
            scope_map = {
                "user": SkillScope.USER,
                "shared": SkillScope.SHARED,
                "global": SkillScope.GLOBAL,
                "agent": SkillScope.AGENT,
            }
            scope_enum = scope_map.get(scope)
        
        # Map type string to enum
        type_enum = None
        if type:
            type_map = {
                "learned": SkillType.LEARNED,
                "authored": SkillType.AUTHORED,
            }
            type_enum = type_map.get(type)
        
        if query:
            # Search
            results = service.search_skills(
                query=query,
                agent_name=agent,
                user_id=user_id,
                scope=scope_enum,
                skill_type=type_enum,
                include_global=True,
                limit=page_size,
            )
            groups = [group for group, _ in results]
        else:
            # List
            groups = service.list_skills(
                agent_name=agent,
                user_id=user_id,
                scope=scope_enum,
                skill_type=type_enum,
                include_archived=include_archived,
                include_global=True,
                limit=page_size,
                offset=(page - 1) * page_size,
            )
        
        return SkillGroupListResponse(
            skills=[_group_to_summary(g) for g in groups],
            total=len(groups),
            page=page,
            page_size=page_size,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        log.exception("%sError listing skills: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while listing skills.",
        )


@router.get("/skills/{group_id}", response_model=SkillGroupDTO, tags=["Skills"])
async def get_skill(
    group_id: str,
    request: FastAPIRequest,
    include_versions: bool = Query(False, description="Include all versions"),
    db: DBSession = Depends(get_db),
    user_id: UserId = Depends(get_user_id),
):
    """
    Get a skill group by ID.
    
    Returns the skill group with its production version.
    """
    log_prefix = f"[GET /api/v1/skills/{group_id}] "
    log.info("%sRequest from user %s", log_prefix, user_id)
    
    try:
        service = get_versioned_skill_service()
        if service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Skill learning service is not available",
            )
        
        group = service.get_skill(group_id, include_versions=include_versions)
        
        if not group:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Skill with ID '{group_id}' not found.",
            )
        
        return _group_to_dto(group)
        
    except HTTPException:
        raise
    except Exception as e:
        log.exception("%sError getting skill: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while getting the skill.",
        )


@router.post("/skills", response_model=SkillGroupDTO, status_code=status.HTTP_201_CREATED, tags=["Skills"])
async def create_skill(
    request: FastAPIRequest,
    payload: CreateSkillRequest,
    db: DBSession = Depends(get_db),
    user_id: UserId = Depends(get_user_id),
):
    """
    Create a new skill.
    
    Creates a skill group with an initial version (v1).
    """
    log_prefix = "[POST /api/v1/skills] "
    log.info("%sRequest from user %s to create skill: %s", log_prefix, user_id, payload.name)
    
    try:
        service = get_versioned_skill_service()
        if service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Skill learning service is not available",
            )
        
        from ....services.skill_learning import SkillType, SkillScope, AgentChainNode, AgentToolStep
        
        # Map scope string to enum
        scope_map = {
            "user": SkillScope.USER,
            "shared": SkillScope.SHARED,
            "global": SkillScope.GLOBAL,
            "agent": SkillScope.AGENT,
        }
        scope = scope_map.get(payload.scope, SkillScope.USER)
        
        # Convert steps DTOs to entities
        tool_steps = None
        if payload.steps:
            tool_steps = [
                AgentToolStep(
                    step_type="tool_call",
                    agent_name=step.agent_name or "unknown",
                    tool_name=step.tool_name or "unknown",
                    action=step.description,
                    parameters_template=step.tool_parameters,
                    sequence_number=step.step_number,
                )
                for step in payload.steps
            ]
        
        # Convert agent chain DTOs to entities
        agent_chain = None
        if payload.agent_chain:
            agent_chain = [
                AgentChainNode(
                    agent_name=node.agent_name,
                    task_id=f"task-{node.order}",
                    role=node.role or "specialist",
                    tools_used=node.tools_used,
                )
                for node in payload.agent_chain
            ]
        
        group = service.create_skill(
            name=payload.name,
            description=payload.description,
            skill_type=SkillType.AUTHORED,
            scope=scope,
            category=payload.category,
            owner_agent_name=payload.owner_agent,
            owner_user_id=user_id,
            markdown_content=payload.markdown_content,
            tool_steps=tool_steps,
            agent_chain=agent_chain,
            summary=payload.summary,
            created_by_user_id=user_id,
        )
        
        return _group_to_dto(group)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except HTTPException:
        raise
    except Exception as e:
        log.exception("%sError creating skill: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while creating the skill.",
        )


@router.delete("/skills/{group_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Skills"])
async def delete_skill(
    group_id: str,
    request: FastAPIRequest,
    db: DBSession = Depends(get_db),
    user_id: UserId = Depends(get_user_id),
):
    """
    Delete a skill group (and all its versions).
    
    Only the skill owner can delete a skill.
    """
    log_prefix = f"[DELETE /api/v1/skills/{group_id}] "
    log.info("%sRequest from user %s", log_prefix, user_id)
    
    try:
        service = get_versioned_skill_service()
        if service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Skill learning service is not available",
            )
        
        # First check if the skill exists in the database (not just static cache)
        # We need to check the repository directly to distinguish database vs static skills
        db_group = service.repository.get_group(group_id)
        
        if not db_group:
            # Check if it's a static skill
            group = service.get_skill(group_id)
            if group:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="This is a static skill loaded from the filesystem. Static skills cannot be deleted via the API. To remove it, delete the .SKILL.md file from the skills/ directory.",
                )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Skill with ID '{group_id}' not found.",
            )
        
        # Check ownership - allow deletion if:
        # 1. User is the owner
        # 2. Skill has no owner (e.g., learned skills without explicit owner)
        # 3. User has edit permission
        if db_group.owner_user_id and db_group.owner_user_id != user_id:
            # Check if user has edit permission
            if not service.can_user_edit(group_id, user_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You do not have permission to delete this skill.",
                )
        
        deleted = service.delete_skill(group_id)
        if not deleted:
            log.error("%sUnexpected: Skill %s was in database but delete returned False", log_prefix, group_id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete skill from database.",
            )
        
        log.info("%sSuccessfully deleted skill %s", log_prefix, group_id)
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        log.exception("%sError deleting skill: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while deleting the skill.",
        )


# ============================================================================
# Version Endpoints
# ============================================================================

@router.get("/skills/{group_id}/versions", response_model=List[SkillVersionDTO], tags=["Skills"])
async def list_versions(
    group_id: str,
    request: FastAPIRequest,
    db: DBSession = Depends(get_db),
    user_id: UserId = Depends(get_user_id),
):
    """
    List all versions of a skill.
    
    Returns versions ordered by version number descending (newest first).
    """
    log_prefix = f"[GET /api/v1/skills/{group_id}/versions] "
    log.info("%sRequest from user %s", log_prefix, user_id)
    
    try:
        service = get_versioned_skill_service()
        if service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Skill learning service is not available",
            )
        
        group = service.get_skill(group_id)
        if not group:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Skill with ID '{group_id}' not found.",
            )
        
        versions = service.list_versions(group_id)
        return [_version_to_dto(v) for v in versions]
        
    except HTTPException:
        raise
    except Exception as e:
        log.exception("%sError listing versions: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while listing versions.",
        )


@router.get("/skills/{group_id}/versions/{version_id}", response_model=SkillVersionDTO, tags=["Skills"])
async def get_version(
    group_id: str,
    version_id: str,
    request: FastAPIRequest,
    db: DBSession = Depends(get_db),
    user_id: UserId = Depends(get_user_id),
):
    """
    Get a specific version of a skill.
    """
    log_prefix = f"[GET /api/v1/skills/{group_id}/versions/{version_id}] "
    log.info("%sRequest from user %s", log_prefix, user_id)
    
    try:
        service = get_versioned_skill_service()
        if service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Skill learning service is not available",
            )
        
        version = service.get_version(version_id)
        
        if not version or version.group_id != group_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Version '{version_id}' not found.",
            )
        
        return _version_to_dto(version)
        
    except HTTPException:
        raise
    except Exception as e:
        log.exception("%sError getting version: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while getting the version.",
        )


@router.post("/skills/{group_id}/versions", response_model=SkillVersionDTO, status_code=status.HTTP_201_CREATED, tags=["Skills"])
async def create_version(
    group_id: str,
    request: FastAPIRequest,
    payload: CreateVersionRequest,
    db: DBSession = Depends(get_db),
    user_id: UserId = Depends(get_user_id),
):
    """
    Create a new version of a skill.
    
    Only users with edit permission can create versions.
    """
    log_prefix = f"[POST /api/v1/skills/{group_id}/versions] "
    log.info("%sRequest from user %s", log_prefix, user_id)
    
    try:
        service = get_versioned_skill_service()
        if service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Skill learning service is not available",
            )
        
        # Check permission
        if not service.can_user_edit(group_id, user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to create versions for this skill.",
            )
        
        from ....services.skill_learning import AgentChainNode, AgentToolStep
        
        # Convert steps DTOs to entities
        tool_steps = None
        if payload.steps:
            tool_steps = [
                AgentToolStep(
                    step_type="tool_call",
                    agent_name=step.agent_name or "unknown",
                    tool_name=step.tool_name or "unknown",
                    action=step.description,
                    parameters_template=step.tool_parameters,
                    sequence_number=step.step_number,
                )
                for step in payload.steps
            ]
        
        # Convert agent chain DTOs to entities
        agent_chain = None
        if payload.agent_chain:
            agent_chain = [
                AgentChainNode(
                    agent_name=node.agent_name,
                    task_id=f"task-{node.order}",
                    role=node.role or "specialist",
                    tools_used=node.tools_used,
                )
                for node in payload.agent_chain
            ]
        
        version = service.create_version(
            group_id=group_id,
            description=payload.description,
            creation_reason=payload.creation_reason,
            created_by_user_id=user_id,
            markdown_content=payload.markdown_content,
            tool_steps=tool_steps,
            agent_chain=agent_chain,
            summary=payload.summary,
            set_as_production=payload.set_as_production,
        )
        
        return _version_to_dto(version)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except HTTPException:
        raise
    except Exception as e:
        log.exception("%sError creating version: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while creating the version.",
        )


@router.post("/skills/{group_id}/rollback", response_model=SkillGroupDTO, tags=["Skills"])
async def rollback_skill(
    group_id: str,
    request: FastAPIRequest,
    payload: RollbackRequest,
    db: DBSession = Depends(get_db),
    user_id: UserId = Depends(get_user_id),
):
    """
    Rollback a skill to a previous version.
    
    This changes the production version pointer without deleting any versions.
    """
    log_prefix = f"[POST /api/v1/skills/{group_id}/rollback] "
    log.info("%sRequest from user %s to rollback to %s", log_prefix, user_id, payload.version_id)
    
    try:
        service = get_versioned_skill_service()
        if service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Skill learning service is not available",
            )
        
        # Check permission
        if not service.can_user_edit(group_id, user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to rollback this skill.",
            )
        
        group = service.rollback_to_version(group_id, payload.version_id)
        return _group_to_dto(group)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except HTTPException:
        raise
    except Exception as e:
        log.exception("%sError rolling back skill: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while rolling back the skill.",
        )


# ============================================================================
# Sharing Endpoints
# ============================================================================

@router.post("/skills/{group_id}/share", response_model=dict, tags=["Skills"])
async def share_skill(
    group_id: str,
    request: FastAPIRequest,
    payload: ShareSkillRequest,
    db: DBSession = Depends(get_db),
    user_id: UserId = Depends(get_user_id),
):
    """
    Share a skill with another user.
    
    Only the skill owner can share a skill.
    """
    log_prefix = f"[POST /api/v1/skills/{group_id}/share] "
    log.info("%sRequest from user %s to share with %s", log_prefix, user_id, payload.target_user_id)
    
    try:
        service = get_versioned_skill_service()
        if service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Skill learning service is not available",
            )
        
        group = service.get_skill(group_id)
        
        if not group:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Skill with ID '{group_id}' not found.",
            )
        
        # Check ownership
        if group.owner_user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to share this skill.",
            )
        
        from ....services.skill_learning import SkillGroupRole
        
        role_map = {
            "viewer": SkillGroupRole.VIEWER,
            "editor": SkillGroupRole.EDITOR,
        }
        role = role_map.get(payload.role, SkillGroupRole.VIEWER)
        
        service.share_skill(
            group_id=group_id,
            shared_with_user_id=payload.target_user_id,
            shared_by_user_id=user_id,
            role=role,
        )
        
        return {"message": "Skill shared successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        log.exception("%sError sharing skill: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while sharing the skill.",
        )


@router.delete("/skills/{group_id}/share/{target_user_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Skills"])
async def unshare_skill(
    group_id: str,
    target_user_id: str,
    request: FastAPIRequest,
    db: DBSession = Depends(get_db),
    user_id: UserId = Depends(get_user_id),
):
    """
    Remove a user's access to a skill.
    
    Only the skill owner can unshare a skill.
    """
    log_prefix = f"[DELETE /api/v1/skills/{group_id}/share/{target_user_id}] "
    log.info("%sRequest from user %s", log_prefix, user_id)
    
    try:
        service = get_versioned_skill_service()
        if service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Skill learning service is not available",
            )
        
        group = service.get_skill(group_id)
        
        if not group:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Skill with ID '{group_id}' not found.",
            )
        
        # Check ownership
        if group.owner_user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to unshare this skill.",
            )
        
        service.unshare_skill(group_id, target_user_id)
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        log.exception("%sError unsharing skill: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while unsharing the skill.",
        )


# ============================================================================
# Export Endpoints
# ============================================================================

def _skill_to_markdown(group, version) -> str:
    """
    Convert a skill group and version to .SKILL.md format.
    """
    # Build frontmatter
    frontmatter = {
        "name": group.name,
        "description": group.description or version.description,
    }
    
    if version.summary:
        frontmatter["summary"] = version.summary
    
    # Add involved agents from agent_chain or version
    if version.involved_agents:
        frontmatter["involved_agents"] = version.involved_agents
    elif version.agent_chain:
        frontmatter["involved_agents"] = [node.agent_name for node in version.agent_chain]
    elif group.owner_agent_name:
        frontmatter["involved_agents"] = [group.owner_agent_name]
    
    if version.complexity_score:
        frontmatter["complexity_score"] = version.complexity_score
    
    # Build markdown content
    yaml_str = yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True, sort_keys=False)
    
    # Use existing markdown content or generate from steps
    if version.markdown_content:
        body = version.markdown_content
    else:
        # Generate markdown from steps
        body = f"# {group.name}\n\n{version.description}\n"
        
        if version.tool_steps:
            body += "\n## Steps\n\n"
            for step in version.tool_steps:
                step_num = step.sequence_number if hasattr(step, 'sequence_number') else 1
                action = step.action if hasattr(step, 'action') else ""
                body += f"{step_num}. {action}\n"
    
    return f"---\n{yaml_str}---\n\n{body}"


def _create_skill_zip(group, version, scripts: Dict[str, str] = None,
                      resources: Dict[str, Any] = None) -> BytesIO:
    """
    Create a Skill Package ZIP file from a skill group and version.
    
    Structure:
    skill-name/
    ├── SKILL.md              (instructions with YAML frontmatter)
    ├── scripts/              (executable code)
    └── resources/            (data files, templates)
    """
    zip_buffer = BytesIO()
    
    # Sanitize skill name for directory
    safe_name = re.sub(r'[^\w\-]', '-', group.name)
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        # Add SKILL.md (main skill file with YAML frontmatter)
        skill_md_content = _skill_to_markdown(group, version)
        zip_file.writestr(f'{safe_name}/SKILL.md', skill_md_content)
        
        # Add scripts (executable code)
        if scripts:
            for filename, content in scripts.items():
                zip_file.writestr(f'{safe_name}/scripts/{filename}', content)
        
        # Add resources (data files, templates)
        if resources:
            import base64
            for filename, content in resources.items():
                if isinstance(content, str):
                    # Check if it's base64 encoded binary
                    try:
                        # Try to decode as base64
                        decoded = base64.b64decode(content)
                        zip_file.writestr(f'{safe_name}/resources/{filename}', decoded)
                    except Exception:
                        # It's plain text
                        zip_file.writestr(f'{safe_name}/resources/{filename}', content)
                else:
                    zip_file.writestr(f'{safe_name}/resources/{filename}', content)
    
    zip_buffer.seek(0)
    return zip_buffer


@router.get("/skills/{group_id}/export", tags=["Skills"])
async def export_skill(
    group_id: str,
    request: FastAPIRequest,
    format: str = Query("zip", description="Export format: zip, json, or markdown"),
    version_id: Optional[str] = Query(None, description="Specific version to export (default: production)"),
    db: DBSession = Depends(get_db),
    user_id: UserId = Depends(get_user_id),
):
    """
    Export a skill.
    
    Formats:
    - zip: Skill Package ZIP format (folder with SKILL.md + scripts/ + resources/)
    - json: JSON export with metadata
    - markdown: SKILL.md file only
    """
    log_prefix = f"[GET /api/v1/skills/{group_id}/export] "
    log.info("%sRequest from user %s, format: %s", log_prefix, user_id, format)
    
    try:
        service = get_versioned_skill_service()
        if service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Skill learning service is not available",
            )
        
        group = service.get_skill(group_id, include_versions=True)
        
        if not group:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Skill with ID '{group_id}' not found.",
            )
        
        # Get the version to export
        version = None
        if version_id:
            version = service.get_version(version_id)
            if not version or version.group_id != group_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Version '{version_id}' not found.",
                )
        else:
            # Use production version
            version = group.production_version
            if not version:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No production version available for this skill.",
                )
        
        if format == "zip":
            # Export as Skill Package ZIP
            # Get bundled resources from storage if available
            scripts = None
            resources = None
            
            # Check if version has bundled resources URI
            resource_uri = getattr(version, 'bundled_resources_uri', None)
            if resource_uri:
                resource_storage = get_skill_resource_storage()
                if resource_storage:
                    try:
                        bundled = await resource_storage.load_resources(
                            skill_group_id=group_id,
                            version_id=version.id,
                        )
                        if bundled:
                            # Convert bytes to strings for ZIP creation
                            scripts = {k: v.decode('utf-8') for k, v in bundled.scripts.items()}
                            resources = {}
                            for k, v in bundled.resources.items():
                                try:
                                    resources[k] = v.decode('utf-8')
                                except UnicodeDecodeError:
                                    # Binary file - keep as bytes, will be base64 encoded
                                    resources[k] = base64.b64encode(v).decode('ascii')
                    except Exception as e:
                        log.warning(
                            "%sFailed to load bundled resources: %s",
                            log_prefix,
                            e,
                        )
            
            zip_buffer = _create_skill_zip(group, version, scripts, resources)
            safe_name = re.sub(r'[^\w\-]', '-', group.name)
            filename = f"{safe_name}.skill.zip"
            
            return StreamingResponse(
                zip_buffer,
                media_type="application/zip",
                headers={
                    "Content-Disposition": f'attachment; filename="{filename}"'
                }
            )
            
        elif format == "markdown":
            # Export as SKILL.md file only
            markdown_content = _skill_to_markdown(group, version)
            filename = f"{group.name}.SKILL.md"
            
            return StreamingResponse(
                BytesIO(markdown_content.encode("utf-8")),
                media_type="text/markdown",
                headers={
                    "Content-Disposition": f'attachment; filename="{filename}"'
                }
            )
        else:
            # Export as JSON
            group_dto = _group_to_dto(group)
            version_dto = _version_to_dto(version)
            export_data = {
                "version": "1.0",
                "exported_at": int(datetime.now(timezone.utc).timestamp() * 1000),
                "skill": group_dto.model_dump(),
                "production_version": version_dto.model_dump(),
            }
            return export_data
        
    except HTTPException:
        raise
    except Exception as e:
        log.exception("%sError exporting skill: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while exporting the skill.",
        )
