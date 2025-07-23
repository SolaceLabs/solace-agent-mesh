from solace_ai_connector.common.log import log
from botocore.exceptions import ClientError
import json

from .aws_session_manager import get_aws_session_manager


class BedrockAgentRuntime:
    """Encapsulates Amazon Bedrock Agents Runtime actions."""

    def __init__(self, boto3_config: dict = None, endpoint_url: str = None):
        """
        Initializes the BedrockAgentRuntime.
        It ensures the AWSSessionManager is initialized and retrieves the client.

        Args:
            boto3_config (dict, optional): AWS boto3 session configuration.
                                           Required if AWSSessionManager is not yet initialized.
            endpoint_url (str, optional): Custom endpoint URL for Bedrock.
        """
        session_manager = get_aws_session_manager(
            boto3_config=boto3_config, endpoint_url=endpoint_url
        )
        self.agents_runtime_client = session_manager.get_bedrock_agent_runtime_client()
        log.info(
            "[BedrockAgentRuntime] Initialized with client from AWSSessionManager."
        )

    def invoke_agent(
        self, agent_id, agent_alias_id, session_id, prompt, session_state=None
    ):
        """
        Sends a prompt for the agent to process and respond to.

        :param agent_id: The unique identifier of the agent to use.
        :param agent_alias_id: The alias of the agent to use.
        :param session_id: The unique identifier of the session. Use the same value across requests
                           to continue the same conversation.
        :param prompt: The prompt that you want model to complete.
        :param session_state: The state of the session, can include files.
        :return: Inference response from the model as a string.
        """
        log.debug(
            f"[BedrockAgentRuntime] Invoking agent {agent_id} (alias {agent_alias_id}) for session {session_id} with prompt: '{prompt[:100]}...' and session_state: {'Set' if session_state else 'Not set'}"
        )
        try:
            response = self.agents_runtime_client.invoke_agent(
                agentId=agent_id,
                agentAliasId=agent_alias_id,
                sessionId=session_id,
                inputText=prompt,
                sessionState=session_state,
            )

            completion = ""
            completion_stream = response.get("completion", [])
            for event in completion_stream:
                chunk = event.get("chunk", {})
                if "bytes" in chunk:
                    completion += chunk["bytes"].decode("utf-8", errors="replace")

            log.debug(
                f"[BedrockAgentRuntime] Agent {agent_id} invocation successful. Response length: {len(completion)}"
            )
            return completion

        except ClientError as e:
            log.error(f"Couldn't invoke agent {agent_id}. Error: {e}", exc_info=True)
            raise e
        except Exception as e:
            log.error(
                f"An unexpected error occurred while invoking agent {agent_id}: {e}",
                exc_info=True,
            )
            raise e

    def invoke_flow(self, flow_id, flow_alias_id, input_data: list):
        """
        Invoke an Amazon Bedrock flow and handle the response stream.

        Args:
            flow_id (str): The ID of the flow to invoke.
            flow_alias_id (str): The alias ID of the flow.
            input_data (list): Input data for the flow, typically a list of input nodes.
                               Example: [{"nodeName": "input", "nodeOutputName": "text", "content": {"document": "user prompt"}}]

        Return: Response from the flow as a string.
        """
        log.debug(
            f"[BedrockAgentRuntime] Invoking flow {flow_id} (alias {flow_alias_id}) with input: {input_data}"
        )
        try:
            response = self.agents_runtime_client.invoke_flow(
                flowIdentifier=flow_id,
                flowAliasIdentifier=flow_alias_id,
                inputs=input_data,
            )

            result_stream_content = ""
            for event in response.get("responseStream", []):
                if "flowChunk" in event:
                    chunk = event["flowChunk"]
                    if "bytes" in chunk:
                        result_stream_content += chunk["bytes"].decode(
                            "utf-8", errors="replace"
                        )
                elif "flowOutputEvent" in event:
                    output_event = event["flowOutputEvent"]
                    log.debug(
                        f"[BedrockAgentRuntime] Flow output event: {output_event}"
                    )
                    if "content" in output_event and isinstance(
                        output_event["content"], dict
                    ):
                        try:
                            result_stream_content += (
                                json.dumps(output_event["content"]) + "\n"
                            )
                        except TypeError:
                            result_stream_content += str(output_event["content"]) + "\n"
                    else:
                        result_stream_content += str(output_event) + "\n"

            log.debug(
                f"[BedrockAgentRuntime] Flow {flow_id} invocation successful. Raw result: {result_stream_content[:500]}..."
            )
            return result_stream_content

        except ClientError as e:
            log.error(f"Couldn't invoke flow {flow_id}. Error: {e}", exc_info=True)
            raise e
        except Exception as e:
            log.error(
                f"An unexpected error occurred while invoking flow {flow_id}: {e}",
                exc_info=True,
            )
            raise e
