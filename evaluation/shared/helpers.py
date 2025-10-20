import os

from dotenv import load_dotenv


def get_local_base_url() -> str:
    """
    Constructs the local API base URL from environment variables.
    """
    load_dotenv()
    host = os.getenv("REST_API_HOST", "0.0.0.0")
    port = os.getenv("REST_API_PORT", "8080")
    return f"http://{host}:{port}"
