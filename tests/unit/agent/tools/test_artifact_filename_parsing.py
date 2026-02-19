"""
Unit tests for artifact filename:version parsing.

Tests the parsing logic that handles artifact filenames with optional version suffixes.
The format is: filename[:version] where version is an optional integer.

The key challenge is that filenames can contain colons (e.g., "my:file:name.csv"),
so we must use rsplit from the right and only treat the suffix as a version
if it's a valid integer.
"""

import pytest
from typing import Tuple, Union


def parse_artifact_filename(filename: str) -> Tuple[str, Union[int, str]]:
    """
    Parse artifact filename with optional version suffix.

    This is the canonical parsing logic used throughout the codebase.
    Uses rsplit to handle filenames containing colons.

    Args:
        filename: Artifact filename, optionally with :version suffix

    Returns:
        Tuple of (filename_base, version) where version is int or "latest"
    """
    parts = filename.rsplit(":", 1)
    if len(parts) == 2 and parts[1].isdigit():
        return parts[0], int(parts[1])
    else:
        return filename, "latest"


class TestSimpleFilenames:
    """Test parsing of simple filenames without colons."""

    def test_filename_without_version(self):
        """Simple filename without version should return 'latest'."""
        filename_base, version = parse_artifact_filename("data.csv")
        assert filename_base == "data.csv"
        assert version == "latest"

    def test_filename_with_version(self):
        """Simple filename with version should parse correctly."""
        filename_base, version = parse_artifact_filename("data.csv:2")
        assert filename_base == "data.csv"
        assert version == 2

    def test_filename_with_version_zero(self):
        """Version 0 should be valid."""
        filename_base, version = parse_artifact_filename("data.csv:0")
        assert filename_base == "data.csv"
        assert version == 0

    def test_filename_with_large_version(self):
        """Large version numbers should work."""
        filename_base, version = parse_artifact_filename("data.csv:12345")
        assert filename_base == "data.csv"
        assert version == 12345

    def test_various_extensions(self):
        """Various file extensions should work."""
        test_cases = [
            ("report.pdf", "report.pdf", "latest"),
            ("image.png:3", "image.png", 3),
            ("archive.tar.gz", "archive.tar.gz", "latest"),
            ("archive.tar.gz:1", "archive.tar.gz", 1),
            ("no_extension:5", "no_extension", 5),
        ]
        for input_name, expected_base, expected_version in test_cases:
            filename_base, version = parse_artifact_filename(input_name)
            assert filename_base == expected_base, f"Failed for {input_name}"
            assert version == expected_version, f"Failed for {input_name}"


class TestFilenamesWithColons:
    """Test parsing of filenames that contain colons."""

    def test_single_colon_no_version(self):
        """Filename with single colon and no version."""
        filename_base, version = parse_artifact_filename("my:file.csv")
        assert filename_base == "my:file.csv"
        assert version == "latest"

    def test_single_colon_with_version(self):
        """Filename with single colon and version."""
        filename_base, version = parse_artifact_filename("my:file.csv:2")
        assert filename_base == "my:file.csv"
        assert version == 2

    def test_multiple_colons_no_version(self):
        """Filename with multiple colons and no version."""
        filename_base, version = parse_artifact_filename("my:artifact:name.csv")
        assert filename_base == "my:artifact:name.csv"
        assert version == "latest"

    def test_multiple_colons_with_version(self):
        """Filename with multiple colons and version."""
        filename_base, version = parse_artifact_filename("my:artifact:name.csv:2")
        assert filename_base == "my:artifact:name.csv"
        assert version == 2

    def test_many_colons_with_version(self):
        """Filename with many colons and version."""
        filename_base, version = parse_artifact_filename("a:b:c:d:e:f.txt:99")
        assert filename_base == "a:b:c:d:e:f.txt"
        assert version == 99

    def test_colon_in_extension_area(self):
        """Filename with colon near the extension."""
        filename_base, version = parse_artifact_filename("file:v1.0.csv")
        assert filename_base == "file:v1.0.csv"
        assert version == "latest"

    def test_timestamp_style_filename(self):
        """Timestamp-style filename with colons (like HH:MM:SS)."""
        filename_base, version = parse_artifact_filename("backup_2024-01-15_10:30:45.sql")
        assert filename_base == "backup_2024-01-15_10:30:45.sql"
        assert version == "latest"

    def test_timestamp_style_with_version(self):
        """Timestamp-style filename with version."""
        filename_base, version = parse_artifact_filename("backup_2024-01-15_10:30:45.sql:3")
        assert filename_base == "backup_2024-01-15_10:30:45.sql"
        assert version == 3


class TestEdgeCases:
    """Test edge cases and unusual inputs."""

    def test_empty_string(self):
        """Empty string should return empty filename."""
        filename_base, version = parse_artifact_filename("")
        assert filename_base == ""
        assert version == "latest"

    def test_only_colon(self):
        """Single colon should be treated as filename."""
        filename_base, version = parse_artifact_filename(":")
        assert filename_base == ":"
        assert version == "latest"

    def test_colon_with_non_digit(self):
        """Colon followed by non-digit should be part of filename."""
        filename_base, version = parse_artifact_filename("file:abc")
        assert filename_base == "file:abc"
        assert version == "latest"

    def test_colon_with_mixed_chars(self):
        """Colon followed by mixed characters should be part of filename."""
        filename_base, version = parse_artifact_filename("file:2a")
        assert filename_base == "file:2a"
        assert version == "latest"

    def test_colon_with_negative_number(self):
        """Negative numbers are not valid versions (dash is not a digit)."""
        filename_base, version = parse_artifact_filename("file:-1")
        assert filename_base == "file:-1"
        assert version == "latest"

    def test_colon_with_decimal(self):
        """Decimal numbers are not valid versions."""
        filename_base, version = parse_artifact_filename("file:1.5")
        assert filename_base == "file:1.5"
        assert version == "latest"

    def test_colon_with_empty_suffix(self):
        """Colon with empty suffix should be part of filename."""
        filename_base, version = parse_artifact_filename("file:")
        assert filename_base == "file:"
        assert version == "latest"

    def test_trailing_colon_and_version(self):
        """Filename ending with colon, then version."""
        filename_base, version = parse_artifact_filename("file::5")
        assert filename_base == "file:"
        assert version == 5

    def test_only_numbers_filename(self):
        """Filename that is only numbers without version."""
        filename_base, version = parse_artifact_filename("12345")
        assert filename_base == "12345"
        assert version == "latest"

    def test_only_numbers_with_version(self):
        """Filename that is only numbers with version."""
        filename_base, version = parse_artifact_filename("12345:6")
        assert filename_base == "12345"
        assert version == 6

    def test_unicode_filename(self):
        """Unicode characters in filename."""
        filename_base, version = parse_artifact_filename("données_été.csv")
        assert filename_base == "données_été.csv"
        assert version == "latest"

    def test_unicode_filename_with_version(self):
        """Unicode characters in filename with version."""
        filename_base, version = parse_artifact_filename("données_été.csv:7")
        assert filename_base == "données_été.csv"
        assert version == 7

    def test_spaces_in_filename(self):
        """Spaces in filename should be preserved."""
        filename_base, version = parse_artifact_filename("my file name.csv")
        assert filename_base == "my file name.csv"
        assert version == "latest"

    def test_spaces_in_filename_with_version(self):
        """Spaces in filename with version."""
        filename_base, version = parse_artifact_filename("my file name.csv:2")
        assert filename_base == "my file name.csv"
        assert version == 2


class TestVersionBoundaries:
    """Test version number boundaries."""

    def test_version_leading_zeros(self):
        """Version with leading zeros should be parsed as integer."""
        filename_base, version = parse_artifact_filename("file.txt:007")
        assert filename_base == "file.txt"
        assert version == 7  # int("007") == 7

    def test_very_large_version(self):
        """Very large version number."""
        filename_base, version = parse_artifact_filename("file.txt:999999999")
        assert filename_base == "file.txt"
        assert version == 999999999

    def test_version_with_plus_sign(self):
        """Plus sign is not a digit, so not a valid version."""
        filename_base, version = parse_artifact_filename("file.txt:+5")
        assert filename_base == "file.txt:+5"
        assert version == "latest"


class TestRealWorldExamples:
    """Test real-world filename patterns."""

    def test_iso_timestamp(self):
        """ISO timestamp format in filename."""
        filename_base, version = parse_artifact_filename("log_2024-12-28T10:30:00Z.txt")
        assert filename_base == "log_2024-12-28T10:30:00Z.txt"
        assert version == "latest"

    def test_iso_timestamp_with_version(self):
        """ISO timestamp format with version."""
        filename_base, version = parse_artifact_filename("log_2024-12-28T10:30:00Z.txt:1")
        assert filename_base == "log_2024-12-28T10:30:00Z.txt"
        assert version == 1

    def test_url_encoded_colon(self):
        """URL-like pattern that might have colons."""
        filename_base, version = parse_artifact_filename("cache_http:__example.com_path.html")
        assert filename_base == "cache_http:__example.com_path.html"
        assert version == "latest"

    def test_windows_drive_letter_style(self):
        """Windows drive letter style (C:) in filename."""
        filename_base, version = parse_artifact_filename("backup_C:_Users_data.zip")
        assert filename_base == "backup_C:_Users_data.zip"
        assert version == "latest"

    def test_windows_drive_letter_with_version(self):
        """Windows drive letter style with version."""
        filename_base, version = parse_artifact_filename("backup_C:_Users_data.zip:2")
        assert filename_base == "backup_C:_Users_data.zip"
        assert version == 2

    def test_mac_resource_fork_style(self):
        """Mac resource fork style filename."""
        filename_base, version = parse_artifact_filename("._file:2:data")
        assert filename_base == "._file:2:data"
        assert version == "latest"

    def test_mac_resource_fork_with_version(self):
        """Mac resource fork style with version."""
        filename_base, version = parse_artifact_filename("._file:2:data:5")
        assert filename_base == "._file:2:data"
        assert version == 5

    def test_semver_in_filename(self):
        """Semantic version in filename."""
        filename_base, version = parse_artifact_filename("package-1.2.3.tar.gz")
        assert filename_base == "package-1.2.3.tar.gz"
        assert version == "latest"

    def test_semver_in_filename_with_artifact_version(self):
        """Semantic version in filename with artifact version."""
        filename_base, version = parse_artifact_filename("package-1.2.3.tar.gz:4")
        assert filename_base == "package-1.2.3.tar.gz"
        assert version == 4
