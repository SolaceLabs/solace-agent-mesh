"""
WorkflowExecutorComponent implementation.
Orchestrates workflow execution by coordinating persona agents.
"""

import logging
import threading
import uuid
import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, Optional, TYPE_CHECKING

from solace_ai_connector.common.message import Message as SolaceMessage
from solace_ai_connector.common.event import Event, EventType

from ..common import a2a
from ..common.sac.sam_component_base import SamComponentBase
from ..common.agent_registry import AgentRegistry
from ..agent.adk.services import (
    initialize_session_service,
    initialize_artifact_service,
)
from .app import WorkflowDefinition
from .workflow_execution_context import WorkflowExecutionContext, WorkflowExecutionState
from .dag_executor import DAGExecutor, WorkflowNodeFailureError
from .persona_caller import PersonaCaller
from .protocol.event_handlers import (
    handle_task_request,
    handle_persona_response,
    handle_cancel_request,
    handle_agent_card_message,
)

from a2a.types import (
    AgentCard,
    AgentCapabilities,
    TaskState,
    TaskStatusUpdateEvent,
)

log = logging.getLogger(__name__)

info = {
    "class_name": "WorkflowExecutorComponent",
    "description": "Orchestrates workflow execution by coordinating persona agents.",
    "config_parameters": [],
}


class WorkflowExecutorComponent(SamComponentBase):
    """
    Orchestrates workflow execution by coordinating persona agents.

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
        self.persona_caller = PersonaCaller(self)

        # Create agent registry for persona discovery
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
        request_topic = a2a.get_agent_request_topic(
            self.namespace, self.workflow_name
        )
        discovery_topic = a2a.get_discovery_topic(self.namespace)
        response_sub = a2a.get_agent_response_subscription_topic(
            self.namespace, self.workflow_name
        )
        status_sub = a2a.get_agent_status_subscription_topic(
            self.namespace, self.workflow_name
        )

        if topic == request_topic:
            await handle_task_request(self, message)
        elif topic == discovery_topic:
            handle_agent_card_message(self, message)
        elif a2a.topic_matches_subscription(
            topic, response_sub
        ) or a2a.topic_matches_subscription(topic, status_sub):
            await handle_persona_response(self, message)
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
            discovery_topic = a2a.get_discovery_topic(self.namespace)
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

    def _create_workflow_agent_card(self) -> AgentCard:
        """Create the workflow agent card."""
        # Build extensions list
        extensions_list = []

        # Add schema extension if schemas are defined
        SCHEMAS_EXTENSION_URI = "https://solace.com/a2a/extensions/sam/schemas"
        input_schema = self.workflow_definition.input_schema
        output_schema = self.workflow_definition.output_schema

        if input_schema or output_schema:
            schema_params = {}
            if input_schema:
                schema_params["input_schema"] = input_schema
            if output_schema:
                schema_params["output_schema"] = output_schema

            from a2a.types import AgentExtension
            schemas_extension = AgentExtension(
                uri=SCHEMAS_EXTENSION_URI,
                description="Input and output JSON schemas for the workflow.",
                params=schema_params,
            )
            extensions_list.append(schemas_extension)

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
            version="1.0.0",
            url=f"solace:{a2a.get_agent_request_topic(self.namespace, self.workflow_name)}",
        )


    async def handle_cache_expiry_event(self, cache_data: Dict[str, Any]):
        """Handle persona call timeout via cache expiry."""
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
            f"{self.log_identifier} Persona call timed out for node '{node_id}' "
            f"(sub-task: {sub_task_id})"
        )

        # Create timeout error
        from ..common.data_parts import WorkflowNodeResultData

        result_data = WorkflowNodeResultData(
            type="workflow_node_result",
            status="failure",
            error_message=f"Persona agent timed out after {timeout_seconds} seconds",
        )

        # Handle as node failure
        await self.dag_executor.handle_node_completion(
            workflow_context, sub_task_id, result_data
        )

    async def finalize_workflow_success(self, workflow_context: WorkflowExecutionContext):
        """Finalize successful workflow execution and publish result."""
        log_id = f"{self.log_identifier}[Workflow:{workflow_context.workflow_task_id}]"
        log.info(f"{log_id} Finalizing workflow success")

        # Construct final output based on output mapping
        final_output = await self._construct_final_output(workflow_context)

        # Create final result artifact if needed, or just pass data
        # For MVP, we'll assume the output is small enough to pass in metadata or as text
        # But A2A protocol expects artifacts or text.

        # Create final task response
        final_task = a2a.create_final_task(
            task_id=workflow_context.a2a_context["logical_task_id"],
            context_id=workflow_context.a2a_context["session_id"],
            final_status=a2a.create_task_status(
                state=TaskState.completed,
                message=a2a.create_agent_text_message(
                    text="Workflow completed successfully"
                ),
            ),
            metadata={
                "workflow_name": self.workflow_name,
                "output": final_output # Pass output in metadata for now
            },
        )

        # Publish response
        response_topic = workflow_context.a2a_context.get("replyToTopic") or a2a.get_client_response_topic(
            self.namespace, workflow_context.a2a_context["client_id"]
        )

        response = a2a.create_success_response(
            result=final_task,
            request_id=workflow_context.a2a_context["jsonrpc_request_id"],
        )

        # DEBUG: Log task ID when sending success response to gateway/client
        log.error(
            f"{log_id} [TASK_ID_DEBUG] SENDING workflow SUCCESS response to gateway/client | "
            f"logical_task_id={workflow_context.a2a_context['logical_task_id']} | "
            f"jsonrpc_request_id={workflow_context.a2a_context['jsonrpc_request_id']} | "
            f"response_topic={response_topic} | "
            f"client_id={workflow_context.a2a_context.get('client_id')} | "
            f"context_id={workflow_context.a2a_context['session_id']}"
        )

        self.publish_a2a_message(
            payload=response.model_dump(exclude_none=True),
            topic=response_topic,
            user_properties={"a2aUserConfig": workflow_context.a2a_context.get("a2a_user_config", {})},
        )

        # ACK original message
        original_message = workflow_context.a2a_context.get("original_solace_message")
        if original_message:
            original_message.call_acknowledgements()

        await self._cleanup_workflow_state(workflow_context)

    async def finalize_workflow_failure(
        self, workflow_context: WorkflowExecutionContext, error: Exception
    ):
        """Finalize failed workflow execution and publish error."""
        log_id = f"{self.log_identifier}[Workflow:{workflow_context.workflow_task_id}]"
        log.warning(f"{log_id} Finalizing workflow failure: {error}")

        # Create final task response
        final_task = a2a.create_final_task(
            task_id=workflow_context.a2a_context["logical_task_id"],
            context_id=workflow_context.a2a_context["session_id"],
            final_status=a2a.create_task_status(
                state=TaskState.failed,
                message=a2a.create_agent_text_message(
                    text=f"Workflow failed: {str(error)}"
                ),
            ),
            metadata={"workflow_name": self.workflow_name},
        )

        # Publish response
        response_topic = workflow_context.a2a_context.get("replyToTopic") or a2a.get_client_response_topic(
            self.namespace, workflow_context.a2a_context["client_id"]
        )

        response = a2a.create_success_response(
            result=final_task,
            request_id=workflow_context.a2a_context["jsonrpc_request_id"],
        )

        # DEBUG: Log task ID when sending failure response to gateway/client
        log.error(
            f"{log_id} [TASK_ID_DEBUG] SENDING workflow FAILURE response to gateway/client | "
            f"logical_task_id={workflow_context.a2a_context['logical_task_id']} | "
            f"jsonrpc_request_id={workflow_context.a2a_context['jsonrpc_request_id']} | "
            f"response_topic={response_topic} | "
            f"client_id={workflow_context.a2a_context.get('client_id')} | "
            f"context_id={workflow_context.a2a_context['session_id']} | "
            f"error={str(error)}"
        )

        self.publish_a2a_message(
            payload=response.model_dump(exclude_none=True),
            topic=response_topic,
            user_properties={"a2aUserConfig": workflow_context.a2a_context.get("a2a_user_config", {})},
        )

        # ACK original message (we handled the error gracefully)
        original_message = workflow_context.a2a_context.get("original_solace_message")
        if original_message:
            original_message.call_acknowledgements()
            
        await self._cleanup_workflow_state(workflow_context)

    async def _construct_final_output(self, workflow_context: WorkflowExecutionContext) -> Dict[str, Any]:
        """Construct final output from workflow state using output mapping."""
        mapping = self.workflow_definition.output_mapping
        state = workflow_context.workflow_state
        
        final_output = {}
        for key, template in mapping.items():
            if isinstance(template, str) and template.startswith("{{"):
                value = self.dag_executor._resolve_template(template, state)
                final_output[key] = value
            else:
                final_output[key] = template
                
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
        self, artifact_name: str, artifact_version: int, workflow_context: WorkflowExecutionContext
    ) -> Any:
        """Load a node's output artifact.

        Artifacts are namespace-scoped, so all agents and workflows in the same
        namespace can access the same artifact store regardless of which component
        created them.
        """
        import json

        artifact = await self.artifact_service.load_artifact(
            app_name=self.workflow_name,
            user_id=workflow_context.a2a_context["user_id"],
            session_id=workflow_context.a2a_context["session_id"],
            filename=artifact_name,
            version=artifact_version
        )

        if not artifact or not artifact.inline_data:
            raise ValueError(f"Artifact {artifact_name} v{artifact_version} not found")
            
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
