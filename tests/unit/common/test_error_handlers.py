"""Tests for centralized error handlers."""

import pytest
from litellm.exceptions import (
    AuthenticationError,
    BadRequestError,
    BudgetExceededError,
    ContentPolicyViolationError,
    ContextWindowExceededError,
    APIConnectionError,
    InternalServerError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    ServiceUnavailableError,
    Timeout,
)

from solace_agent_mesh.common.error_handlers import (
    AUTHENTICATION_ERROR_MESSAGE,
    API_CONNECTION_ERROR_MESSAGE,
    BUDGET_EXCEEDED_ERROR_MESSAGE,
    CONTENT_POLICY_VIOLATION_MESSAGE,
    CONTEXT_LIMIT_ERROR_MESSAGE,
    DEFAULT_BAD_REQUEST_MESSAGE,
    DEFAULT_LLM_ERROR_MESSAGE,
    INTERNAL_SERVER_ERROR_MESSAGE,
    LITELLM_EXCEPTIONS,
    NOT_FOUND_ERROR_MESSAGE,
    PERMISSION_DENIED_ERROR_MESSAGE,
    RATE_LIMIT_ERROR_MESSAGE,
    SERVICE_UNAVAILABLE_ERROR_MESSAGE,
    TIMEOUT_ERROR_MESSAGE,
    get_error_message,
    is_llm_exception,
    _is_context_limit_error,
    _get_user_friendly_error_message,
)


class _MockResponse:
    """Minimal mock for httpx.Response needed by some litellm exceptions."""

    def __init__(self):
        self.request = type("Request", (), {"method": "POST", "url": "http://test"})()
        self.status_code = 403
        self.headers = {"x-request-id": "test"}


def _make_litellm_exception(cls, message="test error"):
    """Helper to create litellm exception instances with required args."""
    if cls is BudgetExceededError:
        return cls(message=message, current_cost=1.0, max_budget=0.5)
    if cls is PermissionDeniedError:
        return cls(
            message=message,
            model="test-model",
            llm_provider="test",
            response=_MockResponse(),
        )
    try:
        return cls(message=message, model="test-model", llm_provider="test")
    except TypeError:
        try:
            return cls(message=message)
        except TypeError:
            return cls(message)


class TestIsLlmException:
    """Tests for is_llm_exception()."""

    @pytest.mark.parametrize(
        "exc_class",
        [
            AuthenticationError,
            BadRequestError,
            BudgetExceededError,
            ContentPolicyViolationError,
            ContextWindowExceededError,
            APIConnectionError,
            InternalServerError,
            NotFoundError,
            PermissionDeniedError,
            RateLimitError,
            ServiceUnavailableError,
            Timeout,
        ],
    )
    def test_recognizes_litellm_exceptions(self, exc_class):
        exc = _make_litellm_exception(exc_class)
        assert is_llm_exception(exc) is True

    def test_rejects_plain_exception(self):
        assert is_llm_exception(Exception("some error")) is False

    def test_rejects_value_error(self):
        assert is_llm_exception(ValueError("bad value")) is False

    def test_rejects_runtime_error(self):
        assert is_llm_exception(RuntimeError("runtime")) is False


class TestIsContextLimitError:
    """Tests for _is_context_limit_error()."""

    def test_context_window_exceeded_error(self):
        exc = _make_litellm_exception(ContextWindowExceededError)
        assert _is_context_limit_error(exc) is True

    @pytest.mark.parametrize(
        "pattern",
        [
            "too many tokens",
            "expected maxLength: 12345",
            "input is too long",
            "prompt is too long",
            "prompt: length: 1..",
            "too many input tokens",
        ],
    )
    def test_pattern_based_detection(self, pattern):
        exc = _make_litellm_exception(BadRequestError, message=pattern)
        assert _is_context_limit_error(exc) is True

    def test_non_context_bad_request(self):
        exc = _make_litellm_exception(BadRequestError, message="invalid parameter")
        assert _is_context_limit_error(exc) is False

    def test_non_bad_request_exception(self):
        assert _is_context_limit_error(Exception("too many tokens")) is False

    def test_auth_error_not_context_limit(self):
        exc = _make_litellm_exception(AuthenticationError)
        assert _is_context_limit_error(exc) is False


class TestGetErrorMessage:
    """Tests for get_error_message()."""

    def test_context_limit_error(self):
        exc = _make_litellm_exception(
            ContextWindowExceededError, message="context window exceeded"
        )
        message, is_context = get_error_message(exc)
        assert message == CONTEXT_LIMIT_ERROR_MESSAGE
        assert is_context is True

    def test_context_limit_via_pattern(self):
        exc = _make_litellm_exception(
            BadRequestError, message="too many tokens in request"
        )
        message, is_context = get_error_message(exc)
        assert message == CONTEXT_LIMIT_ERROR_MESSAGE
        assert is_context is True

    def test_content_policy_violation(self):
        exc = _make_litellm_exception(ContentPolicyViolationError)
        message, is_context = get_error_message(exc)
        assert message == CONTENT_POLICY_VIOLATION_MESSAGE
        assert is_context is False

    def test_bad_request_error(self):
        exc = _make_litellm_exception(
            BadRequestError, message="invalid parameter value"
        )
        message, is_context = get_error_message(exc)
        assert message == DEFAULT_BAD_REQUEST_MESSAGE
        assert is_context is False

    def test_authentication_error(self):
        exc = _make_litellm_exception(AuthenticationError)
        message, is_context = get_error_message(exc)
        assert message == AUTHENTICATION_ERROR_MESSAGE
        assert is_context is False

    def test_rate_limit_error(self):
        exc = _make_litellm_exception(RateLimitError)
        message, is_context = get_error_message(exc)
        assert message == RATE_LIMIT_ERROR_MESSAGE
        assert is_context is False

    def test_service_unavailable_error(self):
        exc = _make_litellm_exception(ServiceUnavailableError)
        message, is_context = get_error_message(exc)
        assert message == SERVICE_UNAVAILABLE_ERROR_MESSAGE
        assert is_context is False

    def test_api_connection_error(self):
        exc = _make_litellm_exception(APIConnectionError)
        message, is_context = get_error_message(exc)
        assert message == API_CONNECTION_ERROR_MESSAGE
        assert is_context is False

    def test_timeout_error(self):
        exc = _make_litellm_exception(Timeout)
        message, is_context = get_error_message(exc)
        assert message == TIMEOUT_ERROR_MESSAGE
        assert is_context is False

    def test_not_found_error(self):
        exc = _make_litellm_exception(NotFoundError)
        message, is_context = get_error_message(exc)
        assert message == NOT_FOUND_ERROR_MESSAGE
        assert is_context is False

    def test_permission_denied_error(self):
        exc = _make_litellm_exception(PermissionDeniedError)
        message, is_context = get_error_message(exc)
        assert message == PERMISSION_DENIED_ERROR_MESSAGE
        assert is_context is False

    def test_internal_server_error(self):
        exc = _make_litellm_exception(InternalServerError)
        message, is_context = get_error_message(exc)
        assert message == INTERNAL_SERVER_ERROR_MESSAGE
        assert is_context is False

    def test_budget_exceeded_error(self):
        exc = _make_litellm_exception(BudgetExceededError)
        message, is_context = get_error_message(exc)
        assert message == BUDGET_EXCEEDED_ERROR_MESSAGE
        assert is_context is False

    def test_unknown_exception_fallback(self):
        exc = Exception("something unexpected")
        message, is_context = get_error_message(exc)
        assert message == DEFAULT_LLM_ERROR_MESSAGE
        assert is_context is False

    def test_content_policy_not_treated_as_bad_request(self):
        """ContentPolicyViolationError is a subclass of BadRequestError,
        but should get its own specific message."""
        exc = _make_litellm_exception(ContentPolicyViolationError)
        message, _ = get_error_message(exc)
        assert message != DEFAULT_BAD_REQUEST_MESSAGE
        assert message == CONTENT_POLICY_VIOLATION_MESSAGE


class TestLitellmExceptionsTuple:
    """Tests for the LITELLM_EXCEPTIONS tuple."""

    def test_is_a_tuple(self):
        assert isinstance(LITELLM_EXCEPTIONS, tuple)

    def test_contains_all_expected_types(self):
        expected = {
            AuthenticationError,
            BadRequestError,
            BudgetExceededError,
            ContentPolicyViolationError,
            ContextWindowExceededError,
            APIConnectionError,
            InternalServerError,
            NotFoundError,
            PermissionDeniedError,
            RateLimitError,
            ServiceUnavailableError,
            Timeout,
        }
        assert set(LITELLM_EXCEPTIONS) == expected

    def test_all_are_exception_classes(self):
        for exc_class in LITELLM_EXCEPTIONS:
            assert issubclass(exc_class, BaseException)

    def test_can_be_used_in_except_clause(self):
        """Verify the tuple works as an except clause target."""
        exc = _make_litellm_exception(AuthenticationError)
        caught = False
        try:
            raise exc
        except LITELLM_EXCEPTIONS:
            caught = True
        assert caught is True

    def test_does_not_catch_non_litellm_exception(self):
        """Verify the tuple does not catch unrelated exceptions."""
        caught = False
        try:
            raise ValueError("not an LLM error")
        except LITELLM_EXCEPTIONS:
            caught = True
        except ValueError:
            pass
        assert caught is False


class TestGetUserFriendlyErrorMessage:
    """Tests for _get_user_friendly_error_message() dispatch."""

    @pytest.mark.parametrize(
        "exc_class, expected_message",
        [
            (AuthenticationError, AUTHENTICATION_ERROR_MESSAGE),
            (RateLimitError, RATE_LIMIT_ERROR_MESSAGE),
            (ServiceUnavailableError, SERVICE_UNAVAILABLE_ERROR_MESSAGE),
            (APIConnectionError, API_CONNECTION_ERROR_MESSAGE),
            (Timeout, TIMEOUT_ERROR_MESSAGE),
            (NotFoundError, NOT_FOUND_ERROR_MESSAGE),
            (PermissionDeniedError, PERMISSION_DENIED_ERROR_MESSAGE),
            (InternalServerError, INTERNAL_SERVER_ERROR_MESSAGE),
            (BudgetExceededError, BUDGET_EXCEEDED_ERROR_MESSAGE),
            (ContentPolicyViolationError, CONTENT_POLICY_VIOLATION_MESSAGE),
        ],
    )
    def test_each_exception_gets_specific_message(self, exc_class, expected_message):
        exc = _make_litellm_exception(exc_class)
        assert _get_user_friendly_error_message(exc) == expected_message

    def test_bad_request_non_context_limit(self):
        exc = _make_litellm_exception(BadRequestError, message="some bad request")
        assert _get_user_friendly_error_message(exc) == DEFAULT_BAD_REQUEST_MESSAGE

    def test_bad_request_context_limit_returns_context_message(self):
        exc = _make_litellm_exception(
            BadRequestError, message="too many tokens in request"
        )
        assert _get_user_friendly_error_message(exc) == CONTEXT_LIMIT_ERROR_MESSAGE

    def test_unknown_exception_returns_default(self):
        assert _get_user_friendly_error_message(RuntimeError("oops")) == DEFAULT_LLM_ERROR_MESSAGE

    def test_all_messages_are_actionable(self):
        """Every error message should be actionable — contain guidance for the user."""
        actionable_keywords = ["administrator", "rephrase", "start a new conversation"]
        for exc_class in LITELLM_EXCEPTIONS:
            exc = _make_litellm_exception(exc_class)
            msg = _get_user_friendly_error_message(exc)
            assert any(kw in msg for kw in actionable_keywords), (
                f"{exc_class.__name__} message is not actionable: {msg}"
            )

    def test_no_message_exposes_raw_exception(self):
        """Error messages should not include raw exception repr."""
        for exc_class in LITELLM_EXCEPTIONS:
            exc = _make_litellm_exception(exc_class, message="SECRET_API_KEY_12345")
            msg = _get_user_friendly_error_message(exc)
            assert "SECRET_API_KEY_12345" not in msg, (
                f"{exc_class.__name__} leaks raw exception details"
            )
