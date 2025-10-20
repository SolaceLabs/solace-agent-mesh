import logging
import os

from dotenv import load_dotenv

log = logging.getLogger(__name__)


def get_local_base_url() -> str:
    """
    Constructs the local API base URL from environment variables.
    """
    load_dotenv()
    host = os.getenv("REST_API_HOST", "0.0.0.0")
    port = os.getenv("REST_API_PORT", "8080")
    return f"http://{host}:{port}"


def resolve_env_vars(data: dict) -> dict:
    """
    Resolves environment variables in a dictionary.
    Looks for keys ending in _VAR and replaces them with the corresponding environment variable value.
    """
    resolved = {}
    for key, value in data.items():
        if key.endswith("_VAR"):
            env_var_name = key[:-4]  # Remove '_VAR' suffix
            env_value = os.getenv(value)
            if not env_value:
                log.warning(f"Environment variable '{value}' not set for {env_var_name}")
            resolved[env_var_name] = env_value
        else:
            # This is a direct value, include it as-is
            resolved[key] = value
    return resolved
