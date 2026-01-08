"""
Basic Test LLM Server mimicking an OpenAI-compatible API endpoint.
Provides configurable static responses and captures incoming requests for verification.
"""

from fastapi import FastAPI, Request, HTTPException
from starlette.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Union, Literal, AsyncGenerator
import uvicorn
import json
import threading
import time
import asyncio
import logging
import os
import re
import base64


class ToolCallFunction(BaseModel):
    name: str
    arguments: str


class ToolCall(BaseModel):
    id: str
    type: Literal["function"] = "function"
    function: ToolCallFunction


class Message(BaseModel):
    role: str
    content: Optional[Union[str, List[Dict[str, Any]]]] = None
    tool_calls: Optional[List[ToolCall]] = None
    tool_call_id: Optional[str] = None


class ToolCallDeltaFunction(BaseModel):
    name: Optional[str] = None
    arguments: Optional[str] = None


class ToolCallDelta(BaseModel):
    index: int
    id: Optional[str] = None
    type: Optional[Literal["function"]] = None
    function: Optional[ToolCallDeltaFunction] = None


class DeltaMessage(BaseModel):
    role: Optional[str] = None
    content: Optional[str] = None
    tool_calls: Optional[List[ToolCallDelta]] = None


class StreamingChoice(BaseModel):
    index: int = 0
    delta: DeltaMessage
    finish_reason: Optional[str] = None


class ChatCompletionChunk(BaseModel):
    id: str = Field(default_factory=lambda: f"chatcmpl-test-stream-{int(time.time())}")
    object: str = "chat.completion.chunk"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: List[StreamingChoice]


class Choice(BaseModel):
    index: int = 0
    message: Message
    finish_reason: Optional[str] = "stop"


class Usage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletionResponse(BaseModel):
    id: str = "chatcmpl-test"
    object: str = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str = "test-llm-model"
    choices: List[Choice]
    usage: Optional[Usage] = Field(default_factory=Usage)


class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[Message]
    tools: Optional[List[Dict[str, Any]]] = None
    tool_choice: Optional[Union[str, Dict[str, Any]]] = None
    stream: Optional[bool] = False


app = FastAPI()


class TestLLMServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 8088):
        self.host = host
        self.port = port
        self._server_thread: Optional[threading.Thread] = None
        self._static_response: Optional[ChatCompletionResponse] = None
        self._primed_responses: List[ChatCompletionResponse] = []
        self._primed_image_responses: List[Dict[str, Any]] = []
        self._primed_response_lock = threading.Lock()
        self.captured_requests: List[ChatCompletionRequest] = []
        self._app = app # Keep a reference to the FastAPI app
        self._uvicorn_server: Optional[uvicorn.Server] = None # To store the server instance
        self.response_delay_seconds: float = 0.01
        self._setup_logger()
        self._setup_routes()
        self._stateful_responses_cache: Dict[str, List[Any]] = {}
        self._stateful_cache_lock = threading.Lock()

    def _setup_logger(self):
        """Sets up a dedicated logger for the TestLLMServer."""
        self.logger = logging.getLogger("TestLLMServer")
        self.logger.setLevel(logging.DEBUG)

        self.logger.propagate = False

        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)

        log_file_path = os.path.join(os.getcwd(), "test_llm_server.log")
        file_handler = logging.FileHandler(log_file_path, mode="a")
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        self.logger.addHandler(file_handler)
        self.logger.info(
            f"TestLLMServer logger initialized. Logging to: {log_file_path}"
        )

    @property
    def started(self) -> bool:
        """Checks if the uvicorn server instance is started."""
        return self._uvicorn_server is not None and self._uvicorn_server.started

    def _setup_routes(self):
        @self._app.post("/v1/images/generations")
        async def image_generations(request: Request):
            await asyncio.sleep(0.01)

            response_data = None
            with self._primed_response_lock:
                if self._primed_image_responses:
                    response_data = self._primed_image_responses.pop(0)

            if response_data:
                status_code = response_data.get("status_code", 200)
                response_json_str = response_data.get("response", "{}")
                return json.loads(response_json_str)
            else:
                raise HTTPException(status_code=404, detail="No primed image response")

        @self._app.post("/v1/chat/completions")
        async def chat_completions(
            request: ChatCompletionRequest, raw_request: Request
        ):
            raw_body_bytes = await raw_request.body()
            raw_body_str = raw_body_bytes.decode("utf-8")
            self.logger.debug(f"Received raw request body:\n{raw_body_str}")
            self.logger.debug(
                f"Parsed ChatCompletionRequest model:\n{request.model_dump_json(indent=2)}"
            )

            if request.messages:
                for i, msg in enumerate(request.messages):
                    self.logger.debug(f"Message {i} - Role: {msg.role}")
                    self.logger.debug(
                        f"Message {i} - Content Type: {type(msg.content)}"
                    )
                    self.logger.debug(f"Message {i} - Content Value: {msg.content}")
                    if msg.tool_calls:
                        self.logger.debug(f"Message {i} - Tool Calls: {msg.tool_calls}")

            self.captured_requests.append(request.model_copy(deep=True))

            # Add a small delay to simulate network latency and force the event
            # loop to yield, ensuring true concurrency in stress tests.
            await asyncio.sleep(self.response_delay_seconds)

            initial_prompt = request.messages[0].content if request.messages else ""
            if isinstance(initial_prompt, str):
                case_id_match = re.search(r"\[test_case_id=([\w.-]+)\]", initial_prompt)
                if case_id_match:
                    case_id = case_id_match.group(1)
                    self.logger.info(f"Stateful test case detected: {case_id}")

                    with self._stateful_cache_lock:
                        if case_id not in self._stateful_responses_cache:
                            self.logger.info(
                                f"Caching responses for new test case: {case_id}"
                            )
                            responses_match = re.search(
                                r"\[responses_json=([\w=+/]+)\]", initial_prompt
                            )
                            if responses_match:
                                b64_str = responses_match.group(1)
                                try:
                                    json_str = base64.b64decode(b64_str).decode("utf-8")
                                    self._stateful_responses_cache[case_id] = (
                                        json.loads(json_str)
                                    )
                                    self.logger.info(
                                        f"Cached {len(self._stateful_responses_cache[case_id])} responses for {case_id}"
                                    )
                                except (
                                    base64.binascii.Error,
                                    json.JSONDecodeError,
                                    UnicodeDecodeError,
                                ) as e:
                                    self.logger.error(
                                        f"Failed to decode stateful responses for {case_id}: {e}"
                                    )
                                    raise HTTPException(
                                        status_code=500,
                                        detail=f"Stateful test case '{case_id}' has invalid [responses_json] directive.",
                                    )
                            else:
                                self.logger.error(
                                    f"No [responses_json] directive found for stateful test case: {case_id}"
                                )
                                raise HTTPException(
                                    status_code=500,
                                    detail=f"Stateful test case '{case_id}' found but no [responses_json] directive.",
                                )

                    turn_index = (len(request.messages) - 1) // 2
                    self.logger.info(
                        f"Request for turn {turn_index} of test case {case_id}"
                    )

                    with self._stateful_cache_lock:
                        if turn_index < len(self._stateful_responses_cache[case_id]):
                            response_spec = self._stateful_responses_cache[case_id][
                                turn_index
                            ]
                            self.logger.info(
                                f"Serving response for turn {turn_index} of test case {case_id}"
                            )
                        else:
                            self.logger.error(
                                f"Test case {case_id} ran out of responses. Requested turn {turn_index}, but only {len(self._stateful_responses_cache[case_id])} defined."
                            )
                            raise HTTPException(
                                status_code=500,
                                detail=f"Stateful test case '{case_id}' ran out of responses. Requested turn {turn_index}, but only {len(self._stateful_responses_cache[case_id])} are defined.",
                            )

                    if isinstance(response_spec, dict) and response_spec.get(
                        "status_code"
                    ):
                        status_code = response_spec["status_code"]
                        detail = response_spec.get("json_body", {}).get(
                            "error", "Test server error"
                        )
                        self.logger.info(
                            f"Simulating HTTP error with status code {status_code} and detail '{detail}'"
                        )
                        raise HTTPException(status_code=status_code, detail=detail)

                    if isinstance(response_spec, dict):
                        if "expected_request" in response_spec:
                            self._verify_expected_request(
                                request,
                                response_spec["expected_request"],
                                case_id,
                                turn_index,
                            )
                        response_to_serve = ChatCompletionResponse(
                            **response_spec.get("static_response", {})
                        )
                    else:
                        response_to_serve = response_spec

                    if request.stream:
                        self.logger.info(
                            f"Handling stream request for model {request.model}"
                        )
                        return StreamingResponse(
                            self._generate_stream_chunks(
                                response_to_serve, request.model
                            ),
                            media_type="text/event-stream",
                        )
                    else:
                        self.logger.info(
                            f"Serving non-streamed response for model {request.model}"
                        )
                        return response_to_serve

            response_spec = None
            with self._primed_response_lock:
                if self._primed_responses:
                    response_spec = self._primed_responses.pop(0)
                    self.logger.info(
                        f"Using primed response. {len(self._primed_responses)} remaining."
                    )
                elif self._static_response:
                    response_spec = self._static_response
                    self.logger.info("Using globally configured static response.")
                else:
                    self.logger.info("Using default response.")
                    default_message = Message(
                        role="assistant",
                        content="Default response from Test LLM Server (no specific response primed or configured)",
                    )
                    default_choice = Choice(
                        message=default_message, finish_reason="stop"
                    )
                    response_spec = ChatCompletionResponse(choices=[default_choice])

            if not response_spec:
                self.logger.error(
                    "No response configured and default failed to generate."
                )
                raise HTTPException(
                    status_code=500, detail="TestLLMServer: No response configured."
                )

            if isinstance(response_spec, dict) and response_spec.get("status_code"):
                status_code = response_spec["status_code"]
                detail = response_spec.get("json_body", {}).get(
                    "error", "Test server error"
                )
                self.logger.info(
                    f"Simulating HTTP error with status code {status_code} and detail '{detail}'"
                )
                raise HTTPException(status_code=status_code, detail=detail)

            if isinstance(response_spec, dict):
                response_to_serve = ChatCompletionResponse(**response_spec)
            else:
                response_to_serve = response_spec

            if request.stream:
                self.logger.info(f"Handling stream request for model {request.model}")
                return StreamingResponse(
                    self._generate_stream_chunks(response_to_serve, request.model),
                    media_type="text/event-stream",
                )
            else:
                self.logger.info(
                    f"Serving non-streamed response for model {request.model}"
                )
                return response_to_serve

    async def _generate_stream_chunks(
        self, full_response: ChatCompletionResponse, request_model: str
    ) -> AsyncGenerator[str, None]:
        """
        Asynchronously generates SSE formatted delta chunks from a full ChatCompletionResponse.
        """
        try:
            if (
                full_response.choices
                and full_response.choices[0].message.role == "assistant"
            ):
                role_chunk = ChatCompletionChunk(
                    model=request_model,
                    choices=[StreamingChoice(delta=DeltaMessage(role="assistant"))],
                )
                yield f"data: {role_chunk.model_dump_json()}\n\n"
                await asyncio.sleep(0.01)

            full_content = full_response.choices[0].message.content
            if isinstance(full_content, str) and full_content:
                num_chunks = 3
                content_len = len(full_content)
                if content_len == 0:
                    pass
                elif content_len < num_chunks:
                    num_chunks = 1

                approx_chunk_size = (content_len + num_chunks - 1) // num_chunks

                for i in range(num_chunks):
                    start_idx = i * approx_chunk_size
                    end_idx = min((i + 1) * approx_chunk_size, content_len)
                    content_delta = full_content[start_idx:end_idx]

                    if content_delta:
                        content_chunk_obj = ChatCompletionChunk(
                            model=request_model,
                            choices=[
                                StreamingChoice(
                                    delta=DeltaMessage(content=content_delta)
                                )
                            ],
                        )
                        yield f"data: {content_chunk_obj.model_dump_json()}\n\n"
                        await asyncio.sleep(0.01)

            tool_calls_from_full_response = full_response.choices[0].message.tool_calls
            if tool_calls_from_full_response:
                for tc_idx, complete_tool_call in enumerate(
                    tool_calls_from_full_response
                ):
                    chunk1_delta = DeltaMessage(
                        tool_calls=[
                            ToolCallDelta(
                                index=tc_idx,
                                id=complete_tool_call.id,
                                type="function",
                                function=ToolCallDeltaFunction(
                                    name=complete_tool_call.function.name, arguments=""
                                ),
                            )
                        ]
                    )
                    chunk1_obj = ChatCompletionChunk(
                        model=request_model,
                        choices=[StreamingChoice(delta=chunk1_delta)],
                    )
                    yield f"data: {chunk1_obj.model_dump_json()}\n\n"
                    await asyncio.sleep(0.01)

                    chunk2_delta = DeltaMessage(
                        tool_calls=[
                            ToolCallDelta(
                                index=tc_idx,
                                id=complete_tool_call.id,
                                type="function",
                                function=ToolCallDeltaFunction(
                                    arguments=complete_tool_call.function.arguments
                                ),
                            )
                        ]
                    )
                    chunk2_obj = ChatCompletionChunk(
                        model=request_model,
                        choices=[StreamingChoice(delta=chunk2_delta)],
                    )
                    yield f"data: {chunk2_obj.model_dump_json()}\n\n"
                    await asyncio.sleep(0.01)

            finish_reason = full_response.choices[0].finish_reason
            final_delta_message = DeltaMessage()

            if finish_reason:
                final_choice = StreamingChoice(
                    delta=final_delta_message, finish_reason=finish_reason
                )
                final_chunk_dict = ChatCompletionChunk(
                    model=request_model, choices=[final_choice]
                ).model_dump(exclude_none=True)

                if full_response.usage:
                    final_chunk_dict["usage"] = full_response.usage.model_dump()
                    self.logger.info(
                        f"Adding usage data to final stream chunk: {final_chunk_dict['usage']}"
                    )

                yield f"data: {json.dumps(final_chunk_dict)}\n\n"
                await asyncio.sleep(0.01)

        except Exception as e:
            self.logger.error(f"Error during stream generation: {e}", exc_info=True)
            error_payload = {
                "error": {
                    "message": f"Stream generation error: {str(e)}",
                    "type": "server_error",
                    "code": 500,
                }
            }
            yield f"data: {json.dumps(error_payload)}\n\n"
        finally:
            yield "data: [DONE]\n\n"
            self.logger.info("Stream finished, sent [DONE].")

    def _verify_tool_declarations(
        self,
        actual_tools: List[Dict],
        expected_declarations: List[Dict],
        case_id: str,
        turn_index: int,
    ):
        """Verifies that the tool declarations sent to the LLM match expectations."""
        actual_tool_map = {
            tool.get("function", {}).get("name"): tool.get("function", {})
            for tool in actual_tools
        }

        for expected_decl in expected_declarations:
            expected_name = expected_decl.get("name")
            if not expected_name:
                raise HTTPException(
                    status_code=500,
                    detail=f"Stateful test case '{case_id}' turn {turn_index}: "
                    f"expected_tool_declarations_contain item is missing 'name'.",
                )

            if expected_name not in actual_tool_map:
                raise HTTPException(
                    status_code=500,
                    detail=f"Stateful test case '{case_id}' turn {turn_index}: "
                    f"Expected tool '{expected_name}' was not declared to the LLM. "
                    f"Actual tools: {list(actual_tool_map.keys())}",
                )

            actual_decl = actual_tool_map[expected_name]
            if "description_contains" in expected_decl:
                expected_desc_substr = expected_decl["description_contains"]
                actual_desc = actual_decl.get("description", "")
                if expected_desc_substr not in actual_desc:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Stateful test case '{case_id}' turn {turn_index}: "
                        f"Description for tool '{expected_name}' did not match. "
                        f"Expected to contain: '{expected_desc_substr}'. "
                        f"Actual: '{actual_desc}'",
                    )

    def _verify_tool_responses(
        self,
        actual_messages: List[Message],
        expected_responses: List[Dict],
        case_id: str,
        turn_index: int,
    ):
        """Verifies that tool responses in the LLM history match expectations."""
        tool_messages = [
            msg for msg in actual_messages if msg.role == "tool" and msg.tool_call_id
        ]

        if len(tool_messages) != len(expected_responses):
            raise HTTPException(
                status_code=500,
                detail=f"Stateful test case '{case_id}' turn {turn_index}: "
                f"Mismatch in number of tool responses. "
                f"Expected {len(expected_responses)}, Got {len(tool_messages)}.",
            )

        # Find the previous request to match tool_call_ids
        # The current request is the last one in captured_requests.
        # The one that *made* the tool call is the one before that.
        if len(self.captured_requests) < 2:
            raise HTTPException(
                status_code=500,
                detail=f"Stateful test case '{case_id}' turn {turn_index}: "
                f"Cannot verify tool responses, not enough request history captured.",
            )
        prior_request = self.captured_requests[-2]
        prior_tool_calls = (
            prior_request.messages[-1].tool_calls
            if prior_request.messages and prior_request.messages[-1].tool_calls
            else []
        )

        for expected_resp in expected_responses:
            tool_call_id_to_match = None
            prior_request_index = expected_resp.get(
                "tool_call_id_matches_prior_request_index"
            )
            if prior_request_index is not None:
                if prior_request_index < len(prior_tool_calls):
                    tool_call_id_to_match = prior_tool_calls[prior_request_index].id
                else:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Stateful test case '{case_id}' turn {turn_index}: "
                        f"Invalid tool_call_id_matches_prior_request_index: {prior_request_index}. "
                        f"Prior request only had {len(prior_tool_calls)} tool calls.",
                    )

            if not tool_call_id_to_match:
                raise HTTPException(
                    status_code=500,
                    detail=f"Stateful test case '{case_id}' turn {turn_index}: "
                    f"Could not determine tool_call_id for expected response: {expected_resp}",
                )

            actual_tool_msg = next(
                (
                    msg
                    for msg in tool_messages
                    if msg.tool_call_id == tool_call_id_to_match
                ),
                None,
            )

            if not actual_tool_msg:
                raise HTTPException(
                    status_code=500,
                    detail=f"Stateful test case '{case_id}' turn {turn_index}: "
                    f"No tool response found for tool_call_id '{tool_call_id_to_match}'.",
                )

            if "response_json_matches" in expected_resp:
                expected_json = expected_resp["response_json_matches"]
                try:
                    actual_json = json.loads(actual_tool_msg.content)
                    if actual_json != expected_json:
                        raise HTTPException(
                            status_code=500,
                            detail=f"Stateful test case '{case_id}' turn {turn_index}: "
                            f"JSON content for tool '{tool_call_id_to_match}' did not match.\n"
                            f"Expected: {json.dumps(expected_json)}\n"
                            f"Actual:   {json.dumps(actual_json)}",
                        )
                except json.JSONDecodeError:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Stateful test case '{case_id}' turn {turn_index}: "
                        f"Tool response for '{tool_call_id_to_match}' was not valid JSON. "
                        f"Content: {actual_tool_msg.content}",
                    )

            if "response_contains" in expected_resp:
                expected_substr = expected_resp["response_contains"]
                if expected_substr not in str(actual_tool_msg.content):
                    raise HTTPException(
                        status_code=500,
                        detail=f"Stateful test case '{case_id}' turn {turn_index}: "
                        f"Content for tool '{tool_call_id_to_match}' did not contain expected substring.\n"
                        f"Expected to contain: '{expected_substr}'\n"
                        f"Actual:              '{actual_tool_msg.content}'",
                    )

    def _verify_expected_request(
        self,
        request: ChatCompletionRequest,
        expected_request_spec: Dict,
        case_id: str,
        turn_index: int,
    ):
        """Dispatches verification checks based on keys in the expected_request spec."""
        if "expected_tool_declarations_contain" in expected_request_spec:
            self._verify_tool_declarations(
                request.tools or [],
                expected_request_spec["expected_tool_declarations_contain"],
                case_id,
                turn_index,
            )
        if "expected_tool_responses_in_llm_messages" in expected_request_spec:
            self._verify_tool_responses(
                request.messages,
                expected_request_spec["expected_tool_responses_in_llm_messages"],
                case_id,
                turn_index,
            )

    def configure_static_response(
        self, response: Union[Dict[str, Any], ChatCompletionResponse]
    ):
        """
        Configures a single static response that the server will return if no
        dynamically primed responses are available.
        Accepts either a dictionary (which will be parsed into ChatCompletionResponse)
        or a ChatCompletionResponse object directly.
        """
        if isinstance(response, dict):
            self._static_response = ChatCompletionResponse(**response)
        elif isinstance(response, ChatCompletionResponse):
            self._static_response = response
        else:
            raise TypeError(
                "Static response must be a dict or ChatCompletionResponse object."
            )
        self.logger.info("Global static response configured.")

    def prime_responses(
        self, responses: List[Union[Dict[str, Any], ChatCompletionResponse]]
    ):
        """
        Primes the server with a sequence of responses to serve for subsequent requests.
        Each call to this method overwrites any previously primed responses.
        """
        with self._primed_response_lock:
            self._primed_responses = []
            for rsp in responses:
                if isinstance(rsp, dict):
                    if rsp.get("status_code"):
                        self._primed_responses.append(rsp)
                    else:
                        self._primed_responses.append(ChatCompletionResponse(**rsp))
                elif isinstance(rsp, ChatCompletionResponse):
                    self._primed_responses.append(rsp)
                else:
                    raise TypeError(
                        "Each response in the list must be a dict or ChatCompletionResponse object."
                    )
            self.logger.info(f"Primed with {len(self._primed_responses)} responses.")

    def prime_image_generation_responses(self, responses: List[Dict[str, Any]]):
        with self._primed_response_lock:
            self._primed_image_responses = responses
            self.logger.info(
                f"Primed with {len(self._primed_image_responses)} image generation responses."
            )

    def set_response_delay(self, seconds: float):
        """Sets a delay for all responses from the chat_completions endpoint."""
        self.response_delay_seconds = seconds
        self.logger.info(f"LLM server response delay set to {seconds} seconds.")

    def clear_all_configurations(self):
        """Clears primed responses, the global static response, and captured requests."""
        with self._primed_response_lock:
            self._primed_responses = []
            self._primed_image_responses = []
        self._static_response = None
        self.captured_requests = []
        with self._stateful_cache_lock:
            self._stateful_responses_cache.clear()
        self.logger.info(
            "All configurations (primed, static, captured requests) cleared."
        )

    def clear_stateful_cache_for_id(self, case_id: str):
        """Removes a specific test case ID from the stateful response cache."""
        with self._stateful_cache_lock:
            if case_id in self._stateful_responses_cache:
                del self._stateful_responses_cache[case_id]
                self.logger.info(f"Cleared stateful cache for test case ID: {case_id}")

    def get_captured_requests(self) -> List[ChatCompletionRequest]:
        return self.captured_requests

    def clear_captured_requests(self):
        self.captured_requests = []

    def start(self):
        """Starts the FastAPI server in a separate thread."""
        if self._server_thread is not None and self._server_thread.is_alive():
            self.logger.warning("TestLLMServer is already running.")
            return

        self.clear_all_configurations()

        config = uvicorn.Config(
            self._app, host=self.host, port=self.port, log_level="warning"
        )
        self._uvicorn_server = uvicorn.Server(config)

        async def async_serve_wrapper():
            """Coroutine to run the server's serve() method and handle potential errors."""
            try:
                if self._uvicorn_server:
                    await self._uvicorn_server.serve()
            except asyncio.CancelledError:
                self.logger.info("Server.serve() task was cancelled.")
            except Exception as e:
                self.logger.error(f"Error during server.serve(): {e}", exc_info=True)

        def run_server_in_new_loop():
            """Target function for the server thread. Sets up and runs an event loop."""
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(async_serve_wrapper())
            except KeyboardInterrupt:
                print("TestLLMServer: KeyboardInterrupt in server thread.")
            finally:
                try:
                    all_tasks = asyncio.all_tasks(loop)
                    if all_tasks:
                        for task in all_tasks:
                            task.cancel()
                        loop.run_until_complete(
                            asyncio.gather(*all_tasks, return_exceptions=True)
                        )

                    if hasattr(loop, "shutdown_asyncgens"):
                        loop.run_until_complete(loop.shutdown_asyncgens())
                except Exception as e:
                    self.logger.error(
                        f"Error during loop shutdown tasks: {e}", exc_info=True
                    )
                finally:
                    loop.close()
                    self.logger.info("Event loop in server thread closed.")

        self._server_thread = threading.Thread(
            target=run_server_in_new_loop, daemon=True
        )
        self._server_thread.start()

        self.logger.info(f"TestLLMServer starting on http://{self.host}:{self.port}...")

    def stop(self):
        """Stops the FastAPI server."""
        if self._uvicorn_server:
            self._uvicorn_server.should_exit = True

        if self._server_thread and self._server_thread.is_alive():
            self.logger.info("TestLLMServer stopping, joining thread...")
            self._server_thread.join(timeout=5.0)
            if self._server_thread.is_alive():
                self.logger.warning("Server thread did not exit cleanly.")
        self._server_thread = None
        self._uvicorn_server = None
        self.logger.info("TestLLMServer stopped.")

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"


if __name__ == "__main__":
    if __name__ == "__main__":
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

        server = TestLLMServer()
        server.start()

        sample_response_data = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "Hello from the Test LLM!",
                    },
                    "finish_reason": "stop",
                }
            ]
        }
        server.configure_static_response(sample_response_data)
        server.logger.info(
            f"Test LLM Server running at {server.url}. Configured with a static response."
        )
        server.logger.info(
            'Try: curl -X POST -H "Content-Type: application/json" -d \'{"model": "test", "messages": [{"role": "user", "content": "Hi"}]}\' http://127.0.0.1:8088/v1/chat/completions'
        )

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            server.logger.info("Shutting down Test LLM Server...")
        finally:
            server.stop()
