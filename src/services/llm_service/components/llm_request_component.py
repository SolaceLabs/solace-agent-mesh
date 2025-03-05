"""LLM Request Component for performing LLM service requests."""

import time
import uuid
from typing import Dict, Any

from solace_ai_connector.components.component_base import ComponentBase
from solace_ai_connector.common.log import log
from solace_ai_connector.common.message import Message
from solace_ai_connector.common.utils import ensure_slash_on_end

info = {
    "class_name": "LLMRequestComponent",
    "description": "Component that performs LLM service requests",
    "config_parameters": [
        {
            "name": "llm_service_topic",
            "required": True,
            "description": "The topic for the LLM service",
        },
        {
            "name": "stream_to_flow",
            "required": False,
            "description": (
                "Name the flow to stream the output to - this must be configured for "
                "llm_mode='stream'. This is mutually exclusive with stream_to_next_component."
            ),
            "default": "",
        },
        {
            "name": "stream_to_next_component",
            "required": False,
            "description": (
                "Whether to stream the output to the next component in the flow. "
                "This is mutually exclusive with stream_to_flow."
            ),
            "default": False,
        },
        {
            "name": "llm_mode",
            "required": False,
            "description": (
                "The mode for streaming results: 'sync' or 'stream'. 'stream' "
                "will just stream the results to the named flow. 'none' will "
                "wait for the full response."
            ),
            "default": "none",
        },
        {
            "name": "stream_batch_size",
            "required": False,
            "description": "The minimum number of words in a single streaming result.",
            "default": 15,
        },
    ],
    "input_schema": {
        "type": "object",
        "properties": {
            "messages": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "role": {
                            "type": "string",
                            "enum": ["system", "user", "assistant"],
                        },
                        "content": {"type": "string"},
                    },
                    "required": ["role", "content"],
                },
            },
            "source_info": {
                "type": "object",
                "properties": {
                    "type": {"type": "string"},
                },
                "required": ["type"],
            },
        },
        "required": ["messages"],
    },
    "output_schema": {
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "The generated response from the model",
            },
            "chunk": {
                "type": "string",
                "description": "The current chunk of the response",
            },
            "response_uuid": {
                "type": "string",
                "description": "The UUID of the response",
            },
            "first_chunk": {
                "type": "boolean",
                "description": "Whether this is the first chunk of the response",
            },
            "last_chunk": {
                "type": "boolean",
                "description": "Whether this is the last chunk of the response",
            },
            "streaming": {
                "type": "boolean",
                "description": "Whether this is a streaming response",
            },
        },
        "required": ["content"],
    },
}


class LLMRequestComponent(ComponentBase):
    """Component that performs LLM service requests."""

    def __init__(self, child_info=None, **kwargs):
        super().__init__(child_info or info, **kwargs)
        self.init()

    def init(self):
        """Initialize the component with configuration parameters."""
        self.llm_service_topic = ensure_slash_on_end(
            self.get_config("llm_service_topic")
        )
        self.stream_to_flow = self.get_config("stream_to_flow")
        self.stream_to_next_component = self.get_config("stream_to_next_component")
        self.llm_mode = self.get_config("llm_mode")
        self.stream_batch_size = self.get_config("stream_batch_size")
        self.max_retries = self.get_config("max_retries", 3)
        self.retry_timeout = self.get_config("retry_timeout", 60)

        if self.stream_to_flow and self.stream_to_next_component:
            raise ValueError(
                "stream_to_flow and stream_to_next_component are mutually exclusive"
            )

        if not self.is_broker_request_response_enabled():
            raise ValueError(
                "LLM service topic is set, but the component does not "
                f"have its broker request/response enabled, {self.__class__.__name__}"
            )

    def invoke(self, message: Message, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Invoke the LLM service request.

        Args:
            message (Message): The input message.
            data (Dict[str, Any]): The input data containing the messages.

        Returns:
            Dict[str, Any]: The response from the LLM service.
        """
        messages = data.get("messages", [])
        source_info = data.get("source_info", {})
        llm_message = self._create_llm_message(message, messages, source_info)
        response_uuid = str(uuid.uuid4())

        try:
            if self.llm_mode == "stream":
                return self._handle_streaming(message, llm_message, response_uuid)
            else:
                return self._handle_sync(llm_message)
        except Exception as e:
            log.error("Error invoking LLM service: %s", e, exc_info=True)
            raise

    def _handle_sync(self, llm_message: Message) -> Dict[str, Any]:
        """
        Handle synchronous LLM service request.

        Args:
            llm_message (Message): The message to send to the LLM service.

        Returns:
            Dict[str, Any]: The response from the LLM service.
        """
        response = self.do_broker_request_response(llm_message)
        return response.get_payload()

    def _handle_streaming(
        self, input_message: Message, llm_message: Message, response_uuid: str
    ) -> Dict[str, Any]:
        """
        Handle streaming LLM service request.

        Args:
            input_message (Message): The original input message.
            llm_message (Message): The message to send to the LLM service.
            response_uuid (str): The UUID for the response.

        Returns:
            Dict[str, Any]: The final response from the LLM service.
        """
        aggregate_result = ""
        current_batch = ""
        first_chunk = True
        retry_count = 0
        last_activity_time = time.time()
        sent_content_length = 0

        try:
            while True:
                try:
                    # Start or continue the streaming request
                    broker_responses = self.do_broker_request_response(
                        llm_message,
                        stream=True,
                        streaming_complete_expression="input.payload:last_chunk"
                    )

                    # Process all responses from request
                    for response_message, last_message in broker_responses:
                        # Update last activity time
                        last_activity_time = time.time()

                        payload = response_message.get_payload()
                        content = payload.get("chunk", "")

                        # Clean up content if this is a continuation (not the first chunk)
                        if retry_count > 0 and not first_chunk:
                            # Address formatting in response
                            content = content.lstrip()

                        aggregate_result += content
                        current_batch += content

                        if len(current_batch.split()) >= self.stream_batch_size or last_message:
                            # Check if we have new content to send
                            if len(aggregate_result) > sent_content_length:
                                new_content = aggregate_result[sent_content_length:]
                                self._send_streaming_chunk(
                                    input_message,
                                    new_content,
                                    aggregate_result,
                                    response_uuid,
                                    first_chunk,
                                    last_message,
                                )
                                sent_content_length = len(aggregate_result)
                                current_batch = ""
                                first_chunk = False

                        if last_message:
                            return {
                                "content": aggregate_result,
                                "response_uuid": response_uuid,
                                "streaming": True,
                                "last_chunk": True,
                            }

                    if retry_count < self.max_retries:
                        retry_count += 1
                        log.info(f"Continuing LLM generation (attempt {retry_count}/{self.max_retries})")

                        # Create a continuation request
                        llm_message = self._create_continuation_request(
                            input_message,
                            aggregate_result,
                            llm_message.get_payload()['messages']
                        )
                    else:
                        # Too many retries
                        log.warning(f"Maximum retries ({self.max_retries}) reached for LLM request")
                        break

                except TimeoutError:
                    # Check if we should retry
                    now = time.time()
                    if retry_count < self.max_retries and (now - last_activity_time) < self.retry_timeout:
                        retry_count += 1
                        log.info(f"Retrying LLM request after timeout (attempt {retry_count}/{self.max_retries})")

                        # Create a continuation request
                        llm_message = self._create_continuation_request(
                            input_message,
                            aggregate_result,
                            llm_message.get_payload()['messages']
                        )
                    else:
                        # Too many retries
                        log.warning(f"Maximum retries ({self.max_retries}) reached for LLM request")
                        break

        except Exception as e:
            log.error("Error handling streaming: %s", e, exc_info=True)
            raise e

        return {
            "content": aggregate_result,
            "response_uuid": response_uuid,
            "streaming": True,
            "last_chunk": True
        }

    def _create_continuation_request(self, original_message: Message, current_content: str, original_messages: list) -> Message:
        """
        Create a continuation request when a timeout occurs.

        Args:
            original_message (Message): The original input message.
            current_content (str): The content generated so far.
            original_messages (list): The original messages sent to the LLM.

        Returns:
            Message: A new message configured to continue the generation
        """
        messages = original_messages.copy()

        messages.append({
            'role': 'assistant',
            'content': current_content
        })

        # Add system instruction to continue
        messages.append({
            'role': 'system',
            'content': (
                "You must continue exactly from where the previous message ended, without repeating any content. "
                "Start your response as if you're mid-sentence, picking up directly from the last word/character of the previous message. "
                "Do not add any line breaks, spaces, or other characters at the beginning of your response. "
                "If you were generating a CSV or other structured data format, maintain the exact same structure without adding extra newlines. "
                "For CSV data, continue with the exact column structure from the previous response."
            )
        })

        # Add user instruction to continue
        messages.append({
            'role': 'user',
            'content': (
                "Continue the previous response, starting exactly from its last word/character. "
                "Do not include any line breaks or spaces at the beginning. "
                "Do not summarize or repeat any previous content. "
                "If you were generating CSV data or other structured format, maintain the exact same structure."
            )
        })

        # Create a new LLM message
        source_info = original_message.get_payload().get("source_info", {})
        return self._create_llm_message(original_message, messages, source_info)

    def _create_llm_message(self, message: Message, messages: list, source_info: dict) -> Message:
        """
        Create a message for the LLM service request.

        Args:
            message (Message): The original input message.
            messages (list): The list of messages to send to the LLM service.
            source_info (dict): Information about the caller to help montoring LLM requests.

        Returns:
            Message: The created message for the LLM service.
        """
        user_properties = message.get_user_properties().copy()
        stimulus_uuid = user_properties.get("stimulus_uuid", str(uuid.uuid4()))
        session_id = user_properties.get("session_id", "x")
        originator_id = user_properties.get("originator_id", "x")
        user_properties["llm_request_source_info"] = source_info

        topic = f"{self.llm_service_topic}{stimulus_uuid}/{session_id}/{originator_id}"

        return Message(
            topic=topic,
            payload={"messages": messages, "stream": True},
            user_properties=user_properties,
        )

    def _send_streaming_chunk(
        self,
        input_message: Message,
        chunk: str,
        aggregate_result: str,
        response_uuid: str,
        first_chunk: bool,
        last_chunk: bool,
    ):
        """
        Send a streaming chunk to the specified flow or next component.

        Args:
            input_message (Message): The original input message.
            chunk (str): The current chunk of the response.
            aggregate_result (str): The aggregated result so far.
            response_uuid (str): The UUID of the response.
            first_chunk (bool): Whether this is the first chunk.
            last_chunk (bool): Whether this is the last chunk.
        """
        payload = {
            "chunk": chunk,
            "content": aggregate_result,
            "response_uuid": response_uuid,
            "first_chunk": first_chunk,
            "last_chunk": last_chunk,
            "streaming": True,
        }
        message = Message(
            payload=payload,
            user_properties=input_message.get_user_properties(),
        )

        if self.stream_to_flow:
            self.send_to_flow(self.stream_to_flow, message)
        elif self.stream_to_next_component:
            self.send_message(message)
