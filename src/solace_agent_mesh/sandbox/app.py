"""
Sandbox Worker Application.

This module defines the SandboxWorkerApp class which configures the
sandbox worker component with appropriate Solace subscriptions and
broker settings.
"""

import logging
from typing import Any, Dict, List, Optional

from pydantic import Field, ValidationError

from ..common.app_base import SamAppBase
from ..common.a2a import (
    get_sandbox_request_topic,
    get_discovery_subscription_topic,
)
from ..common.utils.pydantic_utils import SamConfigBase
from .component import SandboxWorkerComponent

log = logging.getLogger(__name__)

info = {
    "class_name": "SandboxWorkerApp",
    "description": "Application for running sandboxed Python tools via nsjail.",
}


# --- Pydantic Models for Configuration Validation ---


class NsjailConfig(SamConfigBase):
    """Configuration for nsjail execution."""

    default_profile: str = Field(
        default="standard",
        description="Default nsjail profile to use (restrictive, standard, permissive).",
    )
    config_dir: str = Field(
        default="/etc/nsjail",
        description="Directory containing nsjail configuration files.",
    )
    max_concurrent_executions: int = Field(
        default=4,
        description="Maximum number of concurrent tool executions.",
    )


class ArtifactServiceConfig(SamConfigBase):
    """Configuration for the artifact service."""

    type: str = Field(
        default="memory",
        description="Type of artifact service (memory, filesystem, s3, gcs).",
    )
    base_path: Optional[str] = Field(
        default=None,
        description="Base path for filesystem artifact service.",
    )
    bucket_name: Optional[str] = Field(
        default=None,
        description="Bucket name for S3/GCS artifact service.",
    )
    region: Optional[str] = Field(
        default=None,
        description="Region for S3 artifact service.",
    )


class SandboxWorkerAppConfig(SamConfigBase):
    """Pydantic model for the sandbox worker application configuration."""

    namespace: str = Field(
        ...,
        description="Absolute topic prefix for A2A communication (e.g., 'myorg/dev').",
    )
    worker_id: str = Field(
        default="sandbox-worker-001",
        description="Unique identifier for this sandbox worker instance.",
    )
    max_message_size_bytes: int = Field(
        default=10_000_000,
        description="Maximum message size in bytes.",
    )
    default_timeout_seconds: int = Field(
        default=300,
        description="Default timeout for tool executions in seconds.",
    )
    nsjail: NsjailConfig = Field(
        default_factory=NsjailConfig,
        description="Configuration for nsjail execution.",
    )
    artifact_service: ArtifactServiceConfig = Field(
        default_factory=lambda: ArtifactServiceConfig(type="memory"),
        description="Configuration for the artifact service.",
    )


class SandboxWorkerApp(SamAppBase):
    """
    Application class for the Sandbox Worker.

    Configures the sandbox worker component with appropriate Solace
    subscriptions and broker settings. Uses the same SAM infrastructure
    as agents and gateways.
    """

    app_schema = {}

    def __init__(self, app_info: Dict[str, Any], **kwargs):
        """
        Initialize the sandbox worker application.

        Args:
            app_info: Application info dictionary containing configuration
            **kwargs: Additional keyword arguments passed to parent class
        """
        log.debug("Initializing SandboxWorkerApp...")

        app_config_dict = app_info.get("app_config", {})

        try:
            # Validate and clean the configuration
            app_config = SandboxWorkerAppConfig.model_validate_and_clean(app_config_dict)
            # Overwrite the raw dict with the validated object
            app_info["app_config"] = app_config
        except ValidationError as e:
            message = SandboxWorkerAppConfig.format_validation_error_message(
                e, app_info.get("name", "unknown"), app_config_dict.get("worker_id")
            )
            log.error("Invalid Sandbox Worker configuration:\n%s", message)
            raise

        namespace = app_config.get("namespace")
        worker_id = app_config.get("worker_id")

        log.info(
            "Configuring SandboxWorkerApp: worker_id='%s' in namespace='%s'",
            worker_id,
            namespace,
        )

        # Generate required topic subscriptions
        required_topics = [
            # Tool invocation requests for this worker
            get_sandbox_request_topic(namespace, worker_id),
            # Discovery messages (to track available agents if needed)
            get_discovery_subscription_topic(namespace),
        ]

        generated_subs = [{"topic": topic} for topic in required_topics]
        log.info(
            "Generated subscriptions for SandboxWorker '%s': %s",
            worker_id,
            generated_subs,
        )

        # Define the component
        component_definition = {
            "name": f"{worker_id}_component",
            "component_class": SandboxWorkerComponent,
            "component_config": {},
            "subscriptions": generated_subs,
        }

        app_info["components"] = [component_definition]
        log.debug("Configured component definition for SandboxWorkerComponent")

        # Configure broker settings
        broker_config = app_info.setdefault("broker", {})
        broker_config["input_enabled"] = True
        broker_config["output_enabled"] = True

        # Generate queue name following SAM conventions
        generated_queue_name = f"{namespace.strip('/')}/q/sandbox/{worker_id}"
        broker_config["queue_name"] = generated_queue_name
        log.debug("Generated broker queue name: %s", generated_queue_name)

        # Use temporary queue by default (can be overridden in config)
        broker_config["temporary_queue"] = app_info.get("broker", {}).get(
            "temporary_queue", True
        )

        super().__init__(app_info, **kwargs)
        log.info("SandboxWorkerApp '%s' initialization complete", worker_id)
