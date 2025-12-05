"""
Contains event handling logic for the A2A_ADK_HostComponent.
"""

import asyncio
import fnmatch
import json
import logging
from typing import TYPE_CHECKING, Any, Dict

from a2a.types import (
    A2ARequest,
    AgentCapabilities,
    AgentCard,
    AgentExtension,
    DataPart,
    JSONRPCResponse,
    Task,
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatusUpdateEvent,
    TextPart,
)
from google.adk.agents import RunConfig
from google.adk.agents.run_config import StreamingMode
from solace_ai_connector.common.event import Event, EventType
from solace_ai_connector.common.message import Message as SolaceMessage
from sqlalchemy.exc import OperationalError

from ...agent.adk.callbacks import _publish_data_part_status_update
from ...agent.adk.runner import TaskCancelledError, run_adk_async_task_thread_wrapper
from ...agent.utils.artifact_helpers import generate_artifact_metadata_summary
from ...common import a2a
from ...common.utils.embeds.constants import (
    EMBED_DELIMITER_OPEN,
    EMBED_DELIMITER_CLOSE,
)
from ...common.a2a import (
    get_agent_request_topic,
    get_agent_response_subscription_topic,
    get_agent_status_subscription_topic,
    get_client_response_topic,
    get_discovery_topic,
    get_sam_events_subscription_topic,
    get_text_from_message,
    topic_matches_subscription,
    translate_a2a_to_adk_content,
)
from ...common.a2a.types import ToolsExtensionParams
from ...common.data_parts import ToolResultData
from ..sac.task_execution_context import TaskExecutionContext

if TYPE_CHECKING:
    from ..sac.component import SamAgentComponent

log = logging.getLogger(__name__)
trace_logger = logging.getLogger("sam_trace")


def _forward_jsonrpc_response(
    component: "SamAgentComponent",
    original_jsonrpc_request_id: str,
    result_data: Any,
    target_topic: str,
    main_logical_task_id: str,
    peer_agent_name: str,
    message: SolaceMessage,
) -> None:
    """
    Utility method to forward a JSONRPCResponse with the given result data.

    Args:
        component: The SamAgentComponent instance
        original_jsonrpc_request_id: The original JSONRPC request ID
        result_data: The data to include in the response result
        target_topic: The topic to publish to
        main_logical_task_id: The main logical task ID for logging
        peer_agent_name: The peer agent name for logging
        message: The original message to acknowledge
    """
    forwarded_rpc_response = JSONRPCResponse(
        id=original_jsonrpc_request_id,
        result=result_data,
    )
    payload_to_publish = forwarded_rpc_response.model_dump(
        by_alias=True, exclude_none=True
    )

    try:
        component.publish_a2a_message(
            payload_to_publish,
            target_topic,
        )
        log.debug(
            "%s Forwarded DataPart signal for main task %s (from peer %s) to %s.",
            component.log_identifier,
            main_logical_task_id,
            peer_agent_name,
            target_topic,
        )
    except Exception as pub_err:
        log.exception(
            "%s Failed to publish forwarded status signal for main task %s: %s",
            component.log_identifier,
            main_logical_task_id,
            pub_err,
        )
    message.call_acknowledgements()


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
            sam_events_topic = get_sam_events_subscription_topic(namespace, "session")
            if topic == agent_request_topic:
                await handle_a2a_request(component, message)
            elif topic == discovery_topic:
                payload = message.get_payload()
                if isinstance(payload, dict) and payload.get("name") != agent_name:
                    handle_agent_card_message(component, message)
                else:
                    message.call_acknowledgements()
            elif topic_matches_subscription(topic, sam_events_topic):
                handle_sam_event(component, message, topic)
            elif topic.startswith(agent_response_sub_prefix) or topic.startswith(
                agent_status_sub_prefix
            ):
                await handle_a2a_response(component, message)
            elif hasattr(component, "trust_manager") and component.trust_manager:
                # Check if this is a trust card message (enterprise feature)
                try:
                    if component.trust_manager.is_trust_card_topic(topic):
                        await component.trust_manager.handle_trust_card_message(
                            message, topic
                        )
                        message.call_acknowledgements()
                        return
                except Exception as e:
                    log.error(
                        "%s Error handling trust card message: %s",
                        component.log_identifier,
                        e,
                    )
                    message.call_acknowledgements()
                    return

                log.warning(
                    "%s Received message on unhandled topic: %s",
                    component.log_identifier,
                    topic,
                )
                message.call_acknowledgements()
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
            else:
                # Handle other timer events including health check timer
                component.handle_timer_event(timer_data)
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


async def _publish_peer_tool_result_notification(
    component: "SamAgentComponent",
    correlation_data: dict[str, Any],
    payload_to_queue: Any,
    log_identifier: str,
):
    """Publishes a ToolResultData status update for a completed peer tool call."""
    peer_tool_name = correlation_data.get("peer_tool_name")
    function_call_id = correlation_data.get("adk_function_call_id")
    original_task_context_data = correlation_data.get("original_task_context")

    if not (peer_tool_name and function_call_id and original_task_context_data):
        log.warning(
            "%s Missing data in correlation_data. Cannot publish peer tool result notification.",
            log_identifier,
        )
        return

    log.info(
        "%s Publishing tool_result notification for completed peer task '%s'.",
        log_identifier,
        peer_tool_name,
    )
    try:
        tool_result_notification = ToolResultData(
            tool_name=peer_tool_name,
            result_data=payload_to_queue,
            function_call_id=function_call_id,
        )
        await _publish_data_part_status_update(
            host_component=component,
            a2a_context=original_task_context_data,
            data_part_model=tool_result_notification,
        )
    except Exception as e:
        log.error(
            "%s Failed to publish peer tool result notification for '%s': %s",
            log_identifier,
            peer_tool_name,
            e,
            exc_info=True,
        )


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
    try:
        payload_dict = message.get_payload()
        if not isinstance(payload_dict, dict):
            raise ValueError("Payload is not a dictionary.")

        a2a_request: A2ARequest = A2ARequest.model_validate(payload_dict)
        jsonrpc_request_id = a2a.get_request_id(a2a_request)

        # Extract properties from message user properties
        client_id = message.get_user_properties().get("clientId", "default_client")
        status_topic_from_peer = message.get_user_properties().get("a2aStatusTopic")
        reply_topic_from_peer = message.get_user_properties().get("replyTo")
        namespace = component.get_config("namespace")
        a2a_user_config = message.get_user_properties().get("a2aUserConfig", {})
        if not isinstance(a2a_user_config, dict):
            log.warning("a2aUserConfig is not a dict, using empty dict instead")
            a2a_user_config = {}

        # The concept of logical_task_id changes. For Cancel, it's in params.id.
        # For Send, we will generate it.
        logical_task_id = None
        method = a2a.get_request_method(a2a_request)

        # Enterprise feature: Verify user authentication if trust manager enabled
        verified_user_identity = None
        if hasattr(component, "trust_manager") and component.trust_manager:
            # Determine task_id for verification
            if method == "tasks/cancel":
                verification_task_id = a2a.get_task_id_from_cancel_request(a2a_request)
            elif method in ["message/send", "message/stream"]:
                verification_task_id = str(a2a.get_request_id(a2a_request))
            else:
                verification_task_id = None

            if verification_task_id:
                try:
                    # Enterprise handles all verification logic
                    verified_user_identity = (
                        component.trust_manager.verify_request_authentication(
                            message=message,
                            task_id=verification_task_id,
                            namespace=namespace,
                            jsonrpc_request_id=jsonrpc_request_id,
                        )
                    )

                    if verified_user_identity:
                        log.info(
                            "%s Successfully authenticated user '%s' for task %s",
                            component.log_identifier,
                            verified_user_identity.get("user_id"),
                            verification_task_id,
                        )

                except Exception as e:
                    # Authentication failed - enterprise provides error details
                    log.error(
                        "%s Authentication failed for task %s: %s",
                        component.log_identifier,
                        verification_task_id,
                        e,
                    )

                    # Build error response using enterprise exception data if available
                    error_data = {
                        "reason": "authentication_failed",
                        "task_id": verification_task_id,
                    }
                    if hasattr(e, "create_error_response_data"):
                        error_data = e.create_error_response_data()

                    error_response = a2a.create_invalid_request_error_response(
                        message="Authentication failed",
                        request_id=jsonrpc_request_id,
                        data=error_data,
                    )

                    # Determine reply topic
                    reply_topic = message.get_user_properties().get("replyTo")
                    if not reply_topic:
                        client_id = message.get_user_properties().get(
                            "clientId", "default_client"
                        )
                        reply_topic = a2a.get_client_response_topic(
                            namespace, client_id
                        )

                    component.publish_a2a_message(
                        payload=error_response.model_dump(exclude_none=True),
                        topic=reply_topic,
                    )

                    try:
                        message.call_acknowledgements()
                        log.debug(
                            "%s ACKed message with failed authentication",
                            component.log_identifier,
                        )
                    except Exception as ack_e:
                        log.error(
                            "%s Failed to ACK message after authentication failure: %s",
                            component.log_identifier,
                            ack_e,
                        )
                    return None

        if method == "tasks/cancel":
            logical_task_id = a2a.get_task_id_from_cancel_request(a2a_request)
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

                peer_sub_tasks = task_context.active_peer_sub_tasks.copy()
                if peer_sub_tasks:
                    for sub_task_id, sub_task_info in peer_sub_tasks.items():
                        target_peer_agent_name = sub_task_info.get("peer_agent_name")
                        peer_task_id_to_cancel = sub_task_info.get("peer_task_id")

                        if not peer_task_id_to_cancel:
                            log.warning(
                                "%s Cannot cancel peer sub-task %s for main task %s because the peer's taskId is not yet known.",
                                component.log_identifier,
                                sub_task_id,
                                logical_task_id,
                            )
                            continue

                        if peer_task_id_to_cancel and target_peer_agent_name:
                            log.info(
                                "%s Attempting to cancel peer sub-task %s (Peer Task ID: %s) for agent %s (main task %s).",
                                component.log_identifier,
                                sub_task_id,
                                peer_task_id_to_cancel,
                                target_peer_agent_name,
                                logical_task_id,
                            )
                            try:
                                peer_cancel_request = a2a.create_cancel_task_request(
                                    task_id=peer_task_id_to_cancel
                                )
                                peer_cancel_user_props = {
                                    "clientId": component.agent_name
                                }
                                component.publish_a2a_message(
                                    payload=peer_cancel_request.model_dump(
                                        exclude_none=True
                                    ),
                                    topic=component._get_agent_request_topic(
                                        target_peer_agent_name
                                    ),
                                    user_properties=peer_cancel_user_props,
                                )
                                log.info(
                                    "%s Sent CancelTaskRequest to peer %s for its task %s.",
                                    component.log_identifier,
                                    target_peer_agent_name,
                                    peer_task_id_to_cancel,
                                )
                            except Exception as e_peer_cancel:
                                log.error(
                                    "%s Failed to send CancelTaskRequest to peer %s for task %s: %s",
                                    component.log_identifier,
                                    target_peer_agent_name,
                                    peer_task_id_to_cancel,
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
                    # No peer sub-tasks - check if task is paused and needs immediate finalization
                    if task_context.get_is_paused():
                        log.info(
                            "%s Task %s is paused with no peer sub-tasks. Scheduling immediate finalization.",
                            component.log_identifier,
                            logical_task_id,
                        )
                        loop = component.get_async_loop()
                        if loop and loop.is_running():
                            task_context.set_paused(False)

                            asyncio.run_coroutine_threadsafe(
                                component.finalize_task_with_cleanup(
                                    task_context.a2a_context,
                                    is_paused=False,
                                    exception=TaskCancelledError(
                                        f"Task {logical_task_id} cancelled while paused."
                                    )
                                ),
                                loop,
                            )
                        else:
                            log.error(
                                "%s Cannot finalize cancelled paused task %s - event loop not available.",
                                component.log_identifier,
                                logical_task_id,
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
        elif method in ["message/send", "message/stream"]:
            a2a_message = a2a.get_message_from_send_request(a2a_request)
            if not a2a_message:
                raise ValueError("Could not extract message from SendMessageRequest")

            # The gateway/client is the source of truth for the task ID.
            # The agent adopts the ID from the JSON-RPC request envelope.
            logical_task_id = str(a2a.get_request_id(a2a_request))

            try:
                from solace_agent_mesh_enterprise.auth.input_required import (
                    a2a_auth_message_handler,
                )

                try:
                    message_handled = await a2a_auth_message_handler(
                        component, a2a_message, logical_task_id
                    )
                    if message_handled:
                        message.call_acknowledgements()
                        log.debug(
                            "%s ACKed message handled by input-required auth handler.",
                            component.log_identifier,
                        )
                        return None
                except Exception as auth_import_err:
                    log.error(
                        "%s Error in input-required auth handler: %s",
                        component.log_identifier,
                        auth_import_err,
                    )
                    message.call_acknowledgements()
                    return None

            except ImportError:
                pass

            # The session id is now contextId on the message
            original_session_id = a2a_message.context_id
            message_id = a2a_message.message_id
            task_metadata = a2a_message.metadata or {}
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
                log.debug(
                    "%s No 'sessionBehavior' in task metadata. Using component default: '%s'.",
                    component.log_identifier,
                    session_behavior,
                )
            user_id = message.get_user_properties().get("userId", "default_user")
            agent_name = component.get_config("agent_name")
            is_streaming_request = method == "message/stream"
            host_supports_streaming = component.get_config("supports_streaming", False)
            if is_streaming_request and not host_supports_streaming:
                raise ValueError(
                    "Host does not support streaming (tasks/sendSubscribe) requests."
                )
            effective_session_id = original_session_id
            is_run_based_session = False
            temporary_run_session_id_for_cleanup = None

            session_id_from_data = None
            if a2a_message and a2a_message.parts:
                for part in a2a_message.parts:
                    if isinstance(part, DataPart) and "session_id" in part.data:
                        session_id_from_data = part.data["session_id"]
                        log.info(
                            f"Extracted session_id '{session_id_from_data}' from DataPart."
                        )
                        break

            if session_id_from_data:
                original_session_id = session_id_from_data

            if session_behavior == "RUN_BASED":
                is_run_based_session = True
                effective_session_id = f"{original_session_id}:{logical_task_id}:run"
                temporary_run_session_id_for_cleanup = effective_session_id
                log.info(
                    "%s Session behavior is RUN_BASED. OriginalID='%s', EffectiveID for this run='%s', TaskID='%s'.",
                    component.log_identifier,
                    original_session_id,
                    effective_session_id,
                    logical_task_id,
                )
            else:
                is_run_based_session = False
                effective_session_id = original_session_id
                temporary_run_session_id_for_cleanup = None
                log.info(
                    "%s Session behavior is PERSISTENT. EffectiveID='%s' for TaskID='%s'.",
                    component.log_identifier,
                    effective_session_id,
                    logical_task_id,
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
                    logical_task_id,
                )

            else:
                log.info(
                    "%s Reusing existing ADK session '%s' for task '%s'.",
                    component.log_identifier,
                    effective_session_id,
                    logical_task_id,
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
                                logical_task_id,
                            )
                    else:
                        log.debug(
                            "%s Original session '%s' not found or has no history, cannot copy for run-based task '%s'.",
                            component.log_identifier,
                            original_session_id,
                            logical_task_id,
                        )
                except Exception as e_copy:
                    log.error(
                        "%s Error copying history for run-based session '%s' (task '%s'): %s. Proceeding with empty session.",
                        component.log_identifier,
                        effective_session_id,
                        logical_task_id,
                        e_copy,
                    )
            a2a_context = {
                "jsonrpc_request_id": jsonrpc_request_id,
                "logical_task_id": logical_task_id,
                "contextId": original_session_id,
                "messageId": message_id,
                "session_id": original_session_id,  # Keep for now for compatibility
                "user_id": user_id,
                "client_id": client_id,
                "is_streaming": is_streaming_request,
                "statusTopic": status_topic_from_peer,
                "replyToTopic": reply_topic_from_peer,
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

            # Store verified user identity claims in a2a_context (not the raw token)
            if verified_user_identity:
                a2a_context["verified_user_identity"] = verified_user_identity
                log.debug(
                    "%s Stored verified user identity in a2a_context for task %s",
                    component.log_identifier,
                    logical_task_id,
                )
            if trace_logger.isEnabledFor(logging.DEBUG):
                trace_logger.debug(
                    "%s A2A Context (shared service model): %s",
                    component.log_identifier,
                    a2a_context,
                )
            else:
                log.debug(
                    "%s A2A Context prepared for task %s",
                    component.log_identifier,
                    a2a_context.get("logical_task_id", "unknown"),
                )

            # Create and store the execution context for this task
            task_context = TaskExecutionContext(
                task_id=logical_task_id, a2a_context=a2a_context
            )

            # Store the original Solace message in TaskExecutionContext instead of a2a_context
            # This avoids serialization issues when a2a_context is stored in ADK session state
            task_context.set_original_solace_message(message)

            # Store auth token for peer delegation using generic security storage
            if hasattr(component, "trust_manager") and component.trust_manager:
                auth_token = message.get_user_properties().get("authToken")
                if auth_token:
                    task_context.set_security_data("auth_token", auth_token)
                    log.debug(
                        "%s Stored authentication token in TaskExecutionContext security storage for task %s",
                        component.log_identifier,
                        logical_task_id,
                    )

            with component.active_tasks_lock:
                component.active_tasks[logical_task_id] = task_context
            log.info(
                "%s Created and stored new TaskExecutionContext for task %s.",
                component.log_identifier,
                logical_task_id,
            )

            a2a_message_for_adk = a2a_message
            invoked_artifacts = (
                a2a_message_for_adk.metadata.get("invoked_with_artifacts", [])
                if a2a_message_for_adk.metadata
                else []
            )

            if invoked_artifacts:
                log.info(
                    "%s Task %s invoked with %d artifact(s). Preparing context from metadata.",
                    component.log_identifier,
                    logical_task_id,
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

                task_description = get_text_from_message(a2a_message_for_adk)
                final_prompt = f"{task_description}\n\n{artifact_summary}"

                a2a_message_for_adk = a2a.update_message_parts(
                    message=a2a_message_for_adk,
                    new_parts=[a2a.create_text_part(text=final_prompt)],
                )
                log.debug(
                    "%s Generated new prompt for task %s with artifact context.",
                    component.log_identifier,
                    logical_task_id,
                )

            adk_content = await translate_a2a_to_adk_content(
                a2a_message=a2a_message_for_adk,
                component=component,
                user_id=user_id,
                session_id=effective_session_id,
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
            log.debug(
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
                method,
            )
            try:
                message.call_acknowledgements()
            except Exception as ack_e:
                log.error(
                    "%s Failed to ACK unhandled request type %s: %s",
                    component.log_identifier,
                    method,
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
        error_response = a2a.create_internal_error_response(
            message=str(e), request_id=jsonrpc_request_id, data=error_data
        )

        target_topic = reply_topic_from_peer or (
            get_client_response_topic(namespace, client_id) if client_id else None
        )
        if target_topic:
            component.publish_a2a_message(
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

    except OperationalError as e:
        log.error(
            "%s Database error while processing A2A request: %s",
            component.log_identifier,
            e,
        )

        # Check if it's a schema error
        error_msg = str(e).lower()
        if "no such column" in error_msg or "no such table" in error_msg:
            user_message = (
                "Database schema update required. "
                "Please contact your administrator to run database migrations."
            )
        else:
            user_message = (
                "Database error occurred. Please try again or contact support."
            )

        error_response = a2a.create_internal_error_response(
            message=user_message,
            request_id=jsonrpc_request_id,
            data={"taskId": logical_task_id} if logical_task_id else None,
        )

        target_topic = reply_topic_from_peer or (
            get_client_response_topic(namespace, client_id) if client_id else None
        )
        if target_topic:
            component.publish_a2a_message(
                error_response.model_dump(exclude_none=True),
                target_topic,
            )

        try:
            message.call_negative_acknowledgements()
            log.warning(
                "%s NACKed A2A request due to database error.",
                component.log_identifier,
            )
        except Exception as nack_e:
            log.error(
                "%s Failed to NACK message after database error: %s",
                component.log_identifier,
                nack_e,
            )

        component.handle_error(e, Event(EventType.MESSAGE, message))
        return None

    except Exception as e:
        log.exception(
            "%s Unexpected error handling A2A request: %s", component.log_identifier, e
        )
        error_response = a2a.create_internal_error_response(
            message=f"Unexpected server error: {e}",
            request_id=jsonrpc_request_id,
            data={"taskId": logical_task_id},
        )
        target_topic = reply_topic_from_peer or (
            get_client_response_topic(namespace, client_id) if client_id else None
        )
        if target_topic:
            component.publish_a2a_message(
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

            # Also store in peer_agents for backward compatibility
            component.peer_agents[agent_name] = agent_card

            # Store the agent card in the registry for health tracking
            is_new = component.agent_registry.add_or_update_agent(agent_card)

            if is_new:
                log.info(
                    "%s Registered new agent '%s' in registry.",
                    component.log_identifier,
                    agent_name,
                )
            else:
                log.debug(
                    "%s Updated existing agent '%s' in registry.",
                    component.log_identifier,
                    agent_name,
                )

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
        agent_response_sub = a2a.get_agent_response_subscription_topic(
            component.namespace, component.agent_name
        )
        agent_status_sub = a2a.get_agent_status_subscription_topic(
            component.namespace, component.agent_name
        )

        if a2a.topic_matches_subscription(topic, agent_response_sub):
            sub_task_id = a2a.extract_task_id_from_topic(
                topic, agent_response_sub, component.log_identifier
            )
        elif a2a.topic_matches_subscription(topic, agent_status_sub):
            sub_task_id = a2a.extract_task_id_from_topic(
                topic, agent_status_sub, component.log_identifier
            )
        else:
            sub_task_id = None

        if not sub_task_id:
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
                a2a_response = JSONRPCResponse.model_validate(payload_dict)

                result = a2a.get_response_result(a2a_response)
                if result:
                    payload_data = result

                    # Store the peer's task ID if we see it for the first time
                    peer_task_id = getattr(payload_data, "task_id", None)
                    if peer_task_id:
                        correlation_data = (
                            await component._get_correlation_data_for_sub_task(
                                sub_task_id
                            )
                        )
                        if correlation_data and "peer_task_id" not in correlation_data:
                            log.info(
                                "%s Received first response for sub-task %s. Storing peer taskId: %s",
                                component.log_identifier,
                                sub_task_id,
                                peer_task_id,
                            )
                            main_logical_task_id = correlation_data.get(
                                "logical_task_id"
                            )
                            with component.active_tasks_lock:
                                task_context = component.active_tasks.get(
                                    main_logical_task_id
                                )
                                if task_context:
                                    with task_context.lock:
                                        if (
                                            sub_task_id
                                            in task_context.active_peer_sub_tasks
                                        ):
                                            task_context.active_peer_sub_tasks[
                                                sub_task_id
                                            ]["peer_task_id"] = peer_task_id

                    parsed_successfully = False
                    is_final_response = False
                    payload_to_queue = None

                    if isinstance(payload_data, TaskStatusUpdateEvent):
                        try:
                            status_event = payload_data

                            data_parts = a2a.get_data_parts_from_status_update(
                                status_event
                            )
                            if data_parts:

                                peer_agent_name = (
                                    status_event.metadata.get(
                                        "agent_name", "UnknownPeer"
                                    )
                                    if status_event.metadata
                                    else "UnknownPeer"
                                )

                                correlation_data = (
                                    await component._get_correlation_data_for_sub_task(
                                        sub_task_id
                                    )
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

                                main_logical_task_id = original_task_context.get(
                                    "logical_task_id"
                                )
                                original_jsonrpc_request_id = original_task_context.get(
                                    "jsonrpc_request_id"
                                )
                                main_context_id = original_task_context.get("contextId")

                                target_topic_for_forward = original_task_context.get(
                                    "statusTopic"
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

                                event_metadata = {
                                    "agent_name": component.agent_name,
                                    "forwarded_from_peer": peer_agent_name,
                                    "original_peer_event_taskId": status_event.task_id,
                                    "original_peer_event_timestamp": (
                                        status_event.status.timestamp
                                        if status_event.status
                                        and status_event.status.timestamp
                                        else None
                                    ),
                                    "function_call_id": correlation_data.get(
                                        "adk_function_call_id", None
                                    ),
                                }

                                if (
                                    status_event.status.state
                                    == TaskState.input_required
                                ):
                                    log.debug(
                                        "%s Received input-required status for sub-task %s. Requesting user input. Forwarding to target.",
                                        component.log_identifier,
                                        sub_task_id,
                                    )

                                    if (
                                        status_event.metadata
                                        and "task_call_stack" in status_event.metadata
                                        and isinstance(
                                            status_event.metadata["task_call_stack"],
                                            list,
                                        )
                                    ):
                                        task_call_stack = status_event.metadata[
                                            "task_call_stack"
                                        ].copy()
                                        task_call_stack.insert(0, sub_task_id)
                                        event_metadata["task_call_stack"] = (
                                            task_call_stack
                                        )
                                    else:
                                        event_metadata["task_call_stack"] = [
                                            sub_task_id
                                        ]

                                    status_event.metadata = event_metadata
                                    status_event.task_id = main_logical_task_id

                                    _forward_jsonrpc_response(
                                        component=component,
                                        original_jsonrpc_request_id=original_jsonrpc_request_id,
                                        result_data=status_event,
                                        target_topic=target_topic_for_forward,
                                        main_logical_task_id=main_logical_task_id,
                                        peer_agent_name=peer_agent_name,
                                        message=message,
                                    )
                                    return

                                # Filter out artifact creation progress from peer agents.
                                # These are implementation details that should not leak across
                                # agent boundaries. Artifacts are properly bubbled up in the
                                # final Task response metadata.
                                filtered_data_parts = []
                                for data_part in data_parts:
                                    if isinstance(data_part.data, dict) and data_part.data.get("type") == "artifact_creation_progress":
                                        log.debug(
                                            "%s Filtered out artifact_creation_progress DataPart from peer sub-task %s. Not forwarding to user.",
                                            component.log_identifier,
                                            sub_task_id,
                                        )
                                        continue
                                    filtered_data_parts.append(data_part)

                                # Only forward if there are non-filtered data parts
                                if filtered_data_parts:
                                    for data_part in filtered_data_parts:
                                        log.info(
                                            "%s Received DataPart signal from peer for sub-task %s. Forwarding...",
                                            component.log_identifier,
                                            sub_task_id,
                                        )

                                        forwarded_message = a2a.create_agent_parts_message(
                                            parts=[data_part],
                                            metadata=event_metadata,
                                        )

                                        forwarded_event = a2a.create_status_update(
                                            task_id=main_logical_task_id,
                                            context_id=main_context_id,
                                            message=forwarded_message,
                                            is_final=False,
                                        )
                                        if (
                                            status_event.status
                                            and status_event.status.timestamp
                                        ):
                                            forwarded_event.status.timestamp = (
                                                status_event.status.timestamp
                                            )
                                        _forward_jsonrpc_response(
                                            component=component,
                                            original_jsonrpc_request_id=original_jsonrpc_request_id,
                                            result_data=forwarded_event,
                                            target_topic=target_topic_for_forward,
                                            main_logical_task_id=main_logical_task_id,
                                            peer_agent_name=peer_agent_name,
                                            message=message,
                                        )
                                    return
                                else:
                                    log.debug(
                                        "%s All DataParts from peer sub-task %s were filtered. Not forwarding.",
                                        component.log_identifier,
                                        sub_task_id,
                                    )

                            payload_to_queue = status_event.model_dump(
                                by_alias=True, exclude_none=True
                            )
                            if status_event.final:
                                log.debug(
                                    "%s Parsed TaskStatusUpdateEvent(final=True) from peer for sub-task %s. This is an intermediate update for PeerAgentTool.",
                                    component.log_identifier,
                                    sub_task_id,
                                )

                                if status_event.status and status_event.status.message:
                                    response_parts_data = []
                                    unwrapped_parts = a2a.get_parts_from_message(
                                        status_event.status.message
                                    )
                                    for part in unwrapped_parts:
                                        if isinstance(part, TextPart):
                                            response_parts_data.append(str(part.text))
                                        elif isinstance(part, DataPart):
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
                                "%s Failed to process payload as TaskStatusUpdateEvent for sub-task %s. Payload: %s. Error: %s",
                                component.log_identifier,
                                sub_task_id,
                                payload_data,
                                e,
                            )
                            payload_to_queue = None

                    elif isinstance(payload_data, TaskArtifactUpdateEvent):
                        try:
                            artifact_event = payload_data
                            payload_to_queue = artifact_event.model_dump(
                                by_alias=True, exclude_none=True
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

                    elif isinstance(payload_data, Task):
                        try:
                            final_task = payload_data
                            payload_to_queue = final_task.model_dump(
                                by_alias=True, exclude_none=True
                            )
                            is_final_response = True
                            log.debug(
                                "%s Parsed final Task object from peer for sub-task %s.",
                                component.log_identifier,
                                sub_task_id,
                            )
                            parsed_successfully = True
                        except Exception as task_parse_error:
                            log.error(
                                "%s Failed to parse peer response for sub-task %s as Task. Payload: %s. Error: %s",
                                component.log_identifier,
                                sub_task_id,
                                payload_data,
                                task_parse_error,
                            )
                            if not a2a.get_response_error(a2a_response):
                                error = a2a.create_internal_error(
                                    message=f"Failed to parse response from peer agent for sub-task {sub_task_id}",
                                    data={
                                        "original_payload": payload_data.model_dump(
                                            by_alias=True, exclude_none=True
                                        ),
                                        "error": str(task_parse_error),
                                    },
                                )
                                a2a_response = a2a.create_error_response(
                                    error, a2a.get_response_id(a2a_response)
                                )
                            payload_to_queue = None
                            is_final_response = True

                    if (
                        not parsed_successfully
                        and not a2a.get_response_error(a2a_response)
                        and payload_to_queue is None
                    ):
                        log.error(
                            "%s Unhandled payload structure from peer for sub-task %s: %s.",
                            component.log_identifier,
                            sub_task_id,
                            payload_data,
                        )
                        error = a2a.create_internal_error(
                            message=f"Unknown response structure from peer agent for sub-task {sub_task_id}",
                            data={
                                "original_payload": payload_data.model_dump(
                                    by_alias=True, exclude_none=True
                                )
                            },
                        )
                        a2a_response = a2a.create_error_response(
                            error, a2a.get_response_id(a2a_response)
                        )
                        is_final_response = True

                elif error := a2a.get_response_error(a2a_response):
                    log.warning(
                        "%s Received error response from peer for sub-task %s: %s",
                        component.log_identifier,
                        sub_task_id,
                        error,
                    )
                    payload_to_queue = {
                        "error": error.message,
                        "code": error.code,
                        "data": error.data,
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
            # Reset the timeout since we received a status update
            await component.reset_peer_timeout(sub_task_id)
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
                            final_text = get_text_from_message(task_obj.status.message)

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

                                    # Add guidance about artifact_return responsibility
                                    artifact_return_guidance = (
                                        f"\n\n**Note:** If any of these artifacts fulfill the user's request, "
                                        f"you should return them directly to the user using the "
                                        f"{EMBED_DELIMITER_OPEN}artifact_return:filename:version{EMBED_DELIMITER_CLOSE} embed. "
                                        f"This is more convenient for the user than just describing the artifacts. "
                                        f"Replace 'filename' and 'version' with the actual values from the artifact metadata above."
                                    )
                                    artifact_summary += artifact_return_guidance
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
                full_response_text = f"{artifact_summary}\n---\n\nPeer Agent Response:\n\n{full_response_text}"

            await _publish_peer_tool_result_notification(
                component=component,
                correlation_data=correlation_data,
                payload_to_queue=payload_to_queue,
                log_identifier=log_retrigger,
            )

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

        # Define unique URIs for our custom extensions.
        DEPLOYMENT_EXTENSION_URI = "https://solace.com/a2a/extensions/sam/deployment"
        PEER_TOPOLOGY_EXTENSION_URI = (
            "https://solace.com/a2a/extensions/peer-agent-topology"
        )
        DISPLAY_NAME_EXTENSION_URI = "https://solace.com/a2a/extensions/display-name"
        TOOLS_EXTENSION_URI = "https://solace.com/a2a/extensions/sam/tools"

        extensions_list = []

        # Create the extension object for deployment tracking.
        deployment_config = component.get_config("deployment", {})
        deployment_id = deployment_config.get("id")

        if deployment_id:
            deployment_extension = AgentExtension(
                uri=DEPLOYMENT_EXTENSION_URI,
                description="SAM deployment tracking for rolling updates",
                required=False,
                params={"id": deployment_id}
            )
            extensions_list.append(deployment_extension)
            log.debug(
                "%s Added deployment extension with ID: %s",
                component.log_identifier,
                deployment_id
            )

        # Create the extension object for peer agents.
        if peer_agents:
            peer_topology_extension = AgentExtension(
                uri=PEER_TOPOLOGY_EXTENSION_URI,
                description="A list of peer agents this agent is configured to communicate with.",
                params={"peer_agent_names": list(peer_agents.keys())},
            )
            extensions_list.append(peer_topology_extension)

        # Create the extension object for the UI display name.
        if display_name:
            display_name_extension = AgentExtension(
                uri=DISPLAY_NAME_EXTENSION_URI,
                description="A UI-friendly display name for the agent.",
                params={"display_name": display_name},
            )
            extensions_list.append(display_name_extension)

        # Create the extension object for the agent's tools.
        dynamic_tools = getattr(component, "agent_card_tool_manifest", [])
        if dynamic_tools:
            # Ensure all tools have a 'tags' field to prevent validation errors.
            processed_tools = []
            for tool in dynamic_tools:
                if "tags" not in tool:
                    log.debug(
                        "%s Tool '%s' in manifest is missing 'tags' field. Defaulting to empty list.",
                        component.log_identifier,
                        tool.get("id", "unknown"),
                    )
                    tool["tags"] = []
                processed_tools.append(tool)

            tools_params = ToolsExtensionParams(tools=processed_tools)
            tools_extension = AgentExtension(
                uri=TOOLS_EXTENSION_URI,
                description="A list of tools available to the agent.",
                params=tools_params.model_dump(exclude_none=True),
            )
            extensions_list.append(tools_extension)

        # Build the capabilities object, including our custom extensions.
        capabilities = AgentCapabilities(
            streaming=supports_streaming,
            push_notifications=False,
            state_transition_history=False,
            extensions=extensions_list if extensions_list else None,
        )

        skills_from_config = card_config.get("skills", [])
        # The 'tools' field is not part of the official AgentCard spec.
        # The tools are now included as an extension.

        # Ensure all skills have a 'tags' field to prevent validation errors.
        processed_skills = []
        for skill in skills_from_config:
            if "tags" not in skill:
                skill["tags"] = []
            processed_skills.append(skill)

        agent_card = AgentCard(
            name=agent_name,
            protocol_version=card_config.get("protocolVersion", "0.3.0"),
            version=component.HOST_COMPONENT_VERSION,
            url=dynamic_url,
            capabilities=capabilities,
            description=card_config.get("description", ""),
            skills=processed_skills,
            default_input_modes=card_config.get("defaultInputModes", ["text"]),
            default_output_modes=card_config.get("defaultOutputModes", ["text"]),
            documentation_url=card_config.get("documentationUrl"),
            provider=card_config.get("provider"),
        )

        discovery_topic = get_discovery_topic(namespace)

        component.publish_a2a_message(
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


def handle_sam_event(component, message, topic):
    """Handle incoming SAM system events."""
    try:
        payload = message.get_payload()

        if not isinstance(payload, dict):
            log.warning("Invalid SAM event payload - not a dict")
            message.call_acknowledgements()
            return

        event_type = payload.get("event_type")
        if not event_type:
            log.warning("SAM event missing event_type field")
            message.call_acknowledgements()
            return

        log.info("%s Received SAM event: %s", component.log_identifier, event_type)

        if event_type == "session.deleted":
            data = payload.get("data", {})
            session_id = data.get("session_id")
            user_id = data.get("user_id")
            agent_id = data.get("agent_id")

            if not all([session_id, user_id, agent_id]):
                log.warning("Missing required fields in session.deleted event")
                message.call_acknowledgements()
                return

            current_agent = component.get_config("agent_name")

            if agent_id == current_agent:
                log.info(
                    "%s Processing session.deleted event for session %s",
                    component.log_identifier,
                    session_id,
                )
                asyncio.create_task(
                    cleanup_agent_session(component, session_id, user_id)
                )
            else:
                log.debug(
                    "Session deletion event for different agent: %s != %s",
                    agent_id,
                    current_agent,
                )
        else:
            log.debug("Unhandled SAM event type: %s", event_type)

        message.call_acknowledgements()

    except Exception as e:
        log.error("Error handling SAM event %s: %s", topic, e)
        message.call_acknowledgements()


async def cleanup_agent_session(component, session_id: str, user_id: str):
    """Clean up agent-side session data."""
    try:
        log.info("Starting cleanup for session %s, user %s", session_id, user_id)

        if hasattr(component, "session_service") and component.session_service:
            agent_name = component.get_config("agent_name")
            log.info(
                "Deleting session %s from agent %s session service",
                session_id,
                agent_name,
            )
            await component.session_service.delete_session(
                app_name=agent_name, user_id=user_id, session_id=session_id
            )
            log.info("Successfully deleted session %s from session service", session_id)
        else:
            log.info("No session service available for cleanup")

        with component.active_tasks_lock:
            tasks_to_cancel = []
            for task_id, context in component.active_tasks.items():
                if (
                    hasattr(context, "a2a_context")
                    and context.a2a_context.get("session_id") == session_id
                ):
                    tasks_to_cancel.append(task_id)

            for task_id in tasks_to_cancel:
                context = component.active_tasks.get(task_id)
                if context:
                    context.cancel()
                    log.info(
                        "Cancelled task %s for deleted session %s", task_id, session_id
                    )

        log.info("Session cleanup completed for session %s", session_id)

    except Exception as e:
        log.error("Error cleaning up session %s: %s", session_id, e)
