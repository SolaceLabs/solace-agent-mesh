"""
Unit tests for common/utils/mime_helpers.py
"""

from solace_agent_mesh.common.utils.mime_helpers import (
    resolve_mime_type,
    get_extension_for_mime_type,
    is_image_artifact,
    _EXTENSION_TO_MIME,
)


# --- resolve_mime_type ---


class TestResolveMimeType:
    """Tests for resolve_mime_type()."""

    def test_valid_mime_type_passes_through(self):
        assert resolve_mime_type("photo.png", "image/png") == "image/png"

    def test_valid_mime_type_passes_through_regardless_of_extension(self):
        assert resolve_mime_type("file.txt", "application/pdf") == "application/pdf"

    def test_octet_stream_resolved_from_md(self):
        assert resolve_mime_type("readme.md", "application/octet-stream") == "text/markdown"

    def test_octet_stream_resolved_from_yaml(self):
        assert resolve_mime_type("config.yaml", "application/octet-stream") == "text/yaml"

    def test_octet_stream_resolved_from_yml(self):
        assert resolve_mime_type("config.yml", "application/octet-stream") == "text/yaml"

    def test_octet_stream_resolved_from_ts(self):
        assert resolve_mime_type("index.ts", "application/octet-stream") == "text/x-typescript"

    def test_octet_stream_resolved_from_tsx(self):
        assert resolve_mime_type("App.tsx", "application/octet-stream") == "text/x-typescript"

    def test_octet_stream_resolved_from_mmd(self):
        assert resolve_mime_type("diagram.mmd", "application/octet-stream") == "text/plain"

    def test_none_mime_type_resolved_from_filename(self):
        assert resolve_mime_type("style.css", None) == "text/css"

    def test_none_mime_type_and_no_filename(self):
        assert resolve_mime_type(None, None) == "application/octet-stream"

    def test_none_mime_type_and_empty_filename(self):
        assert resolve_mime_type("", None) == "application/octet-stream"

    def test_unknown_extension_falls_back_to_octet_stream(self):
        assert resolve_mime_type("data.xyz", "application/octet-stream") == "application/octet-stream"

    def test_unknown_extension_with_none_mime_type(self):
        assert resolve_mime_type("data.xyz", None) == "application/octet-stream"

    def test_no_mimetypes_guess_type_fallback(self):
        """Ensure stdlib mimetypes.guess_type is NOT used (e.g. .mmd should not resolve to karaoke type)."""
        result = resolve_mime_type("file.mmd", "application/octet-stream")
        assert result == "text/plain"

    def test_case_insensitive_extension(self):
        assert resolve_mime_type("README.MD", "application/octet-stream") == "text/markdown"

    def test_octet_stream_with_no_filename_returns_octet_stream(self):
        assert resolve_mime_type(None, "application/octet-stream") == "application/octet-stream"

    def test_mixed_case_mime_type_is_normalized(self):
        assert resolve_mime_type("photo.png", "Image/PNG") == "image/png"

    def test_mime_type_with_parameters_stripped(self):
        assert resolve_mime_type("photo.png", "image/png; charset=binary") == "image/png"

    def test_octet_stream_with_parameters_triggers_resolution(self):
        assert resolve_mime_type("readme.md", "application/octet-stream; charset=binary") == "text/markdown"

    def test_mixed_case_octet_stream_triggers_resolution(self):
        assert resolve_mime_type("readme.md", "Application/Octet-Stream") == "text/markdown"


# --- get_extension_for_mime_type ---


class TestGetExtensionForMimeType:
    """Tests for get_extension_for_mime_type()."""

    def test_known_mime_type(self):
        assert get_extension_for_mime_type("text/markdown") == ".md"

    def test_application_json(self):
        assert get_extension_for_mime_type("application/json") == ".json"

    def test_image_png(self):
        assert get_extension_for_mime_type("image/png") == ".png"

    def test_octet_stream_returns_bin(self):
        assert get_extension_for_mime_type("application/octet-stream") == ".bin"

    def test_unknown_mime_type_returns_default(self):
        assert get_extension_for_mime_type("application/x-unknown") == ".dat"

    def test_none_returns_default(self):
        assert get_extension_for_mime_type(None) == ".dat"

    def test_custom_default_extension(self):
        assert get_extension_for_mime_type("application/x-unknown", ".bin") == ".bin"

    def test_mime_type_with_parameters_stripped(self):
        assert get_extension_for_mime_type("text/html; charset=utf-8") == ".html"


# --- _EXTENSION_TO_MIME aliases ---


class TestExtensionToMimeAliases:
    """Verify aliases in _EXTENSION_TO_MIME resolve to the correct canonical types."""

    def test_jpg_maps_to_standard_jpeg(self):
        assert _EXTENSION_TO_MIME[".jpg"] == "image/jpeg"

    def test_yaml_maps_to_text_yaml(self):
        assert _EXTENSION_TO_MIME[".yaml"] == "text/yaml"

    def test_yml_maps_to_text_yaml(self):
        assert _EXTENSION_TO_MIME[".yml"] == "text/yaml"

    def test_tsx_maps_to_typescript(self):
        assert _EXTENSION_TO_MIME[".tsx"] == "text/x-typescript"

    def test_mmd_maps_to_text_plain(self):
        assert _EXTENSION_TO_MIME[".mmd"] == "text/plain"

    def test_bin_not_in_reverse_map(self):
        assert ".bin" not in _EXTENSION_TO_MIME


# --- is_image_artifact ---


class TestIsImageArtifact:
    """Tests for is_image_artifact()."""

    def test_image_mime_type_returns_true(self):
        assert is_image_artifact("photo.png", "image/png") is True

    def test_image_jpeg_returns_true(self):
        assert is_image_artifact("photo.jpg", "image/jpeg") is True

    def test_image_webp_returns_true(self):
        assert is_image_artifact("anim.webp", "image/webp") is True

    def test_svg_mime_type_excluded(self):
        assert is_image_artifact("icon.svg", "image/svg+xml") is False

    def test_non_image_mime_type_returns_false(self):
        assert is_image_artifact("doc.pdf", "application/pdf") is False

    def test_non_image_mime_with_image_extension_returns_false(self):
        """A .png file with text/plain mime should not be treated as image."""
        assert is_image_artifact("report.png", "text/plain") is False

    def test_octet_stream_falls_back_to_extension(self):
        assert is_image_artifact("photo.png", "application/octet-stream") is True

    def test_octet_stream_non_image_extension(self):
        assert is_image_artifact("data.bin", "application/octet-stream") is False

    def test_none_mime_falls_back_to_extension(self):
        assert is_image_artifact("photo.jpg", None) is True

    def test_none_mime_non_image_extension(self):
        assert is_image_artifact("readme.md", None) is False

    def test_no_filename_no_mime_returns_false(self):
        assert is_image_artifact(None, None) is False

    def test_no_filename_with_image_mime_returns_true(self):
        assert is_image_artifact(None, "image/png") is True

    def test_extensionless_file_with_image_mime_returns_true(self):
        assert is_image_artifact("photo", "image/gif") is True

    def test_extensionless_file_no_mime_returns_false(self):
        assert is_image_artifact("photo", None) is False

    def test_mime_type_case_insensitive(self):
        assert is_image_artifact("x.png", "Image/PNG") is True

    def test_mime_type_with_parameters(self):
        assert is_image_artifact("x.png", "image/png; charset=binary") is True

    def test_svg_extension_no_mime_returns_false(self):
        """SVG extension is not in _INLINE_VISION_EXTENSIONS."""
        assert is_image_artifact("icon.svg", None) is False
