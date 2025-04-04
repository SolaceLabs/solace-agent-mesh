import base64
from solace_ai_connector.common.message import Message
from solace_ai_connector.common.log import log

from .gateway_base import GatewayBase
from ...services.file_service import FileService
from ...common.utils import files_to_block_text
from ...common.constants import HISTORY_ASSISTANT_ROLE

info = {
    "class_name": "GatewayOutput",
    "description": (
        "This component handles stimuli from users and forms the "
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
                "default_originator_scopes": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "description": "Gateway configuration including originators and their configurations.",
        },
    ],
    "input_schema": {
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
                    "first_chunk": {
                        "type": "boolean",
                    },
                    "last_chunk": {
                        "type": "boolean",
                    },
                    "uuid": {
                        "type": "string",
                    },
                    "chunk": {
                        "type": "text",
                    },
                    "status_update": {
                        "type": "boolean",
                    },
                },
            },
        },
    },
    "output_schema": {
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
                    "first_chunk": {
                        "type": "boolean",
                    },
                    "last_chunk": {
                        "type": "boolean",
                    },
                    "uuid": {
                        "type": "string",
                    },
                    "chunk": {
                        "type": "text",
                    },
                    "status_update": {
                        "type": "boolean",
                    },
                },
            },
        },
    },
}


class GatewayOutput(GatewayBase):
    """This is the component that handles incoming stimuli"""

    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)
        self.default_agent_scopes = self.get_config("default_agent_scopes", [])
        self.originators = self.get_config("originators", [])

    def _resolve_text_content(self, data: dict, session_id: str) -> None:
        """
        Resolve all AMFS URLs in text and chunk fields of the data dictionary.

        Args:
            data (dict): The data dictionary containing text and chunk fields
            session_id (str): The session ID for file service operations

        Returns:
            None: Modifies the data dictionary in place
        """
        try:
            file_service = FileService()
            text_output_response = data.get("text", "") or ""
            data["text"] = file_service.resolve_all_resolvable_urls(
                text_output_response, session_id
            )
            chunk_output_response = data.get("chunk", "") or ""
            data["chunk"] = file_service.resolve_all_resolvable_urls(
                chunk_output_response, session_id
            )
        except Exception as e:
            log.error(f"Failed to resolve URLs in text: {e}")

    def invoke(self, message: Message, data) -> Message:
        file_service = FileService()
        user_properties = message.get_user_properties()
        session_id = user_properties.get("session_id")
        identity_value = user_properties.get("identity")
        files = data.get("files", [])

        # Extract the interface queue ID
        interface_properties = user_properties.get("interface_properties", [])
        server_input_id = (
            interface_properties and interface_properties.get("server_input_id", "")
            if interface_properties
            else ""
        )

        if self.use_history and session_id:
            other_history_props = {
                "identity": identity_value,
            }

            topic = message.get_topic()
            content = data.get("text") or ""

            file_text_blocks = files_to_block_text(files)
            if file_text_blocks:
                content += file_text_blocks

            if (
                "/streamingResponse/" in topic
                and data.get("last_chunk")
                and "text" in data
            ):
                actions_called = user_properties.get("actions_called", [])
                if actions_called:
                    self.history_instance.store_actions(session_id, actions_called)
                
                if content:
                    self.history_instance.store_history(
                        session_id, HISTORY_ASSISTANT_ROLE, content, other_history_props
                    )

            for file in files:
                self.history_instance.store_history(
                    session_id, HISTORY_ASSISTANT_ROLE, f'\n[Returned file: {{name: {file.get("name")}, url: {file.get("url")}}}]\n', other_history_props
                )
                self.history_instance.store_file(session_id, file)

            clear_history_tuple = user_properties.get("clear_gateway_history", [])
            if clear_history_tuple and clear_history_tuple[0]:
                keep_depth = clear_history_tuple[1]
                self.history_instance.clear_history(session_id, keep_depth)

        if files:
            downloaded_files = []
            for file in files:
                output_file = {
                    "name": file.get("name"),
                }
                # inline file
                if file.get("data"):
                    data_content = file_service.resolve_all_resolvable_urls(
                        file.get("data"), session_id
                    )
                    inline_data = base64.b64encode(data_content.encode()).decode()
                    output_file["content"] = inline_data
                    output_file["mime_type"] = file.get("mime_type", "text/plain")
                elif file.get("url"):
                    url = file.get("url")
                    try:
                        resolved_content = file_service.resolve_url(url, session_id)
                        buffer_content = (
                            resolved_content
                            if type(resolved_content) == bytes
                            else resolved_content.encode()
                        )
                        output_file["content"] = base64.b64encode(
                            buffer_content
                        ).decode("utf-8")

                        # If the file name or mime type is not provided, try to get it from the resolved URL
                        if not output_file.get("name") or not output_file.get(
                            "mime_type"
                        ):
                            metadata = file_service.get_metadata(url)
                            output_file["name"] = output_file.get(
                                "name"
                            ) or metadata.get("name")
                            output_file["mime_type"] = output_file.get(
                                "mime_type"
                            ) or metadata.get("mime_type")
                    except Exception as e:
                        log.error(f"Failed to download file {file.get('name')}: {e}")
                        continue
                else:
                    log.error(f"No file content found for {file.get('name')}")
                    continue
                downloaded_files.append(output_file)

            data["files"] = downloaded_files
        data["server_input_id"] = server_input_id

        # Promote the interface properties back to the top level of the user_properties
        self.promote_interface_properties(user_properties)
        message.set_user_properties(user_properties)

        # Resolve inline URLs in text and chunk fields
        self._resolve_text_content(data, session_id)

        message.set_payload(data)
        return {"payload": data}

    def promote_interface_properties(self, user_properties):
        """
        Updates the user_properties with the values from the
        "interface_properties" sub-object, if it exists.

        Args:
            user_properties (dict): A dictionary that may contain an
                                    "interface_properties" key with a sub-dictionary
                                    of properties to be merged into the main dictionary.

        Returns:
            None: The function modifies the user_properties dictionary in place.
        """
        interface_properties = user_properties.get("interface_properties", {})
        if isinstance(interface_properties, dict):
            for key, value in interface_properties.items():
                user_properties[key] = value

        user_properties.pop("interface_properties", None)
