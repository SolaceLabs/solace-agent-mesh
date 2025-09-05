from pydantic import BaseModel, Field
from typing import List, Optional

class CreateAgentCardRequest(BaseModel):
    description: str
    default_input_modes: List[str] = Field(default=["text"])
    default_output_modes: List[str] = Field(default=["text"])

class CreateAgentRequest(BaseModel):
    display_name: str
    prompt: str
    agent_card: CreateAgentCardRequest

class UpdateAgentCardRequest(BaseModel):
    description: Optional[str] = None
    default_input_modes: Optional[List[str]] = None
    default_output_modes: Optional[List[str]] = None

class UpdateAgentRequest(BaseModel):
    display_name: Optional[str] = None
    prompt: Optional[str] = None
    agent_card: Optional[UpdateAgentCardRequest] = None
