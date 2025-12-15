"""
App Storage Service - Abstraction for serving built app dist/ files.

This module provides storage backends for serving built React apps.
The Gateway uses this to serve preview files, and the Claude Code tool
uses it to sync dist/ after builds.
"""

from .base import AppStorageService
from .filesystem import FilesystemAppStorageService

__all__ = [
    "AppStorageService",
    "FilesystemAppStorageService",
]

# Conditional imports for cloud backends
try:
    from .s3 import S3AppStorageService
    __all__.append("S3AppStorageService")
except ImportError:
    pass  # boto3 not installed
