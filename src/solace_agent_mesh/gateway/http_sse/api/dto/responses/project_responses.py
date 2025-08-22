"""
Response DTOs for project-related API endpoints.
"""

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class ProjectResponse(BaseModel):
    """Response containing project information."""
    
    id: str
    name: str
    user_id: str
    description: Optional[str] = None
    is_global: bool = False
    template_id: Optional[str] = None
    created_by_user_id: str
    created_at: datetime
    updated_at: datetime


class ProjectListResponse(BaseModel):
    """Response containing a list of projects."""
    
    projects: List[ProjectResponse]
    total: int


class GlobalProjectResponse(BaseModel):
    """Response for global project templates."""
    
    id: str
    name: str
    description: Optional[str] = None
    created_by_user_id: str
    created_at: datetime
    updated_at: datetime
    usage_count: Optional[int] = None  # How many users have copied this template


class GlobalProjectListResponse(BaseModel):
    """Response containing a list of global project templates."""
    
    projects: List[GlobalProjectResponse]
    total: int