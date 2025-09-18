"""
Defines the Pydantic model for a self-contained BuiltinTool definition.
"""

from typing import Callable, List, Dict, Any, Optional
from pydantic import BaseModel, Field
from google.genai import types as adk_types


class BuiltinTool(BaseModel):
    """A self-contained, declarative definition for a built-in agent tool."""

    name: str = Field(..., description="The function name the LLM will call.")
    implementation: Callable = Field(
        ..., description="The async Python function that implements the tool."
    )
    description: str = Field(
        ...,
        description="High-level description for the LLM to understand the tool's purpose.",
    )
    parameters: adk_types.Schema = Field(
        ..., description="The OpenAPI-like schema for the tool's parameters."
    )
    examples: List[Dict[str, Any]] = Field(
        default_factory=list, description="Few-shot examples for the LLM."
    )
    required_scopes: List[str] = Field(
        default_factory=list,
        description="A list of scopes required to execute this tool.",
    )
    category: str = Field(
        default="General",
        description="A category for grouping tools, e.g., 'Artifact', 'Data Analysis'. Used for configuration toggles.",
    )
    category_name: Optional[str] = Field(
        default=None,
        description="A human-readable name for the tool's category.",
    )
    category_description: Optional[str] = Field(
        default=None,
        description="A description for the tool's category. Will be the same for all tools in a category.",
    )
    initializer: Optional[Callable[[Any, Dict[str, Any]], None]] = Field(
        default=None,
        description="An optional function to initialize the tool or its dependencies.",
    )
    raw_string_args: List[str] = Field(
        default_factory=list,
        description="A list of argument names that should be passed as raw strings without embed pre-resolution.",
    )

    class Config:
        arbitrary_types_allowed = True
