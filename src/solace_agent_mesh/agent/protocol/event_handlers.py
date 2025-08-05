"""
Contains event handling logic for the A2A_ADK_HostComponent.
"""

import json
import yaml
import asyncio
from typing import Union, TYPE_CHECKING, List, Dict, Any
import fnmatch
from solace_ai_connector.common.log import log
from solace_ai_connector.common.message import Message as SolaceMessage
from solace_ai_connector.common.event import Event, EventType
from ...common.types import (
    Message as A2AMessage,
    SendTaskRequest,
    SendTaskStreamingRequest,
    CancelTaskRequest,
    GetTaskRequest,
    SetTaskPushNotificationRequest,
    GetTaskPushNotificationRequest,
    TaskResubscriptionRequest,
    TaskIdParams,
    JSONParseError,
    InvalidRequestError,
    InternalError,
    JSONRPCResponse,
    AgentCard,
    AgentCapabilities,
    Task,
    TaskStatusUpdateEvent,
    TaskArtifactUpdateEvent,
    TaskStatus,
    TaskState,
    DataPart,
    TextPart,
    A2ARequest,
)
from ...common.a2a_protocol import (
    get_agent_request_topic,
    get_discovery_topic,
    translate_a2a_to_adk_content,
    get_client_response_topic,
    get_agent_response_subscription_topic,
    get_agent_status_subscription_topic,
    _extract_text_from_parts,
)
from ...agent.utils.artifact_helpers import (
    generate_artifact_metadata_summary,
    load_artifact_content_or_metadata,
)
from ...agent.adk.runner import run_adk_async_task_thread_wrapper
from ..sac.task_execution_context import TaskExecutionContext
from google.adk.agents import RunConfig

if TYPE_CHECKING:
    from ..sac.component import SamAgentComponent
from google.adk.agents.run_config import StreamingMode
from google.adk.events import Event as ADKEvent
from google.genai import types as adk_types




def _register_peer_artifacts_in_parent_context(
    parent_task_context: "TaskExecutionContext",
    peer_task_object: Task,
    log_identifier: str,
):
    """
    Registers artifacts produced by a peer agent in the parent agent's
    task execution context, allowing them to be "bubbled up".
    """
    if not parent_task_context:
        return

    if peer_task_object.metadata and "produced_artifacts" in peer_task_object.metadata:
        peer_artifacts = peer_task_object.metadata.get("produced_artifacts", [])
        if not peer_artifacts:
            return

        log.debug(
            "%s Registering %d artifacts from peer response into parent task context.",
            log_identifier,
            len(peer_artifacts),
        )
        for artifact_ref in peer_artifacts:
            filename = artifact_ref.get("filename")
            version = artifact_ref.get("version")
            if filename and version is not None:
                parent_task_context.register_produced_artifact(
                    filename=filename,
                    version=version,
                )


async def process_event(component, event: Event):
    """
    Processes incoming events (Messages, Timers, etc.). Routes to specific handlers.
    Args:
        component: The A2A_ADK_HostComponent instance.
        event: The event object received from the SAC framework.
    """
    try:
        if event.event_type == EventType.MESSAGE:
            message = event.data
            topic = message.get_topic()
            if not topic:
                log.warning(
                    "%s Received message without topic. Ignoring.",
                    component.log_identifier,
                )
                return
            if component.invocation_monitor:
                component.invocation_monitor.log_message_event(
                    direction="RECEIVED",
                    topic=topic,
                    payload=message.get_payload(),
                    component_identifier=component.log_identifier,
                )
            else:
                log.warning(
                    f"{component.log_identifier} InvocationMonitor not available in component for event on topic {topic}"
                )
            namespace = component.get_config("namespace")
            agent_name = component.get_config("agent_name")
            agent_request_topic = get_agent_request_topic(namespace, agent_name)
            discovery_topic = get_discovery_topic(namespace)
            agent_response_sub_prefix = (
                get_agent_response_subscription_topic(namespace, agent_name)[:-2] + "/"
            )
            agent_status_sub_prefix = (
                get_agent_status_subscription_topic(namespace, agent_name)[:-2] + "/"
            )
            if topic == agent_request_topic:
                await handle_a2a_request(component, message)
            elif topic == discovery_topic:
                payload = message.get_payload()
                if isinstance(payload, dict) and payload.get("name") != agent_name:
                    handle_agent_card_message(component, message)
                else:
                    message.call_acknowledgements()
            elif topic.startswith(agent_response_sub_prefix) or topic.startswith(
                agent_status_sub_prefix
            ):
                await handle_a2a_response(component, message)
            else:
                log.warning(
                    "%s Received message on unhandled topic: %s",
                    component.log_identifier,
                    topic,
                )
                message.call_acknowledgements()
        elif event.event_type == EventType.TIMER:
            timer_data = event.data
            log.debug(
                "%s Received timer event: %s", component.log_identifier, timer_data
            )
            if timer_data.get("timer_id") == component._card_publish_timer_id:
                publish_agent_card(component)
        elif event.event_type == EventType.CACHE_EXPIRY:
            # Delegate cache expiry handling to the component itself.
            await component.handle_cache_expiry_event(event.data)
        else:
            log.warning(
                "%s Received unknown event type: %s",
                component.log_identifier,
                event.event_type,
            )
    except Exception as e:
        log.exception(
            "%s Unhandled error in process_event: %s", component.log_identifier, e
        )
        if event.event_type == EventType.MESSAGE:
            try:
                event.data.call_negative_acknowledgements()
                log.warning(
                    "%s NACKed message due to error in process_event.",
                    component.log_identifier,
                )
            except Exception as nack_e:
                log.error(
                    "%s Failed to NACK message after error in process_event: %s",
                    component.log_identifier,
                    nack_e,
                )
        component.handle_error(e, event)


async def handle_a2a_request(component, message: SolaceMessage):
    """
    Handles an incoming A2A request message.
    Starts the ADK runner for SendTask/SendTaskStreaming requests.
    Handles CancelTask requests directly.
    Stores the original SolaceMessage in context for the ADK runner to ACK/NACK.
    """
    log.info(
        "%s Received new A2A request on topic: %s",
        component.log_identifier,
        message.get_topic(),
    )
    a2a_context = {}
    adk_session = None
    jsonrpc_request_id = None
    logical_task_id = None
    client_id = message.get_user_properties().get("clientId", "default_client")
    status_topic_from_peer = message.get_user_properties().get("a2aStatusTopic")
    reply_topic_from_peer = message.get_user_properties().get("replyTo")
    namespace = component.get_config("namespace")
    a2a_user_config = message.get_user_properties().get("a2aUserConfig", {})
    if not isinstance(a2a_user_config, dict):
        log.warning(
            "%s 'a2aUserConfig' user property is not a dictionary, received: %s. Defaulting to empty dict.",
            component.log_identifier,
            type(a2a_user_config),
        )
        a2a_user_config = {}
    log.debug(
        "%s Extracted 'a2aUserConfig': %s",
        component.log_identifier,
        a2a_user_config,
    )
    try:
        payload_dict = message.get_payload()
        if not isinstance(payload_dict, dict):
            raise ValueError("Payload is not a dictionary.")
        jsonrpc_request_id = payload_dict.get("id")
        a2a_request: Union[
            SendTaskRequest,
            SendTaskStreamingRequest,
            CancelTaskRequest,
            GetTaskRequest,
            SetTaskPushNotificationRequest,
            GetTaskPushNotificationRequest,
            TaskResubscriptionRequest,
        ] = A2ARequest.validate_python(payload_dict)
        jsonrpc_request_id = a2a_request.id
        logical_task_id = a2a_request.params.id
        if isinstance(a2a_request, CancelTaskRequest):
            log.info(
                "%s Received CancelTaskRequest for Task ID: %s.",
                component.log_identifier,
                logical_task_id,
            )
            task_context = None
            with component.active_tasks_lock:
                task_context = component.active_tasks.get(logical_task_id)

            if task_context:
                task_context.cancel()
                log.info(
                    "%s Sent cancellation signal to ADK task %s.",
                    component.log_identifier,
                    logical_task_id,
                )

                peer_sub_tasks = task_context.peer_sub_tasks
                if peer_sub_tasks:
                    for sub_task_info in peer_sub_tasks:
                        sub_task_id = sub_task_info.get("sub_task_id")
                        target_peer_agent_name = sub_task_info.get("peer_agent_name")
                        if sub_task_id and target_peer_agent_name:
                            log.info(
                                "%s Attempting to cancel peer sub-task %s for agent %s (main task %s).",
                                component.log_identifier,
                                sub_task_id,
                                target_peer_agent_name,
                                logical_task_id,
                            )
                            try:
                                peer_cancel_params = TaskIdParams(id=sub_task_id)
                                peer_cancel_request = CancelTaskRequest(
                                    params=peer_cancel_params
                                )
                                peer_cancel_user_props = {
                                    "clientId": component.agent_name
                                }
                                component._publish_a2a_message(
                                    payload=peer_cancel_request.model_dump(
                                        exclude_none=True
                                    ),
                                    topic=component._get_agent_request_topic(
                                        target_peer_agent_name
                                    ),
                                    user_properties=peer_cancel_user_props,
                                )
                                log.info(
                                    "%s Sent CancelTaskRequest to peer %s for sub-task %s.",
                                    component.log_identifier,
                                    target_peer_agent_name,
                                    sub_task_id,
                                )
                            except Exception as e_peer_cancel:
                                log.error(
                                    "%s Failed to send CancelTaskRequest to peer %s for sub-task %s: %s",
                                    component.log_identifier,
                                    target_peer_agent_name,
                                    sub_task_id,
                                    e_peer_cancel,
                                )
                        else:
                            log.warning(
                                "%s Peer info for main task %s incomplete, cannot cancel peer task. Info: %s",
                                component.log_identifier,
                                logical_task_id,
                                sub_task_info,
                            )
            else:
                log.info(
                    "%s No active task found for cancellation (ID: %s) or task already completed. Ignoring signal.",
                    component.log_identifier,
                    logical_task_id,
                )
            try:
                message.call_acknowledgements()
                log.debug(
                    "%s ACKed CancelTaskRequest for Task ID: %s.",
                    component.log_identifier,
                    logical_task_id,
                )
            except Exception as ack_e:
                log.error(
                    "%s Failed to ACK CancelTaskRequest for Task ID %s: %s",
                    component.log_identifier,
                    logical_task_id,
                    ack_e,
                )
            return None
        elif isinstance(a2a_request, (SendTaskRequest, SendTaskStreamingRequest)):
            original_session_id = a2a_request.params.sessionId
            task_id = a2a_request.params.id
            task_metadata = a2a_request.params.metadata or {}
            system_purpose = task_metadata.get("system_purpose")
            response_format = task_metadata.get("response_format")
            session_behavior_from_meta = task_metadata.get("sessionBehavior")
            if session_behavior_from_meta:
                session_behavior = str(session_behavior_from_meta).upper()
                if session_behavior not in ["PERSISTENT", "RUN_BASED"]:
                    log.warning(
                        "%s Invalid 'sessionBehavior' in task metadata: '%s'. Using component default: '%s'.",
                        component.log_identifier,
                        session_behavior,
                        component.default_session_behavior,
                    )
                    session_behavior = component.default_session_behavior
                else:
                    log.info(
                        "%s Using 'sessionBehavior' from task metadata: '%s'.",
                        component.log_identifier,
                        session_behavior,
                    )
            else:
                session_behavior = component.default_session_behavior
                log.info(
                    "%s No 'sessionBehavior' in task metadata. Using component default: '%s'.",
                    component.log_identifier,
                    session_behavior,
                )
            user_id = message.get_user_properties().get("userId", "default_user")
            agent_name = component.get_config("agent_name")
            is_streaming_request = isinstance(a2a_request, SendTaskStreamingRequest)
            host_supports_streaming = component.get_config("supports_streaming", False)
            if is_streaming_request and not host_supports_streaming:
                raise ValueError(
                    "Host does not support streaming (tasks/sendSubscribe) requests."
                )
            effective_session_id = original_session_id
            is_run_based_session = False
            temporary_run_session_id_for_cleanup = None
            if session_behavior == "RUN_BASED":
                is_run_based_session = True
                effective_session_id = f"{original_session_id}:{task_id}:run"
                temporary_run_session_id_for_cleanup = effective_session_id
                log.info(
                    "%s Session behavior is RUN_BASED. OriginalID='%s', EffectiveID for this run='%s', TaskID='%s'.",
                    component.log_identifier,
                    original_session_id,
                    effective_session_id,
                    task_id,
                )
            else:
                is_run_based_session = False
                effective_session_id = original_session_id
                temporary_run_session_id_for_cleanup = None
                log.info(
                    "%s Session behavior is PERSISTENT. EffectiveID='%s' for TaskID='%s'.",
                    component.log_identifier,
                    effective_session_id,
                    task_id,
                )
            adk_session_for_run = await component.session_service.get_session(
                app_name=agent_name, user_id=user_id, session_id=effective_session_id
            )
            if adk_session_for_run is None:
                adk_session_for_run = await component.session_service.create_session(
                    app_name=agent_name,
                    user_id=user_id,
                    session_id=effective_session_id,
                )
                log.info(
                    "%s Created new ADK session '%s' for task '%s'.",
                    component.log_identifier,
                    effective_session_id,
                    task_id,
                )
            else:
                log.info(
                    "%s Reusing existing ADK session '%s' for task '%s'.",
                    component.log_identifier,
                    effective_session_id,
                    task_id,
                )
            if is_run_based_session:
                try:
                    original_adk_session_data = (
                        await component.session_service.get_session(
                            app_name=agent_name,
                            user_id=user_id,
                            session_id=original_session_id,
                        )
                    )
                    if original_adk_session_data and hasattr(
                        original_adk_session_data, "history"
                    ):
                        original_history_events = original_adk_session_data.history
                        if original_history_events:
                            log.debug(
                                "%s Copying %d events from original session '%s' to run-based session '%s'.",
                                component.log_identifier,
                                len(original_history_events),
                                original_session_id,
                                effective_session_id,
                            )
                            run_based_adk_session_for_copy = (
                                await component.session_service.create_session(
                                    app_name=agent_name,
                                    user_id=user_id,
                                    session_id=effective_session_id,
                                )
                            )
                            for event_to_copy in original_history_events:
                                await component.session_service.append_event(
                                    session=run_based_adk_session_for_copy,
                                    event=event_to_copy,
                                )
                        else:
                            log.debug(
                                "%s No history to copy from original session '%s' for run-based task '%s'.",
                                component.log_identifier,
                                original_session_id,
                                task_id,
                            )
                    else:
                        log.debug(
                            "%s Original session '%s' not found or has no history, cannot copy for run-based task '%s'.",
                            component.log_identifier,
                            original_session_id,
                            task_id,
                        )
                except Exception as e_copy:
                    log.error(
                        "%s Error copying history for run-based session '%s' (task '%s'): %s. Proceeding with empty session.",
                        component.log_identifier,
                        effective_session_id,
                        task_id,
                        e_copy,
                    )
            a2a_context = {
                "jsonrpc_request_id": jsonrpc_request_id,
                "logical_task_id": logical_task_id,
                "session_id": original_session_id,
                "user_id": user_id,
                "client_id": client_id,
                "is_streaming": is_streaming_request,
                "statusTopic": status_topic_from_peer,
                "replyToTopic": reply_topic_from_peer,
                "original_solace_message": message,
                "a2a_user_config": a2a_user_config,
                "effective_session_id": effective_session_id,
                "is_run_based_session": is_run_based_session,
                "temporary_run_session_id_for_cleanup": temporary_run_session_id_for_cleanup,
                "agent_name_for_session": (
                    agent_name if is_run_based_session else None
                ),
                "user_id_for_session": user_id if is_run_based_session else None,
                "system_purpose": system_purpose,
                "response_format": response_format,
                "host_agent_name": agent_name,
            }
            log.debug(
                "%s A2A Context (shared service model): %s",
                component.log_identifier,
                a2a_context,
            )

            # Create and store the execution context for this task
            task_context = TaskExecutionContext(
                task_id=logical_task_id, a2a_context=a2a_context
            )
            with component.active_tasks_lock:
                component.active_tasks[logical_task_id] = task_context
            log.info(
                "%s Created and stored new TaskExecutionContext for task %s.",
                component.log_identifier,
                logical_task_id,
            )

            a2a_message_for_adk = a2a_request.params.message
            invoked_artifacts = (
                a2a_message_for_adk.metadata.get("invoked_with_artifacts", [])
                if a2a_message_for_adk.metadata
                else []
            )

            if invoked_artifacts:
                log.info(
                    "%s Task %s invoked with %d artifact(s). Preparing context from metadata.",
                    component.log_identifier,
                    task_id,
                    len(invoked_artifacts),
                )
                header_text = (
                    "The user has provided the following artifacts as context for your task. "
                    "Use the information contained within their metadata to complete your objective."
                )
                artifact_summary = await generate_artifact_metadata_summary(
                    component=component,
                    artifact_identifiers=invoked_artifacts,
                    user_id=user_id,
                    session_id=effective_session_id,
                    app_name=agent_name,
                    header_text=header_text,
                )

                task_description = _extract_text_from_parts(
                    a2a_message_for_adk.parts
                )
                final_prompt = f"{task_description}\n\n{artifact_summary}"

                a2a_message_for_adk = A2AMessage(
                    role="user",
                    parts=[TextPart(text=final_prompt)],
                    metadata=a2a_message_for_adk.metadata,
                )
                log.debug(
                    "%s Generated new prompt for task %s with artifact context.",
                    component.log_identifier,
                    task_id,
                )

            adk_content = translate_a2a_to_adk_content(
                a2a_message_for_adk, component.log_identifier
            )

            adk_session = await component.session_service.get_session(
                app_name=agent_name, user_id=user_id, session_id=effective_session_id
            )
            if adk_session is None:
                log.info(
                    "%s ADK session '%s' not found in component.session_service, creating new one.",
                    component.log_identifier,
                    effective_session_id,
                )
                adk_session = await component.session_service.create_session(
                    app_name=agent_name,
                    user_id=user_id,
                    session_id=effective_session_id,
                )
            else:
                log.info(
                    "%s Reusing existing ADK session '%s' from component.session_service.",
                    component.log_identifier,
                    effective_session_id,
                )

            # Always use SSE streaming mode for the ADK runner.
            # This ensures that real-time callbacks (e.g., for fenced artifact
            # progress) can function correctly for all task types. The component's
            # internal logic uses the 'is_run_based_session' flag to differentiate
            # between aggregating a final response and streaming partial updates.
            streaming_mode = StreamingMode.SSE

            max_llm_calls_per_task = component.get_config("max_llm_calls_per_task", 20)
            log.info(
                "%s Using max_llm_calls_per_task: %s",
                component.log_identifier,
                max_llm_calls_per_task,
            )

            run_config = RunConfig(
                streaming_mode=streaming_mode, max_llm_calls=max_llm_calls_per_task
            )
            log.info(
                "%s Setting ADK RunConfig streaming_mode to: %s, max_llm_calls to: %s",
                component.log_identifier,
                streaming_mode,
                max_llm_calls_per_task,
            )

            log.info(
                "%s Starting ADK runner task for request %s (Task ID: %s)",
                component.log_identifier,
                jsonrpc_request_id,
                logical_task_id,
            )

            await run_adk_async_task_thread_wrapper(
                component,
                adk_session,
                adk_content,
                run_config,
                a2a_context,
            )

            log.info(
                "%s ADK task execution awaited for Task ID %s.",
                component.log_identifier,
                logical_task_id,
            )

        else:
            log.warning(
                "%s Received unhandled A2A request type: %s. Acknowledging.",
                component.log_identifier,
                type(a2a_request).__name__,
            )
            try:
                message.call_acknowledgements()
            except Exception as ack_e:
                log.error(
                    "%s Failed to ACK unhandled request type %s: %s",
                    component.log_identifier,
                    type(a2a_request).__name__,
                    ack_e,
                )
            return None

    except (json.JSONDecodeError, ValueError, TypeError) as e:
        log.error(
            "%s Failed to parse, validate, or start ADK task for A2A request: %s",
            component.log_identifier,
            e,
        )
        error_data = {"taskId": logical_task_id} if logical_task_id else None
        if isinstance(e, ValueError):
            error_response = JSONRPCResponse(
                id=jsonrpc_request_id,
                error=InvalidRequestError(message=str(e), data=error_data),
            )
        else:
            error_response = JSONRPCResponse(
                id=jsonrpc_request_id,
                error=JSONParseError(message=str(e), data=error_data),
            )

        target_topic = reply_topic_from_peer or (
            get_client_response_topic(namespace, client_id) if client_id else None
        )
        if target_topic:
            component._publish_a2a_message(
                error_response.model_dump(exclude_none=True),
                target_topic,
            )

        try:
            message.call_negative_acknowledgements()
            log.warning(
                "%s NACKed original A2A request due to parsing/validation/start error.",
                component.log_identifier,
            )
        except Exception as nack_e:
            log.error(
                "%s Failed to NACK message after pre-start error: %s",
                component.log_identifier,
                nack_e,
            )

        component.handle_error(e, Event(EventType.MESSAGE, message))
        return None

    except Exception as e:
        log.exception(
            "%s Unexpected error handling A2A request: %s", component.log_identifier, e
        )
        error_response = JSONRPCResponse(
            id=jsonrpc_request_id,
            error=InternalError(
                message=f"Unexpected server error: {e}",
                data={"taskId": logical_task_id},
            ),
        )
        target_topic = reply_topic_from_peer or (
            get_client_response_topic(namespace, client_id) if client_id else None
        )
        if target_topic:
            component._publish_a2a_message(
                error_response.model_dump(exclude_none=True),
                target_topic,
            )

        try:
            message.call_negative_acknowledgements()
            log.warning(
                "%s NACKed original A2A request due to unexpected error.",
                component.log_identifier,
            )
        except Exception as nack_e:
            log.error(
                "%s Failed to NACK message after unexpected error: %s",
                component.log_identifier,
                nack_e,
            )

        component.handle_error(e, Event(EventType.MESSAGE, message))
        return None


def handle_agent_card_message(component, message: SolaceMessage):
    """Handles incoming Agent Card messages."""
    try:
        payload = message.get_payload()
        if not isinstance(payload, dict):
            log.warning(
                "%s Received agent card with non-dict payload. Ignoring.",
                component.log_identifier,
            )
            message.call_acknowledgements()
            return

        agent_card = AgentCard(**payload)
        agent_name = agent_card.name
        self_agent_name = component.get_config("agent_name")

        if agent_name == self_agent_name:
            message.call_acknowledgements()
            return

        agent_discovery = component.get_config("agent_discovery", {})
        if agent_discovery.get("enabled", False) is False:
            message.call_acknowledgements()
            return

        inter_agent_config = component.get_config("inter_agent_communication", {})
        allow_list = inter_agent_config.get("allow_list", ["*"])
        deny_list = inter_agent_config.get("deny_list", [])
        is_allowed = False
        for pattern in allow_list:
            if fnmatch.fnmatch(agent_name, pattern):
                is_allowed = True
                break

        if is_allowed:
            for pattern in deny_list:
                if fnmatch.fnmatch(agent_name, pattern):
                    is_allowed = False
                    break

        if is_allowed:
            agent_card.peer_agents = {}
            component.peer_agents[agent_name] = agent_card

        message.call_acknowledgements()

    except Exception as e:
        log.exception(
            "%s Error processing agent card message: %s", component.log_identifier, e
        )
        message.call_acknowledgements()
        component.handle_error(e, Event(EventType.MESSAGE, message))


async def handle_a2a_response(component, message: SolaceMessage):
    """Handles incoming responses/status updates from peer agents."""
    sub_task_id = None
    payload_to_queue = None
    is_final_response = False

    try:
        topic = message.get_topic()
        topic_parts = topic.split("/")
        if len(topic_parts) > 0:
            sub_task_id = topic_parts[-1]
            if not sub_task_id.startswith(component.CORRELATION_DATA_PREFIX):
                log.warning(
                    "%s Topic %s does not end with expected sub-task ID format. Ignoring.",
                    component.log_identifier,
                    topic,
                )
                message.call_acknowledgements()
                return
        else:
            log.error(
                "%s Could not extract sub-task ID from topic: %s",
                component.log_identifier,
                topic,
            )
            message.call_negative_acknowledgements()
            return

        log.debug("%s Extracted sub-task ID: %s", component.log_identifier, sub_task_id)

        payload_dict = message.get_payload()
        if not isinstance(payload_dict, dict):
            log.error(
                "%s Received non-dict payload for sub-task %s. Payload: %s",
                component.log_identifier,
                sub_task_id,
                payload_dict,
            )
            payload_to_queue = {
                "error": "Received invalid payload format from peer.",
                "code": "PEER_PAYLOAD_ERROR",
            }
            is_final_response = True
        else:
            try:
                a2a_response = JSONRPCResponse(**payload_dict)

                if a2a_response.result and isinstance(a2a_response.result, dict):
                    payload_data = a2a_response.result
                    parsed_successfully = False
                    is_final_response = False
                    payload_to_queue = None

                    if (
                        "final" in payload_data
                        and "status" in payload_data
                        and isinstance(payload_data.get("final"), bool)
                    ):
                        try:
                            status_event = TaskStatusUpdateEvent(**payload_data)

                            if (
                                status_event.status
                                and status_event.status.message
                                and status_event.status.message.parts
                            ):
                                for part_from_peer in status_event.status.message.parts:
                                    if (
                                        isinstance(part_from_peer, DataPart)
                                        and part_from_peer.data.get("a2a_signal_type")
                                        == "agent_status_message"
                                    ):
                                        log.info(
                                            "%s Received agent_status_message signal from peer for sub-task %s.",
                                            component.log_identifier,
                                            sub_task_id,
                                        )
                                        correlation_data = await component._get_correlation_data_for_sub_task(
                                            sub_task_id
                                        )
                                        if not correlation_data:
                                            log.warning(
                                                "%s Correlation data not found for sub-task %s. Cannot forward status signal.",
                                                component.log_identifier,
                                                sub_task_id,
                                            )
                                            message.call_acknowledgements()
                                            return

                                        original_task_context = correlation_data.get(
                                            "original_task_context"
                                        )
                                        if not original_task_context:
                                            log.warning(
                                                "%s original_task_context not found in correlation data for sub-task %s. Cannot forward status signal.",
                                                component.log_identifier,
                                                sub_task_id,
                                            )
                                            message.call_acknowledgements()
                                            return

                                        main_logical_task_id = (
                                            original_task_context.get("logical_task_id")
                                        )
                                        original_jsonrpc_request_id = (
                                            original_task_context.get(
                                                "jsonrpc_request_id"
                                            )
                                        )

                                        target_topic_for_forward = (
                                            original_task_context.get("statusTopic")
                                        )

                                        if (
                                            not main_logical_task_id
                                            or not original_jsonrpc_request_id
                                            or not target_topic_for_forward
                                        ):
                                            log.error(
                                                "%s Missing critical info (main_task_id, original_rpc_id, or target_status_topic) in context for sub-task %s. Cannot forward. Context: %s",
                                                component.log_identifier,
                                                sub_task_id,
                                                original_task_context,
                                            )
                                            message.call_acknowledgements()
                                            return

                                        peer_agent_name = (
                                            status_event.metadata.get(
                                                "agent_name", "UnknownPeer"
                                            )
                                            if status_event.metadata
                                            else "UnknownPeer"
                                        )

                                        forwarded_message = A2AMessage(
                                            role="agent",
                                            parts=[part_from_peer],
                                            metadata={
                                                "agent_name": component.agent_name,
                                                "forwarded_from_peer": peer_agent_name,
                                                "original_peer_event_id": status_event.id,
                                                "original_peer_event_timestamp": (
                                                    status_event.status.timestamp.isoformat()
                                                    if status_event.status
                                                    and status_event.status.timestamp
                                                    else None
                                                ),
                                                "function_call_id": correlation_data.get(
                                                    "adk_function_call_id", None
                                                ),
                                            },
                                        )
                                        forwarded_status = TaskStatus(
                                            state=TaskState.WORKING,
                                            message=forwarded_message,
                                            timestamp=status_event.status.timestamp,
                                        )
                                        forwarded_event = TaskStatusUpdateEvent(
                                            id=main_logical_task_id,
                                            status=forwarded_status,
                                            final=False,
                                        )
                                        forwarded_rpc_response = JSONRPCResponse(
                                            id=original_jsonrpc_request_id,
                                            result=forwarded_event,
                                        )
                                        payload_to_publish = (
                                            forwarded_rpc_response.model_dump(
                                                exclude_none=True
                                            )
                                        )

                                        try:
                                            component._publish_a2a_message(
                                                payload_to_publish,
                                                target_topic_for_forward,
                                            )
                                            log.info(
                                                "%s Forwarded agent_status_message signal for main task %s (from peer %s) to %s.",
                                                component.log_identifier,
                                                main_logical_task_id,
                                                peer_agent_name,
                                                target_topic_for_forward,
                                            )
                                        except Exception as pub_err:
                                            log.exception(
                                                "%s Failed to publish forwarded status signal for main task %s: %s",
                                                component.log_identifier,
                                                main_logical_task_id,
                                                pub_err,
                                            )
                                        message.call_acknowledgements()
                                        return

                            payload_to_queue = status_event.model_dump(
                                exclude_none=True
                            )
                            if status_event.final:
                                log.debug(
                                    "%s Parsed TaskStatusUpdateEvent(final=True) from peer for sub-task %s. This is an intermediate update for PeerAgentTool.",
                                    component.log_identifier,
                                    sub_task_id,
                                )

                                if (
                                    status_event.status
                                    and status_event.status.message
                                    and status_event.status.message.parts
                                ):
                                    response_parts_data = []
                                    for part in status_event.status.message.parts:
                                        if (
                                            hasattr(part, "text")
                                            and part.text is not None
                                        ):
                                            response_parts_data.append(str(part.text))
                                        elif (
                                            hasattr(part, "data")
                                            and part.data is not None
                                        ):
                                            try:
                                                response_parts_data.append(
                                                    json.dumps(part.data)
                                                )
                                            except TypeError:
                                                response_parts_data.append(
                                                    str(part.data)
                                                )

                                    payload_to_queue = {
                                        "result": "\n".join(response_parts_data)
                                    }
                                    log.debug(
                                        "%s Extracted content for TaskStatusUpdateEvent(final=True) for sub-task %s: %s",
                                        component.log_identifier,
                                        sub_task_id,
                                        payload_to_queue,
                                    )
                                else:
                                    log.debug(
                                        "%s TaskStatusUpdateEvent(final=True) for sub-task %s has no message parts to extract. Sending event object.",
                                        component.log_identifier,
                                        sub_task_id,
                                    )
                            else:
                                log.debug(
                                    "%s Parsed TaskStatusUpdateEvent(final=False) from peer for sub-task %s. This is an intermediate update.",
                                    component.log_identifier,
                                    sub_task_id,
                                )
                            parsed_successfully = True
                        except Exception as e:
                            log.warning(
                                "%s Failed to parse payload as TaskStatusUpdateEvent for sub-task %s. Payload: %s. Error: %s",
                                component.log_identifier,
                                sub_task_id,
                                payload_data,
                                e,
                            )
                            payload_to_queue = None

                    if (
                        not parsed_successfully
                        and "artifact" in payload_data
                        and isinstance(payload_data.get("artifact"), dict)
                    ):
                        try:
                            artifact_event = TaskArtifactUpdateEvent(**payload_data)
                            payload_to_queue = artifact_event.model_dump(
                                exclude_none=True
                            )
                            is_final_response = False
                            log.debug(
                                "%s Parsed TaskArtifactUpdateEvent from peer for sub-task %s. This is an intermediate update.",
                                component.log_identifier,
                                sub_task_id,
                            )
                            parsed_successfully = True
                        except Exception as e:
                            log.warning(
                                "%s Failed to parse payload as TaskArtifactUpdateEvent for sub-task %s. Payload: %s. Error: %s",
                                component.log_identifier,
                                sub_task_id,
                                payload_data,
                                e,
                            )
                            payload_to_queue = None

                    if not parsed_successfully:
                        try:
                            final_task = Task(**payload_data)
                            payload_to_queue = final_task.model_dump(exclude_none=True)
                            is_final_response = True
                            log.debug(
                                "%s Parsed final Task object from peer for sub-task %s.",
                                component.log_identifier,
                                sub_task_id,
                            )
                            parsed_successfully = True
                        except Exception as task_parse_error:
                            log.error(
                                "%s Failed to parse peer response for sub-task %s as any known type. Payload: %s. Error: %s",
                                component.log_identifier,
                                sub_task_id,
                                payload_data,
                                task_parse_error,
                            )
                            if not a2a_response.error:
                                a2a_response.error = InternalError(
                                    message=f"Failed to parse response from peer agent for sub-task {sub_task_id}",
                                    data={
                                        "original_payload": payload_data,
                                        "error": str(task_parse_error),
                                    },
                                )
                            payload_to_queue = None
                            is_final_response = True

                    if (
                        not parsed_successfully
                        and not a2a_response.error
                        and payload_to_queue is None
                    ):
                        log.error(
                            "%s Unhandled payload structure from peer for sub-task %s: %s.",
                            component.log_identifier,
                            sub_task_id,
                            payload_data,
                        )
                        a2a_response.error = InternalError(
                            message=f"Unknown response structure from peer agent for sub-task {sub_task_id}",
                            data={"original_payload": payload_data},
                        )
                        is_final_response = True

                elif a2a_response.error:
                    log.warning(
                        "%s Received error response from peer for sub-task %s: %s",
                        component.log_identifier,
                        sub_task_id,
                        a2a_response.error,
                    )
                    payload_to_queue = {
                        "error": a2a_response.error.message,
                        "code": a2a_response.error.code,
                        "data": a2a_response.error.data,
                    }
                    is_final_response = True
                else:
                    log.warning(
                        "%s Received JSONRPCResponse with no result or error for sub-task %s.",
                        component.log_identifier,
                        sub_task_id,
                    )
                    payload_to_queue = {"result": "Peer responded with empty message."}
                    is_final_response = True

            except Exception as parse_error:
                log.error(
                    "%s Failed to parse A2A response payload for sub-task %s: %s",
                    component.log_identifier,
                    sub_task_id,
                    parse_error,
                )
                payload_to_queue = {
                    "error": f"Failed to parse response from peer: {parse_error}",
                    "code": "PEER_PARSE_ERROR",
                }
                # Print out the stack trace for debugging
                log.exception(
                    "%s Exception stack trace: %s",
                    component.log_identifier,
                    parse_error,
                )

        if not is_final_response:
            # This is an intermediate status update for monitoring.
            # Log it, acknowledge it, but do not aggregate its content.
            log.debug(
                "%s Received and ignored intermediate status update from peer for sub-task %s.",
                component.log_identifier,
                sub_task_id,
            )
            message.call_acknowledgements()
            return

        correlation_data = await component._claim_peer_sub_task_completion(sub_task_id)
        if not correlation_data:
            # The helper method logs the reason (timeout, already claimed, etc.)
            message.call_acknowledgements()
            return

        async def _handle_final_peer_response():
            """
            Handles a final peer response by updating the completion counter and,
            if all peer tasks are complete, calling the re-trigger logic.
            """
            logical_task_id = correlation_data.get("logical_task_id")
            invocation_id = correlation_data.get("invocation_id")

            if not logical_task_id or not invocation_id:
                log.error(
                    "%s 'logical_task_id' or 'invocation_id' not found in correlation data for sub-task %s. Cannot proceed.",
                    component.log_identifier,
                    sub_task_id,
                )
                return

            log_retrigger = (
                f"{component.log_identifier}[RetriggerManager:{logical_task_id}]"
            )

            with component.active_tasks_lock:
                task_context = component.active_tasks.get(logical_task_id)

            if not task_context:
                log.error(
                    "%s TaskExecutionContext not found for task %s. Cannot process final peer response.",
                    log_retrigger,
                    logical_task_id,
                )
                return

            final_text = ""
            artifact_summary = ""
            if isinstance(payload_to_queue, dict):
                if "result" in payload_to_queue:
                    final_text = payload_to_queue["result"]
                elif "error" in payload_to_queue:
                    final_text = (
                        f"Peer agent returned an error: {payload_to_queue['error']}"
                    )
                elif "status" in payload_to_queue:  # It's a Task object
                    try:
                        task_obj = Task(**payload_to_queue)
                        if task_obj.status and task_obj.status.message:
                            final_text = _extract_text_from_parts(
                                task_obj.status.message.parts
                            )

                        if (
                            task_obj.metadata
                            and "produced_artifacts" in task_obj.metadata
                        ):
                            produced_artifacts = task_obj.metadata.get(
                                "produced_artifacts", []
                            )
                            if produced_artifacts:
                                peer_agent_name = task_obj.metadata.get(
                                    "agent_name", "A peer agent"
                                )
                                original_task_context = correlation_data.get(
                                    "original_task_context", {}
                                )
                                user_id = original_task_context.get("user_id")
                                session_id = original_task_context.get("session_id")

                                header_text = f"Peer agent `{peer_agent_name}` created {len(produced_artifacts)} artifact(s):"

                                if user_id and session_id:
                                    artifact_summary = (
                                        await generate_artifact_metadata_summary(
                                            component=component,
                                            artifact_identifiers=produced_artifacts,
                                            user_id=user_id,
                                            session_id=session_id,
                                            app_name=peer_agent_name,
                                            header_text=header_text,
                                        )
                                    )
                                else:
                                    log.warning(
                                        "%s Could not generate artifact summary: missing user_id or session_id in correlation data.",
                                        log_retrigger,
                                    )
                                    artifact_summary = ""
                                # Bubble up the peer's artifacts to the parent context
                                _register_peer_artifacts_in_parent_context(
                                    task_context, task_obj, log_retrigger
                                )

                    except Exception:
                        final_text = json.dumps(payload_to_queue)
                else:
                    final_text = json.dumps(payload_to_queue)
            elif isinstance(payload_to_queue, str):
                final_text = payload_to_queue
            else:
                final_text = str(payload_to_queue)

            full_response_text = final_text
            if artifact_summary:
                full_response_text = f"{artifact_summary}\n\n{full_response_text}"

            current_result = {
                "adk_function_call_id": correlation_data.get("adk_function_call_id"),
                "peer_tool_name": correlation_data.get("peer_tool_name"),
                "payload": {"result": full_response_text},
            }

            all_sub_tasks_completed = task_context.record_parallel_result(
                current_result, invocation_id
            )
            log.info(
                "%s Updated parallel counter for task %s: %s",
                log_retrigger,
                logical_task_id,
                task_context.parallel_tool_calls.get(invocation_id),
            )

            if not all_sub_tasks_completed:
                log.info(
                    "%s Waiting for more peer responses for task %s.",
                    log_retrigger,
                    logical_task_id,
                )
                return

            log.info(
                "%s All peer responses received for task %s. Retriggering agent.",
                log_retrigger,
                logical_task_id,
            )
            results_to_inject = task_context.parallel_tool_calls.get(
                invocation_id, {}
            ).get("results", [])

            await component._retrigger_agent_with_peer_responses(
                results_to_inject, correlation_data, task_context
            )

        loop = component.get_async_loop()
        if loop and loop.is_running():
            asyncio.run_coroutine_threadsafe(_handle_final_peer_response(), loop)
        else:
            log.error(
                "%s Async loop not available. Cannot handle final peer response for sub-task %s.",
                component.log_identifier,
                sub_task_id,
            )

        message.call_acknowledgements()
        log.info(
            "%s Acknowledged final peer response message for sub-task %s.",
            component.log_identifier,
            sub_task_id,
        )

    except Exception as e:
        log.exception(
            "%s Unexpected error handling A2A response for sub-task %s: %s",
            component.log_identifier,
            sub_task_id,
            e,
        )
        try:
            message.call_negative_acknowledgements()
            log.warning(
                "%s NACKed peer response message for sub-task %s due to unexpected error.",
                component.log_identifier,
                sub_task_id,
            )
        except Exception as nack_e:
            log.error(
                "%s Failed to NACK peer response message for sub-task %s after error: %s",
                component.log_identifier,
                sub_task_id,
                nack_e,
            )
        component.handle_error(e, Event(EventType.MESSAGE, message))


def publish_agent_card(component):
    """Publishes the agent's card to the discovery topic."""
    try:
        card_config = component.get_config("agent_card", {})
        agent_name = component.get_config("agent_name")
        display_name = component.get_config("display_name")
        namespace = component.get_config("namespace")
        supports_streaming = component.get_config("supports_streaming", False)
        peer_agents = component.peer_agents

        agent_request_topic = get_agent_request_topic(namespace, agent_name)
        dynamic_url = f"solace:{agent_request_topic}"

        capabilities = AgentCapabilities(
            streaming=supports_streaming,
            pushNotifications=False,
            stateTransitionHistory=False,
        )

        skills = card_config.get("skills", [])
        dynamic_tools = getattr(component, "agent_card_tool_manifest", [])

        agent_card = AgentCard(
            name=agent_name,
            display_name=display_name,
            version=component.HOST_COMPONENT_VERSION,
            url=dynamic_url,
            capabilities=capabilities,
            description=card_config.get("description", ""),
            skills=skills,
            tools=dynamic_tools,
            defaultInputModes=card_config.get("defaultInputModes", ["text"]),
            defaultOutputModes=card_config.get("defaultOutputModes", ["text"]),
            documentationUrl=card_config.get("documentationUrl"),
            provider=card_config.get("provider"),
            peer_agents=peer_agents,
        )

        discovery_topic = get_discovery_topic(namespace)

        component._publish_a2a_message(
            agent_card.model_dump(exclude_none=True), discovery_topic
        )
        log.debug(
            "%s Successfully published Agent Card to %s",
            component.log_identifier,
            discovery_topic,
        )

    except Exception as e:
        log.exception(
            "%s Failed to publish Agent Card: %s", component.log_identifier, e
        )
        component.handle_error(e, None)
