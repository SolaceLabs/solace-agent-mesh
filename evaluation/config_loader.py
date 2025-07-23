"""
Refactored configuration loader with comprehensive validation and error handling.
This module provides robust configuration loading with validation for every field.
"""

import json
import os
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Union
from enum import Enum
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


class ValidationLevel(Enum):
    """Defines the validation level for configuration fields."""

    REQUIRED = "required"
    OPTIONAL = "optional"
    CONDITIONAL = "conditional"


class ConfigurationError(Exception):
    """Base exception for configuration-related errors."""

    pass


class ConfigurationFileNotFoundError(ConfigurationError):
    """Raised when the configuration file is not found."""

    pass


class ConfigurationParseError(ConfigurationError):
    """Raised when the configuration file cannot be parsed."""

    pass


class ConfigurationValidationError(ConfigurationError):
    """Raised when configuration validation fails."""

    pass


class EnvironmentVariableError(ConfigurationError):
    """Raised when required environment variables are missing."""

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
        return "\n".join(summary) if summary else "Configuration validation passed."


@dataclass
class FieldValidator:
    """Defines validation rules for a configuration field."""

    name: str
    validation_level: ValidationLevel
    field_type: type
    default_value: Any = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    allowed_values: Optional[List[Any]] = None
    condition_field: Optional[str] = None
    condition_value: Any = None
    custom_validator: Optional[str] = None


@dataclass
class EnvironmentConfig:
    """Environment variable configuration with validation."""

    variables: Dict[str, Optional[str]] = field(default_factory=dict)

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get environment variable value with default."""
        return self.variables.get(key, default)

    def is_complete(self, required_vars: List[str]) -> bool:
        """Check if all required environment variables are present."""
        return all(self.variables.get(var) is not None for var in required_vars)


@dataclass
class LLMModelConfig:
    """Individual LLM model configuration with validation."""

    name: str
    env: EnvironmentConfig

    def __post_init__(self):
        """Validate the model configuration after initialization."""
        if not self.name or not self.name.strip():
            raise ConfigurationValidationError("LLM model name cannot be empty")

        essential_vars = ["LLM_SERVICE_PLANNING_MODEL_NAME"]
        if not any(var in self.env.variables for var in essential_vars):
            raise ConfigurationValidationError(
                f"LLM model '{self.name}' must have at least one of: {essential_vars}"
            )


@dataclass
class EvaluationSettings:
    """Evaluation settings with comprehensive validation."""

    tool_match_enabled: bool = True
    response_match_enabled: bool = True
    llm_evaluator_enabled: bool = False
    llm_evaluator_env: Optional[EnvironmentConfig] = None

    def __post_init__(self):
        """Validate evaluation settings after initialization."""
        if self.llm_evaluator_enabled and not self.llm_evaluator_env:
            raise ConfigurationValidationError(
                "llm_evaluator.env is required when llm_evaluator.enabled is true"
            )

        if self.llm_evaluator_enabled and self.llm_evaluator_env:
            required_vars = [
                "LLM_SERVICE_PLANNING_MODEL_NAME",
                "LLM_SERVICE_ENDPOINT",
                "LLM_SERVICE_API_KEY",
            ]
            if not self.llm_evaluator_env.is_complete(required_vars):
                raise ConfigurationValidationError(
                    f"LLM evaluator requires environment variables: {required_vars}"
                )


@dataclass
class EvaluationConfig:
    """Main configuration with full validation and defaults."""

    agents: List[str]
    llm_models: List[LLMModelConfig]
    test_cases: List[str]
    results_dir_name: str = "tests"
    runs: int = 1
    evaluation_settings: EvaluationSettings = field(default_factory=EvaluationSettings)

    def __post_init__(self):
        """Validate the complete configuration after initialization."""
        if not self.agents:
            raise ConfigurationValidationError(
                "At least one agent configuration is required"
            )

        if not self.llm_models:
            raise ConfigurationValidationError("At least one LLM model is required")

        if not self.test_cases:
            raise ConfigurationValidationError("At least one test case is required")

        if self.runs < 1:
            raise ConfigurationValidationError("Number of runs must be at least 1")

        if not self.results_dir_name or not self.results_dir_name.strip():
            raise ConfigurationValidationError("Results directory name cannot be empty")


class EnvironmentVariableResolver:
    """Enhanced environment variable resolver with comprehensive validation."""

    REQUIRED_LLM_VARS = [
        "LLM_SERVICE_PLANNING_MODEL_NAME",
        "LLM_SERVICE_ENDPOINT",
        "LLM_SERVICE_API_KEY",
    ]

    OPTIONAL_VARS = ["MAX_TOKENS"]

    def resolve_environment_config(
        self, env_config: Dict[str, str], context: str
    ) -> EnvironmentConfig:
        """Resolve environment variables with comprehensive validation."""
        resolved = {}
        missing_required = []
        missing_optional = []

        for key, value in env_config.items():
            if key.endswith("_VAR"):
                env_var_name = key[:-4]  # Remove '_VAR' suffix
                env_var_value = os.getenv(value)

                if not env_var_value:
                    if value in self.REQUIRED_LLM_VARS:
                        missing_required.append(f"{value} (for {env_var_name})")
                    else:
                        missing_optional.append(f"{value} (for {env_var_name})")
                        logger.warning(
                            f"Optional environment variable '{value}' not set for {context}"
                        )
                    resolved[env_var_name] = None
                else:
                    resolved[env_var_name] = env_var_value
            else:
                resolved[key] = value

        if missing_required:
            raise EnvironmentVariableError(
                f"Required environment variables missing for {context}: {', '.join(missing_required)}"
            )

        if missing_optional:
            logger.info(
                f"Optional environment variables not set for {context}: {', '.join(missing_optional)}"
            )

        return EnvironmentConfig(variables=resolved)


class ConfigurationValidator:
    """Comprehensive configuration validator with detailed error reporting."""

    ROOT_LEVEL_RULES = {
        "agents": FieldValidator(
            name="agents",
            validation_level=ValidationLevel.REQUIRED,
            field_type=list,
            min_length=1,
        ),
        "llm_models": FieldValidator(
            name="llm_models",
            validation_level=ValidationLevel.REQUIRED,
            field_type=list,
            min_length=1,
        ),
        "test_cases": FieldValidator(
            name="test_cases",
            validation_level=ValidationLevel.REQUIRED,
            field_type=list,
            min_length=1,
        ),
        "results_dir_name": FieldValidator(
            name="results_dir_name",
            validation_level=ValidationLevel.OPTIONAL,
            field_type=str,
            default_value="tests",
        ),
        "runs": FieldValidator(
            name="runs",
            validation_level=ValidationLevel.OPTIONAL,
            field_type=int,
            default_value=1,
        ),
        "evaluation_settings": FieldValidator(
            name="evaluation_settings",
            validation_level=ValidationLevel.OPTIONAL,
            field_type=dict,
            default_value={},
        ),
    }

    LLM_MODEL_RULES = {
        "name": FieldValidator(
            name="name",
            validation_level=ValidationLevel.REQUIRED,
            field_type=str,
            min_length=1,
        ),
        "env": FieldValidator(
            name="env",
            validation_level=ValidationLevel.REQUIRED,
            field_type=dict,
            min_length=1,
        ),
    }

    def __init__(self, env_resolver: EnvironmentVariableResolver):
        self.env_resolver = env_resolver
        self.report = ValidationReport()

    def validate_field(
        self,
        field_name: str,
        value: Any,
        rules: Dict[str, FieldValidator],
        config: Dict[str, Any],
    ) -> Any:
        """Validate individual field with comprehensive checks."""
        rule = rules.get(field_name)
        if not rule:
            self.report.add_warning(field_name, "Unknown field in configuration")
            return value

        if value is None:
            if rule.validation_level == ValidationLevel.REQUIRED:
                self.report.add_error(field_name, "Required field is missing")
                return None
            else:
                return rule.default_value

        if not isinstance(value, rule.field_type):
            self.report.add_error(
                field_name,
                f"Expected {rule.field_type.__name__}, got {type(value).__name__}",
            )
            return rule.default_value

        if rule.min_length is not None:
            if hasattr(value, "__len__") and len(value) < rule.min_length:
                self.report.add_error(
                    field_name, f"Minimum length is {rule.min_length}, got {len(value)}"
                )
                return rule.default_value

        if rule.max_length is not None:
            if hasattr(value, "__len__") and len(value) > rule.max_length:
                self.report.add_error(
                    field_name, f"Maximum length is {rule.max_length}, got {len(value)}"
                )
                return value[: rule.max_length]  # Truncate

        if rule.allowed_values is not None and value not in rule.allowed_values:
            self.report.add_error(
                field_name, f"Value must be one of {rule.allowed_values}, got {value}"
            )
            return rule.default_value

        if rule.condition_field and rule.condition_value:
            condition_met = config.get(rule.condition_field) == rule.condition_value
            if (
                rule.validation_level == ValidationLevel.CONDITIONAL
                and not condition_met
            ):
                return rule.default_value

        return value

    def validate_llm_model(
        self, model_data: Dict[str, Any], index: int
    ) -> Optional[LLMModelConfig]:
        """Validate LLM model configuration."""
        context = f"llm_models[{index}]"

        name = self.validate_field(
            "name", model_data.get("name"), self.LLM_MODEL_RULES, model_data
        )
        env_data = self.validate_field(
            "env", model_data.get("env"), self.LLM_MODEL_RULES, model_data
        )

        if not name or not env_data:
            self.report.add_error(context, "Invalid model configuration")
            return None

        try:
            env_config = self.env_resolver.resolve_environment_config(
                env_data, f"model '{name}'"
            )
            return LLMModelConfig(name=name, env=env_config)
        except (EnvironmentVariableError, ConfigurationValidationError) as e:
            self.report.add_error(context, str(e))
            return None

    def validate_evaluation_settings(
        self, settings_data: Dict[str, Any]
    ) -> EvaluationSettings:
        """Validate evaluation settings with conditional logic."""
        tool_match = settings_data.get("tool_match", {})
        tool_match_enabled = tool_match.get("enabled", True)
        if not isinstance(tool_match_enabled, bool):
            self.report.add_warning(
                "evaluation_settings.tool_match.enabled",
                "Expected boolean, using default True",
            )
            tool_match_enabled = True

        response_match = settings_data.get("response_match", {})
        response_match_enabled = response_match.get("enabled", True)
        if not isinstance(response_match_enabled, bool):
            self.report.add_warning(
                "evaluation_settings.response_match.enabled",
                "Expected boolean, using default True",
            )
            response_match_enabled = True

        llm_evaluator = settings_data.get("llm_evaluator", {})
        llm_evaluator_enabled = llm_evaluator.get("enabled", False)
        if not isinstance(llm_evaluator_enabled, bool):
            self.report.add_warning(
                "evaluation_settings.llm_evaluator.enabled",
                "Expected boolean, using default False",
            )
            llm_evaluator_enabled = False

        llm_evaluator_env = None
        if llm_evaluator_enabled:
            env_data = llm_evaluator.get("env")
            if not env_data:
                self.report.add_error(
                    "evaluation_settings.llm_evaluator.env",
                    "Required when llm_evaluator is enabled",
                )
            else:
                try:
                    llm_evaluator_env = self.env_resolver.resolve_environment_config(
                        env_data, "llm_evaluator"
                    )
                except (EnvironmentVariableError, ConfigurationValidationError) as e:
                    self.report.add_error(
                        "evaluation_settings.llm_evaluator.env", str(e)
                    )

        try:
            return EvaluationSettings(
                tool_match_enabled=tool_match_enabled,
                response_match_enabled=response_match_enabled,
                llm_evaluator_enabled=llm_evaluator_enabled,
                llm_evaluator_env=llm_evaluator_env,
            )
        except ConfigurationValidationError as e:
            self.report.add_error("evaluation_settings", str(e))
            return EvaluationSettings()


class ConfigurationLoader:
    """Loads configuration files with error handling."""

    def __init__(self, config_path: str):
        self.config_path = config_path

    def load_file(self) -> Dict[str, Any]:
        """Load configuration file with comprehensive error handling."""
        try:
            with open(self.config_path, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            raise ConfigurationFileNotFoundError(
                f"Configuration file not found: {self.config_path}"
            )
        except json.JSONDecodeError as e:
            raise ConfigurationParseError(f"Invalid JSON in configuration file: {e}")
        except Exception as e:
            raise ConfigurationError(f"Error reading configuration file: {e}")


class ConfigurationProcessor:
    """Main orchestrator for configuration processing."""

    def __init__(self, config_path: str):
        self.loader = ConfigurationLoader(config_path)
        self.env_resolver = EnvironmentVariableResolver()
        self.validator = ConfigurationValidator(self.env_resolver)

    def load_and_process(self) -> Dict[str, Any]:
        """Load and process configuration, returning the same format as original."""
        try:
            raw_config = self.loader.load_file()
            processed_config = self._process_configuration(raw_config)
            if self.validator.report.has_errors():
                error_summary = self.validator.report.get_summary()
                print(f"Configuration validation failed:\n{error_summary}")
                sys.exit(1)

            if self.validator.report.warnings:
                for warning in self.validator.report.warnings:
                    print(f"Warning: {warning}")

            return processed_config

        except ConfigurationFileNotFoundError:
            print(
                f"Error: test_suite_config.json not found at {self.loader.config_path}"
            )
            sys.exit(1)
        except ConfigurationParseError as e:
            print(f"Error: Could not decode JSON from {self.loader.config_path}: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"Error loading configuration: {e}")
            sys.exit(1)

    def _process_configuration(self, raw_config: Dict[str, Any]) -> Dict[str, Any]:
        """Process and validate the raw configuration."""
        config_dir = Path(self.loader.config_path).parent.resolve()

        agents_relative = self.validator.validate_field(
            "agents",
            raw_config.get("agents"),
            self.validator.ROOT_LEVEL_RULES,
            raw_config,
        )
        agents = (
            [
                str(config_dir / p) if not Path(p).is_absolute() else p
                for p in agents_relative
            ]
            if agents_relative
            else []
        )

        test_cases_relative = self.validator.validate_field(
            "test_cases",
            raw_config.get("test_cases"),
            self.validator.ROOT_LEVEL_RULES,
            raw_config,
        )
        test_cases = (
            [
                str(config_dir / p) if not Path(p).is_absolute() else p
                for p in test_cases_relative
            ]
            if test_cases_relative
            else []
        )
        results_dir_name = self.validator.validate_field(
            "results_dir_name",
            raw_config.get("results_dir_name"),
            self.validator.ROOT_LEVEL_RULES,
            raw_config,
        )
        runs = self.validator.validate_field(
            "runs", raw_config.get("runs"), self.validator.ROOT_LEVEL_RULES, raw_config
        )

        llm_models_data = raw_config.get("llm_models", [])
        processed_models = []

        if not llm_models_data:
            self.validator.report.add_error(
                "llm_models", "At least one LLM model is required"
            )
        else:
            for i, model_data in enumerate(llm_models_data):
                model = self.validator.validate_llm_model(model_data, i)
                if model:
                    processed_models.append(
                        {"name": model.name, "env": model.env.variables}
                    )

        evaluation_settings_data = raw_config.get("evaluation_settings", {})
        evaluation_settings = self.validator.validate_evaluation_settings(
            evaluation_settings_data
        )

        processed_eval_settings = {
            "tool_match": {"enabled": evaluation_settings.tool_match_enabled},
            "response_match": {"enabled": evaluation_settings.response_match_enabled},
            "llm_evaluator": {
                "enabled": evaluation_settings.llm_evaluator_enabled,
                "env": (
                    evaluation_settings.llm_evaluator_env.variables
                    if evaluation_settings.llm_evaluator_env
                    else {}
                ),
            },
        }

        if agents and not any(Path(p).name == "eval_backend.yaml" for p in agents):
            project_root = Path.cwd()
            eval_backend_path = str(project_root / "configs" / "eval_backend.yaml")
            agents.append(eval_backend_path)

        return {
            "agents": agents or [],
            "llm_models": processed_models,
            "test_cases": test_cases or [],
            "results_dir_name": results_dir_name or "tests",
            "runs": runs or 1,
            "evaluation_settings": processed_eval_settings,
        }


class ConfigLoader:
    """
    Main configuration loader class that provides a clean interface for loading
    and validating configuration data.
    """

    def __init__(self, config_path: str):
        """
        Initialize the ConfigLoader with a specific config path.

        Args:
            config_path: Path to the configuration file
        """
        self.processor = ConfigurationProcessor(config_path)

    def load_config(self) -> Dict[str, Any]:
        """
        Load configuration from config.json with comprehensive validation.
        Returns the validated configuration data.
        """
        return self.processor.load_and_process()

    def get_evaluation_settings(self) -> Dict[str, Any]:
        """
        Load evaluation settings from the config file with validation.
        Returns the evaluation settings configuration.
        """
        config = self.load_config()
        settings = config.get("evaluation_settings", {})

        tool_match_enabled = settings.get("tool_match", {}).get("enabled", True)
        response_match_enabled = settings.get("response_match", {}).get("enabled", True)

        llm_evaluator_config = settings.get("llm_evaluator", {})
        llm_evaluator_enabled = llm_evaluator_config.get("enabled", False)

        if llm_evaluator_enabled and "env" in llm_evaluator_config:
            env_vars = llm_evaluator_config["env"]
            required_vars = [
                "LLM_SERVICE_PLANNING_MODEL_NAME",
                "LLM_SERVICE_API_KEY",
                "LLM_SERVICE_ENDPOINT",
            ]
            if not all(env_vars.get(var) for var in required_vars):
                print(
                    "Warning: LLM evaluator is enabled, but one or more required environment variables are not set. Disabling LLM evaluator."
                )
                llm_evaluator_config["enabled"] = False

        return {
            "tool_match": {"enabled": tool_match_enabled},
            "response_match": {"enabled": response_match_enabled},
            "llm_evaluator": llm_evaluator_config,
        }
