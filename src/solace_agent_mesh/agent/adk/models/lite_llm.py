# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

import base64
import hashlib
import json
import logging
from typing import Any
from typing import AsyncGenerator
from typing import cast
from typing import Dict
from typing import Generator
from typing import Iterable
from typing import List
from typing import Literal
from typing import Optional
from typing import Tuple
from typing import Union

from google.genai import types
from litellm import acompletion
from litellm import ChatCompletionAssistantMessage
from litellm import ChatCompletionAssistantToolCall
from litellm import ChatCompletionDeveloperMessage
from litellm import ChatCompletionImageUrlObject
from litellm import ChatCompletionMessageToolCall
from litellm import ChatCompletionTextObject
from litellm import ChatCompletionToolMessage
from litellm import ChatCompletionUserMessage
from litellm import ChatCompletionVideoUrlObject
from litellm import completion
from litellm import CustomStreamWrapper
from litellm import Function
from litellm import Message
from litellm import ModelResponse
from litellm import OpenAIMessageContent
from pydantic import BaseModel
from pydantic import Field
from typing_extensions import override

from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from .oauth2_token_manager import OAuth2ClientCredentialsTokenManager

logger = logging.getLogger("google_adk." + __name__)

_NEW_LINE = "\n"
_EXCLUDED_PART_FIELD = {"inline_data": {"data"}}


class FunctionChunk(BaseModel):
    id: Optional[str]
    name: Optional[str]
    args: Optional[str]
    index: Optional[int] = 0


class TextChunk(BaseModel):
    text: str


class UsageMetadataChunk(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class LiteLLMClient:
    """Provides acompletion method (for better testability)."""

    async def acompletion(
        self, model, messages, tools, **kwargs
    ) -> Union[ModelResponse, CustomStreamWrapper]:
        """Asynchronously calls acompletion.

        Args:
          model: The model name.
          messages: The messages to send to the model.
          tools: The tools to use for the model.
          **kwargs: Additional arguments to pass to acompletion.

        Returns:
          The model response as a message.
        """

        return await acompletion(
            model=model,
            messages=messages,
            tools=tools,
            **kwargs,
        )

    def completion(
        self, model, messages, tools, stream=False, **kwargs
    ) -> Union[ModelResponse, CustomStreamWrapper]:
        """Synchronously calls completion. This is used for streaming only.

        Args:
          model: The model to use.
          messages: The messages to send.
          tools: The tools to use for the model.
          stream: Whether to stream the response.
          **kwargs: Additional arguments to pass to completion.

        Returns:
          The response from the model.
        """

        return completion(
            model=model,
            messages=messages,
            tools=tools,
            stream=stream,
            **kwargs,
        )


def _safe_json_serialize(obj) -> str:
    """Convert any Python object to a JSON-serializable type or string.

    Args:
      obj: The object to serialize.

    Returns:
      The JSON-serialized object string or string.
    """

    try:
        return json.dumps(obj, ensure_ascii=False)
    except (TypeError, OverflowError):
        return str(obj)


def _truncate_tool_call_id(tool_call_id: str, max_length: int = 40) -> str:
    """Truncates tool call ID to meet OpenAI's maximum length requirement.
    
    OpenAI requires tool_call_id to be at most 40 characters. If the ID exceeds
    this limit, we create a deterministic hash-based truncation to ensure:
    1. The ID stays within the limit
    2. The same input always produces the same output (deterministic)
    3. Collisions are extremely unlikely
    
    Args:
        tool_call_id: The original tool call ID
        max_length: Maximum allowed length (default: 40 for OpenAI)
    
    Returns:
        Truncated tool call ID that meets the length requirement
    """
    if len(tool_call_id) <= max_length:
        return tool_call_id
    
    # Use first part of ID + hash of full ID to maintain uniqueness
    # Format: prefix_hash where prefix is from original and hash ensures uniqueness
    prefix_length = max_length - 33  # Reserve 33 chars for hash (32) + underscore (1)
    if prefix_length < 1:
        prefix_length = 1
    
    prefix = tool_call_id[:prefix_length]
    # Use SHA256 and take first 32 hex characters for uniqueness
    hash_suffix = hashlib.sha256(tool_call_id.encode()).hexdigest()[:32]
    
    return f"{prefix}_{hash_suffix}"


def _content_to_message_param(
    content: types.Content,
) -> Union[Message, list[Message]]:
    """Converts a types.Content to a litellm Message or list of Messages.

    Handles multipart function responses by returning a list of
    ChatCompletionToolMessage objects if multiple function_response parts exist.

    Args:
      content: The content to convert.

    Returns:
      A litellm Message, a list of litellm Messages.
    """

    tool_messages = []
    for part in content.parts:
        if part.function_response:
            tool_messages.append(
                ChatCompletionToolMessage(
                    role="tool",
                    tool_call_id=_truncate_tool_call_id(part.function_response.id),
                    content=_safe_json_serialize(part.function_response.response),
                )
            )
    if tool_messages:
        return tool_messages if len(tool_messages) > 1 else tool_messages[0]

    role = _to_litellm_role(content.role)
    message_content = _get_content(content.parts) or None

    if role == "user":
        return ChatCompletionUserMessage(role="user", content=message_content)
    else:  # assistant/model
        tool_calls = []
        content_present = False
        for part in content.parts:
            if part.function_call:
                tool_calls.append(
                    ChatCompletionAssistantToolCall(
                        type="function",
                        id=_truncate_tool_call_id(part.function_call.id),
                        function=Function(
                            name=part.function_call.name,
                            arguments=_safe_json_serialize(part.function_call.args),
                        ),
                    )
                )
            elif part.text or part.inline_data:
                content_present = True

        final_content = message_content if content_present else None
        if final_content and isinstance(final_content, list):
            # when the content is a single text object, we can use it directly.
            # this is needed for ollama_chat provider which fails if content is a list
            final_content = (
                final_content[0].get("text", "")
                if final_content[0].get("type", None) == "text"
                else final_content
            )

        return ChatCompletionAssistantMessage(
            role=role,
            content=final_content,
            tool_calls=tool_calls or None,
        )


def _get_content(
    parts: Iterable[types.Part],
) -> Union[OpenAIMessageContent, str]:
    """Converts a list of parts to litellm content.

    Args:
      parts: The parts to convert.

    Returns:
      The litellm content.
    """

    content_objects = []
    for part in parts:
        if part.text:
            if len(parts) == 1:
                return part.text
            content_objects.append(
                ChatCompletionTextObject(
                    type="text",
                    text=part.text,
                )
            )
        elif part.inline_data and part.inline_data.data and part.inline_data.mime_type:
            base64_string = base64.b64encode(part.inline_data.data).decode("utf-8")
            data_uri = f"data:{part.inline_data.mime_type};base64,{base64_string}"

            if part.inline_data.mime_type.startswith("image"):
                content_objects.append(
                    ChatCompletionImageUrlObject(
                        type="image_url",
                        image_url=data_uri,
                    )
                )
            elif part.inline_data.mime_type.startswith("video"):
                content_objects.append(
                    ChatCompletionVideoUrlObject(
                        type="video_url",
                        video_url=data_uri,
                    )
                )
            else:
                raise ValueError("LiteLlm(BaseLlm) does not support this content part.")

    return content_objects


def _to_litellm_role(role: Optional[str]) -> Literal["user", "assistant"]:
    """Converts a types.Content role to a litellm role.

    Args:
      role: The types.Content role.

    Returns:
      The litellm role.
    """

    if role in ["model", "assistant"]:
        return "assistant"
    return "user"


TYPE_LABELS = {
    "STRING": "string",
    "NUMBER": "number",
    "BOOLEAN": "boolean",
    "OBJECT": "object",
    "ARRAY": "array",
    "INTEGER": "integer",
}


def _schema_to_dict(schema: types.Schema) -> dict:
    """Recursively converts a types.Schema to a dictionary.

    Args:
      schema: The schema to convert.

    Returns:
      The dictionary representation of the schema.
    """

    schema_dict = schema.model_dump(exclude_none=True)
    if "type" in schema_dict:
        schema_dict["type"] = schema_dict["type"].lower()
    if "items" in schema_dict:
        if isinstance(schema_dict["items"], dict):
            schema_dict["items"] = _schema_to_dict(
                types.Schema.model_validate(schema_dict["items"])
            )
        elif isinstance(schema_dict["items"]["type"], types.Type):
            schema_dict["items"]["type"] = TYPE_LABELS[
                schema_dict["items"]["type"].value
            ]
    if "properties" in schema_dict:
        properties = {}
        for key, value in schema_dict["properties"].items():
            if isinstance(value, types.Schema):
                properties[key] = _schema_to_dict(value)
            else:
                properties[key] = value
                if "type" in properties[key]:
                    properties[key]["type"] = properties[key]["type"].lower()
        schema_dict["properties"] = properties
    return schema_dict


def _function_declaration_to_tool_param(
    function_declaration: types.FunctionDeclaration,
) -> dict:
    """Converts a types.FunctionDeclaration to a openapi spec dictionary.

    Args:
      function_declaration: The function declaration to convert.

    Returns:
      The openapi spec dictionary representation of the function declaration.
    """

    assert function_declaration.name

    properties = {}
    if function_declaration.parameters and function_declaration.parameters.properties:
        for key, value in function_declaration.parameters.properties.items():
            properties[key] = _schema_to_dict(value)

    return {
        "type": "function",
        "function": {
            "name": function_declaration.name,
            "description": function_declaration.description or "",
            "parameters": {
                "type": "object",
                "properties": properties,
            },
        },
    }


def _model_response_to_chunk(
    response: ModelResponse,
) -> Generator[
    Tuple[
        Optional[Union[TextChunk, FunctionChunk, UsageMetadataChunk]],
        Optional[str],
    ],
    None,
    None,
]:
    """Converts a litellm message to text, function or usage metadata chunk.

    Args:
      response: The response from the model.

    Yields:
      A tuple of text or function or usage metadata chunk and finish reason.
    """

    message = None
    if response.get("choices", None):
        message = response["choices"][0].get("message", None)
        finish_reason = response["choices"][0].get("finish_reason", None)
        # check streaming delta
        if message is None and response["choices"][0].get("delta", None):
            message = response["choices"][0]["delta"]

        if message.get("content", None):
            yield TextChunk(text=message.get("content")), finish_reason

        if message.get("tool_calls", None):
            for tool_call in message.get("tool_calls"):
                if tool_call.type == "function":
                    yield FunctionChunk(
                        id=tool_call.id,
                        name=tool_call.function.name,
                        args=tool_call.function.arguments,
                        index=tool_call.index,
                    ), finish_reason

        if finish_reason and not (
            message.get("content", None) or message.get("tool_calls", None)
        ):
            yield None, finish_reason

    if not message:
        yield None, None

    # Ideally usage would be expected with the last ModelResponseStream with a
    # finish_reason set. But this is not the case we are observing from litellm.
    # So we are sending it as a separate chunk to be set on the llm_response.
    if response.get("usage", None):
        yield UsageMetadataChunk(
            prompt_tokens=response["usage"].get("prompt_tokens", 0),
            completion_tokens=response["usage"].get("completion_tokens", 0),
            total_tokens=response["usage"].get("total_tokens", 0),
        ), None


def _model_response_to_generate_content_response(
    response: ModelResponse,
) -> LlmResponse:
    """Converts a litellm response to LlmResponse. Also adds usage metadata.

    Args:
      response: The model response.

    Returns:
      The LlmResponse.
    """

    message = None
    if response.get("choices", None):
        message = response["choices"][0].get("message", None)

    if not message:
        raise ValueError("No message in response")

    llm_response = _message_to_generate_content_response(message)
    if response.get("usage", None):
        llm_response.usage_metadata = types.GenerateContentResponseUsageMetadata(
            prompt_token_count=response["usage"].get("prompt_tokens", 0),
            candidates_token_count=response["usage"].get("completion_tokens", 0),
            total_token_count=response["usage"].get("total_tokens", 0),
        )
    return llm_response


def _message_to_generate_content_response(
    message: Message, is_partial: bool = False
) -> LlmResponse:
    """Converts a litellm message to LlmResponse.

    Args:
      message: The message to convert.
      is_partial: Whether the message is partial.

    Returns:
      The LlmResponse.
    """

    parts = []
    if message.get("content", None):
        parts.append(types.Part.from_text(text=message.get("content")))

    if message.get("tool_calls", None):
        for tool_call in message.get("tool_calls"):
            if tool_call.type == "function":
                try:
                    part = types.Part.from_function_call(
                        name=tool_call.function.name,
                        args=json.loads(tool_call.function.arguments or "{}"),
                    )
                    part.function_call.id = _truncate_tool_call_id(tool_call.id)
                    parts.append(part)
                except json.JSONDecodeError as e:
                    logger.error(
                        "Failed to decode function call arguments: %s. Arguments: %s",
                        e,
                        tool_call.function.arguments,
                    )

    return LlmResponse(
        content=types.Content(role="model", parts=parts), partial=is_partial
    )


def _get_completion_inputs(
    llm_request: LlmRequest,
    cache_strategy: str = "5m",
) -> Tuple[
    List[Message],
    Optional[List[Dict]],
    Optional[types.SchemaUnion],
    Optional[Dict],
]:
    """Converts an LlmRequest to litellm inputs and extracts generation params.

    Args:
      llm_request: The LlmRequest to convert.
      cache_strategy: Cache strategy to apply ("none", "5m", "1h").

    Returns:
      The litellm inputs (message list, tool dictionary and response format).
    """
    messages: List[Message] = []
    for content in llm_request.contents or []:
        message_param_or_list = _content_to_message_param(content)
        if isinstance(message_param_or_list, list):
            messages.extend(message_param_or_list)
        elif message_param_or_list:  # Ensure it's not None before appending
            messages.append(message_param_or_list)

    if llm_request.config and llm_request.config.system_instruction:
        # Build system instruction content with optional cache control
        system_content = {
            "type": "text",
            "text": llm_request.config.system_instruction,
        }

        # Add cache control based on strategy
        # LiteLLM translates this to provider-specific format (Anthropic, OpenAI, Bedrock, Deepseek)
        if cache_strategy == "5m":
            # 5-minute ephemeral cache (Anthropic default)
            system_content["cache_control"] = {"type": "ephemeral"}
        elif cache_strategy == "1h":
            # 1-hour extended cache (Anthropic extended)
            system_content["cache_control"] = {"type": "ephemeral", "ttl": "1h"}
        # For "none", no cache_control is added

        messages.insert(
            0,
            ChatCompletionDeveloperMessage(
                role="developer",
                content=[system_content],
            ),
        )

    # 2. Convert tool declarations with caching support
    tools: Optional[List[Dict]] = None
    if (
        llm_request.config
        and llm_request.config.tools
        and llm_request.config.tools[0].function_declarations
    ):
        tools = [
            _function_declaration_to_tool_param(tool)
            for tool in llm_request.config.tools[0].function_declarations
        ]

        # Enable tool caching via LiteLLM's generic interface
        # LiteLLM handles provider-specific translation (Anthropic, OpenAI, Bedrock, Deepseek)
        # Tools are stable because peer agents are alphabetically sorted (component.py)
        if tools and cache_strategy != "none":
            # Add cache_control to the LAST tool (required by caching providers)
            if cache_strategy == "5m":
                tools[-1]["cache_control"] = {"type": "ephemeral"}
            elif cache_strategy == "1h":
                tools[-1]["cache_control"] = {"type": "ephemeral", "ttl": "1h"}

    # 3. Handle response format
    response_format: Optional[types.SchemaUnion] = None
    if llm_request.config and llm_request.config.response_schema:
        response_format = llm_request.config.response_schema

    # 4. Extract generation parameters
    generation_params: Optional[Dict] = None
    if llm_request.config:
        config_dict = llm_request.config.model_dump(exclude_none=True)
        # Generate LiteLlm parameters here,
        # Following https://docs.litellm.ai/docs/completion/input.
        generation_params = {}
        param_mapping = {
            "max_output_tokens": "max_completion_tokens",
            "stop_sequences": "stop",
        }
        for key in (
            "temperature",
            "max_output_tokens",
            "top_p",
            "top_k",
            "stop_sequences",
            "presence_penalty",
            "frequency_penalty",
        ):
            if key in config_dict:
                mapped_key = param_mapping.get(key, key)
                generation_params[mapped_key] = config_dict[key]

            if not generation_params:
                generation_params = None

    return messages, tools, response_format, generation_params


def _build_function_declaration_log(
    func_decl: types.FunctionDeclaration,
) -> str:
    """Builds a function declaration log.

    Args:
      func_decl: The function declaration to convert.

    Returns:
      The function declaration log.
    """

    param_str = "{}"
    if func_decl.parameters and func_decl.parameters.properties:
        param_str = str(
            {
                k: v.model_dump(exclude_none=True)
                for k, v in func_decl.parameters.properties.items()
            }
        )
    return_str = "None"
    if func_decl.response:
        return_str = str(func_decl.response.model_dump(exclude_none=True))
    return f"{func_decl.name}: {param_str} -> {return_str}"


def _build_request_log(req: LlmRequest) -> str:
    """Builds a request log.

    Args:
      req: The request to convert.

    Returns:
      The request log.
    """

    function_decls: list[types.FunctionDeclaration] = cast(
        list[types.FunctionDeclaration],
        req.config.tools[0].function_declarations if req.config and req.config.tools else [],
    )
    function_logs = (
        [_build_function_declaration_log(func_decl) for func_decl in function_decls]
        if function_decls
        else []
    )
    contents_logs = [
        content.model_dump_json(
            exclude_none=True,
            exclude={
                "parts": {i: _EXCLUDED_PART_FIELD for i in range(len(content.parts))}
            },
        )
        for content in req.contents
    ]

    return f"""
LLM Request:
-----------------------------------------------------------
System Instruction:
{req.config.system_instruction if req.config else None}
-----------------------------------------------------------
Contents:
{_NEW_LINE.join(contents_logs)}
-----------------------------------------------------------
Functions:
{_NEW_LINE.join(function_logs)}
-----------------------------------------------------------
"""


class LiteLlm(BaseLlm):
    """Wrapper around litellm.

    This wrapper can be used with any of the models supported by litellm. The
    environment variable(s) needed for authenticating with the model endpoint must
    be set prior to instantiating this class.

    Example usage:
    ```
    os.environ["VERTEXAI_PROJECT"] = "your-gcp-project-id"
    os.environ["VERTEXAI_LOCATION"] = "your-gcp-location"

    agent = Agent(
        model=LiteLlm(model="vertex_ai/claude-3-7-sonnet@20250219"),
        ...
    )
    ```

    Attributes:
      model: The name of the LiteLlm model.
      llm_client: The LLM client to use for the model.
    """

    llm_client: LiteLLMClient = Field(default_factory=LiteLLMClient)
    """The LLM client to use for the model."""

    _additional_args: Dict[str, Any] = None
    _oauth_token_manager: Optional[OAuth2ClientCredentialsTokenManager] = None
    _cache_strategy: str = "5m"  # Default to 5-minute ephemeral cache

    def __init__(self, model: str, cache_strategy: str = "5m", **kwargs):
        """Initializes the LiteLlm class.

        Args:
          model: The name of the LiteLlm model.
          cache_strategy: Cache strategy to use. Options: "none", "5m" (ephemeral), "1h" (extended).
                         Defaults to "5m" for backward compatibility.
          **kwargs: Additional arguments to pass to the litellm completion api.
                   Can include OAuth configuration parameters.
        """
        super().__init__(model=model, **kwargs)
        self._additional_args = kwargs.copy()

        # Remove handlers added by LiteLLM as they produce duplicate and misformatted logs.
        # Logging is an application concern and libraries should not set handlers/formatters.
        for logger_name in ["LiteLLM", "LiteLLM Proxy", "LiteLLM Router", "litellm"]:
            logging.getLogger(logger_name).handlers.clear()

        # Validate and store cache strategy
        valid_strategies = ["none", "5m", "1h"]
        if cache_strategy not in valid_strategies:
            logger.warning(
                "Invalid cache_strategy '%s'. Valid options are: %s. Defaulting to '5m'.",
                cache_strategy,
                valid_strategies,
            )
            cache_strategy = "5m"
        self._cache_strategy = cache_strategy
        logger.info("LiteLlm initialized with cache strategy: %s", self._cache_strategy)

        # Extract OAuth configuration if present
        oauth_config = self._extract_oauth_config(self._additional_args)
        if oauth_config:
            self._oauth_token_manager = OAuth2ClientCredentialsTokenManager(**oauth_config)
            logger.info("OAuth2 token manager initialized for model: %s", model)
        else:
            self._oauth_token_manager = None

        # preventing generation call with llm_client
        # and overriding messages, tools and stream which are managed internally
        self._additional_args.pop("llm_client", None)
        self._additional_args.pop("messages", None)
        self._additional_args.pop("tools", None)
        # public api called from runner determines to stream or not
        self._additional_args.pop("stream", None)

    def _extract_oauth_config(self, kwargs: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract OAuth configuration from kwargs.

        Args:
            kwargs: Keyword arguments that may contain OAuth parameters

        Returns:
            OAuth configuration dictionary or None if no OAuth config found
        """
        oauth_params = [
            "oauth_token_url",
            "oauth_client_id",
            "oauth_client_secret",
            "oauth_scope",
            "oauth_ca_cert",
            "oauth_token_refresh_buffer_seconds",
            "oauth_max_retries"
        ]

        oauth_config = {}
        for param in oauth_params:
            if param in kwargs:
                # Map parameter names to OAuth2ClientCredentialsTokenManager constructor
                if param == "oauth_ca_cert":
                    oauth_config["ca_cert_path"] = kwargs.pop(param)
                elif param == "oauth_token_refresh_buffer_seconds":
                    oauth_config["refresh_buffer_seconds"] = kwargs.pop(param)
                elif param == "oauth_max_retries":
                    oauth_config["max_retries"] = kwargs.pop(param)
                else:
                    # Remove oauth_ prefix for the token manager
                    key = param.replace("oauth_", "")
                    oauth_config[key] = kwargs.pop(param)

        # Return config only if we have the required parameters
        if "token_url" in oauth_config and "client_id" in oauth_config and "client_secret" in oauth_config:
            return oauth_config
        elif oauth_config:
            logger.warning("Incomplete OAuth configuration found, missing required parameters")

        return None

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        """Generates content asynchronously.

        Args:
          llm_request: LlmRequest, the request to send to the LiteLlm model.
          stream: bool = False, whether to do streaming call.

        Yields:
          LlmResponse: The model response.
        """

        if not llm_request.contents or llm_request.contents[-1].role not in [
            "user",
            "tool",
        ]:
            self._maybe_append_user_content(llm_request)
        logger.debug(_build_request_log(llm_request))

        messages, tools, response_format, generation_params = _get_completion_inputs(
            llm_request, self._cache_strategy
        )
        completion_args = {
            "model": self.model,
            "messages": messages,
            "tools": tools,
            "response_format": response_format,
            "stream_options": {"include_usage": True},
        }
        completion_args.update(self._additional_args)

        # Inject OAuth token if OAuth is configured
        if self._oauth_token_manager:
            try:
                access_token = await self._oauth_token_manager.get_token()
                # Inject Bearer token via extra_headers
                extra_headers = completion_args.get("extra_headers", {})
                extra_headers["Authorization"] = f"Bearer {access_token}"
                completion_args["extra_headers"] = extra_headers
                logger.debug("OAuth token injected into request headers")
            except Exception as e:
                logger.error("Failed to get OAuth token: %s", str(e))
                # Check if we have a fallback API key
                if "api_key" in completion_args:
                    logger.info("Falling back to API key authentication")
                else:
                    logger.error("No fallback authentication available")
                    raise

        if generation_params:
            completion_args.update(generation_params)

        if not tools and completion_args.get("parallel_tool_calls", False):
            # Setting parallel_tool_calls without any tools causes an error from Anthropic.
            completion_args.pop("parallel_tool_calls")

        # Remove stream_options when not streaming (Azure doesn't support it)
        if not stream:
            completion_args.pop("stream_options", None)

        if stream:
            text = ""
            function_calls = {}  # index -> {name, args, id}
            completion_args["stream"] = True
            aggregated_llm_response = None
            aggregated_llm_response_with_tool_call = None
            usage_metadata = None
            fallback_index = 0
            async for part in await self.llm_client.acompletion(**completion_args):
                for chunk, finish_reason in _model_response_to_chunk(part):
                    if isinstance(chunk, FunctionChunk):
                        index = chunk.index or fallback_index
                        if index not in function_calls:
                            function_calls[index] = {"name": "", "args": "", "id": None}

                        if chunk.name:
                            function_calls[index]["name"] += chunk.name
                        if chunk.args:
                            function_calls[index]["args"] += chunk.args

                            # check if args is completed (workaround for improper chunk
                            # indexing)
                            try:
                                json.loads(function_calls[index]["args"])
                                fallback_index += 1
                            except json.JSONDecodeError:
                                pass

                        function_calls[index]["id"] = (
                            chunk.id or function_calls[index]["id"] or str(index)
                        )
                    elif isinstance(chunk, TextChunk):
                        text += chunk.text
                        yield _message_to_generate_content_response(
                            ChatCompletionAssistantMessage(
                                role="assistant",
                                content=chunk.text,
                            ),
                            is_partial=True,
                        )
                    elif isinstance(chunk, UsageMetadataChunk):
                        usage_metadata = types.GenerateContentResponseUsageMetadata(
                            prompt_token_count=chunk.prompt_tokens,
                            candidates_token_count=chunk.completion_tokens,
                            total_token_count=chunk.total_tokens,
                        )

                    if (
                        finish_reason == "tool_calls" or finish_reason == "stop"
                    ) and function_calls:
                        tool_calls = []
                        for index, func_data in function_calls.items():
                            if func_data["id"]:
                                tool_calls.append(
                                    ChatCompletionMessageToolCall(
                                        type="function",
                                        id=_truncate_tool_call_id(func_data["id"]),
                                        function=Function(
                                            name=func_data["name"],
                                            arguments=func_data["args"],
                                            index=index,
                                        ),
                                    )
                                )
                        aggregated_llm_response_with_tool_call = (
                            _message_to_generate_content_response(
                                ChatCompletionAssistantMessage(
                                    role="assistant",
                                    content=text or "",
                                    tool_calls=tool_calls,
                                )
                            )
                        )
                        function_calls.clear()
                        text = ""
                    elif finish_reason == "length":
                        # The stream was interrupted due to token limit.
                        # Create a final response indicating interruption, including any
                        # buffered text AND any buffered tool calls.
                        tool_calls = []
                        for index, func_data in function_calls.items():
                            if func_data["id"]:
                                tool_calls.append(
                                    ChatCompletionMessageToolCall(
                                        type="function",
                                        id=_truncate_tool_call_id(func_data["id"]),
                                        function=Function(
                                            name=func_data["name"],
                                            arguments=func_data["args"],
                                            index=index,
                                        ),
                                    )
                                )

                        aggregated_llm_response = _message_to_generate_content_response(
                            ChatCompletionAssistantMessage(
                                role="assistant",
                                content=text or None,
                                tool_calls=tool_calls or None,
                            )
                        )
                        aggregated_llm_response.interrupted = True

                        # Yield the interrupted response immediately and stop processing this stream.
                        # This ensures the partial text and tool calls are preserved.
                        if usage_metadata:
                            aggregated_llm_response.usage_metadata = usage_metadata
                        yield aggregated_llm_response
                        return
                    elif finish_reason == "MALFORMED_FUNCTION_CALL":
                        # Create an error response that will allow the LLM to continue
                        aggregated_llm_response = _message_to_generate_content_response(
                            ChatCompletionAssistantMessage(
                                role="assistant",
                                content="I attempted to call a function that doesn't exist or with invalid parameters. Let me try a different approach or provide a direct response instead.",
                            ),
                            is_partial=True,
                        )
                        text = ""
                    elif finish_reason == "stop" and text:
                        aggregated_llm_response = _message_to_generate_content_response(
                            ChatCompletionAssistantMessage(
                                role="assistant", content=text
                            )
                        )
                        text = ""

            # waiting until streaming ends to yield the llm_response as litellm tends
            # to send chunk that contains usage_metadata after the chunk with
            # finish_reason set to tool_calls or stop.
            if aggregated_llm_response:
                if usage_metadata:
                    aggregated_llm_response.usage_metadata = usage_metadata
                    usage_metadata = None
                yield aggregated_llm_response

            if aggregated_llm_response_with_tool_call:
                if usage_metadata:
                    aggregated_llm_response_with_tool_call.usage_metadata = (
                        usage_metadata
                    )
                yield aggregated_llm_response_with_tool_call

        else:
            response = await self.llm_client.acompletion(**completion_args)
            yield _model_response_to_generate_content_response(response)

    @staticmethod
    @override
    def supported_models() -> list[str]:
        """Provides the list of supported models.

        LiteLlm supports all models supported by litellm. We do not keep track of
        these models here. So we return an empty list.

        Returns:
          A list of supported models.
        """

        return []
