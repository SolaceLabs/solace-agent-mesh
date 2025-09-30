"""Provides a Pydantic BaseModel for SAM configuration with dict-like access."""
from pydantic import BaseModel
from typing import Any, Dict, Type, TypeVar

T = TypeVar("T", bound="SamConfigBase")


class SamConfigBase(BaseModel):
    """
    A Pydantic BaseModel for SAM configuration that allows dictionary-style access
    for backward compatibility with components expecting dicts.
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

    def __setitem__(self, key: str, value: Any):
        """Provides dict-like ['key'] = value assignment."""
        setattr(self, key, value)

    def __contains__(self, key: str) -> bool:
        """
        Provides dict-like 'in' support that mimics the old behavior.
        Returns True only if the key was explicitly provided during model creation.
        """
        return key in self.model_fields_set

    def keys(self):
        """Provides dict-like .keys() method."""
        return self.model_dump().keys()

    def values(self):
        """Provides dict-like .values() method."""
        return self.model_dump().values()

    def items(self):
        """Provides dict-like .items() method."""
        return self.model_dump().items()

    def __iter__(self):
        """Provides dict-like iteration over keys."""
        return iter(self.model_dump())
