"""
Feature flag response DTOs.
"""

from pydantic import BaseModel, ConfigDict, Field


class FeatureFlagResponse(BaseModel):
    """Evaluated state of a single feature flag."""

    model_config = ConfigDict(populate_by_name=True)

    key: str = Field(..., description="Unique snake_case flag identifier")
    name: str = Field(..., description="Human-readable label for the flag")
    release_phase: str = Field(
        ...,
        description="Lifecycle phase: early_access, beta, experimental, or ga",
    )
    resolved: bool = Field(
        ...,
        description="Effective on/off after applying all evaluation tiers",
    )
    has_env_override: bool = Field(
        ...,
        description="True when a SAM_FEATURE_<KEY> environment variable is set",
    )
    registry_default: bool = Field(
        ..., description="Baseline value declared in the flag's definition"
    )
    description: str = Field(
        ..., description="Brief explanation of what the flag controls"
    )
