"""
Project API controller using 3-tiered architecture.
"""

import json
from typing import List, Optional
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

from ..dependencies import get_project_service, get_sac_component, get_shared_artifact_service
from ..services.project_service import ProjectService, GLOBAL_PROJECT_USER_ID
from ..shared.auth_utils import get_current_user
from ....agent.utils.artifact_helpers import get_artifact_info_list
from ....common.a2a.types import ArtifactInfo

try:
    from google.adk.artifacts import BaseArtifactService
except ImportError:
    class BaseArtifactService:
        pass
from .dto.requests.project_requests import (
    CreateProjectRequest,
    UpdateProjectRequest,
    CopyProjectRequest,
    GetProjectRequest,
    GetProjectsRequest,
    DeleteProjectRequest,
    ProjectCopyRequest,
)
from .dto.responses.project_responses import (
    ProjectResponse,
    ProjectListResponse,
    GlobalProjectResponse,
    GlobalProjectListResponse,
)

router = APIRouter()


@router.post("/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    name: str = Form(...),
    description: Optional[str] = Form(None),
    system_prompt: Optional[str] = Form(None, alias="systemPrompt"),
    file_metadata: Optional[str] = Form(None, alias="fileMetadata"),
    files: Optional[List[UploadFile]] = File(None),
    user: dict = Depends(get_current_user),
    project_service: ProjectService = Depends(get_project_service),
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
            is_global=project.is_global,
            template_id=project.template_id,
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
                is_global=p.is_global,
                template_id=p.template_id,
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
            is_global=project.is_global,
            template_id=project.template_id,
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


@router.put("/projects/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    request: UpdateProjectRequest,
    user: dict = Depends(get_current_user),
    project_service: ProjectService = Depends(get_project_service),
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

        # Add user_id to the request
        request.user_id = user_id
        request.project_id = project_id

        project = project_service.update_project(
            project_id=request.project_id,
            user_id=request.user_id,
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
            is_global=project.is_global,
            template_id=project.template_id,
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


@router.get("/projects/templates/global", response_model=GlobalProjectListResponse)
async def get_global_project_templates(
    project_service: ProjectService = Depends(get_project_service),
):
    """
    Get all available global project templates.
    """
    try:
        projects = project_service.get_global_projects()
        
        # Get usage counts for each template
        template_responses = []
        for project in projects:
            usage_count = project_service.get_template_usage_count(project.id)
            template_responses.append(
                GlobalProjectResponse(
                    id=project.id,
                    name=project.name,
                    description=project.description,
                    system_prompt=project.system_prompt,
                    created_by_user_id=project.created_by_user_id,
                    created_at=project.created_at,
                    updated_at=project.updated_at,
                    usage_count=usage_count,
                )
            )
        
        return GlobalProjectListResponse(
            projects=template_responses,
            total=len(template_responses)
        )
    
    except Exception as e:
        log.error("Error retrieving global project templates: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve global project templates"
        )


@router.get("/projects/{project_id}/artifacts", response_model=list[ArtifactInfo])
async def get_project_artifacts(
    project_id: str,
    user: dict = Depends(get_current_user),
    project_service: ProjectService = Depends(get_project_service),
    artifact_service: BaseArtifactService = Depends(get_shared_artifact_service),
    component = Depends(get_sac_component),
):
    """
    Get all artifacts associated with a specific project.
    """
    user_id = user.get("id")
    log.info("User %s attempting to fetch artifacts for project %s", user_id, project_id)

    try:
        if (
            not project_id
            or project_id.strip() == ""
            or project_id in ["null", "undefined"]
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="Project not found."
            )

        # Verify user has access to the project
        project = project_service.get_project(project_id, user_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found."
            )

        if artifact_service is None:
            log.warning("Artifact service not available for project %s", project_id)
            return []

        # Determine the user_id for artifact storage based on project type
        storage_user_id = GLOBAL_PROJECT_USER_ID if project.is_global else project.user_id
        project_session_id = f"project-{project_id}"
        app_name = component.get_config("name", "WebUIBackendApp")

        log.info("Fetching artifacts for project %s (storage_user_id: %s, session_id: %s)", 
                project_id, storage_user_id, project_session_id)

        artifact_info_list = await get_artifact_info_list(
            artifact_service=artifact_service,
            app_name=app_name,
            user_id=storage_user_id,
            session_id=project_session_id,
        )

        log.info("Found %d artifacts for project %s", len(artifact_info_list), project_id)
        return artifact_info_list

    except HTTPException:
        raise
    except Exception as e:
        log.error("Error fetching artifacts for project %s for user %s: %s", project_id, user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve project artifacts"
        )


@router.get("/projects/{project_id}/artifacts/{filename}/versions", response_model=list[int])
async def get_project_artifact_versions(
    project_id: str,
    filename: str,
    user: dict = Depends(get_current_user),
    project_service: ProjectService = Depends(get_project_service),
    artifact_service: BaseArtifactService = Depends(get_shared_artifact_service),
    component = Depends(get_sac_component),
):
    """
    Get all available versions for a specific project artifact.
    """
    user_id = user.get("id")
    log.info("User %s attempting to fetch versions for artifact %s in project %s", user_id, filename, project_id)

    try:
        if (
            not project_id
            or project_id.strip() == ""
            or project_id in ["null", "undefined"]
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="Project not found."
            )

        # Verify user has access to the project
        project = project_service.get_project(project_id, user_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found."
            )

        if artifact_service is None:
            log.warning("Artifact service not available for project %s", project_id)
            return []

        # Determine the user_id for artifact storage based on project type
        storage_user_id = GLOBAL_PROJECT_USER_ID if project.is_global else project.user_id
        project_session_id = f"project-{project_id}"
        app_name = component.get_config("name", "WebUIBackendApp")

        log.info("Fetching versions for artifact %s in project %s (storage_user_id: %s, session_id: %s)", 
                filename, project_id, storage_user_id, project_session_id)

        if not hasattr(artifact_service, "list_versions"):
            log.warning("Configured artifact service does not support listing versions")
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Version listing not supported by the configured artifact service"
            )

        versions = await artifact_service.list_versions(
            app_name=app_name,
            user_id=storage_user_id,
            session_id=project_session_id,
            filename=filename,
        )

        log.info("Found %d versions for artifact %s in project %s", len(versions), filename, project_id)
        return versions

    except HTTPException:
        raise
    except Exception as e:
        log.error("Error fetching versions for artifact %s in project %s for user %s: %s", filename, project_id, user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve artifact versions"
        )


@router.get("/projects/{project_id}/artifacts/{filename}")
async def get_project_artifact_content(
    project_id: str,
    filename: str,
    user: dict = Depends(get_current_user),
    project_service: ProjectService = Depends(get_project_service),
    artifact_service: BaseArtifactService = Depends(get_shared_artifact_service),
    component = Depends(get_sac_component),
):
    """
    Get the latest version content of a specific project artifact.
    """
    user_id = user.get("id")
    log.info("User %s attempting to fetch content for artifact %s in project %s", user_id, filename, project_id)

    try:
        if (
            not project_id
            or project_id.strip() == ""
            or project_id in ["null", "undefined"]
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="Project not found."
            )

        # Verify user has access to the project
        project = project_service.get_project(project_id, user_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found."
            )

        if artifact_service is None:
            log.warning("Artifact service not available for project %s", project_id)
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Artifact service not configured"
            )

        # Determine the user_id for artifact storage based on project type
        storage_user_id = GLOBAL_PROJECT_USER_ID if project.is_global else project.user_id
        project_session_id = f"project-{project_id}"
        app_name = component.get_config("name", "WebUIBackendApp")

        log.info("Fetching content for artifact %s in project %s (storage_user_id: %s, session_id: %s)", 
                filename, project_id, storage_user_id, project_session_id)

        artifact_part = await artifact_service.load_artifact(
            app_name=app_name,
            user_id=storage_user_id,
            session_id=project_session_id,
            filename=filename,
        )

        if artifact_part is None or artifact_part.inline_data is None:
            log.warning("Artifact %s not found in project %s", filename, project_id)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Artifact '{filename}' not found in project"
            )

        data_bytes = artifact_part.inline_data.data
        mime_type = artifact_part.inline_data.mime_type or "application/octet-stream"
        
        log.info("Successfully loaded artifact %s from project %s (%d bytes, %s)", 
                filename, project_id, len(data_bytes), mime_type)

        from fastapi.responses import StreamingResponse
        from urllib.parse import quote
        import io

        filename_encoded = quote(filename)
        return StreamingResponse(
            io.BytesIO(data_bytes),
            media_type=mime_type,
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{filename_encoded}"
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        log.error("Error fetching content for artifact %s in project %s for user %s: %s", filename, project_id, user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve artifact content"
        )


@router.get("/projects/{project_id}/artifacts/{filename}/versions/{version}")
async def get_project_artifact_version_content(
    project_id: str,
    filename: str,
    version: int,
    user: dict = Depends(get_current_user),
    project_service: ProjectService = Depends(get_project_service),
    artifact_service: BaseArtifactService = Depends(get_shared_artifact_service),
    component = Depends(get_sac_component),
):
    """
    Get a specific version of a project artifact.
    """
    user_id = user.get("id")
    log.info("User %s attempting to fetch version %d of artifact %s in project %s", user_id, version, filename, project_id)

    try:
        if (
            not project_id
            or project_id.strip() == ""
            or project_id in ["null", "undefined"]
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="Project not found."
            )

        # Verify user has access to the project
        project = project_service.get_project(project_id, user_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found."
            )

        if artifact_service is None:
            log.warning("Artifact service not available for project %s", project_id)
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Artifact service not configured"
            )

        # Determine the user_id for artifact storage based on project type
        storage_user_id = GLOBAL_PROJECT_USER_ID if project.is_global else project.user_id
        project_session_id = f"project-{project_id}"
        app_name = component.get_config("name", "WebUIBackendApp")

        log.info("Fetching version %d of artifact %s in project %s (storage_user_id: %s, session_id: %s)", 
                version, filename, project_id, storage_user_id, project_session_id)

        artifact_part = await artifact_service.load_artifact(
            app_name=app_name,
            user_id=storage_user_id,
            session_id=project_session_id,
            filename=filename,
            version=version,
        )

        if artifact_part is None or artifact_part.inline_data is None:
            log.warning("Artifact %s version %d not found in project %s", filename, version, project_id)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Artifact '{filename}' version {version} not found in project"
            )

        data_bytes = artifact_part.inline_data.data
        mime_type = artifact_part.inline_data.mime_type or "application/octet-stream"
        
        log.info("Successfully loaded artifact %s version %d from project %s (%d bytes, %s)", 
                filename, version, project_id, len(data_bytes), mime_type)

        from fastapi.responses import StreamingResponse
        from urllib.parse import quote
        import io

        filename_encoded = quote(filename)
        return StreamingResponse(
            io.BytesIO(data_bytes),
            media_type=mime_type,
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{filename_encoded}"
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        log.error("Error fetching version %d of artifact %s in project %s for user %s: %s", version, filename, project_id, user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve artifact version content"
        )


@router.post("/projects/templates/{template_id}/copy", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def copy_project_from_template(
    template_id: str,
    request: CopyProjectRequest,
    user: dict = Depends(get_current_user),
    project_service: ProjectService = Depends(get_project_service),
):
    """
    Copy a project from a global template.
    """
    user_id = user.get("id")
    log.info("User %s attempting to copy from template %s", user_id, template_id)

    try:
        copy_request = ProjectCopyRequest(
            template_id=template_id,
            new_name=request.name,
            new_description=request.description,
            user_id=user_id
        )
        
        project = project_service.copy_project_from_template(copy_request)
        
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template not found or is not a global project"
            )

        log.info("Project copied successfully from template %s", template_id)
        
        return ProjectResponse(
            id=project.id,
            name=project.name,
            user_id=project.user_id,
            description=project.description,
            system_prompt=project.system_prompt,
            is_global=project.is_global,
            template_id=project.template_id,
            created_by_user_id=project.created_by_user_id,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )
    
    except ValueError as e:
        log.warning("Validation error copying from template %s: %s", template_id, e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        log.error("Error copying from template %s for user %s: %s", template_id, user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to copy project from template"
        )
