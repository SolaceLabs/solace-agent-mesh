import json
from typing import Any, Dict, Optional, List

from solace_ai_connector.common.log import log
from google.adk.tools import ToolContext

from .bedrock_agent_runtime import BedrockAgentRuntime


async def invoke_bedrock_flow(
    input_text: str,
    tool_context: Optional[ToolContext] = None,
    tool_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    plugin_name = "sam-bedrock-agent"
    log_identifier = f"[{plugin_name}:invoke_bedrock_flow]"
    log.info(f"{log_identifier} Received request. Input text: '{input_text[:100]}...'")

    if not tool_context or not tool_context._invocation_context:
        log.error(f"{log_identifier} ToolContext or InvocationContext is missing.")
        return {
            "status": "error",
            "message": "ToolContext or InvocationContext is missing.",
        }

    if not tool_config:
        log.error(f"{log_identifier} Tool configuration (tool_config) is missing.")
        return {"status": "error", "message": "Tool configuration is missing."}

    bedrock_flow_id = tool_config.get("bedrock_flow_id")
    bedrock_flow_alias_id = tool_config.get("bedrock_flow_alias_id")
    input_node_name = tool_config.get("input_node_name", "FlowInputNode")
    input_node_output_name = tool_config.get("input_node_output_name", "document")
    amazon_bedrock_runtime_config = tool_config.get("amazon_bedrock_runtime_config")

    if not bedrock_flow_id or not bedrock_flow_alias_id:
        log.error(
            f"{log_identifier} Missing bedrock_flow_id or bedrock_flow_alias_id in tool_config."
        )
        return {
            "status": "error",
            "message": "Bedrock flow ID or alias ID is missing in configuration.",
        }

    if not amazon_bedrock_runtime_config:
        log.error(
            f"{log_identifier} Missing amazon_bedrock_runtime_config in agent configuration."
        )
        return {
            "status": "error",
            "message": "Amazon Bedrock runtime configuration is missing.",
        }

    boto3_config = amazon_bedrock_runtime_config.get("boto3_config")
    endpoint_url = amazon_bedrock_runtime_config.get("endpoint_url")

    if not boto3_config:
        log.error(
            f"{log_identifier} Missing boto3_config in amazon_bedrock_runtime_config."
        )
        return {
            "status": "error",
            "message": "Boto3 configuration is missing in Bedrock runtime configuration.",
        }

    try:
        bedrock_runtime = BedrockAgentRuntime(
            boto3_config=boto3_config, endpoint_url=endpoint_url
        )

        flow_input_data = [
            {
                "nodeName": input_node_name,
                "nodeOutputName": input_node_output_name,
                "content": {"document": input_text},
            }
        ]

        log.info(
            f"{log_identifier} Invoking Bedrock flow {bedrock_flow_id} (alias {bedrock_flow_alias_id})."
        )
        log.debug(f"{log_identifier} Flow input data: {json.dumps(flow_input_data)}")

        response_text = bedrock_runtime.invoke_flow(
            flow_id=bedrock_flow_id,
            flow_alias_id=bedrock_flow_alias_id,
            input_data=flow_input_data,
        )
        log.info(
            f"{log_identifier} Successfully invoked Bedrock flow. Response length: {len(response_text)}"
        )

        try:
            parsed_response = json.loads(response_text)
            final_response = parsed_response
        except json.JSONDecodeError:
            log.debug(
                f"{log_identifier} Flow response is not JSON, returning as plain text."
            )
            final_response = response_text

        return {
            "status": "success",
            "message": "Bedrock flow invoked successfully.",
            "response": final_response,
        }

    except RuntimeError as r_err:
        log.error(
            f"{log_identifier} Runtime error during Bedrock flow invocation: {r_err}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Runtime error: {r_err}"}
    except Exception as e:
        log.error(f"{log_identifier} Error invoking Bedrock flow: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"Failed to invoke Bedrock flow: {str(e)}",
        }
