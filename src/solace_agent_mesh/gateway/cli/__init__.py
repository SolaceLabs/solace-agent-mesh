"""
CLI Gateway for Solace Agent Mesh.

A simple interactive command-line gateway that uses the generic gateway adapter pattern.
"""

from .adapter import CliAdapter, CliAdapterConfig

__all__ = ["CliAdapter", "CliAdapterConfig"]
