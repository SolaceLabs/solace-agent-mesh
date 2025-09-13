"""Provides a Pydantic BaseModel that is backward-compatible with dict access."""
from pydantic import BaseModel
from typing import Any

class BackwardCompatibleModel(BaseModel):
    """
    A Pydantic BaseModel that allows dictionary-style access for backward compatibility.
    Supports .get(), ['key'], and 'in' operator.
    """
    def get(self, key: str, default: Any = None) -> Any:
        """Provides dict-like .get() method."""
        return getattr(self, key, default)

    def __getitem__(self, key: str) -> Any:
        """Provides dict-like ['key'] access."""
        return getattr(self, key)

    def __contains__(self, key: str) -> bool:
        """Provides dict-like 'in' support."""
        return hasattr(self, key)
