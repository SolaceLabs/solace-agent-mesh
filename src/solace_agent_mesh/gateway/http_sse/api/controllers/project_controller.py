"""
Project controller for handling HTTP requests in the presentation layer.
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
import logging

from ...dependencies import get_user_id
from ...application.services.project_service import ProjectService
from ...domain.entities.project_domain import ProjectCopyRequest
from ...dependencies import get_project_service
from ..dto.requests.project_requests import (
    CreateProjectRequest,
    UpdateProjectRequest,
    CopyProjectRequest,
)
from ..dto.responses.project_responses import (
    ProjectResponse,
    ProjectListResponse,
    GlobalProjectResponse,
    GlobalProjectListResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    name: str = Form(...),
    description: Optional[str] = Form(None),
    system_prompt: Optional[str] = Form(None),
    files: Optional[List[UploadFile]] = File(None),
    user_id: str = Depends(get_user_id),
    project_service: ProjectService = Depends(get_project_service),
):
    """
    Create a new project for the authenticated user.
    
    Args:
        name: Project name
        description: Optional project description
        system_prompt: Optional system prompt
        files: Optional list of files to attach to the project
        user_id: Authenticated user ID
        project_service: Injected project service
        
    Returns:
        ProjectResponse: The created project
    """
    try:
        logger.info(f"Creating project '{name}' for user {user_id}")

        if files:
            logger.info(f"Received {len(files)} files for project creation:")
            for file in files:
                logger.info(f"  - Filename: {file.filename}, Content-Type: {file.content_type}")
        else:
            logger.info("No files received for project creation.")

        project = await project_service.create_project(
            name=name,
            user_id=user_id,
            description=description,
            system_prompt=system_prompt,
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
        logger.warning(f"Validation error creating project: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.exception(f"Error creating project: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create project"
        )


@router.get("/projects", response_model=ProjectListResponse)
async def get_user_projects(
    user_id: str = Depends(get_user_id),
    project_service: ProjectService = Depends(get_project_service),
):
    """
    Get all projects owned by the authenticated user.
    
    Args:
        user_id: Authenticated user ID
        project_service: Injected project service
        
    Returns:
        ProjectListResponse: List of user's projects
    """
    try:
        logger.debug(f"Retrieving projects for user {user_id}")
        
        projects = project_service.get_user_projects(user_id)
        
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
        logger.exception(f"Error retrieving projects for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve projects"
        )


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    user_id: str = Depends(get_user_id),
    project_service: ProjectService = Depends(get_project_service),
):
    """
    Get a specific project by ID.
    
    Args:
        project_id: The project ID
        user_id: Authenticated user ID
        project_service: Injected project service
        
    Returns:
        ProjectResponse: The requested project
    """
    try:
        project = project_service.get_project(project_id, user_id)
        
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found or access denied"
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
    
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error retrieving project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve project"
        )


@router.put("/projects/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    request: UpdateProjectRequest,
    user_id: str = Depends(get_user_id),
    project_service: ProjectService = Depends(get_project_service),
):
    """
    Update a project's details.
    
    Args:
        project_id: The project ID
        request: Update request
        user_id: Authenticated user ID
        project_service: Injected project service
        
    Returns:
        ProjectResponse: The updated project
    """
    try:
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
                detail="Project not found or access denied"
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
        logger.warning(f"Validation error updating project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error updating project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update project"
        )


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: str,
    user_id: str = Depends(get_user_id),
    project_service: ProjectService = Depends(get_project_service),
):
    """
    Delete a project.
    
    Args:
        project_id: The project ID
        user_id: Authenticated user ID
        project_service: Injected project service
    """
    try:
        success = project_service.delete_project(project_id, user_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found or access denied"
            )
    
    except ValueError as e:
        logger.warning(f"Validation error deleting project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error deleting project {project_id}: {e}")
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
    
    Args:
        project_service: Injected project service
        
    Returns:
        GlobalProjectListResponse: List of global project templates
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
        logger.exception(f"Error retrieving global project templates: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve global project templates"
        )


@router.post("/projects/templates/{template_id}/copy", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def copy_project_from_template(
    template_id: str,
    request: CopyProjectRequest,
    user_id: str = Depends(get_user_id),
    project_service: ProjectService = Depends(get_project_service),
):
    """
    Copy a project from a global template.
    
    Args:
        template_id: The template project ID
        request: Copy request
        user_id: Authenticated user ID
        project_service: Injected project service
        
    Returns:
        ProjectResponse: The copied project
    """
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
        logger.warning(f"Validation error copying from template {template_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error copying from template {template_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to copy project from template"
        )
