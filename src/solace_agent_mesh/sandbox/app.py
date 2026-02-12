"""
Sandbox Worker Application.

This module defines the SandboxWorkerApp class which configures the
sandbox worker component with appropriate Solace subscriptions and
broker settings. Subscriptions are derived from the tool manifest.
"""

import logging
from typing import Any, Dict, List, Optional

from pydantic import Field, ValidationError

from ..common.app_base import SamAppBase
from ..common.a2a import (
    get_sam_remote_tool_invoke_topic,
    get_discovery_subscription_topic,
)
from ..common.utils.pydantic_utils import SamConfigBase
from .component import SandboxWorkerComponent
from .manifest import ToolManifest

log = logging.getLogger(__name__)

info = {
    "class_name": "SandboxWorkerApp",
    "description": "Application for running sandboxed Python tools via bubblewrap (bwrap).",
}


# --- Pydantic Models for Configuration Validation ---


class SandboxConfig(SamConfigBase):
    """Configuration for sandbox execution.

    Supports two modes:
    - 'bwrap': Full bubblewrap sandboxing (Linux, containers) — default
    - 'direct': Plain subprocess (no isolation) — for local dev on any OS
    """

    mode: str = Field(
        default="bwrap",
        description="Execution mode: 'bwrap' for sandboxed, 'direct' for plain subprocess (dev).",
    )
    python_bin: str = Field(
        default="/usr/local/bin/python3",
        description="Python binary path (used in both bwrap and direct modes).",
    )
    work_base_dir: str = Field(
        default="/sandbox/work",
        description="Base directory for tool execution work directories.",
    )
    default_profile: str = Field(
        default="standard",
        description="Default sandbox profile to use (restrictive, standard, permissive).",
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
    manifest_path: str = Field(
        default="/tools/manifest.yaml",
        description="Path to the tool manifest YAML file.",
    )
    tools_python_dir: str = Field(
        default="/tools/python",
        description="Directory containing Python tool modules.",
    )
    max_message_size_bytes: int = Field(
        default=10_000_000,
        description="Maximum message size in bytes.",
    )
    default_timeout_seconds: int = Field(
        default=300,
        description="Default timeout for tool executions in seconds.",
    )
    sandbox: SandboxConfig = Field(
        default_factory=SandboxConfig,
        description="Configuration for bubblewrap sandbox execution.",
    )
    artifact_service: ArtifactServiceConfig = Field(
        default_factory=lambda: ArtifactServiceConfig(type="memory"),
        description="Configuration for the artifact service.",
    )


class SandboxWorkerApp(SamAppBase):
    """
    Application class for the Sandbox Worker.

    Configures the sandbox worker component with appropriate Solace
    subscriptions and broker settings. Subscriptions are derived from
    the tool manifest - one topic per tool.
    """

    app_schema = {}

    def __init__(self, app_info: Dict[str, Any], **kwargs):
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
        manifest_path = app_config.get("manifest_path")

        log.info(
            "Configuring SandboxWorkerApp: worker_id='%s' in namespace='%s'",
            worker_id,
            namespace,
        )

        # Read manifest to build initial per-tool subscriptions
        manifest = ToolManifest(manifest_path)
        tool_names = manifest.get_tool_names()

        required_topics = []

        # One subscription per tool from the manifest
        for tool_name in sorted(tool_names):
            required_topics.append(
                get_sam_remote_tool_invoke_topic(namespace, tool_name)
            )

        # Discovery messages (to track available agents if needed)
        required_topics.append(get_discovery_subscription_topic(namespace))

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
