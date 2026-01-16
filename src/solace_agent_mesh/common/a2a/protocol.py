"""
Helpers for A2A protocol-level concerns, such as topic construction and
parsing of JSON-RPC requests and responses.
"""
import logging
import re
import uuid
from typing import Any, Dict, Optional, Tuple, Union

from a2a.types import (
    A2ARequest,
    CancelTaskRequest,
    GetTaskSuccessResponse,
    InternalError,
    InvalidRequestError,
    JSONRPCError,
    JSONRPCResponse,
    JSONRPCSuccessResponse,
    Message,
    MessageSendParams,
    SendMessageRequest,
    SendMessageSuccessResponse,
    SendStreamingMessageRequest,
    SendStreamingMessageSuccessResponse,
    Task,
    TaskArtifactUpdateEvent,
    TaskIdParams,
    TaskStatusUpdateEvent,
)

log = logging.getLogger(__name__)

# --- Topic Construction Helpers ---

A2A_VERSION = "v1"
A2A_BASE_PATH = f"a2a/{A2A_VERSION}"


def get_a2a_base_topic(namespace: str) -> str:
    """Returns the base topic prefix for all A2A communication."""
    if not namespace:
        raise ValueError("A2A namespace cannot be empty.")
    return f"{namespace.rstrip('/')}/{A2A_BASE_PATH}"


def get_agent_discovery_topic(namespace: str) -> str:
    """Returns the topic for publishing agent card discovery."""
    return f"{get_a2a_base_topic(namespace)}/discovery/agentcards"


def get_gateway_discovery_topic(namespace: str) -> str:
    """Returns the topic for publishing gateway card discovery."""
    return f"{get_a2a_base_topic(namespace)}/discovery/gatewaycards"


def get_discovery_subscription_topic(namespace: str) -> str:
    """
    Returns a wildcard subscription topic for receiving all discovery messages
    (both agents and gateways).
    """
    return f"{get_a2a_base_topic(namespace)}/discovery/>"


def get_agent_request_topic(namespace: str, agent_name: str) -> str:
    """Returns the topic for sending requests to a specific agent."""
    if not agent_name:
        raise ValueError("Agent name cannot be empty.")
    return f"{get_a2a_base_topic(namespace)}/agent/request/{agent_name}"


def get_gateway_status_topic(namespace: str, gateway_id: str, task_id: str) -> str:
    """
    Returns the specific topic for an agent to publish status updates TO a specific gateway instance.
    """
    if not gateway_id:
        raise ValueError("Gateway ID cannot be empty.")
    if not task_id:
        raise ValueError("Task ID cannot be empty.")
    return f"{get_a2a_base_topic(namespace)}/gateway/status/{gateway_id}/{task_id}"


def get_gateway_response_topic(namespace: str, gateway_id: str, task_id: str) -> str:
    """
    Returns the specific topic for an agent to publish the final response TO a specific gateway instance.
    Includes task_id for potential correlation/filtering, though gateway might subscribe more broadly.
    """
    if not gateway_id:
        raise ValueError("Gateway ID cannot be empty.")
    if not task_id:
        raise ValueError("Task ID cannot be empty.")
    return f"{get_a2a_base_topic(namespace)}/gateway/response/{gateway_id}/{task_id}"


def get_gateway_status_subscription_topic(namespace: str, self_gateway_id: str) -> str:
    """
    Returns the wildcard topic for a gateway instance to subscribe to receive status updates
    intended for it.
    """
    if not self_gateway_id:
        raise ValueError("Gateway ID is required for gateway status subscription")
    return f"{get_a2a_base_topic(namespace)}/gateway/status/{self_gateway_id}/>"


def get_gateway_response_subscription_topic(
    namespace: str, self_gateway_id: str
) -> str:
    """
    Returns the wildcard topic for a gateway instance to subscribe to receive final responses
    intended for it.
    """
    if not self_gateway_id:
        raise ValueError("Gateway ID is required for gateway response subscription")
    return f"{get_a2a_base_topic(namespace)}/gateway/response/{self_gateway_id}/>"


def get_peer_agent_status_topic(
    namespace: str, delegating_agent_name: str, sub_task_id: str
) -> str:
    """
    Returns the topic for publishing status updates for a sub-task *back to the delegating agent*.
    This topic includes the delegating agent's name.
    """
    if not delegating_agent_name:
        raise ValueError("delegating_agent_name is required for peer status topic")
    return (
        f"{get_a2a_base_topic(namespace)}/agent/status/{delegating_agent_name}/{sub_task_id}"
    )


def get_agent_response_topic(
    namespace: str, delegating_agent_name: str, sub_task_id: str
) -> str:
    """
    Returns the specific topic for publishing the final response for a sub-task
    back to the delegating agent. Includes the delegating agent's name.
    """
    if not delegating_agent_name:
        raise ValueError("delegating_agent_name is required for peer response topic")
    if not sub_task_id:
        raise ValueError("sub_task_id is required for peer response topic")
    return f"{get_a2a_base_topic(namespace)}/agent/response/{delegating_agent_name}/{sub_task_id}"


def get_agent_response_subscription_topic(namespace: str, self_agent_name: str) -> str:
    """
    Returns the wildcard topic for an agent to subscribe to receive responses
    for tasks it delegated. Includes the agent's own name.
    """
    if not self_agent_name:
        raise ValueError("self_agent_name is required for agent response subscription")
    return f"{get_a2a_base_topic(namespace)}/agent/response/{self_agent_name}/>"


def get_agent_status_subscription_topic(namespace: str, self_agent_name: str) -> str:
    """
    Returns the wildcard topic for an agent to subscribe to receive status updates
    for tasks it delegated. Includes the agent's own name.
    """
    if not self_agent_name:
        raise ValueError("self_agent_name is required for agent status subscription")
    return f"{get_a2a_base_topic(namespace)}/agent/status/{self_agent_name}/>"


def get_client_response_topic(namespace: str, client_id: str) -> str:
    """Returns the topic for publishing the final response TO a specific client."""
    if not client_id:
        raise ValueError("Client ID cannot be empty.")
    return f"{get_a2a_base_topic(namespace)}/client/response/{client_id}"


def get_client_status_topic(namespace: str, client_id: str, task_id: str) -> str:
    """
    Returns the specific topic for publishing status updates for a task *to the original client*.
    This topic is client and task-specific.
    """
    if not client_id:
        raise ValueError("Client ID cannot be empty.")
    if not task_id:
        raise ValueError("Task ID cannot be empty.")
    return f"{get_a2a_base_topic(namespace)}/client/status/{client_id}/{task_id}"


def get_client_status_subscription_topic(namespace: str, client_id: str) -> str:
    """
    Returns the wildcard topic for a client to subscribe to receive status updates
    for tasks it initiated. Includes the client's own ID.
    """
    if not client_id:
        raise ValueError("Client ID cannot be empty.")
    return f"{get_a2a_base_topic(namespace)}/client/status/{client_id}/>"


def get_sam_events_topic(namespace: str, category: str, action: str) -> str:
    """Returns SAM system events topic."""
    if not namespace:
        raise ValueError("Namespace cannot be empty.")
    if not category:
        raise ValueError("Category cannot be empty.")
    if not action:
        raise ValueError("Action cannot be empty.")
    return f"{namespace.rstrip('/')}/sam/events/{category}/{action}"


def get_feedback_topic(namespace: str) -> str:
    """Returns the topic for publishing user feedback events."""
    return f"{namespace.rstrip('/')}/sam/v1/feedback/submit"


def get_sam_events_subscription_topic(namespace: str, category: str) -> str:
    """Returns SAM system events subscription topic."""
    if not namespace:
        raise ValueError("Namespace cannot be empty.")
    if not category:
        raise ValueError("Category cannot be empty.")
    return f"{namespace.rstrip('/')}/sam/events/{category}/>"


def get_trust_card_topic(namespace: str, component_type: str, component_id: str) -> str:
    """
    Returns the topic for publishing a Trust Card.

    IMPORTANT: The component_id parameter MUST be the exact broker client-username
    that the component uses to authenticate with the Solace broker. This is critical
    for trust verification - trust cards are validated against the actual broker
    authentication identity.

    Args:
        namespace: SAM namespace
        component_type: Type of component ("gateway", "agent", etc.)
        component_id: MUST be the broker client-username (from broker_username config).
                     DO NOT use arbitrary IDs like agent_name or gateway_id unless they
                     match the broker_username exactly.

    Returns:
        Topic string: {namespace}/a2a/v1/trust/{component_type}/{component_id}

    Raises:
        ValueError: If any parameter is empty

    Security Note:
        Trust card verification relies on matching the topic component_id with the
        authenticated broker client-username. Using a different value breaks the
        security model and trust chain verification.
    """
    if not namespace:
        raise ValueError("Namespace cannot be empty.")
    if not component_type:
        raise ValueError("Component type cannot be empty.")
    if not component_id:
        raise ValueError("Component ID cannot be empty.")
    return f"{get_a2a_base_topic(namespace)}/trust/{component_type}/{component_id}"


def get_trust_card_subscription_topic(namespace: str, component_type: Optional[str] = None) -> str:
    """
    Returns subscription pattern for Trust Cards.
    
    Args:
        namespace: SAM namespace
        component_type: Optional - subscribe to specific type, or None for all types
    
    Returns:
        Subscription pattern
    """
    if not namespace:
        raise ValueError("Namespace cannot be empty.")
    
    if component_type:
        return f"{get_a2a_base_topic(namespace)}/trust/{component_type}/*"
    else:
        return f"{get_a2a_base_topic(namespace)}/trust/*/*"


def extract_trust_card_info_from_topic(topic: str) -> tuple[str, str]:
    """
    Extracts component type and ID from trust card topic.
    
    Args:
        topic: Trust card topic
    
    Returns:
        Tuple of (component_type, component_id)
    
    Raises:
        ValueError: If topic format is invalid
    """
    parts = topic.split('/')
    if len(parts) < 6 or parts[1] != 'a2a' or parts[2] != 'v1' or parts[3] != 'trust':
        raise ValueError(f"Invalid trust card topic format: {topic}")
    
    component_type = parts[4]
    component_id = parts[5]
    return component_type, component_id


def subscription_to_regex(subscription: str) -> str:
    """Converts a Solace topic subscription string to a regex pattern."""
    # Escape regex special characters except for Solace wildcards
    pattern = re.escape(subscription)
    # Replace Solace single-level wildcard '*' with regex equivalent '[^/]+'
    pattern = pattern.replace(r"\*", r"[^/]+")
    # Replace Solace multi-level wildcard '>' at the end with regex equivalent '.*'
    if pattern.endswith(r"/>"):
        pattern = pattern[:-1] + r".*"  # Remove escaped '>' and add '.*'
    return pattern


def topic_matches_subscription(topic: str, subscription: str) -> bool:
    """Checks if a topic matches a Solace subscription pattern."""
    regex_pattern = subscription_to_regex(subscription)
    return re.fullmatch(regex_pattern, topic) is not None


# --- JSON-RPC Envelope Helpers ---


def get_request_id(request: A2ARequest) -> str | int:
    """Gets the JSON-RPC request ID from any A2A request object."""
    return request.root.id


def get_request_method(request: A2ARequest) -> str:
    """Gets the JSON-RPC method name from any A2A request object."""
    return request.root.method


def get_message_from_send_request(request: A2ARequest) -> Optional[Message]:
    """
    Safely gets the Message object from a SendMessageRequest or
    SendStreamingMessageRequest. Returns None for other request types.
    """
    if isinstance(request.root, (SendMessageRequest, SendStreamingMessageRequest)):
        return request.root.params.message
    return None


def get_task_id_from_cancel_request(request: A2ARequest) -> Optional[str]:
    """Safely gets the task ID from a CancelTaskRequest."""
    if isinstance(request.root, CancelTaskRequest):
        return request.root.params.id
    return None


def get_response_id(response: JSONRPCResponse) -> Optional[Union[str, int]]:
    """Safely gets the ID from any JSON-RPC response object."""
    if hasattr(response.root, "id"):
        return response.root.id
    return None


def get_response_result(response: JSONRPCResponse) -> Optional[Any]:
    """Safely gets the result object from any successful JSON-RPC response."""
    if hasattr(response.root, "result"):
        return response.root.result
    return None


def get_response_error(response: JSONRPCResponse) -> Optional[JSONRPCError]:
    """Safely gets the error object from any JSON-RPC error response."""
    if hasattr(response.root, "error"):
        return response.root.error
    return None


def get_error_message(error: JSONRPCError) -> str:
    """Safely gets the message string from a JSONRPCError object."""
    return error.message


def get_error_code(error: JSONRPCError) -> int:
    """Safely gets the code from a JSONRPCError object."""
    return error.code


def get_error_data(error: JSONRPCError) -> Optional[Any]:
    """Safely gets the data from a JSONRPCError object."""
    return error.data


def create_success_response(
    result: Any, request_id: Optional[Union[str, int]]
) -> JSONRPCResponse:
    """
    Creates a successful JSON-RPC response object by wrapping the result in the
    appropriate specific success response model based on the result's type.

    Args:
        result: The result payload (e.g., Task, TaskStatusUpdateEvent).
        request_id: The ID of the original request.

    Returns:
        A new `JSONRPCResponse` object.

    Raises:
        TypeError: If the result type is not a supported A2A model.
    """
    specific_response: Any
    if isinstance(result, (TaskStatusUpdateEvent, TaskArtifactUpdateEvent)):
        specific_response = SendStreamingMessageSuccessResponse(
            id=request_id, result=result
        )
    elif isinstance(result, Task):
        # When returning a final task, GetTaskSuccessResponse is a suitable choice.
        specific_response = GetTaskSuccessResponse(id=request_id, result=result)
    else:
        raise TypeError(
            f"Unsupported result type for create_success_response: {type(result).__name__}"
        )

    return JSONRPCResponse(root=specific_response)


def create_internal_error_response(
    message: str,
    request_id: Optional[Union[str, int]],
    data: Optional[Dict[str, Any]] = None,
) -> JSONRPCResponse:
    """
    Creates a JSON-RPC response object for an InternalError.

    Args:
        message: The error message.
        request_id: The ID of the original request.
        data: Optional structured data to include with the error.

    Returns:
        A new `JSONRPCResponse` object containing an `InternalError`.
    """
    error = create_internal_error(message=message, data=data)
    return JSONRPCResponse(id=request_id, error=error)


def create_invalid_request_error_response(
    message: str,
    request_id: Optional[Union[str, int]],
    data: Optional[Any] = None,
) -> JSONRPCResponse:
    """
    Creates a JSON-RPC response object for an InvalidRequestError.

    Args:
        message: The error message.
        request_id: The ID of the original request.
        data: Optional structured data to include with the error.

    Returns:
        A new `JSONRPCResponse` object containing an `InvalidRequestError`.
    """
    error = create_invalid_request_error(message=message, data=data)
    return JSONRPCResponse(id=request_id, error=error)


def create_internal_error(
    message: str,
    data: Optional[Dict[str, Any]] = None,
) -> InternalError:
    """
    Creates an InternalError object.

    Args:
        message: The error message.
        data: Optional structured data to include with the error.

    Returns:
        A new `InternalError` object.
    """
    return InternalError(message=message, data=data)


def create_invalid_request_error(
    message: str, data: Optional[Any] = None
) -> InvalidRequestError:
    """
    Creates an InvalidRequestError object.

    Args:
        message: The error message.
        data: Optional structured data to include with the error.

    Returns:
        A new `InvalidRequestError` object.
    """
    return InvalidRequestError(message=message, data=data)


def create_generic_success_response(
    result: Any, request_id: Optional[Union[str, int]] = None
) -> JSONRPCSuccessResponse:
    """
    Creates a generic successful JSON-RPC response object.
    Note: This is for non-A2A-spec-compliant endpoints that use a similar structure.

    Args:
        result: The result payload for the response.
        request_id: The ID of the original request.

    Returns:
        A new `JSONRPCSuccessResponse` object.
    """
    return JSONRPCSuccessResponse(id=request_id, result=result)


def create_error_response(
    error: JSONRPCError,
    request_id: Optional[Union[str, int]],
) -> JSONRPCResponse:
    """
    Creates a JSON-RPC error response object from a given error model.

    Args:
        error: The JSONRPCError model instance.
        request_id: The ID of the original request.

    Returns:
        A new `JSONRPCResponse` object containing the error.
    """
    return JSONRPCResponse(id=request_id, error=error)


def create_cancel_task_request(task_id: str) -> CancelTaskRequest:
    """
    Creates a CancelTaskRequest object.

    Args:
        task_id: The ID of the task to cancel.

    Returns:
        A new `CancelTaskRequest` object.
    """
    params = TaskIdParams(id=task_id)
    return CancelTaskRequest(id=uuid.uuid4().hex, params=params)


def create_send_message_request(
    message: Message,
    task_id: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> SendMessageRequest:
    """
    Creates a SendMessageRequest object.

    Args:
        message: The A2AMessage object to send.
        task_id: The unique ID for the task.
        metadata: Optional metadata for the send request.

    Returns:
        A new `SendMessageRequest` object.
    """
    send_params = MessageSendParams(message=message, metadata=metadata)
    return SendMessageRequest(id=task_id, params=send_params)


def create_send_streaming_message_request(
    message: Message,
    task_id: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> SendStreamingMessageRequest:
    """
    Creates a SendStreamingMessageRequest object.

    Args:
        message: The A2AMessage object to send.
        task_id: The unique ID for the task.
        metadata: Optional metadata for the send request.

    Returns:
        A new `SendStreamingMessageRequest` object.
    """
    send_params = MessageSendParams(message=message, metadata=metadata)
    return SendStreamingMessageRequest(id=task_id, params=send_params)


def create_send_message_success_response(
    result: Union[Task, Message], request_id: Optional[Union[str, int]]
) -> SendMessageSuccessResponse:
    """
    Creates a SendMessageSuccessResponse object.

    Args:
        result: The result payload (Task or Message).
        request_id: The ID of the original request.

    Returns:
        A new `SendMessageSuccessResponse` object.
    """
    return SendMessageSuccessResponse(id=request_id, result=result)


def create_send_streaming_message_success_response(
    result: Union[Task, Message, TaskStatusUpdateEvent, TaskArtifactUpdateEvent],
    request_id: Optional[Union[str, int]],
) -> SendStreamingMessageSuccessResponse:
    """
    Creates a SendStreamingMessageSuccessResponse object.

    Args:
        result: The result payload.
        request_id: The ID of the original request.

    Returns:
        A new `SendStreamingMessageSuccessResponse` object.
    """
    return SendStreamingMessageSuccessResponse(id=request_id, result=result)


def extract_task_id_from_topic(
    topic: str, subscription_pattern: str, log_identifier: str
) -> Optional[str]:
    """Extracts the task ID from the end of a topic string based on the subscription."""
    base_regex_str = subscription_to_regex(subscription_pattern).replace(r".*", "")
    match = re.match(base_regex_str, topic)
    if match:
        task_id_part = topic[match.end() :]
        task_id = task_id_part.lstrip("/")
        if task_id:
            log.debug(
                "%s Extracted Task ID '%s' from topic '%s'",
                log_identifier,
                task_id,
                topic,
            )
            return task_id
    log.warning(
        "%s Could not extract Task ID from topic '%s' using pattern '%s'",
        log_identifier,
        topic,
        subscription_pattern,
    )
    return None


# --- Client Event Helpers ---


def is_client_event(obj: Any) -> bool:
    """
    Checks if an object is a ClientEvent tuple (Task, UpdateEvent).

    A ClientEvent is a tuple with 2 elements where the first element is a Task
    and the second is either a TaskStatusUpdateEvent, TaskArtifactUpdateEvent, or None.

    Args:
        obj: The object to check.

    Returns:
        True if the object is a ClientEvent tuple, False otherwise.
    """
    if not isinstance(obj, tuple) or len(obj) != 2:
        return False
    
    task, update_event = obj
    
    # First element must be a Task
    if not isinstance(task, Task):
        return False
    
    # Second element must be an update event or None
    if update_event is not None and not isinstance(
        update_event, (TaskStatusUpdateEvent, TaskArtifactUpdateEvent)
    ):
        return False
    
    return True


def is_message_object(obj: Any) -> bool:
    """
    Checks if an object is a Message.

    Args:
        obj: The object to check.

    Returns:
        True if the object is a Message, False otherwise.
    """
    return isinstance(obj, Message)


def unpack_client_event(
    event: tuple,
) -> Tuple[Task, Optional[Union[TaskStatusUpdateEvent, TaskArtifactUpdateEvent]]]:
    """
    Safely unpacks a ClientEvent tuple into its components.

    Args:
        event: A ClientEvent tuple (Task, UpdateEvent).

    Returns:
        A tuple of (Task, Optional[UpdateEvent]) where UpdateEvent can be
        TaskStatusUpdateEvent, TaskArtifactUpdateEvent, or None.

    Raises:
        ValueError: If the event is not a valid ClientEvent tuple.
    """
    if not is_client_event(event):
        raise ValueError(
            f"Expected a ClientEvent tuple, got {type(event).__name__}"
        )
    
    task, update_event = event
    return task, update_event
