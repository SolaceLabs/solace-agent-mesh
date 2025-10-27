"""
CLI Gateway (Pure prompt_toolkit) for Solace Agent Mesh.

A command-line gateway built entirely with prompt_toolkit for better
terminal compatibility, especially in VS Code.
"""

from .adapter import CliPtAdapter, CliPtAdapterConfig

__all__ = ["CliPtAdapter", "CliPtAdapterConfig"]
