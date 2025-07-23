import pytest
import yaml
import base64
import json
from pathlib import Path

from typing import Any, Dict, List

from tests.integration.infrastructure.dev_broker_client.client import TestDataPlaneClient
from tests.integration.infrastructure.llm_server.server import TestLLMServer
from tests.integration.infrastructure.artifact_service.service import (
    TestInMemoryArtifactService,
)
from solace_ai_connector.common.message import Message as SolaceMessage
from google.genai import types as adk_types


def find_test_files() -> List[Path]:
    """Finds all YAML test files in the 'test_data' subdirectory."""
    test_dir = Path(__file__).parent / "test_data"
    if not test_dir.is_dir():
        return []
    return list(test_dir.rglob("*.yaml"))


async def setup_artifacts(
    artifact_service: TestInMemoryArtifactService,
    setup_config: List[Dict[str, Any]],
):
    """Helper function to set up initial artifacts for a test case."""
    if not setup_config:
        return

    for artifact_def in setup_config:
        content_bytes = b""
        if "content_base64" in artifact_def:
            content_bytes = base64.b64decode(artifact_def["content_base64"])
        elif "content" in artifact_def:
            content_bytes = str(artifact_def["content"]).encode("utf-8")

        part = adk_types.Part(
            inline_data=adk_types.Blob(
                mime_type=artifact_def.get("mime_type", "text/plain"),
                data=content_bytes,
            )
        )
        await artifact_service.save_artifact(
            app_name=artifact_def["app_name"],
            user_id=artifact_def["user_id"],
            session_id=artifact_def["session_id"],
            filename=artifact_def["filename"],
            artifact=part,
        )


async def assert_artifact_state(
    artifact_service: TestInMemoryArtifactService,
    assert_config: List[Dict[str, Any]],
):
    """Helper function to assert the final state of artifacts."""
    if not assert_config:
        return

    for artifact_check in assert_config:
        session_id = artifact_check["session_id"]
        user_id = artifact_check["user_id"]
        filename = artifact_check["filename"]
        version = artifact_check.get("version", 0)
        app_name = artifact_check.get("app_name", "TestEMGateway_01")

        if session_id == "ANY":
            all_artifacts = await artifact_service.get_raw_store()
            found_artifact = None
            for app_data in all_artifacts.values():
                if user_id in app_data:
                    for sess_id, session_data in app_data[user_id].items():
                        if filename in session_data and version in session_data[filename]:
                            found_artifact = session_data[filename][version]
                            break
                    if found_artifact:
                        break

            assert (
                found_artifact is not None
            ), f"Artifact '{filename}' v{version} not found for user '{user_id}' in any session."
            actual_content_bytes, actual_mime_type = found_artifact
        else:
            details = await artifact_service.get_artifact_details(
                app_name=app_name,
                user_id=user_id,
                session_id=session_id,
                filename=filename,
                version=version,
            )
            assert (
                details is not None
            ), f"Artifact '{filename}' v{version} not found for session '{session_id}'."
            actual_content_bytes, actual_mime_type = details

        if "expected_content_bytes_base64" in artifact_check:
            expected_bytes = base64.b64decode(
                artifact_check["expected_content_bytes_base64"]
            )
            assert actual_content_bytes == expected_bytes

        if "expected_content_contains" in artifact_check:
            assert (
                artifact_check["expected_content_contains"]
                in actual_content_bytes.decode("utf-8")
            )

        if "expected_metadata_contains" in artifact_check:
            if "mime_type" in artifact_check["expected_metadata_contains"]:
                assert (
                    actual_mime_type
                    == artifact_check["expected_metadata_contains"]["mime_type"]
                )


@pytest.mark.asyncio
@pytest.mark.parametrize("test_file_path", find_test_files())
async def test_em_gateway_declarative_scenario(
    test_file_path: Path,
    test_data_plane_client: TestDataPlaneClient,
    test_llm_server: TestLLMServer,
    test_artifact_service_instance: TestInMemoryArtifactService,
):
    """
    Runs a declarative test case for the Event Mesh Gateway by:
    1. Reading a YAML test case file.
    2. Setting up mocks (LLM) and initial state (artifacts).
    3. Publishing an input message to the dev_mode broker.
    4. Capturing and validating all expected output messages from the broker.
    5. Asserting the final state of artifacts.
    """
    with open(test_file_path, "r") as f:
        test_case = yaml.safe_load(f)

    test_id = test_case.get("test_case_id", test_file_path.name)
    print(f"\n--- Running Test Case: {test_id} ---")

    if test_case.get("llm_interactions"):
        test_llm_server.prime_responses(test_case["llm_interactions"])

    if test_case.get("setup_artifacts"):
        await setup_artifacts(
            test_artifact_service_instance, test_case["setup_artifacts"]
        )

    input_data = test_case.get("em_gateway_input")
    if not input_data:
        pytest.fail(f"Test case '{test_id}' must contain an 'em_gateway_input' block.")

    payload_bytes = b""
    if "payload_base64" in input_data:
        payload_bytes = base64.b64decode(input_data["payload_base64"])
    elif "payload" in input_data:
        payload_data = input_data["payload"]
        payload_str = (
            json.dumps(payload_data)
            if isinstance(payload_data, (dict, list))
            else str(payload_data)
        )
        payload_bytes = payload_str.encode("utf-8")

    await test_data_plane_client.publish(
        topic=input_data["topic"],
        payload=payload_bytes,
        user_properties=input_data.get("user_properties", {}),
    )

    expected_outputs = test_case.get("expected_em_gateway_outputs", [])
    for i, expected_output in enumerate(expected_outputs):
        print(f"Awaiting expected output #{i+1}...")
        captured_message: SolaceMessage = await test_data_plane_client.get_next_message(
            timeout=5.0
        )

        assert (
            captured_message.get_topic() == expected_output["topic"]
        ), f"Output #{i+1}: Topic mismatch"

        captured_payload_str = captured_message.get_payload().decode("utf-8")
        if "payload_contains" in expected_output:
            assert (
                expected_output["payload_contains"] in captured_payload_str
            ), f"Output #{i+1}: payload_contains mismatch"
        elif "payload_equals" in expected_output:
            assert (
                expected_output["payload_equals"] == captured_payload_str
            ), f"Output #{i+1}: payload_equals mismatch"
        elif "payload_json_equals" in expected_output:
            captured_json = json.loads(captured_payload_str)
            assert (
                expected_output["payload_json_equals"] == captured_json
            ), f"Output #{i+1}: payload_json_equals mismatch"

    if test_case.get("assert_artifact_state"):
        await assert_artifact_state(
            test_artifact_service_instance, test_case["assert_artifact_state"]
        )

    print(f"--- Test Case Passed: {test_id} ---")
