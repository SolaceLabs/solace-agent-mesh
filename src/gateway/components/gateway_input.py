from typing import Dict, Any
import base64
import json
from uuid import uuid4

from solace_ai_connector.common.message import Message
from solace_ai_connector.common.log import log
from ...services.file_service import FileService
from ...common.constants import DEFAULT_IDENTITY_KEY_FIELD, HISTORY_USER_ROLE
from .gateway_base import GatewayBase

info = {
    "class_name": "GatewayInput",
    "description": (
        "This component handles requests from users and forms the "
        "appropriate prompt for the next component in the flow."
    ),
    "config_parameters": [
        {
            "name": "gateway_config",
            "type": "object",
            "properties": {
                "gateway_id": {"type": "string"},
                "system_purpose": {"type": "string"},
                "interaction_type": {"type": "string"},
                "history_class": {"type": "string"},
                "history_config": {"type": "object"},
                "identity_key_field": {"type": "string", "default": DEFAULT_IDENTITY_KEY_FIELD},
                "identity": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string"},
                        "module": {"type": "string"},
                        "configuration": {"type": "object"},
                    },
                    "description": "Identity component configuration including module and class names.",
                },
            },
            "description": "Gateway configuration including originators and their configurations.",
        },
        {
            "name": "response_format_prompt",
            "type": "string",
            "description": "Format instructions for the response that will be passed to the model",
            "default": ""
        }
    ],
    "input_schema": {
        "type": "object",
        "properties": {
            "event": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "files": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {
                                    "type": "string",
                                },
                                "content": {
                                    "type": "string",
                                },
                                "mime_type": {"type": "string"},
                                "url": {
                                    "type": "string",
                                },
                                "size": {
                                    "type": "number",
                                },
                            },
                        },
                    },
                },
            },
        },
        "required": ["event"],
    },
    "output_schema": {
        "type": "object",
        "properties": {
            "files": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                        },
                        "content": {
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
            "text": {"type": "string"},
            "interface_properties": {"type": "object"},
            "history": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "role": {"type": "string"},
                        "content": {"type": "string"},
                    },
                },
            },
        },
        "required": ["session_id", "clear_history", "messages"],
    },
}

DEFAULT_SYSTEM_PURPOSE = "You are participating in the chat bot framework."
DEFAULT_INTERACTION_TYPE = "interactive"  # vs "autonomous"


class GatewayInput(GatewayBase):
    """This component handles incoming stimuli and prepares the context for processing."""

    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)
        self.system_purpose = self.get_config("system_purpose", DEFAULT_SYSTEM_PURPOSE) + self.system_purpose_prompt_suffix
        self.interaction_type = self.get_config(
            "interaction_type", DEFAULT_INTERACTION_TYPE
        )
        self.identity_component = self._initialize_identity_component()
        self.response_format_prompt = self.get_config("response_format_prompt", "")

    def _authenticate_user(self, _user_properties: Dict[str, Any]) -> bool:
        # Implement actual authentication logic here
        return True

    def invoke(self, message: Message, data: Dict[str, Any]) -> Dict[str, Any]:
        user_properties = message.get_user_properties() or {}
        copied_data = data.copy()

        errors = []
        available_files = []

        try:
            if not self._authenticate_user(user_properties):
                log.error("User authentication failed")
                raise PermissionError("User authentication failed")

            # Get identity info
            identity_field = self.identity_component.get_identity_field()
            identity_value = user_properties.get(identity_field)
            if not identity_value:
                log.error("Identity field '%s' not found", identity_field)
                raise ValueError(f"Identity field '{identity_field}' not found")

            user_info = self.identity_component.get_user_info(identity_value)

            session_id = user_properties.get("session_id")

            # De-clutter the data and user_properties by moving some properties to a nested sub-object
            top_level_data_properties = {"text", "files"}
            self.demote_interface_properties(copied_data, top_level_data_properties)

            top_level_user_properties = {
                "input_type",
                "session_id",
            }
            self.demote_interface_properties(user_properties, top_level_user_properties)

            prompt = data.get("text", "")
            files = data.get("files", [])

            attached_files = []
            if len(files) > 0:
                file_service = FileService()
                for file in files:
                    content = file["content"]
                    if type(content) == str:
                        try:
                            byte_buffer = base64.b64decode(content)
                        except Exception as e:
                            byte_buffer = content.encode("utf-8")
                    elif type(content) == bytes:
                        byte_buffer = content
                    else:
                        log.error(
                            "Invalid content type for file %s: %s",
                            file["name"],
                            type(content),
                        )
                        continue

                    file_metadata = file_service.upload_from_buffer(
                        byte_buffer,
                        file["name"],
                        session_id,
                        file_size=file["size"],
                        data_source=f"User provided file - {self.gateway_id} Gateway",
                    )
                    attached_files.append(file_metadata)
            copied_data["files"] = attached_files

            copied_data["history"] = []
            if self.use_history:
                other_history_props = {
                    "identity": identity_value,
                }
                prompt = data.get("text", "")
                self.history_instance.store_history(session_id, HISTORY_USER_ROLE, prompt, other_history_props)

                for file in attached_files:
                    self.history_instance.store_file(session_id, file )

                # retrieve all files for the session
                available_files = self.history_instance.get_files(session_id)

                # Add history to the data
                copied_data["history"] = self.history_instance.get_history(session_id, other_history_props)

            available_files = json.dumps(available_files)
        except Exception as e:
            log.error("Error processing input: %s", e)
            errors.append(str(e))

        stimulus_uuid = self.gateway_id + str(uuid4())

        # Add response format prompt from config if available
        if self.response_format_prompt:
            user_properties["response_format_prompt"] = self.response_format_prompt

        user_properties.update(
            {
                "gateway_id": self.gateway_id,
                "system_purpose": self.system_purpose,
                "interaction_type": self.interaction_type,
                "available_files": available_files,
                "stimulus_uuid": stimulus_uuid,
                "user_info": user_info,
                "identity": identity_value,
            }
        )
        copied_data["user_info"] = user_info
        copied_data["errors"] = errors
        message.set_user_properties(user_properties)
        message.set_payload(copied_data)

        return copied_data

    def demote_interface_properties(
        self, dict_properties: Dict[str, Any], top_level_properties: set
    ):
        """
        Demotes specified properties from the top level of a dictionary to a nested dictionary under the key 'interface_properties'.

        Args:
            dict_properties (Dict[str, Any]): The dictionary containing the properties.
            top_level_properties (set): A set of property names that should remain at the top level.

        Modifies:
            dict_properties: Adds a new key 'interface_properties' containing the properties that are not in top_level_properties.
                             Removes the demoted properties from the top level of dict_properties.
        """

        interface_properties = {
            k: v for k, v in dict_properties.items() if k not in top_level_properties
        }
        dict_properties["interface_properties"] = interface_properties

        # Remove keys from user_properties that are in interface_user_properties
        for key in interface_properties:
            dict_properties.pop(key, None)
