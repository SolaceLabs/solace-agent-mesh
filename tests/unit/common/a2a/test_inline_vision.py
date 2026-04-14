"""
Tests for inline vision feature — both Layer 1 (force-inline on first message)
and Layer 2 (on-demand via load_artifact tool).

These tests verify:
1. Image files are inlined when enable_inline_vision=True
2. Non-image files fall back to text metadata
3. Limits (max_inline_vision_images, max_inline_vision_bytes) are enforced
4. The LiteLLM layer creates multipart tool messages for vision data URLs
5. The _sanitize_bytes_in_dict helper works correctly
6. The _vision_image_data_url key is detected and handled in tool responses
"""

import base64
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any, Optional

from google.genai import types as adk_types

# ─── Test helpers ───────────────────────────────────────────────────────────

def _make_png_bytes(size: int = 100) -> bytes:
    """Create fake PNG bytes of a given size."""
    # Minimal PNG header + padding
    header = b"\x89PNG\r\n\x1a\n"
    return header + b"\x00" * (size - len(header))


def _make_mock_component(
    enable_inline_vision: bool = False,
    max_inline_vision_images: int = 5,
    max_inline_vision_bytes: int = 20971520,
    agent_name: str = "TestAgent",
):
    """Create a mock SamAgentComponent with inline vision config."""
    component = MagicMock()
    component.log_identifier = "[TestComponent]"
    component.enable_inline_vision = enable_inline_vision
    component.max_inline_vision_images = max_inline_vision_images
    component.max_inline_vision_bytes = max_inline_vision_bytes
    component.get_config = MagicMock(side_effect=lambda key, default=None: {
        "agent_name": agent_name,
        "enable_inline_vision": enable_inline_vision,
        "max_inline_vision_images": max_inline_vision_images,
        "max_inline_vision_bytes": max_inline_vision_bytes,
    }.get(key, default))
    component.artifact_service = MagicMock()
    return component


# ─── Layer 1 Tests: _prepare_a2a_filepart_for_adk ──────────────────────────

class TestPrepareFilePartForADK:
    """Tests for _prepare_a2a_filepart_for_adk with inline vision."""

    @pytest.mark.asyncio
    async def test_image_inlined_when_vision_enabled(self):
        """When enable_inline_vision=True and file is an image, return inline_data Part."""
        from solace_agent_mesh.common.a2a.translation import _prepare_a2a_filepart_for_adk
        from a2a.types import FilePart, FileWithBytes

        png_bytes = _make_png_bytes(200)
        b64_bytes = base64.b64encode(png_bytes).decode("utf-8")
        part = FilePart(file=FileWithBytes(bytes=b64_bytes, name="test.png", mime_type="image/png"))
        component = _make_mock_component(enable_inline_vision=True)

        # Mock save_artifact_with_metadata to succeed (patched at source module)
        with patch(
            "solace_agent_mesh.agent.utils.artifact_helpers.save_artifact_with_metadata",
            new_callable=AsyncMock,
            return_value={"status": "success", "data_version": 0},
        ):
            result = await _prepare_a2a_filepart_for_adk(
                part, component, "user1", "session1"
            )

        assert result is not None
        assert result.inline_data is not None
        assert result.inline_data.mime_type == "image/png"
        assert result.inline_data.data == png_bytes
        assert result.text is None  # Should NOT be text

    @pytest.mark.asyncio
    async def test_non_image_returns_text_when_vision_enabled(self):
        """Non-image files should still return text metadata even with vision enabled."""
        from solace_agent_mesh.common.a2a.translation import _prepare_a2a_filepart_for_adk
        from a2a.types import FilePart, FileWithBytes

        csv_bytes = b"col1,col2\nval1,val2"
        b64_bytes = base64.b64encode(csv_bytes).decode("utf-8")
        part = FilePart(file=FileWithBytes(bytes=b64_bytes, name="data.csv", mime_type="text/csv"))
        component = _make_mock_component(enable_inline_vision=True)

        with patch(
            "solace_agent_mesh.agent.utils.artifact_helpers.save_artifact_with_metadata",
            new_callable=AsyncMock,
            return_value={"status": "success", "data_version": 0},
        ), patch(
            "solace_agent_mesh.agent.utils.artifact_helpers.load_artifact_content_or_metadata",
            new_callable=AsyncMock,
            return_value={"status": "success", "metadata": {"filename": "data.csv"}},
        ):
            result = await _prepare_a2a_filepart_for_adk(
                part, component, "user1", "session1"
            )

        assert result is not None
        assert result.text is not None  # Should be text metadata
        assert result.inline_data is None

    @pytest.mark.asyncio
    async def test_image_returns_text_when_vision_disabled(self):
        """Images should return text metadata when enable_inline_vision=False."""
        from solace_agent_mesh.common.a2a.translation import _prepare_a2a_filepart_for_adk
        from a2a.types import FilePart, FileWithBytes

        png_bytes = _make_png_bytes(200)
        b64_bytes = base64.b64encode(png_bytes).decode("utf-8")
        part = FilePart(file=FileWithBytes(bytes=b64_bytes, name="test.png", mime_type="image/png"))
        component = _make_mock_component(enable_inline_vision=False)

        with patch(
            "solace_agent_mesh.agent.utils.artifact_helpers.save_artifact_with_metadata",
            new_callable=AsyncMock,
            return_value={"status": "success", "data_version": 0},
        ), patch(
            "solace_agent_mesh.agent.utils.artifact_helpers.load_artifact_content_or_metadata",
            new_callable=AsyncMock,
            return_value={"status": "success", "metadata": {"filename": "test.png"}},
        ):
            result = await _prepare_a2a_filepart_for_adk(
                part, component, "user1", "session1"
            )

        assert result is not None
        assert result.text is not None  # Should be text metadata
        assert result.inline_data is None


class TestInlineVisionLimits:
    """Tests for max_inline_vision_images and max_inline_vision_bytes limits."""

    @pytest.mark.asyncio
    async def test_max_images_limit_enforced(self):
        """After max_inline_vision_images, additional images fall back to text."""
        from solace_agent_mesh.common.a2a.translation import _prepare_a2a_filepart_for_adk
        from a2a.types import FilePart, FileWithBytes

        component = _make_mock_component(
            enable_inline_vision=True,
            max_inline_vision_images=2,
        )

        tracker = {"images_inlined": 0, "bytes_inlined": 0}
        results = []

        for i in range(3):
            png_bytes = _make_png_bytes(100)
            b64_bytes = base64.b64encode(png_bytes).decode("utf-8")
            part = FilePart(file=FileWithBytes(
                bytes=b64_bytes, name=f"img{i}.png", mime_type="image/png"
            ))

            with patch(
                "solace_agent_mesh.agent.utils.artifact_helpers.save_artifact_with_metadata",
                new_callable=AsyncMock,
                return_value={"status": "success", "data_version": 0},
            ), patch(
                "solace_agent_mesh.agent.utils.artifact_helpers.load_artifact_content_or_metadata",
                new_callable=AsyncMock,
                return_value={"status": "success", "metadata": {"filename": f"img{i}.png"}},
            ):
                result = await _prepare_a2a_filepart_for_adk(
                    part, component, "user1", "session1",
                    inline_vision_tracker=tracker,
                )
                results.append(result)

        # First 2 should be inline_data
        assert results[0].inline_data is not None
        assert results[1].inline_data is not None
        # Third should fall back to text
        assert results[2].text is not None
        assert results[2].inline_data is None
        # Tracker should show 2 images inlined
        assert tracker["images_inlined"] == 2

    @pytest.mark.asyncio
    async def test_max_bytes_limit_enforced(self):
        """After max_inline_vision_bytes, additional images fall back to text."""
        from solace_agent_mesh.common.a2a.translation import _prepare_a2a_filepart_for_adk
        from a2a.types import FilePart, FileWithBytes

        component = _make_mock_component(
            enable_inline_vision=True,
            max_inline_vision_bytes=50,  # Very small limit — less than one image
        )

        tracker = {"images_inlined": 0, "bytes_inlined": 0}
        results = []

        for i in range(2):
            png_bytes = _make_png_bytes(100)
            b64_bytes = base64.b64encode(png_bytes).decode("utf-8")
            part = FilePart(file=FileWithBytes(
                bytes=b64_bytes, name=f"img{i}.png", mime_type="image/png"
            ))

            with patch(
                "solace_agent_mesh.agent.utils.artifact_helpers.save_artifact_with_metadata",
                new_callable=AsyncMock,
                return_value={"status": "success", "data_version": 0},
            ), patch(
                "solace_agent_mesh.agent.utils.artifact_helpers.load_artifact_content_or_metadata",
                new_callable=AsyncMock,
                return_value={"status": "success", "metadata": {"filename": f"img{i}.png"}},
            ):
                result = await _prepare_a2a_filepart_for_adk(
                    part, component, "user1", "session1",
                    inline_vision_tracker=tracker,
                )
                results.append(result)

        # First should be inline_data (0 bytes < 50 limit, so it proceeds)
        assert results[0].inline_data is not None
        # Second should fall back to text (100 bytes >= 50 limit, exceeded)
        assert results[1].text is not None
        assert results[1].inline_data is None


# ─── Layer 2 Tests: LiteLLM multipart tool messages ───────────────────────

class TestLiteLLMVisionToolMessages:
    """Tests for _content_to_message_param handling of _vision_image_data_url."""

    def test_tool_response_with_vision_data_url_creates_tool_plus_user_messages(self):
        """Tool response with _vision_image_data_url should create tool msg + user msg with image."""
        from solace_agent_mesh.agent.adk.models.lite_llm import _content_to_message_param

        data_url = "data:image/png;base64,iVBORw0KGgo="
        response_data = {
            "status": "success",
            "message": "Image loaded",
            "filename": "test.png",
            "_vision_image_data_url": data_url,
        }

        content = adk_types.Content(
            role="tool",
            parts=[
                adk_types.Part(
                    function_response=adk_types.FunctionResponse(
                        id="call_123",
                        name="load_artifact",
                        response=response_data,
                    )
                )
            ],
        )

        result = _content_to_message_param(content)
        # Should be a list of 2 messages: tool + user
        assert isinstance(result, list)
        assert len(result) == 2

        # First: tool message with text-only content
        tool_msg = result[0]
        assert tool_msg["role"] == "tool"
        assert tool_msg["tool_call_id"] == "call_123"
        assert isinstance(tool_msg["content"], str)
        text_data = json.loads(tool_msg["content"])
        assert text_data["status"] == "success"
        assert "_vision_image_data_url" not in text_data

        # Second: user message with image
        user_msg = result[1]
        assert user_msg["role"] == "user"
        assert isinstance(user_msg["content"], list)
        assert len(user_msg["content"]) == 2
        assert user_msg["content"][0]["type"] == "text"
        assert user_msg["content"][1]["type"] == "image_url"
        assert user_msg["content"][1]["image_url"] == {"url": data_url}

    def test_tool_response_without_vision_data_url_is_text_only(self):
        """Normal tool response without _vision_image_data_url should be text-only."""
        from solace_agent_mesh.agent.adk.models.lite_llm import _content_to_message_param

        response_data = {
            "status": "success",
            "message": "Loaded text file",
            "content": "Hello world",
        }

        content = adk_types.Content(
            role="tool",
            parts=[
                adk_types.Part(
                    function_response=adk_types.FunctionResponse(
                        id="call_456",
                        name="load_artifact",
                        response=response_data,
                    )
                )
            ],
        )

        result = _content_to_message_param(content)
        assert isinstance(result, dict)
        assert result["role"] == "tool"
        # Content should be a string (not a list)
        assert isinstance(result["content"], str)
        parsed = json.loads(result["content"])
        assert parsed["status"] == "success"


# ─── Bytes sanitization tests ─────────────────────────────────────────────

def _sanitize_bytes_in_dict(obj):
    """Local copy of the helper for testing (callbacks.py has heavy deps)."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(value, (bytes, bytearray)):
                obj[key] = f"<binary data: {len(value)} bytes>"
            elif isinstance(value, (dict, list)):
                _sanitize_bytes_in_dict(value)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            if isinstance(item, (bytes, bytearray)):
                obj[i] = f"<binary data: {len(item)} bytes>"
            elif isinstance(item, (dict, list)):
                _sanitize_bytes_in_dict(item)


class TestSanitizeBytesInDict:
    """Tests for _sanitize_bytes_in_dict helper."""

    def test_sanitizes_bytes_in_flat_dict(self):
        data = {"text": "hello", "image": b"\x89PNG\r\n\x1a\n" + b"\x00" * 92}
        _sanitize_bytes_in_dict(data)
        assert data["text"] == "hello"
        assert isinstance(data["image"], str)
        assert "100 bytes" in data["image"]

    def test_sanitizes_bytes_in_nested_dict(self):
        data = {"outer": {"inner": b"\x00" * 50}}
        _sanitize_bytes_in_dict(data)
        assert isinstance(data["outer"]["inner"], str)
        assert "50 bytes" in data["outer"]["inner"]

    def test_sanitizes_bytes_in_list(self):
        data = [b"\x00" * 10, "text", {"key": b"\x00" * 20}]
        _sanitize_bytes_in_dict(data)
        assert isinstance(data[0], str)
        assert "10 bytes" in data[0]
        assert data[1] == "text"
        assert isinstance(data[2]["key"], str)
        assert "20 bytes" in data[2]["key"]

    def test_no_change_for_dict_without_bytes(self):
        data = {"text": "hello", "number": 42, "nested": {"key": "value"}}
        original = json.dumps(data)
        _sanitize_bytes_in_dict(data)
        assert json.dumps(data) == original


# ─── Image artifact detection tests ───────────────────────────────────────

class TestIsImageArtifact:
    """Tests for is_image_artifact helper used in inline vision."""

    def test_png_detected(self):
        from solace_agent_mesh.common.utils.mime_helpers import is_image_artifact
        assert is_image_artifact("photo.png", "image/png") is True

    def test_jpg_detected(self):
        from solace_agent_mesh.common.utils.mime_helpers import is_image_artifact
        assert is_image_artifact("photo.jpg", "image/jpeg") is True

    def test_webp_detected(self):
        from solace_agent_mesh.common.utils.mime_helpers import is_image_artifact
        assert is_image_artifact("photo.webp", "image/webp") is True

    def test_svg_excluded(self):
        from solace_agent_mesh.common.utils.mime_helpers import is_image_artifact
        assert is_image_artifact("diagram.svg", "image/svg+xml") is False

    def test_csv_not_image(self):
        from solace_agent_mesh.common.utils.mime_helpers import is_image_artifact
        assert is_image_artifact("data.csv", "text/csv") is False

    def test_filename_fallback_when_no_mime(self):
        from solace_agent_mesh.common.utils.mime_helpers import is_image_artifact
        assert is_image_artifact("photo.png", None) is True

    def test_non_image_filename_when_no_mime(self):
        from solace_agent_mesh.common.utils.mime_helpers import is_image_artifact
        assert is_image_artifact("data.csv", None) is False
