"""Base classes for platform service DTOs.

Provides CamelCaseModel which automatically converts snake_case field names
to camelCase in JSON responses.
"""

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelCaseModel(BaseModel):
    """
    Base model that automatically converts snake_case field names to camelCase
    in JSON responses.

    Uses Pydantic's alias_generator to apply to_camel to all fields,
    and populate_by_name=True to accept both snake_case (internal) and
    camelCase (API) field names.
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )
