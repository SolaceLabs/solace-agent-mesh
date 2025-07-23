"""
Initializes ADK Services based on configuration.
"""

import os
import re
from typing import Dict

from solace_ai_connector.common.log import log

from google.adk.sessions import (
    BaseSessionService,
    InMemorySessionService,
    DatabaseSessionService,
    VertexAiSessionService,
)
from google.adk.artifacts import (
    BaseArtifactService,
    InMemoryArtifactService,
    GcsArtifactService,
)
from google.adk.memory import (
    BaseMemoryService,
    InMemoryMemoryService,
    VertexAiRagMemoryService,
)

from .filesystem_artifact_service import FilesystemArtifactService

try:
    from tests.integration.infrastructure.artifact_service.service import (
        TestInMemoryArtifactService,
    )
except ImportError:
    TestInMemoryArtifactService = None


def _sanitize_for_path(identifier: str) -> str:
    """Sanitizes a string to be safe for use as a directory name."""
    if not identifier:
        return "_invalid_scope_"
    sanitized = re.sub(r'[\\/*?:"<>|]', "_", identifier)
    sanitized = re.sub(r"_+", "_", sanitized)
    sanitized = sanitized.strip("_ ")
    if not sanitized:
        return "_empty_scope_"
    return sanitized


def initialize_session_service(component) -> BaseSessionService:
    """Initializes the ADK Session Service based on configuration."""
    config: Dict = component.get_config("session_service", {})
    service_type = config.get("type", "memory").lower()
    log.info(
        "%s Initializing Session Service of type: %s",
        component.log_identifier,
        service_type,
    )

    if service_type == "memory":
        return InMemorySessionService()
    elif service_type == "database":
        db_url = config.get("db_url")
        if not db_url:
            raise ValueError(
                f"{component.log_identifier} 'db_url' is required for database session service."
            )
        try:
            return DatabaseSessionService(db_url=db_url)
        except ImportError:
            log.error(
                "%s SQLAlchemy not installed. Please install 'google-adk[database]' or 'sqlalchemy'.",
                component.log_identifier,
            )
            raise
    elif service_type == "vertex":
        project = os.environ.get("GOOGLE_CLOUD_PROJECT")
        location = os.environ.get("GOOGLE_CLOUD_LOCATION")
        if not project or not location:
            raise ValueError(
                f"{component.log_identifier} GOOGLE_CLOUD_PROJECT and GOOGLE_CLOUD_LOCATION env vars required for vertex session service."
            )
        return VertexAiSessionService(project=project, location=location)
    else:
        raise ValueError(
            f"{component.log_identifier} Unsupported session service type: {service_type}"
        )


def initialize_artifact_service(component) -> BaseArtifactService:
    """Initializes the ADK Artifact Service based on configuration."""
    config: Dict = component.get_config("artifact_service", {"type": "memory"})
    service_type = config.get("type", "memory").lower()
    log.info(
        "%s Initializing Artifact Service of type: %s",
        component.log_identifier,
        service_type,
    )

    if service_type == "memory":
        return InMemoryArtifactService()
    elif service_type == "gcs":
        bucket_name = config.get("bucket_name")
        if not bucket_name:
            raise ValueError(
                f"{component.log_identifier} 'bucket_name' is required for GCS artifact service."
            )
        try:
            gcs_args = {
                k: v for k, v in config.items() if k not in ["type", "bucket_name"]
            }
            return GcsArtifactService(bucket_name=bucket_name, **gcs_args)
        except ImportError:
            log.error(
                "%s google-cloud-storage not installed. Please install 'google-adk[gcs]' or 'google-cloud-storage'.",
                component.log_identifier,
            )
            raise
    elif service_type == "filesystem":
        base_path = config.get("base_path")
        if not base_path:
            raise ValueError(
                f"{component.log_identifier} 'base_path' is required for filesystem artifact service."
            )

        artifact_scope = config.get("artifact_scope", "namespace").lower()
        scope_identifier_raw = None

        if artifact_scope == "app":
            app_instance = component.get_app()
            if not app_instance or not app_instance.name:
                raise ValueError(
                    f"{component.log_identifier} Cannot determine app name for 'app' scope."
                )
            scope_identifier_raw = app_instance.name
            log.info(
                "%s Using 'app' scope for filesystem artifacts: %s",
                component.log_identifier,
                scope_identifier_raw,
            )
        elif artifact_scope == "namespace":
            scope_identifier_raw = component.get_config("namespace")
            log.info(
                "%s Using 'namespace' scope for filesystem artifacts: %s",
                component.log_identifier,
                scope_identifier_raw,
            )
        elif artifact_scope == "custom":
            scope_identifier_raw = config.get("artifact_scope_value")
            if not scope_identifier_raw:
                raise ValueError(
                    f"{component.log_identifier} 'artifact_scope_value' is required when artifact_scope is 'custom'."
                )
            log.info(
                "%s Using 'custom' scope for filesystem artifacts: %s",
                component.log_identifier,
                scope_identifier_raw,
            )
        else:
            raise ValueError(
                f"{component.log_identifier} Invalid 'artifact_scope' value: {artifact_scope}"
            )

        if not scope_identifier_raw:
            raise ValueError(
                f"{component.log_identifier} Failed to determine scope identifier for filesystem artifacts."
            )

        scope_identifier_sanitized = _sanitize_for_path(scope_identifier_raw)
        log.info(
            "%s Sanitized scope identifier: %s",
            component.log_identifier,
            scope_identifier_sanitized,
        )

        try:
            return FilesystemArtifactService(
                base_path=base_path, scope_identifier=scope_identifier_sanitized
            )
        except Exception as e:
            log.error(
                "%s Failed to initialize FilesystemArtifactService: %s",
                component.log_identifier,
                e,
            )
            raise
    elif service_type == "test_in_memory":
        if TestInMemoryArtifactService is None:
            log.error(
                "%s TestInMemoryArtifactService is configured but could not be imported. "
                "Ensure test infrastructure is in PYTHONPATH if running tests, or check configuration.",
                component.log_identifier,
            )
            raise ImportError("TestInMemoryArtifactService not available.")
        log.info(
            "%s Using TestInMemoryArtifactService for testing.",
            component.log_identifier,
        )
        return TestInMemoryArtifactService()
    else:
        raise ValueError(
            f"{component.log_identifier} Unsupported artifact service type: {service_type}"
        )


def initialize_memory_service(component) -> BaseMemoryService:
    """Initializes the ADK Memory Service based on configuration."""
    config: Dict = component.get_config("memory_service", {"type": "memory"})
    service_type = config.get("type", "memory").lower()
    log.info(
        "%s Initializing Memory Service of type: %s",
        component.log_identifier,
        service_type,
    )

    if service_type == "memory":
        return InMemoryMemoryService()
    elif service_type == "vertex_rag":
        try:
            rag_args = {
                k: v for k, v in config.items() if k not in ["type", "default_behavior"]
            }
            return VertexAiRagMemoryService(**rag_args)
        except ImportError:
            log.error(
                "%s google-cloud-aiplatform not installed. Please install 'google-adk[vertex]' or 'google-cloud-aiplatform'.",
                component.log_identifier,
            )
            raise
        except TypeError as e:
            log.error(
                "%s Error initializing VertexAiRagMemoryService: %s. Check config params.",
                component.log_identifier,
                e,
            )
            raise
    else:
        raise ValueError(
            f"{component.log_identifier} Unsupported memory service type: {service_type}"
        )
