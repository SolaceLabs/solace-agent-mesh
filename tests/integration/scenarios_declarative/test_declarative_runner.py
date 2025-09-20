"""
Pytest test runner for declarative (YAML/JSON) test scenarios.
"""

import base64
import pytest
import yaml
import os
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Union, Optional, Tuple

from sam_test_infrastructure.llm_server.server import (
    TestLLMServer,
    ChatCompletionRequest,
)

from sam_test_infrastructure.gateway_interface.component import (
    TestGatewayComponent,
)
from sam_test_infrastructure.artifact_service.service import (
    TestInMemoryArtifactService,
)
from sam_test_infrastructure.a2a_validator.validator import A2AMessageValidator
from a2a.types import (
    TextPart,
    DataPart,
    Task,
    TaskStatusUpdateEvent,
    TaskArtifactUpdateEvent,
    JSONRPCError,
)
from a2a.utils.message import get_data_parts, get_message_text
from solace_agent_mesh.agent.sac.app import SamAgentApp
from solace_agent_mesh.agent.sac.component import SamAgentComponent
from google.genai import types as adk_types  # Add this import
import re
import json
import builtins
from asteval import Interpreter
import math
from ..scenarios_programmatic.test_helpers import (
    get_all_task_events,
    extract_outputs_from_event_list,
)
from solace_agent_mesh.agent.utils.artifact_helpers import (
    generate_artifact_metadata_summary,
    load_artifact_content_or_metadata,
)
from solace_agent_mesh.agent.testing.debug_utils import pretty_print_event_history

MODEL_SUFFIX_REGEX = r"test-model-([^-]+)-"

TEST_RUNNER_MATH_SYMBOLS = {
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "sqrt": math.sqrt,
    "pow": math.pow,
    "exp": math.exp,
    "log": math.log,
    "log10": math.log10,
    "pi": math.pi,
    "e": math.e,
    "inf": math.inf,
    "radians": math.radians,
    "factorial": math.factorial,
    "sum": sum,
    "sinh": math.sinh,
    "cosh": math.cosh,
    "tanh": math.tanh,
}


async def _setup_scenario_environment(
    declarative_scenario: Dict[str, Any],
    test_llm_server: TestLLMServer,
    test_artifact_service_instance: TestInMemoryArtifactService,
    scenario_id: str,
    artifact_scope: str,
) -> None:
    """
    Primes the LLM server and sets up initial artifacts based on the scenario definition.
    """
    llm_interactions = declarative_scenario.get("llm_interactions", [])
    primed_llm_responses = []
    for interaction in llm_interactions:
        if "static_response" in interaction:
            try:
                primed_llm_responses.append(interaction["static_response"])
            except Exception as e:
                pytest.fail(
                    f"Scenario {scenario_id}: Error parsing LLM static_response: {e}\nResponse data: {interaction['static_response']}"
                )
        else:
            raise AssertionError(
                f"Scenario {scenario_id}: 'static_response' missing in llm_interaction: {interaction}"
            )
    test_llm_server.prime_responses(primed_llm_responses)
    primed_image_responses = declarative_scenario.get(
        "primed_image_generation_responses", []
    )
    if primed_image_responses:
        test_llm_server.prime_image_generation_responses(primed_image_responses)
    setup_artifacts_spec = declarative_scenario.get("setup_artifacts", [])
    if setup_artifacts_spec:
        gateway_input_data_for_artifact_setup = declarative_scenario.get(
            "gateway_input", {}
        )
        user_identity_for_artifacts = gateway_input_data_for_artifact_setup.get(
            "user_identity", "default_artifact_user@example.com"
        )
        app_name_for_setup = (
            "test_namespace"
            if artifact_scope == "namespace"
            else gateway_input_data_for_artifact_setup.get(
                "target_agent_name", "TestAgent_Setup"
            )
        )
        session_id_for_setup = gateway_input_data_for_artifact_setup.get(
            "external_context", {}
        ).get("a2a_session_id", f"setup_session_for_{user_identity_for_artifacts}")

        for artifact_spec in setup_artifacts_spec:
            filename = artifact_spec["filename"]
            mime_type = artifact_spec.get("mime_type", "application/octet-stream")
            content_str = artifact_spec.get("content")
            content_base64 = artifact_spec.get("content_base64")

            content_bytes = b""
            if content_str is not None:
                content_bytes = content_str.encode("utf-8")
            elif content_base64 is not None:
                content_bytes = base64.b64decode(content_base64)
            else:
                raise AssertionError(
                    f"Scenario {scenario_id}: Artifact spec for '{filename}' must have 'content' or 'content_base64'."
                )

            part_to_save = adk_types.Part(
                inline_data=adk_types.Blob(mime_type=mime_type, data=content_bytes)
            )

            effective_session_id_for_save = session_id_for_setup

            await test_artifact_service_instance.save_artifact(
                app_name=app_name_for_setup,
                user_id=user_identity_for_artifacts,
                session_id=effective_session_id_for_save,
                filename=filename,
                artifact=part_to_save,
            )
            if "metadata" in artifact_spec:
                metadata_filename = f"{filename}.metadata.json"
                metadata_bytes = json.dumps(artifact_spec["metadata"]).encode("utf-8")
                metadata_part = adk_types.Part(
                    inline_data=adk_types.Blob(
                        mime_type="application/json", data=metadata_bytes
                    )
                )
                await test_artifact_service_instance.save_artifact(
                    app_name=app_name_for_setup,
                    user_id=user_identity_for_artifacts,
                    session_id=effective_session_id_for_save,
                    filename=metadata_filename,
                    artifact=metadata_part,
                )
            print(f"Scenario {scenario_id}: Setup artifact '{filename}' created.")


async def _execute_gateway_and_collect_events(
    test_gateway_app_instance: TestGatewayComponent,
    gateway_input_data: Dict[str, Any],
    overall_timeout: float,
    scenario_id: str,
) -> Tuple[
    str,
    List[Union[TaskStatusUpdateEvent, TaskArtifactUpdateEvent, Task, JSONRPCError]],
    Optional[str],
    Optional[str],
]:
    """
    Submits input to the gateway, collects all events, and extracts key text outputs.
    """
    task_id = await test_gateway_app_instance.send_test_input(gateway_input_data)
    assert (
        task_id
    ), f"Scenario {scenario_id}: Failed to submit task via TestGatewayComponent."
    print(f"Scenario {scenario_id}: Task {task_id} submitted.")

    all_captured_events = await get_all_task_events(
        gateway_component=test_gateway_app_instance,
        task_id=task_id,
        overall_timeout=overall_timeout,
    )
    assert (
        all_captured_events
    ), f"Scenario {scenario_id}: No events captured from gateway for task {task_id}."

    (
        _terminal_event_obj_for_text,
        aggregated_stream_text_for_final_assert,
        text_from_terminal_event_for_final_assert,
    ) = extract_outputs_from_event_list(all_captured_events, scenario_id)

    return (
        task_id,
        all_captured_events,
        aggregated_stream_text_for_final_assert,
        text_from_terminal_event_for_final_assert,
    )


async def _assert_summary_in_text(
    text_to_search: str,
    artifact_identifiers: List[Dict[str, Any]],
    component: "SamAgentComponent",
    user_id: str,
    session_id: str,
    app_name: str,
    scenario_id: str,
    context_str: str,
):
    """Asserts that key details of an artifact's metadata summary are present in text."""
    # The header check is now performed by the caller (_assert_llm_interactions)
    # to handle multiple valid header formats.

    for artifact_ref in artifact_identifiers:
        filename = artifact_ref.get("filename")
        filename_regex = artifact_ref.get("filename_matches_regex")
        version = artifact_ref.get("version", "latest")

        if filename_regex:
            # For regex, we can't load the artifact. We just check that a summary
            # with a matching filename exists in the prompt.
            header_regex = re.compile(
                r"(?:--- Metadata for artifact '(.+?)' \(v\d+\) ---|Artifact: '(.+?)' \(version: \d+\))"
            )
            found_match = False
            for line in text_to_search.splitlines():
                match = header_regex.search(line)
                if match:
                    # The filename could be in group 1 or group 2
                    extracted_filename = match.group(1) or match.group(2)
                    if extracted_filename and re.match(
                        filename_regex, extracted_filename
                    ):
                        found_match = True
                        print(
                            f"Scenario {scenario_id}: {context_str} - Found artifact summary header for filename '{extracted_filename}' which matches regex '{filename_regex}'."
                        )
                        break
            assert found_match, (
                f"Scenario {scenario_id}: {context_str} - Could not find an artifact summary header in the text "
                f"with a filename matching the regex '{filename_regex}'.\nText searched:\n---\n{text_to_search}\n---"
            )
            continue  # Move to the next artifact identifier

        metadata_result = await load_artifact_content_or_metadata(
            artifact_service=component.artifact_service,
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
            filename=filename,
            version=version,
            load_metadata_only=True,
        )

        assert metadata_result.get("status") == "success", (
            f"Scenario {scenario_id}: {context_str} - Failed to load metadata for '{filename}' v{version} for assertion: "
            f"{metadata_result.get('message')}"
        )

        metadata = metadata_result.get("metadata", {})
        resolved_version = metadata_result.get("version")

        # Spot-check key fields
        # The agent can produce two different headers depending on the context.
        header_format_1 = (
            f"--- Metadata for artifact '{filename}' (v{resolved_version}) ---"
        )
        header_format_2 = f"Artifact: '{filename}' (version: {resolved_version})"

        assert header_format_1 in text_to_search or header_format_2 in text_to_search, (
            f"Scenario {scenario_id}: {context_str} - Expected artifact header not found for '{filename}' v{resolved_version} in text:\n"
            f"---\n{text_to_search}\n---"
        )

        if "description" in metadata:
            desc_val = metadata["description"]
            expected_desc_md = f"*   **Description:** {desc_val}"
            expected_desc_yaml = f"description: {desc_val}"
            assert (
                expected_desc_md in text_to_search
                or expected_desc_yaml in text_to_search
            ), (
                f"Scenario {scenario_id}: {context_str} - Expected description for artifact '{filename}' not found in either markdown or yaml format in text:\n"
                f"---\n{text_to_search}\n---"
            )

        if "mime_type" in metadata:
            mime_val = metadata["mime_type"]
            expected_mime_md = f"*   **Type:** {mime_val}"
            expected_mime_yaml = f"mime_type: {mime_val}"
            assert (
                expected_mime_md in text_to_search
                or expected_mime_yaml in text_to_search
            ), (
                f"Scenario {scenario_id}: {context_str} - Expected mime_type for artifact '{filename}' not found in either markdown or yaml format in text:\n"
                f"---\n{text_to_search}\n---"
            )


async def _assert_llm_interactions(
    expected_llm_interactions: List[Dict[str, Any]],
    captured_llm_requests: List[ChatCompletionRequest],
    scenario_id: str,
    test_artifact_service_instance: TestInMemoryArtifactService,
    gateway_input_data: Dict[str, Any],
    agent_components: Dict[str, SamAgentComponent],
    artifact_scope: str,
) -> None:
    """
    Asserts the captured LLM requests against the expected interactions.
    """
    # Build a map from model suffix to component instance ONCE.
    model_suffix_to_component = {}
    for agent_name, component in agent_components.items():
        model_config = component.get_config("model", {})
        if isinstance(model_config, dict):
            model_name_str = model_config.get("model", "")
            match = re.search(MODEL_SUFFIX_REGEX, model_name_str)
            if match:
                suffix = match.group(1)
                model_suffix_to_component[suffix] = component

    assert len(captured_llm_requests) == len(
        expected_llm_interactions
    ), f"Scenario {scenario_id}: Mismatch in number of LLM calls. Expected {len(expected_llm_interactions)}, Got {len(captured_llm_requests)}"

    for i, expected_interaction in enumerate(expected_llm_interactions):
        if "expected_request" in expected_interaction:
            actual_request_raw = captured_llm_requests[i]
            expected_req_details = expected_interaction["expected_request"]

            # Determine which agent is making the call
            calling_agent_component = None
            model_name_str = actual_request_raw.model
            match = re.search(MODEL_SUFFIX_REGEX, model_name_str)
            if match:
                suffix = match.group(1)
                calling_agent_component = model_suffix_to_component.get(suffix)

            assert (
                calling_agent_component is not None
            ), f"Could not determine calling agent component from model name '{model_name_str}'"

            if "prompt_contains_artifact_summary_for" in expected_req_details:
                artifact_identifiers = expected_req_details[
                    "prompt_contains_artifact_summary_for"
                ]
                user_id = gateway_input_data.get("user_identity")
                session_id = gateway_input_data.get("external_context", {}).get(
                    "a2a_session_id"
                )

                app_name_for_artifacts = (
                    "test_namespace"
                    if artifact_scope == "namespace"
                    else calling_agent_component.agent_name
                )

                assert (
                    user_id
                ), "gateway_input.user_identity is required for artifact summary assertion."
                assert (
                    session_id
                ), "gateway_input.external_context.a2a_session_id is required for artifact summary assertion."
                assert (
                    app_name_for_artifacts
                ), "Could not determine app_name for artifact summary assertion."

                sam_agent_component = calling_agent_component

                # The agent code uses two possible headers depending on the input method.
                # We will check for the presence of the common part.
                header_for_filepart = (
                    "The user has provided the following file as context for your task."
                )
                header_for_invoked = "The user has provided the following artifacts as context for your task."

                # The enriched prompt is the last message in the history.
                last_message = actual_request_raw.messages[-1]
                assert (
                    last_message.role == "user"
                ), f"Expected last message to be from user, but was {last_message.role}"

                actual_prompt_text = ""
                if isinstance(last_message.content, str):
                    actual_prompt_text = last_message.content
                elif isinstance(last_message.content, list):
                    # Handle multi-part content by concatenating text parts
                    for part in last_message.content:
                        if isinstance(part, dict) and part.get("type") == "text":
                            actual_prompt_text += part.get("text", "") + "\n"
                    actual_prompt_text = actual_prompt_text.strip()
                else:
                    pytest.fail(
                        f"Scenario {scenario_id}: LLM call {i+1} - Last message content is neither a string nor a list of parts. Got type: {type(last_message.content)}"
                    )

                assert (
                    header_for_filepart in actual_prompt_text
                    or header_for_invoked in actual_prompt_text
                ), (
                    f"Scenario {scenario_id}: LLM call {i+1} prompt - Expected an artifact summary header but none was found in text:\n"
                    f"---\n{actual_prompt_text}\n---"
                )

                await _assert_summary_in_text(
                    text_to_search=actual_prompt_text,
                    artifact_identifiers=artifact_identifiers,
                    component=sam_agent_component,
                    user_id=user_id,
                    session_id=session_id,
                    app_name=app_name_for_artifacts,
                    scenario_id=scenario_id,
                    context_str=f"LLM call {i+1} prompt",
                )

            actual_tool_names = []
            if actual_request_raw.tools:
                for tool_config_dict in actual_request_raw.tools:
                    if tool_config_dict.get(
                        "type"
                    ) == "function" and tool_config_dict.get("function"):
                        actual_tool_names.append(tool_config_dict["function"]["name"])

            if "assert_tools_exact" in expected_req_details:
                expected_tools = expected_req_details["assert_tools_exact"]
                assert sorted(actual_tool_names) == sorted(
                    expected_tools
                ), f"Scenario {scenario_id}: LLM call {i+1} exact tool list mismatch. Expected {sorted(expected_tools)}, Got {sorted(actual_tool_names)}"

            elif "tools_present" in expected_req_details:
                expected_tools_subset = set(expected_req_details["tools_present"])
                actual_tools_set = set(actual_tool_names)
                assert expected_tools_subset.issubset(
                    actual_tools_set
                ), f"Scenario {scenario_id}: LLM call {i+1} tools not present. Expected {expected_tools_subset} to be in {actual_tools_set}"

            if "tools_not_present" in expected_req_details:
                unexpected_tools = set(expected_req_details["tools_not_present"])
                actual_tools_set = set(actual_tool_names)
                intersection = unexpected_tools.intersection(actual_tools_set)
                assert not intersection, (
                    f"Scenario {scenario_id}: LLM call {i+1} - Found unexpected tools. "
                    f"Tools {intersection} should NOT have been present in {actual_tools_set}"
                )

            if "expected_tool_responses_in_llm_messages" in expected_req_details:
                expected_tool_responses_spec = expected_req_details[
                    "expected_tool_responses_in_llm_messages"
                ]
                actual_tool_response_messages = [
                    msg
                    for msg in actual_request_raw.messages
                    if msg.role == "tool"
                    or (
                        isinstance(msg.content, list)
                        and any(
                            part.get("type") == "tool_result"
                            for part in msg.content
                            if isinstance(part, dict)
                        )
                    )
                ]

                num_expected = len(expected_tool_responses_spec)
                assert (
                    len(actual_tool_response_messages) >= num_expected
                ), f"Scenario {scenario_id}: LLM call {i+1} - Not enough tool responses in history. Expected at least {num_expected}, Got {len(actual_tool_response_messages)}"

                # Only assert against the most recent tool responses, as prior calls will be in history.
                most_recent_tool_responses = actual_tool_response_messages[
                    -num_expected:
                ]

                for j, expected_tool_resp_spec in enumerate(
                    expected_tool_responses_spec
                ):
                    actual_tool_resp_msg = most_recent_tool_responses[j]

                    expected_tool_name = expected_tool_resp_spec.get(
                        "tool_name"
                    ) or expected_tool_resp_spec.get("function_name")

                    if (
                        "tool_call_id_matches_prior_request_index"
                        in expected_tool_resp_spec
                    ):
                        actual_tool_call_id_from_response = (
                            actual_tool_resp_msg.tool_call_id
                        )
                        if not actual_tool_call_id_from_response:
                            raise AssertionError(
                                f"Scenario {scenario_id}: LLM call {i+1}, Tool Response {j+1} - Actual tool response message is missing a tool_call_id."
                            )

                        originating_llm_interaction_yaml_idx = -1
                        for k_origin_search in range(i - 1, -1, -1):
                            potential_origin_interaction_yaml = (
                                expected_llm_interactions[k_origin_search]
                            )
                            potential_origin_static_response_yaml = (
                                potential_origin_interaction_yaml.get("static_response")
                            )

                            if potential_origin_static_response_yaml:
                                potential_choices = (
                                    potential_origin_static_response_yaml.get(
                                        "choices", []
                                    )
                                )
                                tool_calls_in_potential_origin_yaml = []
                                if potential_choices:
                                    tool_calls_in_potential_origin_yaml = (
                                        potential_choices[0]
                                        .get("message", {})
                                        .get("tool_calls", [])
                                    )
                                for (
                                    tool_call_yaml_obj
                                ) in tool_calls_in_potential_origin_yaml:
                                    if (
                                        tool_call_yaml_obj.get("id")
                                        == actual_tool_call_id_from_response
                                    ):
                                        originating_llm_interaction_yaml_idx = (
                                            k_origin_search
                                        )
                                        break
                                if originating_llm_interaction_yaml_idx != -1:
                                    break

                        if originating_llm_interaction_yaml_idx == -1:
                            raise AssertionError(
                                f"Scenario {scenario_id}: LLM call {i+1}, Tool Response {j+1} - Could not find an originating LLM interaction in the YAML's 'llm_interactions' (index 0 to {i-1}) that produced tool_call_id '{actual_tool_call_id_from_response}'."
                            )

                        originating_static_response_yaml = expected_llm_interactions[
                            originating_llm_interaction_yaml_idx
                        ].get("static_response")
                        originating_choices = originating_static_response_yaml.get(
                            "choices", []
                        )
                        originating_tool_calls_array_in_yaml = []
                        if originating_choices:
                            originating_tool_calls_array_in_yaml = (
                                originating_choices[0]
                                .get("message", {})
                                .get("tool_calls", [])
                            )

                        expected_tool_call_idx_within_origin = expected_tool_resp_spec[
                            "tool_call_id_matches_prior_request_index"
                        ]

                        if not (
                            0
                            <= expected_tool_call_idx_within_origin
                            < len(originating_tool_calls_array_in_yaml)
                        ):
                            raise AssertionError(
                                f"Scenario {scenario_id}: LLM call {i+1}, Tool Response {j+1} - 'tool_call_id_matches_prior_request_index' ({expected_tool_call_idx_within_origin}) "
                                f"is out of bounds for the tool_calls (count: {len(originating_tool_calls_array_in_yaml)}) of the identified originating LLM interaction (YAML index {originating_llm_interaction_yaml_idx})."
                            )

                        expected_originating_tool_call_obj_yaml = (
                            originating_tool_calls_array_in_yaml[
                                expected_tool_call_idx_within_origin
                            ]
                        )
                        expected_tool_call_id_from_yaml_origin = (
                            expected_originating_tool_call_obj_yaml.get("id")
                        )

                        assert (
                            actual_tool_call_id_from_response
                            == expected_tool_call_id_from_yaml_origin
                        ), (
                            f"Scenario {scenario_id}: LLM call {i+1}, Tool Response {j+1} - tool_call_id mismatch. "
                            f"Actual response tool_call_id '{actual_tool_call_id_from_response}' does not match "
                            f"expected originating tool_call_id '{expected_tool_call_id_from_yaml_origin}' from YAML interaction {originating_llm_interaction_yaml_idx + 1}, tool_call index {expected_tool_call_idx_within_origin}."
                        )
                        originating_tool_name_from_yaml = (
                            expected_originating_tool_call_obj_yaml.get(
                                "function", {}
                            ).get("name")
                        )
                        if expected_tool_name:
                            assert (
                                originating_tool_name_from_yaml == expected_tool_name
                            ), (
                                f"Scenario {scenario_id}: LLM call {i+1}, Tool Response {j+1} - Tool name mismatch. "
                                f"Expected '{expected_tool_name}' (from current tool_response assertion spec), "
                                f"Got '{originating_tool_name_from_yaml}' from originating tool call in YAML interaction {originating_llm_interaction_yaml_idx + 1}."
                            )
                        else:
                            # If the spec doesn't provide a name, derive it from the originating call
                            expected_tool_name = originating_tool_name_from_yaml

                    if (
                        "response_contains_artifact_summary_for"
                        in expected_tool_resp_spec
                    ):
                        artifact_identifiers = expected_tool_resp_spec[
                            "response_contains_artifact_summary_for"
                        ]
                        user_id = gateway_input_data.get("user_identity")
                        session_id = gateway_input_data.get("external_context", {}).get(
                            "a2a_session_id"
                        )

                        # Determine the peer agent that was called
                        peer_tool_name = expected_tool_name
                        assert peer_tool_name and peer_tool_name.startswith(
                            "peer_"
                        ), f"Scenario {scenario_id}: LLM call {i+1}, Tool Response {j+1} - 'response_contains_artifact_summary_for' can only be used with peer tool calls."
                        peer_agent_name = peer_tool_name.replace("peer_", "", 1)

                        peer_component = agent_components.get(peer_agent_name)
                        assert (
                            peer_component is not None
                        ), f"Could not find SamAgentComponent for peer agent '{peer_agent_name}' to generate artifact summary."

                        header_text = f"Peer agent `{peer_agent_name}` created {len(artifact_identifiers)} artifact(s):"

                        assert isinstance(
                            actual_tool_resp_msg.content, str
                        ), f"Scenario {scenario_id}: LLM call {i+1}, Tool Response {j+1} - Expected string content for tool response, got {type(actual_tool_resp_msg.content)}"

                        try:
                            actual_response_json = json.loads(
                                actual_tool_resp_msg.content
                            )
                            actual_result_text = actual_response_json.get("result", "")
                        except json.JSONDecodeError:
                            pytest.fail(
                                f"Scenario {scenario_id}: LLM call {i+1}, Tool Response {j+1} - Expected JSON content for peer tool response, but got non-JSON string: '{actual_tool_resp_msg.content}'"
                            )

                        app_name_for_summary = (
                            "test_namespace"
                            if artifact_scope == "namespace"
                            else peer_agent_name
                        )
                        assert header_text in actual_result_text, (
                            f"Scenario {scenario_id}: LLM call {i+1}, Tool Response {j+1} - Expected header '{header_text}' not found in text:\n"
                            f"---\n{actual_result_text}\n---"
                        )

                        await _assert_summary_in_text(
                            text_to_search=actual_result_text,
                            artifact_identifiers=artifact_identifiers,
                            component=peer_component,
                            user_id=user_id,
                            session_id=session_id,
                            app_name=app_name_for_summary,
                            scenario_id=scenario_id,
                            context_str=f"LLM call {i+1}, Tool Response {j+1}",
                        )

                    if "response_contains" in expected_tool_resp_spec:
                        assert isinstance(
                            actual_tool_resp_msg.content, str
                        ), f"Scenario {scenario_id}: LLM call {i+1}, Tool Response {j+1} - Expected string content for tool response, got {type(actual_tool_resp_msg.content)}"

                        expected_content = expected_tool_resp_spec["response_contains"]
                        if isinstance(expected_content, list):
                            for substring in expected_content:
                                assert (
                                    substring in actual_tool_resp_msg.content
                                ), f"Scenario {scenario_id}: LLM call {i+1}, Tool Response {j+1} - Content mismatch. Expected to contain '{substring}', Got '{actual_tool_resp_msg.content}'"
                        else:
                            assert (
                                expected_content in actual_tool_resp_msg.content
                            ), f"Scenario {scenario_id}: LLM call {i+1}, Tool Response {j+1} - Content mismatch. Expected to contain '{expected_content}', Got '{actual_tool_resp_msg.content}'"

                    if "response_exact_match" in expected_tool_resp_spec:
                        expected_content = expected_tool_resp_spec[
                            "response_exact_match"
                        ]
                        actual_content = actual_tool_resp_msg.content
                        if isinstance(expected_content, dict) and isinstance(
                            actual_content, str
                        ):
                            try:
                                actual_content = json.loads(actual_content)
                            except json.JSONDecodeError:
                                pytest.fail(
                                    f"Scenario {scenario_id}: LLM call {i+1}, Tool Response {j+1} - Expected a dictionary, but actual content is a non-JSON string: '{actual_content}'"
                                )

                        assert (
                            expected_content == actual_content
                        ), f"Scenario {scenario_id}: LLM call {i+1}, Tool Response {j+1} - Exact content mismatch. Expected '{expected_content}', Got '{actual_content}'"

                    if "response_json_matches" in expected_tool_resp_spec:
                        try:
                            actual_response_json = json.loads(
                                actual_tool_resp_msg.content
                            )
                            expected_subset = expected_tool_resp_spec[
                                "response_json_matches"
                            ]
                            _assert_dict_subset(
                                expected_subset,
                                actual_response_json,
                                scenario_id,
                                event_index=i,
                                context_path=f"LLM call {i+1} Tool Response {j+1} JSON content",
                            )
                        except json.JSONDecodeError:
                            raise AssertionError(
                                f"Scenario {scenario_id}: LLM call {i+1}, Tool Response {j+1} - Tool response content was not valid JSON: '{actual_tool_resp_msg.content}'"
                            )


async def _assert_gateway_event_sequence(
    expected_event_specs_list: List[Dict[str, Any]],
    actual_events_list: List[
        Union[TaskStatusUpdateEvent, TaskArtifactUpdateEvent, Task, JSONRPCError]
    ],
    scenario_id: str,
    skip_intermediate_events: bool,
    expected_llm_interactions: List[Dict[str, Any]],
    captured_llm_requests: List[ChatCompletionRequest],
    aggregated_stream_text_for_final_assert: Optional[str],
    text_from_terminal_event_for_final_assert: Optional[str],
    test_artifact_service_instance: TestInMemoryArtifactService,
    gateway_input_data: Dict[str, Any],
    agent_components: Dict[str, SamAgentComponent],
    artifact_scope: str,
) -> None:
    """
    Asserts the sequence and content of captured gateway events against expected specifications.
    """
    actual_event_cursor = 0
    expected_event_idx = 0

    while expected_event_idx < len(expected_event_specs_list):
        if actual_event_cursor >= len(actual_events_list):
            raise AssertionError(
                f"Scenario {scenario_id}: Ran out of actual events while looking for expected event "
                f"{expected_event_idx + 1} (Type: '{expected_event_specs_list[expected_event_idx].get('type')}', "
                f"Purpose: '{expected_event_specs_list[expected_event_idx].get('event_purpose', 'N/A')}'). "
                f"Found {len(actual_events_list)} actual events in total."
            )

        current_expected_spec = expected_event_specs_list[expected_event_idx]

        is_expected_aggregated_generic_text = (
            current_expected_spec.get("type") == "status_update"
            and current_expected_spec.get("event_purpose") == "generic_text_update"
            and current_expected_spec.get("assert_aggregated_stream_content", False)
        )

        if is_expected_aggregated_generic_text:
            print(
                f"Scenario {scenario_id}: Expecting aggregated generic_text_update for expected event {expected_event_idx + 1}."
            )
            aggregated_text_content = ""
            last_consumed_actual_event_for_aggregation: Optional[
                TaskStatusUpdateEvent
            ] = None
            initial_actual_cursor_for_aggregation = actual_event_cursor

            while actual_event_cursor < len(actual_events_list):
                potential_chunk_event = actual_events_list[actual_event_cursor]
                if (
                    isinstance(potential_chunk_event, TaskStatusUpdateEvent)
                    and _get_actual_event_purpose(potential_chunk_event)
                    == "generic_text_update"
                ):
                    aggregated_text_content += _extract_text_from_generic_update(
                        potential_chunk_event
                    )
                    last_consumed_actual_event_for_aggregation = potential_chunk_event
                    actual_event_cursor += 1

                    if potential_chunk_event.final:
                        print(
                            f"Scenario {scenario_id}: Aggregation stopped due to final_flag=true on chunk at actual index {actual_event_cursor-1}."
                        )
                        break
                else:
                    print(
                        f"Scenario {scenario_id}: Aggregation stopped. Next actual event at index {actual_event_cursor} is not a continuable generic_text_update (Type: {type(potential_chunk_event).__name__}, Purpose: {_get_actual_event_purpose(potential_chunk_event)})."
                    )
                    break

            if last_consumed_actual_event_for_aggregation is None:
                raise AssertionError(
                    f"Scenario {scenario_id}: Expected an aggregated generic_text_update (event {expected_event_idx + 1}), "
                    f"but no generic_text_update events found at or after actual event index {initial_actual_cursor_for_aggregation}."
                )

            print(
                f"Scenario {scenario_id}: Matched expected event {expected_event_idx + 1} (Aggregated generic_text_update) "
                f"with actual events from index {initial_actual_cursor_for_aggregation} to {actual_event_cursor - 1}. "
                f"Aggregated text: '{aggregated_text_content}'"
            )

            await _assert_event_details(
                last_consumed_actual_event_for_aggregation,
                current_expected_spec,
                scenario_id,
                expected_event_idx,
                llm_interactions=expected_llm_interactions,
                actual_llm_requests=captured_llm_requests,
                aggregated_stream_text_for_final_assert=aggregated_stream_text_for_final_assert,
                text_from_terminal_event_for_final_assert=text_from_terminal_event_for_final_assert,
                override_text_for_assertion=aggregated_text_content,
                test_artifact_service_instance=test_artifact_service_instance,
                gateway_input_data=gateway_input_data,
                agent_components=agent_components,
                artifact_scope=artifact_scope,
            )
            expected_event_idx += 1
        else:
            current_actual_event = actual_events_list[actual_event_cursor]
            if _match_event(current_actual_event, current_expected_spec):
                print(
                    f"Scenario {scenario_id}: Matched expected event {expected_event_idx + 1} "
                    f"(Type: '{current_expected_spec.get('type')}', Purpose: '{current_expected_spec.get('event_purpose', 'N/A')}') "
                    f"with actual event at index {actual_event_cursor} (Type: {type(current_actual_event).__name__})."
                )
                await _assert_event_details(
                    current_actual_event,
                    current_expected_spec,
                    scenario_id,
                    expected_event_idx,
                    llm_interactions=expected_llm_interactions,
                    actual_llm_requests=captured_llm_requests,
                    aggregated_stream_text_for_final_assert=aggregated_stream_text_for_final_assert,
                    text_from_terminal_event_for_final_assert=text_from_terminal_event_for_final_assert,
                    test_artifact_service_instance=test_artifact_service_instance,
                    gateway_input_data=gateway_input_data,
                    agent_components=agent_components,
                    artifact_scope=artifact_scope,
                )
                expected_event_idx += 1
                actual_event_cursor += 1
            elif skip_intermediate_events:
                print(
                    f"Scenario {scenario_id}: Skipping actual event at index {actual_event_cursor} "
                    f"(Type: {type(current_actual_event).__name__}, Purpose: '{_get_actual_event_purpose(current_actual_event) or 'N/A'}') "
                    f"while looking for expected event {expected_event_idx + 1} "
                    f"(Type: '{current_expected_spec.get('type')}', Purpose: '{current_expected_spec.get('event_purpose', 'N/A')}')."
                )
                actual_event_cursor += 1
            else:
                raise AssertionError(
                    f"Scenario {scenario_id}: Event {expected_event_idx + 1} mismatch. "
                    f"Expected type '{current_expected_spec.get('type')}' (Purpose: '{current_expected_spec.get('event_purpose', 'N/A')}') "
                    f"but got actual type '{type(current_actual_event).__name__}' "
                    f"(Actual Purpose: '{_get_actual_event_purpose(current_actual_event) or 'N/A'}') "
                    f"at actual event index {actual_event_cursor}. Details: {str(current_actual_event)[:200]}"
                )

    if not skip_intermediate_events and actual_event_cursor < len(actual_events_list):
        raise AssertionError(
            f"Scenario {scenario_id}: Extra unexpected events found after matching all expected events. "
            f"Expected {len(expected_event_specs_list)} events, but got {len(actual_events_list)}. "
            f"Next unexpected event at index {actual_event_cursor}: {type(actual_events_list[actual_event_cursor]).__name__}"
        )
    elif skip_intermediate_events and expected_event_idx < len(
        expected_event_specs_list
    ):
        raise AssertionError(
            f"Scenario {scenario_id}: Not all expected events were found, even with skipping enabled. "
            f"Found {expected_event_idx} out of {len(expected_event_specs_list)} expected events. "
            f"Next expected was Type: '{expected_event_specs_list[expected_event_idx].get('type')}', "
            f"Purpose: '{expected_event_specs_list[expected_event_idx].get('event_purpose', 'N/A')}'."
        )


async def _assert_artifact_state(
    expected_artifact_state_specs: List[Dict[str, Any]],
    test_artifact_service_instance: TestInMemoryArtifactService,
    gateway_input_data: Dict[str, Any],
    scenario_id: str,
    artifact_scope: str,
) -> None:
    """
    Asserts the state of specific artifacts in the TestInMemoryArtifactService.
    This is called when an `assert_artifact_state` block is found in an event spec.
    """
    if not expected_artifact_state_specs:
        return
    agent_name_for_artifacts = (
        "test_namespace"
        if artifact_scope == "namespace"
        else gateway_input_data.get("target_agent_name")
    )
    assert (
        agent_name_for_artifacts
    ), f"Scenario {scenario_id}: could not determine app_name for artifact state assertion"

    for i, spec in enumerate(expected_artifact_state_specs):
        context_path = f"assert_artifact_state[{i}]"
        filename = spec.get("filename")
        filename_regex = spec.get("filename_matches_regex")

        if filename and filename_regex:
            raise AssertionError(
                f"Scenario {scenario_id}: '{context_path}' - Cannot specify both 'filename' and 'filename_matches_regex'."
            )
        if not filename and not filename_regex:
            raise AssertionError(
                f"Scenario {scenario_id}: '{context_path}' - Must specify either 'filename' or 'filename_matches_regex'."
            )
        user_id = spec.get("user_id") or gateway_input_data.get("user_identity")
        session_id = spec.get("session_id") or gateway_input_data.get(
            "external_context", {}
        ).get("a2a_session_id")

        assert (
            user_id
        ), f"Scenario {scenario_id}: '{context_path}' - could not determine user_id."
        assert (
            session_id
        ), f"Scenario {scenario_id}: '{context_path}' - could not determine session_id."

        version_to_check = spec.get("version")
        assert (
            version_to_check is not None
        ), f"Scenario {scenario_id}: '{context_path}' must specify 'version'."
        filename_for_lookup = filename
        if spec.get("namespace") == "user":
            filename_for_lookup = f"user:{filename}"
        elif filename_regex:
            # List all keys from the artifact service
            all_keys_raw = await test_artifact_service_instance.list_artifact_keys(
                app_name=agent_name_for_artifacts,
                user_id=user_id,
                session_id=session_id,
            )
            # Explicitly filter out metadata files to prevent incorrect matches
            all_keys_filtered = [
                k for k in all_keys_raw if not k.endswith(".metadata.json")
            ]

            matching_filenames = [
                k for k in all_keys_filtered if re.match(filename_regex, k)
            ]

            assert (
                len(matching_filenames) == 1
            ), f"Scenario {scenario_id}: '{context_path}' - Expected exactly one artifact matching regex '{filename_regex}', but found {len(matching_filenames)}: {matching_filenames}. All non-metadata keys checked: {all_keys_filtered}"
            filename_for_lookup = matching_filenames[0]
        details = await test_artifact_service_instance.get_artifact_details(
            app_name=agent_name_for_artifacts,
            user_id=user_id,
            session_id=session_id,
            filename=filename_for_lookup,
            version=version_to_check,
        )
        assert (
            details is not None
        ), f"Scenario {scenario_id}: Artifact '{filename_for_lookup}' version {version_to_check} not found for user '{user_id}' in session '{session_id}'."

        content_bytes, mime_type = details
        has_text_spec = "expected_content_text" in spec
        has_bytes_spec = "expected_content_bytes_base64" in spec

        if has_text_spec and has_bytes_spec:
            raise AssertionError(
                f"Scenario {scenario_id}: '{context_path}' - Cannot specify both 'expected_content_text' and 'expected_content_bytes_base64'."
            )

        if has_text_spec:
            expected_text = spec["expected_content_text"]
            try:
                actual_text = content_bytes.decode("utf-8")
                assert (
                    actual_text == expected_text
                ), f"Scenario {scenario_id}: '{context_path}' - Text content mismatch for '{filename_for_lookup}'. Expected '{expected_text}', Got '{actual_text}'"
            except UnicodeDecodeError:
                raise AssertionError(
                    f"Scenario {scenario_id}: '{context_path}' - Artifact '{filename_for_lookup}' content could not be decoded as UTF-8 for text comparison."
                )

        if has_bytes_spec:
            expected_bytes = base64.b64decode(spec["expected_content_bytes_base64"])
            assert (
                content_bytes == expected_bytes
            ), f"Scenario {scenario_id}: '{context_path}' - Byte content mismatch for '{filename_for_lookup}'."
        if (
            "expected_metadata_contains" in spec
            or "assert_metadata_schema_key_count" in spec
        ):
            metadata_filename = f"{filename_for_lookup}.metadata.json"
            metadata_details = (
                await test_artifact_service_instance.get_artifact_details(
                    app_name=agent_name_for_artifacts,
                    user_id=user_id,
                    session_id=session_id,
                    filename=metadata_filename,
                    version=version_to_check,
                )
            )
            assert (
                metadata_details
            ), f"Scenario {scenario_id}: Metadata for artifact '{filename_for_lookup}' v{version_to_check} not found."

            metadata_bytes, _ = metadata_details
            try:
                actual_metadata = json.loads(metadata_bytes.decode("utf-8"))
                if "expected_metadata_contains" in spec:
                    _assert_dict_subset(
                        expected_subset=spec["expected_metadata_contains"],
                        actual_superset=actual_metadata,
                        scenario_id=scenario_id,
                        event_index=-1,
                        context_path=f"{context_path}.metadata",
                    )
                if "assert_metadata_schema_key_count" in spec:
                    expected_key_count = spec["assert_metadata_schema_key_count"]
                    schema = actual_metadata.get("schema", {})
                    structure = schema.get("structure", {})
                    assert isinstance(
                        structure, dict
                    ), f"Scenario {scenario_id}: '{context_path}' - Metadata schema 'structure' is not a dictionary."
                    actual_key_count = len(structure)

                    assert (
                        actual_key_count == expected_key_count
                    ), f"Scenario {scenario_id}: '{context_path}' - Metadata schema key count mismatch. Expected {expected_key_count}, Got {actual_key_count}"

            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                raise AssertionError(
                    f"Scenario {scenario_id}: '{context_path}' - Failed to decode metadata for '{filename_for_lookup}': {e}"
                )


async def _assert_generated_artifacts(
    expected_artifacts_spec_list: List[Dict[str, Any]],
    test_artifact_service_instance: TestInMemoryArtifactService,
    task_id: str,
    gateway_input_data: Dict[str, Any],
    test_gateway_app_instance: TestGatewayComponent,
    scenario_id: str,
    artifact_scope: str,
) -> None:
    """
    Asserts that artifacts generated during the test match the expected specifications.
    User ID and Session ID are now sourced directly from gateway_input_data, as the
    gateway's task context is correctly cleared after task completion (which occurs
    before this function is called in the test sequence). This ensures artifact assertions
    can still proceed using reliable identifiers.
    """
    if not expected_artifacts_spec_list:
        return

    user_id_for_artifacts = gateway_input_data.get("user_identity")
    agent_name_for_artifacts = (
        "test_namespace"
        if artifact_scope == "namespace"
        else gateway_input_data.get("target_agent_name")
    )

    external_context_from_input = gateway_input_data.get("external_context", {})
    session_id_for_artifacts = external_context_from_input.get("a2a_session_id")

    assert (
        agent_name_for_artifacts
    ), f"Scenario {scenario_id}: could not determine app_name for _assert_generated_artifacts"
    assert (
        user_id_for_artifacts
    ), f"Scenario {scenario_id}: user_identity missing in gateway_input for _assert_generated_artifacts"
    assert (
        session_id_for_artifacts
    ), f"Scenario {scenario_id}: external_context.a2a_session_id missing in gateway_input for _assert_generated_artifacts"

    for i, expected_artifact_spec in enumerate(expected_artifacts_spec_list):
        context_path = f"expected_artifacts[{i}]"
        filename_from_spec = expected_artifact_spec.get("filename")
        filename_regex_from_spec = expected_artifact_spec.get("filename_matches_regex")

        if filename_from_spec and filename_regex_from_spec:
            raise AssertionError(
                f"Scenario {scenario_id}: '{context_path}' - Cannot specify both 'filename' and 'filename_matches_regex'."
            )
        if not filename_from_spec and not filename_regex_from_spec:
            raise AssertionError(
                f"Scenario {scenario_id}: '{context_path}' - Must specify either 'filename' or 'filename_matches_regex'."
            )

        filename_to_process = ""
        if filename_from_spec:
            filename_to_process = filename_from_spec
        elif filename_regex_from_spec:
            all_artifact_keys_in_session = (
                await test_artifact_service_instance.list_artifact_keys(
                    app_name=agent_name_for_artifacts,
                    user_id=user_id_for_artifacts,
                    session_id=session_id_for_artifacts,
                )
            )
            matching_filenames = [
                key
                for key in all_artifact_keys_in_session
                if re.match(filename_regex_from_spec, key)
            ]
            assert len(matching_filenames) == 1, (
                f"Scenario {scenario_id}: '{context_path}' - Expected exactly one artifact matching regex "
                f"'{filename_regex_from_spec}' in session, but found {len(matching_filenames)}: {matching_filenames}. "
                f"All keys in session: {all_artifact_keys_in_session}"
            )
            filename_to_process = matching_filenames[0]
            print(
                f"Scenario {scenario_id}: Matched regex '{filename_regex_from_spec}' to filename '{filename_to_process}' for artifact assertion."
            )

        versions = await test_artifact_service_instance.list_versions(
            app_name=agent_name_for_artifacts,
            user_id=user_id_for_artifacts,
            session_id=session_id_for_artifacts,
            filename=filename_to_process,
        )
        assert (
            versions
        ), f"Scenario {scenario_id}: No versions found for expected artifact '{filename_to_process}' (app: {agent_name_for_artifacts}, user: {user_id_for_artifacts}, session: {session_id_for_artifacts})."
        latest_version = max(versions)
        version_to_check = expected_artifact_spec.get("version", latest_version)
        if version_to_check == "latest":
            version_to_check = latest_version

        details = await test_artifact_service_instance.get_artifact_details(
            app_name=agent_name_for_artifacts,
            user_id=user_id_for_artifacts,
            session_id=session_id_for_artifacts,
            filename=filename_to_process,
            version=version_to_check,
        )
        assert (
            details is not None
        ), f"Scenario {scenario_id}: Artifact '{filename_to_process}' version {version_to_check} not found."

        content_bytes, mime_type = details

        if "mime_type" in expected_artifact_spec:
            assert (
                mime_type == expected_artifact_spec["mime_type"]
            ), f"Scenario {scenario_id}: Artifact '{filename_to_process}' MIME type mismatch. Expected '{expected_artifact_spec['mime_type']}', Got '{mime_type}'"

        if "content_contains" in expected_artifact_spec:
            try:
                content_str = content_bytes.decode("utf-8")
                assert (
                    expected_artifact_spec["content_contains"] in content_str
                ), f"Scenario {scenario_id}: Artifact '{filename_to_process}' content mismatch. Expected to contain '{expected_artifact_spec['content_contains']}', Got '{content_str[:200]}...'"
            except UnicodeDecodeError:
                raise AssertionError(
                    f"Scenario {scenario_id}: Artifact '{filename_to_process}' content could not be decoded as UTF-8 for 'content_contains' check. Consider a bytes-based assertion if it's binary."
                )
        if "text_exact" in expected_artifact_spec:
            try:
                content_str = content_bytes.decode("utf-8")
                assert (
                    expected_artifact_spec["text_exact"] == content_str
                ), f"Scenario {scenario_id}: Artifact '{filename_to_process}' content exact match failed. Expected '{expected_artifact_spec['text_exact']}', Got '{content_str}'"
            except UnicodeDecodeError:
                raise AssertionError(
                    f"Scenario {scenario_id}: Artifact '{filename_to_process}' content could not be decoded as UTF-8 for 'text_exact' check."
                )
        if "content_base64_exact" in expected_artifact_spec:
            actual_base64 = base64.b64encode(content_bytes).decode("utf-8")
            assert (
                expected_artifact_spec["content_base64_exact"] == actual_base64
            ), f"Scenario {scenario_id}: Artifact '{filename_to_process}' base64 content exact match failed."

        if "metadata_contains" in expected_artifact_spec:
            metadata_filename = f"{filename_to_process}.metadata.json"
            metadata_versions = await test_artifact_service_instance.list_versions(
                app_name=agent_name_for_artifacts,
                user_id=user_id_for_artifacts,
                session_id=session_id_for_artifacts,
                filename=metadata_filename,
            )
            assert (
                metadata_versions
            ), f"Scenario {scenario_id}: No versions found for metadata artifact '{metadata_filename}'"
            latest_metadata_version = max(metadata_versions)

            metadata_details = (
                await test_artifact_service_instance.get_artifact_details(
                    app_name=agent_name_for_artifacts,
                    user_id=user_id_for_artifacts,
                    session_id=session_id_for_artifacts,
                    filename=metadata_filename,
                    version=latest_metadata_version,
                )
            )
            assert (
                metadata_details
            ), f"Scenario {scenario_id}: Metadata artifact '{metadata_filename}' version {latest_metadata_version} not found."

            metadata_content_bytes, _ = metadata_details
            try:
                actual_metadata_dict = json.loads(
                    metadata_content_bytes.decode("utf-8")
                )
                _assert_dict_subset(
                    expected_subset=expected_artifact_spec["metadata_contains"],
                    actual_superset=actual_metadata_dict,
                    scenario_id=scenario_id,
                    event_index=-1,
                    context_path=f"Artifact '{filename_to_process}' metadata",
                )
            except json.JSONDecodeError:
                raise AssertionError(
                    f"Scenario {scenario_id}: Metadata for artifact '{filename_to_process}' was not valid JSON."
                )
            except UnicodeDecodeError:
                raise AssertionError(
                    f"Scenario {scenario_id}: Metadata for artifact '{filename_to_process}' could not be decoded as UTF-8."
                )


DECLARATIVE_TEST_DATA_DIR = Path(__file__).parent / "test_data"


def load_declarative_test_cases():
    """
    Loads all declarative test cases from the specified directory.
    """
    test_cases = []
    if not DECLARATIVE_TEST_DATA_DIR.is_dir():
        return []

    for filepath in sorted(DECLARATIVE_TEST_DATA_DIR.glob("**/*.yaml")):
        try:
            with open(filepath, "r") as f:
                data = yaml.safe_load(f)
                if isinstance(data, dict):
                    relative_path = filepath.relative_to(DECLARATIVE_TEST_DATA_DIR)
                    test_id = str(relative_path.with_suffix("")).replace(
                        os.path.sep, "/"
                    )
                    tags = data.get("tags", [])
                    test_cases.append(
                        pytest.param(
                            data,
                            id=test_id,
                            marks=[getattr(pytest.mark, tag) for tag in tags],
                        )
                    )
                else:
                    print(f"Warning: Skipping file with non-dict content: {filepath}")
        except Exception as e:
            print(f"Warning: Could not load or parse test case file {filepath}: {e}")
    return test_cases


def pytest_generate_tests(metafunc):
    """
    Pytest hook to discover and parameterize tests based on declarative files.
    """
    if "declarative_scenario" in metafunc.fixturenames:
        test_cases = load_declarative_test_cases()
        metafunc.parametrize("declarative_scenario", test_cases)


SKIPPED_MERMAID_DIAGRAM_GENERATOR_SCENARIOS = [
    "test_mermaid_autogen_filename",
    "test_mermaid_basic_success",
    "test_mermaid_empty_syntax",
    "test_mermaid_invalid_syntax",
    "test_mermaid_no_extension",
]

SKIPPED_FAILING_EMBED_TESTS = [
    "embed_general_chain_malformed_001",
    "embed_general_malformed_no_close_delimiter_001",
    "embed_ac_template_missing_template_file_001",
]


@pytest.mark.asyncio
async def test_declarative_scenario(
    declarative_scenario: Dict[str, Any],
    test_llm_server: TestLLMServer,
    test_gateway_app_instance: TestGatewayComponent,
    test_artifact_service_instance: TestInMemoryArtifactService,
    a2a_message_validator: A2AMessageValidator,
    mock_gemini_client: None,
    sam_app_under_test: SamAgentApp,
    main_agent_component: SamAgentComponent,
    peer_a_component: SamAgentComponent,
    peer_b_component: SamAgentComponent,
    peer_c_component: SamAgentComponent,
    peer_d_component: SamAgentComponent,
    combined_dynamic_agent_component: SamAgentComponent,
    empty_provider_agent_component: SamAgentComponent,
    docstringless_agent_component: SamAgentComponent,
    mixed_discovery_agent_component: SamAgentComponent,
    complex_signatures_agent_component: SamAgentComponent,
    config_context_agent_component: SamAgentComponent,
    monkeypatch: pytest.MonkeyPatch,
    mcp_server_harness,
    request: pytest.FixtureRequest,
):
    """
    Executes a single declarative test scenario discovered by pytest_generate_tests.
    """
    scenario_id = declarative_scenario.get("test_case_id", "N/A")
    scenario_description = declarative_scenario.get("description", "No description")

    # --- Phase 0: MCP Configuration now handled by mcp_configured_sam_app fixture ---

    if "monkeypatch_spec" in declarative_scenario:
        for patch_spec in declarative_scenario["monkeypatch_spec"]:
            target_str = patch_spec["target"]
            side_effect_type = patch_spec.get("side_effect")

            if side_effect_type == "exception":
                exception_type_str = patch_spec.get("exception_type", "Exception")
                exception_message = patch_spec.get(
                    "exception_message", "Simulated failure"
                )
                exception_class = getattr(builtins, exception_type_str, Exception)

                async def mock_save_fail(*args, **kwargs):
                    raise exception_class(exception_message)

                monkeypatch.setattr(target_str, mock_save_fail)
                print(
                    f"Scenario {scenario_id}: MONKEYPATCH APPLIED to '{target_str}' to raise {exception_type_str}."
                )

    if scenario_id in SKIPPED_FAILING_EMBED_TESTS:
        pytest.skip(f"Skipping failing embed test '{scenario_id}' until fixed.")

    if scenario_id in SKIPPED_MERMAID_DIAGRAM_GENERATOR_SCENARIOS:
        pytest.xfail(
            f"Skipping test '{scenario_id}' because the 'mermaid_diagram_generator' requires Playwright, which is not available in this environment."
        )
    print(f"\nRunning declarative scenario: {scenario_id} - {scenario_description}")

    agent_config_overrides = declarative_scenario.get(
        "test_runner_config_overrides", {}
    ).get("agent_config", {})
    # Default to 'namespace' to match the application's default schema.
    # Tests that require 'app' scope must explicitly set it in their YAML.
    artifact_scope = agent_config_overrides.get("artifact_scope", "namespace")
    print(f"Scenario {scenario_id}: Using artifact_scope: '{artifact_scope}'")

    agent_components = {
        main_agent_component.agent_name: main_agent_component,
        peer_a_component.agent_name: peer_a_component,
        peer_b_component.agent_name: peer_b_component,
        peer_c_component.agent_name: peer_c_component,
        peer_d_component.agent_name: peer_d_component,
        combined_dynamic_agent_component.agent_name: combined_dynamic_agent_component,
        empty_provider_agent_component.agent_name: empty_provider_agent_component,
        docstringless_agent_component.agent_name: docstringless_agent_component,
        mixed_discovery_agent_component.agent_name: mixed_discovery_agent_component,
        complex_signatures_agent_component.agent_name: complex_signatures_agent_component,
        config_context_agent_component.agent_name: config_context_agent_component,
    }

    # --- Phase 1: Setup Environment (including config overrides) ---
    if "test_runner_config_overrides" in declarative_scenario:
        if agent_config_overrides:
            # Get the component instance to patch
            sam_agent_component = None
            if (
                sam_app_under_test.flows
                and sam_app_under_test.flows[0].component_groups
            ):
                for group in sam_app_under_test.flows[0].component_groups:
                    for comp_wrapper in group:
                        actual_comp = getattr(comp_wrapper, "component", comp_wrapper)
                        if isinstance(actual_comp, SamAgentComponent):
                            sam_agent_component = actual_comp
                            break
                    if sam_agent_component:
                        break

            if not sam_agent_component:
                pytest.fail(
                    f"Scenario {scenario_id}: Could not find SamAgentComponent in sam_app_under_test to apply config overrides."
                )

            original_get_config = sam_agent_component.get_config

            def _patched_get_config(key: str, default: Any = None) -> Any:
                if key in agent_config_overrides:
                    override_value = agent_config_overrides[key]
                    print(
                        f"Scenario {scenario_id}: MONKEYPATCH OVERRIDE for config key '{key}'. Returning '{override_value}'."
                    )
                    return override_value
                return original_get_config(key, default)

            monkeypatch.setattr(sam_agent_component, "get_config", _patched_get_config)
            print(
                f"Scenario {scenario_id}: Applied config overrides: {agent_config_overrides}"
            )

    await _setup_scenario_environment(
        declarative_scenario,
        test_llm_server,
        test_artifact_service_instance,
        scenario_id,
        artifact_scope,
    )

    skip_intermediate_events = declarative_scenario.get(
        "skip_intermediate_events", False
    )

    gateway_input_data = declarative_scenario.get("gateway_input")
    if not gateway_input_data:
        pytest.fail(f"Scenario {scenario_id}: 'gateway_input' is missing.")

    overall_timeout = declarative_scenario.get(
        "expected_completion_timeout_seconds", 10000.0
    )

    (
        task_id,
        all_captured_events,
        aggregated_stream_text_for_final_assert,
        text_from_terminal_event_for_final_assert,
    ) = await _execute_gateway_and_collect_events(
        test_gateway_app_instance, gateway_input_data, overall_timeout, scenario_id
    )
    print(
        f"Scenario {scenario_id}: Task {task_id} execution and event collection complete."
    )

    try:
        actual_events_list = all_captured_events
        captured_llm_requests = test_llm_server.get_captured_requests()
        expected_llm_interactions = declarative_scenario.get("llm_interactions", [])
        await _assert_llm_interactions(
            expected_llm_interactions,
            captured_llm_requests,
            scenario_id,
            test_artifact_service_instance,
            gateway_input_data,
            agent_components,
            artifact_scope,
        )
        expected_gateway_outputs_spec_list = declarative_scenario.get(
            "expected_gateway_output", []
        )
        await _assert_gateway_event_sequence(
            expected_event_specs_list=expected_gateway_outputs_spec_list,
            actual_events_list=actual_events_list,
            scenario_id=scenario_id,
            skip_intermediate_events=skip_intermediate_events,
            expected_llm_interactions=expected_llm_interactions,
            captured_llm_requests=captured_llm_requests,
            aggregated_stream_text_for_final_assert=aggregated_stream_text_for_final_assert,
            text_from_terminal_event_for_final_assert=text_from_terminal_event_for_final_assert,
            test_artifact_service_instance=test_artifact_service_instance,
            gateway_input_data=gateway_input_data,
            agent_components=agent_components,
            artifact_scope=artifact_scope,
        )
        expected_artifacts_spec_list = declarative_scenario.get(
            "expected_artifacts", []
        )
        await _assert_generated_artifacts(
            expected_artifacts_spec_list=expected_artifacts_spec_list,
            test_artifact_service_instance=test_artifact_service_instance,
            task_id=task_id,
            gateway_input_data=gateway_input_data,
            test_gateway_app_instance=test_gateway_app_instance,
            scenario_id=scenario_id,
            artifact_scope=artifact_scope,
        )

        print(f"Scenario {scenario_id}: Completed.")
    except Exception as e:
        print(
            f"\n--- Test failed for scenario: {scenario_id}. Printing event history: ---"
        )
        event_payloads = [
            event.model_dump(exclude_none=True) for event in all_captured_events
        ]
        pretty_print_event_history(event_payloads)
        raise e


def _extract_text_from_generic_update(event: TaskStatusUpdateEvent) -> str:
    if event.status and event.status.message:
        return get_message_text(event.status.message, delimiter="")
    return ""


def _get_actual_event_purpose(
    actual_event: Union[
        TaskStatusUpdateEvent, TaskArtifactUpdateEvent, Task, JSONRPCError
    ],
) -> Optional[str]:
    """Determines the 'purpose' of a TaskStatusUpdateEvent for matching against expected_spec."""
    if isinstance(actual_event, TaskStatusUpdateEvent):
        if actual_event.status and actual_event.status.message:
            data_payloads = get_data_parts(actual_event.status.message.parts)
            for data in data_payloads:
                # New, preferred way of signaling
                signal_type = data.get("type")
                if signal_type in [
                    "tool_invocation_start",
                    "llm_invocation",
                    "llm_response",
                    "agent_progress_update",
                    "artifact_creation_progress",
                ]:
                    return signal_type
                # Legacy check for older signals
                if (
                    data.get("a2a_signal_type") == "agent_status_message"
                    or data.get("type") == "agent_progress"
                    or data.get("type") == "agent_status"
                ):
                    return "agent_progress_update"

        # Legacy check for metadata-based signals
        if (
            actual_event.status
            and actual_event.status.message
            and actual_event.status.message.metadata
        ):
            meta_type = actual_event.status.message.metadata.get("type")
            if meta_type in ["tool_invocation_start", "llm_invocation", "llm_response"]:
                return meta_type

        return "generic_text_update"
    return None


def _match_event(actual_event: Any, expected_spec: Dict[str, Any]) -> bool:
    """
    Checks if an actual_event broadly matches an expected_spec based on 'type'
    and 'event_purpose' (if applicable).
    """
    expected_type_str = expected_spec.get("type")
    actual_type_name = type(actual_event).__name__

    type_matches = False
    if expected_type_str == "status_update" and isinstance(
        actual_event, TaskStatusUpdateEvent
    ):
        type_matches = True
    elif expected_type_str == "artifact_update" and isinstance(
        actual_event, TaskArtifactUpdateEvent
    ):
        type_matches = True
    elif expected_type_str == "final_response" and isinstance(actual_event, Task):
        type_matches = True
    elif expected_type_str == "error" and isinstance(actual_event, JSONRPCError):
        type_matches = True

    if not type_matches:
        return False
    if (
        isinstance(actual_event, TaskStatusUpdateEvent)
        and "event_purpose" in expected_spec
    ):
        actual_purpose = _get_actual_event_purpose(actual_event)
        expected_purpose = expected_spec["event_purpose"]
        if actual_purpose != expected_purpose:
            return False

    return True


async def _assert_event_details(
    actual_event: Any,
    expected_spec: Dict[str, Any],
    scenario_id: str,
    event_index: int,
    llm_interactions: List[Dict[str, Any]],
    actual_llm_requests: List[Any],
    aggregated_stream_text_for_final_assert: Optional[str],
    text_from_terminal_event_for_final_assert: Optional[str],
    override_text_for_assertion: Optional[str] = None,
    test_artifact_service_instance: TestInMemoryArtifactService = None,
    gateway_input_data: Dict[str, Any] = None,
    agent_components: Dict[str, SamAgentComponent] = None,
    artifact_scope: str = "namespace",
):
    """
    Performs detailed assertions on a matched event.
    The `event_index` here refers to the index in the `expected_gateway_outputs_spec_list`.
    """
    print(
        f"Scenario {scenario_id}: Asserting details for event {event_index + 1} (Actual type: {type(actual_event).__name__}, Expected spec type: {expected_spec.get('type')})"
    )

    if isinstance(actual_event, TaskStatusUpdateEvent):
        actual_event_purpose = _get_actual_event_purpose(actual_event)

        text_to_assert_against = ""
        if actual_event_purpose == "generic_text_update":
            is_aggregated_assertion = expected_spec.get(
                "assert_aggregated_stream_content", False
            )
            if is_aggregated_assertion:
                if override_text_for_assertion is not None:
                    text_to_assert_against = override_text_for_assertion
                    print(
                        f"Scenario {scenario_id}: Event {event_index+1} [AGGREGATED ASSERTION] Using override text: '{text_to_assert_against}'"
                    )
                else:
                    pytest.fail(
                        f"Scenario {scenario_id}: Event {event_index+1} - Internal Test Runner Error: Expected aggregated content but override_text_for_assertion is None."
                    )
            else:
                text_to_assert_against = _extract_text_from_generic_update(actual_event)
                print(
                    f"Scenario {scenario_id}: Event {event_index+1} [SINGLE EVENT ASSERTION] Using event text: '{text_to_assert_against}'"
                )
        elif actual_event_purpose == "agent_progress_update":
            if actual_event.status and actual_event.status.message:
                data_parts = get_data_parts(actual_event.status.message.parts)
                for data in data_parts:
                    if (
                        data.get("a2a_signal_type") == "agent_status_message"
                        or data.get("type") == "agent_status"
                    ):
                        text_to_assert_against = data.get("text", "")
                        break

        if "content_parts" in expected_spec and (
            actual_event_purpose == "agent_progress_update"
            or actual_event_purpose == "generic_text_update"
        ):
            for part_spec in expected_spec["content_parts"]:
                if part_spec["type"] == "text":
                    _assert_text_content(
                        text_to_assert_against,
                        part_spec,
                        scenario_id,
                        event_index=event_index,
                    )
                elif part_spec["type"] == "data":
                    data_parts = get_data_parts(actual_event.status.message.parts)
                    assert (
                        data_parts
                    ), f"Scenario {scenario_id}: Event {event_index+1} - Expected a DataPart but none was found."
                    actual_data_part_content = data_parts[0]

                    if "data_contains" in part_spec:
                        _assert_dict_subset(
                            expected_subset=part_spec["data_contains"],
                            actual_superset=actual_data_part_content,
                            scenario_id=scenario_id,
                            event_index=event_index,
                            context_path="DataPart content",
                        )

        if actual_event_purpose == "tool_invocation_start":
            data_parts = get_data_parts(actual_event.status.message.parts)
            assert (
                data_parts
            ), f"Scenario {scenario_id}: Event {event_index+1} - Expected a DataPart for tool_invocation_start event, but none was found."
            tool_data = data_parts[0]

            if "expected_tool_name" in expected_spec:
                assert (
                    tool_data.get("tool_name") == expected_spec["expected_tool_name"]
                ), f"Scenario {scenario_id}: Event {event_index+1} - Tool name mismatch. Expected '{expected_spec['expected_tool_name']}', Got '{tool_data.get('tool_name')}'"
            if "expected_tool_args_contain" in expected_spec:
                expected_args_subset = expected_spec["expected_tool_args_contain"]
                actual_args = tool_data.get("tool_args", {})
                if isinstance(actual_args, str):
                    try:
                        actual_args = json.loads(actual_args)
                    except json.JSONDecodeError:
                        pytest.fail(
                            f"Scenario {scenario_id}: Event {event_index+1} - Tool args were a string but not valid JSON: {actual_args}"
                        )

                assert isinstance(
                    actual_args, dict
                ), f"Scenario {scenario_id}: Event {event_index+1} - Tool args is not a dict: {actual_args}"
                for k, v_expected in expected_args_subset.items():
                    assert (
                        k in actual_args
                    ), f"Scenario {scenario_id}: Event {event_index+1} - Expected key '{k}' not in tool_args {actual_args}"
                    assert (
                        actual_args[k] == v_expected
                    ), f"Scenario {scenario_id}: Event {event_index+1} - Value for tool_arg '{k}' mismatch. Expected '{v_expected}', Got '{actual_args[k]}'"

        if actual_event_purpose in ["llm_invocation", "llm_response"]:
            data_parts = get_data_parts(actual_event.status.message.parts)
            assert (
                data_parts
            ), f"Scenario {scenario_id}: Event {event_index+1} - Expected a DataPart for {actual_event_purpose} event, but none was found."
            llm_data = data_parts[0]

            if "expected_llm_data_contains" in expected_spec:
                expected_subset = expected_spec["expected_llm_data_contains"]

                data_to_check = llm_data
                if actual_event_purpose == "llm_invocation":
                    data_to_check = llm_data.get("request", {})
                elif actual_event_purpose == "llm_response":
                    data_to_check = llm_data.get("data", {})

                for k, v_expected in expected_subset.items():
                    assert (
                        k in data_to_check
                    ), f"Scenario {scenario_id}: Event {event_index+1} - Expected key '{k}' not in LLM data {data_to_check}"
                    if (
                        k == "model"
                        and isinstance(v_expected, str)
                        and v_expected.endswith("...")
                    ):
                        assert data_to_check[k].startswith(
                            v_expected[:-3]
                        ), f"Scenario {scenario_id}: Event {event_index+1} - Value for LLM data key '{k}' start mismatch. Expected to start with '{v_expected[:-3]}', Got '{data_to_check[k]}'"
                    else:
                        if isinstance(v_expected, dict) and isinstance(
                            data_to_check.get(k), dict
                        ):
                            _assert_dict_subset(
                                expected_subset=v_expected,
                                actual_superset=data_to_check.get(k, {}),
                                scenario_id=scenario_id,
                                event_index=event_index,
                                context_path=f"LLM data key '{k}'",
                            )
                        elif isinstance(v_expected, list) and isinstance(
                            data_to_check.get(k), list
                        ):
                            _assert_list_subset(
                                expected_list_subset=v_expected,
                                actual_list_superset=data_to_check.get(k, []),
                                scenario_id=scenario_id,
                                event_index=event_index,
                                context_path=f"LLM data key '{k}'",
                            )
                        else:
                            assert (
                                data_to_check.get(k) == v_expected
                            ), f"Scenario {scenario_id}: Event {event_index+1} - Value for LLM data key '{k}' mismatch. Expected '{v_expected}', Got '{data_to_check.get(k)}'"

        if "final_flag" in expected_spec:
            assert (
                actual_event.final == expected_spec["final_flag"]
            ), f"Scenario {scenario_id}: Event {event_index+1} - Final flag mismatch. Expected {expected_spec['final_flag']}, Got {actual_event.final}"

    elif isinstance(actual_event, TaskArtifactUpdateEvent):
        if "expected_artifact_name_contains" in expected_spec:
            assert (
                expected_spec["expected_artifact_name_contains"]
                in actual_event.artifact.name
            ), f"Scenario {scenario_id}: Event {event_index+1} - Artifact name mismatch. Expected to contain '{expected_spec['expected_artifact_name_contains']}', Got '{actual_event.artifact.name}'"

    elif isinstance(actual_event, Task):
        if "task_state" in expected_spec:
            assert (
                actual_event.status
                and actual_event.status.state.value == expected_spec["task_state"]
            ), f"Scenario {scenario_id}: Event {event_index+1} - Task state mismatch. Expected '{expected_spec['task_state']}', Got '{actual_event.status.state.value if actual_event.status else 'None'}'"

        if "expected_produced_artifacts" in expected_spec:
            expected_artifacts = expected_spec["expected_produced_artifacts"]
            actual_artifacts = actual_event.metadata.get("produced_artifacts", [])
            # Convert to set of tuples to ignore order and allow comparison
            expected_set = {tuple(sorted(d.items())) for d in expected_artifacts}
            actual_set = {tuple(sorted(d.items())) for d in actual_artifacts}
            assert (
                expected_set == actual_set
            ), f"Scenario {scenario_id}: Event {event_index+1} - 'produced_artifacts' mismatch. Expected {expected_set}, Got {actual_set}"

        text_for_final_assertion = ""
        if expected_spec.get("assert_content_against_stream", False):
            text_for_final_assertion = (
                aggregated_stream_text_for_final_assert
                if aggregated_stream_text_for_final_assert is not None
                else ""
            )
            print(
                f"Scenario {scenario_id}: Event {event_index+1} (Final Response) - Asserting content_parts against AGGREGATED STREAM TEXT."
            )
        else:
            text_for_final_assertion = (
                text_from_terminal_event_for_final_assert
                if text_from_terminal_event_for_final_assert is not None
                else ""
            )
            print(
                f"Scenario {scenario_id}: Event {event_index+1} (Final Response) - Asserting content_parts against TEXT FROM TERMINAL EVENT."
            )

        if "content_parts" in expected_spec:
            for part_spec in expected_spec["content_parts"]:
                if part_spec["type"] == "text":
                    _assert_text_content(
                        text_for_final_assertion,
                        part_spec,
                        scenario_id,
                        event_index=event_index,
                    )

    elif isinstance(actual_event, JSONRPCError):
        if "error_code" in expected_spec:
            assert (
                actual_event.code == expected_spec["error_code"]
            ), f"Scenario {scenario_id}: Event {event_index+1} - Error code mismatch. Expected {expected_spec['error_code']}, Got {actual_event.code}"
        if "error_message_contains" in expected_spec:
            assert (
                expected_spec["error_message_contains"] in actual_event.message
            ), f"Scenario {scenario_id}: Event {event_index+1} - Error message content mismatch. Expected to contain '{expected_spec['error_message_contains']}', Got '{actual_event.message}'"

    if "assert_artifact_state" in expected_spec:
        assert (
            test_artifact_service_instance is not None
            and gateway_input_data is not None
        ), "Internal Test Runner Error: Fixtures for artifact state assertion not passed down."

        await _assert_artifact_state(
            expected_artifact_state_specs=expected_spec["assert_artifact_state"],
            test_artifact_service_instance=test_artifact_service_instance,
            gateway_input_data=gateway_input_data,
            scenario_id=scenario_id,
            artifact_scope=artifact_scope,
        )


def _assert_dict_subset(
    expected_subset: Dict,
    actual_superset: Dict,
    scenario_id: str,
    event_index: int,
    context_path: str,
):
    for expected_key_in_yaml, expected_value in expected_subset.items():
        actual_key_to_check = expected_key_in_yaml
        is_regex_match = False
        regex_suffix = "_matches_regex"

        is_contains_match = False
        if expected_key_in_yaml.endswith(regex_suffix):
            actual_key_to_check = expected_key_in_yaml[: -len(regex_suffix)]
            is_regex_match = True
        elif expected_key_in_yaml.endswith("_contains"):
            actual_key_to_check = expected_key_in_yaml[: -len("_contains")]
            is_contains_match = True

        current_path = f"{context_path}.{actual_key_to_check}"

        assert (
            actual_key_to_check in actual_superset
        ), f"Scenario {scenario_id}: Event {event_index+1} - Expected key '{current_path}' (derived from YAML key '{expected_key_in_yaml}') not in actual data: {actual_superset.keys()}"

        actual_value = actual_superset[actual_key_to_check]

        if is_regex_match:
            assert isinstance(
                actual_value, str
            ), f"Scenario {scenario_id}: Event {event_index+1} - Regex match for key '{current_path}' (from YAML key '{expected_key_in_yaml}') expected a string value in actual data, but got {type(actual_value)} ('{actual_value}')."
            # Using re.fullmatch to ensure the entire string matches the pattern
            assert re.fullmatch(
                str(expected_value), actual_value
            ), f"Scenario {scenario_id}: Event {event_index+1} - Regex mismatch for key '{current_path}' (from YAML key '{expected_key_in_yaml}'). Pattern '{expected_value}' did not fully match actual value '{actual_value}'."
        elif is_contains_match:
            assert isinstance(
                actual_value, str
            ), f"Scenario {scenario_id}: Event {event_index+1} - Contains match for key '{current_path}' (from YAML key '{expected_key_in_yaml}') expected a string value in actual data, but got {type(actual_value)} ('{actual_value}')."
            expected_substrings = (
                expected_value if isinstance(expected_value, list) else [expected_value]
            )
            for item_to_contain in expected_substrings:
                assert str(item_to_contain) in actual_value, (
                    f"Scenario {scenario_id}: Event {event_index+1} - Contains mismatch for key '{current_path}'. "
                    f"Expected to contain '{item_to_contain}', but it was not found in actual value '{actual_value}'."
                )
        # Check for special assertion directives in the expected_value
        elif (
            isinstance(expected_value, dict)
            and len(expected_value) == 1
            and "_regex" in expected_value
        ):
            regex_pattern = expected_value["_regex"]
            assert isinstance(
                actual_value, str
            ), f"Scenario {scenario_id}: Event {event_index+1} - Key '{current_path}' - Expected a string value for regex match, but got type {type(actual_value)}."
            assert re.search(
                regex_pattern, actual_value
            ), f"Scenario {scenario_id}: Event {event_index+1} - Key '{current_path}' - Regex mismatch. Pattern '{regex_pattern}' not found in '{actual_value}'"

        # Default recursive/equality checks
        elif isinstance(expected_value, dict) and isinstance(actual_value, dict):
            _assert_dict_subset(
                expected_value, actual_value, scenario_id, event_index, current_path
            )
        elif isinstance(expected_value, list) and isinstance(actual_value, list):
            _assert_list_subset(
                expected_value, actual_value, scenario_id, event_index, current_path
            )
        else:
            if isinstance(actual_value, str) and isinstance(expected_value, str):
                normalized_actual_value = _normalize_newlines(actual_value)
                normalized_expected_value = _normalize_newlines(expected_value)
                assert (
                    normalized_actual_value == normalized_expected_value
                ), f"Scenario {scenario_id}: Event {event_index+1} - Value mismatch for key '{current_path}'. Expected '{normalized_expected_value}', Got '{normalized_actual_value}'"
            else:
                assert (
                    actual_value == expected_value
                ), f"Scenario {scenario_id}: Event {event_index+1} - Value mismatch for key '{current_path}'. Expected '{expected_value}' (type: {type(expected_value)}), Got '{actual_value}' (type: {type(actual_value)})"


def _assert_list_subset(
    expected_list_subset: List,
    actual_list_superset: List,
    scenario_id: str,
    event_index: int,
    context_path: str,
):
    if len(expected_list_subset) > len(actual_list_superset):
        pytest.fail(
            f"Scenario {scenario_id}: Event {event_index+1} - List at '{context_path}' - expected list has more items ({len(expected_list_subset)}) than actual ({len(actual_list_superset)})."
        )

    for i, expected_item in enumerate(expected_list_subset):
        current_item_path = f"{context_path}[{i}]"
        if isinstance(expected_item, dict) and isinstance(
            actual_list_superset[i], dict
        ):
            _assert_dict_subset(
                expected_item,
                actual_list_superset[i],
                scenario_id,
                event_index,
                current_item_path,
            )
        elif isinstance(expected_item, list) and isinstance(
            actual_list_superset[i], list
        ):
            _assert_list_subset(
                expected_item,
                actual_list_superset[i],
                scenario_id,
                event_index,
                current_item_path,
            )
        else:
            assert (
                expected_item == actual_list_superset[i]
            ), f"Scenario {scenario_id}: Event {event_index+1} - Item mismatch at '{current_item_path}'. Expected '{expected_item}', Got '{actual_list_superset[i]}'"


def _normalize_newlines(text: str) -> str:
    """Converts all CRLF and CR to LF."""
    if text is None:
        return None
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _assert_text_content(
    actual_text: str, expected_part_spec: Dict, scenario_id: str, event_index: int
):
    """Helper to assert text content based on spec (contains, regex, exact, not_contains)."""
    normalized_actual_text = _normalize_newlines(actual_text)

    if "text_contains" in expected_part_spec:
        expected_substring_template = expected_part_spec["text_contains"]
        final_resolved_substring = ""
        last_end = 0
        for eval_match in re.finditer(
            r"eval_math:\[(.+?)\]", expected_substring_template
        ):
            expression_to_eval = eval_match.group(1).strip()
            final_resolved_substring += expected_substring_template[
                last_end : eval_match.start()
            ]
            try:
                aeval = Interpreter()
                aeval.symtable.update(TEST_RUNNER_MATH_SYMBOLS)
                evaluated_value = aeval.eval(expression_to_eval)
                final_resolved_substring += str(evaluated_value)
            except Exception as e:
                raise AssertionError(
                    f"Scenario {scenario_id}: Event {event_index+1} - Failed to dynamically evaluate math expression '{expression_to_eval}' in test: {e}"
                )
            last_end = eval_match.end()
        final_resolved_substring += expected_substring_template[last_end:]

        normalized_expected_substring = _normalize_newlines(final_resolved_substring)

        assert (
            normalized_expected_substring in normalized_actual_text
        ), f"Scenario {scenario_id}: Event {event_index+1} - Content mismatch. Expected to contain '{normalized_expected_substring}', Got '{normalized_actual_text}'"

    if "text_matches_regex" in expected_part_spec:
        regex_pattern = expected_part_spec["text_matches_regex"]
        assert re.search(
            regex_pattern, actual_text
        ), f"Scenario {scenario_id}: Event {event_index+1} - Content regex mismatch. Pattern '{regex_pattern}' not found in '{actual_text}'"

    if "text_exact" in expected_part_spec:
        normalized_expected_exact = _normalize_newlines(
            expected_part_spec["text_exact"]
        )
        assert (
            normalized_expected_exact == normalized_actual_text
        ), f"Scenario {scenario_id}: Event {event_index+1} - Content exact match failed. Expected '{normalized_expected_exact}', Got '{normalized_actual_text}'"

    if "text_not_contains" in expected_part_spec:
        unexpected_substring_template = expected_part_spec["text_not_contains"]
        final_resolved_unexpected_substring = ""
        last_end_not = 0
        for eval_match_not in re.finditer(
            r"eval_math:\[(.+?)\]", unexpected_substring_template
        ):
            expression_to_eval_not = eval_match_not.group(1).strip()
            final_resolved_unexpected_substring += unexpected_substring_template[
                last_end_not : eval_match_not.start()
            ]
            try:
                aeval_not = Interpreter()
                aeval_not.symtable.update(TEST_RUNNER_MATH_SYMBOLS)
                evaluated_value_not = aeval_not.eval(expression_to_eval_not)
                final_resolved_unexpected_substring += str(evaluated_value_not)
            except Exception as e_not:
                raise AssertionError(
                    f"Scenario {scenario_id}: Event {event_index+1} - Failed to dynamically evaluate math expression '{expression_to_eval_not}' in text_not_contains: {e_not}"
                )
            last_end_not = eval_match_not.end()
        final_resolved_unexpected_substring += unexpected_substring_template[
            last_end_not:
        ]

        normalized_unexpected_substring = _normalize_newlines(
            final_resolved_unexpected_substring
        )
        assert (
            normalized_unexpected_substring not in normalized_actual_text
        ), f"Scenario {scenario_id}: Event {event_index+1} - Content mismatch. Expected NOT to contain '{normalized_unexpected_substring}', Got '{normalized_actual_text}'"
