"""This is the component that handles processing all streaming outputs from LLM"""

from datetime import datetime

from solace_ai_connector.components.component_base import ComponentBase
from solace_ai_connector.common.log import log
from solace_ai_connector.common.message import Message
from ...common.utils import parse_orchestrator_response, strip_text_after_invoke_action
from ...services.history_service import HistoryService
from ...services.file_service import FileService
from ...orchestrator.orchestrator_main import (
    ORCHESTRATOR_HISTORY_IDENTIFIER,
    ORCHESTRATOR_HISTORY_CONFIG,
)

info = {
    "class_name": "OrchestratorStreamingOutputComponent",
    "description": ("This component handles all streaming outputs from LLM"),
    "config_parameters": [],
    "input_schema": {
        # A streaming output object - it doesn't have a fixed schema
        "type": "object",
        "additionalProperties": True,
    },
    "output_schema": {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "streaming": {"type": "boolean"},
                "first_chunk": {"type": "boolean"},
                "last_chunk": {"type": "boolean"},
                "uuid": {"type": "string"},
            },
            "required": [
                "text",
                "streaming",
                "first_chunk",
                "last_chunk",
                "uuid",
            ],
        },
    },
}


class OrchestratorStreamingOutputComponent(ComponentBase):
    """This is the component that handles processing all streaming outputs from LLM"""

    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)
        self._response_state = {}
        self.history = HistoryService(
            ORCHESTRATOR_HISTORY_CONFIG, identifier=ORCHESTRATOR_HISTORY_IDENTIFIER
        )
        self.file_service = FileService()

    def invoke(self, message: Message, data):
        """Handle streaming outputs from LLM"""
        if not data:
            log.error("No data received from LLM")
            self.discard_current_message()
            return None

        # response complete messages also go through this flow
        # to maintain the order of messages with the streamed responses
        if data.get("response_complete"):
            return [data]

        user_properties = message.get_user_properties()
        stimulus_uuid = user_properties.get("stimulus_uuid")
        session_id = user_properties.get("session_id")
        text = data.get("content")
        response_uuid = data.get("response_uuid")
        first_chunk = data.get("first_chunk")
        last_chunk = data.get("last_chunk")
        check_reasoning = data.get("check_reasoning", True)

        if first_chunk:
            response_state = self.add_response_state(response_uuid)
        else:
            response_state = self.get_response_state(response_uuid)
            if not response_state:
                # Just discard the data
                self.discard_current_message()
                return None
            if last_chunk:
                self.delete_response_state(response_uuid)
                if stimulus_uuid:
                    # Temporary change to remove any bare text and files after the last invoke_action tag
                    stripped_text = strip_text_after_invoke_action(text)
                    self.history.store_history(
                        stimulus_uuid, "assistant", stripped_text
                    )

        obj = parse_orchestrator_response(
            text, last_chunk=last_chunk, check_reasoning=check_reasoning
        )

        if not obj or isinstance(obj, str) or not obj.get("content"):
            log.debug("Error parsing LLM output: %s", obj)
            self.discard_current_message()
            return None

        content = obj.get("content")
        status_updates = obj.get("status_updates")
        send_last_status_update = obj.get("send_last_status_update")

        outputs = []
        full_text = ""
        last_text_output_idx = None
        if content and isinstance(content, list):
            for item_idx, item in enumerate(content):
                output, item_text = self.process_content_item(
                    item_idx,
                    len(content),
                    item,
                    response_state,
                    response_uuid,
                    last_chunk,
                    session_id,
                )
                if item_text:
                    full_text += item_text
                if output:
                    outputs.append(output)
                    if output.get("text"):
                        last_text_output_idx = len(outputs) - 1

        if status_updates and isinstance(status_updates, list):
            last_status_update_idx = response_state.get("last_status_update_idx", -1)
            if (
                last_status_update_idx < len(status_updates) - 1
                or send_last_status_update
            ):
                user_properties = message.get_user_properties()
                stimulus_uuid = user_properties.get("stimulus_uuid")
                if not stimulus_uuid:
                    log.error("No stimulus_uuid found in user_properties")
                    stimulus_uuid = response_uuid
                output = {
                    "status_update": True,
                    "text": status_updates[-1],
                    "uuid": stimulus_uuid + "-status",
                    "streaming": True,
                }
                outputs.append(output)
                response_state["last_status_update_idx"] = len(status_updates) - 1

        if not outputs:
            self.discard_current_message()
            return None

        chunk, next_chunk_index = self.get_current_chunk(
            full_text, response_state.get("previous_chunk_index", 0)
        )

        # Add the chunk to the last output
        if chunk:
            if last_text_output_idx is not None:
                outputs[last_text_output_idx]["chunk"] = chunk
            response_state["previous_chunk_index"] = next_chunk_index

        return outputs

    def process_content_item(
        self,
        item_idx,
        num_items,
        item,
        response_state,
        response_uuid,
        last_chunk,
        session_id,
    ):
        """Process a content item"""
        streaming_content_idx = response_state.get("streaming_content_idx", 0)

        if item_idx < streaming_content_idx:
            if (
                item.get("type") == "text"
                and not item.get("status_update")
                and not item.get("response_complete")
            ):
                return None, item.get("body")
            return None, ""

        streaming_started = response_state.get("streaming_started", False)
        last_chunk = last_chunk or item_idx < (num_items - 1)
        first_chunk = not streaming_started or item_idx > streaming_content_idx

        output = {
            "streaming": True,
        }

        if item.get("type") == "text":
            output["text"] = item.get("body")
        elif item.get("type") == "file":
            file_info = item.get("body", {})
            if file_info.get("url") or file_info.get("data"):
                # If there is no url but there is data, we need to store the data in the file service
                if not file_info.get("url") and file_info.get("data"):
                    file_meta = self.file_service.upload_from_buffer(
                        file_info["data"],
                        file_info["name"],
                        session_id,
                        data_source="Orchestrator created data",
                    )
                    if not session_id:
                        log.error("No session_id found in user_properties")
                    file_info.update(file_meta)

                output["files"] = [file_info]
        else:
            return None

        output["first_chunk"] = first_chunk
        output["last_chunk"] = last_chunk
        output["uuid"] = response_uuid + "-" + str(item_idx)
        response_state["streaming_content_idx"] = item_idx
        response_state["streaming_started"] = True
        return output, output.get("text") or ""

    def get_current_chunk(self, full_text, previous_chunk_index):
        """Use the previous_chunk_index to get the current chunk of text from the full_text"""

        # The chunk is the text from the previous_chunk_index to the end of the full_text
        chunk = full_text[previous_chunk_index:]
        return chunk, len(full_text)

    def age_out_response_state(self):
        """Remove any responses that have been around for too long"""
        # Loop through all states and remove any that are too old
        current_time = datetime.now()
        for response_uuid in list(self._response_state.keys()):
            response_state = self._response_state[response_uuid]
            delta = current_time - response_state["create_time"]
            if delta.total_seconds() > 60:
                del self._response_state[response_uuid]

    def get_response_state(self, response_uuid):
        """Get the state of a response"""
        return self._response_state.get(response_uuid)

    def add_response_state(self, response_uuid):
        """Add a new response state"""
        response_state = {
            "create_time": datetime.now(),
            "streaming_content_idx": 0,
            "previous_chunk_index": 0,
        }
        self._response_state[response_uuid] = response_state
        self.age_out_response_state()
        return response_state

    def delete_response_state(self, response_uuid):
        """Delete a response state"""
        if response_uuid in self._response_state:
            del self._response_state[response_uuid]
