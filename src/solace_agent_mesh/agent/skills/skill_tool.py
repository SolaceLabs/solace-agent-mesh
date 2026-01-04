"""
ADK Tool implementation for skill-provided tools.

Wraps tools defined in skill.sam.yaml with name prefixing and
description annotation to indicate the skill source.
"""

import asyncio
import inspect
import logging
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple

from google.adk.tools import BaseTool, ToolContext
from google.genai import types as adk_types
from solace_ai_connector.common.utils import import_module

if TYPE_CHECKING:
    from ..sac.component import SamAgentComponent

log = logging.getLogger(__name__)


def create_skill_tool(
    tool_config: Dict[str, Any],
    skill_name: str,
    component: "SamAgentComponent",
) -> Tuple[Optional["SkillTool"], Optional[adk_types.FunctionDeclaration]]:
    """
    Factory function to create a skill tool from configuration.

    Args:
        tool_config: Tool configuration from skill.sam.yaml.
        skill_name: Name of the skill providing this tool.
        component: The host agent component.

    Returns:
        Tuple of (SkillTool instance, FunctionDeclaration) or (None, None) on error.
    """
    try:
        tool = SkillTool(
            skill_name=skill_name,
            tool_config=tool_config,
            host_component=component,
        )
        declaration = tool._get_declaration()
        return tool, declaration
    except Exception as e:
        log.error("Failed to create skill tool: %s", e)
        return None, None


class SkillTool(BaseTool):
    """
    An ADK Tool that wraps a skill-provided tool.

    Handles name prefixing to avoid conflicts and description annotation
    to indicate the skill source.
    """

    def __init__(
        self,
        skill_name: str,
        tool_config: Dict[str, Any],
        host_component: "SamAgentComponent",
    ):
        """
        Initializes the SkillTool.

        Args:
            skill_name: Name of the skill providing this tool.
            tool_config: Tool configuration from skill.sam.yaml.
            host_component: The host agent component.
        """
        self.skill_name = skill_name
        self.tool_config = tool_config
        self.host_component = host_component

        # Get original name and build prefixed name
        original_name = tool_config.get("name") or tool_config.get("function_name")
        if not original_name:
            raise ValueError("Skill tool config missing 'name' or 'function_name'")

        self.original_name = original_name
        tool_name = f"{original_name}_{skill_name}"

        # Build description with skill attribution
        original_desc = tool_config.get("description", "No description provided.")
        description = f"Loaded by skill {skill_name}: {original_desc}"

        super().__init__(
            name=tool_name,
            description=description,
        )

        self.log_identifier = (
            f"{host_component.log_identifier}[SkillTool:{tool_name}]"
        )

        # Load the implementation
        self._implementation = self._load_implementation()

    def _load_implementation(self):
        """
        Loads the Python function for this tool.

        Supports both direct function reference and module.function_name pattern.
        """
        tool_type = self.tool_config.get("tool_type", "python")

        if tool_type != "python":
            raise ValueError(
                f"Skill tools currently only support 'python' tool_type, got '{tool_type}'"
            )

        module_name = self.tool_config.get("component_module")
        func_name = self.tool_config.get("function_name")
        base_path = self.tool_config.get("component_base_path")

        if not module_name or not func_name:
            raise ValueError(
                f"Skill tool config missing 'component_module' or 'function_name': {self.tool_config}"
            )

        try:
            module = import_module(module_name, base_path=base_path)
            func = getattr(module, func_name, None)
            if func is None:
                raise ValueError(
                    f"Function '{func_name}' not found in module '{module_name}'"
                )
            return func
        except Exception as e:
            raise ValueError(
                f"Failed to import skill tool function '{module_name}.{func_name}': {e}"
            ) from e

    def _get_declaration(self) -> Optional[adk_types.FunctionDeclaration]:
        """
        Generates the FunctionDeclaration for this tool.

        Builds the OpenAPI-style parameter schema from config.
        """
        params_config = self.tool_config.get("parameters", {})

        properties = {}
        for prop_name, prop_config in params_config.get("properties", {}).items():
            prop_type = prop_config.get("type", "string")
            prop_desc = prop_config.get("description", "")
            nullable = prop_config.get("nullable", False)

            schema = adk_types.Schema(
                type=_map_type(prop_type),
                description=prop_desc,
                nullable=nullable,
            )
            properties[prop_name] = schema

        parameters_schema = adk_types.Schema(
            type=adk_types.Type.OBJECT,
            properties=properties,
            required=params_config.get("required", []),
        )

        return adk_types.FunctionDeclaration(
            name=self.name,
            description=self.description,
            parameters=parameters_schema,
        )

    async def run_async(
        self, *, args: Dict[str, Any], tool_context: ToolContext
    ) -> Any:
        """
        Executes the skill tool.

        Injects tool_context and tool_config if the function accepts them.
        """
        log.debug("%s Executing with args: %s", self.log_identifier, list(args.keys()))

        try:
            # Build kwargs for the function
            call_kwargs = dict(args)

            # Inspect the function signature to see what it accepts
            sig = inspect.signature(self._implementation)
            params = sig.parameters

            # Inject tool_context if accepted
            if "tool_context" in params:
                call_kwargs["tool_context"] = tool_context

            # Inject tool_config if accepted
            if "tool_config" in params:
                call_kwargs["tool_config"] = self.tool_config.get("tool_config", {})

            # Execute the function
            if inspect.iscoroutinefunction(self._implementation):
                result = await self._implementation(**call_kwargs)
            else:
                result = await asyncio.to_thread(self._implementation, **call_kwargs)

            log.debug("%s Execution completed successfully", self.log_identifier)
            return result

        except Exception as e:
            log.exception("%s Tool execution failed: %s", self.log_identifier, e)
            return {
                "status": "error",
                "message": f"Skill tool '{self.name}' failed: {e}",
            }


def _map_type(type_str: str) -> adk_types.Type:
    """
    Maps YAML type strings to ADK types.

    Args:
        type_str: Type string from YAML config (e.g., 'string', 'integer').

    Returns:
        Corresponding adk_types.Type enum value.
    """
    mapping = {
        "string": adk_types.Type.STRING,
        "integer": adk_types.Type.INTEGER,
        "number": adk_types.Type.NUMBER,
        "boolean": adk_types.Type.BOOLEAN,
        "array": adk_types.Type.ARRAY,
        "object": adk_types.Type.OBJECT,
    }
    return mapping.get(type_str.lower(), adk_types.Type.STRING)
