"""Tests for ToolManifest."""

import subprocess
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from solace_agent_mesh.sandbox.manifest import ManifestEntry, ToolManifest


VALID_MANIFEST = """\
version: 1
tools:
  my_tool:
    runtime: python
    module: my_module
    function: my_function
    description: "A test tool"
    timeout_seconds: 60
    sandbox_profile: restrictive
"""

TWO_TOOLS_MANIFEST = """\
version: 1
tools:
  tool_a:
    runtime: python
    module: mod_a
    function: fn_a
  tool_b:
    runtime: python
    module: mod_b
    class_name: ToolB
    package: my-package
    version: ">=1.0"
"""


class TestValidManifestParsing:
    def test_single_tool_loaded(self, tmp_path: Path):
        mf = tmp_path / "manifest.yaml"
        mf.write_text(VALID_MANIFEST)
        manifest = ToolManifest(str(mf))

        tools = manifest.list_tools()
        assert len(tools) == 1
        assert tools[0].tool_name == "my_tool"
        assert tools[0].module == "my_module"
        assert tools[0].function == "my_function"
        assert tools[0].sandbox_profile == "restrictive"


class TestMultipleTools:
    def test_two_tools_loaded(self, tmp_path: Path):
        mf = tmp_path / "manifest.yaml"
        mf.write_text(TWO_TOOLS_MANIFEST)
        manifest = ToolManifest(str(mf))

        assert manifest.get_tool_names() == {"tool_a", "tool_b"}


class TestGetTool:
    def test_returns_entry(self, tmp_path: Path):
        mf = tmp_path / "manifest.yaml"
        mf.write_text(VALID_MANIFEST)
        manifest = ToolManifest(str(mf))

        entry = manifest.get_tool("my_tool")
        assert entry is not None
        assert entry.module == "my_module"

    def test_returns_none_for_unknown(self, tmp_path: Path):
        mf = tmp_path / "manifest.yaml"
        mf.write_text(VALID_MANIFEST)
        manifest = ToolManifest(str(mf))

        assert manifest.get_tool("nonexistent") is None


class TestListTools:
    def test_returns_all_entries(self, tmp_path: Path):
        mf = tmp_path / "manifest.yaml"
        mf.write_text(TWO_TOOLS_MANIFEST)
        manifest = ToolManifest(str(mf))

        names = [e.tool_name for e in manifest.list_tools()]
        assert sorted(names) == ["tool_a", "tool_b"]


class TestInvalidYaml:
    def test_malformed_yaml_results_in_empty(self, tmp_path: Path):
        mf = tmp_path / "manifest.yaml"
        mf.write_text("{{{{not yaml")
        manifest = ToolManifest(str(mf))

        assert manifest.list_tools() == []


class TestMissingFile:
    def test_missing_file_results_in_empty(self, tmp_path: Path):
        manifest = ToolManifest(str(tmp_path / "does_not_exist.yaml"))
        assert manifest.list_tools() == []


class TestMissingToolsKey:
    def test_no_tools_section(self, tmp_path: Path):
        mf = tmp_path / "manifest.yaml"
        mf.write_text("version: 1\n")
        manifest = ToolManifest(str(mf))

        assert manifest.list_tools() == []


class TestPythonToolValidation:
    def test_missing_module_skipped(self, tmp_path: Path):
        content = """\
version: 1
tools:
  bad_tool:
    runtime: python
    function: fn
"""
        mf = tmp_path / "manifest.yaml"
        mf.write_text(content)
        manifest = ToolManifest(str(mf))

        assert manifest.get_tool("bad_tool") is None

    def test_missing_function_and_class_skipped(self, tmp_path: Path):
        content = """\
version: 1
tools:
  bad_tool:
    runtime: python
    module: mod
"""
        mf = tmp_path / "manifest.yaml"
        mf.write_text(content)
        manifest = ToolManifest(str(mf))

        assert manifest.get_tool("bad_tool") is None

    def test_class_name_is_valid_without_function(self, tmp_path: Path):
        content = """\
version: 1
tools:
  class_tool:
    runtime: python
    module: mod
    class_name: MyTool
"""
        mf = tmp_path / "manifest.yaml"
        mf.write_text(content)
        manifest = ToolManifest(str(mf))

        entry = manifest.get_tool("class_tool")
        assert entry is not None
        assert entry.class_name == "MyTool"


class TestMtimeAutoReload:
    def test_has_changed_detects_modification(self, tmp_path: Path):
        mf = tmp_path / "manifest.yaml"
        mf.write_text(VALID_MANIFEST)
        manifest = ToolManifest(str(mf))

        assert manifest.has_changed() is False

        time.sleep(0.05)
        mf.write_text(TWO_TOOLS_MANIFEST)

        assert manifest.has_changed() is True

    def test_get_tool_reloads_on_change(self, tmp_path: Path):
        mf = tmp_path / "manifest.yaml"
        mf.write_text(VALID_MANIFEST)
        manifest = ToolManifest(str(mf))

        assert manifest.get_tool("tool_a") is None

        time.sleep(0.05)
        mf.write_text(TWO_TOOLS_MANIFEST)

        assert manifest.get_tool("tool_a") is not None


class TestWheelDiscovery:
    def test_installs_wheels_from_directory(self, tmp_path: Path):
        mf = tmp_path / "manifest.yaml"
        mf.write_text(VALID_MANIFEST)
        manifest = ToolManifest(str(mf))

        wheels_dir = tmp_path / "wheels"
        wheels_dir.mkdir()
        (wheels_dir / "pkg-1.0-py3-none-any.whl").write_bytes(b"fake")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            manifest.install_pending_wheels()

        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "pkg-1.0-py3-none-any.whl" in args[-1]

    def test_already_installed_wheels_skipped(self, tmp_path: Path):
        mf = tmp_path / "manifest.yaml"
        mf.write_text(VALID_MANIFEST)
        manifest = ToolManifest(str(mf))

        wheels_dir = tmp_path / "wheels"
        wheels_dir.mkdir()
        (wheels_dir / "pkg-1.0-py3-none-any.whl").write_bytes(b"fake")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            manifest.install_pending_wheels()
            manifest.install_pending_wheels()

        assert mock_run.call_count == 1


class TestPackageInstall:
    def test_uv_fallback_to_pip(self, tmp_path: Path):
        mf = tmp_path / "manifest.yaml"
        content = """\
version: 1
tools:
  t:
    runtime: python
    module: pkg_mod
    function: fn
    package: my-pkg
"""
        mf.write_text(content)

        with patch.object(ToolManifest, "_is_package_installed", return_value=False):
            with patch("solace_agent_mesh.sandbox.manifest.subprocess.run") as mock_run:
                mock_run.side_effect = [
                    FileNotFoundError(),
                    MagicMock(returncode=0),
                ]
                manifest = ToolManifest(str(mf))
                manifest.ensure_packages_installed()

        calls = mock_run.call_args_list
        assert calls[0][0][0][0] == "uv"
        assert calls[1][0][0][0] == "pip"

    def test_already_installed_package_skipped(self, tmp_path: Path):
        mf = tmp_path / "manifest.yaml"
        content = """\
version: 1
tools:
  t:
    runtime: python
    module: json
    function: fn
    package: json
"""
        mf.write_text(content)
        manifest = ToolManifest(str(mf))

        with patch("solace_agent_mesh.sandbox.manifest.subprocess.run") as mock_run:
            manifest.ensure_packages_installed()

        mock_run.assert_not_called()


class TestInvalidToolEntry:
    def test_non_dict_tool_entry_skipped(self, tmp_path: Path):
        content = """\
version: 1
tools:
  bad_tool: "just a string"
"""
        mf = tmp_path / "manifest.yaml"
        mf.write_text(content)
        manifest = ToolManifest(str(mf))

        assert manifest.list_tools() == []


class TestNonDictRoot:
    def test_non_dict_root_results_in_empty(self, tmp_path: Path):
        mf = tmp_path / "manifest.yaml"
        mf.write_text("- item1\n- item2\n")
        manifest = ToolManifest(str(mf))

        assert manifest.list_tools() == []
