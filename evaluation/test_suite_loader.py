"""
Modern Pydantic-based configuration loader with comprehensive validation.
Replaces complex custom validation with clean, declarative models.
"""

from pydantic import BaseModel, Field, field_validator, model_validator, ValidationError
from pathlib import Path
import os
import json
import sys
import logging

log = logging.getLogger(__name__)


class EnvironmentVariables(BaseModel):
    """Environment variable configuration with automatic resolution."""
    variables: dict[str, str | None] = Field(default_factory=dict)

    @model_validator(mode='before')
    @classmethod
    def resolve_env_vars(cls, data):
        """Automatically resolve environment variables ending with _VAR."""
        # If data is a dict that doesn't have 'variables' key, treat the whole dict as variables
        if isinstance(data, dict) and 'variables' not in data:
            resolved = {}
            for key, value in data.items():
                if key.endswith("_VAR"):
                    env_var_name = key[:-4]  # Remove '_VAR' suffix
                    env_value = os.getenv(value)
                    if not env_value:
                        log.warning(f"Environment variable '{value}' not set for {env_var_name}")
                    resolved[env_var_name] = env_value
                else:
                    # This is a direct value, include it as-is
                    resolved[key] = value
            return {"variables": resolved}
        return data

    def get(self, key: str, default: str | None = None) -> str | None:
        """Get environment variable value with default."""
        return self.variables.get(key, default)

    def is_complete(self, required_vars: list[str]) -> bool:
        """Check if all required environment variables are present."""
        return all(self.variables.get(var) is not None for var in required_vars)


class ModelConfiguration(BaseModel):
    """Individual LLM model configuration with validation."""
    name: str = Field(min_length=1, description="Model name cannot be empty")
    environment: EnvironmentVariables = Field(alias="env")

    @model_validator(mode='after')
    def validate_essential_vars(self):
        """Ensure essential environment variables are present."""
        essential_vars = ["LLM_SERVICE_PLANNING_MODEL_NAME"]
        if not any(var in self.environment.variables for var in essential_vars):
            raise ValueError(f"Model '{self.name}' must have at least one of: {essential_vars}")
        return self


class EvaluationOptions(BaseModel):
    """Evaluation behavior settings with conditional validation."""
    tool_matching_enabled: bool = Field(default=True)
    response_matching_enabled: bool = Field(default=True)
    llm_evaluation_enabled: bool = Field(default=False)
    llm_evaluator_environment: EnvironmentVariables | None = Field(default=None)

    @model_validator(mode='after')
    def validate_llm_evaluator_config(self):
        """Validate LLM evaluator configuration when enabled."""
        if self.llm_evaluation_enabled:
            if not self.llm_evaluator_environment:
                raise ValueError("llm_evaluator_environment is required when llm_evaluation_enabled is true")

            required_vars = [
                "LLM_SERVICE_PLANNING_MODEL_NAME",
                "LLM_SERVICE_ENDPOINT",
                "LLM_SERVICE_API_KEY"
            ]
            if not self.llm_evaluator_environment.is_complete(required_vars):
                raise ValueError(f"LLM evaluator requires environment variables: {required_vars}")
        return self


class TestSuiteConfiguration(BaseModel):
    """Complete test suite configuration with comprehensive validation."""
    agent_configs: list[str] = Field(min_length=1, alias="agents")
    model_configurations: list[ModelConfiguration] = Field(min_length=1, alias="llm_models")
    test_case_files: list[str] = Field(min_length=1, alias="test_cases") 
    results_directory: str = Field(default="tests", min_length=1, alias="results_dir_name")
    run_count: int = Field(default=1, ge=1, alias="runs")
    evaluation_options: EvaluationOptions = Field(default_factory=EvaluationOptions, alias="evaluation_settings")

    @field_validator('agent_configs', 'test_case_files', mode='before')
    @classmethod
    def resolve_relative_paths(cls, v: list[str], info) -> list[str]:
        """Convert relative paths to absolute paths."""
        config_dir = getattr(info.context, 'config_dir', Path.cwd())
        return [str(config_dir / p) if not Path(p).is_absolute() else p for p in v]

    @model_validator(mode='after')
    def add_eval_backend_if_missing(self):
        """Add eval_backend.yaml if not present in agent configs."""
        if not any(Path(p).name == "eval_backend.yaml" for p in self.agent_configs):
            project_root = Path.cwd()
            eval_backend_path = str(project_root / "configs" / "eval_backend.yaml")
            self.agent_configs.append(eval_backend_path)
        return self


class ConfigurationParser:
    """Handles raw JSON parsing and transformation."""

    def __init__(self, config_path: str):
        self.config_path = Path(config_path)
        self.config_dir = self.config_path.parent.resolve()

    def load_raw_config(self) -> dict[str, any]:
        """Load raw JSON configuration."""
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            log.error(f"Configuration file not found: {self.config_path}")
            sys.exit(1)
        except json.JSONDecodeError as e:
            log.error(f"Invalid JSON in configuration file: {e}")
            sys.exit(1)

    def transform_evaluation_settings(self, raw_settings: dict[str, any]) -> dict[str, any]:
        """Transform nested evaluation settings structure."""
        result = {
            "tool_matching_enabled": raw_settings.get("tool_match", {}).get("enabled", True),
            "response_matching_enabled": raw_settings.get("response_match", {}).get("enabled", True),
            "llm_evaluation_enabled": raw_settings.get("llm_evaluator", {}).get("enabled", False),
            "llm_evaluator_environment": None
        }

        # Handle LLM evaluator environment if enabled
        if result["llm_evaluation_enabled"]:
            env_data = raw_settings.get("llm_evaluator", {}).get("env", {})
            if env_data:
                # Pre-resolve environment variables for evaluation settings
                resolved_env = {}
                for key, value in env_data.items():
                    if key.endswith("_VAR"):
                        env_var_name = key[:-4]  # Remove '_VAR' suffix
                        env_value = os.getenv(value)
                        if env_value:  # Only include if environment variable is set
                            resolved_env[env_var_name] = env_value
                    else:
                        resolved_env[key] = value

                result["llm_evaluator_environment"] = EnvironmentVariables(variables=resolved_env)

        return result


class EvaluationConfigLoader:
    """Modern configuration loader using Pydantic validation."""

    def __init__(self, config_path: str):
        self.parser = ConfigurationParser(config_path)

    def load_configuration(self) -> TestSuiteConfiguration:
        """Load and validate configuration, returning Pydantic model."""
        try:
            # Load raw JSON
            raw_config = self.parser.load_raw_config()

            # Transform evaluation settings structure
            if "evaluation_settings" in raw_config:
                raw_config["evaluation_settings"] = self.parser.transform_evaluation_settings(
                    raw_config["evaluation_settings"]
                )

            config = TestSuiteConfiguration.model_validate(
                raw_config,
                context={'config_dir': self.parser.config_dir}
            )

            log.info("Configuration loaded and validated successfully.")
            return config

        except ValidationError as e:
            self._handle_validation_error(e)
            sys.exit(1)

    def get_evaluation_options(self) -> EvaluationOptions:
        """Get evaluation options from configuration."""
        config = self.load_configuration()
        return config.evaluation_options

    def _handle_validation_error(self, e: ValidationError):
        """Convert Pydantic validation errors to user-friendly format."""
        log.error("Configuration validation failed:")
        for error in e.errors():
            field_path = " -> ".join(str(loc) for loc in error['loc'])
            message = error['msg']
            log.error(f"  Field '{field_path}': {message}")
