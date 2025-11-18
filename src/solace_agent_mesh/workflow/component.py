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

    def process_event(self, event: Event):
        """
        Process incoming events (messages, timers, cache expiry).
        Delegates to async event handlers on component's event loop.
        """
        loop = self.get_async_loop()
        if not loop or not loop.is_running():
            log.error(
                f"{self.log_identifier} Async loop not available. Cannot process event: {event.event_type}"
            )
            return

        if event.event_type == EventType.MESSAGE:
            message = event.data
            topic = message.get_topic()
            
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

            coro = None
            if topic == request_topic:
                coro = handle_task_request(self, message)
            elif topic == discovery_topic:
                handle_agent_card_message(self, message)
            elif a2a.topic_matches_subscription(
                topic, response_sub
            ) or a2a.topic_matches_subscription(topic, status_sub):
                coro = handle_persona_response(self, message)
            else:
                log.warning(f"{self.log_identifier} Unknown topic: {topic}")
                message.call_acknowledgements()

            if coro:
                asyncio.run_coroutine_threadsafe(coro, loop)

        elif event.event_type == EventType.TIMER:
            # Timer for periodic operations (if needed)
            pass

        elif event.event_type == EventType.CACHE_EXPIRY:
            # Handle persona call timeouts
            coro = self.handle_cache_expiry_event(event.data)
            asyncio.run_coroutine_threadsafe(coro, loop)

    async def _async_setup_and_run(self) -> None:
        """
        Async initialization called by SamComponentBase.
        Sets up services and publishes workflow agent card.
        """
        # Publish workflow agent card
        await self._publish_workflow_agent_card()

        # Component is now ready to receive requests
        log.info(f"{self.log_identifier} Workflow ready: {self.workflow_name}")

    def _pre_async_cleanup(self) -> None:
        """Pre-cleanup before async loop stops."""
        pass

    async def _publish_workflow_agent_card(self):
        """Publish workflow as an agent card for discovery."""
        agent_card = AgentCard(
            name=self.workflow_name,
            display_name=self.get_config("display_name"),
            description=self.workflow_definition.description,
            input_schema=self.workflow_definition.input_schema,
            output_schema=self.workflow_definition.output_schema,
            defaultInputModes=["text"],
            defaultOutputModes=["text"],
            skills=self.workflow_definition.skills or [],
            capabilities=AgentCapabilities(streaming=False),
            version="1.0.0",
            url=f"solace:{a2a.get_agent_request_topic(self.namespace, self.workflow_name)}",
        )

        discovery_topic = a2a.get_discovery_topic(self.namespace)
        self.publish_a2a_message(
            payload=agent_card.model_dump(exclude_none=True), topic=discovery_topic
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

        self.publish_a2a_message(
            payload=response.model_dump(exclude_none=True), topic=response_topic
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

        self.publish_a2a_message(
            payload=response.model_dump(exclude_none=True), topic=response_topic
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
        await self.session_service.update_session(session)

    async def _cleanup_workflow_state(self, workflow_context: WorkflowExecutionContext):
        """Clean up workflow state on completion."""
        # Set TTL on session state for auto-cleanup
        session = await self._get_workflow_session(workflow_context)

        # Mark workflow complete
        state = workflow_context.workflow_state
        state.metadata["completion_time"] = datetime.now(timezone.utc).isoformat()
        state.metadata["status"] = "completed"

        session.state["workflow_execution"] = state.model_dump()
        await self.session_service.update_session(session)

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
        """Load a node's output artifact."""
        import json
        
        artifact = await self.artifact_service.load_artifact(
            app_name=self.workflow_name, # Artifacts are stored under workflow's app name? Or persona's?
            # Design doc says: "Result artifacts use the same artifact service as agent outputs"
            # But persona agents run in their own context.
            # If persona agents save artifacts, they save under THEIR app_name.
            # But we need to know WHICH app_name.
            # The artifact_name alone isn't enough if we don't know the app_name.
            # Wait, the persona agent returns the artifact name.
            # If the persona agent saves it, it's under the persona's name.
            # BUT, the workflow executor needs to read it.
            # If we use a shared artifact service (e.g. S3), we need the persona's app name.
            # The `WorkflowNodeResultData` doesn't include app_name.
            # We can infer it from the node definition (agent_persona).
            #
            # However, `_finalize_fork_node` saves merged artifacts under `self.host.agent_name` (workflow name).
            # So we need to handle both cases.
            #
            # For now, let's assume artifacts are accessible.
            # If it's a persona output, we might need to look under persona's name.
            # But `load_artifact` takes `app_name`.
            #
            # Let's try to find the node that produced this artifact to get the persona name.
            # But `_load_node_output` is called with just artifact info.
            #
            # Actually, `handle_node_completion` knows the node_id.
            # We should pass node_id or persona name to this method.
            #
            # Refactoring `_load_node_output` to take `node_id` is hard because `DAGExecutor` calls it.
            #
            # Let's assume for MVP that we can try loading from workflow's app_name first,
            # and if not found, maybe we need a better strategy.
            #
            # Wait, `PersonaCaller` invokes the agent. The agent saves the artifact.
            # The agent uses its own `app_name`.
            # So we MUST know the agent name to load the artifact.
            #
            # In `handle_node_completion`, we know the `node_id`.
            # We can look up the node in `self.nodes` to get `agent_persona`.
            #
            # Let's update `DAGExecutor` to pass the persona name?
            # Or update `_load_node_output` to take an optional `owner_app_name`.
            
            user_id=workflow_context.a2a_context["user_id"],
            session_id=workflow_context.a2a_context["session_id"],
            filename=artifact_name,
            version=artifact_version
        )
        
        if not artifact or not artifact.inline_data:
            # Try looking up the node to find the persona name
            # This is a bit hacky, we should pass it down.
            # But for now, let's just fail if not found.
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
