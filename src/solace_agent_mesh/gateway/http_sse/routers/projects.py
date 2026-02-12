"""
Project API controller using 3-tiered architecture.
"""
from __future__ import annotations

import asyncio
import json
from typing import List, Optional, Dict, Any
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    Form,
    File,
    UploadFile,
    Query,
    Response,
)
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from solace_ai_connector.common.log import log

from ..dependencies import (
    get_project_service,
    get_sac_component,
    get_api_config,
    get_db,
    get_indexing_task_service,
)
from ..services.project_service import ProjectService
from solace_agent_mesh.shared.api.auth_utils import get_current_user
from solace_agent_mesh.shared.auth.dependencies import ValidatedUserConfig
from ....common.a2a.types import ArtifactInfo
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..component import WebUIBackendComponent

from .dto.requests.project_requests import (
    CreateProjectRequest,
    UpdateProjectRequest,
    GetProjectRequest,
    GetProjectsRequest,
    DeleteProjectRequest,
)
from .dto.responses.project_responses import (
    ProjectResponse,
    ProjectListResponse,
)
from .dto.project_dto import (
    ProjectImportOptions,
    ProjectImportResponse,
)

router = APIRouter()


def check_projects_enabled(
    component: "WebUIBackendComponent" = Depends(get_sac_component),
    api_config: Dict[str, Any] = Depends(get_api_config),
) -> None:
    """
    Dependency to check if projects feature is enabled.
    Raises HTTPException if projects are disabled.
    """
    # Check if persistence is enabled (required for projects)
    persistence_enabled = api_config.get("persistence_enabled", False)
    if not persistence_enabled:
        log.warning("Projects API called but persistence is not enabled")
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Projects feature requires persistence to be enabled. Please configure session_service.type as 'sql'."
        )
    
    # Check explicit projects config
    projects_config = component.get_config("projects", {})
    if isinstance(projects_config, dict):
        projects_explicitly_enabled = projects_config.get("enabled", True)
        if not projects_explicitly_enabled:
            log.warning("Projects API called but projects are explicitly disabled in config")
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Projects feature is disabled. Please enable it in the configuration."
            )
    
    # Check frontend_feature_enablement override
    feature_flags = component.get_config("frontend_feature_enablement", {})
    if "projects" in feature_flags:
        projects_flag = feature_flags.get("projects", True)
        if not projects_flag:
            log.warning("Projects API called but projects are disabled via feature flag")
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Projects feature is disabled via feature flag."
            )

def check_project_indexing_enabled(
    component: "WebUIBackendComponent" = Depends(get_sac_component)
) -> bool:
    """
    Dependency to check if project indexing feature is enabled.
    Raises HTTPException if project indexing is disabled.
    """

    # Check explicit project_indexing config
    project_indexing_config = component.get_config("project_indexing", {})
    if isinstance(project_indexing_config, dict):
        indexing_explicitly_enabled = project_indexing_config.get("enabled", False)
        if not indexing_explicitly_enabled:
            log.info("Project indexing is explicitly disabled in config")
            return False
        else:
            log.info("Project indexing is explicitly enabled in config")
            return True
    return False

@router.post("/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    name: str = Form(...),
    description: Optional[str] = Form(None),
    system_prompt: Optional[str] = Form(None, alias="systemPrompt"),
    default_agent_id: Optional[str] = Form(None, alias="defaultAgentId"),
    file_metadata: Optional[str] = Form(None, alias="fileMetadata"),
    files: Optional[List[UploadFile]] = File(None),
    user: dict = Depends(get_current_user),
    project_service: ProjectService = Depends(get_project_service),
    db: Session = Depends(get_db),
    _: None = Depends(check_projects_enabled),
):
    """
    Create a new project for the authenticated user.
    """
    user_id = user.get("id")
    log.info(f"Creating project '{name}' for user {user_id}")
    log.info(f"Received system_prompt: {system_prompt}")
    log.info(f"Received file_metadata: {file_metadata}")

    try:
        if files:
            log.info(f"Received {len(files)} files for project creation:")
            for file in files:
                log.info(f"  - Filename: {file.filename}, Content-Type: {file.content_type}")
        else:
            log.info("No files received for project creation.")

        request_dto = CreateProjectRequest(
            name=name,
            description=description,
            system_prompt=system_prompt,
            default_agent_id=default_agent_id,
            file_metadata=file_metadata,
            user_id=user_id
        )

        parsed_file_metadata = {}
        if request_dto.file_metadata:
            try:
                parsed_file_metadata = json.loads(request_dto.file_metadata)
            except json.JSONDecodeError:
                log.warning("Could not parse file_metadata JSON string, ignoring.")
                pass

        project = await project_service.create_project(
            db=db,
            name=request_dto.name,
            user_id=request_dto.user_id,
            description=request_dto.description,
            system_prompt=request_dto.system_prompt,
            default_agent_id=request_dto.default_agent_id,
            files=files,
            file_metadata=parsed_file_metadata,
        )

        return ProjectResponse(
            id=project.id,
            name=project.name,
            user_id=project.user_id,
            description=project.description,
            system_prompt=project.system_prompt,
            default_agent_id=project.default_agent_id,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )
    
    except ValueError as e:
        error_msg = str(e)
        log.warning(f"Validation error creating project: {error_msg}")
        # Check if this is a file size error
        if "exceeds maximum" in error_msg.lower() and "bytes" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=error_msg
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )
    except Exception as e:
        log.error("Error creating project for user %s: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create project"
        )


@router.get("/projects", response_model=ProjectListResponse)
async def get_user_projects(
    include_artifact_count: bool = False,
    user: dict = Depends(get_current_user),
    project_service: ProjectService = Depends(get_project_service),
    db: Session = Depends(get_db),
    _: None = Depends(check_projects_enabled),
):
    """
    Get all projects owned by the authenticated user.
    
    Args:
        include_artifact_count: If True, includes artifact count for each project
    """
    user_id = user.get("id")
    log.info(f"Fetching projects for user_id: {user_id}, include_artifact_count: {include_artifact_count}")

    try:
        request_dto = GetProjectsRequest(user_id=user_id)

        if include_artifact_count:
            # Fetch projects with artifact counts
            projects_with_counts = await project_service.get_user_projects_with_counts(db, request_dto.user_id)
            
            project_responses = [
                ProjectResponse(
                    id=p.id,
                    name=p.name,
                    user_id=p.user_id,
                    description=p.description,
                    system_prompt=p.system_prompt,
                    default_agent_id=p.default_agent_id,
                    artifact_count=count,
                    created_at=p.created_at,
                    updated_at=p.updated_at,
                )
                for p, count in projects_with_counts
            ]
        else:
            # Fetch projects without counts (faster)
            projects = project_service.get_user_projects(db, request_dto.user_id)
            
            project_responses = [
                ProjectResponse(
                    id=p.id,
                    name=p.name,
                    user_id=p.user_id,
                    description=p.description,
                    system_prompt=p.system_prompt,
                    default_agent_id=p.default_agent_id,
                    created_at=p.created_at,
                    updated_at=p.updated_at,
                )
                for p in projects
            ]
        
        return ProjectListResponse(
            projects=project_responses,
            total=len(project_responses)
        )
    
    except Exception as e:
        log.error("Error fetching projects for user %s: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve projects"
        )


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    user: dict = Depends(get_current_user),
    project_service: ProjectService = Depends(get_project_service),
    db: Session = Depends(get_db),
    _: None = Depends(check_projects_enabled),
):
    """
    Get a specific project by ID.
    """
    user_id = user.get("id")
    log.info("User %s attempting to fetch project_id: %s", user_id, project_id)

    try:
        if (
            not project_id
            or project_id.strip() == ""
            or project_id in ["null", "undefined"]
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Project not found."
            )

        request_dto = GetProjectRequest(project_id=project_id, user_id=user_id)

        project = project_service.get_project(
            db=db,
            project_id=request_dto.project_id,
            user_id=request_dto.user_id
        )
        
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found."
            )

        log.info("User %s authorized. Fetching project_id: %s", user_id, project_id)
        
        return ProjectResponse(
            id=project.id,
            name=project.name,
            user_id=project.user_id,
            description=project.description,
            system_prompt=project.system_prompt,
            default_agent_id=project.default_agent_id,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )
    
    except HTTPException:
        raise
    except Exception as e:
        log.error(
            "Error fetching project %s for user %s: %s",
            project_id,
            user_id,
            e,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve project"
        )


@router.get("/projects/{project_id}/artifacts", response_model=List[ArtifactInfo])
async def get_project_artifacts(
    project_id: str,
    user: dict = Depends(get_current_user),
    project_service: ProjectService = Depends(get_project_service),
    db: Session = Depends(get_db),
    _: None = Depends(check_projects_enabled),
):
    """
    Get all artifacts for a specific project.
    """
    user_id = user.get("id")
    log.info("User %s attempting to fetch artifacts for project_id: %s", user_id, project_id)

    try:
        artifacts = await project_service.get_project_artifacts(
            db=db, project_id=project_id, user_id=user_id
        )
        return artifacts
    except ValueError as e:
        log.warning(f"Validation error getting project artifacts: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        log.error(
            "Error fetching artifacts for project %s for user %s: %s",
            project_id,
            user_id,
            e,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve project artifacts"
        )


@router.post("/projects/{project_id}/artifacts")
async def add_project_artifacts(
    response: Response,
    project_id: str,
    files: List[UploadFile] = File(...),
    file_metadata: Optional[str] = Form(None, alias="fileMetadata"),
    async_mode: bool = Query(True, alias="async", description="Process conversion/indexing asynchronously with SSE"),
    user: dict = Depends(get_current_user),
    project_service: ProjectService = Depends(get_project_service),
    indexing_task_service = Depends(get_indexing_task_service),
    db: Session = Depends(get_db),
    _: None = Depends(check_projects_enabled),
    indexing_enabled: bool = Depends(check_project_indexing_enabled)
):
    """
    Add one or more artifacts to a project.

    With indexing enabled, converts PDF/DOCX/PPTX to text and builds BM25 index.

    Query Parameters:
        async: If true, process asynchronously with SSE progress (default: false for now)
               If false, block until processing completes

    Returns:
        200 OK: Files uploaded, processing complete (or not needed)
        202 Accepted: Files uploaded, processing in background (check SSE-Location header)
    """
    user_id = user.get("id")
    log.info(f"User {user_id} adding artifacts to project {project_id} (indexing={indexing_enabled}, async={async_mode})")

    try:
        parsed_file_metadata = {}
        if file_metadata:
            try:
                parsed_file_metadata = json.loads(file_metadata)
            except json.JSONDecodeError:
                log.warning(f"Could not parse file_metadata for project {project_id}, ignoring.")
                pass

        # Step 1: Save files immediately (fast ~100ms, no processing yet)
        results = await project_service.add_artifacts_to_project(
            db=db,
            project_id=project_id,
            user_id=user_id,
            files=files,
            file_metadata=parsed_file_metadata,
            indexing_enabled=False  # Don't process yet - we'll handle async/sync separately
        )

        # Step 2: Check if background processing is needed
        # Feature flag check (highest priority)
        if not indexing_enabled:
            # Feature disabled - return immediately
            response.status_code = status.HTTP_201_CREATED
            return {"uploaded": results}

        # Step 3: Classify files to determine if work is needed
        project = project_service.get_project(db, project_id, user_id)
        needs_conversion = []
        is_text_based = []

        # Classify files by type (using MIME type)
        for file in files:
            if project_service._should_convert_file(file.content_type, file.filename):
                # Find version from results
                file_result = next((r for r in results if r.get('data_filename') == file.filename), None)
                if file_result:
                    needs_conversion.append((file.filename, file_result['data_version'], file.content_type))
            elif project_service._is_text_file(file.content_type, file.filename):
                file_result = next((r for r in results if r.get('data_filename') == file.filename), None)
                if file_result:
                    is_text_based.append((file.filename, file_result['data_version']))

        # Step 4: Check if any processing is needed
        needs_processing = (len(needs_conversion) > 0 or len(is_text_based) > 0)

        if not needs_processing:
            # No work needed - return immediately
            response.status_code = status.HTTP_201_CREATED
            return {"uploaded": results}

        # Step 5: Processing is needed - check async mode
        if async_mode:
            # Async SSE mode - return 202 immediately, process in background
            task_id = indexing_task_service.create_task_id("upload", project_id)

            # Set SSE header
            response.status_code = status.HTTP_202_ACCEPTED
            response.headers["SSE-Location"] = f"/api/v1/sse/subscribe/{task_id}"

            # Start background task (fire and forget)
            loop = asyncio.get_event_loop()
            loop.create_task(
                indexing_task_service.convert_and_index_upload_async(
                    task_id=task_id,
                    project=project,
                    files_to_convert=needs_conversion,
                    is_text_based=is_text_based
                )
            )

            log.info(f"Started background indexing task {task_id} for project {project_id}")

            return {
                "uploaded": results
            }
        else:
            # Synchronous blocking mode - process now
            log.info(f"Processing synchronously for project {project_id}")

            # Convert files
            conversion_results = []
            if needs_conversion:
                conversion_results = await project_service._convert_project_artifacts(
                    project, needs_conversion, indexing_enabled=True
                )

            # Rebuild index
            index_result = None
            if is_text_based or conversion_results:
                index_result = await project_service._rebuild_project_index(
                    project, indexing_enabled=True
                )

            response.status_code = status.HTTP_201_CREATED
            return {
                "uploaded": results,
                "converted": conversion_results,
                "index": {
                    "version": index_result.get('data_version') if index_result else None,
                    "status": index_result.get('status') if index_result else None
                } if index_result else None
            }
    except ValueError as e:
        error_msg = str(e)
        log.warning(f"Validation error adding artifacts to project {project_id}: {error_msg}")
        # Could be 404 if project not found, 413 if file too large, or 400 if other validation fails
        if "not found" in error_msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg)
        if "exceeds maximum" in error_msg.lower() and "bytes" in error_msg.lower():
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=error_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
    except Exception as e:
        log.error(
            "Error adding artifacts to project %s for user %s: %s",
            project_id,
            user_id,
            e,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add artifacts to project"
        )


@router.patch("/projects/{project_id}/artifacts/{filename}", status_code=status.HTTP_200_OK)
async def update_project_artifact_metadata(
    project_id: str,
    filename: str,
    description: Optional[str] = Form(None),
    user: dict = Depends(get_current_user),
    project_service: ProjectService = Depends(get_project_service),
    db: Session = Depends(get_db),
    _: None = Depends(check_projects_enabled),
):
    """
    Update metadata (description) for a project artifact.
    """
    user_id = user.get("id")
    log.info(f"User {user_id} attempting to update metadata for artifact '{filename}' in project {project_id}")

    try:
        success = await project_service.update_artifact_metadata(
            db=db,
            project_id=project_id,
            user_id=user_id,
            filename=filename,
            description=description,
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project or artifact not found, or access denied."
            )
        
        return {"message": "Artifact metadata updated successfully"}
    except ValueError as e:
        error_msg = str(e)
        # Check if this is a permission error (403) or validation error (400)
        if "permission denied" in error_msg.lower():
            log.warning(f"Permission denied updating artifact metadata in project {project_id}: {error_msg}")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)
        else:
            log.warning(f"Validation error updating artifact metadata in project {project_id}: {error_msg}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
    except HTTPException:
        raise
    except Exception as e:
        log.error(
            "Error updating metadata for artifact '%s' in project %s for user %s: %s",
            filename,
            project_id,
            user_id,
            e,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update artifact metadata"
        )


@router.delete("/projects/{project_id}/artifacts/{filename}")
async def delete_project_artifact(
    response: Response,
    project_id: str,
    filename: str,
    async_mode: bool = Query(True, alias="async", description="Rebuild index asynchronously with SSE"),
    user: dict = Depends(get_current_user),
    project_service: ProjectService = Depends(get_project_service),
    indexing_task_service = Depends(get_indexing_task_service),
    db: Session = Depends(get_db),
    _: None = Depends(check_projects_enabled),
    indexing_enabled: bool = Depends(check_project_indexing_enabled)
):
    """
    Delete an artifact from a project.

    With indexing enabled, may trigger async index rebuild.

    Query Parameters:
        async: If true, rebuild index asynchronously with SSE (default: false for now)

    Returns:
        204 No Content: File deleted, no indexing needed
        202 Accepted: File deleted, index rebuild in background (check SSE-Location header)
    """
    user_id = user.get("id")
    log.info(f"User {user_id} deleting artifact '{filename}' from project {project_id} (indexing={indexing_enabled}, async={async_mode})")

    try:
        # Step 1: Get file type before deletion (if indexing enabled)
        project = None
        mime_type = ""
        was_text_file = False
        was_convertible = False

        if indexing_enabled:
            project = project_service.get_project(db, project_id, user_id)
            if not project:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Project not found or access denied."
                )

            # Load metadata to determine file type
            try:
                from ....agent.utils.artifact_helpers import load_artifact_content_or_metadata
                metadata_result = await load_artifact_content_or_metadata(
                    artifact_service=project_service.artifact_service,
                    app_name=project_service.app_name,
                    user_id=project.user_id,
                    session_id=f"project-{project.id}",
                    filename=filename,
                    version="latest",
                    load_metadata_only=True
                )
                mime_type = metadata_result.get("metadata", {}).get("mime_type", "")
                was_text_file = project_service._is_text_file(mime_type, filename)
                was_convertible = project_service._should_convert_file(mime_type, filename)
            except Exception as e:
                log.warning(f"Could not load metadata for {filename}: {e}")

        # Step 2: Delete original file
        if not project:
            project = project_service.get_project(db, project_id, user_id)
            if not project:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Project not found or access denied."
                )

        storage_session_id = f"project-{project.id}"

        # Delete original file (all versions)
        await project_service.artifact_service.delete_artifact(
            app_name=project_service.app_name,
            user_id=project.user_id,
            session_id=storage_session_id,
            filename=filename,
        )
        log.info(f"Deleted all versions of {filename}")

        # Step 3: Delete converted file if this was convertible (PDF/DOCX/PPTX)
        if indexing_enabled and was_convertible:
            converted_filename = f"{filename}.converted.txt"
            try:
                await project_service.artifact_service.delete_artifact(
                    app_name=project_service.app_name,
                    user_id=project.user_id,
                    session_id=storage_session_id,
                    filename=converted_filename,
                )
                log.info(f"Deleted all versions of converted file: {converted_filename}")
            except Exception as e:
                log.debug(f"No converted file to delete: {e}")

        # Step 4: Check if index rebuild is needed
        needs_index_rebuild = indexing_enabled and (was_text_file or was_convertible)

        if not needs_index_rebuild:
            # No index rebuild needed - return 204 immediately
            response.status_code = status.HTTP_204_NO_CONTENT
            return

        # Step 5: Index rebuild is needed - check async mode
        if not project:
            project = project_service.get_project(db, project_id, user_id)

        if async_mode:
            # Async SSE mode - return 202, rebuild in background
            task_id = indexing_task_service.create_task_id("delete", project_id)

            # Set SSE header
            response.status_code = status.HTTP_202_ACCEPTED
            response.headers["SSE-Location"] = f"/api/v1/sse/subscribe/{task_id}"

            # Start background task (fire and forget)
            loop = asyncio.get_event_loop()
            loop.create_task(
                indexing_task_service.rebuild_index_after_delete_async(
                    task_id=task_id,
                    project=project
                )
            )

            log.info(f"Started background index rebuild task {task_id} after deleting {filename}")

            return {
                "deleted": True,
                "filename": filename
            }
        else:
            # Synchronous blocking mode - rebuild now
            log.info(f"Rebuilding index synchronously after deleting {filename}")

            await project_service._rebuild_project_index(
                project, indexing_enabled=True
            )

            response.status_code = status.HTTP_204_NO_CONTENT
            return
    except ValueError as e:
        error_msg = str(e)
        # Check if this is a permission error (403) or validation error (400)
        if "permission denied" in error_msg.lower():
            log.warning(f"Permission denied deleting artifact from project {project_id}: {error_msg}")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)
        else:
            log.warning(f"Validation error deleting artifact from project {project_id}: {error_msg}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
    except HTTPException:
        raise
    except Exception as e:
        log.error(
            "Error deleting artifact '%s' from project %s for user %s: %s",
            filename,
            project_id,
            user_id,
            e,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete artifact from project"
        )


@router.put("/projects/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    request: UpdateProjectRequest,
    user: dict = Depends(get_current_user),
    project_service: ProjectService = Depends(get_project_service),
    db: Session = Depends(get_db),
    _: None = Depends(check_projects_enabled),
):
    """
    Update a project's details.
    """
    user_id = user.get("id")
    log.info("User %s attempting to update project %s", user_id, project_id)

    try:
        if (
            not project_id
            or project_id.strip() == ""
            or project_id in ["null", "undefined"]
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Project not found."
            )

        update_fields = request.model_dump(exclude_unset=True, by_alias=False)
        
        # Pass only explicitly set fields to the service
        kwargs = {
            'db': db,
            'project_id': project_id,
            'user_id': user_id,
            'name': update_fields.get('name', ...),
            'description': update_fields.get('description', ...),
            'system_prompt': update_fields.get('system_prompt', ...),
            'default_agent_id': update_fields.get('default_agent_id', ...),
        }

        project = project_service.update_project(**kwargs)

        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found."
            )

        log.info("Project %s updated successfully", project_id)

        return ProjectResponse(
            id=project.id,
            name=project.name,
            user_id=project.user_id,
            description=project.description,
            system_prompt=project.system_prompt,
            default_agent_id=project.default_agent_id,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )

    except HTTPException:
        raise
    except ValueError as e:
        error_msg = str(e)
        # Check if this is a permission error (403) or validation error (422)
        if "permission denied" in error_msg.lower():
            log.warning("Permission denied updating project %s: %s", project_id, error_msg)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)
        else:
            log.warning("Validation error updating project %s: %s", project_id, error_msg)
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=error_msg)

    except Exception as e:
        log.error(
            "Error updating project %s for user %s: %s",
            project_id,
            user_id,
            e,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update project"
        )


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: str,
    user: dict = Depends(get_current_user),
    project_service: ProjectService = Depends(get_project_service),
    db: Session = Depends(get_db),
    _: None = Depends(check_projects_enabled),
):
    """
    Soft delete a project (marks as deleted without removing from database).
    """
    user_id = user.get("id")
    log.info("User %s attempting to soft delete project %s", user_id, project_id)

    try:
        request_dto = DeleteProjectRequest(project_id=project_id, user_id=user_id)

        success = project_service.soft_delete_project(
            db=db,
            project_id=request_dto.project_id,
            user_id=request_dto.user_id
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found."
            )

        log.info("Project %s soft deleted successfully", project_id)

    except HTTPException:
        raise
    except ValueError as e:
        error_msg = str(e)
        # Check if this is a permission error (403) or validation error (400)
        if "permission denied" in error_msg.lower():
            log.warning("Permission denied deleting project %s: %s", project_id, error_msg)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)
        else:
            log.warning("Validation error deleting project %s: %s", project_id, error_msg)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)

    except Exception as e:
        log.error(
            "Error deleting project %s for user %s: %s",
            project_id,
            user_id,
            e,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete project"
        )


@router.get("/projects/{project_id}/export")
async def export_project(
    project_id: str,
    user: dict = Depends(get_current_user),
    project_service: ProjectService = Depends(get_project_service),
    db: Session = Depends(get_db),
    _: None = Depends(check_projects_enabled),
):
    """
    Export project as ZIP containing:
    - project.json (metadata)
    - artifacts/ (all project files)
    
    Excludes: chat history, sessions
    """
    user_id = user.get("id")
    log.info(f"User {user_id} exporting project {project_id}")
    
    try:
        # Create ZIP file
        zip_buffer = await project_service.export_project_as_zip(
            db=db,
            project_id=project_id,
            user_id=user_id
        )
        
        # Get project for filename
        project = project_service.get_project(db, project_id, user_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        
        # Create safe filename
        safe_name = project.name.replace(' ', '-').replace('/', '-')
        filename = f"project-{safe_name}-{project_id[:8]}.zip"
        
        log.info(f"Project {project_id} exported successfully")
        
        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
    
    except ValueError as e:
        log.warning(f"Validation error exporting project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        log.error(f"Error exporting project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export project"
        )


@router.post("/projects/import", response_model=ProjectImportResponse)
async def import_project(
    response: Response,
    file: UploadFile = File(...),
    options: Optional[str] = Form(None),
    async_mode: bool = Query(True, alias="async", description="Process conversion/indexing asynchronously with SSE"),
    user: dict = Depends(get_current_user),
    project_service: ProjectService = Depends(get_project_service),
    indexing_task_service = Depends(get_indexing_task_service),
    db: Session = Depends(get_db),
    _: None = Depends(check_projects_enabled),
    indexing_enabled: bool = Depends(check_project_indexing_enabled)
):
    """
    Import project from ZIP file.
    Handles name conflicts automatically.

    Query Parameters:
        async: If true, process conversion/indexing asynchronously with SSE (default: false for now)

    Returns:
        ProjectImportResponse (with task info if async mode)
    """
    user_id = user.get("id")
    log.info(f"User {user_id} importing project from {file.filename} (indexing={indexing_enabled}, async={async_mode})")
    
    try:
        # Validate file type
        if not file.filename.endswith('.zip'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must be a ZIP archive"
            )
        
        # Parse options
        import_options = ProjectImportOptions()
        if options:
            try:
                options_dict = json.loads(options)
                import_options = ProjectImportOptions(**options_dict)
            except (json.JSONDecodeError, ValueError) as e:
                log.warning(f"Invalid import options: {e}")
        
        # Step 1: Import project files immediately (fast ~1-2s, no conversion/indexing yet)
        project, artifacts_count, warnings = await project_service.import_project_from_zip(
            db=db,
            zip_file=file,
            user_id=user_id,
            preserve_name=import_options.preserve_name,
            custom_name=import_options.custom_name,
            indexing_enabled=False  # Don't process yet - we'll handle async/sync separately
        )

        log.info(
            f"Project imported successfully: {project.id} with {artifacts_count} artifacts"
        )

        # CRITICAL: Commit the database transaction NOW before async processing
        # This ensures project is saved even if post-processing fails
        db.commit()
        log.debug("Database transaction committed - project and artifacts saved")

        # Step 2: Check if background processing is needed
        # Feature flag check (highest priority)
        if not indexing_enabled:
            # Feature disabled - return immediately
            return ProjectImportResponse(
                project_id=project.id,
                name=project.name,
                artifacts_imported=artifacts_count,
                warnings=warnings,
            )

        # Step 3: Get list of imported artifacts to classify
        # CRITICAL: Wrap in try/except to prevent exceptions from affecting the import
        # Import is already committed, so we just skip indexing if this fails
        try:
            artifacts = await project_service.get_project_artifacts(db, project.id, user_id)
        except Exception as e:
            log.error(f"Failed to get artifacts for classification after import: {e}")
            # Import succeeded, but classification failed - return success anyway
            return ProjectImportResponse(
                project_id=project.id,
                name=project.name,
                artifacts_imported=artifacts_count,
                warnings=warnings + ["Post-import indexing skipped due to classification error"],
            )

        needs_conversion = []
        is_text_based = []

        for artifact in artifacts:
            if project_service._should_convert_file(artifact.mime_type, artifact.filename):
                needs_conversion.append((artifact.filename, artifact.version, artifact.mime_type))
            elif project_service._is_text_file(artifact.mime_type, artifact.filename):
                is_text_based.append((artifact.filename, artifact.version))

        # Step 4: Check if any processing is needed
        needs_processing = (len(needs_conversion) > 0 or len(is_text_based) > 0)

        if not needs_processing:
            # No work needed - return immediately
            return ProjectImportResponse(
                project_id=project.id,
                name=project.name,
                artifacts_imported=artifacts_count,
                warnings=warnings,
            )

        # Step 5: Processing is needed - check async mode
        if async_mode:
            # Async SSE mode - return 202 immediately, process in background
            task_id = indexing_task_service.create_task_id("import", project.id)

            # Set SSE header
            response.status_code = status.HTTP_202_ACCEPTED
            response.headers["SSE-Location"] = f"/api/v1/sse/subscribe/{task_id}"

            # Start background task (fire and forget)
            loop = asyncio.get_event_loop()
            loop.create_task(
                indexing_task_service.convert_and_index_import_async(
                    task_id=task_id,
                    project=project,
                    files_to_convert=needs_conversion,
                    is_text_based=is_text_based
                )
            )

            log.info(f"Started background indexing task {task_id} for imported project {project.id}")

            # Return response (status code changed to 202)
            return ProjectImportResponse(
                project_id=project.id,
                name=project.name,
                artifacts_imported=artifacts_count,
                warnings=warnings,
            )
        else:
            # Synchronous blocking mode - process now
            log.info(f"Processing imported project {project.id} synchronously")

            # Convert files
            conversion_results = []
            if needs_conversion:
                conversion_results = await project_service._convert_project_artifacts(
                    project, needs_conversion, indexing_enabled=True
                )

            # Rebuild index
            if is_text_based or conversion_results:
                await project_service._rebuild_project_index(
                    project, indexing_enabled=True
                )

            return ProjectImportResponse(
                project_id=project.id,
                name=project.name,
                artifacts_imported=artifacts_count,
                warnings=warnings,
            )
    
    except ValueError as e:
        error_msg = str(e)
        log.warning(f"Validation error importing project: {error_msg}")
        # Check if this is a file size error 
        if "exceeds maximum" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=error_msg
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )
    except Exception as e:
        log.error(f"Error importing project: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to import project"
        )
