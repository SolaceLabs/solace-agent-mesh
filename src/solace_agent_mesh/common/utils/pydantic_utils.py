"""Provides a Pydantic BaseModel for SAM configuration with dict-like access."""
from pydantic import BaseModel, ValidationError
from typing import Any, TypeVar, Union, get_args, get_origin
from types import UnionType

T = TypeVar("T", bound="SamConfigBase")


class SamConfigBase(BaseModel):
    """
    A Pydantic BaseModel for SAM configuration that allows dictionary-style access
    for backward compatibility with components expecting dicts.
    Supports .get(), ['key'], and 'in' operator.
    """

    @classmethod
    def model_validate_and_clean(cls: type[T], obj: Any) -> T:
        """
        Validates a dictionary, first removing any keys with None values.
        This allows Pydantic's default values to be applied correctly when
        a config key is present but has no value in YAML.
        """
        if isinstance(obj, dict):
            cleaned_obj = {k: v for k, v in obj.items() if v is not None}
            return cls.model_validate(cleaned_obj)
        return cls.model_validate(obj)

    @classmethod
    def format_validation_error_message(cls: type[T], error: ValidationError, app_name: str | None, agent_name: str | None = None) -> str:
        """
        Formats Pydantic validation error messages into a clear, actionable format.

        Example output:
        ---- Configuration validation failed for 'my-agent-app' ----

           Agent Name: AgentConfig

        ERROR 1:
           Missing required field: 'namespace'
           Location: app_config.namespace
           Description: Absolute topic prefix for A2A communication (e.g., 'myorg/dev')

        ---- Please update your YAML configuration ----
        """

        error_lines = [
            f"\n---- Configuration validation failed for {app_name or 'UNKNOWN'} ----",
            ""
        ]

        if agent_name:
            error_lines.append(f"   Agent Name: {agent_name}\n")

        def get_nested_field_description(model_class: type[BaseModel], path: list[str | int]) -> str | None:
            """Recursively get field description from nested models"""
            if not path:
                return None

            current_field = path[0]
            if str(current_field) not in model_class.model_fields:
                return None

            field_info = model_class.model_fields[str(current_field)]

            if len(path) == 1:
                return field_info.description

            annotation = field_info.annotation

            # Handle Optional/Union types
            if annotation is not None:
                origin = get_origin(annotation)
                if origin is Union or origin is UnionType:
                    types = get_args(annotation)
                    annotation = next((t for t in types if t is not type(None)), None)
                elif origin is list:
                    inner_type = get_args(annotation)[0]
                    if len(path) > 1 and isinstance(path[1], int):
                        if isinstance(inner_type, type) and issubclass(inner_type, BaseModel):
                            return get_nested_field_description(inner_type, path[2:])
                        return None
                    annotation = inner_type

            if annotation is not None and isinstance(annotation, type) and issubclass(annotation, BaseModel):
                return get_nested_field_description(annotation, path[1:])

            return None


        for index, err in enumerate(error.errors()):
            error_type = err.get('type')
            loc = err['loc']
            msg = err['msg']

            error_lines.append(f"ERROR {index + 1}:")

            absolute_path = '.'.join(str(item) for item in loc)
            description = get_nested_field_description(cls, list(loc))
            if error_type == 'missing':
                error_lines.extend([
                    f"   Missing required field: '{loc[-1]}'",
                ])
            else:
                error_lines.extend([
                    f"   Error: {msg}",
                ])
            error_lines.append(f"   Location: app_config.{absolute_path}")
            error_lines.append(f"   Description: {description or 'UNKNOWN'}")
            error_lines.append("")

        error_lines.append('---- Please update your YAML configuration ----')
        return '\n'.join(error_lines) + "\n"

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
    
    def pop(self, key: str, default: Any = None) -> Any:
        """
        Provides dict-like .pop() method.
        Removes the attribute and returns its value, or default if not present.
        """
        if hasattr(self, key):
            value = getattr(self, key)
            # Set to None rather than deleting, as Pydantic models don't support delattr
            setattr(self, key, None)
            return value
        return default
