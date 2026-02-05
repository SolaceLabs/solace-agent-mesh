"""
Pydantic models for prompt library API.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class PromptBase(BaseModel):
    """Base schema for Prompt"""
    prompt_text: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="The prompt text content",
        alias="promptText"
    )
    
    class Config:
        populate_by_name = True


class PromptCreate(PromptBase):
    """Schema for creating a new prompt version"""
    pass


class PromptResponse(PromptBase):
    """Schema for prompt response"""
    id: str
    group_id: str = Field(alias="groupId")
    user_id: str = Field(alias="userId")
    version: int
    # Versioned metadata fields
    name: Optional[str] = Field(None, description="Prompt name at this version")
    description: Optional[str] = Field(None, description="Prompt description at this version")
    category: Optional[str] = Field(None, description="Prompt category at this version")
    command: Optional[str] = Field(None, description="Prompt command at this version")
    created_at: int = Field(alias="createdAt")  # epoch milliseconds
    updated_at: int = Field(alias="updatedAt")  # epoch milliseconds
    
    class Config:
        from_attributes = True
        populate_by_name = True


class PromptGroupBase(BaseModel):
    """Base schema for PromptGroup"""
    name: str = Field(
        ..., 
        min_length=1, 
        max_length=255, 
        description="Name of the prompt group"
    )
    description: Optional[str] = Field(
        None, 
        max_length=1000, 
        description="Short description"
    )
    category: Optional[str] = Field(
        None, 
        max_length=100, 
        description="Category for organization"
    )
    command: Optional[str] = Field(
        None,
        min_length=1,
        max_length=50,
        pattern="^[a-zA-Z0-9_-]+$",
        description="Shorthand command (alphanumeric, dash, underscore only)"
    )


class PromptGroupCreate(PromptGroupBase):
    """Schema for creating a new prompt group"""
    initial_prompt: str = Field(
        ..., 
        min_length=1, 
        max_length=10000, 
        description="Initial prompt text"
    )


class PromptGroupUpdate(BaseModel):
    """Schema for updating a prompt group"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    category: Optional[str] = Field(None, max_length=100)
    command: Optional[str] = Field(
        None,
        min_length=1,
        max_length=50,
        pattern="^[a-zA-Z0-9_-]+$"
    )
    initial_prompt: Optional[str] = Field(
        None,
        min_length=1,
        max_length=10000,
        description="Updated prompt text (creates new version if changed)"
    )


class PromptGroupResponse(PromptGroupBase):
    """Schema for prompt group response"""
    id: str
    user_id: str = Field(alias="userId")
    author_name: Optional[str] = Field(None, alias="authorName")
    production_prompt_id: Optional[str] = Field(None, alias="productionPromptId")
    is_shared: bool = Field(alias="isShared")
    is_pinned: bool = Field(alias="isPinned")
    created_at: int = Field(alias="createdAt")  # epoch milliseconds
    updated_at: int = Field(alias="updatedAt")  # epoch milliseconds
    
    # Include production prompt if available
    production_prompt: Optional[PromptResponse] = Field(None, alias="productionPrompt")
    
    class Config:
        from_attributes = True
        populate_by_name = True


class PromptGroupListResponse(BaseModel):
    """Schema for paginated prompt group list"""
    groups: List[PromptGroupResponse]
    total: int
    skip: int
    limit: int


# AI-Assisted Prompt Builder Models

class ChatMessage(BaseModel):
    """Schema for a chat message"""
    role: str = Field(
        ..., 
        pattern="^(user|assistant)$", 
        description="Message role"
    )
    content: str = Field(..., min_length=1, description="Message content")


class PromptBuilderChatRequest(BaseModel):
    """Schema for prompt builder chat request"""
    message: str = Field(
        ...,
        min_length=1,
        max_length=200000,
        description="User message (supports long conversation histories for template creation)"
    )
    conversation_history: List[ChatMessage] = Field(
        default_factory=list, 
        description="Previous messages"
    )
    current_template: Optional[Dict[str, Any]] = Field(
        None, 
        description="Current template state"
    )


class PromptBuilderChatResponse(BaseModel):
    """Schema for prompt builder chat response"""
    message: str = Field(..., description="Assistant's response message")
    template_updates: Dict[str, Any] = Field(
        default_factory=dict, 
        description="Updates to template config"
    )
    confidence: float = Field(
        0.0, 
        ge=0.0, 
        le=1.0, 
        description="Confidence score"
    )
    ready_to_save: bool = Field(
        False,
        description="Whether template is ready to save"
    )


# Export/Import Models

class PromptExportMetadata(BaseModel):
    """Metadata for exported prompt"""
    author_name: Optional[str] = Field(None, alias="authorName")
    original_version: int = Field(alias="originalVersion")
    original_created_at: int = Field(alias="originalCreatedAt")
    
    class Config:
        populate_by_name = True


class PromptExportData(BaseModel):
    """Data structure for exported prompt"""
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    command: Optional[str] = None
    prompt_text: str = Field(alias="promptText")
    metadata: PromptExportMetadata
    
    class Config:
        populate_by_name = True


class PromptExportResponse(BaseModel):
    """Schema for exported prompt file"""
    version: str = "1.0"
    exported_at: int = Field(alias="exportedAt")
    prompt: PromptExportData
    
    class Config:
        populate_by_name = True
        by_alias = True


class PromptImportOptions(BaseModel):
    """Options for importing a prompt"""
    preserve_command: bool = Field(
        False,
        alias="preserveCommand",
        description="If true, attempt to keep original command (may be modified if conflict exists)"
    )
    preserve_category: bool = Field(
        True,
        alias="preserveCategory",
        description="If true, keep the original category"
    )
    
    class Config:
        populate_by_name = True


class PromptImportRequest(BaseModel):
    """Schema for importing a prompt"""
    prompt_data: Dict[str, Any] = Field(
        ...,
        description="The exported prompt JSON data"
    )
    options: Optional[PromptImportOptions] = Field(
        default_factory=PromptImportOptions,
        description="Import options"
    )


class PromptImportResponse(BaseModel):
    """Schema for import response"""
    success: bool
    prompt_group_id: str = Field(alias="promptGroupId")
    warnings: List[str] = Field(
        default_factory=list,
        description="Any warnings generated during import (e.g., command conflicts)"
    )
    
    class Config:
        populate_by_name = True
        by_alias = True