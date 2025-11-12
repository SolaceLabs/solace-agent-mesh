"""
Initializes ADK Services based on configuration.
"""

import logging
import os
import re
from typing import Any, Dict, List, Optional

from google.adk.artifacts import (
    BaseArtifactService,
    GcsArtifactService,
    InMemoryArtifactService,
)
from google.adk.artifacts.base_artifact_service import ArtifactVersion
from google.adk.auth.credential_service.base_credential_service import (
    BaseCredentialService,
)
from google.adk.auth.credential_service.in_memory_credential_service import (
    InMemoryCredentialService,
)
from google.adk.memory import (
    BaseMemoryService,
    InMemoryMemoryService,
    VertexAiRagMemoryService,
)
from google.adk.sessions import (
    BaseSessionService,
    DatabaseSessionService,
    InMemorySessionService,
    VertexAiSessionService,
)
from google.genai import types as adk_types
from typing_extensions import override

from .artifacts.filesystem_artifact_service import FilesystemArtifactService
from .schema_migration import run_migrations

log = logging.getLogger(__name__)

try:
    from sam_test_infrastructure.artifact_service.service import (
        TestInMemoryArtifactService,
    )
except ImportError:
    TestInMemoryArtifactService = None


class ScopedArtifactServiceWrapper(BaseArtifactService):
    """
    A wrapper for an artifact service that transparently applies a configured scope.
    This ensures all artifact operations respect either 'namespace' or 'app' scoping
    without requiring changes at the call site. It dynamically checks the component's
    configuration on each call to support test-specific overrides.
    """

    def __init__(
        self,
        wrapped_service: BaseArtifactService,
        component: Any,
    ):
        """
        Initializes the ScopedArtifactServiceWrapper.

        Args:
            wrapped_service: The concrete artifact service instance (e.g., InMemory, GCS).
            component: The component instance (agent or gateway) that owns this service.
        """
        self.wrapped_service = wrapped_service
        self.component = component

    def _get_scoped_app_name(self, app_name: str) -> str:
        """
        Determines the effective app_name for an artifact operation by dynamically
        checking the component's configuration.
        """
        # The component's get_config will handle test-injected overrides.
        # The default scope is 'namespace' as defined in the app schema.
        scope_type = self.component.get_config("artifact_scope", "namespace")

        if scope_type == "namespace":
            # For namespace scope, the value is always the component's namespace.
            return self.component.namespace

        # For 'app' scope, use the app_name that was passed into the method, which is
        # typically the agent_name or gateway_id.
        return app_name

    @override
    async def save_artifact(
        self,
        *,
        app_name: str,
        user_id: str,
        session_id: str,
        filename: str,
        artifact: adk_types.Part,
    ) -> int:
        scoped_app_name = self._get_scoped_app_name(app_name)
        return await self.wrapped_service.save_artifact(
            app_name=scoped_app_name,
            user_id=user_id,
            session_id=session_id,
            filename=filename,
            artifact=artifact,
        )

    @override
    async def load_artifact(
        self,
        *,
        app_name: str,
        user_id: str,
        session_id: str,
        filename: str,
        version: Optional[int] = None,
    ) -> Optional[adk_types.Part]:
        scoped_app_name = self._get_scoped_app_name(app_name)
        return await self.wrapped_service.load_artifact(
            app_name=scoped_app_name,
            user_id=user_id,
            session_id=session_id,
            filename=filename,
            version=version,
        )

    @override
    async def list_artifact_keys(
        self, *, app_name: str, user_id: str, session_id: str
    ) -> List[str]:
        scoped_app_name = self._get_scoped_app_name(app_name)
        return await self.wrapped_service.list_artifact_keys(
            app_name=scoped_app_name, user_id=user_id, session_id=session_id
        )

    @override
    async def delete_artifact(
        self, *, app_name: str, user_id: str, session_id: str, filename: str
    ) -> None:
        scoped_app_name = self._get_scoped_app_name(app_name)
        await self.wrapped_service.delete_artifact(
            app_name=scoped_app_name,
            user_id=user_id,
            session_id=session_id,
            filename=filename,
        )
        return

    @override
    async def list_versions(
        self, *, app_name: str, user_id: str, session_id: str, filename: str
    ) -> List[int]:
        scoped_app_name = self._get_scoped_app_name(app_name)
        return await self.wrapped_service.list_versions(
            app_name=scoped_app_name,
            user_id=user_id,
            session_id=session_id,
            filename=filename,
        )

    @override
    async def list_artifact_versions(
        self,
        *,
        app_name: str,
        user_id: str,
        filename: str,
        session_id: str,
    ) -> List[ArtifactVersion]:
        scoped_app_name = self._get_scoped_app_name(app_name)
        return await self.wrapped_service.list_artifact_versions(
            app_name=scoped_app_name,
            user_id=user_id,
            filename=filename,
            session_id=session_id,
        )

    @override
    async def get_artifact_version(
        self,
        *,
        app_name: str,
        user_id: str,
        filename: str,
        session_id: str,
        version: Optional[int] = None,
    ) -> Optional[ArtifactVersion]:
        scoped_app_name = self._get_scoped_app_name(app_name)
        return await self.wrapped_service.get_artifact_version(
            app_name=scoped_app_name,
            user_id=user_id,
            filename=filename,
            session_id=session_id,
            version=version,
        )


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
    config = component.get_config("session_service", {})

    # Handle both dict and SessionServiceConfig object
    if hasattr(config, "type"):
        service_type = config.type.lower()
        db_url = getattr(config, "database_url", None)
    else:
        service_type = config.get("type", "memory").lower()
        db_url = config.get("database_url")

    log.info(
        "%s Initializing Session Service of type: %s",
        component.log_identifier,
        service_type,
    )

    if service_type == "memory":
        return InMemorySessionService()
    elif service_type == "sql":
        if not db_url:
            raise ValueError(
                f"{component.log_identifier} 'database_url' is required for sql session service."
            )
        try:
            db_service = DatabaseSessionService(db_url=db_url)
            run_migrations(db_service, component)
            return db_service
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
    """
    Initializes the ADK Artifact Service based on configuration.
    This factory creates the concrete service instance and then wraps it with
    the ScopedArtifactServiceWrapper to enforce artifact scoping rules dynamically.
    """
    config: Dict = component.get_config("artifact_service", {"type": "memory"})
    service_type = config.get("type", "memory").lower()
    log.info(
        "%s Initializing Artifact Service of type: %s",
        component.log_identifier,
        service_type,
    )

    concrete_service: BaseArtifactService
    if service_type == "memory":
        concrete_service = InMemoryArtifactService()
    elif service_type == "gcs":
        bucket_name = config.get("bucket_name")
        if not bucket_name:
            raise ValueError(
                f"{component.log_identifier} 'bucket_name' is required for GCS artifact service."
            )
        try:
            gcs_args = {
                k: v
                for k, v in config.items()
                if k not in ["type", "bucket_name", "artifact_scope"]
            }
            concrete_service = GcsArtifactService(bucket_name=bucket_name, **gcs_args)
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

        try:
            concrete_service = FilesystemArtifactService(base_path=base_path)
        except Exception as e:
            log.error(
                "%s Failed to initialize FilesystemArtifactService: %s",
                component.log_identifier,
                e,
            )
            raise
    elif service_type == "s3":
        bucket_name = config.get("bucket_name")
        if not bucket_name or not bucket_name.strip():
            raise ValueError(
                f"{component.log_identifier} 'bucket_name' is required and cannot be empty for S3 artifact service."
            )

        try:
            from .artifacts.s3_artifact_service import S3ArtifactService

            # Whitelist of valid parameters for the boto3 S3 client.
            valid_boto3_params = [
                "aws_access_key_id",
                "aws_secret_access_key",
                "aws_session_token",
                "region_name",
                "config",
            ]

            s3_config = {}

            # Explicitly map the 'region' from our config to 'region_name' for boto3.
            if config.get("region"):
                s3_config["region_name"] = config.get("region")

            # Copy any other valid parameters from the config.
            for key in valid_boto3_params:
                if key in config and config[key] is not None:
                    s3_config[key] = config[key]

            # Set credentials from environment variables as a fallback.
            endpoint_url = config.get("endpoint_url") or os.environ.get("S3_ENDPOINT_URL") or "https://s3.amazonaws.com"
            s3_config["endpoint_url"] = endpoint_url

            if "aws_access_key_id" not in s3_config:
                env_access_key = os.environ.get("AWS_ACCESS_KEY_ID")
                if env_access_key is not None:
                    s3_config["aws_access_key_id"] = env_access_key
            if "aws_secret_access_key" not in s3_config:
                env_secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
                if env_secret_key is not None:
                    s3_config["aws_secret_access_key"] = env_secret_key

            # Filter out any keys that ended up with a None value.
            s3_config_cleaned = {k: v for k, v in s3_config.items() if v is not None}

            concrete_service = S3ArtifactService(bucket_name=bucket_name, **s3_config_cleaned)
        except ImportError as e:
            log.error(
                "%s S3 dependencies not available: %s",
                component.log_identifier,
                e,
            )
            raise
        except Exception as e:
            log.error(
                "%s Failed to initialize S3ArtifactService: %s",
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
        concrete_service = TestInMemoryArtifactService()
    else:
        raise ValueError(
            f"{component.log_identifier} Unsupported artifact service type: {service_type}"
        )

    # Wrap the concrete service to enforce scoping dynamically.
    # The wrapper will query the component's config at runtime.
    log.info(
        "%s Wrapping artifact service with dynamic ScopedArtifactServiceWrapper.",
        component.log_identifier,
    )
    return ScopedArtifactServiceWrapper(
        wrapped_service=concrete_service,
        component=component,
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


def initialize_credential_service(component) -> BaseCredentialService | None:
    """Initializes the ADK Credential Service based on configuration."""
    config = component.get_config("credential_service", None)

    # If no credential service is configured, return None
    if config is None:
        log.info(
            "%s No credential service configured, skipping initialization",
            component.log_identifier,
        )
        return None

    # Handle both dict and CredentialServiceConfig object
    if hasattr(config, "type"):
        service_type = config.type.lower()
    else:
        service_type = config.get("type", "memory").lower()

    log.info(
        "%s Initializing Credential Service of type: %s",
        component.log_identifier,
        service_type,
    )

    if service_type == "memory":
        return InMemoryCredentialService()
    else:
        raise ValueError(
            f"{component.log_identifier} Unsupported credential service type: {service_type}"
        )
