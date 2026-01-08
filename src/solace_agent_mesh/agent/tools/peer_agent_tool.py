"""
ADK Tool implementation for delegating tasks to peer A2A agents over Solace.
"""

import logging
from typing import Any, Dict, Optional, List, Union
import uuid

from google.adk.tools import BaseTool, ToolContext
from google.genai import types as adk_types
from pydantic import BaseModel, Field

from ...common.a2a.types import ContentPart
from a2a.types import (
    AgentCard,
)
from ...common import a2a
from ...common.constants import DEFAULT_COMMUNICATION_TIMEOUT
from ...common.exceptions import MessageSizeExceededError

log = logging.getLogger(__name__)

class ArtifactIdentifier(BaseModel):
    """Identifies a specific version of an artifact."""

    filename: str = Field(..., description="The filename of the artifact.")
    version: Union[str, int] = Field(
        "latest",
        description="The version of the artifact (e.g., 'latest' or a number).",
    )


PEER_TOOL_PREFIX = "peer_"
CORRELATION_DATA_PREFIX = "a2a_subtask_"


class PeerAgentTool(BaseTool):
    """
    An ADK Tool that represents a discovered peer agent and handles task delegation
    via the A2A protocol over Solace.

    This tool is long-running and operates in a "fire-and-forget" manner. It sends a
    task to a peer agent, including a `task_description` and an optional list of
    `artifacts` to provide context. The artifact identifiers are passed in the
    A2A message metadata, and the peer agent is responsible for fetching them.

    The response from the peer is handled asynchronously by the agent's event handlers.
    """

    is_long_running = True

    def __init__(self, target_agent_name: str, host_component):
        """
        Initializes the PeerAgentTool.

        Args:
            target_agent_name: The name of the peer agent this tool represents.
            host_component: A reference to the SamAgentComponent instance.
        """
        tool_name = f"{PEER_TOOL_PREFIX}{target_agent_name}"
        super().__init__(
            name=tool_name,
            description=f"Delegate tasks to the {target_agent_name} agent.",
            is_long_running=True,
        )
        self.target_agent_name = target_agent_name
        self.host_component = host_component
        self.log_identifier = (
            f"{host_component.log_identifier}[PeerTool:{target_agent_name}]"
        )
        self.sub_task_id: Optional[str] = None

    def _get_peer_agent_card(self) -> Optional[AgentCard]:
        """Safely retrieves the AgentCard for the target peer."""
        return self.host_component.peer_agents.get(self.target_agent_name)

    def _build_enhanced_description(self, agent_card: AgentCard) -> str:
        """
        Builds an enhanced description including skills.
        Returns a structured, markdown-formatted description with:
        - Base description
        - Skills section (if skills are available)
        - Summary format (counts + skill names, up to 8 skills before truncation)
        - Soft limit of ~500 chars (allows overflow to ~600 for important info)

        Args:
            agent_card: The AgentCard to extract information from

        Returns:
            Enhanced description string with markdown formatting
        """
        # Start with base description - ensure it's clean (no extra whitespace)
        base_desc = agent_card.description or f"Interact with the {self.target_agent_name} agent."
        base_desc = " ".join(base_desc.split())  # Normalize whitespace

        # Extract skills information
        if agent_card.skills and len(agent_card.skills) > 0:
            skill_count = len(agent_card.skills)
            # Get first 8 skill names
            max_skills_to_show = 8
            skill_names = []
            for skill in agent_card.skills[:max_skills_to_show]:
                # Prefer name, fallback to id
                skill_name = getattr(skill, 'name', None) or getattr(skill, 'id', None)
                if skill_name:
                    skill_names.append(skill_name)

            skills_str = ", ".join(skill_names)
            # Add truncation indicator with count if there are more skills
            if skill_count > max_skills_to_show:
                remaining = skill_count - max_skills_to_show
                skills_str += f" ({remaining} more...)"

            # Include skill count in the header
            if skill_count > 1:
                enhanced_desc = f"{base_desc}\n\n**Skills ({skill_count}):** {skills_str}"
            else:
                enhanced_desc = f"{base_desc}\n\n**Skills:** {skills_str}"

            # Check length and truncate if needed (soft limit ~600 chars)
            if len(enhanced_desc) > 600:
                # Truncate to first 4 skills to keep it concise
                skill_names = []
                for skill in agent_card.skills[:4]:
                    skill_name = getattr(skill, 'name', None) or getattr(skill, 'id', None)
                    if skill_name:
                        skill_names.append(skill_name)
                skills_str = ", ".join(skill_names)
                if skill_count > 4:
                    remaining = skill_count - 4
                    skills_str += f" ({remaining} more...)"

                if skill_count > 1:
                    enhanced_desc = f"{base_desc}\n\n**Skills ({skill_count}):** {skills_str}"
                else:
                    enhanced_desc = f"{base_desc}\n\n**Skills:** {skills_str}"
        else:
            # No skills - just return base description
            enhanced_desc = base_desc

        return enhanced_desc

    def _get_declaration(self) -> Optional[adk_types.FunctionDeclaration]:
        """
        Dynamically generates the FunctionDeclaration based on the peer's AgentCard.
        Returns None if the peer agent is not currently discovered/allowed.
        """
        agent_card = self._get_peer_agent_card()
        if not agent_card:
            log.warning(
                "%s Peer agent '%s' not found in registry. Tool unavailable.",
                self.log_identifier,
                self.target_agent_name,
            )
            return None

        # Use enhanced description with capabilities information
        self.description = self._build_enhanced_description(agent_card)

        parameters_schema = adk_types.Schema(
            type=adk_types.Type.OBJECT,
            properties={
                "task_description": adk_types.Schema(
                    type=adk_types.Type.STRING,
                    description="Detailed description of the task for the peer agent.",
                ),
                "artifacts": adk_types.Schema(
                    type=adk_types.Type.ARRAY,
                    items=adk_types.Schema(
                        type=adk_types.Type.OBJECT,
                        properties={
                            "filename": adk_types.Schema(
                                type=adk_types.Type.STRING,
                                description="The filename of the artifact.",
                            ),
                            "version": adk_types.Schema(
                                type=adk_types.Type.STRING,
                                description="The version of the artifact (e.g., 'latest' or a number). Defaults to 'latest'.",
                                nullable=True,
                            ),
                        },
                        required=["filename"],
                    ),
                    description="A list of artifacts to provide as context to the peer agent.",
                    nullable=True,
                ),
            },
            required=["task_description"],
        )

        log.debug(
            "%s Generated declaration for peer '%s'",
            self.log_identifier,
            self.target_agent_name,
        )
        return adk_types.FunctionDeclaration(
            name=self.name,
            description=self.description,
            parameters=parameters_schema,
        )

    def _prepare_a2a_parts(
        self, args: Dict[str, Any], tool_context: ToolContext
    ) -> List[ContentPart]:
        """
        Prepares the A2A message parts from tool arguments.
        """
        task_description = args.get("task_description", "No description provided.")
        calling_agent_name = self.host_component.agent_name or "Unknown Agent"

        # Create the multi-agent context message
        context_message = (
            f"You are part of a multi-agent AI platform. The task below is being sent to you by agent '{calling_agent_name}'. "
            "You must perform this task to the best of your abilities. All artifacts that you create will automatically be "
            "returned to the calling agent, but you must provide context and description for which artifacts are important "
            "and how they should be used. Note that the calling agent will not see any of your history - only the text "
            "that you respond with.\n\n"
            "Note that if the request has not provided the information you need to do your job, you must ask for it. "
            "You must not 'make up' data unless specifically instructed to do so.\n\n"
            f"Now please execute this task that was given to you:\n\n{task_description}"
        )

        return [a2a.create_text_part(text=context_message)]

    async def run_async(
        self, *, args: Dict[str, Any], tool_context: ToolContext
    ) -> Any:
        """
        Handles the delegation of a task to a peer agent in a non-blocking,
        "fire-and-forget" manner suitable for a long-running tool.
        """
        sub_task_id = f"{CORRELATION_DATA_PREFIX}{uuid.uuid4().hex}"
        log_identifier = f"{self.log_identifier}[SubTask:{sub_task_id}]"
        main_logical_task_id = "unknown_task"

        try:
            agent_card = self._get_peer_agent_card()
            if not agent_card:
                raise ValueError(
                    f"Peer agent '{self.target_agent_name}' not found or unavailable."
                )

            original_task_context = tool_context.state.get("a2a_context", {})
            main_logical_task_id = original_task_context.get(
                "logical_task_id", "unknown_task"
            )
            original_session_id = tool_context._invocation_context.session.id
            user_id = tool_context._invocation_context.user_id
            user_config = original_task_context.get("a2a_user_config", {})

            invocation_id = tool_context._invocation_context.invocation_id
            timeout_sec = self.host_component.get_config(
                "inter_agent_communication", {}
            ).get("request_timeout_seconds", DEFAULT_COMMUNICATION_TIMEOUT)

            task_context_obj = None
            with self.host_component.active_tasks_lock:
                task_context_obj = self.host_component.active_tasks.get(
                    main_logical_task_id
                )

            if not task_context_obj:
                raise ValueError(
                    f"TaskExecutionContext not found for task '{main_logical_task_id}'"
                )

            task_context_obj.register_parallel_call_sent(invocation_id)
            log.info(
                "%s Registered parallel call for invocation %s. Current state: %s",
                log_identifier,
                invocation_id,
                task_context_obj.parallel_tool_calls.get(invocation_id),
            )

            a2a_message_parts = self._prepare_a2a_parts(args, tool_context)
            a2a_metadata = {}
            raw_artifacts = args.get("artifacts", [])
            if raw_artifacts and isinstance(raw_artifacts, list):
                try:
                    # The ADK gives us a list of dicts, not Pydantic models
                    # so we can use them directly.
                    a2a_metadata["invoked_with_artifacts"] = raw_artifacts
                    log.debug(
                        "%s Included %d artifact identifiers in A2A message metadata.",
                        log_identifier,
                        len(raw_artifacts),
                    )
                except Exception as e:
                    log.warning(
                        "%s Failed to serialize artifact identifiers: %s. Proceeding without them.",
                        log_identifier,
                        e,
                    )

            a2a_metadata["sessionBehavior"] = "RUN_BASED"
            a2a_metadata["parentTaskId"] = main_logical_task_id
            a2a_metadata["function_call_id"] = tool_context.function_call_id
            a2a_metadata["agent_name"] = self.target_agent_name

            a2a_message = a2a.create_user_message(
                parts=a2a_message_parts,
                metadata=a2a_metadata,
                context_id=original_task_context.get("contextId"),
            )

            correlation_data = {
                "adk_function_call_id": tool_context.function_call_id,
                "original_task_context": original_task_context,
                "peer_tool_name": self.name,
                "peer_agent_name": self.target_agent_name,
                "logical_task_id": main_logical_task_id,
                "invocation_id": invocation_id,
            }

            # Register the sub-task's state within the parent task's context.
            task_context_obj.register_peer_sub_task(sub_task_id, correlation_data)

            # Add a simple mapping to the cache for timeout tracking.
            self.host_component.cache_service.add_data(
                key=sub_task_id,
                value=main_logical_task_id,
                expiry=timeout_sec,
                component=self.host_component,
            )

            try:
                self.host_component.submit_a2a_task(
                    target_agent_name=self.target_agent_name,
                    a2a_message=a2a_message,
                    user_id=user_id,
                    user_config=user_config,
                    sub_task_id=sub_task_id,
                )
            except MessageSizeExceededError as e:
                log.error(
                    "%s Message size exceeded for peer agent request: %s",
                    log_identifier,
                    e,
                )
                return {
                    "status": "error",
                    "message": f"Error: {str(e)}. Message size exceeded for peer agent request.",
                }

            log.info(
                "%s Registered active peer sub-task %s for main task %s.",
                log_identifier,
                sub_task_id,
                main_logical_task_id,
            )

            log.info(
                "%s Task fired. Returning to unblock ADK framework.",
                log_identifier,
            )
            return None

        except Exception as e:
            log.exception("%s Error during peer tool execution: %s", log_identifier, e)
            return {
                "status": "error",
                "message": f"Failed to delegate task to peer agent '{self.target_agent_name}': {e}",
            }
