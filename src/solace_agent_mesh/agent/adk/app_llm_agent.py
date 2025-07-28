"""
Custom LlmAgent subclass for the A2A Host Component.
"""

from typing import Any
from google.adk.agents import LlmAgent
from pydantic import Field


class AppLlmAgent(LlmAgent):
    """
    Custom LlmAgent subclass that includes a reference to the hosting
    SamAgentComponent.

    This allows tools and callbacks within the ADK agent's execution context
    to access host-level configurations and services.
    """

    host_component: Any = Field(None, exclude=True)
    """
    A reference to the SamAgentComponent instance that hosts this agent.
    Using `Any` to avoid Pydantic's early type resolution issues with
    forward references and circular dependencies.
    This field is excluded from Pydantic's model serialization and validation
    if not provided during instantiation, and is intended to be set post-init.
    """
