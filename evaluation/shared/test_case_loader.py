"""
Refactored test case loader with Pydantic-based validation.
This module provides robust test case loading and validation using Pydantic.
"""

import json
import logging
import os
import sys
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, field_validator

from .constants import (
    DEFAULT_CATEGORY,
    DEFAULT_DESCRIPTION,
    DEFAULT_WAIT_TIME,
    MAX_WAIT_TIME,
)
from .exceptions import (
    TestCaseError,
    TestCaseFileNotFoundError,
    TestCaseParseError,
)

log = logging.getLogger(__name__)


class Artifact(BaseModel):
    """
    Configuration for an individual artifact.
    Uses Pydantic for built-in validation.
    """
    artifact_type: Literal["file", "url", "text"] = Field(..., alias="type")
    path: str = Field(..., min_length=1)

    @field_validator("path")
    def validate_path_security(cls, v, values):
        """
        Validate file path security to prevent directory traversal.
        """
        if "artifact_type" in values.data and values.data["artifact_type"] == "file":
            normalized_path = os.path.normpath(v)
            if normalized_path.startswith("..") or os.path.isabs(normalized_path):
                raise ValueError(
                    f"Artifact path '{v}' is not safe (no absolute paths or directory traversal)"
                )
        return v

    class Config:
        validate_by_name = True


class Evaluation(BaseModel):
    """
    Configuration for evaluation criteria.
    """
    expected_tools: list[str] = Field(default_factory=list)
    expected_response: str = ""
    criterion: str = ""

    @field_validator("expected_tools")
    def validate_tool_names(cls, tools: list[str]) -> list[str]:
        """
        Ensures that tool names are non-empty strings.
        """
        if any(not isinstance(tool, str) or not tool.strip() for tool in tools):
            raise ValueError("All tool names must be non-empty strings.")
        return tools

class TestCase(BaseModel):
    """
    Complete test case configuration using Pydantic for validation.
    """
    test_case_id: str = Field(..., min_length=1)
    query: str = Field(..., min_length=1)
    target_agent: str = Field(..., min_length=1)
    category: str = DEFAULT_CATEGORY
    description: str = DEFAULT_DESCRIPTION
    wait_time: int = Field(DEFAULT_WAIT_TIME, gt=0, le=MAX_WAIT_TIME)
    artifacts: list[Artifact] = Field(default_factory=list)
    evaluation: Evaluation = Field(default_factory=Evaluation)

    def to_dict(self) -> dict[str, any]:
        """Convert test case to dictionary format for JSON serialization."""
        return self.model_dump(by_alias=True)

def load_test_case(test_case_path: str) -> dict[str, any]:
    """
    Load a test case from a JSON file with Pydantic validation.

    Args:
        test_case_path: The full path to the test case file.

    Returns:
        A dictionary containing the validated test case data.

    Raises:
        TestCaseFileNotFoundError: If the file does not exist.
        TestCaseParseError: If the file is not valid JSON or fails validation.
        TestCaseError: For other unexpected errors.
    """
    path = Path(test_case_path)
    if not path.is_file():
        raise TestCaseFileNotFoundError(f"Test case file not found: {test_case_path}")

    try:
        with open(path) as f:
            data = json.load(f)
            test_case = TestCase.model_validate(data)
            return test_case.to_dict()
    except json.JSONDecodeError as e:
        raise TestCaseParseError(f"Invalid JSON in test case file {test_case_path}: {e}") from e
    except ValidationError as e:
        raise TestCaseParseError(f"Test case validation failed for {test_case_path}:\n{e}") from e
    except Exception as e:
        raise TestCaseError(f"Error reading or processing test case file {test_case_path}: {e}") from e

def validate_test_case_file(test_case_path: str) -> None:
    """
    Validates a test case file and logs errors if any. Exits on failure.

    Args:
        test_case_path: The full path to the test case file.

    Raises:
        SystemExit: If validation fails.
    """
    try:
        load_test_case(test_case_path)
        log.info(f"Test case '{test_case_path}' validation successful.")
    except (TestCaseFileNotFoundError, TestCaseParseError, TestCaseError) as e:
        log.error(f"Error: {e}")
        sys.exit(1)

def main():
    """Main entry point for command-line usage and testing."""
    if len(sys.argv) != 2:
        log.error(f"Usage: python {sys.argv[0]} <path_to_test_case.json>")
        log.error(f"Example: python {sys.argv[0]} /path/to/hello_world.test.json")
        sys.exit(1)

    test_case_path = sys.argv[1]

    try:
        # Load and validate test case
        test_case_data = load_test_case(test_case_path)

        log.info(f"Successfully loaded test case: {test_case_data['test_case_id']}")
        log.info(f"Target Agent: {test_case_data['target_agent']}")
        log.info(f"Category: {test_case_data['category']}")
        query = test_case_data['query']
        log.info(f"Query: {query[:100]}{'...' if len(query) > 100 else ''}")
        log.info(f"Wait Time: {test_case_data['wait_time']} seconds")
        log.info(f"Artifacts: {len(test_case_data['artifacts'])} artifact(s)")
        log.info(f"Expected Tools: {len(test_case_data['evaluation']['expected_tools'])} tool(s)")

    except (TestCaseFileNotFoundError, TestCaseParseError, TestCaseError) as e:
        log.error(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        log.error(f"An unexpected error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
