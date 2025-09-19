"""
Project API controller using 3-tiered architecture.
"""

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

from ..dependencies import get_project_service
from ..services.project_service import ProjectService
from ..shared.auth_utils import get_current_user
from .dto.requests.project_requests import (
    CreateProjectRequest,
    UpdateProjectRequest,
    CopyProjectRequest,
    GetProjectRequest,
    GetProjectsRequest,
    DeleteProjectRequest,
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
    system_prompt: Optional[str] = Form(None),
    files: Optional[List[UploadFile]] = File(None),
    user: dict = Depends(get_current_user),
    project_service: ProjectService = Depends(get_project_service),
):
    """
    Create a new project for the authenticated user.
    """
    user_id = user.get("id")
    log.info(f"Creating project '{name}' for user {user_id}")

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
            user_id=user_id
        )

        project = await project_service.create_project(
            name=request_dto.name,
            user_id=request_dto.user_id,
            description=request_dto.description,
            system_prompt=request_dto.system_prompt,
            files=files,
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