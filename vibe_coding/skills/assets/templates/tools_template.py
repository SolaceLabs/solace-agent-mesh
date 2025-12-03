import logging
import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from google.adk.tools import ToolContext
from solace_agent_mesh.agent.utils.artifact_helpers import (
    save_artifact_with_metadata,
    DEFAULT_SCHEMA_MAX_KEYS,
)
from solace_agent_mesh.agent.utils.context_helpers import get_original_session_id

log = logging.getLogger(__name__)

async def example_text_processor_tool(
    text_input: str,
    uppercase: bool = False,  # Example of a boolean parameter
    tool_context: Optional[ToolContext] = None,
    tool_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    An example tool that processes input text, optionally converts it to uppercase,
    and adds a prefix from tool_config.
    """
    plugin_name = "__PLUGIN_SPACED_NAME__"
    log_identifier = f"[{plugin_name}:example_text_processor_tool]"
    log.info(f"{log_identifier} Received text: '{text_input}', uppercase: {uppercase}")

    current_tool_config = tool_config if tool_config is not None else {}
    prefix = current_tool_config.get("prefix", "Processed: ")

    processed_text = text_input
    if uppercase:
        processed_text = processed_text.upper()

    final_text = f"{prefix}{processed_text}"

    log.info(f"{log_identifier} Processed text: '{final_text}'")
    return {
        "status": "success",
        "message": "Text processed successfully by example_text_processor_tool.",
        "original_input": text_input,
        "processed_text": final_text,
        "was_uppercased": uppercase,
    }


async def example_text_file_creator_tool(
    filename: str,
    content: str,
    tool_context: Optional[ToolContext] = None,
    tool_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    An example tool that creates a text file and saves it as an artifact
    using the Solace Agent Mesh artifact service.
    """
    plugin_name = "__PLUGIN_SPACED_NAME__"
    log_identifier = f"[{plugin_name}:example_text_file_creator_tool]"
    log.info(
        f"{log_identifier} Received request to create file: '{filename}' with content starting: '{content[:50]}...'"
    )

    if not tool_context or not tool_context._invocation_context:
        log.error(
            f"{log_identifier} ToolContext or InvocationContext is missing. Cannot save artifact."
        )
        return {
            "status": "error",
            "message": "ToolContext or InvocationContext is missing.",
        }

    inv_context = tool_context._invocation_context
    app_name = getattr(inv_context, "app_name", None)
    user_id = getattr(inv_context, "user_id", None)
    session_id = get_original_session_id(inv_context)
    artifact_service = getattr(inv_context, "artifact_service", None)

    if not all([app_name, user_id, session_id, artifact_service]):
        missing_parts = [
            part
            for part, val in [
                ("app_name", app_name),
                ("user_id", user_id),
                ("session_id", session_id),
                ("artifact_service", artifact_service),
            ]
            if not val
        ]
        log.error(
            f"{log_identifier} Missing required context parts for artifact saving: {', '.join(missing_parts)}"
        )
        return {
            "status": "error",
            "message": f"Missing required context parts for artifact saving: {', '.join(missing_parts)}",
        }

    output_filename = filename
    if not output_filename.lower().endswith(".txt"):
        output_filename += ".txt"

    content_bytes = content.encode("utf-8")
    mime_type = "text/plain"
    timestamp = datetime.now(timezone.utc)

    metadata_dict = {
        "description": f"Text file created by {plugin_name}'s example_text_file_creator_tool.",
        "source_tool": "example_text_file_creator_tool",
        "original_requested_filename": filename,
        "creation_timestamp_iso": timestamp.isoformat(),
        "content_character_count": len(content),
    }

    log.info(
        f"{log_identifier} Attempting to save artifact '{output_filename}' via artifact_service."
    )
    try:
        save_result = await save_artifact_with_metadata(
            artifact_service=artifact_service,
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
            filename=output_filename,
            content_bytes=content_bytes,
            mime_type=mime_type,
            metadata_dict=metadata_dict,
            timestamp=timestamp,
            schema_max_keys=DEFAULT_SCHEMA_MAX_KEYS,
            tool_context=tool_context,
        )
        if save_result.get("status") == "error":
            log.error(
                f"{log_identifier} Failed to save artifact: {save_result.get('message')}"
            )
            return {
                "status": "error",
                "message": f"Failed to save artifact: {save_result.get('message')}",
            }

        log.info(
            f"{log_identifier} Artifact '{output_filename}' v{save_result['data_version']} saved successfully."
        )
        return {
            "status": "success",
            "message": f"File '{output_filename}' created and saved as artifact v{save_result['data_version']}.",
            "output_filename": output_filename,
            "output_version": save_result["data_version"],
        }
    except Exception as e:
        log.exception(f"{log_identifier} Unexpected error during artifact saving: {e}")
        return {
            "status": "error",
            "message": f"An unexpected error occurred during artifact saving: {e}",
        }


# Example of how these might be tested or run if this file was executed directly.
# This assumes the script is run in an environment where solace_agent_mesh is importable,
# or the imports at the top will fail.
if __name__ == "__main__":

    async def run_tests():
        print("--- Testing example_text_processor_tool ---")
        # For standalone testing, ToolContext might be minimal or None if ADK is not fully available.
        # The tool should handle tool_context=None gracefully if it's designed to be testable standalone.

        # A more complete mock for standalone testing if needed:
        class MockArtifactService:
            async def save_artifact(
                self, **kwargs
            ):  # Match expected signature elements
                log.info(
                    f"MockArtifactService.save_artifact called with filename: {kwargs.get('filename')}"
                )
                return {
                    "uri": f"mock://{kwargs.get('filename')}",
                    "version": 1,
                }  # Simulate ADK response

            async def save_artifact_metadata(self, **kwargs):
                log.info(
                    f"MockArtifactService.save_artifact_metadata called for: {kwargs.get('filename')}"
                )
                return {
                    "uri": f"mock://{kwargs.get('filename')}.metadata",
                    "version": 1,
                }

        class MockInvocationContext:
            def __init__(self):
                self.app_name = "test_app"
                self.user_id = "test_user"
                self.session_id = "test_session_123"
                self.artifact_service = MockArtifactService()
                # Add other attributes if your tool or helpers expect them

        class MockToolContext:
            def __init__(self):
                self._invocation_context = MockInvocationContext()

        mock_context = MockToolContext()

        text_result1 = await example_text_processor_tool(
            "hello world",
            uppercase=True,
            tool_context=mock_context,
            tool_config={"prefix": "TestPrefix: "},
        )
        print(f"Text tool result 1: {text_result1}")

        text_result2 = await example_text_processor_tool(
            "another test", tool_context=mock_context
        )
        print(f"Text tool result 2: {text_result2}")

        print("\n--- Testing example_text_file_creator_tool ---")
        file_result = await example_text_file_creator_tool(
            "my_example_file.txt",
            "This is the content of the example file created by the plugin template.",
            tool_context=mock_context,  # Using the mock context with a mock artifact service
        )
        print(f"File tool result: {file_result}")

    asyncio.run(run_tests())
