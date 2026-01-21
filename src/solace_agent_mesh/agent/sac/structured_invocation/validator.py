"""
Schema validation utilities for workflow node input/output.
"""

import logging
from typing import Any, Dict, List, Optional
import jsonschema
from jsonschema import ValidationError

log = logging.getLogger(__name__)


def validate_against_schema(
    data: Any, schema: Dict[str, Any]
) -> Optional[List[str]]:
    """
    Validate data against a JSON schema.
    Returns a list of error messages if validation fails, or None if valid.
    """
    try:
        jsonschema.validate(instance=data, schema=schema)
        return None
    except ValidationError as e:
        # Extract a user-friendly error message
        path = ".".join([str(p) for p in e.path]) if e.path else "root"
        error_msg = f"Validation error at '{path}': {e.message}"
        return [error_msg]
    except Exception as e:
        return [f"Schema validation failed with unexpected error: {str(e)}"]
