"""
Unit tests for common/utils/embeds/evaluators.py
Tests individual evaluator functions for different embed types.
"""

import pytest
import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from solace_agent_mesh.common.utils.embeds.evaluators import (
    _evaluate_math_embed,
    _evaluate_datetime_embed,
    _evaluate_uuid_embed,
    _evaluate_artifact_meta_embed,
    _evaluate_artifact_content_embed,
    EMBED_EVALUATORS,
    MATH_SAFE_SYMBOLS,
)


class TestMathEvaluator:
    """Test _evaluate_math_embed function."""

    def test_simple_arithmetic(self):
        """Test basic arithmetic operations."""
        result, error, size = _evaluate_math_embed("2 + 2", None, "[Test]")
        assert result == "4"
        assert error is None
        assert size == len("4".encode("utf-8"))

    def test_complex_expression(self):
        """Test complex mathematical expression."""
        result, error, size = _evaluate_math_embed("sqrt(16) + pow(2, 3)", None, "[Test]")
        assert result == "12.0"
        assert error is None

    def test_trigonometric_functions(self):
        """Test trigonometric functions."""
        result, error, size = _evaluate_math_embed("sin(0)", None, "[Test]")
        assert result == "0.0"
        assert error is None

    def test_math_constants(self):
        """Test math constants."""
        result, error, size = _evaluate_math_embed("pi", None, "[Test]")
        assert "3.14" in result
        assert error is None

    def test_format_spec_integer(self):
        """Test format specification for integers."""
        result, error, size = _evaluate_math_embed("42", None, "[Test]", ".2f")
        assert result == "42.00"
        assert error is None

    def test_format_spec_float(self):
        """Test format specification for floats."""
        result, error, size = _evaluate_math_embed("3.14159", None, "[Test]", ".2f")
        assert result == "3.14"
        assert error is None

    def test_invalid_format_spec(self):
        """Test invalid format specification falls back to str()."""
        result, error, size = _evaluate_math_embed("42", None, "[Test]", "invalid")
        assert result == "42"
        assert error is None

    def test_math_error(self):
        """Test math evaluation error."""
        result, error, size = _evaluate_math_embed("1/0", None, "[Test]")
        assert "[Error:" in result
        assert error is not None

    def test_syntax_error(self):
        """Test syntax error in expression."""
        result, error, size = _evaluate_math_embed("2 +", None, "[Test]")
        assert "[Error:" in result
        assert error is not None

    def test_undefined_variable(self):
        """Test undefined variable error."""
        result, error, size = _evaluate_math_embed("undefined_var", None, "[Test]")
        assert "[Error:" in result
        assert error is not None

    def test_random_functions(self):
        """Test random functions are available."""
        result, error, size = _evaluate_math_embed("randint(1, 10)", None, "[Test]")
        assert error is None
        assert 1 <= int(result) <= 10

    def test_hyperbolic_functions(self):
        """Test hyperbolic functions."""
        result, error, size = _evaluate_math_embed("sinh(0)", None, "[Test]")
        assert result == "0.0"
        assert error is None

    def test_factorial(self):
        """Test factorial function."""
        result, error, size = _evaluate_math_embed("factorial(5)", None, "[Test]")
        assert result == "120"
        assert error is None

    def test_min_max_functions(self):
        """Test min and max functions."""
        result, error, size = _evaluate_math_embed("max(1, 5, 3)", None, "[Test]")
        assert result == "5"
        assert error is None


class TestDatetimeEvaluator:
    """Test _evaluate_datetime_embed function."""

    def test_default_iso_format(self):
        """Test default ISO format."""
        result, error, size = _evaluate_datetime_embed("", None, "[Test]")
        assert error is None
        assert "T" in result  # ISO format contains T

    def test_now_format(self):
        """Test 'now' format."""
        result, error, size = _evaluate_datetime_embed("now", None, "[Test]")
        assert error is None
        assert "T" in result

    def test_iso_format(self):
        """Test 'iso' format."""
        result, error, size = _evaluate_datetime_embed("iso", None, "[Test]")
        assert error is None
        assert "T" in result

    def test_timestamp_format(self):
        """Test 'timestamp' format."""
        result, error, size = _evaluate_datetime_embed("timestamp", None, "[Test]")
        assert error is None
        assert result.replace(".", "").isdigit()

    def test_date_format(self):
        """Test 'date' format."""
        result, error, size = _evaluate_datetime_embed("date", None, "[Test]")
        assert error is None
        assert len(result) == 10  # YYYY-MM-DD
        assert result.count("-") == 2

    def test_time_format(self):
        """Test 'time' format."""
        result, error, size = _evaluate_datetime_embed("time", None, "[Test]")
        assert error is None
        assert result.count(":") == 2  # HH:MM:SS

    def test_custom_format(self):
        """Test custom strftime format."""
        result, error, size = _evaluate_datetime_embed("%Y-%m-%d", None, "[Test]")
        assert error is None
        assert len(result) == 10

    def test_invalid_format(self):
        """Test invalid format string."""
        result, error, size = _evaluate_datetime_embed("%Z%Z%Z", None, "[Test]")
        # Should handle gracefully, might succeed or fail depending on platform
        assert isinstance(result, str)

    def test_format_spec_ignored(self):
        """Test that format_spec parameter is ignored."""
        result1, _, _ = _evaluate_datetime_embed("date", None, "[Test]", None)
        result2, _, _ = _evaluate_datetime_embed("date", None, "[Test]", "ignored")
        # Both should produce date format
        assert len(result1) == 10
        assert len(result2) == 10


class TestUuidEvaluator:
    """Test _evaluate_uuid_embed function."""

    def test_uuid_generation(self):
        """Test UUID generation."""
        result, error, size = _evaluate_uuid_embed("", None, "[Test]")
        assert error is None
        assert len(result) == 36  # UUID4 format
        assert result.count("-") == 4

    def test_uuid_uniqueness(self):
        """Test that UUIDs are unique."""
        result1, _, _ = _evaluate_uuid_embed("", None, "[Test]")
        result2, _, _ = _evaluate_uuid_embed("", None, "[Test]")
        assert result1 != result2

    def test_format_spec_ignored(self):
        """Test that format_spec is ignored."""
        result, error, size = _evaluate_uuid_embed("", None, "[Test]", "ignored")
        assert error is None
        assert len(result) == 36


@pytest.mark.asyncio
class TestArtifactMetaEvaluator:
    """Test _evaluate_artifact_meta_embed function."""

    async def test_invalid_context_type(self):
        """Test with invalid context type."""
        result, error, size = await _evaluate_artifact_meta_embed(
            "test.txt", "not_a_dict", "[Test]"
        )
        assert "[Error:" in result
        assert "Invalid context type" in error

    async def test_missing_artifact_service(self):
        """Test with missing artifact service."""
        context = {"session_context": {}}
        result, error, size = await _evaluate_artifact_meta_embed(
            "test.txt", context, "[Test]"
        )
        assert "[Error:" in result
        assert "ArtifactService not available" in error

    async def test_missing_session_context(self):
        """Test with missing session context."""
        context = {"artifact_service": MagicMock()}
        result, error, size = await _evaluate_artifact_meta_embed(
            "test.txt", context, "[Test]"
        )
        assert "[Error:" in result
        assert "Session context" in error

    async def test_missing_session_identifiers(self):
        """Test with missing session identifiers."""
        context = {
            "artifact_service": MagicMock(),
            "session_context": {"app_name": "test"},
        }
        result, error, size = await _evaluate_artifact_meta_embed(
            "test.txt", context, "[Test]"
        )
        assert "[Error:" in result
        assert "Missing app_name, user_id, or session_id" in error

    async def test_missing_filename(self):
        """Test with missing filename."""
        context = {
            "artifact_service": MagicMock(),
            "session_context": {
                "app_name": "test",
                "user_id": "user1",
                "session_id": "session1",
            },
        }
        result, error, size = await _evaluate_artifact_meta_embed("", context, "[Test]")
        assert "[Error:" in result
        assert "Filename missing" in error

    async def test_artifact_not_found(self):
        """Test with artifact not found."""
        mock_service = AsyncMock()
        mock_service.list_versions.return_value = []
        context = {
            "artifact_service": mock_service,
            "session_context": {
                "app_name": "test",
                "user_id": "user1",
                "session_id": "session1",
            },
        }
        result, error, size = await _evaluate_artifact_meta_embed(
            "test.txt", context, "[Test]"
        )
        assert "[Error:" in result
        assert "not found" in error

    async def test_invalid_version_format(self):
        """Test with invalid version format."""
        mock_service = AsyncMock()
        context = {
            "artifact_service": mock_service,
            "session_context": {
                "app_name": "test",
                "user_id": "user1",
                "session_id": "session1",
            },
        }
        result, error, size = await _evaluate_artifact_meta_embed(
            "test.txt:invalid", context, "[Test]"
        )
        assert "[Error:" in result
        assert "Invalid version" in error

    async def test_successful_metadata_retrieval(self):
        """Test successful metadata retrieval."""
        mock_artifact = MagicMock()
        mock_artifact.inline_data.mime_type = "text/plain"
        mock_artifact.inline_data.data = b"test content"

        mock_service = AsyncMock()
        mock_service.list_versions.return_value = [1, 2, 3]
        mock_service.load_artifact.return_value = mock_artifact

        context = {
            "artifact_service": mock_service,
            "session_context": {
                "app_name": "test",
                "user_id": "user1",
                "session_id": "session1",
            },
        }
        result, error, size = await _evaluate_artifact_meta_embed(
            "test.txt", context, "[Test]"
        )
        assert error is None
        assert "artifact" in result.lower()
        assert "(v" in result.lower()  # Check for version format like (v3)

    async def test_with_companion_metadata(self):
        """Test with companion metadata file."""
        mock_artifact = MagicMock()
        mock_artifact.inline_data.mime_type = "text/plain"
        mock_artifact.inline_data.data = b"test content"

        mock_metadata = MagicMock()
        mock_metadata.inline_data.data = json.dumps({"custom": "metadata"}).encode()

        mock_service = AsyncMock()
        mock_service.list_versions.return_value = [1]
        mock_service.load_artifact.side_effect = [mock_artifact, mock_metadata]

        context = {
            "artifact_service": mock_service,
            "session_context": {
                "app_name": "test",
                "user_id": "user1",
                "session_id": "session1",
            },
        }
        result, error, size = await _evaluate_artifact_meta_embed(
            "test.txt:1", context, "[Test]"
        )
        assert error is None
        assert "custom" in result.lower()


@pytest.mark.asyncio
class TestArtifactContentEvaluator:
    """Test _evaluate_artifact_content_embed function."""

    async def test_chain_delimiter_in_expression(self):
        """Test error when chain delimiter is in expression."""
        result, mime, error = await _evaluate_artifact_content_embed(
            "test.txt>>>invalid", {}, "[Test]"
        )
        assert result is None
        assert mime is None
        assert "chain delimiter" in error

    async def test_invalid_context_type(self):
        """Test with invalid context type."""
        result, mime, error = await _evaluate_artifact_content_embed(
            "test.txt", "not_a_dict", "[Test]"
        )
        assert result is None
        assert "Invalid context" in error

    async def test_missing_artifact_service(self):
        """Test with missing artifact service."""
        context = {"session_context": {}}
        result, mime, error = await _evaluate_artifact_content_embed(
            "test.txt", context, "[Test]"
        )
        assert result is None
        assert "ArtifactService" in error

    async def test_missing_session_identifiers(self):
        """Test with missing session identifiers."""
        context = {
            "artifact_service": MagicMock(),
            "session_context": {"app_name": "test"},
        }
        result, mime, error = await _evaluate_artifact_content_embed(
            "test.txt", context, "[Test]"
        )
        assert result is None
        assert "Missing required session identifiers" in error

    async def test_missing_filename(self):
        """Test with missing filename."""
        context = {
            "artifact_service": MagicMock(),
            "session_context": {
                "app_name": "test",
                "user_id": "user1",
                "session_id": "session1",
            },
        }
        result, mime, error = await _evaluate_artifact_content_embed(
            "", context, "[Test]"
        )
        assert result is None
        assert "Filename missing" in error

    async def test_invalid_version_format(self):
        """Test with invalid version format."""
        mock_service = AsyncMock()
        context = {
            "artifact_service": mock_service,
            "session_context": {
                "app_name": "test",
                "user_id": "user1",
                "session_id": "session1",
            },
        }
        result, mime, error = await _evaluate_artifact_content_embed(
            "test.txt:invalid", context, "[Test]"
        )
        assert result is None
        assert "Invalid version format" in error

    async def test_artifact_not_found_no_versions(self):
        """Test with artifact not found (no versions)."""
        mock_service = AsyncMock()
        mock_service.list_versions.return_value = []
        context = {
            "artifact_service": mock_service,
            "session_context": {
                "app_name": "test",
                "user_id": "user1",
                "session_id": "session1",
            },
        }
        result, mime, error = await _evaluate_artifact_content_embed(
            "test.txt", context, "[Test]"
        )
        assert result is None
        assert "not found" in error

    async def test_successful_content_load(self):
        """Test successful artifact content load."""
        mock_artifact = MagicMock()
        mock_artifact.inline_data.data = b"test content"
        mock_artifact.inline_data.mime_type = "text/plain"

        mock_service = AsyncMock()
        mock_service.list_versions.return_value = [1, 2]
        mock_service.load_artifact.return_value = mock_artifact

        context = {
            "artifact_service": mock_service,
            "session_context": {
                "app_name": "test",
                "user_id": "user1",
                "session_id": "session1",
            },
        }
        result, mime, error = await _evaluate_artifact_content_embed(
            "test.txt", context, "[Test]"
        )
        assert result == b"test content"
        assert mime == "text/plain"
        assert error is None

    async def test_with_specific_version(self):
        """Test loading specific version."""
        mock_artifact = MagicMock()
        mock_artifact.inline_data.data = b"version 1 content"
        mock_artifact.inline_data.mime_type = "text/plain"

        mock_service = AsyncMock()
        mock_service.load_artifact.return_value = mock_artifact

        context = {
            "artifact_service": mock_service,
            "session_context": {
                "app_name": "test",
                "user_id": "user1",
                "session_id": "session1",
            },
        }
        result, mime, error = await _evaluate_artifact_content_embed(
            "test.txt:1", context, "[Test]"
        )
        assert result == b"version 1 content"
        assert error is None

    async def test_size_limit_exceeded(self):
        """Test size limit exceeded."""
        large_content = b"x" * 10000
        mock_artifact = MagicMock()
        mock_artifact.inline_data.data = large_content
        mock_artifact.inline_data.mime_type = "text/plain"

        mock_service = AsyncMock()
        mock_service.list_versions.return_value = [1]
        mock_service.load_artifact.return_value = mock_artifact

        context = {
            "artifact_service": mock_service,
            "session_context": {
                "app_name": "test",
                "user_id": "user1",
                "session_id": "session1",
            },
        }
        config = {"gateway_max_artifact_resolve_size_bytes": 100}
        result, mime, error = await _evaluate_artifact_content_embed(
            "test.txt", context, "[Test]", config
        )
        assert result is None
        assert "exceeds maximum size limit" in error

    async def test_artifact_empty(self):
        """Test with empty artifact."""
        mock_artifact = MagicMock()
        mock_artifact.inline_data = None

        mock_service = AsyncMock()
        mock_service.list_versions.return_value = [1]
        mock_service.load_artifact.return_value = mock_artifact

        context = {
            "artifact_service": mock_service,
            "session_context": {
                "app_name": "test",
                "user_id": "user1",
                "session_id": "session1",
            },
        }
        result, mime, error = await _evaluate_artifact_content_embed(
            "test.txt", context, "[Test]"
        )
        assert result is None
        assert "not found or empty" in error

    async def test_file_not_found_exception(self):
        """Test FileNotFoundError handling."""
        mock_service = AsyncMock()
        mock_service.list_versions.return_value = [1]
        mock_service.load_artifact.side_effect = FileNotFoundError()

        context = {
            "artifact_service": mock_service,
            "session_context": {
                "app_name": "test",
                "user_id": "user1",
                "session_id": "session1",
            },
        }
        result, mime, error = await _evaluate_artifact_content_embed(
            "test.txt", context, "[Test]"
        )
        assert result is None
        assert "not found" in error


class TestEmbedEvaluators:
    """Test EMBED_EVALUATORS dictionary."""

    def test_evaluators_registered(self):
        """Test that all expected evaluators are registered."""
        assert "math" in EMBED_EVALUATORS
        assert "datetime" in EMBED_EVALUATORS
        assert "uuid" in EMBED_EVALUATORS
        assert "artifact_meta" in EMBED_EVALUATORS

    def test_math_safe_symbols(self):
        """Test that MATH_SAFE_SYMBOLS contains expected functions."""
        assert "sin" in MATH_SAFE_SYMBOLS
        assert "cos" in MATH_SAFE_SYMBOLS
        assert "sqrt" in MATH_SAFE_SYMBOLS
        assert "pi" in MATH_SAFE_SYMBOLS
        assert "random" in MATH_SAFE_SYMBOLS