"""
Pydantic configuration models for proxy applications.
"""

from typing import List, Literal, Optional

from pydantic import Field, model_validator

from ....common.utils.pydantic_utils import SamConfigBase


class ArtifactServiceConfig(SamConfigBase):
    """Configuration for the shared Artifact Service."""

    type: str = Field(
        ..., description="Service type (e.g., 'memory', 'gcs', 'filesystem')."
    )
    base_path: Optional[str] = Field(
        default=None,
        description="Base directory path (required for type 'filesystem').",
    )
    bucket_name: Optional[str] = Field(
        default=None, description="GCS bucket name (required for type 'gcs')."
    )
    artifact_scope: Literal["namespace", "app", "custom"] = Field(
        default="namespace", description="Process-wide scope for all artifact services."
    )
    artifact_scope_value: Optional[str] = Field(
        default=None,
        description="Custom identifier for artifact scope (required if artifact_scope is 'custom').",
    )

    @model_validator(mode="after")
    def check_artifact_scope(self) -> "ArtifactServiceConfig":
        if self.artifact_scope == "custom" and not self.artifact_scope_value:
            raise ValueError(
                "'artifact_scope_value' is required when 'artifact_scope' is 'custom'."
            )
        if self.artifact_scope != "custom" and self.artifact_scope_value:
            from solace_ai_connector.common.log import log
            log.warning(
                "Configuration Warning: 'artifact_scope_value' is ignored when 'artifact_scope' is not 'custom'."
            )
        return self


class ProxiedAgentConfig(SamConfigBase):
    """Base configuration for a proxied agent."""

    name: str = Field(
        ...,
        description="The name the agent will have on the Solace mesh.",
    )
    request_timeout_seconds: Optional[int] = Field(
        default=None,
        description="Optional timeout override for this specific agent.",
    )


class BaseProxyAppConfig(SamConfigBase):
    """Base configuration for all proxy applications."""

    namespace: str = Field(
        ...,
        description="Absolute topic prefix for A2A communication (e.g., 'myorg/dev').",
    )
    proxied_agents: List[ProxiedAgentConfig] = Field(
        ...,
        min_length=1,
        description="A list of downstream agents to be proxied.",
    )
    artifact_service: ArtifactServiceConfig = Field(
        default_factory=lambda: ArtifactServiceConfig(type="memory"),
        description="Configuration for the shared Artifact Service.",
    )
    discovery_interval_seconds: int = Field(
        default=60,
        ge=0,
        description="Interval (seconds) to re-fetch agent cards. <= 0 disables periodic discovery.",
    )
    default_request_timeout_seconds: int = Field(
        default=300,
        gt=0,
        description="Default timeout in seconds for requests to downstream agents.",
    )
