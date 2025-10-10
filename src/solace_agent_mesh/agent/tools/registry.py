"""
A singleton registry for discovering and holding all BuiltinTool definitions.
"""

import logging
from typing import Dict, List, Optional
from .tool_definition import BuiltinTool

log = logging.getLogger(__name__)


class _ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, BuiltinTool] = {}

    def register(self, tool: BuiltinTool):
        if tool.name in self._tools:
            log.warning("Tool '%s' is already registered. Overwriting.", tool.name)
        self._tools[tool.name] = tool

    def get_tool_by_name(self, name: str) -> Optional[BuiltinTool]:
        """Returns a tool by its registered name."""
        return self._tools.get(name)

    def get_tools_by_category(self, category_name: str) -> List[BuiltinTool]:
        """Returns a list of all tools belonging to a specific category."""
        return [tool for tool in self._tools.values() if tool.category == category_name]

    def get_all_tools(self) -> List[BuiltinTool]:
        return list(self._tools.values())

    def clear(self):
        """Clears all registered tools. For testing purposes only."""
        self._tools.clear()
        log.debug("Tool registry cleared.")


tool_registry = _ToolRegistry()
