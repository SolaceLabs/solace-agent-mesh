"""
ADK Tool implementation for an agent to start an isolated, self-contained sub-task.
"""

from typing import Any, Dict, Optional, List, Union
import uuid

from google.adk.tools import BaseTool, ToolContext
from google.genai import types as adk_types
from pydantic import BaseModel, Field
from solace_ai_connector.common.log import log

from ...common.a2a.types import ContentPart
from ...common import a2a
from ...common.constants import DEFAULT_COMMUNICATION_TIMEOUT
from ...common.exceptions import MessageSizeExceededError
from ...agent.utils.context_helpers import get_original_session_id
from .peer_agent_tool import CORRELATION_DATA_PREFIX, ArtifactIdentifier


class SelfSideQuestTool(BaseTool):
    """
    An ADK Tool that allows an agent to start an isolated, self-contained
    sub-task on itself. This is useful for complex, multi-step reasoning
    or data processing that should not pollute the main conversation history.
    """

    is_long_running = True

    def __init__(self, host_component):
        """
        Initializes the SelfSideQuestTool.

        Args:
            host_component: A reference to the SamAgentComponent instance.
        """
        super().__init__(
            name="self_side_quest",
            description=(
                "Initiates an isolated, self-contained 'side quest' sub-task on this agent. "
                "Use this for complex, multi-step reasoning or data processing that requires a clean context. "
                "The side quest inherits the current conversation history but its intermediate steps will not "
                "pollute the main conversation. Only the final result is returned."
            ),
            is_long_running=True,
        )
        self.host_component = host_component
        self.log_identifier = f"{host_component.log_identifier}[SelfSideQuestTool]"

    def _get_declaration(self) -> Optional[adk_types.FunctionDeclaration]:
        """Generates the FunctionDeclaration for the tool."""
        parameters_schema = adk_types.Schema(
            type=adk_types.Type.OBJECT,
            properties={
                "task_description": adk_types.Schema(
                    type=adk_types.Type.STRING,
                    description="A detailed, natural language description of the goal for the side quest.",
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
                    description="A list of artifacts to pre-load into the side quest's context.",
                    nullable=True,
                ),
            },
            required=["task_description"],
        )

        return adk_types.FunctionDeclaration(
            name=self.name,
            description=self.description,
            parameters=parameters_schema,
        )

    def _prepare_a2a_parts(
        self, args: Dict[str, Any], tool_context: ToolContext
    ) -> List[ContentPart]:
        """Prepares the A2A message parts from tool arguments."""
        task_description = args.get("task_description", "No description provided.")
        return [a2a.create_text_part(text=task_description)]

    async def run_async(
        self, *, args: Dict[str, Any], tool_context: ToolContext
    ) -> Any:
        """
        Handles the initiation of a side quest in a non-blocking,
        "fire-and-forget" manner suitable for a long-running tool.
        """
        sub_task_id = f"{CORRELATION_DATA_PREFIX}{uuid.uuid4().hex}"
        log_identifier = f"{self.log_identifier}[SubTask:{sub_task_id}]"
        main_logical_task_id = "unknown_task"

        try:
            target_agent_name = self.host_component.agent_name
            if not target_agent_name:
                raise ValueError("Host component agent_name is not set.")

            original_task_context = tool_context.state.get("a2a_context", {})
            main_logical_task_id = original_task_context.get(
                "logical_task_id", "unknown_task"
            )
            parent_session_id = get_original_session_id(
                tool_context._invocation_context
            )
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
                "%s Registered parallel call for invocation %s.",
                log_identifier,
                invocation_id,
            )

            a2a_message_parts = self._prepare_a2a_parts(args, tool_context)
            a2a_metadata = {}
            raw_artifacts = args.get("artifacts", [])
            if raw_artifacts and isinstance(raw_artifacts, list):
                a2a_metadata["invoked_with_artifacts"] = raw_artifacts
                log.debug(
                    "%s Included %d artifact identifiers in A2A message metadata.",
                    log_identifier,
                    len(raw_artifacts),
                )

            # Add side quest specific metadata
            a2a_metadata["is_side_quest"] = True
            a2a_metadata["parent_session_id"] = parent_session_id
            a2a_metadata["sessionBehavior"] = "RUN_BASED"
            a2a_metadata["parentTaskId"] = main_logical_task_id
            a2a_metadata["function_call_id"] = tool_context.function_call_id
            a2a_metadata["agent_name"] = target_agent_name

            a2a_message = a2a.create_user_message(
                parts=a2a_message_parts,
                metadata=a2a_metadata,
                context_id=original_task_context.get("contextId"),
            )

            correlation_data = {
                "adk_function_call_id": tool_context.function_call_id,
                "original_task_context": original_task_context,
                "peer_tool_name": self.name,
                "peer_agent_name": target_agent_name,
                "logical_task_id": main_logical_task_id,
                "invocation_id": invocation_id,
            }

            task_context_obj.register_peer_sub_task(sub_task_id, correlation_data)

            self.host_component.cache_service.add_data(
                key=sub_task_id,
                value=main_logical_task_id,
                expiry=timeout_sec,
                component=self.host_component,
            )

            try:
                self.host_component.submit_a2a_task(
                    target_agent_name=target_agent_name,
                    a2a_message=a2a_message,
                    user_id=user_id,
                    user_config=user_config,
                    sub_task_id=sub_task_id,
                )
            except MessageSizeExceededError as e:
                log.error(
                    "%s Message size exceeded for side quest request: %s",
                    log_identifier,
                    e,
                )
                return {
                    "status": "error",
                    "message": f"Error: {str(e)}. Message size exceeded for side quest request.",
                }

            log.info(
                "%s Registered active side quest sub-task %s for main task %s.",
                log_identifier,
                sub_task_id,
                main_logical_task_id,
            )

            log.info(
                "%s Side quest task fired. Returning to unblock ADK framework.",
                log_identifier,
            )
            return None

        except Exception as e:
            log.exception(
                "%s Error during side quest tool execution: %s", log_identifier, e
            )
            return {
                "status": "error",
                "message": f"Failed to initiate side quest: {e}",
            }
