default_options = {
    "namespace": "",
    "config_dir": "configs",
    "module_dir": "modules",
    "env_file": ".env",
    "build_dir": "build",
    "broker_type": "solace",
    "broker_url": "ws://localhost:8008",
    "broker_vpn": "default",
    "broker_username": "default",
    "broker_password": "default",
    "container_engine": "docker",
    "llm_model_name": "openai/gpt-4o",
    "llm_endpoint_url": "https://api.openai.com/v1",
    "llm_api_key": "",
    "embedding_model_name": "openai/text-embedding-ada-002",
    "embedding_endpoint_url": "https://api.openai.com/v1",
    "embedding_api_key": "",
    "built_in_agent": ["web_request"],
    "file_service_provider": "volume",
    "file_service_config": ["directory=/tmp/solace-agent-mesh"],
    "env_var": [],
    "rest_api_enabled": True,
    "rest_api_server_input_port": "5050",
    "rest_api_server_host": "127.0.0.1",
    "rest_api_server_input_endpoint": "/api/v1/request",
    "rest_api_gateway_name": "rest-api",
    "webui_enabled": True,
    "webui_listen_port": "5001",
    "webui_host": "127.0.0.1",
    "dev_mode": True,
}

CONTAINER_RUN_COMMAND = " run -d -p 8080:8080 -p 55554:55555 -p 8008:8008 -p 1883:1883 -p 8000:8000 -p 5672:5672 -p 9000:9000 -p 2222:2222 --shm-size=2g --env username_admin_globalaccesslevel=admin --env username_admin_password=admin --name=solace solace/solace-pubsub-standard"