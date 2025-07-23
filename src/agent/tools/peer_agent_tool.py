"""
ADK Tool implementation for delegating tasks to peer A2A agents over Solace.
"""

from typing import Any, Dict, Optional, List, Union
import uuid

from google.adk.tools import BaseTool, ToolContext
from google.genai import types as adk_types
from solace_ai_connector.common.log import log

from ...common.types import (
    Message as A2AMessage,
    TextPart,
    FilePart,
    AgentCard,
)
from ...common.constants import DEFAULT_COMMUNICATION_TIMEOUT

PEER_TOOL_PREFIX = "peer_"
CORRELATION_DATA_PREFIX = "a2a_subtask_"


class PeerAgentTool(BaseTool):
    """
    An ADK Tool that represents a discovered peer agent and handles task delegation
    via the A2A protocol over Solace. Uses an asyncio Queue to block and wait for
    the asynchronous response. Handles artifact passthrough from peer responses.
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

        self.description = (
            agent_card.description
            or f"Interact with the {self.target_agent_name} agent."
        )

        parameters_schema = adk_types.Schema(
            type=adk_types.Type.OBJECT,
            properties={
                "task_description": adk_types.Schema(
                    type=adk_types.Type.STRING,
                    description="Detailed description of the task for the peer agent.",
                ),
                "user_query": adk_types.Schema(
                    type=adk_types.Type.STRING,
                    description="The original user query or relevant context.",
                ),
                "data_artifacts": adk_types.Schema(
                    type=adk_types.Type.ARRAY,
                    items=adk_types.Schema(type=adk_types.Type.STRING),
                    description="A list of artifact filenames to be sent to the peer agent for context.",
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

    async def _prepare_a2a_parts(
        self, args: Dict[str, Any], tool_context: ToolContext
    ) -> List[Union[TextPart, FilePart]]:
        """
        Prepares the A2A message parts from tool arguments, including text and artifacts.
        """
        task_description = args.get("task_description", "No description provided.")
        calling_agent_name = self.host_component.agent_name or "Unknown Agent"

        # Create the multi-agent context message
        context_message = (
            f"You are part of a multi-agent AI platform. The task below is being sent to you by agent '{calling_agent_name}'. "
            f"You must perform this task to the best of your abilities. All artifacts that you create will automatically be "
            f"returned to the calling agent, but you must provide context and description for which artifacts are important "
            f"and how they should be used. Note that the calling agent will not see any of your history - only the text "
            f"that you respond with.\n\n"
            f"Now please execute this task that was given to you:\n\n{task_description}"
        )

        a2a_message_parts = [TextPart(text=context_message)]

        artifact_names = args.get("data_artifacts", [])
        if not isinstance(artifact_names, list):
            log.warning(
                "%s 'data_artifacts' argument is not a list, ignoring. Value: %s",
                self.log_identifier,
                artifact_names,
            )
            artifact_names = []

        if artifact_names:
            log.debug(
                "%s Preparing to include %d artifacts in peer request.",
                self.log_identifier,
                len(artifact_names),
            )
            a2a_context = tool_context.state.get("a2a_context", {})
            for artifact_name in artifact_names:
                try:
                    loaded_part = (
                        await self.host_component.artifact_service.load_artifact(
                            app_name=tool_context._invocation_context.app_name,
                            user_id=tool_context._invocation_context.user_id,
                            session_id=tool_context._invocation_context.session.id,
                            filename=artifact_name,
                            version=None,
                        )
                    )
                    if loaded_part:
                        a2a_file_part = await self.host_component._translate_adk_part_to_a2a_filepart(
                            loaded_part, artifact_name, a2a_context
                        )
                        if a2a_file_part:
                            a2a_message_parts.append(a2a_file_part)
                            log.info(
                                "%s Included latest artifact '%s' in peer request.",
                                self.log_identifier,
                                artifact_name,
                            )
                        else:
                            log.warning(
                                "%s Failed to translate loaded artifact '%s' to A2A part. Skipping.",
                                self.log_identifier,
                                artifact_name,
                            )
                    else:
                        log.warning(
                            "%s Could not load artifact '%s' to include in peer request. Skipping.",
                            self.log_identifier,
                            artifact_name,
                        )
                except Exception as e:
                    log.exception(
                        "%s Error loading artifact '%s' for peer request: %s",
                        self.log_identifier,
                        artifact_name,
                        e,
                    )
        return a2a_message_parts

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

            a2a_message_parts = await self._prepare_a2a_parts(args, tool_context)
            a2a_message = A2AMessage(role="user", parts=a2a_message_parts)

            correlation_data = {
                "adk_function_call_id": tool_context.function_call_id,
                "original_task_context": original_task_context,
                "peer_tool_name": self.name,
                "logical_task_id": main_logical_task_id,
                "invocation_id": invocation_id,
            }

            self.host_component.cache_service.add_data(
                key=sub_task_id,
                value=correlation_data,
                expiry=timeout_sec,
                component=self.host_component,
            )

            self.host_component.submit_a2a_task(
                target_agent_name=self.target_agent_name,
                a2a_message=a2a_message,
                original_session_id=original_session_id,
                main_logical_task_id=main_logical_task_id,
                user_id=user_id,
                user_config=user_config,
                sub_task_id=sub_task_id,
                function_call_id=tool_context.function_call_id,
            )

            task_context_obj.register_peer_sub_task(
                sub_task_id=sub_task_id, peer_agent_name=self.target_agent_name
            )
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
