"""
Utility modules for Solace Agent Mesh agents.

Exports:
    ToolContextFacade: Simplified interface for tool authors to access context and artifacts.
"""

from .tool_context_facade import ToolContextFacade

__all__ = [
    "ToolContextFacade",
]
