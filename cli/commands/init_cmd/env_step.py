from pathlib import Path

import click

from ...utils import ask_if_not_provided

ENV_DEFAULTS = {
    "LLM_SERVICE_ENDPOINT": "YOUR_LLM_SERVICE_ENDPOINT_HERE",
    "LLM_SERVICE_API_KEY": "YOUR_LLM_SERVICE_API_KEY_HERE",
    "LLM_SERVICE_PLANNING_MODEL_NAME": "YOUR_LLM_SERVICE_PLANNING_MODEL_NAME_HERE",
    "LLM_SERVICE_GENERAL_MODEL_NAME": "YOUR_LLM_SERVICE_GENERAL_MODEL_NAME_HERE",
    "NAMESPACE": "my_project_namespace/",
    "SOLACE_BROKER_URL": "ws://localhost:8008",
    "SOLACE_BROKER_VPN": "default",
    "SOLACE_BROKER_USERNAME": "default",
    "SOLACE_BROKER_PASSWORD": "default",
    "SOLACE_DEV_MODE": "false",
    "SESSION_SECRET_KEY": "please_change_me_in",
    "FASTAPI_HOST": "127.0.0.1",
    "FASTAPI_PORT": "8000",
    "FASTAPI_HTTPS_PORT": "8443",
    "ENABLE_EMBED_RESOLUTION": "true",
    "SSL_KEYFILE": "",
    "SSL_CERTFILE": "",
    "SSL_KEYFILE_PASSWORD": "",
    "LOGGING_CONFIG_PATH": "configs/logging_config.yaml",
    "S3_BUCKET_NAME": "",
    "S3_ENDPOINT_URL": "",
    "S3_REGION": "us-east-1",
    "PLATFORM_SERVICE_URL": None,
    "LLM_SERVICE_OAUTH_TOKEN_URL": "YOUR_LLM_SERVICE_OAUTH_TOKEN_URL_HERE",
    "LLM_SERVICE_OAUTH_CLIENT_ID": "YOUR_LLM_SERVICE_OAUTH_CLIENT_ID_HERE",
    "LLM_SERVICE_OAUTH_CLIENT_SECRET": "YOUR_LLM_SERVICE_OAUTH_CLIENT_SECRET_HERE",
    "LLM_SERVICE_OAUTH_SCOPE": "",
    "LLM_SERVICE_OAUTH_CA_CERT_PATH": "",
    "LLM_SERVICE_OAUTH_TOKEN_REFRESH_BUFFER_SECONDS": "300",
    "LLM_SERVICE_OAUTH_PLANNING_MODEL_NAME": "YOUR_LLM_SERVICE_OAUTH_PLANNING_MODEL_NAME_HERE",
    "LLM_SERVICE_OAUTH_GENERAL_MODEL_NAME": "YOUR_LLM_SERVICE_OAUTH_GENERAL_MODEL_NAME_HERE",
    "LLM_SERVICE_OAUTH_ENDPOINT": "YOUR_LLM_SERVICE_OAUTH_ENDPOINT_HERE",
    "PLATFORM_API_HOST": "127.0.0.1",
    "PLATFORM_API_PORT": "8001",
}


def create_env_file(project_root: Path, options: dict, skip_interactive: bool) -> bool:
    """
    Creates the .env file, using ask_if_not_provided to get values.
    The 'options' dict contains values from CLI args or web_init.
    Returns True on success, False on failure.
    """
    env_path = project_root / ".env"
    click.echo("Configuring .env file...")

    env_params_config = [
        (
            "llm_service_endpoint",
            "LLM_SERVICE_ENDPOINT",
            "Enter LLM Service Endpoint URL",
            False,
            "LLM_SERVICE_ENDPOINT",
        ),
        (
            "llm_service_api_key",
            "LLM_SERVICE_API_KEY",
            "Enter LLM Service API Key",
            True,
            "LLM_SERVICE_API_KEY",
        ),
        (
            "llm_service_planning_model_name",
            "LLM_SERVICE_PLANNING_MODEL_NAME",
            "Enter LLM Planning Model Name (e.g., openai/gpt-4o)",
            False,
            "LLM_SERVICE_PLANNING_MODEL_NAME",
        ),
        (
            "llm_service_general_model_name",
            "LLM_SERVICE_GENERAL_MODEL_NAME",
            "Enter LLM General Model Name (e.g., openai/gpt-3.5-turbo)",
            False,
            "LLM_SERVICE_GENERAL_MODEL_NAME",
        ),
        (
            "namespace",
            "NAMESPACE",
            "Enter Namespace for the project (e.g., my_project)",
            False,
            "NAMESPACE",
        ),
        (
            "broker_url",
            "SOLACE_BROKER_URL",
            "Solace Broker URL",
            False,
            "SOLACE_BROKER_URL",
        ),
        (
            "broker_vpn",
            "SOLACE_BROKER_VPN",
            "Solace Broker VPN",
            False,
            "SOLACE_BROKER_VPN",
        ),
        (
            "broker_username",
            "SOLACE_BROKER_USERNAME",
            "Solace Broker Username",
            False,
            "SOLACE_BROKER_USERNAME",
        ),
        (
            "broker_password",
            "SOLACE_BROKER_PASSWORD",
            "Solace Broker Password",
            True,
            "SOLACE_BROKER_PASSWORD",
        ),
        (
            "dev_mode",
            "SOLACE_DEV_MODE",
            "Enable Solace Dev Mode (true/false)",
            False,
            "SOLACE_DEV_MODE",
        ),
        (
            "webui_session_secret_key",
            "SESSION_SECRET_KEY",
            "Enter Web UI Session Secret Key",
            True,
            "SESSION_SECRET_KEY",
        ),
        (
            "webui_fastapi_host",
            "FASTAPI_HOST",
            "Enter Web UI FastAPI Host",
            False,
            "FASTAPI_HOST",
        ),
        (
            "webui_fastapi_port",
            "FASTAPI_PORT",
            "Enter Web UI FastAPI Port",
            False,
            "FASTAPI_PORT",
        ),
        (
            "webui_fastapi_https_port",
            "FASTAPI_HTTPS_PORT",
            "Enter Web UI FastAPI HTTPS Port",
            False,
            "FASTAPI_HTTPS_PORT",
        ),
        (
            "webui_ssl_keyfile",
            "SSL_KEYFILE",
            "Enter SSL Key File Path",
            False,
            "SSL_KEYFILE",
        ),
        (
            "webui_ssl_certfile",
            "SSL_CERTFILE",
            "Enter SSL Certificate File Path",
            False,
            "SSL_CERTFILE",
        ),
        (
            "webui_ssl_keyfile_password",
            "SSL_KEYFILE_PASSWORD",
            "Enter SSL Key File Passphrase",
            True,
            "SSL_KEYFILE_PASSWORD",
        ),
        (
            "webui_enable_embed_resolution",
            "ENABLE_EMBED_RESOLUTION",
            "Enable Embed Resolution for Web UI? (true/false)",
            False,
            "ENABLE_EMBED_RESOLUTION",
        ),
        (
            "logging_config_path",
            "LOGGING_CONFIG_PATH",
            "Enter Logging Config Path",
            False,
            "LOGGING_CONFIG_PATH",
        ),
        (
            "s3_bucket_name",
            "S3_BUCKET_NAME",
            "Enter S3 Bucket Name (for S3 artifact service)",
            False,
            "S3_BUCKET_NAME",
        ),
        (
            "s3_endpoint_url",
            "S3_ENDPOINT_URL",
            "Enter S3 Endpoint URL (for S3-compatible services, leave empty for AWS S3)",
            False,
            "S3_ENDPOINT_URL",
        ),
        (
            "s3_region",
            "S3_REGION",
            "Enter S3 Region (for S3 artifact service)",
            False,
            "S3_REGION",
        ),
        (
            "platform_api_host",
            "PLATFORM_API_HOST",
            "Enter Platform API Host",
            False,
            "PLATFORM_API_HOST",
        ),
        (
            "platform_api_port",
            "PLATFORM_API_PORT",
            "Enter Platform API Port",
            False,
            "PLATFORM_API_PORT",
        ),
    ]

    env_vars_to_write = {}

    for opt_key, env_name, prompt, is_secret, default_key in env_params_config:
        ask_if_not_provided(
            options,
            opt_key,
            prompt,
            default=ENV_DEFAULTS.get(default_key),
            none_interactive=skip_interactive,
            hide_input=is_secret,
        )
        env_vars_to_write[env_name] = options.get(opt_key)

    if (
        env_vars_to_write.get("NAMESPACE")
        and env_vars_to_write["NAMESPACE"] != ENV_DEFAULTS.get("NAMESPACE")
        and not str(env_vars_to_write["NAMESPACE"]).endswith("/")
    ):
        env_vars_to_write["NAMESPACE"] = str(env_vars_to_write["NAMESPACE"]) + "/"

    # Handle Platform Service URL generation
    frontend_is_ssl = env_vars_to_write.get("SSL_CERTFILE") and env_vars_to_write.get("SSL_KEYFILE")
    if not env_vars_to_write.get("PLATFORM_SERVICE_URL"):
        platform_url = "https://" if frontend_is_ssl else "http://"
        platform_url += env_vars_to_write.get("PLATFORM_API_HOST") or "127.0.0.1"
        platform_url += ":" + str(env_vars_to_write.get("PLATFORM_API_PORT") or 8001)
        env_vars_to_write["PLATFORM_SERVICE_URL"] = platform_url

    final_env_vars = {k: v for k, v in env_vars_to_write.items() if v is not None}
    env_content_lines = [f'{key}="{value}"' for key, value in final_env_vars.items()]

    try:
        with open(env_path, "w", encoding="utf-8") as f:
            f.write("\n".join(env_content_lines) + "\n")
        click.echo(f"  Created: {env_path.relative_to(project_root)}")
        return True
    except IOError as e:
        click.echo(
            click.style(f"Error creating file {env_path}: {e}", fg="red"), err=True
        )
        return False
