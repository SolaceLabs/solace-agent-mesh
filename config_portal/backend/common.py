import sys

INIT_DEFAULT = {
    "namespace": "default_namespace",
    "broker_type": "solace",
    "broker_url": "ws://localhost:8008",
    "broker_vpn": "default",
    "broker_username": "default",
    "broker_password": "default",
    "container_engine": "docker",
    "llm_model_name": "openai/gpt-4o",
    "llm_endpoint_url": "https://api.openai.com/v1",
    "llm_api_key": "",
    "dev_mode": False,
    "add_webui_gateway": True,
    "webui_frontend_welcome_message": "",
    "webui_frontend_bot_name": "Solace Agent Mesh",
    "webui_frontend_collect_feedback": False,
    "webui_fastapi_host": "127.0.0.1",
    "webui_fastapi_port": 8000,
    "webui_enable_embed_resolution": True,
    "platform_api_host": "127.0.0.1",
    "platform_api_port": 8001,
}

USE_DEFAULT_SHARED_SESSION = "use_default_shared_session"
USE_DEFAULT_SHARED_ARTIFACT = "use_default_shared_artifact"

DEFAULT_COMMUNICATION_TIMEOUT = 600

AGENT_DEFAULTS = {
    "supports_streaming": True,
    "model_type": "general",
    "instruction": "You are a helpful AI assistant named __AGENT_NAME__.",
    "artifact_handling_mode": "reference",
    "enable_embed_resolution": True,
    "enable_artifact_content_instruction": True,
    "tools": "[]",
    "session_service_type": "sql",
    "session_service_behavior": "PERSISTENT",
    "artifact_service_type": USE_DEFAULT_SHARED_ARTIFACT,
    "artifact_service_base_path": "/tmp/samv2",
    "artifact_service_scope": "namespace",
    "agent_card_description": "A helpful AI assistant.",
    "agent_card_default_input_modes": ["text"],
    "agent_card_default_output_modes": ["text", "file"],
    "agent_card_skills_str": "[]",
    "agent_card_publishing_interval": 10,
    "agent_discovery_enabled": True,
    "inter_agent_communication_allow_list": [],
    "inter_agent_communication_deny_list": [],
    "inter_agent_communication_timeout": DEFAULT_COMMUNICATION_TIMEOUT,
    "namespace": "${NAMESPACE}",
}

GATEWAY_DEFAULTS = {
    "namespace": "${NAMESPACE}",
    "gateway_id_suffix": "-gw-01",
    "artifact_service_type": USE_DEFAULT_SHARED_ARTIFACT,
    "artifact_service_scope": "namespace",
    "artifact_service_base_path": "/tmp/samv2",
    "system_purpose": (
        "The system is an AI Chatbot with agentic capabilities.\n"
        "It will use the agents available to provide information,\n"
        "reasoning and general assistance for the users in this system.\n"
        "**Always return useful artifacts and files that you create to the user.**\n"
        "Provide a status update before each tool call.\n"
        "Your external name is Agent Mesh."
    ),
    "response_format": (
        "Responses should be clear, concise, and professionally toned.\n"
        "Format responses to the user in Markdown using appropriate formatting."
    ),
}

PROXY_DEFAULTS = {
    "namespace": "${NAMESPACE}",
    "artifact_service_type": "filesystem",
    "artifact_service_base_path": "/tmp/samv2",
    "artifact_service_scope": "namespace",
    "artifact_handling_mode": "reference",
    "discovery_interval_seconds": 5,
    "proxied_agents": [],
}


port_55555 = "-p 55554:55555" if sys.platform == "darwin" else "-p 55555:55555"

CONTAINER_RUN_COMMAND = f" run -d --rm -p 8080:8080 {port_55555} -p 8008:8008 -u 1004 --shm-size=2g --env username_admin_globalaccesslevel=admin --env username_admin_password=admin --name=solace-broker solace/solace-pubsub-standard"
