"""
Initializes ADK Services based on configuration.
"""

import logging
import os
import re
from typing import Any, Callable, Dict, List, Optional

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
from google.adk.events import Event as ADKEvent
from google.adk.sessions import (
    BaseSessionService,
    DatabaseSessionService,
    InMemorySessionService,
    Session as ADKSession,
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


def _filter_session_by_latest_compaction(
    session: Optional[ADKSession],
    log_identifier: str = ""
) -> Optional[ADKSession]:
    """
    Proactively filter session.events by most recent compaction event.

    This function finds the most recent compaction event and returns a session
    with events filtered to:
    - The compaction event itself (contains summary)
    - All events after the compaction's end_timestamp

    This eliminates ghost events and prevents re-compaction loops while
    maintaining ADK's append-only event store (DB remains unchanged).

    Args:
        session: The ADK session loaded from DB
        log_identifier: Logging prefix

    Returns:
        Session with filtered events (in-memory only, DB unchanged)
    """
    if not session or not session.events:
        return session

    # If compaction_time is not set → no compaction, return immediately (99% of sessions)
    compaction_time = session.state.get('compaction_time')
    if not compaction_time:
        return session

    latest_compaction = None
    filtered_events = []

    for event in session.events:
        if event.actions and event.actions.compaction:
            # Extract timestamp from this compaction event
            comp = event.actions.compaction
            start_ts = comp['start_timestamp'] if isinstance(comp, dict) else comp.start_timestamp
            end_ts = comp['end_timestamp'] if isinstance(comp, dict) else comp.end_timestamp
            end_ts = max(start_ts, end_ts)  # Defensive handling llmsumarizer inverts start/end

            # Only use this compaction if it matches the stored timestamp
            # to ensure only the LAST matching compaction event is kept
            if end_ts == compaction_time:
                latest_compaction = event
                # Don't append yet - will add after loop to ensure only last one is kept
        elif event.timestamp > compaction_time:
            # Keep events after compaction timestamp
            filtered_events.append(event)

    # Defensive fallback: If compaction_time set but no matching event found
    if not latest_compaction:
        log.error(
            "%s Data inconsistency: compaction_time=%.6f set but no matching compaction event found. Session has %d events total.",
            log_identifier,
            compaction_time,
            len(session.events)
        )
        return session

    # Add the latest compaction event to the beginning of filtered events
    filtered_events.insert(0, latest_compaction)

    # Check if compaction event has actions.compaction with compacted_content
    if hasattr(latest_compaction, 'actions') and latest_compaction.actions and hasattr(latest_compaction.actions, 'compaction'):
        comp = latest_compaction.actions.compaction

        # Handle both dict (from DB) and object (in-memory) forms
        compacted_content = None
        if isinstance(comp, dict):
            compacted_content = comp.get('compacted_content')
        elif hasattr(comp, 'compacted_content'):
            compacted_content = comp.compacted_content

        if compacted_content:
            # Create proper adk_types.Content object from compacted_content dict
            # This allows normal LLM prompts to include the summary (via .content)
            # while LlmEventSummarizer can still detect it's a compaction (via .actions.compaction)
            if isinstance(compacted_content, dict):
                # Extract role and parts from dict
                role = compacted_content.get('role', 'model')
                parts_data = compacted_content.get('parts', [])

                # Convert parts dicts to adk_types.Part objects
                parts = []
                for part_dict in parts_data:
                    if isinstance(part_dict, dict) and part_dict.get('text'):
                        parts.append(adk_types.Part(text=part_dict['text']))

                # Create proper Content object
                latest_compaction.content = adk_types.Content(role=role, parts=parts)
                log.info(
                    "%s Set .content on compaction event (role=%s, parts=%d) for LLM prompts",
                    log_identifier,
                    role,
                    len(parts)
                )
            else:
                # Already an object, assign directly
                latest_compaction.content = compacted_content
                log.info(
                    "%s Set .content on compaction event (object form) for LLM prompts",
                    log_identifier
                )
        else:
            log.warning(
                "%s Compaction event has NO compacted_content - LLM will miss the summary!",
                log_identifier
            )

    # Update session.events in-memory with filtered results
    original_count = len(session.events)
    session.events = filtered_events

    log.info(
        "%s Proactive compaction filter: %d → %d events (removed %d ghost events before ts=%.6f)",
        log_identifier,
        original_count,
        len(filtered_events),
        original_count - len(filtered_events),
        compaction_time
    )

    return session


class FilteringSessionService(BaseSessionService):
    """
    Wrapper around ADK's session services that automatically filters
    ghost events from compacted sessions.

    This ensures ALL get_session() calls across the codebase automatically
    receive filtered sessions, eliminating the need for manual filtering
    at 13+ callsites throughout the codebase.

    Architecture:
    - Wraps any BaseSessionService implementation (memory, SQL, Vertex)
    - Intercepts get_session() to apply compaction filtering
    - Delegates all other methods transparently to wrapped service
    - Maintains ADK's append-only event store (DB unchanged)
    """

    def __init__(self, wrapped_service: BaseSessionService):
        """
        Initialize the filtering wrapper.

        Args:
            wrapped_service: The underlying session service to wrap
        """
        self._wrapped = wrapped_service

    async def get_session(
        self,
        *,
        app_name: str,
        user_id: str,
        session_id: str,
        config: Optional[Any] = None
    ) -> Optional[ADKSession]:
        """
        Get session and automatically filter ghost events from compactions.

        This is the key method that provides automatic filtering for ALL
        session retrievals across the codebase.
        """
        # Get session from underlying service
        session = await self._wrapped.get_session(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
            config=config
        )

        # Apply compaction filtering (in-memory only, DB unchanged)
        return _filter_session_by_latest_compaction(
            session,
            log_identifier=f"[SessionService:{app_name}]"
        )

    async def create_session(
        self,
        *,
        app_name: str,
        user_id: str,
        state: Optional[dict[str, Any]] = None,
        session_id: Optional[str] = None
    ) -> ADKSession:
        """Delegate to wrapped service."""
        return await self._wrapped.create_session(
            app_name=app_name,
            user_id=user_id,
            state=state,
            session_id=session_id
        )

    async def delete_session(
        self,
        *,
        app_name: str,
        user_id: str,
        session_id: str
    ) -> None:
        """Delegate to wrapped service."""
        return await self._wrapped.delete_session(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id
        )

    async def clone_session(
        self,
        *,
        app_name: str,
        source_user_id: str,
        source_session_id: str,
        target_user_id: str,
        target_session_id: str,
        log_identifier: str = ""
    ) -> Optional[ADKSession]:
        """
        Clone an ADK session by copying all events from source to target.
        Delegates to the standalone clone_adk_session function.
        """
        return await clone_adk_session(
            session_service=self,
            app_name=app_name,
            source_user_id=source_user_id,
            source_session_id=source_session_id,
            target_user_id=target_user_id,
            target_session_id=target_session_id,
            log_identifier=log_identifier,
        )

    async def list_sessions(
        self,
        *,
        app_name: str,
        user_id: Optional[str] = None
    ) -> Any:
        """Delegate to wrapped service."""
        return await self._wrapped.list_sessions(
            app_name=app_name,
            user_id=user_id
        )

    async def append_event(
        self,
        session: ADKSession,
        event: ADKEvent
    ) -> ADKEvent:
        """Delegate to wrapped service."""
        return await self._wrapped.append_event(session, event)

def initialize_session_service(component) -> BaseSessionService:
    """
    Initializes the ADK Session Service based on configuration.

    The returned service is automatically wrapped with FilteringSessionService
    to provide transparent ghost event filtering on all get_session() calls.
    """
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

    # Create the base service
    base_service: BaseSessionService

    if service_type == "memory":
        base_service = InMemorySessionService()
    elif service_type == "sql":
        if not db_url:
            raise ValueError(
                f"{component.log_identifier} 'database_url' is required for sql session service."
            )
        try:
            base_service = DatabaseSessionService(db_url=db_url)
            run_migrations(base_service, component)
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
        base_service = VertexAiSessionService(project=project, location=location)
    else:
        raise ValueError(
            f"{component.log_identifier} Unsupported session service type: {service_type}"
        )

    # Check if auto-summarization is enabled from component config
    auto_sum_config = component.auto_summarization_config
    if auto_sum_config.get("enabled", True):
        # Wrap with FilteringSessionService to automatically filter ghost events
        # This ensures ALL get_session() calls across the codebase get filtered sessions
        # There is a risk of spilling summary events in case if flag flips between True/False - and no filtering.
        log.info(
            "%s Wrapping session service with FilteringSessionService for automatic compaction filtering.",
            component.log_identifier,
        )
        return FilteringSessionService(base_service)

    return base_service


async def clone_adk_session(
    *,
    session_service,
    app_name: str,
    source_user_id: str,
    source_session_id: str,
    target_user_id: str,
    target_session_id: str,
    log_identifier: str = ""
) -> Optional[ADKSession]:
    """
    Clone an ADK session by copying all events from source to target.
    Creates a new independent session with the same conversation history.
    
    Works with any session service (FilteringSessionService, DatabaseSessionService, etc.)
    
    Used when forking a shared chat - the forked session gets its own
    copy of the conversation history for true isolation.
    
    Returns the new session, or None if the source session doesn't exist.
    """
    # Get the source session
    source_session = await session_service.get_session(
        app_name=app_name,
        user_id=source_user_id,
        session_id=source_session_id,
    )
    
    if source_session is None:
        log.warning(
            "%s Cannot clone session - source session '%s' (user '%s') not found in ADK. "
            "Forked session will start with empty history.",
            log_identifier, source_session_id, source_user_id
        )
        return None
    
    source_events = getattr(source_session, "events", None)
    if source_events is None:
        source_events = getattr(source_session, "history", None) or []
    if not source_events:
        log.info(
            "%s Source session '%s' has no events to clone.",
            log_identifier, source_session_id
        )
        return None
    
    log.info(
        "%s Cloning %d events from session '%s' (user '%s') to session '%s' (user '%s').",
        log_identifier, len(source_events),
        source_session_id, source_user_id,
        target_session_id, target_user_id
    )
    
    # Create the target session (strip compaction_time — it references source timestamps)
    clone_state = None
    if hasattr(source_session, "state") and source_session.state:
        clone_state = {k: v for k, v in source_session.state.items() if k != "compaction_time"}
    target_session = await session_service.create_session(
        app_name=app_name,
        user_id=target_user_id,
        session_id=target_session_id,
        state=clone_state,
    )
    
    # Copy events one by one (same pattern as RUN_BASED session copy)
    for event_to_copy in source_events:
        await append_event_with_retry(
            session_service=session_service,
            session=target_session,
            event=event_to_copy,
            app_name=app_name,
            user_id=target_user_id,
            session_id=target_session_id,
            log_identifier=f"{log_identifier}[ForkClone]",
        )

    # Fetch final session state once after all events are appended
    target_session = await session_service.get_session(
        app_name=app_name,
        user_id=target_user_id,
        session_id=target_session_id,
    )
    
    log.info(
        "%s Successfully cloned %d events to forked session '%s'.",
        log_identifier, len(source_events), target_session_id
    )
    
    return target_session


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
            valid_gcs_params = [
                "project",
                "credentials",
                "client_info",
                "client_options",
            ]

            gcs_args = {}
            for key in valid_gcs_params:
                val = config.get(key)
                if val is not None:
                    gcs_args[key] = val

            project = config.get("project") or os.environ.get("GCS_PROJECT")
            if project:
                gcs_args.setdefault("project", project)

            credentials_json = os.environ.get("GCS_CREDENTIALS_JSON")
            if credentials_json and "credentials" not in gcs_args:
                import json

                from google.oauth2 import service_account

                try:
                    info = json.loads(credentials_json)
                except json.JSONDecodeError as e:
                    raise ValueError(
                        f"GCS_CREDENTIALS_JSON contains invalid JSON: {e}. "
                        "Ensure the value is a valid JSON string, not base64-encoded."
                    ) from e
                gcs_args["credentials"] = (
                    service_account.Credentials.from_service_account_info(info)
                )

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
    elif service_type == "azure":
        container_name = config.get("container_name") or config.get("bucket_name")
        if not container_name or not container_name.strip():
            raise ValueError(
                f"{component.log_identifier} 'container_name' is required for Azure artifact service."
            )
        try:
            from .artifacts.azure_artifact_service import AzureArtifactService

            azure_config = {}
            for key, env_var in [
                ("connection_string", "AZURE_STORAGE_CONNECTION_STRING"),
                ("account_name", "AZURE_STORAGE_ACCOUNT_NAME"),
                ("account_key", "AZURE_STORAGE_ACCOUNT_KEY"),
            ]:
                azure_config[key] = config.get(key) or os.environ.get(env_var)

            azure_config_cleaned = {k: v for k, v in azure_config.items() if v is not None}
            concrete_service = AzureArtifactService(
                container_name=container_name, **azure_config_cleaned
            )
        except ImportError as e:
            log.error(
                "%s Azure dependencies not available: %s",
                component.log_identifier, e,
            )
            raise
        except Exception as e:
            log.error(
                "%s Failed to initialize AzureArtifactService: %s",
                component.log_identifier, e,
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


# Constants for stale session retry logic
STALE_SESSION_MAX_RETRIES = 3
STALE_SESSION_ERROR_SUBSTRING = "earlier than the update_time in the storage_session"


async def append_event_with_retry(
    session_service: BaseSessionService,
    session: ADKSession,
    event: ADKEvent,
    app_name: str,
    user_id: str,
    session_id: str,
    max_retries: int = STALE_SESSION_MAX_RETRIES,
    log_identifier: str = "",
) -> ADKEvent:
    """
    Appends an event to a session with automatic retry on stale session errors.

    The Google ADK's DatabaseSessionService validates that the session object's
    `last_update_time` is not older than the database's `update_timestamp_tz`.
    When another process updates the session between when we fetch it and when
    we call append_event, this validation fails with a "stale session" error.

    This helper function handles this race condition by:
    1. Attempting to append the event
    2. On stale session error, re-fetching the session from the database
    3. Retrying the append with the fresh session

    Args:
        session_service: The session service instance
        session: The ADK session object (may become stale)
        event: The event to append
        app_name: The application/agent name for session lookup
        user_id: The user ID for session lookup
        session_id: The session ID for session lookup
        max_retries: Maximum number of retry attempts (default: 3)
        log_identifier: Optional log identifier for debugging

    Returns:
        The appended event (from the session service)

    Raises:
        ValueError: If the stale session error persists after max_retries
        Exception: Any other exception from append_event
    """
    current_session = session
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            return await session_service.append_event(
                session=current_session, event=event
            )
        except ValueError as e:
            error_message = str(e)
            
            # Check if this is a stale session error
            if STALE_SESSION_ERROR_SUBSTRING not in error_message:
                # Not a stale session error, re-raise immediately
                raise
            
            last_error = e
            
            if attempt < max_retries:
                log.warning(
                    "%s Stale session detected on attempt %d/%d. Re-fetching session '%s' and retrying. Error: %s",
                    log_identifier,
                    attempt + 1,
                    max_retries + 1,
                    session_id,
                    error_message,
                )
                
                # Re-fetch the session from the database to get the latest timestamp
                current_session = await session_service.get_session(
                    app_name=app_name,
                    user_id=user_id,
                    session_id=session_id,
                )
                
                if current_session is None:
                    log.error(
                        "%s Failed to re-fetch session '%s' during stale session retry.",
                        log_identifier,
                        session_id,
                    )
                    raise ValueError(
                        f"Session '{session_id}' not found during stale session retry"
                    ) from e
            else:
                log.error(
                    "%s Stale session error persisted after %d attempts for session '%s'. Error: %s",
                    log_identifier,
                    max_retries + 1,
                    session_id,
                    error_message,
                )
    
    # This should not be reached, but just in case
    if last_error:
        raise last_error
    raise RuntimeError("Unexpected state in append_event_with_retry")


def _extract_compaction_summary(event: ADKEvent) -> str | None:
    """Extract the summary text from a compaction event, handling both dict and object forms."""
    compacted_content = event.actions.compaction
    if isinstance(compacted_content, dict):
        cc = compacted_content.get("compacted_content", {})
        parts = cc.get("parts", []) if isinstance(cc, dict) else []
        for part in parts:
            text = part.get("text", "") if isinstance(part, dict) else getattr(part, "text", "")
            if text:
                return text
    else:
        cc = getattr(compacted_content, "compacted_content", None)
        if cc and hasattr(cc, "parts") and cc.parts:
            for part in cc.parts:
                if hasattr(part, "text") and part.text:
                    return part.text
    return None


def extract_session_text_for_transfer(
    session: ADKSession,
    source_agent_display_name: str = "previous agent",
    log_identifier: str = "",
) -> str | None:
    """
    Extract a clean text transcript from an ADK session for cross-agent context transfer.

    Delegates event filtering to _filter_events_for_transfer, then builds a formatted
    text transcript from the filtered events. Handles compacted sessions by extracting
    the compaction summary and prepending it to the transcript.

    The session MUST be loaded through FilteringSessionService (which automatically
    filters ghost events from compacted sessions) before calling this function.

    Args:
        session: The ADK session loaded via FilteringSessionService.get_session()
        source_agent_display_name: Display name of the source agent for context marker
        log_identifier: Logging prefix

    Returns:
        A formatted text transcript suitable for injection into a new agent's session,
        or None if the session has no meaningful text content.
    """
    if not session or not session.events:
        log.info("%s No events in session to extract text from.", log_identifier)
        return None

    # Step 1: Use shared filtering logic
    filtered_events = _filter_events_for_transfer(
        events=session.events,
        log_identifier=log_identifier,
    )

    # Step 2: Separate compaction summaries from regular text events
    compaction_summary = None
    transcript_lines = []

    for event in filtered_events:
        if event.actions and event.actions.compaction:
            summary = _extract_compaction_summary(event)
            if summary:
                compaction_summary = summary
            continue

        if not event.content or not event.content.parts:
            continue

        role = event.content.role
        text_parts = []
        for part in event.content.parts:
            if hasattr(part, "text") and part.text:
                text_parts.append(part.text)

        combined_text = "\n".join(text_parts).strip()
        if not combined_text:
            continue

        role_label = "User" if role == "user" else "Assistant"
        transcript_lines.append(f"{role_label}: {combined_text}")

    # Step 3: Build the final transcript
    if not compaction_summary and not transcript_lines:
        log.info("%s No text content found in session events.", log_identifier)
        return None

    parts = []

    if compaction_summary:
        parts.append(f"[Summary of earlier conversation]\n{compaction_summary}")

    if transcript_lines:
        if compaction_summary:
            parts.append("\n[Recent conversation]")
        parts.append("\n".join(transcript_lines))

    transcript = "\n\n".join(parts)

    # Step 4: Wrap with context markers
    result = (
        f"[Context from previous conversation with {source_agent_display_name}]\n"
        f"{transcript}\n"
        f"[End of previous context]"
    )

    log.info(
        "%s Extracted %d chars of text for context transfer (%d filtered events, compaction=%s).",
        log_identifier,
        len(result),
        len(filtered_events),
        "yes" if compaction_summary else "no",
    )

    return result


def _filter_events_for_transfer(
    events: list[ADKEvent],
    log_identifier: str = "",
) -> list[ADKEvent]:
    """
    Filter ADK session events for cross-agent transfer by stripping tool-only events.

    Keeps:
    - User text events (user messages)
    - Model text events (assistant responses with text content)
    - Compaction events (contain conversation summaries)

    Strips from kept events:
    - function_call parts (tool invocations the new agent doesn't have)
    - function_response parts (tool results)

    Removes entirely:
    - Events with ONLY function_call/function_response parts (no text)
    - System/context-setting events (state_delta events)
    - Events with no content

    Args:
        events: List of ADK events from the source session
        log_identifier: Logging prefix

    Returns:
        List of filtered ADKEvent objects safe for the target agent
    """
    filtered = []
    skipped_count = 0

    for event in events:
        # Keep compaction events as-is (they contain conversation summaries)
        if event.actions and event.actions.compaction:
            filtered.append(event)
            continue

        # Skip events with no content
        if not event.content or not event.content.parts:
            skipped_count += 1
            continue

        # Skip system/context-setting events (state_delta only, no text)
        if event.actions and event.actions.state_delta:
            has_text = any(
                hasattr(p, "text") and p.text for p in event.content.parts
            )
            if not has_text:
                skipped_count += 1
                continue

        role = event.content.role
        # Only keep user and model events
        if role not in ("user", "model"):
            skipped_count += 1
            continue

        # Filter parts: keep only text parts, strip function_call/function_response
        # Deep copy text parts to avoid shared references with source events
        text_parts = []
        for part in event.content.parts:
            if hasattr(part, "text") and part.text:
                text_parts.append(adk_types.Part(text=part.text))
            # Explicitly skip function_call and function_response parts

        # If no text parts remain after filtering, skip the entire event
        if not text_parts:
            skipped_count += 1
            continue

        # Create a new event with fresh invocation ID to avoid correlation confusion
        import uuid as _uuid
        filtered_event = ADKEvent(
            invocation_id=f"ctx-transfer-{_uuid.uuid4().hex[:12]}",
            author=event.author,
            content=adk_types.Content(
                role=role,
                parts=text_parts,
            ),
            timestamp=event.timestamp,
        )
        filtered.append(filtered_event)

    log.info(
        "%s Filtered events for transfer: %d kept, %d skipped (tool-only/system).",
        log_identifier,
        len(filtered),
        skipped_count,
    )
    return filtered


# Maximum number of events to transfer to prevent unbounded clone loops
MAX_TRANSFER_EVENTS = 200

# Allowlist of session state keys safe to copy across agents
_SAFE_STATE_KEYS = frozenset({
    # Add known-safe keys here as needed; empty set means no state is copied
})


class TransferResult:
    """Result of a context transfer operation with detailed counts."""

    __slots__ = ("success", "transferred_count", "total_count", "message")

    def __init__(self, success: bool, transferred_count: int = 0, total_count: int = 0, message: str = ""):
        self.success = success
        self.transferred_count = transferred_count
        self.total_count = total_count
        self.message = message

    def __bool__(self) -> bool:
        return self.success


async def transfer_session_context(
    session_service: BaseSessionService,
    source_agent_name: str,
    target_agent_name: str,
    user_id: str,
    session_id: str,
    source_agent_display_name: str = "previous agent",
    log_identifier: str = "",
    max_events: int = MAX_TRANSFER_EVENTS,
) -> TransferResult:
    """
    Transfer conversation context from one agent's ADK session to another.

    Uses a filtered clone approach: copies user/model text events from the source
    session to the target session, stripping tool call/response parts that would
    confuse the new agent. Compaction events (conversation summaries) are preserved.

    Args:
        session_service: The ADK session service (should be FilteringSessionService)
        source_agent_name: The source agent's name (used as app_name)
        target_agent_name: The target agent's name (used as app_name)
        user_id: The user ID
        session_id: The session ID (same for both agents)
        source_agent_display_name: Human-readable name for context marker
        log_identifier: Logging prefix
        max_events: Maximum number of events to transfer (oldest truncated first)

    Returns:
        TransferResult with success flag, transferred/total counts, and message.
    """
    # 1. Load source session (FilteringSessionService handles compaction filtering)
    source_session = await session_service.get_session(
        app_name=source_agent_name,
        user_id=user_id,
        session_id=session_id,
    )

    if not source_session or not source_session.events:
        log.info(
            "%s No source session found for agent '%s', session '%s'. Nothing to transfer.",
            log_identifier,
            source_agent_name,
            session_id,
        )
        return TransferResult(False, message="No source session found.")

    # 2. Filter events: strip tool calls, keep text + compaction events
    filtered_events = _filter_events_for_transfer(
        events=source_session.events,
        log_identifier=log_identifier,
    )

    if not filtered_events:
        log.info(
            "%s No transferable events from agent '%s' session '%s'.",
            log_identifier,
            source_agent_name,
            session_id,
        )
        return TransferResult(False, message="No text content to transfer.")

    # 2b. Truncate from oldest if exceeding max_events limit
    total_before_truncation = len(filtered_events)
    if len(filtered_events) > max_events:
        log.warning(
            "%s Truncating %d filtered events to max_events=%d (dropping oldest).",
            log_identifier,
            len(filtered_events),
            max_events,
        )
        filtered_events = filtered_events[-max_events:]

    # 3. Get or create target session
    target_session = await session_service.get_session(
        app_name=target_agent_name,
        user_id=user_id,
        session_id=session_id,
    )

    if target_session is None:
        # Use allowlist for state cloning — only copy known-safe keys
        clone_state = None
        if _SAFE_STATE_KEYS and hasattr(source_session, "state") and source_session.state:
            clone_state = {
                k: v for k, v in source_session.state.items()
                if k in _SAFE_STATE_KEYS
            }
            if not clone_state:
                clone_state = None
        try:
            target_session = await session_service.create_session(
                app_name=target_agent_name,
                user_id=user_id,
                session_id=session_id,
                state=clone_state,
            )
        except Exception as exc:
            # Race condition: another request may have created it
            log.warning(
                "%s create_session failed, retrying with get_session: %s",
                log_identifier, exc,
            )
            target_session = await session_service.get_session(
                app_name=target_agent_name,
                user_id=user_id,
                session_id=session_id,
            )

    if target_session is None:
        log.error(
            "%s Failed to create/get target session for agent '%s', session '%s'.",
            log_identifier,
            target_agent_name,
            session_id,
        )
        return TransferResult(False, message="Failed to create target session.")

    # 4. Append a context marker event first
    marker_text = (
        f"[The user has switched from {source_agent_display_name}. "
        f"The following is the conversation history from that agent.]"
    )
    marker_event = ADKEvent(
        invocation_id=f"context-transfer-marker-{session_id}",
        author="model",
        content=adk_types.Content(
            role="model",
            parts=[adk_types.Part(text=marker_text)],
        ),
    )

    try:
        await append_event_with_retry(
            session_service=session_service,
            session=target_session,
            event=marker_event,
            app_name=target_agent_name,
            user_id=user_id,
            session_id=session_id,
            log_identifier=f"{log_identifier}[ContextTransfer:Marker]",
        )
    except Exception as e:
        log.error(
            "%s Failed to append context marker event: %s",
            log_identifier, e, exc_info=True,
        )
        return TransferResult(False, message="Failed to append context marker.")

    # 5. Clone filtered events into target session
    # Refresh target_session before the loop to avoid stale-session retries
    # on every append (append_event_with_retry doesn't return the refreshed session)
    target_session = await session_service.get_session(
        app_name=target_agent_name,
        user_id=user_id,
        session_id=session_id,
    ) or target_session

    cloned_count = 0
    failed_count = 0
    for event_to_copy in filtered_events:
        try:
            await append_event_with_retry(
                session_service=session_service,
                session=target_session,
                event=event_to_copy,
                app_name=target_agent_name,
                user_id=user_id,
                session_id=session_id,
                log_identifier=f"{log_identifier}[ContextTransfer:Clone]",
            )
            cloned_count += 1

            # Periodically refresh session to reduce stale-session retries
            if cloned_count % 20 == 0:
                refreshed = await session_service.get_session(
                    app_name=target_agent_name,
                    user_id=user_id,
                    session_id=session_id,
                )
                if refreshed:
                    target_session = refreshed
        except Exception as e:
            failed_count += 1
            log.warning(
                "%s Failed to clone event %d to target session: %s",
                log_identifier, cloned_count + failed_count, e,
            )
            # Continue cloning remaining events

    total_events = len(filtered_events)
    log.info(
        "%s Context transfer complete: %d/%d events cloned (%d failed, %d truncated) "
        "from '%s' to '%s' for session '%s'.",
        log_identifier,
        cloned_count,
        total_events,
        failed_count,
        max(0, total_before_truncation - max_events),
        source_agent_name,
        target_agent_name,
        session_id,
    )

    if cloned_count == 0:
        return TransferResult(False, 0, total_events, "All event clones failed.")

    if failed_count > 0:
        return TransferResult(
            True, cloned_count, total_events,
            f"Partial transfer: {cloned_count}/{total_events} events.",
        )

    return TransferResult(True, cloned_count, total_events, "Transfer complete.")
