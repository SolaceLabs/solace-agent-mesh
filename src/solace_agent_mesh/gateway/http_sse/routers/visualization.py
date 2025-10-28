"""
API Router for managing A2A message visualization streams.
"""

import logging
import asyncio
import uuid
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request as FastAPIRequest,
    Response,
    status,
)
from pydantic import BaseModel, Field
import json
from typing import List, Optional, Dict, Any, Set


from ....gateway.http_sse.dependencies import (
    get_sac_component,
    get_user_id,
    get_sse_manager,
)
from ....gateway.http_sse.sse_manager import SSEManager
from ....common.middleware.registry import MiddlewareRegistry

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ....gateway.http_sse.component import WebUIBackendComponent

log = logging.getLogger(__name__)
trace_logger = logging.getLogger("sam_trace")

router = APIRouter()


class SubscriptionTarget(BaseModel):
    """Defines an abstract target for A2A message visualization."""

    type: str = Field(
        ...,
        description="Type of the target to monitor.",
        examples=[
            "my_a2a_messages",
            "current_namespace_a2a_messages",
            "namespace_a2a_messages",
            "agent_a2a_messages",
        ],
    )
    identifier: Optional[str] = Field(
        default=None,
        description="Identifier for the target (e.g., namespace string or agent name). Not required if type is 'current_namespace_a2a_messages'.",
    )


class ActualSubscribedTarget(SubscriptionTarget):
    """Represents an abstract target that the gateway attempted to subscribe to, including its status."""

    status: str = Field(
        ...,
        description="Status of the subscription attempt for this target.",
        examples=["subscribed", "denied_due_to_scope", "error_translating_target"],
    )


class VisualizationSubscribeRequest(BaseModel):
    """Request body for initiating a visualization stream."""

    subscription_targets: Optional[List[SubscriptionTarget]] = Field(
        default_factory=list,
        description="Optional list of abstract targets to monitor.",
    )
    client_stream_id: Optional[str] = Field(
        default=None,
        description="Optional client-generated ID for idempotency or re-association. If not provided, a new one is generated.",
    )


class VisualizationSubscribeResponse(BaseModel):
    """Response body for a successful visualization subscription."""

    stream_id: str = Field(..., description="Unique ID for the visualization stream.")
    sse_endpoint_url: str = Field(..., description="URL for the SSE event stream.")
    actual_subscribed_targets: List[ActualSubscribedTarget] = Field(
        default_factory=list,
        description="List of abstract targets processed, with their subscription status.",
    )
    message: str = "Visualization stream initiated. Connect to the SSE endpoint."


class VisualizationConfigUpdateRequest(BaseModel):
    """Request body for updating an active visualization stream's configuration."""

    subscription_targets_to_add: Optional[List[SubscriptionTarget]] = Field(
        default=None,
        description="List of new abstract targets to add to the subscription.",
    )
    subscription_targets_to_remove: Optional[List[SubscriptionTarget]] = Field(
        default=None,
        description="List of abstract targets to remove from the subscription.",
    )


class VisualizationConfigUpdateResponse(BaseModel):
    """Response body for a successful visualization configuration update."""

    stream_id: str = Field(..., description="ID of the updated visualization stream.")
    message: str = "Visualization stream configuration updated successfully."
    current_subscribed_targets: List[ActualSubscribedTarget] = Field(
        default_factory=list,
        description="Current list of active abstract targets for this stream, with their status.",
    )


class VisualizationSubscriptionError(BaseModel):
    """Error response for subscription failures."""

    message: str = Field(..., description="Human-readable error message")
    failed_targets: List[ActualSubscribedTarget] = Field(
        ..., description="List of targets that failed to subscribe"
    )
    error_type: str = Field(
        ...,
        description="Type of error: 'authorization_failure' or 'subscription_failure'",
    )
    suggested_action: Optional[str] = Field(
        default=None, description="Suggested action for the user"
    )


from sse_starlette.sse import EventSourceResponse


def _generate_sse_url(fastapi_request: FastAPIRequest, stream_id: str) -> str:
    """
    Generate SSE endpoint URL with proper scheme and host detection for reverse proxy scenarios.

    Args:
        fastapi_request: The FastAPI request object
        stream_id: The stream ID for the SSE endpoint

    Returns:
        Complete SSE URL with correct scheme (http/https) and host.
    """
    base_url = fastapi_request.url_for(
        "get_visualization_stream_events", stream_id=stream_id
    )

    forwarded_proto = fastapi_request.headers.get("x-forwarded-proto")
    forwarded_host = fastapi_request.headers.get("x-forwarded-host")

    if forwarded_proto and forwarded_host:
        # In a reverse proxy environment like GitHub Codespaces, reconstruct the URL
        # using the forwarded headers to ensure it's publicly accessible.
        return str(base_url.replace(scheme=forwarded_proto, netloc=forwarded_host))
    elif forwarded_proto:
        # Handle cases with only a forwarded protocol (standard reverse proxy)
        return str(base_url.replace(scheme=forwarded_proto))
    else:
        # Default behavior when not behind a reverse proxy
        return str(base_url)


def _translate_target_to_solace_topics(
    target: SubscriptionTarget, component_namespace: str
) -> List[str]:
    """Translates an abstract SubscriptionTarget to a list of Solace topic strings."""
    topics = []
    target_identifier = target.identifier.strip("/") if target.identifier else ""
    component_namespace_formatted = component_namespace.strip("/")
    if target.type == "current_namespace_a2a_messages":
        topics.append(f"{component_namespace_formatted}/a2a/>")
    elif target.type == "namespace_a2a_messages":
        if not target.identifier:
            log.warning(f"Identifier missing for target type {target.type}")
            return []
        topics.append(f"{target_identifier}/a2a/>")
    elif target.type == "agent_a2a_messages":
        if not target.identifier:
            log.warning(f"Identifier missing for target type {target.type}")
            return []
        base_agent_topic = f"{component_namespace_formatted}/a2a/v1/agent"
        topics.append(f"{base_agent_topic}/request/{target_identifier}/>")
        topics.append(f"{base_agent_topic}/response/{target_identifier}/>")
        topics.append(f"{base_agent_topic}/status/{target_identifier}/>")
    else:
        log.warning(f"Unknown subscription target type: {target.type}")
    return topics


def _resolve_user_identity_for_authorization(
    component: "WebUIBackendComponent", raw_user_id: str
) -> str:
    """
    Applies the same user identity resolution logic as BaseGatewayComponent.submit_a2a_task().
    This ensures visualization authorization uses the same identity resolution as task submission.

    Args:
        component: The WebUIBackendComponent instance
        raw_user_id: The raw user ID from the session (e.g., web-client-xxxxx)

    Returns:
        The resolved user identity to use for authorization
    """
    log_id_prefix = f"{component.log_identifier}[ResolveUserIdentity]"
    user_identity = raw_user_id

    force_identity = component.get_config("force_user_identity")
    if force_identity:
        original_identity = user_identity
        user_identity = force_identity
        log.info(
            "%s DEVELOPMENT MODE: Forcing user_identity from '%s' to '%s' for visualization",
            log_id_prefix,
            original_identity,
            user_identity,
        )
        return user_identity

    if not user_identity:
        use_authorization = component.get_config("frontend_use_authorization", False)
        if not use_authorization:
            user_identity = "sam_dev_user"
            log.info(
                "%s No user_identity provided and auth is disabled, using sam_dev_user for visualization",
                log_id_prefix,
            )
        else:
            log.error(
                "%s No user_identity provided but authorization is enabled. This should not happen.",
                log_id_prefix,
            )
            raise ValueError(
                "No user identity available when authorization is required"
            )

    return user_identity


def _include_for_visualization(event_payload: Dict[str, Any]) -> bool:
    """
    Check if an event should be included for visualization based on metadata.

    Args:
        event_payload: The event payload containing event data

    Returns:
        False if the event should be excluded from visualization (when visualization is False),
        True otherwise (include by default)
    """
    try:
        # Get the data field from the event payload
        data_str = event_payload.get("data")
        if not data_str:
            return True  # Include by default if no data

        # Parse the JSON data
        try:
            data = json.loads(data_str)
        except (json.JSONDecodeError, TypeError):
            return True

        # Look for the full_payload in the data
        full_payload = data.get("full_payload")
        if not full_payload:
            return True

        # Check if full_payload has params
        params = full_payload.get("params")
        if not params:
            return True

        # Check if params has message
        message = params.get("message")
        if not message:
            return True

        # Check if message has metadata
        metadata = message.get("metadata")
        if not metadata:
            return True

        # Check the visualization setting in metadata
        visualization_setting = metadata.get("visualization")
        if visualization_setting is not None and (
            (
                isinstance(visualization_setting, str)
                and visualization_setting.lower() == "false"
            )
            or (
                isinstance(visualization_setting, bool)
                and visualization_setting is False
            )
        ):
            return False

        return True

    except Exception as e:
        log.warning("Error checking visualization filter for event: %s", e)
        return True


@router.post(
    "/subscribe",
    response_model=VisualizationSubscribeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def subscribe_to_visualization_stream(
    request_data: VisualizationSubscribeRequest,
    fastapi_request: FastAPIRequest,
    component: "WebUIBackendComponent" = Depends(get_sac_component),
    user_id: str = Depends(get_user_id),
    sse_manager: SSEManager = Depends(get_sse_manager),
):
    """Initiates a new A2A message visualization stream using abstract targets."""
    log_id_prefix = f"{component.log_identifier}[POST /viz/subscribe]"
    log.info(
        "%s Request received from user %s. Client Stream ID: %s",
        log_id_prefix,
        user_id,
        request_data.client_stream_id,
    )

    try:
        component._ensure_visualization_flow_is_running()
    except Exception as e:
        log.exception(
            "%s Failed to ensure visualization flow is running: %s", log_id_prefix, e
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initialize visualization backend.",
        )

    stream_id = request_data.client_stream_id or f"viz-stream-{uuid.uuid4().hex}"

    log.debug(
        "%s Acquiring viz lock to check for existing stream %s",
        log_id_prefix,
        stream_id,
    )
    async with component._get_visualization_lock():
        if stream_id in component._active_visualization_streams:
            existing_stream_data = component._active_visualization_streams[stream_id]
            if existing_stream_data.get("user_id") != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Client stream ID already in use by another user.",
                )

            log.warning(
                "%s Stream ID %s (client-provided) already exists. Returning existing info.",
                log_id_prefix,
                stream_id,
            )
            sse_url = _generate_sse_url(fastapi_request, stream_id)
            return VisualizationSubscribeResponse(
                stream_id=stream_id,
                sse_endpoint_url=sse_url,
                actual_subscribed_targets=existing_stream_data.get(
                    "abstract_targets", []
                ),
                message="Visualization stream with this client_stream_id already exists and is active.",
            )
    log.debug(
        "%s Released viz lock after checking for existing stream %s",
        log_id_prefix,
        stream_id,
    )

    try:
        sse_queue = await sse_manager.create_sse_connection(stream_id)
    except Exception as e:
        log.exception(
            "%s Failed to create SSE connection queue for stream %s: %s",
            log_id_prefix,
            stream_id,
            e,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to establish SSE infrastructure.",
        )

    resolved_user_identity = _resolve_user_identity_for_authorization(
        component, user_id
    )
    log.debug(
        "%s Resolved user identity for authorization: '%s' (from raw user_id: '%s')",
        log_id_prefix,
        resolved_user_identity,
        user_id,
    )

    config_resolver = MiddlewareRegistry.get_config_resolver()
    gateway_context = {
        "gateway_id": component.gateway_id,
        "request": fastapi_request,
        "gateway_namespace": component.namespace,
    }
    user_config: Dict[str, Any] = {}
    try:
        user_config = await config_resolver.resolve_user_config(
            resolved_user_identity, gateway_context, {}
        )
        log.debug(
            "%s Resolved user_config for resolved_user_identity '%s': %s",
            log_id_prefix,
            resolved_user_identity,
            {k: v for k, v in user_config.items() if not k.startswith("_")},
        )
    except Exception as config_err:
        log.exception(
            "%s Error resolving user_config for user %s: %s. Proceeding with empty config.",
            log_id_prefix,
            resolved_user_identity,
            config_err,
        )
        user_config = {}
    processed_targets_for_response: List[ActualSubscribedTarget] = []
    current_solace_topics_for_stream: Set[str] = set()
    current_abstract_targets_for_stream: List[ActualSubscribedTarget] = []

    initial_stream_config = {
        "user_id": user_id,
        "user_config": user_config,
        "solace_topics": current_solace_topics_for_stream,
        "abstract_targets": current_abstract_targets_for_stream,
        "sse_queue": sse_queue,
        "client_stream_id": request_data.client_stream_id,
    }
    log.debug(
        "%s Acquiring viz lock to add initial stream config for %s",
        log_id_prefix,
        stream_id,
    )
    async with component._get_visualization_lock():
        component._active_visualization_streams[stream_id] = initial_stream_config
    log.debug(
        "%s Released viz lock after adding initial stream config for %s",
        log_id_prefix,
        stream_id,
    )

    targets_to_process = request_data.subscription_targets
    if not targets_to_process:
        log.info(
            "%s No subscription targets provided, defaulting to current namespace.",
            log_id_prefix,
        )
        targets_to_process = [SubscriptionTarget(type="current_namespace_a2a_messages")]

    log.debug(
        "%s Starting to process %d subscription targets.",
        log_id_prefix,
        len(targets_to_process),
    )
    for target_request_idx, target_request in enumerate(targets_to_process):
        log.debug(
            "%s Processing target %d/%d: %s",
            log_id_prefix,
            target_request_idx + 1,
            len(targets_to_process),
            target_request.model_dump(),
        )
        target_status = "denied_due_to_scope"
        required_scope = ""
        effective_identifier = target_request.identifier

        if target_request.type == "current_namespace_a2a_messages":
            effective_identifier = component.namespace
            required_scope = (
                f"monitor/namespace/{effective_identifier}:a2a_messages:subscribe"
            )
        elif target_request.type == "namespace_a2a_messages":
            if not effective_identifier:
                log.warning(
                    "%s Identifier missing for target type 'namespace_a2a_messages'",
                    log_id_prefix,
                )
                target_status = "error_missing_identifier"
                processed_targets_for_response.append(
                    ActualSubscribedTarget(
                        **target_request.model_dump(), status=target_status
                    )
                )
                continue
            required_scope = (
                f"monitor/namespace/{effective_identifier}:a2a_messages:subscribe"
            )
        elif target_request.type == "agent_a2a_messages":
            if not effective_identifier:
                log.warning(
                    "%s Identifier missing for target type 'agent_a2a_messages'",
                    log_id_prefix,
                )
                target_status = "error_missing_identifier"
                processed_targets_for_response.append(
                    ActualSubscribedTarget(
                        **target_request.model_dump(), status=target_status
                    )
                )
                continue

            pass
        elif target_request.type == "my_a2a_messages":
            operation_spec = {
                "operation_type": "visualization_subscription",
                "target_type": "my_a2a_messages",
            }
            validation_result = config_resolver.validate_operation_config(
                user_config, operation_spec, gateway_context
            )
            has_permission = validation_result.get("valid", False)

            if has_permission:
                target_status = "subscribed"
                response_target_data = target_request.model_dump()
                current_abstract_targets_for_stream.append(
                    ActualSubscribedTarget(**response_target_data, status=target_status)
                )

                firehose_topic = f"{component.namespace.strip('/')}/a2a/>"
                log.debug(
                    "%s Adding firehose subscription '%s' for my_a2a_messages stream.",
                    log_id_prefix,
                    firehose_topic,
                )
                if not await component._add_visualization_subscription(
                    firehose_topic, stream_id
                ):
                    log.error(
                        "%s Failed to add required firehose subscription for my_a2a_messages.",
                        log_id_prefix,
                    )
                    target_status = "error_adding_subscription"
                    current_abstract_targets_for_stream.pop()

            else:
                log.warning(
                    "%s User %s denied subscription to 'my_a2a_messages' due to missing scope.",
                    log_id_prefix,
                    resolved_user_identity,
                )
            processed_targets_for_response.append(
                ActualSubscribedTarget(
                    **target_request.model_dump(), status=target_status
                )
            )
            continue
        else:
            log.warning(
                "%s Unknown subscription target type: %s for identifier %s",
                log_id_prefix,
                target_request.type,
                effective_identifier,
            )
            target_status = "error_unknown_target_type"
            processed_targets_for_response.append(
                ActualSubscribedTarget(
                    **target_request.model_dump(), status=target_status
                )
            )
            continue

        identifier_for_spec = target_request.identifier
        if (
            target_request.type == "current_namespace_a2a_messages"
            and target_request.identifier is None
        ):
            identifier_for_spec = None

        operation_spec = {
            "operation_type": "visualization_subscription",
            "target_type": target_request.type,
            "target_identifier": identifier_for_spec,
        }

        validation_result = config_resolver.validate_operation_config(
            user_config, operation_spec, gateway_context
        )
        has_permission = validation_result.get("valid", False)

        if has_permission:
            target_for_translation = target_request
            if target_request.type == "current_namespace_a2a_messages":
                target_for_translation = SubscriptionTarget(
                    type="namespace_a2a_messages", identifier=effective_identifier
                )

            solace_topics_for_target = _translate_target_to_solace_topics(
                target_for_translation, component.namespace
            )
            if not solace_topics_for_target:
                log.warning(
                    "%s No Solace topics derived for target: %s",
                    log_id_prefix,
                    target_request.model_dump(),
                )
                target_status = "error_translating_target"
            else:
                all_topics_added_successfully = True
                for topic_str in solace_topics_for_target:
                    success = await component._add_visualization_subscription(
                        topic_str, stream_id
                    )
                    if success:
                        current_solace_topics_for_stream.add(topic_str)
                    else:
                        all_topics_added_successfully = False
                        log.error(
                            "%s Failed to add subscription to Solace topic: %s for stream %s (target: %s)",
                            log_id_prefix,
                            topic_str,
                            stream_id,
                            effective_identifier,
                        )

                if all_topics_added_successfully:
                    target_status = "subscribed"
                    response_target_data = target_request.model_dump()
                    if target_request.type == "current_namespace_a2a_messages":
                        response_target_data["identifier"] = effective_identifier
                    current_abstract_targets_for_stream.append(
                        ActualSubscribedTarget(
                            **response_target_data, status=target_status
                        )
                    )
                else:
                    target_status = "error_adding_subscription"
        else:
            log.warning(
                "%s User %s denied subscription to target %s (type: %s) due to missing scope: %s",
                log_id_prefix,
                resolved_user_identity,
                effective_identifier,
                target_request.type,
                required_scope,
            )

        response_target_data_for_processed_list = target_request.model_dump()
        if (
            target_request.type == "current_namespace_a2a_messages"
            and target_status == "subscribed"
        ):
            response_target_data_for_processed_list["identifier"] = effective_identifier

        processed_targets_for_response.append(
            ActualSubscribedTarget(
                **response_target_data_for_processed_list, status=target_status
            )
        )
    log.debug("%s Finished processing all subscription targets.", log_id_prefix)

    successful_subscriptions = [
        target
        for target in processed_targets_for_response
        if target.status == "subscribed"
    ]

    if not successful_subscriptions:
        log.warning(
            "%s All subscription targets failed for user %s. Cleaning up stream %s.",
            log_id_prefix,
            user_id,
            stream_id,
        )

        try:
            await sse_manager.close_all_for_task(stream_id)
        except Exception as cleanup_error:
            log.warning(
                "%s Failed to cleanup SSE connection for stream %s: %s",
                log_id_prefix,
                stream_id,
                cleanup_error,
            )

        log.debug(
            "%s Acquiring viz lock to clean up failed stream %s",
            log_id_prefix,
            stream_id,
        )
        async with component._get_visualization_lock():
            component._active_visualization_streams.pop(stream_id, None)
        log.debug(
            "%s Released viz lock after cleaning up failed stream %s",
            log_id_prefix,
            stream_id,
        )

        denied_targets = [
            target
            for target in processed_targets_for_response
            if target.status == "denied_due_to_scope"
        ]

        if denied_targets:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "message": "Access denied: insufficient permissions for all requested targets",
                    "failed_targets": [
                        target.model_dump() for target in processed_targets_for_response
                    ],
                    "error_type": "authorization_failure",
                    "suggested_action": "Please check your permissions or contact your administrator",
                },
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": "All subscription targets failed to process",
                    "failed_targets": [
                        target.model_dump() for target in processed_targets_for_response
                    ],
                    "error_type": "subscription_failure",
                    "suggested_action": "Please check your target specifications and try again",
                },
            )

    failed_targets = [
        target
        for target in processed_targets_for_response
        if target.status != "subscribed"
    ]

    response_message = "Visualization stream initiated. Connect to the SSE endpoint."
    if failed_targets:
        response_message = f"Visualization stream initiated with {len(successful_subscriptions)} successful and {len(failed_targets)} failed subscriptions."
        log.warning(
            "%s Partial subscription success for user %s: %d successful, %d failed",
            log_id_prefix,
            user_id,
            len(successful_subscriptions),
            len(failed_targets),
        )

    sse_url = _generate_sse_url(fastapi_request, stream_id)
    log.info(
        "%s Visualization stream %s initiated for user %s. SSE URL: %s. Processed Targets: %s",
        log_id_prefix,
        stream_id,
        user_id,
        sse_url,
        processed_targets_for_response,
    )

    return VisualizationSubscribeResponse(
        stream_id=stream_id,
        sse_endpoint_url=sse_url,
        actual_subscribed_targets=processed_targets_for_response,
        message=response_message,
    )


@router.get("/{stream_id}/events")
async def get_visualization_stream_events(
    stream_id: str,
    fastapi_request: FastAPIRequest,
    component: "WebUIBackendComponent" = Depends(get_sac_component),
    sse_manager: SSEManager = Depends(get_sse_manager),
    user_id: str = Depends(get_user_id),
):
    """Establishes an SSE connection for receiving filtered A2A messages for a specific stream."""
    log_id_prefix = f"{component.log_identifier}[GET /viz/{stream_id}/events]"
    log.info("%s Client %s requesting SSE connection.", log_id_prefix, user_id)

    stream_config: Optional[Dict[str, Any]] = None
    log.debug(
        "%s Acquiring viz lock to get stream config for %s", log_id_prefix, stream_id
    )
    async with component._get_visualization_lock():
        stream_config = component._active_visualization_streams.get(stream_id)
    log.debug(
        "%s Released viz lock after getting stream config for %s",
        log_id_prefix,
        stream_id,
    )

    if not stream_config:
        log.warning("%s Stream ID %s not found.", log_id_prefix, stream_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Visualization stream not found.",
        )

    stream_owner_id = stream_config.get("user_id")
    resolved_stream_owner = _resolve_user_identity_for_authorization(
        component, stream_owner_id
    )
    resolved_requester = _resolve_user_identity_for_authorization(component, user_id)

    if resolved_stream_owner != resolved_requester:
        log.warning(
            "%s User %s (resolved: %s) forbidden to access stream %s owned by %s (resolved: %s).",
            log_id_prefix,
            user_id,
            resolved_requester,
            stream_id,
            stream_owner_id,
            resolved_stream_owner,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access to this visualization stream is forbidden.",
        )

    sse_queue: Optional[asyncio.Queue] = stream_config.get("sse_queue")
    if not sse_queue:
        log.error(
            "%s SSE queue not found for stream ID %s, though stream config exists.",
            log_id_prefix,
            stream_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error: SSE queue missing for stream.",
        )

    async def event_generator():
        log.debug(
            "%s SSE event generator started for stream %s.", log_id_prefix, stream_id
        )
        try:
            yield {
                "comment": f"SSE connection established for visualization stream {stream_id}"
            }
            while True:
                if await fastapi_request.is_disconnected():
                    log.info(
                        "%s Client disconnected from stream %s.",
                        log_id_prefix,
                        stream_id,
                    )
                    break
                try:
                    event_payload = await asyncio.wait_for(sse_queue.get(), timeout=30)
                    if event_payload is None:
                        log.info(
                            "%s SSE queue for stream %s received None sentinel. Closing connection.",
                            log_id_prefix,
                            stream_id,
                        )
                        break
                    if _include_for_visualization(event_payload):
                        if trace_logger.isEnabledFor(logging.DEBUG):
                            trace_logger.debug(
                                "%s Yielding event for stream %s: %s",
                                log_id_prefix,
                                stream_id,
                                event_payload,
                            )
                        else:
                            log.debug(
                                "%s Yielding event for stream %s",
                                log_id_prefix,
                                stream_id,
                            )
                        yield event_payload
                    sse_queue.task_done()
                except asyncio.TimeoutError:
                    yield {"comment": "keep-alive"}
                    continue
                except asyncio.CancelledError:
                    log.debug(
                        "%s SSE event generator for stream %s cancelled.",
                        log_id_prefix,
                        stream_id,
                    )
                    break
        except Exception as e:
            log.exception(
                "%s Error in SSE event generator for stream %s: %s",
                log_id_prefix,
                stream_id,
                e,
            )
        finally:
            log.debug(
                "%s SSE event generator for stream %s finished.",
                log_id_prefix,
                stream_id,
            )

    return EventSourceResponse(event_generator())


@router.put("/{stream_id}/config", response_model=VisualizationConfigUpdateResponse)
async def update_visualization_stream_config(
    stream_id: str,
    update_request: VisualizationConfigUpdateRequest,
    component: "WebUIBackendComponent" = Depends(get_sac_component),
    user_id: str = Depends(get_user_id),
):
    """Modifies the configuration of an active visualization stream."""
    log_id_prefix = f"{component.log_identifier}[PUT /viz/{stream_id}/config]"
    log.info(
        "%s Request received from user %s to update stream.", log_id_prefix, user_id
    )

    log.debug(
        "%s Acquiring viz lock to update stream config for %s", log_id_prefix, stream_id
    )
    async with component._get_visualization_lock():
        stream_config = component._active_visualization_streams.get(stream_id)
        if not stream_config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Visualization stream not found.",
            )

        if stream_config.get("user_id") != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User not authorized to modify this stream.",
            )

        user_config = stream_config.get("user_config", {})
        config_resolver = MiddlewareRegistry.get_config_resolver()
        gateway_context_for_validation = {
            "gateway_id": component.gateway_id,
            "gateway_namespace": component.namespace,
        }
        current_abstract_targets: List[ActualSubscribedTarget] = [
            ActualSubscribedTarget(**t.model_dump())
            for t in stream_config.get("abstract_targets", [])
        ]
        current_solace_topics: Set[str] = stream_config.get(
            "solace_topics", set()
        ).copy()

        if update_request.subscription_targets_to_remove:
            targets_actually_removed_abstract = []
            for target_to_remove_req in update_request.subscription_targets_to_remove:
                effective_identifier_remove = target_to_remove_req.identifier
                target_for_translation_remove = target_to_remove_req

                if target_to_remove_req.type == "current_namespace_a2a_messages":
                    effective_identifier_remove = component.namespace
                    target_for_translation_remove = SubscriptionTarget(
                        type="namespace_a2a_messages",
                        identifier=effective_identifier_remove,
                    )

                if (
                    not effective_identifier_remove
                    and target_to_remove_req.type != "current_namespace_a2a_messages"
                ):
                    log.warning(
                        "%s Identifier missing for removal target type %s. Skipping.",
                        log_id_prefix,
                        target_to_remove_req.type,
                    )
                    continue

                solace_topics_for_removal = _translate_target_to_solace_topics(
                    target_for_translation_remove, component.namespace
                )
                removed_any_solace_topic_for_this_abstract_target = False
                for topic_str in solace_topics_for_removal:
                    if topic_str in current_solace_topics:
                        if await component._remove_visualization_subscription_nolock(
                            topic_str, stream_id
                        ):
                            log.info(
                                "%s Unsubscribed (no-lock) from Solace topic: %s for stream %s (due to removal of %s)",
                                log_id_prefix,
                                topic_str,
                                stream_id,
                                effective_identifier_remove,
                            )
                            current_solace_topics.remove(topic_str)
                            removed_any_solace_topic_for_this_abstract_target = True
                        else:
                            log.error(
                                "%s Failed to unsubscribe from Solace topic: %s for stream %s",
                                log_id_prefix,
                                topic_str,
                                stream_id,
                            )

                if removed_any_solace_topic_for_this_abstract_target:
                    if target_to_remove_req.type == "current_namespace_a2a_messages":
                        current_abstract_targets = [
                            t
                            for t in current_abstract_targets
                            if not (
                                t.type == target_to_remove_req.type
                                or (
                                    t.type == "namespace_a2a_messages"
                                    and t.identifier == effective_identifier_remove
                                )
                            )
                        ]
                    else:
                        current_abstract_targets = [
                            t
                            for t in current_abstract_targets
                            if not (
                                t.type == target_to_remove_req.type
                                and t.identifier == effective_identifier_remove
                            )
                        ]
                    targets_actually_removed_abstract.append(
                        effective_identifier_remove
                    )

            log.info(
                "%s Processed removals. Abstract targets effectively removed identifiers: %s",
                log_id_prefix,
                targets_actually_removed_abstract,
            )

        if update_request.subscription_targets_to_add:
            for target_to_add_req in update_request.subscription_targets_to_add:
                effective_identifier_add = target_to_add_req.identifier
                target_for_translation_add = target_to_add_req
                original_type_add = target_to_add_req.type

                if target_to_add_req.type == "current_namespace_a2a_messages":
                    effective_identifier_add = component.namespace
                    target_for_translation_add = SubscriptionTarget(
                        type="namespace_a2a_messages",
                        identifier=effective_identifier_add,
                    )

                is_already_present = False
                for existing_target in current_abstract_targets:
                    if existing_target.type == original_type_add and (
                        original_type_add == "current_namespace_a2a_messages"
                        or existing_target.identifier == effective_identifier_add
                    ):
                        is_already_present = True
                        break
                    if (
                        original_type_add == "namespace_a2a_messages"
                        and existing_target.type == "current_namespace_a2a_messages"
                        and effective_identifier_add == component.namespace
                    ):
                        is_already_present = True
                        break

                if is_already_present:
                    log.info(
                        "%s Target %s (type: %s) effectively already subscribed. Skipping add.",
                        log_id_prefix,
                        effective_identifier_add,
                        original_type_add,
                    )
                    continue

                target_status = "denied_due_to_scope"
                required_scope = ""

                identifier_for_spec = target_to_add_req.identifier
                if original_type_add == "current_namespace_a2a_messages":
                    if target_to_add_req.identifier is None:
                        identifier_for_spec = None

                operation_spec = {
                    "operation_type": "visualization_subscription_update",
                    "target_type": original_type_add,
                    "target_identifier": identifier_for_spec,
                }

                validation_result = config_resolver.validate_operation_config(
                    user_config, operation_spec, gateway_context_for_validation
                )
                has_permission = validation_result.get("valid", False)

                if has_permission:
                    solace_topics_for_target = _translate_target_to_solace_topics(
                        target_for_translation_add, component.namespace
                    )
                    if not solace_topics_for_target:
                        target_status = "error_translating_target"
                    else:
                        all_topics_added_successfully = True
                        temp_solace_topics_added_for_this_target = set()
                        for topic_str in solace_topics_for_target:
                            if await component._add_visualization_subscription(
                                topic_str, stream_id
                            ):
                                current_solace_topics.add(topic_str)
                                temp_solace_topics_added_for_this_target.add(topic_str)
                            else:
                                all_topics_added_successfully = False
                                log.error(
                                    "%s Failed to add subscription to Solace topic: %s for stream %s (target: %s)",
                                    log_id_prefix,
                                    topic_str,
                                    stream_id,
                                    effective_identifier_add,
                                )

                        if all_topics_added_successfully:
                            target_status = "subscribed"
                            response_target_data = target_to_add_req.model_dump()
                            if original_type_add == "current_namespace_a2a_messages":
                                response_target_data["identifier"] = (
                                    effective_identifier_add
                                )
                            current_abstract_targets.append(
                                ActualSubscribedTarget(
                                    **response_target_data, status=target_status
                                )
                            )
                        else:
                            target_status = "error_adding_subscription"
                            for topic_str in temp_solace_topics_added_for_this_target:
                                await component._remove_visualization_subscription_nolock(
                                    topic_str, stream_id
                                )
                                current_solace_topics.discard(topic_str)
                            log.warning(
                                "%s Rolled back Solace subscriptions (no-lock) for failed abstract target %s",
                                log_id_prefix,
                                effective_identifier_add,
                            )
                else:
                    log.warning(
                        "%s User %s denied subscription to target %s (type: %s) due to missing scope: %s",
                        log_id_prefix,
                        user_id,
                        effective_identifier_add,
                        original_type_add,
                        required_scope,
                    )

                if target_status not in ["subscribed", "denied_due_to_scope"]:
                    failed_target_data = target_to_add_req.model_dump()
                    if original_type_add == "current_namespace_a2a_messages":
                        failed_target_data["identifier"] = effective_identifier_add

        component._active_visualization_streams[stream_id][
            "abstract_targets"
        ] = current_abstract_targets
        component._active_visualization_streams[stream_id][
            "solace_topics"
        ] = current_solace_topics

        log.info(
            "%s Stream %s configuration updated. Current abstract targets: %d, Solace topics: %d",
            log_id_prefix,
            stream_id,
            len(current_abstract_targets),
            len(current_solace_topics),
        )
    log.debug(
        "%s Released viz lock after updating stream config for %s",
        log_id_prefix,
        stream_id,
    )

    return VisualizationConfigUpdateResponse(
        stream_id=stream_id,
        current_subscribed_targets=current_abstract_targets,
    )


@router.delete("/{stream_id}/unsubscribe", status_code=status.HTTP_204_NO_CONTENT)
async def unsubscribe_from_visualization_stream(
    stream_id: str,
    component: "WebUIBackendComponent" = Depends(get_sac_component),
    sse_manager: SSEManager = Depends(get_sse_manager),
    user_id: str = Depends(get_user_id),
):
    """Terminates an active visualization stream."""
    log_id_prefix = f"{component.log_identifier}[DELETE /viz/{stream_id}]"
    log.info(
        "%s Request received from user %s to unsubscribe from stream.",
        log_id_prefix,
        user_id,
    )

    log.debug(
        "%s Acquiring viz lock to unsubscribe from stream %s", log_id_prefix, stream_id
    )
    async with component._get_visualization_lock():
        stream_config = component._active_visualization_streams.get(stream_id)
        if not stream_config:
            log.info(
                "%s Stream %s not found, no action needed.", log_id_prefix, stream_id
            )
            return Response(status_code=status.HTTP_204_NO_CONTENT)

        if stream_config.get("user_id") != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User not authorized to unsubscribe from this stream.",
            )

        topics_to_remove = list(stream_config.get("solace_topics", []))
        for topic_str in topics_to_remove:
            await component._remove_visualization_subscription_nolock(
                topic_str, stream_id
            )

        sse_queue = stream_config.get("sse_queue")
        if sse_queue:
            await sse_manager.close_connection(stream_id, sse_queue)

        component._active_visualization_streams.pop(stream_id, None)
        log.info("%s Stream %s unsubscribed and removed.", log_id_prefix, stream_id)
    log.debug(
        "%s Released viz lock after unsubscribing from stream %s",
        log_id_prefix,
        stream_id,
    )

    return Response(status_code=status.HTTP_204_NO_CONTENT)


log.info("Initialized Router for A2A Message Visualization.")
