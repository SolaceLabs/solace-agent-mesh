"""
Custom LlmAgent subclass for the A2A Host Component.
"""

from typing import Any

from google.adk.agents import LlmAgent
from google.adk.flows.llm_flows.base_llm_flow import BaseLlmFlow
from google.adk.flows.llm_flows.single_flow import SingleFlow
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

    # Override the _llm_flow property to inject the patched auth preprocessor
    @property
    def _llm_flow(self) -> BaseLlmFlow:
        try:
            from solace_agent_mesh_enterprise.auth.auth_preprocessor_patch import (
                request_processor,
            )
        except ImportError:
            # If enterprise module doesn't exist, use standard parent flow
            return super()._llm_flow

        llm_flow = super()._llm_flow
        if isinstance(llm_flow, SingleFlow):
            # Replace auth_preprocessor.request_processor with the patched version from _AuthLlmRequestProcessorPatched
            from google.adk.auth import auth_preprocessor

            for i, processor in enumerate(llm_flow.request_processors):
                if processor is auth_preprocessor.request_processor:
                    llm_flow.request_processors[i] = request_processor
                    break

        return llm_flow
