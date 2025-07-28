"""
Middleware package for pluggable system components.

This package provides a framework for pluggable middleware components that can be
extended or replaced at runtime. The default implementations provide permissive
behavior suitable for development and testing.
"""

from .config_resolver import ConfigResolver
from .registry import MiddlewareRegistry

__all__ = ["ConfigResolver", "MiddlewareRegistry"]
