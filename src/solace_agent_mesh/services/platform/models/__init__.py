"""
Platform service database models.

Provides SQLAlchemy models for platform configuration data.
"""

from .base import Base
from .model_configuration import ModelConfiguration

__all__ = [
    "Base",
    "ModelConfiguration",
]
