"""Provides a Pydantic BaseModel that is backward-compatible with dict access."""
from pydantic import BaseModel
from typing import Any, Dict, Type, TypeVar

T = TypeVar("T", bound="BackwardCompatibleModel")


class BackwardCompatibleModel(BaseModel):
    """
    A Pydantic BaseModel that allows dictionary-style access for backward compatibility.
    Supports .get(), ['key'], and 'in' operator.
    """

    @classmethod
    def model_validate_and_clean(cls: Type[T], obj: Any) -> T:
        """
        Validates a dictionary, first removing any keys with None values.
        This allows Pydantic's default values to be applied correctly when
        a config key is present but has no value in YAML.
        """
        if isinstance(obj, dict):
            cleaned_obj = {k: v for k, v in obj.items() if v is not None}
            return cls.model_validate(cleaned_obj)
        return cls.model_validate(obj)

    def get(self, key: str, default: Any = None) -> Any:
        """Provides dict-like .get() method."""
        return getattr(self, key, default)

    def __getitem__(self, key: str) -> Any:
        """Provides dict-like ['key'] access."""
        return getattr(self, key)

    def __contains__(self, key: str) -> bool:
        """Provides dict-like 'in' support."""
        return hasattr(self, key)
