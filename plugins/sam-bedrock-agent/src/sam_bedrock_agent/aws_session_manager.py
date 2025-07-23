import boto3
from botocore.config import Config
from solace_ai_connector.common.log import log


class AWSSessionManager:
    _instance = None
    _session = None
    _bedrock_agent_runtime_client = None
    _boto3_config = None
    _endpoint_url = None

    def __new__(cls, boto3_config: dict = None, endpoint_url: str = None):
        if cls._instance is None:
            cls._instance = super(AWSSessionManager, cls).__new__(cls)
            if boto3_config:
                cls._initialize_session(boto3_config, endpoint_url)
        return cls._instance

    @classmethod
    def _initialize_session(cls, boto3_config: dict, endpoint_url: str = None):
        """
        Initializes the boto3 session and client.
        This method should only be called once.
        """
        if cls._session is None:
            log.info(
                f"[AWSSessionManager] Initializing AWS session with config: {boto3_config}, endpoint_url: {endpoint_url}"
            )
            cls._boto3_config = boto3_config
            cls._endpoint_url = endpoint_url
            try:
                cls._session = boto3.Session(**boto3_config)

                client_config_params = {}
                if endpoint_url:
                    client_config_params["endpoint_url"] = endpoint_url

                cls._bedrock_agent_runtime_client = cls._session.client(
                    "bedrock-agent-runtime", **client_config_params
                )
                log.info(
                    "[AWSSessionManager] AWS session and Bedrock Agent Runtime client initialized successfully."
                )
            except Exception as e:
                log.error(
                    f"[AWSSessionManager] Failed to initialize AWS session or client: {e}",
                    exc_info=True,
                )
                cls._session = None
                cls._bedrock_agent_runtime_client = None
                cls._instance = None
                raise
        else:
            log.warn(
                "[AWSSessionManager] AWS session already initialized. Skipping re-initialization."
            )

    @classmethod
    def get_bedrock_agent_runtime_client(cls):
        """
        Returns the bedrock-agent-runtime client.
        Initializes the session if it hasn't been already, requiring prior config.
        """
        if cls._instance is None:
            log.error(
                "[AWSSessionManager] AWSSessionManager not initialized. Call with boto3_config first."
            )
            raise RuntimeError(
                "AWSSessionManager not initialized. Please ensure it's initialized with configuration first."
            )

        if cls._bedrock_agent_runtime_client is None:
            if cls._boto3_config:
                log.warn(
                    "[AWSSessionManager] Bedrock client not available, attempting re-initialization."
                )
                cls._initialize_session(cls._boto3_config, cls._endpoint_url)
            else:
                log.error(
                    "[AWSSessionManager] Bedrock client not available and no configuration to initialize."
                )
                raise RuntimeError(
                    "Bedrock client not available and no configuration to initialize."
                )

        return cls._bedrock_agent_runtime_client

    @classmethod
    def is_initialized(cls) -> bool:
        """Checks if the session manager has been initialized."""
        return (
            cls._session is not None and cls._bedrock_agent_runtime_client is not None
        )


def get_aws_session_manager(
    boto3_config: dict = None, endpoint_url: str = None
) -> AWSSessionManager:
    """
    Gets the singleton instance of AWSSessionManager.
    If boto3_config is provided and the manager is not yet initialized,
    it will initialize the session.
    """
    if not AWSSessionManager.is_initialized() and boto3_config:
        return AWSSessionManager(boto3_config=boto3_config, endpoint_url=endpoint_url)
    elif AWSSessionManager.is_initialized():
        return AWSSessionManager()
    else:
        return AWSSessionManager()
