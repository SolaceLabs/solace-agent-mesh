"""
Base response classes with automatic timestamp serialization.
"""

from typing import Any

from pydantic import BaseModel

from ....shared import epoch_ms_to_iso8601


class BaseTimestampResponse(BaseModel):
    """
    Base class for responses that include standard timestamp fields.

    Timestamp fields are stored as epoch milliseconds (int) internally.
    Automatically converts created_time and updated_time to ISO strings in JSON output.
    """

    def model_dump(self, **kwargs) -> dict[str, Any]:
        """Override model_dump to convert timestamp fields to ISO strings."""
        data = super().model_dump(**kwargs)

        # Convert timestamp fields to ISO strings for JSON output
        timestamp_fields = ["created_time", "updated_time"]
        for field in timestamp_fields:
            if field in data and data[field] is not None:
                data[field] = epoch_ms_to_iso8601(data[field])

        return data

    def model_dump_json(self, **kwargs) -> str:
        """Override model_dump_json to use our timestamp conversion."""
        # Get the converted data first, then serialize to JSON
        converted_data = self.model_dump(**kwargs)
        import json

        return json.dumps(converted_data, default=str)
