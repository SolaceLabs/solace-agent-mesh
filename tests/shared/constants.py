"""Shared test constants across all SAM tests."""


class TestIds:
    """Standard test IDs for use in tests."""

    NONEXISTENT_ID = "00000000-0000-0000-0000-000000000000"
    DEFAULT_USER = "sam_dev_user"
    SECONDARY_USER = "secondary_user"
    TEST_SESSION_PREFIX = "test-session-"
    TEST_TASK_PREFIX = "task-"
    TEST_PROJECT_PREFIX = "test-project-"


class HttpStatus:
    """HTTP status codes for API testing."""

    OK = 200
    CREATED = 201
    ACCEPTED = 202
    NO_CONTENT = 204
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    CONFLICT = 409
    UNPROCESSABLE_ENTITY = 422
    INTERNAL_SERVER_ERROR = 500


class TestPaths:
    """Common test file paths."""

    SAMPLE_PDF = "sample.pdf"
    SAMPLE_DOCX = "sample.docx"
    SAMPLE_TXT = "sample.txt"


class AgentDefaults:
    """Default values for agent testing."""

    DEFAULT_AGENT_NAME = "TestAgent"
    DEFAULT_NAMESPACE = "test_namespace"
    DEFAULT_MODEL = "openai/test-model"
    DEFAULT_TIMEOUT = 30.0


class GatewayDefaults:
    """Default values for gateway testing."""

    DEFAULT_GATEWAY_ID = "TestGateway"
    DEFAULT_USER_ID = "test-user@example.com"
