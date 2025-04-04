"""This is the component that handles request from users and forms the appropriate prompt for the LLM, makes the call, and parses the output and creates the appropriate ActionRequests"""

import datetime
import random
import json
import copy
import uuid
import os
from dateutil.tz import tzlocal
from time import time
from typing import Dict, Any
import yaml

from solace_ai_connector.common.log import log
from solace_ai_connector.common.message import Message

from ...common.constants import ORCHESTRATOR_COMPONENT_NAME, HISTORY_MEMORY_ROLE
from ...services.llm_service.components.llm_request_component import LLMRequestComponent, info as base_info
from ...services.middleware_service.middleware_service import MiddlewareService
from ...services.file_service import FileService
from ...services.history_service import HistoryService
from ..orchestrator_main import (
    OrchestratorState,
    ORCHESTRATOR_HISTORY_IDENTIFIER,
    ORCHESTRATOR_HISTORY_CONFIG,
)
from ..orchestrator_prompt import (
    SystemPrompt,
    UserStimulusPrompt,
    ActionResponsePrompt,
)
from ...common.utils import files_to_block_text, parse_orchestrator_response
from ..action_manager import ActionManager


info = base_info.copy()
info["class_name"] = "OrchestratorStimulusProcessorComponent"
info["description"] = (
    "This component is the main orchestrator of the system that "
    "handles request from users and forms the appropriate prompt "
    "for the LLM, makes the call, and parses the output and creates "
    "the appropriate ActionRequests"
)
info["input_schema"] = {
    "type": "object",
    "properties": {
        "event": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                },
                "files": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                            },
                            "data": {
                                "type": "string",
                            },
                            "mime_type": {
                                "type": "string",
                            },
                            "url": {
                                "type": "string",
                            },
                            "file_size": {
                                "type": "number",
                            },
                        },
                    },
                },
                "identity": {
                    "type": "string",
                },
            },
        },
    },
    "required": ["event"],
}

info["output_schema"] = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "topic": {"type": "string"},
            "payload": {"type": "object"},
        },
        "required": ["topic", "payload"],
    },
}


class OrchestratorStimulusProcessorComponent(LLMRequestComponent):
    """This is the component that handles request fromn users and forms the appropriate prompt for the LLM, makes the call, and parses the output and creates the appropriate ActionRequests"""

    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)
        with self.get_lock("orchestrator_state"):
            self.orchestrator_state = self.kv_store_get("orchestrator_state")
            if not self.orchestrator_state:
                self.orchestrator_state = OrchestratorState()
                self.kv_store_set("orchestrator_state", self.orchestrator_state)

        self.history = HistoryService(
            ORCHESTRATOR_HISTORY_CONFIG, identifier=ORCHESTRATOR_HISTORY_IDENTIFIER
        )
        self.action_manager = ActionManager(self.flow_kv_store, self.flow_lock_manager)
        self.stream_to_flow = self.get_config("stream_to_flow")


    def invoke(self, message: Message, data: Dict[str, Any]) -> Dict[str, Any]:
        user_properties = message.get_user_properties()
        user_properties['timestamp_start'] = time()
        message.set_user_properties(user_properties)

        results = self.pre_llm(message, data)
        message.set_payload(results)

        results = self.llm_call(message, results)
        message.set_payload(results)

        results = self.post_llm(message, results)

        user_properties = message.get_user_properties()
        user_properties['timestamp_end'] = time()

        actions_called = []
        if results:
            for result in results:
                if result.get("payload", {}).get("action_name"):
                    actions_called.append({
                        "agent_name": result.get("payload", {}).get("agent_name"),
                        "action_name": result.get("payload", {}).get("action_name"),
                        "action_params": result.get("payload", {}).get("action_params"),
                    })
        user_properties['actions_called'] = actions_called

        message.set_user_properties(user_properties)

        return results

    def pre_llm(self, message: Message, data) -> Message:
        """Handle incoming stimuli"""

        payload = data

        chat_text = payload.get("text")
        files = payload.get("files") or []
        errors = payload.get("errors") or []
        action_response_reinvoke = payload.get("action_response_reinvoke")

        # Expand the files into the chat_text
        file_text_blocks = files_to_block_text(files)
        if file_text_blocks:
            chat_text += file_text_blocks

        available_files = []
        try:
            user_properties = message.get_user_properties() or {}
            available_files_user_prop = json.loads(
                user_properties.get("available_files", "[]")
            )
            # If we have some files, also add them
            if files:
                for file in files:
                    if file.get("url"):
                        available_files_user_prop.append(
                            {
                                "url": file.get("url"),
                                "name": file.get("name"),
                                "mime_type": file.get("mime_type"),
                            }
                        )
                # Save the available files in the user properties
                user_properties["available_files"] = json.dumps(
                    available_files_user_prop
                )
            if available_files_user_prop:
                available_files = [
                    FileService.get_file_block_by_metadata(file)
                    for file in available_files_user_prop
                ]
        except Exception as e:
            log.error("Failed to get available files: %s", str(e))

        user_properties = message.get_user_properties()
        stimulus_uuid = user_properties.get("stimulus_uuid")

        if not stimulus_uuid:
            stimulus_uuid = str(uuid.uuid4())
            user_properties["stimulus_uuid"] = stimulus_uuid
            message.set_user_properties(user_properties)

        input_data = self.get_user_input(chat_text)
        user_info = user_properties.get("user_info", {"email": "unknown"})

        agent_state_yaml, examples = self.get_agents_yaml(user_properties)
        full_input = {
            "input_yaml": yaml.dump(input_data),
            "input": input_data,
            "originator_info_yaml": yaml.dump(user_info),
            "originator_persona_prompt": user_properties.get(
                "originator_persona_prompt"
            ),
            "system_purpose": user_properties.get("system_purpose"),
            "response_format_prompt": user_properties.get("response_format_prompt"),
            "originator_info": user_info,  # Do we need this?
            "agent_state_yaml": agent_state_yaml,
            "tag_prefix": "t"
            + str(random.randint(100, 999))
            + "_",  # Prefix with 't' as XML tags cannot start with a number
            "available_files": available_files,
        }

        # Get the prompts
        gateway_history, memory_history = self.get_gateway_history(data)
        system_prompt = SystemPrompt(full_input, examples)
        if action_response_reinvoke:
            user_prompt = ActionResponsePrompt(
                {"input": chat_text, "tag_prefix": full_input["tag_prefix"]}
            )
        else:
            has_files = len(files) > 0 or len(available_files) > 0
            user_prompt = UserStimulusPrompt(
                full_input, gateway_history, errors, has_files
            )
            if memory_history:
                self.history.store_history(stimulus_uuid, "system", memory_history)


        # Store the user prompt in the history
        self.history.store_history(stimulus_uuid, "user", user_prompt)

        # Get the all the messages
        orchestrator_history = self.history.get_history(stimulus_uuid)

        result = {
            "messages": [
                {"role": "system", "content": system_prompt},
                *orchestrator_history,
            ],
        }

        return result

    def post_llm(self, message: Message, data) -> Message:
        """Handle LLM responses"""
        content = data.get("content", "")
        response_obj = parse_orchestrator_response(content, last_chunk=True)
        user_properties = message.get_user_properties()
        session_id = user_properties.get("session_id")

        # Check if there was a parsing error
        if (
            not response_obj
            or "actions" not in response_obj
            or "content" not in response_obj
            or not isinstance(response_obj["actions"], list)
            or not isinstance(response_obj["content"], list)
            or (len(response_obj["actions"]) == 0 and len(response_obj["content"]) == 0)
        ):
            # We need to re-invoke the LLM to let it know that the
            # response was not correctly formatted
            log.error("Failed to parse response - reinvoking LLM: %s", data)
            msg = "Failed to parse your response. Please try again and make sure your response conforms to the expected format."
            if response_obj:
                content = response_obj.get("content", [])
                actions = response_obj.get("actions", [])
                if len(content) == 0 and len(actions) == 0:
                    msg = "There were no actions and no text or files in the response. Please try again and ensure your formatting is correct."
                elif len(actions):
                    # Loop through the actions and make sure they all have an action and agent
                    for action in actions:
                        if not action.get("action") or not action.get("agent"):
                            msg = "There were actions in the response that were missing an action or agent. Please try again and ensure your formatting is correct."
                            break
            # Store the current_subject_starting_id in the session state so that we can
            # use it later to trim history
            self.orchestrator_state.set_current_subject_starting_id(
                session_id,
                response_obj.get("current_subject_starting_id"),
            )
            return [
                {
                    "payload": {
                        "text": msg,
                        "identity": user_properties.get("identity"),
                        "channel": user_properties.get("channel"),
                        "thread_ts": user_properties.get("thread_ts"),
                        "action_response_reinvoke": True,
                    },
                    "topic": f"{os.getenv('SOLACE_AGENT_MESH_NAMESPACE')}solace-agent-mesh/v1/stimulus/orchestrator/reinvokeModel",
                }
            ]

        try:
            # If there are errors, we need to send it to the orchestrator
            if "errors" in response_obj and len(response_obj["errors"]) > 0:
                log.error("Errors in response: %s", response_obj["errors"])
                return [
                    {
                        "payload": {
                            "text": "The following errors were encountered while processing the stimulus: "
                            + ", ".join(response_obj["errors"]),
                            "identity": user_properties.get("identity"),
                            "channel": user_properties.get("channel"),
                            "thread_ts": user_properties.get("thread_ts"),
                            "action_response_reinvoke": True,
                        },
                        "topic": f"{os.getenv('SOLACE_AGENT_MESH_NAMESPACE')}solace-agent-mesh/v1/stimulus/orchestrator/reinvokeModel",
                    }
                ]

            action_requests = self.create_action_requests(response_obj, user_properties)
        except ValueError as e:
            return [
                {
                    "payload": {
                        "text": f"Check your agents and actions something was wrong: {str(e)}",
                        "identity": user_properties.get("identity"),
                        "action_response_reinvoke": True,
                    },
                    "topic": f"{os.getenv('SOLACE_AGENT_MESH_NAMESPACE')}solace-agent-mesh/v1/stimulus/orchestrator/reinvokeModel",
                }
            ]

        if not action_requests or len(action_requests) == 0:
            # There are no actions to perform, so we must send the
            # responseComplete message - note that because it
            # is very likely that there is a streamed response in flight
            # we need to send the complete event on the same path to ensure
            # that the ordering is preserved
            user_properties = message.get_user_properties()
            gateway_id = user_properties.get("gateway_id")
            if self.stream_to_flow:
                message = Message(
                    payload={
                        "response_complete": True,
                        "streaming": True,
                    },
                    user_properties=user_properties,
                    topic=f"{os.getenv('SOLACE_AGENT_MESH_NAMESPACE')}solace-agent-mesh/v1/responseComplete/orchestrator/{gateway_id}",
                )
                self.send_to_flow(self.stream_to_flow, message)
                self.discard_current_message()
                return None
            else:
                return [
                    {
                        "payload": {},
                        "topic": f"{os.getenv('SOLACE_AGENT_MESH_NAMESPACE')}solace-agent-mesh/v1/responseComplete/orchestrator/{gateway_id}",
                    }
                ]

        # Pull out the action requests from the payload and add them to the action manager
        ars = [item["payload"] for item in action_requests]

        self.action_manager.add_action_request(ars, message.get_user_properties())

        return action_requests

    def llm_call(self, message: Message, data) -> Message:
        """
        Invoke the LLM service request.

        Args:
            message (Message): The input message.
            data (Dict[str, Any]): The input data containing the messages.

        Returns:
            Dict[str, Any]: The response from the LLM service.
        """
        messages = data.get("messages", [])
        llm_message = self._create_llm_message(message, messages, {"type": "orchestrator"})
        response_uuid = str(uuid.uuid4())

        try:
            if self.llm_mode == "stream":
                return self._handle_streaming(message, llm_message, response_uuid)
            else:
                return self._handle_sync(llm_message)
        except Exception as e:
            log.error("Error invoking LLM service: %s", e, exc_info=True)
            raise

    def get_gateway_history(self, data):
        gateway_history = data.get("history", [])
        memory_history = None
        if gateway_history and gateway_history[0].get("role") == HISTORY_MEMORY_ROLE:
            memory_history =gateway_history[0].get("content")
        # Returning the history from the last user message
        first_user_idx = None
        last_user_idx = None
        for idx, item in enumerate(gateway_history):
            if item["role"] == "user":
                if first_user_idx is None:
                    first_user_idx = idx
                last_user_idx = idx

        if first_user_idx is None:
            return [], memory_history  # No user query found

        if not last_user_idx > first_user_idx:
            # Latest user message is already handled by orchestator history
            return [], memory_history

        return gateway_history[first_user_idx:last_user_idx], memory_history

    def get_user_input(self, chat_text):

        now = datetime.datetime.now(tzlocal())
        datetime_string = now.strftime("%Y-%m-%d %H:%M:%S %Z%z")
        # Add the current day of the week
        day_of_week = now.strftime("%A")
        datetime_string += f" ({day_of_week})"

        input_data = {
            "originator_input": chat_text,
            "current_time_iso": datetime_string,
        }

        return input_data

    def extract_examples_from_actions(self, agents):
        examples = []
        for agent in agents.values():
            if not agent.get("actions"):
                continue
            for action in agent["actions"]:
                if action:
                    action_data = action[next(iter(action))]
                    popped_examples = action_data.pop("examples", [])
                    if agent.get("state") == "open":
                        examples.extend(popped_examples)
        return examples

    def get_agents_yaml(self, user_properties: dict):
        agents = copy.deepcopy(
            self.orchestrator_state.get_agents_and_actions(user_properties)
        )
        examples = self.extract_examples_from_actions(agents)
        agents_yaml = yaml.dump(agents)
        return agents_yaml, examples

    def create_action_requests(self, response_obj: dict, user_properties: dict) -> list:
        """Create ActionRequests from the response object"""

        action_requests = []

        if "actions" not in response_obj:
            return action_requests

        action_idx = 0
        for action in response_obj["actions"]:
            action_name = action.get("action")
            agent_name = action.get("agent")
            action_details = self.orchestrator_state.get_agent_action(
                agent_name, action_name
            )
            if not action_details:
                raise ValueError(
                    f"Action not found in agent: {agent_name}, {action_name}"
                )
            middleware_service = MiddlewareService()
            if middleware_service.get("validate_action_request")(user_properties, action_details):
                action_params = action.get("parameters", {})

                action_requests.append(
                    {
                        "payload": {
                            "agent_name": agent_name,
                            "action_name": action_name,
                            "action_params": action_params,
                            "action_idx": action_idx,
                            "originator": ORCHESTRATOR_COMPONENT_NAME,
                        },
                        "topic": f"{os.getenv('SOLACE_AGENT_MESH_NAMESPACE')}solace-agent-mesh/v1/actionRequest/orchestrator/agent/{agent_name}/{action_name}",
                    }
                )
                action_idx += 1

            else:
                log.error(
                    "Unauthorized to perform action: %s, %s",
                    agent_name,
                    action_name,
                )
                raise ValueError(
                    f"Unauthorized to perform action: {agent_name}, {action_name}"
                )

        return action_requests
