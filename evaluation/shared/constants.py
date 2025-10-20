import os
from enum import Enum

EVALUATION_DIR = os.path.dirname(os.path.abspath(__file__))

# Timeouts and Delays
DEFAULT_STARTUP_WAIT_TIME = 60
DEFAULT_TEST_TIMEOUT = 60
DEFAULT_CONNECTION_TIMEOUT = 30
DEFAULT_RECONNECT_ATTEMPTS = 3
DEFAULT_RECONNECT_DELAY = 1.0
DEFAULT_WAIT_TIME = 60

# Test Suite Defaults
DEFAULT_RESULTS_DIR = "tests"
DEFAULT_RUN_COUNT = 1

# Test Case Defaults
DEFAULT_CATEGORY = "Other"
DEFAULT_DESCRIPTION = "No description provided."
MAX_WAIT_TIME = 300

# Validation
BROKER_REQUIRED_FIELDS = ["host", "vpn_name", "username", "password"]
REMOTE_REQUIRED_FIELDS = ["EVAL_REMOTE_URL", "EVAL_NAMESPACE"]


# Subscription Defaults
ALLOWED_TOPIC_INFIXES: list[str] = [
    "/agent/request/",
    "/gateway/status/",
    "/gateway/response/",
]
BLOCKED_TOPIC_INFIXES: list[str] = ["/discovery/"]
MESSAGE_TIMEOUT: int = 1000


class ConnectionState(Enum):
    """Represents the connection state of the subscriber."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTING = "disconnecting"
    ERROR = "error"
