"""
Refactored test case loader with comprehensive validation and error handling.
This module provides robust test case loading with validation for every field.
"""

import json
import os
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Union
from enum import Enum
from pathlib import Path
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


class ValidationLevel(Enum):
    """Defines the validation level for test case fields."""

    REQUIRED = "required"
    OPTIONAL = "optional"
    CONDITIONAL = "conditional"


class TestCaseError(Exception):
    """Base exception for test case-related errors."""

    pass


class TestCaseFileNotFoundError(TestCaseError):
    """Raised when the test case file is not found."""

    pass


class TestCaseParseError(TestCaseError):
    """Raised when the test case file cannot be parsed."""

    pass


class TestCaseValidationError(TestCaseError):
    """Raised when test case validation fails."""

    pass


class ArtifactValidationError(TestCaseError):
    """Raised when artifact validation fails."""

    pass


@dataclass
class ValidationReport:
    """Detailed validation report with all errors and warnings."""

    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def add_error(self, field: str, message: str):
        """Add a validation error."""
        self.errors.append(f"Field '{field}': {message}")

    def add_warning(self, field: str, message: str):
        """Add a validation warning."""
        self.warnings.append(f"Field '{field}': {message}")

    def has_errors(self) -> bool:
        """Check if there are any validation errors."""
        return len(self.errors) > 0

    def get_summary(self) -> str:
        """Get human-readable validation summary."""
        summary = []
        if self.errors:
            summary.append("ERRORS:")
            summary.extend([f"  - {error}" for error in self.errors])
        if self.warnings:
            summary.append("WARNINGS:")
            summary.extend([f"  - {warning}" for warning in self.warnings])
        return "\n".join(summary) if summary else "Test case validation passed."


@dataclass
class FieldValidator:
    """Defines validation rules for a test case field."""

    name: str
    validation_level: ValidationLevel
    field_type: type
    default_value: Any = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None
    allowed_values: Optional[List[Any]] = None
    pattern: Optional[str] = None
    custom_validator: Optional[str] = None


@dataclass
class ArtifactConfig:
    """Individual artifact configuration with validation."""

    artifact_type: str
    path: str

    def __post_init__(self):
        """Validate artifact configuration after initialization."""
        if not self.artifact_type or self.artifact_type.strip() == "":
            raise ArtifactValidationError("Artifact type cannot be empty")

        if not self.path or self.path.strip() == "":
            raise ArtifactValidationError("Artifact path cannot be empty")

        # Validate artifact type
        allowed_types = ["file", "url", "text"]
        if self.artifact_type not in allowed_types:
            raise ArtifactValidationError(
                f"Artifact type must be one of {allowed_types}, got '{self.artifact_type}'"
            )

        # Validate file path security (prevent directory traversal)
        if self.artifact_type == "file":
            normalized_path = os.path.normpath(self.path)
            if normalized_path.startswith("..") or os.path.isabs(normalized_path):
                raise ArtifactValidationError(
                    f"Artifact path '{self.path}' is not safe (no absolute paths or directory traversal)"
                )


@dataclass
class EvaluationConfig:
    """Evaluation criteria configuration with validation."""

    expected_tools: List[str] = field(default_factory=list)
    expected_response: str = ""
    criterion: str = ""

    def __post_init__(self):
        """Validate evaluation configuration after initialization."""
        # Validate expected_tools
        if not isinstance(self.expected_tools, list):
            raise TestCaseValidationError("expected_tools must be a list")

        # Validate tool names format
        for tool in self.expected_tools:
            if not isinstance(tool, str) or not tool.strip():
                raise TestCaseValidationError(
                    f"Tool name must be a non-empty string, got '{tool}'"
                )

        # Validate strings
        if not isinstance(self.expected_response, str):
            raise TestCaseValidationError("expected_response must be a string")

        if not isinstance(self.criterion, str):
            raise TestCaseValidationError("criterion must be a string")


@dataclass
class TestCase:
    """Complete test case configuration with validation."""

    test_case_id: str
    query: str
    target_agent: str
    category: str = "Other"
    description: str = "No description provided."
    wait_time: int = 60
    artifacts: List[ArtifactConfig] = field(default_factory=list)
    evaluation: EvaluationConfig = field(default_factory=EvaluationConfig)

    def __post_init__(self):
        """Validate the complete test case after initialization."""
        # Validate required string fields
        if not self.test_case_id or not self.test_case_id.strip():
            raise TestCaseValidationError("test_case_id cannot be empty")

        if not self.query or not self.query.strip():
            raise TestCaseValidationError("query cannot be empty")

        if not self.target_agent or not self.target_agent.strip():
            raise TestCaseValidationError("target_agent cannot be empty")

        # Validate wait_time
        if not isinstance(self.wait_time, int) or self.wait_time < 1:
            raise TestCaseValidationError("wait_time must be a positive integer")

        if self.wait_time > 300:  # 5 minutes max
            raise TestCaseValidationError("wait_time cannot exceed 300 seconds")

        # Validate artifacts
        if not isinstance(self.artifacts, list):
            raise TestCaseValidationError("artifacts must be a list")

    def to_dict(self) -> Dict[str, Any]:
        """Convert test case to dictionary format for JSON serialization."""
        return {
            "test_case_id": self.test_case_id,
            "category": self.category,
            "description": self.description,
            "query": self.query,
            "target_agent": self.target_agent,
            "wait_time": self.wait_time,
            "artifacts": [
                {"type": artifact.artifact_type, "path": artifact.path}
                for artifact in self.artifacts
            ],
            "evaluation": {
                "expected_tools": self.evaluation.expected_tools,
                "expected_response": self.evaluation.expected_response,
                "criterion": self.evaluation.criterion,
            },
        }


class TestCaseValidator:
    """Comprehensive test case validator with detailed error reporting."""

    # Validation rules for root-level fields
    ROOT_LEVEL_RULES = {
        "test_case_id": FieldValidator(
            name="test_case_id",
            validation_level=ValidationLevel.REQUIRED,
            field_type=str,
            min_length=1,
            max_length=100,
        ),
        "query": FieldValidator(
            name="query",
            validation_level=ValidationLevel.REQUIRED,
            field_type=str,
            min_length=1,
            max_length=2000,
        ),
        "target_agent": FieldValidator(
            name="target_agent",
            validation_level=ValidationLevel.REQUIRED,
            field_type=str,
            min_length=1,
            max_length=100,
        ),
        "category": FieldValidator(
            name="category",
            validation_level=ValidationLevel.OPTIONAL,
            field_type=str,
            default_value="Other",
            max_length=100,
        ),
        "description": FieldValidator(
            name="description",
            validation_level=ValidationLevel.OPTIONAL,
            field_type=str,
            default_value="No description provided.",
            max_length=1000,
        ),
        "wait_time": FieldValidator(
            name="wait_time",
            validation_level=ValidationLevel.OPTIONAL,
            field_type=int,
            default_value=60,
            min_value=1,
            max_value=300,
        ),
        "artifacts": FieldValidator(
            name="artifacts",
            validation_level=ValidationLevel.OPTIONAL,
            field_type=list,
            default_value=[],
        ),
        "evaluation": FieldValidator(
            name="evaluation",
            validation_level=ValidationLevel.OPTIONAL,
            field_type=dict,
            default_value={},
        ),
    }

    # Validation rules for evaluation fields
    EVALUATION_RULES = {
        "expected_tools": FieldValidator(
            name="expected_tools",
            validation_level=ValidationLevel.OPTIONAL,
            field_type=list,
            default_value=[],
        ),
        "expected_response": FieldValidator(
            name="expected_response",
            validation_level=ValidationLevel.OPTIONAL,
            field_type=str,
            default_value="",
            max_length=2000,
        ),
        "criterion": FieldValidator(
            name="criterion",
            validation_level=ValidationLevel.OPTIONAL,
            field_type=str,
            default_value="",
            max_length=1000,
        ),
    }

    # Validation rules for artifact fields
    ARTIFACT_RULES = {
        "type": FieldValidator(
            name="type",
            validation_level=ValidationLevel.REQUIRED,
            field_type=str,
            allowed_values=["file", "url", "text"],
        ),
        "path": FieldValidator(
            name="path",
            validation_level=ValidationLevel.REQUIRED,
            field_type=str,
            min_length=1,
            max_length=500,
        ),
    }

    def __init__(self, test_cases_dir: str):
        self.test_cases_dir = test_cases_dir
        self.report = ValidationReport()

    def validate_field(
        self,
        field_name: str,
        value: Any,
        rules: Dict[str, FieldValidator],
        context: str = "",
    ) -> Any:
        """Validate individual field with comprehensive checks."""
        rule = rules.get(field_name)
        if not rule:
            self.report.add_warning(
                f"{context}.{field_name}" if context else field_name,
                "Unknown field in test case",
            )
            return value

        full_field_name = f"{context}.{field_name}" if context else field_name

        # Handle missing required fields
        if value is None:
            if rule.validation_level == ValidationLevel.REQUIRED:
                self.report.add_error(full_field_name, "Required field is missing")
                return None
            else:
                return rule.default_value

        # Type validation
        if not isinstance(value, rule.field_type):
            self.report.add_error(
                full_field_name,
                f"Expected {rule.field_type.__name__}, got {type(value).__name__}",
            )
            return rule.default_value

        # Length validation for lists and strings
        if rule.min_length is not None:
            if hasattr(value, "__len__") and len(value) < rule.min_length:
                self.report.add_error(
                    full_field_name,
                    f"Minimum length is {rule.min_length}, got {len(value)}",
                )
                return rule.default_value

        if rule.max_length is not None:
            if hasattr(value, "__len__") and len(value) > rule.max_length:
                self.report.add_error(
                    full_field_name,
                    f"Maximum length is {rule.max_length}, got {len(value)}",
                )
                # Truncate for strings, return default for lists
                if isinstance(value, str):
                    return value[: rule.max_length]
                else:
                    return rule.default_value

        # Value range validation for numbers
        if rule.min_value is not None and isinstance(value, (int, float)):
            if value < rule.min_value:
                self.report.add_error(
                    full_field_name, f"Minimum value is {rule.min_value}, got {value}"
                )
                return rule.default_value

        if rule.max_value is not None and isinstance(value, (int, float)):
            if value > rule.max_value:
                self.report.add_error(
                    full_field_name, f"Maximum value is {rule.max_value}, got {value}"
                )
                return rule.default_value

        # Allowed values validation
        if rule.allowed_values is not None and value not in rule.allowed_values:
            self.report.add_error(
                full_field_name,
                f"Value must be one of {rule.allowed_values}, got '{value}'",
            )
            return rule.default_value

        return value

    def validate_artifact(
        self, artifact_data: Dict[str, Any], index: int
    ) -> Optional[ArtifactConfig]:
        """Validate individual artifact configuration."""
        context = f"artifacts[{index}]"

        # Validate required fields
        artifact_type = self.validate_field(
            "type", artifact_data.get("type"), self.ARTIFACT_RULES, context
        )
        path = self.validate_field(
            "path", artifact_data.get("path"), self.ARTIFACT_RULES, context
        )

        if not artifact_type or not path:
            self.report.add_error(context, "Invalid artifact configuration")
            return None

        try:
            artifact = ArtifactConfig(artifact_type=artifact_type, path=path)

            # Additional file existence check for file artifacts
            if artifact.artifact_type == "file":
                full_path = os.path.join(self.test_cases_dir, artifact.path)
                if not os.path.exists(full_path):
                    self.report.add_warning(
                        f"{context}.path", f"Artifact file does not exist: {full_path}"
                    )

            return artifact

        except ArtifactValidationError as e:
            self.report.add_error(context, str(e))
            return None

    def validate_evaluation(self, eval_data: Dict[str, Any]) -> EvaluationConfig:
        """Validate evaluation configuration."""
        context = "evaluation"

        # Validate evaluation fields
        expected_tools = self.validate_field(
            "expected_tools",
            eval_data.get("expected_tools"),
            self.EVALUATION_RULES,
            context,
        )
        expected_response = self.validate_field(
            "expected_response",
            eval_data.get("expected_response"),
            self.EVALUATION_RULES,
            context,
        )
        criterion = self.validate_field(
            "criterion", eval_data.get("criterion"), self.EVALUATION_RULES, context
        )

        try:
            return EvaluationConfig(
                expected_tools=expected_tools or [],
                expected_response=expected_response or "",
                criterion=criterion or "",
            )
        except TestCaseValidationError as e:
            self.report.add_error(context, str(e))
            # Return default evaluation config if validation fails
            return EvaluationConfig()


class TestCaseLoader:
    """Loads test case files with comprehensive error handling."""

    def __init__(self, test_cases_dir: str):
        self.test_cases_dir = test_cases_dir

    def load_file(self, test_case_id: str) -> Dict[str, Any]:
        """Load test case file with comprehensive error handling."""
        # Normalize test case ID
        if test_case_id.endswith(".test.json"):
            test_case_id = test_case_id.replace(".test.json", "")

        test_case_path = os.path.join(self.test_cases_dir, f"{test_case_id}.test.json")

        try:
            with open(test_case_path, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            raise TestCaseFileNotFoundError(
                f"Test case file not found: {test_case_path}"
            )
        except json.JSONDecodeError as e:
            raise TestCaseParseError(
                f"Invalid JSON in test case file {test_case_path}: {e}"
            )
        except Exception as e:
            raise TestCaseError(f"Error reading test case file {test_case_path}: {e}")


class TestCaseProcessor:
    """Main orchestrator for test case processing with comprehensive validation."""

    def __init__(self, test_cases_dir: str):
        self.loader = TestCaseLoader(test_cases_dir)
        self.validator = TestCaseValidator(test_cases_dir)

    def load_and_process(self, test_case_id: str) -> Dict[str, Any]:
        """Load and process test case, returning the same format as original."""
        try:
            # Load raw test case
            raw_test_case = self.loader.load_file(test_case_id)

            # Process and validate
            processed_test_case = self._process_test_case(raw_test_case, test_case_id)

            # Check for validation errors
            if self.validator.report.has_errors():
                error_summary = self.validator.report.get_summary()
                print(
                    f"Test case validation failed for '{test_case_id}':\n{error_summary}"
                )
                sys.exit(1)

            # Log warnings if any
            if self.validator.report.warnings:
                for warning in self.validator.report.warnings:
                    logger.warning(f"Test case '{test_case_id}': {warning}")

            return processed_test_case

        except TestCaseFileNotFoundError:
            print(
                f"Error: Test case file not found for '{test_case_id}' in {self.loader.test_cases_dir}"
            )
            sys.exit(1)
        except TestCaseParseError as e:
            print(f"Error: Could not decode JSON from test case '{test_case_id}': {e}")
            sys.exit(1)
        except Exception as e:
            print(f"Error loading test case '{test_case_id}': {e}")
            sys.exit(1)

    def _process_test_case(
        self, raw_test_case: Dict[str, Any], test_case_id: str
    ) -> Dict[str, Any]:
        """Process and validate the raw test case."""
        # Validate and set defaults for root-level fields
        validated_test_case_id = self.validator.validate_field(
            "test_case_id",
            raw_test_case.get("test_case_id"),
            self.validator.ROOT_LEVEL_RULES,
        )

        query = self.validator.validate_field(
            "query", raw_test_case.get("query"), self.validator.ROOT_LEVEL_RULES
        )

        target_agent = self.validator.validate_field(
            "target_agent",
            raw_test_case.get("target_agent"),
            self.validator.ROOT_LEVEL_RULES,
        )

        category = self.validator.validate_field(
            "category", raw_test_case.get("category"), self.validator.ROOT_LEVEL_RULES
        )

        description = self.validator.validate_field(
            "description",
            raw_test_case.get("description"),
            self.validator.ROOT_LEVEL_RULES,
        )

        wait_time = self.validator.validate_field(
            "wait_time", raw_test_case.get("wait_time"), self.validator.ROOT_LEVEL_RULES
        )

        # Process artifacts with validation
        artifacts_data = raw_test_case.get("artifacts", [])
        processed_artifacts = []

        if artifacts_data and isinstance(artifacts_data, list):
            for i, artifact_data in enumerate(artifacts_data):
                artifact = self.validator.validate_artifact(artifact_data, i)
                if artifact:
                    processed_artifacts.append(
                        {"type": artifact.artifact_type, "path": artifact.path}
                    )

        # Process evaluation with validation
        evaluation_data = raw_test_case.get("evaluation", {})
        evaluation = self.validator.validate_evaluation(evaluation_data)

        processed_evaluation = {
            "expected_tools": evaluation.expected_tools,
            "expected_response": evaluation.expected_response,
            "criterion": evaluation.criterion,
        }

        # Return processed test case in original format
        return {
            "test_case_id": validated_test_case_id or test_case_id,
            "category": category or "Other",
            "description": description or "No description provided.",
            "query": query or "",
            "target_agent": target_agent or "",
            "wait_time": wait_time or 60,
            "artifacts": processed_artifacts,
            "evaluation": processed_evaluation,
        }


# Main API function - same interface as original
def load_test_case(test_case_path: str) -> Dict[str, Any]:
    """
    Load test case from a JSON file with comprehensive validation.
    Returns the same format as the original function.

    Args:
        test_case_path: The full path to the test case file.

    Returns:
        Dictionary containing the validated test case data

    Raises:
        SystemExit: If validation fails or file cannot be loaded
    """
    test_case_dir = str(Path(test_case_path).parent)
    test_case_filename = Path(test_case_path).name
    processor = TestCaseProcessor(test_cases_dir=test_case_dir)
    return processor.load_and_process(test_case_filename)


def validate_test_case_file(test_case_path: str) -> ValidationReport:
    """
    Validate a test case file and return detailed validation report.

    Args:
        test_case_path: The full path to the test case file.

    Returns:
        ValidationReport with errors and warnings
    """
    try:
        test_case_dir = str(Path(test_case_path).parent)
        test_case_filename = Path(test_case_path).name
        processor = TestCaseProcessor(test_cases_dir=test_case_dir)
        processor.load_and_process(test_case_filename)
        return processor.validator.report
    except SystemExit:
        # Capture the validation report even if processing failed
        return processor.validator.report
    except Exception as e:
        report = ValidationReport()
        report.add_error("general", f"Unexpected error: {str(e)}")
        return report


def main():
    """Main entry point for command-line usage and testing."""
    import sys

    if len(sys.argv) != 2:
        print("Usage: python test_case_loader.py <test_case_id>")
        print("Example: python test_case_loader.py hello_world")
        sys.exit(1)

    test_case_id = sys.argv[1]

    try:
        # Load and validate test case
        test_case = load_test_case(test_case_id)

        # Print results
        print(f"Successfully loaded test case: {test_case_id}")
        print(f"Target Agent: {test_case['target_agent']}")
        print(f"Category: {test_case['category']}")
        print(
            f"Query: {test_case['query'][:100]}{'...' if len(test_case['query']) > 100 else ''}"
        )
        print(f"Wait Time: {test_case['wait_time']} seconds")
        print(f"Artifacts: {len(test_case['artifacts'])} artifact(s)")
        print(
            f"Expected Tools: {len(test_case['evaluation']['expected_tools'])} tool(s)"
        )

        # Show validation report
        processor = TestCaseProcessor()
        report = validate_test_case_file(test_case_id)
        if report.warnings:
            print("\nWarnings:")
            for warning in report.warnings:
                print(f"  - {warning}")

    except SystemExit:
        # Error already printed by load_test_case
        pass
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
