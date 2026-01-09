
DEFAULT_COMMUNICATION_TIMEOUT = 600  # 10 minutes
HEALTH_CHECK_TTL_SECONDS = 60  # 60 seconds - time after which a health check is considered stale
HEALTH_CHECK_INTERVAL_SECONDS = 10  # 10 seconds - interval between health checks
TEXT_ARTIFACT_CONTEXT_MAX_LENGTH_CAPACITY = 200000  # maximum number of characters that can be loaded from a text artifact
TEXT_ARTIFACT_CONTEXT_DEFAULT_LENGTH = 100000  # default number of characters to load from a text artifact

# Extension URIs
EXTENSION_URI_SCHEMAS = "https://solace.com/a2a/extensions/sam/schemas"
EXTENSION_URI_AGENT_TYPE = "https://solace.com/a2a/extensions/agent-type"
