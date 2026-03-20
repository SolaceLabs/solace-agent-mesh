"""Tests for tool_runner DynamicTool class-based execution."""

import asyncio
import json
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock

import pytest

from solace_agent_mesh.sandbox.tool_runner import (
    run_class_tool_async,
    run_init,
    serialize_result,
)
from solace_agent_mesh.sandbox.context_facade import SandboxToolContextFacade


def _make_facade(tmp_path: Path) -> SandboxToolContextFacade:
    return SandboxToolContextFacade(
        status_pipe_path="",
        tool_config={},
        artifacts={},
        output_dir=str(tmp_path / "output"),
        user_id="test-user",
        session_id="test-session",
        app_name="test-app",
        artifact_paths={},
    )


class FakeSchema:
    def to_dict(self):
        return {
            "type": "OBJECT",
            "properties": {"city": {"type": "STRING"}},
            "required": ["city"],
        }


class FakeDynamicTool:
    config_model = None

    def __init__(self, tool_config=None):
        self.tool_config = tool_config or {}

    @property
    def tool_name(self):
        return "fake_tool"

    @property
    def tool_description(self):
        return "A fake tool for testing"

    @property
    def parameters_schema(self):
        return FakeSchema()

    @property
    def artifact_params(self):
        return {}

    @property
    def ctx_facade_param_name(self):
        return None

    async def _run_async_impl(self, args, tool_context=None, credential=None):
        return {"text": f"result: {args.get('input', '')}", "data_objects": []}

    async def init(self, component=None, tool_config=None):
        pass

    async def cleanup(self, component=None, tool_config=None):
        pass


class FakeToolWithConfig:
    class _ConfigModel:
        @classmethod
        def model_validate(cls, data):
            obj = cls()
            obj.api_key = data.get("api_key", "")
            obj.mode = data.get("mode", "default")
            return obj

    config_model = _ConfigModel

    def __init__(self, tool_config=None):
        self.tool_config = tool_config or {}

    @property
    def tool_name(self):
        return "config_tool"

    @property
    def tool_description(self):
        return "Tool with config model"

    @property
    def parameters_schema(self):
        return {"type": "OBJECT", "properties": {"input": {"type": "STRING"}}}

    @property
    def artifact_params(self):
        return {}

    @property
    def ctx_facade_param_name(self):
        return None

    async def _run_async_impl(self, args, tool_context=None, credential=None):
        api_key = getattr(self.tool_config, "api_key", "none")
        return {"text": f"key={api_key}", "data_objects": []}

    async def init(self, component=None, tool_config=None):
        pass

    async def cleanup(self, component=None, tool_config=None):
        pass


class FakeToolBadConfig:
    class _ConfigModel:
        @classmethod
        def model_validate(cls, data):
            if "api_key" not in data:
                raise ValueError("api_key is required")
            obj = cls()
            obj.api_key = data["api_key"]
            return obj

    config_model = _ConfigModel

    def __init__(self, tool_config=None):
        self.tool_config = tool_config or {}

    @property
    def tool_name(self):
        return "strict_tool"

    @property
    def tool_description(self):
        return "Tool with strict config"

    @property
    def parameters_schema(self):
        return FakeSchema()

    @property
    def artifact_params(self):
        return {}

    @property
    def ctx_facade_param_name(self):
        return None

    async def _run_async_impl(self, args, tool_context=None, credential=None):
        return {"text": "ok", "data_objects": []}

    async def init(self, component=None, tool_config=None):
        pass

    async def cleanup(self, component=None, tool_config=None):
        pass


class TestRunClassToolAsync:
    def test_basic_execution(self, tmp_path):
        import types
        mod = types.ModuleType("fake_module")
        mod.FakeDynamicTool = FakeDynamicTool

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "solace_agent_mesh.sandbox.tool_runner.importlib.import_module",
                lambda path: mod,
            )
            facade = _make_facade(tmp_path)
            (tmp_path / "output").mkdir(exist_ok=True)

            result = asyncio.run(
                run_class_tool_async(
                    module_path="fake_module",
                    class_name="FakeDynamicTool",
                    args={"input": "hello"},
                    context=facade,
                    tool_config={},
                    artifact_metadata={},
                    output_dir=str(tmp_path / "output"),
                )
            )

            assert result["text"] == "result: hello"
            assert result["data_objects"] == []

    def test_config_model_validation(self, tmp_path):
        import types
        mod = types.ModuleType("config_module")
        mod.FakeToolWithConfig = FakeToolWithConfig

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "solace_agent_mesh.sandbox.tool_runner.importlib.import_module",
                lambda path: mod,
            )
            facade = _make_facade(tmp_path)
            (tmp_path / "output").mkdir(exist_ok=True)

            result = asyncio.run(
                run_class_tool_async(
                    module_path="config_module",
                    class_name="FakeToolWithConfig",
                    args={"input": "test"},
                    context=facade,
                    tool_config={"api_key": "my-secret-key", "mode": "fast"},
                    artifact_metadata={},
                    output_dir=str(tmp_path / "output"),
                )
            )

            assert result["text"] == "key=my-secret-key"

    def test_config_model_validation_failure(self, tmp_path):
        import types
        mod = types.ModuleType("bad_config_module")
        mod.FakeToolBadConfig = FakeToolBadConfig

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "solace_agent_mesh.sandbox.tool_runner.importlib.import_module",
                lambda path: mod,
            )
            facade = _make_facade(tmp_path)
            (tmp_path / "output").mkdir(exist_ok=True)

            with pytest.raises(ValueError, match="api_key is required"):
                asyncio.run(
                    run_class_tool_async(
                        module_path="bad_config_module",
                        class_name="FakeToolBadConfig",
                        args={"input": "test"},
                        context=facade,
                        tool_config={},
                        artifact_metadata={},
                        output_dir=str(tmp_path / "output"),
                    )
                )

    def test_no_config_model_uses_raw_dict(self, tmp_path):
        import types
        mod = types.ModuleType("noconfig_module")
        mod.FakeDynamicTool = FakeDynamicTool

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "solace_agent_mesh.sandbox.tool_runner.importlib.import_module",
                lambda path: mod,
            )
            facade = _make_facade(tmp_path)
            (tmp_path / "output").mkdir(exist_ok=True)

            result = asyncio.run(
                run_class_tool_async(
                    module_path="noconfig_module",
                    class_name="FakeDynamicTool",
                    args={"input": "raw"},
                    context=facade,
                    tool_config={"some": "dict"},
                    artifact_metadata={},
                    output_dir=str(tmp_path / "output"),
                )
            )

            assert result["text"] == "result: raw"


class TestRunInit:
    def test_init_returns_metadata(self):
        import types
        mod = types.ModuleType("init_module")
        mod.FakeDynamicTool = FakeDynamicTool

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "solace_agent_mesh.sandbox.tool_runner.importlib.import_module",
                lambda path: mod,
            )

            result = run_init({
                "module": "init_module",
                "class_name": "FakeDynamicTool",
                "tool_config": {},
            })

            assert "result" in result
            meta = result["result"]
            assert meta["tool_description"] == "A fake tool for testing"
            assert meta["parameters_schema"] == {
                "type": "OBJECT",
                "properties": {"city": {"type": "STRING"}},
                "required": ["city"],
            }
            assert meta["ctx_facade_param_name"] is None

    def test_init_with_config_model_validation(self):
        import types
        mod = types.ModuleType("init_config_module")
        mod.FakeToolWithConfig = FakeToolWithConfig

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "solace_agent_mesh.sandbox.tool_runner.importlib.import_module",
                lambda path: mod,
            )

            result = run_init({
                "module": "init_config_module",
                "class_name": "FakeToolWithConfig",
                "tool_config": {"api_key": "test-key"},
            })

            assert "result" in result

    def test_init_schema_to_dict_fallback(self):
        import types
        mod = types.ModuleType("schema_module")
        mod.FakeDynamicTool = FakeDynamicTool

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "solace_agent_mesh.sandbox.tool_runner.importlib.import_module",
                lambda path: mod,
            )

            result = run_init({
                "module": "schema_module",
                "class_name": "FakeDynamicTool",
                "tool_config": {},
            })

            schema = result["result"]["parameters_schema"]
            assert schema["type"] == "OBJECT"
            assert "city" in schema["properties"]

    def test_init_import_error(self):
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "solace_agent_mesh.sandbox.tool_runner.importlib.import_module",
                MagicMock(side_effect=ImportError("no module")),
            )

            result = run_init({
                "module": "nonexistent",
                "class_name": "Foo",
                "tool_config": {},
            })

            assert "error" in result
            assert "Import error" in result["error"]


class TestSerializeResult:
    def test_serialize_none(self):
        assert serialize_result(None) == {"text": None, "data_objects": []}

    def test_serialize_dict(self):
        d = {"text": "hello", "data_objects": []}
        assert serialize_result(d) == d

    def test_serialize_string(self):
        assert serialize_result("hello") == {"text": "hello", "data_objects": []}

    def test_serialize_pydantic_like(self):
        mock = MagicMock()
        mock.data_objects = []
        mock.model_dump.return_value = {"text": "pydantic", "data_objects": []}
        assert serialize_result(mock) == {"text": "pydantic", "data_objects": []}
