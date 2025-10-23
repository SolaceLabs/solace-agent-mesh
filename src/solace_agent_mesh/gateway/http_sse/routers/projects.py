"""
Project API controller using 3-tiered architecture.
"""

import json
from typing import List, Optional, Dict, Any
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    Request,
    Form,
    File,
    UploadFile,
)
from solace_ai_connector.common.log import log

from ..dependencies import get_project_service, get_sac_component, get_shared_artifact_service, get_api_config
from ..services.project_service import ProjectService
from ..shared.auth_utils import get_current_user
from ....agent.utils.artifact_helpers import get_artifact_info_list
from ....common.a2a.types import ArtifactInfo
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..component import WebUIBackendComponent

try:
    from google.adk.artifacts import BaseArtifactService
except ImportError:
    class BaseArtifactService:
        pass
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


@router.post("/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    name: str = Form(...),
    description: Optional[str] = Form(None),
    system_prompt: Optional[str] = Form(None, alias="systemPrompt"),
    file_metadata: Optional[str] = Form(None, alias="fileMetadata"),
    files: Optional[List[UploadFile]] = File(None),
    user: dict = Depends(get_current_user),
    project_service: ProjectService = Depends(get_project_service),
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
            name=request_dto.name,
            user_id=request_dto.user_id,
            description=request_dto.description,
            system_prompt=request_dto.system_prompt,
            files=files,
            file_metadata=parsed_file_metadata,
        )

        return ProjectResponse(
            id=project.id,
            name=project.name,
            user_id=project.user_id,
            description=project.description,
            system_prompt=project.system_prompt,
            created_by_user_id=project.created_by_user_id,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )
    
    except ValueError as e:
        log.warning(f"Validation error creating project: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        log.error("Error creating project for user %s: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create project"
        )


@router.get("/projects", response_model=ProjectListResponse)
async def get_user_projects(
    user: dict = Depends(get_current_user),
    project_service: ProjectService = Depends(get_project_service),
    _: None = Depends(check_projects_enabled),
):
    """
    Get all projects owned by the authenticated user.
    """
    user_id = user.get("id")
    log.info(f"Fetching projects for user_id: {user_id}")

    try:
        request_dto = GetProjectsRequest(user_id=user_id)

        projects = project_service.get_user_projects(request_dto.user_id)
        
        project_responses = [
            ProjectResponse(
                id=p.id,
                name=p.name,
                user_id=p.user_id,
                description=p.description,
                system_prompt=p.system_prompt,
                created_by_user_id=p.created_by_user_id,
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
            created_by_user_id=project.created_by_user_id,
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
    _: None = Depends(check_projects_enabled),
):
    """
    Get all artifacts for a specific project.
    """
    user_id = user.get("id")
    log.info("User %s attempting to fetch artifacts for project_id: %s", user_id, project_id)

    try:
        artifacts = await project_service.get_project_artifacts(
            project_id=project_id, user_id=user_id
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


@router.post("/projects/{project_id}/artifacts", status_code=status.HTTP_201_CREATED)
async def add_project_artifacts(
    project_id: str,
    files: List[UploadFile] = File(...),
    file_metadata: Optional[str] = Form(None, alias="fileMetadata"),
    user: dict = Depends(get_current_user),
    project_service: ProjectService = Depends(get_project_service),
    _: None = Depends(check_projects_enabled),
):
    """
    Add one or more artifacts to a project.
    """
    user_id = user.get("id")
    log.info(f"User {user_id} attempting to add artifacts to project {project_id}")

    try:
        parsed_file_metadata = {}
        if file_metadata:
            try:
                parsed_file_metadata = json.loads(file_metadata)
            except json.JSONDecodeError:
                log.warning(f"Could not parse file_metadata for project {project_id}, ignoring.")
                pass

        results = await project_service.add_artifacts_to_project(
            project_id=project_id,
            user_id=user_id,
            files=files,
            file_metadata=parsed_file_metadata
        )
        return results
    except ValueError as e:
        log.warning(f"Validation error adding artifacts to project {project_id}: {e}")
        # Could be 404 if project not found, or 400 if other validation fails
        if "not found" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
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


@router.delete("/projects/{project_id}/artifacts/{filename}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project_artifact(
    project_id: str,
    filename: str,
    user: dict = Depends(get_current_user),
    project_service: ProjectService = Depends(get_project_service),
    _: None = Depends(check_projects_enabled),
):
    """
    Delete an artifact from a project.
    """
    user_id = user.get("id")
    log.info(f"User {user_id} attempting to delete artifact '{filename}' from project {project_id}")

    try:
        success = await project_service.delete_artifact_from_project(
            project_id=project_id,
            user_id=user_id,
            filename=filename,
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found or access denied."
            )
        
        return
    except ValueError as e:
        log.warning(f"Validation error deleting artifact from project {project_id}: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
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

        project = project_service.update_project(
            project_id=project_id,
            user_id=user_id,
            name=request.name,
            description=request.description,
            system_prompt=request.system_prompt
        )
        
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
            created_by_user_id=project.created_by_user_id,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )
    
    except HTTPException:
        raise
    except ValueError as e:
        log.warning("Validation error updating project %s: %s", project_id, e)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        )
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
    _: None = Depends(check_projects_enabled),
):
    """
    Delete a project.
    """
    user_id = user.get("id")
    log.info("User %s attempting to delete project %s", user_id, project_id)

    try:
        request_dto = DeleteProjectRequest(project_id=project_id, user_id=user_id)

        success = project_service.delete_project(
            project_id=request_dto.project_id, 
            user_id=request_dto.user_id
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found."
            )

        log.info("Project %s deleted successfully", project_id)
    
    except HTTPException:
        raise
    except ValueError as e:
        log.warning("Validation error deleting project %s: %s", project_id, e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )
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
