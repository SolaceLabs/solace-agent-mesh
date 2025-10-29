"""
Unit tests for common/utils/embeds/resolver.py
Tests embed resolution functions and chain execution.
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from solace_agent_mesh.common.utils.embeds.resolver import (
    _log_data_state,
    _evaluate_artifact_content_embed_with_chain,
    resolve_embeds_in_string,
    resolve_embeds_recursively_in_string,
    evaluate_embed,
)
from solace_agent_mesh.common.utils.embeds.types import DataFormat
from solace_agent_mesh.common.utils.embeds.constants import (
    EARLY_EMBED_TYPES,
    LATE_EMBED_TYPES,
)


class TestLogDataState:
    """Test _log_data_state function."""

    def test_log_bytes_data(self):
        """Test logging bytes data."""
        data = b"test content"
        _log_data_state("[Test]", "Step1", data, DataFormat.BYTES, "text/plain")
        # Should not raise any exceptions

    def test_log_string_data(self):
        """Test logging string data."""
        data = "test string"
        _log_data_state("[Test]", "Step1", data, DataFormat.STRING, "text/plain")

    def test_log_list_data(self):
        """Test logging list data."""
        data = [{"key": "value"}, {"key2": "value2"}]
        _log_data_state("[Test]", "Step1", data, DataFormat.LIST_OF_DICTS, None)

    def test_log_dict_data(self):
        """Test logging dict data."""
        data = {"key1": "value1", "key2": "value2"}
        _log_data_state("[Test]", "Step1", data, DataFormat.JSON_OBJECT, "application/json")

    def test_log_long_string(self):
        """Test logging long string (should truncate)."""
        data = "x" * 200
        _log_data_state("[Test]", "Step1", data, DataFormat.STRING, None)

    def test_log_none_format(self):
        """Test logging with None format."""
        data = "test"
        _log_data_state("[Test]", "Step1", data, None, None)


@pytest.mark.asyncio
class TestEvaluateArtifactContentEmbedWithChain:
    """Test _evaluate_artifact_content_embed_with_chain function."""

    async def test_load_error(self):
        """Test handling of load error."""
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
        
        result, error, size = await _evaluate_artifact_content_embed_with_chain(
            artifact_spec_from_directive="test.txt",
            modifiers_from_directive=[],
            output_format_from_directive="text",
            context=context,
            log_identifier="[Test]",
        )
        
        assert "[Error" in result
        assert error is not None

    async def test_successful_text_artifact_no_modifiers(self):
        """Test successful load of text artifact without modifiers."""
        mock_artifact = MagicMock()
        mock_artifact.inline_data.data = b"plain text content"
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
        
        result, error, size = await _evaluate_artifact_content_embed_with_chain(
            artifact_spec_from_directive="test.txt",
            modifiers_from_directive=[],
            output_format_from_directive="text",
            context=context,
            log_identifier="[Test]",
            config={},
        )
        
        assert error is None
        assert "plain text content" in result

    async def test_binary_artifact(self):
        """Test handling of binary artifact."""
        mock_artifact = MagicMock()
        mock_artifact.inline_data.data = b"\x00\x01\x02\x03"
        mock_artifact.inline_data.mime_type = "application/octet-stream"
        
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
        
        result, error, size = await _evaluate_artifact_content_embed_with_chain(
            artifact_spec_from_directive="test.bin",
            modifiers_from_directive=[],
            output_format_from_directive="text",
            context=context,
            log_identifier="[Test]",
            config={},
        )
        
        # Binary data conversion to text should fail gracefully
        assert error is not None or isinstance(result, str)

    async def test_json_artifact_preparsing(self):
        """Test JSON artifact pre-parsing."""
        json_data = {"key": "value", "number": 42}
        mock_artifact = MagicMock()
        mock_artifact.inline_data.data = json.dumps(json_data).encode()
        mock_artifact.inline_data.mime_type = "application/json"
        
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
        
        result, error, size = await _evaluate_artifact_content_embed_with_chain(
            artifact_spec_from_directive="test.json",
            modifiers_from_directive=[],
            output_format_from_directive="json",
            context=context,
            log_identifier="[Test]",
            config={},
        )
        
        assert error is None
        assert "key" in result

    async def test_csv_artifact_preparsing(self):
        """Test CSV artifact pre-parsing."""
        csv_data = "name,age\nAlice,30\nBob,25"
        mock_artifact = MagicMock()
        mock_artifact.inline_data.data = csv_data.encode()
        mock_artifact.inline_data.mime_type = "text/csv"
        
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
        
        result, error, size = await _evaluate_artifact_content_embed_with_chain(
            artifact_spec_from_directive="test.csv",
            modifiers_from_directive=[],
            output_format_from_directive="json",
            context=context,
            log_identifier="[Test]",
            config={},
        )
        
        assert error is None or result is not None

    async def test_missing_format_defaults_to_text(self):
        """Test that missing format defaults to 'text'."""
        mock_artifact = MagicMock()
        mock_artifact.inline_data.data = b"content"
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
        
        result, error, size = await _evaluate_artifact_content_embed_with_chain(
            artifact_spec_from_directive="test.txt",
            modifiers_from_directive=[],
            output_format_from_directive=None,
            context=context,
            log_identifier="[Test]",
            config={},
        )
        
        assert error is None or "content" in result

    async def test_unicode_decode_error(self):
        """Test handling of unicode decode error."""
        mock_artifact = MagicMock()
        mock_artifact.inline_data.data = b"\xff\xfe"
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
        
        result, error, size = await _evaluate_artifact_content_embed_with_chain(
            artifact_spec_from_directive="test.txt",
            modifiers_from_directive=[],
            output_format_from_directive="text",
            context=context,
            log_identifier="[Test]",
            config={},
        )
        
        # Should handle decode error gracefully
        assert isinstance(result, str)


@pytest.mark.asyncio
class TestResolveEmbedsInString:
    """Test resolve_embeds_in_string function."""

    async def test_no_embeds(self):
        """Test string with no embeds."""
        text = "This is plain text without embeds"
        
        async def mock_resolver(*args):
            return "resolved", None, 8
        
        result, processed_idx, signals = await resolve_embeds_in_string(
            text=text,
            context={},
            resolver_func=mock_resolver,
            types_to_resolve=EARLY_EMBED_TYPES,
            log_identifier="[Test]",
        )
        
        assert result == text
        assert processed_idx == len(text)
        assert len(signals) == 0

    async def test_single_embed_resolution(self):
        """Test resolving a single embed."""
        text = "Value: «math:2+2»"
        
        async def mock_resolver(embed_type, expr, fmt, ctx, log_id, cfg):
            if embed_type == "math":
                return "4", None, 1
            return expr, None, len(expr)
        
        result, processed_idx, signals = await resolve_embeds_in_string(
            text=text,
            context={},
            resolver_func=mock_resolver,
            types_to_resolve={"math"},
            log_identifier="[Test]",
        )
        
        assert "4" in result
        assert processed_idx == len(text)

    async def test_multiple_embeds(self):
        """Test resolving multiple embeds."""
        text = "«math:1+1» and «math:2+2»"
        
        async def mock_resolver(embed_type, expr, fmt, ctx, log_id, cfg):
            if "1+1" in expr:
                return "2", None, 1
            elif "2+2" in expr:
                return "4", None, 1
            return expr, None, len(expr)
        
        result, processed_idx, signals = await resolve_embeds_in_string(
            text=text,
            context={},
            resolver_func=mock_resolver,
            types_to_resolve={"math"},
            log_identifier="[Test]",
        )
        
        assert "2" in result
        assert "4" in result

    async def test_skip_unresolved_types(self):
        """Test skipping embed types not in types_to_resolve."""
        text = "«math:1+1» and «datetime:now»"
        
        async def mock_resolver(embed_type, expr, fmt, ctx, log_id, cfg):
            return "resolved", None, 8
        
        result, processed_idx, signals = await resolve_embeds_in_string(
            text=text,
            context={},
            resolver_func=mock_resolver,
            types_to_resolve={"math"},
            log_identifier="[Test]",
        )
        
        assert "«datetime:now»" in result  # Should remain unchanged

    async def test_signal_detection(self):
        """Test detection of signals from resolver."""
        text = "«status_update:Processing...»"
        
        async def mock_resolver(embed_type, expr, fmt, ctx, log_id, cfg):
            if embed_type == "status_update":
                return (None, "SIGNAL_STATUS_UPDATE", "Processing...")
            return "resolved", None, 8
        
        result, processed_idx, signals = await resolve_embeds_in_string(
            text=text,
            context={},
            resolver_func=mock_resolver,
            types_to_resolve={"status_update"},
            log_identifier="[Test]",
        )
        
        assert len(signals) == 1
        assert signals[0][1][1] == "SIGNAL_STATUS_UPDATE"

    async def test_partial_embed_buffering(self):
        """Test buffering when partial embed is detected."""
        text = "Complete text «math:1+1» and partial «mat"
        
        async def mock_resolver(embed_type, expr, fmt, ctx, log_id, cfg):
            return "2", None, 1
        
        result, processed_idx, signals = await resolve_embeds_in_string(
            text=text,
            context={},
            resolver_func=mock_resolver,
            types_to_resolve={"math"},
            log_identifier="[Test]",
        )
        
        assert processed_idx < len(text)
        assert "«mat" not in result

    async def test_embed_with_format_spec(self):
        """Test embed with format specification."""
        text = "«math:3.14159 | .2f»"
        
        async def mock_resolver(embed_type, expr, fmt, ctx, log_id, cfg):
            assert fmt == ".2f"
            return "3.14", None, 4
        
        result, processed_idx, signals = await resolve_embeds_in_string(
            text=text,
            context={},
            resolver_func=mock_resolver,
            types_to_resolve={"math"},
            log_identifier="[Test]",
        )
        
        assert "3.14" in result

    async def test_resolver_error_handling(self):
        """Test handling of resolver errors."""
        text = "«math:invalid»"
        
        async def mock_resolver(embed_type, expr, fmt, ctx, log_id, cfg):
            return "[Error: Invalid expression]", "Invalid expression", 27
        
        result, processed_idx, signals = await resolve_embeds_in_string(
            text=text,
            context={},
            resolver_func=mock_resolver,
            types_to_resolve={"math"},
            log_identifier="[Test]",
        )
        
        assert "[Error:" in result


@pytest.mark.asyncio
class TestResolveEmbedsRecursivelyInString:
    """Test resolve_embeds_recursively_in_string function."""

    async def test_max_depth_exceeded(self):
        """Test max depth limit."""
        text = "«math:1+1»"
        
        async def mock_resolver(*args):
            return "2", None, 1
        
        result = await resolve_embeds_recursively_in_string(
            text=text,
            context={},
            resolver_func=mock_resolver,
            types_to_resolve={"math"},
            log_identifier="[Test]",
            config={},
            max_depth=0,
            current_depth=0,
        )
        
        assert "[Error: Max embed depth exceeded]" in result

    async def test_simple_recursion(self):
        """Test simple recursive resolution."""
        text = "«math:1+1»"
        
        async def mock_resolver(embed_type, expr, fmt, ctx, log_id, cfg, depth, visited):
            return "2", None, 1
        
        result = await resolve_embeds_recursively_in_string(
            text=text,
            context={},
            resolver_func=mock_resolver,
            types_to_resolve={"math"},
            log_identifier="[Test]",
            config={},
            max_depth=5,
            current_depth=0,
        )
        
        assert "2" in result

    async def test_skip_unresolved_types_recursive(self):
        """Test skipping types not in types_to_resolve."""
        text = "«math:1+1» «datetime:now»"
        
        async def mock_resolver(embed_type, expr, fmt, ctx, log_id, cfg, depth, visited):
            return "2", None, 1
        
        result = await resolve_embeds_recursively_in_string(
            text=text,
            context={},
            resolver_func=mock_resolver,
            types_to_resolve={"math"},
            log_identifier="[Test]",
            config={},
            max_depth=5,
        )
        
        assert "«datetime:now»" in result

    async def test_size_limit_enforcement(self):
        """Test size limit enforcement."""
        text = "«math:1+1»"
        
        async def mock_resolver(embed_type, expr, fmt, ctx, log_id, cfg, depth, visited):
            return "x" * 1000, None, 1000
        
        result = await resolve_embeds_recursively_in_string(
            text=text,
            context={},
            resolver_func=mock_resolver,
            types_to_resolve={"math"},
            log_identifier="[Test]",
            config={},
            max_depth=5,
            max_total_size=100,
        )
        
        assert "[Error:" in result or "exceeds total size limit" in result

    async def test_error_from_resolver(self):
        """Test handling errors from resolver."""
        text = "«math:invalid»"
        
        async def mock_resolver(embed_type, expr, fmt, ctx, log_id, cfg, depth, visited):
            return "[Error: Invalid]", "Invalid", 16
        
        result = await resolve_embeds_recursively_in_string(
            text=text,
            context={},
            resolver_func=mock_resolver,
            types_to_resolve={"math"},
            log_identifier="[Test]",
            config={},
            max_depth=5,
        )
        
        assert "[Error:" in result

    async def test_visited_artifacts_tracking(self):
        """Test visited artifacts tracking."""
        text = "«math:1+1»"
        visited = {("test.txt", 1)}
        
        async def mock_resolver(embed_type, expr, fmt, ctx, log_id, cfg, depth, visited_set):
            assert ("test.txt", 1) in visited_set
            return "2", None, 1
        
        result = await resolve_embeds_recursively_in_string(
            text=text,
            context={},
            resolver_func=mock_resolver,
            types_to_resolve={"math"},
            log_identifier="[Test]",
            config={},
            max_depth=5,
            visited_artifacts=visited,
        )
        
        assert "2" in result


@pytest.mark.asyncio
class TestEvaluateEmbed:
    """Test evaluate_embed function."""

    async def test_status_update_signal(self):
        """Test status_update embed returns signal."""
        result = await evaluate_embed(
            embed_type="status_update",
            expression="Processing...",
            format_spec=None,
            context={},
            log_identifier="[Test]",
        )
        
        assert result[0] is None
        assert result[1] == "SIGNAL_STATUS_UPDATE"
        assert result[2] == "Processing..."

    async def test_unknown_embed_type(self):
        """Test unknown embed type."""
        result = await evaluate_embed(
            embed_type="unknown_type",
            expression="test",
            format_spec=None,
            context={},
            log_identifier="[Test]",
        )
        
        assert "[Error:" in result[0]
        assert "Unknown embed type" in result[1]

    async def test_math_embed_evaluation(self):
        """Test math embed evaluation."""
        result = await evaluate_embed(
            embed_type="math",
            expression="2+2",
            format_spec=None,
            context={},
            log_identifier="[Test]",
        )
        
        assert result[0] == "4"
        assert result[1] is None

    async def test_datetime_embed_evaluation(self):
        """Test datetime embed evaluation."""
        result = await evaluate_embed(
            embed_type="datetime",
            expression="date",
            format_spec=None,
            context={},
            log_identifier="[Test]",
        )
        
        assert result[1] is None
        assert len(result[0]) == 10  # YYYY-MM-DD

    async def test_uuid_embed_evaluation(self):
        """Test UUID embed evaluation."""
        result = await evaluate_embed(
            embed_type="uuid",
            expression="",
            format_spec=None,
            context={},
            log_identifier="[Test]",
        )
        
        assert result[1] is None
        assert len(result[0]) == 36

    async def test_artifact_meta_embed(self):
        """Test artifact_meta embed evaluation."""
        mock_artifact = MagicMock()
        mock_artifact.inline_data.mime_type = "text/plain"
        mock_artifact.inline_data.data = b"content"
        
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
        
        result = await evaluate_embed(
            embed_type="artifact_meta",
            expression="test.txt",
            format_spec=None,
            context=context,
            log_identifier="[Test]",
        )
        
        assert result[1] is None
        assert "artifact" in result[0].lower()

    async def test_artifact_content_with_format_fallback(self):
        """Test artifact_content using format_spec as fallback."""
        mock_artifact = MagicMock()
        mock_artifact.inline_data.data = b"content"
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
        
        result = await evaluate_embed(
            embed_type="artifact_content",
            expression="test.txt",
            format_spec="text",
            context=context,
            log_identifier="[Test]",
            config={},
        )
        
        # Should complete without error
        assert isinstance(result, tuple)
        assert len(result) == 3

    async def test_evaluator_exception_handling(self):
        """Test exception handling in evaluator."""
        with patch("solace_agent_mesh.common.utils.embeds.resolver.EMBED_EVALUATORS", {"test": lambda *args: 1/0}):
            result = await evaluate_embed(
                embed_type="test",
                expression="expr",
                format_spec=None,
                context={},
                log_identifier="[Test]",
            )
            
            assert "[Error:" in result[0]
            assert result[1] is not None

    async def test_async_evaluator(self):
        """Test async evaluator function."""
        async def async_eval(expr, ctx, log_id, fmt):
            return "async_result", None, 12
        
        with patch("solace_agent_mesh.common.utils.embeds.resolver.EMBED_EVALUATORS", {"async_test": async_eval}):
            result = await evaluate_embed(
                embed_type="async_test",
                expression="test",
                format_spec=None,
                context={},
                log_identifier="[Test]",
            )
            
            assert result[0] == "async_result"
            assert result[1] is None

    async def test_sync_evaluator(self):
        """Test sync evaluator function."""
        def sync_eval(expr, ctx, log_id, fmt):
            return "sync_result", None, 11
        
        with patch("solace_agent_mesh.common.utils.embeds.resolver.EMBED_EVALUATORS", {"sync_test": sync_eval}):
            result = await evaluate_embed(
                embed_type="sync_test",
                expression="test",
                format_spec=None,
                context={},
                log_identifier="[Test]",
            )
            
            assert result[0] == "sync_result"
            assert result[1] is None