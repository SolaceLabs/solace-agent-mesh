"""
WorkflowExecutorComponent implementation.
Orchestrates workflow execution by coordinating agents.
"""

import logging
import threading
import uuid
import asyncio
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional, TYPE_CHECKING

from solace_ai_connector.common.message import Message as SolaceMessage
from solace_ai_connector.common.event import Event, EventType

from ..common import a2a
from ..common.sac.sam_component_base import SamComponentBase
from ..common.agent_registry import AgentRegistry
from ..common.constants import (
    EXTENSION_URI_AGENT_TYPE,
    EXTENSION_URI_SCHEMAS,
)

EXTENSION_URI_WORKFLOW_VISUALIZATION = "https://solace.com/a2a/extensions/sam/workflow-visualization"
from ..common.data_parts import (
    WorkflowExecutionStartData,
    WorkflowExecutionResultData,
    WorkflowNodeExecutionStartData,
    WorkflowNodeExecutionResultData,
    WorkflowMapProgressData,
    ArtifactRef,
)
from ..agent.adk.services import (
    initialize_session_service,
    initialize_artifact_service,
)
from ..agent.utils.artifact_helpers import save_artifact_with_metadata
from .app import WorkflowDefinition
from .workflow_execution_context import WorkflowExecutionContext, WorkflowExecutionState
from .dag_executor import DAGExecutor, WorkflowNodeFailureError
from .agent_caller import AgentCaller
from .protocol.event_handlers import (
    handle_task_request,
    handle_agent_response,
    handle_cancel_request,
    handle_agent_card_message,
)

from a2a.types import (
    A2ARequest,
    AgentCard,
    AgentCapabilities,
    TaskState,
    TaskStatusUpdateEvent,
)

log = logging.getLogger(__name__)

info = {
    "class_name": "WorkflowExecutorComponent",
    "description": "Orchestrates workflow execution by coordinating agents.",
    "config_parameters": [],
}


class WorkflowExecutorComponent(SamComponentBase):
    """
    Orchestrates workflow execution by coordinating agents.

    Extends SamComponentBase to leverage:
    - Dedicated asyncio event loop
    - A2A message publishing infrastructure
    - Component lifecycle management
    """

    def __init__(self, **kwargs):
        """
        Initialize workflow executor component.
        """
        if "component_config" in kwargs and "app_config" in kwargs["component_config"]:
            name = kwargs["component_config"]["app_config"].get("agent_name")
            if name:
                kwargs.setdefault("name", name)

        super().__init__(info, **kwargs)

        # Configuration
        self.workflow_name = self.get_config("agent_name")
        self.namespace = self.get_config("namespace")
        workflow_config = self.get_config("workflow")

        # Parse workflow definition
        self.workflow_definition = WorkflowDefinition.model_validate(workflow_config)

        # Initialize synchronous services
        self.session_service = initialize_session_service(self)
        self.artifact_service = initialize_artifact_service(self)

        # Initialize execution tracking
        self.active_workflows: Dict[str, WorkflowExecutionContext] = {}
        self.active_workflows_lock = threading.Lock()

        # Initialize executor components
        self.dag_executor = DAGExecutor(self.workflow_definition, self)
        self.agent_caller = AgentCaller(self)

        # Create agent registry for agent discovery
        self.agent_registry = AgentRegistry()

    def invoke(self, message: SolaceMessage, data: dict) -> dict:
        """Placeholder invoke method. Logic in process_event."""
        return None

    def _get_component_id(self) -> str:
        """Returns the workflow name as the component identifier."""
        return self.workflow_name

    def _get_component_type(self) -> str:
        """Returns 'workflow' as the component type."""
        return "workflow"

    async def _handle_message_async(self, message: SolaceMessage, topic: str) -> None:
        """
        Async handler for incoming messages.
        """
        # Determine message type based on topic
        request_topic = a2a.get_agent_request_topic(self.namespace, self.workflow_name)
        discovery_topic = a2a.get_discovery_subscription_topic(self.namespace)
        response_sub = a2a.get_agent_response_subscription_topic(
            self.namespace, self.workflow_name
        )
        status_sub = a2a.get_agent_status_subscription_topic(
            self.namespace, self.workflow_name
        )
        if topic == request_topic:
            # Check if this is a cancel request or a regular task request
            try:
                payload = message.get_payload()
                method = payload.get("method") if isinstance(payload, dict) else None
                if method == "tasks/cancel":
                    task_id = a2a.get_task_id_from_cancel_request(
                        A2ARequest.model_validate(payload)
                    )
                    await handle_cancel_request(self, task_id, message)
                else:
                    await handle_task_request(self, message)
            except Exception as e:
                log.error(f"{self.log_identifier} Error processing request: {e}")
                message.call_acknowledgements()
        elif a2a.topic_matches_subscription(topic, discovery_topic):
            handle_agent_card_message(self, message)
        elif a2a.topic_matches_subscription(
            topic, response_sub
        ) or a2a.topic_matches_subscription(topic, status_sub):
            await handle_agent_response(self, message)
        else:
            log.warning(f"{self.log_identifier} Unknown topic: {topic}")
            message.call_acknowledgements()

    async def _async_setup_and_run(self) -> None:
        """
        Async initialization called by SamComponentBase.
        Sets up services and publishes workflow agent card.
        """
        # Set up periodic agent card publishing
        self._setup_periodic_agent_card_publishing()

        # Component is now ready to receive requests
        log.info(f"{self.log_identifier} Workflow ready: {self.workflow_name}")

    def _pre_async_cleanup(self) -> None:
        """Pre-cleanup before async loop stops."""
        pass

    def _setup_periodic_agent_card_publishing(self) -> None:
        """
        Sets up periodic publishing of the workflow agent card.
        Similar to SamAgentComponent's _publish_agent_card method.
        """
        try:
            publish_config = self.get_config("agent_card_publishing", {})
            publish_interval_sec = publish_config.get("interval_seconds")

            if publish_interval_sec and publish_interval_sec > 0:
                log.info(
                    f"{self.log_identifier} Scheduling workflow agent card publishing "
                    f"every {publish_interval_sec} seconds."
                )

                # Publish immediately on first call
                self._publish_workflow_agent_card_sync()

                # Set up periodic timer
                self.add_timer(
                    delay_ms=publish_interval_sec * 1000,
                    timer_id="workflow_agent_card_publish",
                    interval_ms=publish_interval_sec * 1000,
                    callback=lambda timer_data: self._publish_workflow_agent_card_sync(),
                )
            else:
                log.warning(
                    f"{self.log_identifier} Workflow agent card publishing interval not "
                    f"configured or invalid, card will not be published periodically."
                )
        except Exception as e:
            log.exception(
                f"{self.log_identifier} Error during agent card publishing setup: {e}"
            )

    def _publish_workflow_agent_card_sync(self) -> None:
        """
        Synchronous wrapper for publishing workflow agent card.
        Called by timer callback.
        """
        try:
            agent_card = self._create_workflow_agent_card()
            discovery_topic = a2a.get_agent_discovery_topic(self.namespace)
            self.publish_a2a_message(
                payload=agent_card.model_dump(exclude_none=True), topic=discovery_topic
            )
            log.debug(
                f"{self.log_identifier} Published workflow agent card to {discovery_topic}"
            )
        except Exception as e:
            log.error(
                f"{self.log_identifier} Failed to publish workflow agent card: {e}"
            )

    def _get_workflow_config_json(self) -> Dict[str, Any]:
        """Get workflow configuration as a JSON-serializable dict."""
        nodes_json = []
        for node in self.workflow_definition.nodes:
            node_dict = {
                "id": node.id,
                "type": node.type,
            }
            if node.depends_on:
                node_dict["depends_on"] = node.depends_on

            # Add type-specific fields
            if node.type == "agent":
                node_dict["agent_name"] = node.agent_name
                if node.input:
                    node_dict["input"] = node.input
                if node.instruction:
                    node_dict["instruction"] = node.instruction
                if node.input_schema_override:
                    node_dict["input_schema_override"] = node.input_schema_override
                if node.output_schema_override:
                    node_dict["output_schema_override"] = node.output_schema_override
            elif node.type == "switch":
                node_dict["cases"] = [
                    {"condition": c.condition, "node": c.node}
                    for c in node.cases
                ]
                if node.default:
                    node_dict["default"] = node.default
            elif node.type == "map":
                node_dict["node"] = node.node
                node_dict["items"] = node.items
            elif node.type == "loop":
                node_dict["node"] = node.node
                if node.condition:
                    node_dict["condition"] = node.condition
                if node.max_iterations:
                    node_dict["max_iterations"] = node.max_iterations
            elif node.type == "workflow":
                node_dict["workflow_name"] = node.workflow_name
                if node.input:
                    node_dict["input"] = node.input
                if node.instruction:
                    node_dict["instruction"] = node.instruction
                if node.input_schema_override:
                    node_dict["input_schema_override"] = node.input_schema_override
                if node.output_schema_override:
                    node_dict["output_schema_override"] = node.output_schema_override

            nodes_json.append(node_dict)

        config = {
            "nodes": nodes_json,
        }

        if self.workflow_definition.description:
            config["description"] = self.workflow_definition.description
        if self.workflow_definition.input_schema:
            config["input_schema"] = self.workflow_definition.input_schema
        if self.workflow_definition.output_schema:
            config["output_schema"] = self.workflow_definition.output_schema
        if self.workflow_definition.version:
            config["version"] = self.workflow_definition.version
        if self.workflow_definition.output_mapping:
            config["output_mapping"] = self.workflow_definition.output_mapping

        return config

    def _create_workflow_agent_card(self) -> AgentCard:
        """Create the workflow agent card."""
        # Build extensions list
        extensions_list = []

        from a2a.types import AgentExtension

        # Add agent type extension
        agent_type_extension = AgentExtension(
            uri=EXTENSION_URI_AGENT_TYPE,
            description="Specifies the type of agent (e.g., 'workflow').",
            params={"type": "workflow"},
        )
        extensions_list.append(agent_type_extension)

        # Add schema extension if schemas are defined
        input_schema = self.workflow_definition.input_schema
        output_schema = self.workflow_definition.output_schema

        if input_schema or output_schema:
            schema_params = {}
            if input_schema:
                schema_params["input_schema"] = input_schema
            if output_schema:
                schema_params["output_schema"] = output_schema

            schemas_extension = AgentExtension(
                uri=EXTENSION_URI_SCHEMAS,
                description="Input and output JSON schemas for the workflow.",
                params=schema_params,
            )
            extensions_list.append(schemas_extension)

        # Add workflow configuration extension
        try:
            workflow_config = self._get_workflow_config_json()
            viz_extension = AgentExtension(
                uri=EXTENSION_URI_WORKFLOW_VISUALIZATION,
                description="JSON configuration of the workflow.",
                params={"workflow_config": workflow_config},
            )
            extensions_list.append(viz_extension)
        except Exception as e:
            log.warning(
                f"{self.log_identifier} Failed to generate workflow configuration: {e}"
            )

        capabilities = AgentCapabilities(
            streaming=False,
            extensions=extensions_list if extensions_list else None,
        )

        return AgentCard(
            name=self.workflow_name,
            display_name=self.get_config("display_name"),
            description=self.workflow_definition.description,
            defaultInputModes=["text"],
            defaultOutputModes=["text"],
            skills=self.workflow_definition.skills or [],
            capabilities=capabilities,
            version=self.workflow_definition.version,
            url=f"solace:{a2a.get_agent_request_topic(self.namespace, self.workflow_name)}",
        )

    async def handle_cache_expiry_event(self, cache_data: Dict[str, Any]):
        """Handle agent call timeout via cache expiry."""
        sub_task_id = cache_data.get("key")
        workflow_task_id = cache_data.get("expired_data")

        if not sub_task_id or not workflow_task_id:
            return

        # Find workflow context
        with self.active_workflows_lock:
            workflow_context = self.active_workflows.get(workflow_task_id)

        if not workflow_context:
            log.warning(
                f"{self.log_identifier} Timeout for unknown workflow: {workflow_task_id}"
            )
            return

        # Get node ID for this sub-task
        node_id = workflow_context.get_node_id_for_sub_task(sub_task_id)

        if not node_id:
            return

        timeout_seconds = self.get_config("default_node_timeout_seconds", 300)
        log.error(
            f"{self.log_identifier} Agent call timed out for node '{node_id}' "
            f"(sub-task: {sub_task_id})"
        )

        # Create timeout error
        from ..common.data_parts import StructuredInvocationResult

        result_data = StructuredInvocationResult(
            type="structured_invocation_result",
            status="error",
            error_message=f"Agent timed out after {timeout_seconds} seconds",
        )

        # Handle as node failure
        await self.dag_executor.handle_node_completion(
            workflow_context, sub_task_id, result_data
        )

    async def publish_workflow_event(
        self,
        workflow_context: WorkflowExecutionContext,
        event_data: Any,
    ):
        """Publish a workflow status event."""
        try:
            status_update_event = a2a.create_data_signal_event(
                task_id=workflow_context.a2a_context["logical_task_id"],
                context_id=workflow_context.a2a_context["session_id"],
                signal_data=event_data,
                agent_name=self.workflow_name,
            )

            rpc_response = a2a.create_success_response(
                result=status_update_event,
                request_id=workflow_context.a2a_context["jsonrpc_request_id"],
            )

            target_topic = workflow_context.a2a_context.get(
                "statusTopic"
            ) or a2a.get_gateway_status_topic(
                self.namespace,
                "gateway",  # Placeholder, usually gateway_id
                workflow_context.a2a_context["logical_task_id"],
            )

            self.publish_a2a_message(
                payload=rpc_response.model_dump(exclude_none=True),
                topic=target_topic,
                user_properties={
                    "a2aUserConfig": workflow_context.a2a_context.get(
                        "a2a_user_config", {}
                    )
                },
            )
        except Exception as e:
            log.error(f"{self.log_identifier} Failed to publish workflow event: {e}")

    async def _execute_exit_handlers(
        self,
        workflow_context: WorkflowExecutionContext,
        outcome: str,
        error: Exception = None,
    ):
        """
        Execute exit handlers (onExit) based on workflow outcome.

        Args:
            workflow_context: The workflow context
            outcome: "success" or "failure"
            error: The error if outcome is "failure"
        """
        log_id = f"{self.log_identifier}[ExitHandler:{workflow_context.workflow_task_id}]"

        on_exit = self.workflow_definition.on_exit
        if not on_exit:
            return

        workflow_state = workflow_context.workflow_state

        # Inject workflow status and error into node_outputs for template resolution
        workflow_state.node_outputs["workflow"] = {
            "status": outcome,
            "error": {
                "message": str(error) if error else None,
                "node_id": (
                    workflow_state.error_state.get("failed_node_id")
                    if workflow_state.error_state
                    else None
                ),
            }
            if error
            else None,
        }

        # Determine which handlers to run
        nodes_to_run = []
        if isinstance(on_exit, str):
            # Simple string reference to a single node
            nodes_to_run.append(on_exit)
        else:
            # ExitHandler object with conditional handlers
            if on_exit.always:
                nodes_to_run.append(on_exit.always)
            if outcome == "success" and on_exit.on_success:
                nodes_to_run.append(on_exit.on_success)
            if outcome == "failure" and on_exit.on_failure:
                nodes_to_run.append(on_exit.on_failure)
            if outcome == "cancelled" and on_exit.on_cancel:
                nodes_to_run.append(on_exit.on_cancel)

        # Execute each exit handler node
        for node_id in nodes_to_run:
            try:
                log.info(f"{log_id} Executing exit handler node '{node_id}'")
                await self.dag_executor.execute_node(
                    node_id, workflow_state, workflow_context
                )
            except Exception as e:
                # Log but don't fail the workflow - exit handlers shouldn't break finalization
                log.error(
                    f"{log_id} Exit handler node '{node_id}' failed: {e}. "
                    "Continuing with finalization."
                )

    async def finalize_workflow_success(
        self, workflow_context: WorkflowExecutionContext
    ):
        """Finalize successful workflow execution and publish result."""
        log_id = f"{self.log_identifier}[Workflow:{workflow_context.workflow_task_id}]"
        log.info(f"{log_id} Finalizing workflow success")

        # Execute exit handlers first
        await self._execute_exit_handlers(workflow_context, "success")

        # Construct final output based on output mapping
        final_output = await self._construct_final_output(workflow_context)

        # Create output artifact with the workflow result
        # Use unique filename: <workflow_name>_<4-digit-uuid>_result.json
        unique_suffix = uuid.uuid4().hex[:4]
        output_artifact_name = f"{self.workflow_name}_{unique_suffix}_result.json"

        user_id = workflow_context.a2a_context["user_id"]
        session_id = workflow_context.a2a_context["session_id"]

        # Prepare artifact content - store just the output data
        # (not wrapped in {"status": ..., "output": ...} to match agent artifact format)
        content_bytes = json.dumps(final_output).encode("utf-8")

        # Get output schema from workflow definition for artifact metadata
        output_schema = self.workflow_definition.output_schema
        metadata_dict = {
            "description": f"Output from workflow '{self.workflow_name}'",
            "source": "workflow_execution",
            "workflow_name": self.workflow_name,
        }
        if output_schema:
            metadata_dict["schema"] = output_schema

        try:
            save_result = await save_artifact_with_metadata(
                artifact_service=self.artifact_service,
                app_name=self.workflow_name,
                user_id=user_id,
                session_id=session_id,
                filename=output_artifact_name,
                content_bytes=content_bytes,
                mime_type="application/json",
                metadata_dict=metadata_dict,
                timestamp=datetime.now(timezone.utc),
            )

            if save_result["status"] != "success":
                log.error(f"{log_id} Failed to save workflow output artifact: {save_result.get('message')}")
                artifact_version = None
            else:
                artifact_version = save_result.get("data_version")
                log.info(f"{log_id} Created workflow output artifact: {output_artifact_name} v{artifact_version}")
        except Exception as e:
            log.exception(f"{log_id} Error saving workflow output artifact: {e}")
            artifact_version = None

        # Publish completion event
        await self.publish_workflow_event(
            workflow_context,
            WorkflowExecutionResultData(
                type="workflow_execution_result",
                status="success",
                workflow_output=final_output,
            ),
        )

        # Build produced_artifacts list for the response
        produced_artifacts = []
        if artifact_version is not None:
            produced_artifacts.append({
                "filename": output_artifact_name,
                "version": artifact_version,
            })

        # Create response message text that includes artifact reference
        if artifact_version is not None:
            response_text = f"Workflow completed successfully. Output artifact: {output_artifact_name}:v{artifact_version}"
        else:
            response_text = "Workflow completed successfully"

        # Check if this workflow was invoked by another workflow (structured invocation)
        # Check if this was a structured invocation (from gateway, workflow, or agent)
        # This is indicated by either:
        # 1. The is_structured_invocation flag set during request handling, OR
        # 2. Legacy check: replyToTopic containing '/agent/response/'
        reply_to_topic = workflow_context.a2a_context.get("replyToTopic", "")
        is_structured_invocation = workflow_context.a2a_context.get(
            "is_structured_invocation", False
        ) or "/agent/response/" in reply_to_topic

        # Build message parts
        message_parts = []

        if is_structured_invocation and artifact_version is not None:
            # When invoked as a sub-workflow, include StructuredInvocationResult
            # so the parent workflow can process the response
            from ..common.data_parts import ArtifactRef, StructuredInvocationResult
            invocation_result = StructuredInvocationResult(
                type="structured_invocation_result",
                status="success",
                output_artifact_ref=ArtifactRef(
                    name=output_artifact_name, version=artifact_version
                ),
            )
            message_parts.append(a2a.create_data_part(data=invocation_result.model_dump()))

        # Add text part
        message_parts.append(a2a.create_text_part(text=response_text))

        # Create final task response
        final_task = a2a.create_final_task(
            task_id=workflow_context.a2a_context["logical_task_id"],
            context_id=workflow_context.a2a_context["session_id"],
            final_status=a2a.create_task_status(
                state=TaskState.completed,
                message=a2a.create_agent_parts_message(parts=message_parts),
            ),
            metadata={
                "workflow_name": self.workflow_name,
                "agent_name": self.workflow_name,  # For compatibility with peer agent response handling
                "output": final_output,
                "produced_artifacts": produced_artifacts,
            },
        )

        # Publish response
        response_topic = workflow_context.a2a_context.get(
            "replyToTopic"
        ) or a2a.get_client_response_topic(
            self.namespace, workflow_context.a2a_context["client_id"]
        )

        response = a2a.create_success_response(
            result=final_task,
            request_id=workflow_context.a2a_context["jsonrpc_request_id"],
        )

        self.publish_a2a_message(
            payload=response.model_dump(exclude_none=True),
            topic=response_topic,
            user_properties={
                "a2aUserConfig": workflow_context.a2a_context.get("a2a_user_config", {})
            },
        )

        # ACK original message
        original_message = workflow_context.get_original_solace_message()
        if original_message:
            original_message.call_acknowledgements()

        await self._cleanup_workflow_state(workflow_context)

    async def finalize_workflow_failure(
        self, workflow_context: WorkflowExecutionContext, error: Exception
    ):
        """Finalize failed workflow execution and publish error."""
        log_id = f"{self.log_identifier}[Workflow:{workflow_context.workflow_task_id}]"
        log.warning(f"{log_id} Finalizing workflow failure: {error}")

        # Execute exit handlers first (passing error info)
        await self._execute_exit_handlers(workflow_context, "failure", error)

        # Create output artifact with the error information
        # Use unique filename: <workflow_name>_<4-digit-uuid>_result.json
        unique_suffix = uuid.uuid4().hex[:4]
        output_artifact_name = f"{self.workflow_name}_{unique_suffix}_result.json"

        user_id = workflow_context.a2a_context["user_id"]
        session_id = workflow_context.a2a_context["session_id"]

        # Prepare artifact content with status and error
        artifact_content = {
            "status": "error",
            "message": str(error),
        }
        content_bytes = json.dumps(artifact_content).encode("utf-8")

        metadata_dict = {
            "description": f"Error output from workflow '{self.workflow_name}'",
            "source": "workflow_execution",
            "workflow_name": self.workflow_name,
        }

        try:
            save_result = await save_artifact_with_metadata(
                artifact_service=self.artifact_service,
                app_name=self.workflow_name,
                user_id=user_id,
                session_id=session_id,
                filename=output_artifact_name,
                content_bytes=content_bytes,
                mime_type="application/json",
                metadata_dict=metadata_dict,
                timestamp=datetime.now(timezone.utc),
            )

            if save_result["status"] != "success":
                log.error(f"{log_id} Failed to save workflow error artifact: {save_result.get('message')}")
                artifact_version = None
            else:
                artifact_version = save_result.get("data_version")
                log.info(f"{log_id} Created workflow error artifact: {output_artifact_name} v{artifact_version}")
        except Exception as e:
            log.exception(f"{log_id} Error saving workflow error artifact: {e}")
            artifact_version = None

        # Publish failure event
        await self.publish_workflow_event(
            workflow_context,
            WorkflowExecutionResultData(
                type="workflow_execution_result",
                status="error",
                error_message=str(error),
            ),
        )

        # Build produced_artifacts list for the response
        produced_artifacts = []
        if artifact_version is not None:
            produced_artifacts.append({
                "filename": output_artifact_name,
                "version": artifact_version,
            })

        # Create response message text that includes artifact reference
        if artifact_version is not None:
            response_text = f"Workflow failed: {str(error)}. Error artifact: {output_artifact_name}:v{artifact_version}"
        else:
            response_text = f"Workflow failed: {str(error)}"

        # Check if this was a structured invocation (from gateway, workflow, or agent)
        reply_to_topic = workflow_context.a2a_context.get("replyToTopic", "")
        is_structured_invocation = workflow_context.a2a_context.get(
            "is_structured_invocation", False
        ) or "/agent/response/" in reply_to_topic

        # Build message parts
        message_parts = []

        if is_structured_invocation:
            # When invoked as structured invocation, include StructuredInvocationResult
            # so the caller (gateway, workflow, agent) can process the error response
            from ..common.data_parts import ArtifactRef, StructuredInvocationResult
            invocation_result = StructuredInvocationResult(
                type="structured_invocation_result",
                status="error",
                error_message=str(error),
                output_artifact_ref=ArtifactRef(
                    name=output_artifact_name, version=artifact_version
                ) if artifact_version is not None else None,
            )
            message_parts.append(a2a.create_data_part(data=invocation_result.model_dump()))

        # Add text part
        message_parts.append(a2a.create_text_part(text=response_text))

        # Create final task response
        final_task = a2a.create_final_task(
            task_id=workflow_context.a2a_context["logical_task_id"],
            context_id=workflow_context.a2a_context["session_id"],
            final_status=a2a.create_task_status(
                state=TaskState.failed,
                message=a2a.create_agent_parts_message(parts=message_parts),
            ),
            metadata={
                "workflow_name": self.workflow_name,
                "agent_name": self.workflow_name,  # For compatibility with peer agent response handling
                "produced_artifacts": produced_artifacts,
            },
        )

        # Publish response
        response_topic = workflow_context.a2a_context.get(
            "replyToTopic"
        ) or a2a.get_client_response_topic(
            self.namespace, workflow_context.a2a_context["client_id"]
        )

        response = a2a.create_success_response(
            result=final_task,
            request_id=workflow_context.a2a_context["jsonrpc_request_id"],
        )

        self.publish_a2a_message(
            payload=response.model_dump(exclude_none=True),
            topic=response_topic,
            user_properties={
                "a2aUserConfig": workflow_context.a2a_context.get("a2a_user_config", {})
            },
        )

        # ACK original message (we handled the error gracefully)
        original_message = workflow_context.get_original_solace_message()
        if original_message:
            original_message.call_acknowledgements()

        await self._cleanup_workflow_state(workflow_context)

    async def finalize_workflow_cancelled(
        self, workflow_context: WorkflowExecutionContext
    ):
        """Finalize cancelled workflow execution and publish cancellation status."""
        log_id = f"{self.log_identifier}[Workflow:{workflow_context.workflow_task_id}]"
        log.info(f"{log_id} Finalizing workflow cancellation")

        # Execute exit handlers (passing cancellation info)
        await self._execute_exit_handlers(workflow_context, "cancelled")

        # Publish cancellation event
        await self.publish_workflow_event(
            workflow_context,
            WorkflowExecutionResultData(
                type="workflow_execution_result",
                status="cancelled",
                error_message="Workflow was cancelled",
            ),
        )

        # Create final task response with cancelled state
        final_task = a2a.create_final_task(
            task_id=workflow_context.a2a_context["logical_task_id"],
            context_id=workflow_context.a2a_context["session_id"],
            final_status=a2a.create_task_status(
                state=TaskState.canceled,
                message=a2a.create_agent_text_message(
                    text="Workflow was cancelled"
                ),
            ),
            metadata={
                "workflow_name": self.workflow_name,
                "agent_name": self.workflow_name,
            },
        )

        # Publish response
        response_topic = workflow_context.a2a_context.get(
            "replyToTopic"
        ) or a2a.get_client_response_topic(
            self.namespace, workflow_context.a2a_context["client_id"]
        )

        response = a2a.create_success_response(
            result=final_task,
            request_id=workflow_context.a2a_context["jsonrpc_request_id"],
        )

        self.publish_a2a_message(
            payload=response.model_dump(exclude_none=True),
            topic=response_topic,
            user_properties={
                "a2aUserConfig": workflow_context.a2a_context.get("a2a_user_config", {})
            },
        )

        # ACK original message
        original_message = workflow_context.get_original_solace_message()
        if original_message:
            original_message.call_acknowledgements()

        await self._cleanup_workflow_state(workflow_context)
        log.info(f"{log_id} Workflow cancellation finalized")

    async def _construct_final_output(
        self, workflow_context: WorkflowExecutionContext
    ) -> Dict[str, Any]:
        """Construct final output from workflow state using output mapping."""
        mapping = self.workflow_definition.output_mapping
        state = workflow_context.workflow_state

        final_output = {}
        for key, value_def in mapping.items():
            final_output[key] = self.dag_executor.resolve_value(value_def, state)

        return final_output

    async def _update_workflow_state(
        self,
        workflow_context: WorkflowExecutionContext,
        workflow_state: WorkflowExecutionState,
    ):
        """Persist workflow state to session service."""
        session = await self._get_workflow_session(workflow_context)
        session.state["workflow_execution"] = workflow_state.model_dump()
        # Note: Session state is persisted automatically by the SessionService
        # when managed through ADK operations (get_session, append_event, etc.)

    async def _cleanup_workflow_state(self, workflow_context: WorkflowExecutionContext):
        """Clean up workflow state on completion."""
        # Set TTL on session state for auto-cleanup
        session = await self._get_workflow_session(workflow_context)

        # Mark workflow complete
        state = workflow_context.workflow_state
        state.metadata["completion_time"] = datetime.now(timezone.utc).isoformat()
        state.metadata["status"] = "completed"

        session.state["workflow_execution"] = state.model_dump()
        # Note: Session state is persisted automatically by the SessionService

        # Clean up any remaining cache entries for timeout tracking
        # These should normally be removed when nodes complete, but this is a safety net
        for sub_task_id in workflow_context.get_all_sub_task_ids():
            self.cache_service.remove_data(sub_task_id)

        # Remove from active workflows
        with self.active_workflows_lock:
            self.active_workflows.pop(workflow_context.workflow_task_id, None)

    async def _get_workflow_session(self, workflow_context: WorkflowExecutionContext):
        """Retrieve the ADK session for the workflow."""
        return await self.session_service.get_session(
            app_name=self.workflow_name,
            user_id=workflow_context.a2a_context["user_id"],
            session_id=workflow_context.a2a_context["session_id"],
        )

    async def _load_node_output(
        self,
        node_id: str,
        artifact_name: str,
        artifact_version: int,
        workflow_context: WorkflowExecutionContext,
        sub_task_id: Optional[str] = None,
    ) -> Any:
        """Load a node's output artifact.

        Artifacts are namespace-scoped by the ScopedArtifactServiceWrapper,
        so the app_name parameter is automatically transformed to the namespace
        when artifact_scope is "namespace". This allows all agents and workflows
        in the same namespace to access the same artifact store.

        We use the parent workflow session ID to load artifacts, as agents are expected
        to save their outputs to the shared parent session scope.
        """
        user_id = workflow_context.a2a_context["user_id"]
        # Use the parent session ID (caller's session) to ensure artifacts are shared/persisted
        workflow_session_id = workflow_context.a2a_context["session_id"]

        # If sub_task_id is not provided, look it up from the node_id
        if not sub_task_id:
            sub_task_id = workflow_context.get_sub_task_for_node(node_id)
            if not sub_task_id:
                raise ValueError(f"No sub-task ID found for node {node_id}")

        # The app_name doesn't matter in namespace mode - the ScopedArtifactServiceWrapper
        # will replace it with self.namespace. But we pass workflow_name for consistency.
        artifact = await self.artifact_service.load_artifact(
            app_name=self.workflow_name,
            user_id=user_id,
            session_id=workflow_session_id,
            filename=artifact_name,
            version=artifact_version,
        )

        if not artifact or not artifact.inline_data:
            raise ValueError(
                f"Artifact {artifact_name} v{artifact_version} not found in session {workflow_session_id}"
            )

        return json.loads(artifact.inline_data.data.decode("utf-8"))

    def cleanup(self):
        """Clean up resources on component shutdown."""
        log.info(f"{self.log_identifier} Cleaning up workflow executor")

        # Cancel active workflows
        with self.active_workflows_lock:
            for workflow_context in self.active_workflows.values():
                workflow_context.cancel()
            self.active_workflows.clear()

        # Call base class cleanup (stops async loop)
        super().cleanup()
