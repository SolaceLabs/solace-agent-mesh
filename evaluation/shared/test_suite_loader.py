"""
Modern Pydantic-based configuration loader with comprehensive validation.
Replaces complex custom validation with clean, declarative models.
"""

import json
import logging
import sys
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator
from solace.messaging.config.solace_properties import (
    authentication_properties,
    service_properties,
    transport_layer_properties,
    transport_layer_security_properties,
)

from .constants import (
    BROKER_REQUIRED_FIELDS,
    DEFAULT_CONNECTION_TIMEOUT,
    DEFAULT_RECONNECT_ATTEMPTS,
    DEFAULT_RECONNECT_DELAY,
    DEFAULT_RUN_COUNT,
    DEFAULT_WORKERS,
    MAX_WORKERS,
    REMOTE_REQUIRED_FIELDS,
)
from .helpers import resolve_env_vars

log = logging.getLogger(__name__)


class EnvironmentVariables(BaseModel):
    """Environment variable configuration with automatic resolution."""
    variables: dict[str, str | None] = Field(default_factory=dict)

    @model_validator(mode='before')
    @classmethod
    def build_variables(cls, data: any) -> any:
        """Build a variables dictionary from raw data."""
        if isinstance(data, dict) and 'variables' not in data:
            return {"variables": resolve_env_vars(data)}
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


class RemoteConfig(BaseModel):
    """Remote configuration with environment variable support."""
    environment: EnvironmentVariables

    @model_validator(mode='before')
    @classmethod
    def build_environment(cls, data: any) -> any:
        if isinstance(data, dict):
            # All fields are environment variables
            return {"environment": data}
        return data

    @model_validator(mode='after')
    def sanitize_namespace(self):
        """Remove trailing slashes from EVAL_NAMESPACE."""
        if self.environment and "EVAL_NAMESPACE" in self.environment.variables:
            namespace = self.environment.variables.get("EVAL_NAMESPACE")
            if namespace:
                self.environment.variables["EVAL_NAMESPACE"] = namespace.rstrip("/")
        return self


class BrokerConfig(BaseModel):
    """Broker connection configuration with validation and environment variable resolution."""
    host: str | None = Field(default=None, alias="SOLACE_BROKER_URL")
    vpn_name: str | None = Field(default=None, alias="SOLACE_BROKER_VPN")
    username: str | None = Field(default=None, alias="SOLACE_BROKER_USERNAME")
    password: str | None = Field(default=None, alias="SOLACE_BROKER_PASSWORD")
    cert_validated: bool = False
    connection_timeout: int = DEFAULT_CONNECTION_TIMEOUT
    reconnect_attempts: int = DEFAULT_RECONNECT_ATTEMPTS
    reconnect_delay: float = DEFAULT_RECONNECT_DELAY

    @model_validator(mode='before')
    @classmethod
    def resolve_env_vars(cls, data: dict) -> dict:
        """Resolve environment variables for broker configuration."""
        return resolve_env_vars(data)

    @model_validator(mode='after')
    def check_required_fields(self):
        """Ensure all required broker fields are present."""
        missing_fields = [field for field in BROKER_REQUIRED_FIELDS if getattr(self, field) is None]
        if missing_fields:
            raise ValueError(f"Broker configuration is missing required fields: {missing_fields}")
        return self

    def to_solace_properties(self) -> dict[str, any]:
        """Convert to Solace messaging properties."""
        return {
            transport_layer_properties.HOST: self.host,
            service_properties.VPN_NAME: self.vpn_name,
            authentication_properties.SCHEME_BASIC_USER_NAME: self.username,
            authentication_properties.SCHEME_BASIC_PASSWORD: self.password,
            transport_layer_security_properties.CERT_VALIDATED: self.cert_validated,
        }


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
    broker: BrokerConfig
    agent_configs: list[str] | None = Field(default=None, min_length=1, alias="agents")
    model_configurations: list[ModelConfiguration] | None = Field(default=None, min_length=1, alias="llm_models")
    remote: RemoteConfig | None = Field(default=None)
    test_case_files: list[str] = Field(min_length=1, alias="test_cases")
    results_directory: str = Field(min_length=1, alias="results_dir_name")
    run_count: int = Field(default=DEFAULT_RUN_COUNT, ge=1, alias="runs")
    workers: int = Field(default=DEFAULT_WORKERS, ge=1, le=MAX_WORKERS)
    evaluation_options: EvaluationOptions = Field(default_factory=EvaluationOptions, alias="evaluation_settings")

    @field_validator('agent_configs', 'test_case_files', mode='before')
    @classmethod
    def resolve_relative_paths(cls, v: list[str], info) -> list[str]:
        """Convert relative paths to absolute paths."""
        if not v:
            return v
        config_dir = getattr(info.context, 'config_dir', Path.cwd())
        return [str(config_dir / p) if not Path(p).is_absolute() else p for p in v]

    @model_validator(mode='after')
    def add_eval_backend_if_missing(self):
        """Add eval_backend.yaml if not present in agent configs."""
        if self.agent_configs and not any(Path(p).name == "eval_backend.yaml" for p in self.agent_configs):
            project_root = Path.cwd()
            eval_backend_path = str(project_root / "configs" / "eval_backend.yaml")
            self.agent_configs.append(eval_backend_path)
        return self

    @model_validator(mode='after')
    def validate_configuration_mode(self):
        """Validate that either remote or local configuration is correctly provided."""
        is_remote = self.remote is not None
        is_local = self.agent_configs is not None and self.model_configurations is not None

        if is_remote and is_local:
            raise ValueError("Configuration cannot have both 'remote' and local settings ('agents', 'llm_models').")

        if is_remote and (self.agent_configs or self.model_configurations):
            raise ValueError("When 'remote' is provided, 'agents' and 'llm_models' must not be set.")

        if is_remote and not self.remote.environment.is_complete(REMOTE_REQUIRED_FIELDS):
            raise ValueError(f"Remote configuration requires environment variables: {REMOTE_REQUIRED_FIELDS}")

        if not is_remote and not is_local:
            raise ValueError("Configuration must include either 'remote' or local settings ('agents', 'llm_models').")

        return self


class ConfigurationParser:
    """Handles raw JSON parsing and transformation."""

    def __init__(self, config_path: str):
        self.config_path = Path(config_path)
        self.config_dir = self.config_path.parent.resolve()

    def load_raw_config(self) -> dict[str, any]:
        """Load raw JSON configuration."""
        try:
            with open(self.config_path) as f:
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
                result["llm_evaluator_environment"] = env_data

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
