"""
Defines the Pydantic models for the Generic Gateway Adapter framework.

These types create a stable abstraction layer, decoupling gateway adapters from the
underlying A2A protocol specifics.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, model_validator

if TYPE_CHECKING:
    from google.adk.artifacts import BaseArtifactService
    from ...common.a2a.types import ArtifactInfo


# --- Content Part Models ---


class SamTextPart(BaseModel):
    """Text content in a SAM task."""

    type: Literal["text"] = "text"
    text: str


class SamFilePart(BaseModel):
    """File content in a SAM task, with either inline bytes or a URI."""

    type: Literal["file"] = "file"
    name: str
    content_bytes: Optional[bytes] = None
    uri: Optional[str] = None
    mime_type: Optional[str] = None

    @model_validator(mode="after")
    def validate_content_or_uri(self) -> "SamFilePart":
        """Ensures that either content_bytes or uri is set, but not both."""
        if not self.content_bytes and not self.uri:
            raise ValueError("SamFilePart must have either 'content_bytes' or 'uri'.")
        if self.content_bytes and self.uri:
            raise ValueError("SamFilePart cannot have both 'content_bytes' and 'uri'.")
        return self


class SamDataPart(BaseModel):
    """Structured data in a SAM task."""

    type: Literal["data"] = "data"
    data: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = None


SamContentPart = Union[SamTextPart, SamFilePart, SamDataPart]


# --- Task and Update Models ---


class SamTask(BaseModel):
    """A task prepared for submission to the SAM agent mesh."""

    parts: List[SamContentPart]
    session_id: Optional[str] = None
    target_agent: str = Field(..., description="Target agent name (required).")
    is_streaming: bool = Field(default=True, description="Enable streaming responses.")
    platform_context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Platform-specific data for response routing.",
    )


class SamUpdate(BaseModel):
    """An update event from the agent containing one or more parts."""

    parts: List[SamContentPart] = Field(default_factory=list)
    is_final: bool = Field(
        default=False,
        description="True if this is the final update before task completion.",
    )


# --- Auth and Error Models ---


class AuthClaims(BaseModel):
    """Authentication claims extracted from a platform event."""

    id: Optional[str] = Field(
        default=None,
        description="Primary user identifier. If None, generic gateway uses auth_config default.",
    )
    email: Optional[str] = None
    token: Optional[str] = Field(
        default=None, description="Bearer token or API key for token-based auth flows."
    )
    token_type: Optional[Literal["bearer", "api_key"]] = None
    source: str = Field(default="platform", description="Authentication source.")
    raw_context: Dict[str, Any] = Field(
        default_factory=dict, description="Platform-specific auth context."
    )


class SamError(BaseModel):
    """A structured error object for outbound error handling."""

    message: str
    code: int
    category: Literal[
        "FAILED", "CANCELED", "TIMED_OUT", "PROTOCOL_ERROR", "GATEWAY_ERROR"
    ]


class SamFeedback(BaseModel):
    """A structured model for submitting user feedback."""

    task_id: str
    session_id: str
    rating: Literal["up", "down"]
    comment: Optional[str] = None
    user_id: str


# --- Context Models ---


class ResponseContext(BaseModel):
    """Context provided with each outbound response callback."""

    task_id: str
    session_id: Optional[str]
    user_id: str
    platform_context: Dict[str, Any]


class GatewayContext:
    """
    Context provided to gateway adapter during initialization.

    Provides access to gateway services and helper methods.
    This is an abstract class definition; the concrete implementation is the
    GenericGatewayComponent.
    """

    gateway_id: str
    namespace: str
    config: Dict[str, Any]
    adapter_config: Any  # Can be a Pydantic model or a dict
    artifact_service: "BaseArtifactService"

    async def handle_external_input(
        self, external_input: Any, endpoint_context: Optional[Dict[str, Any]] = None
    ) -> str:
        raise NotImplementedError

    async def cancel_task(self, task_id: str) -> None:
        raise NotImplementedError

    async def submit_feedback(self, feedback: "SamFeedback") -> None:
        """Submits user feedback related to a task."""
        raise NotImplementedError

    async def load_artifact_content(
        self, context: "ResponseContext", filename: str, version: Union[int, str] = "latest"
    ) -> Optional[bytes]:
        """Loads the raw byte content of an artifact."""
        raise NotImplementedError

    async def list_artifacts(
        self, context: "ResponseContext"
    ) -> List["ArtifactInfo"]:
        """Lists all artifacts available in the user's context."""
        raise NotImplementedError

    def add_timer(
        self, delay_ms: int, callback: "Callable", interval_ms: Optional[int] = None
    ) -> str:
        raise NotImplementedError

    def cancel_timer(self, timer_id: str) -> None:
        raise NotImplementedError

    def get_task_state(self, task_id: str, key: str, default: Any = None) -> Any:
        raise NotImplementedError

    def set_task_state(self, task_id: str, key: str, value: Any) -> None:
        raise NotImplementedError

    def get_session_state(self, session_id: str, key: str, default: Any = None) -> Any:
        raise NotImplementedError

    def set_session_state(self, session_id: str, key: str, value: Any) -> None:
        raise NotImplementedError

    def create_text_part(self, text: str) -> SamTextPart:
        return SamTextPart(text=text)

    def create_file_part_from_bytes(
        self, name: str, content_bytes: bytes, mime_type: str
    ) -> SamFilePart:
        return SamFilePart(name=name, content_bytes=content_bytes, mime_type=mime_type)

    def create_file_part_from_uri(
        self, uri: str, name: str, mime_type: Optional[str] = None
    ) -> SamFilePart:
        return SamFilePart(name=name, uri=uri, mime_type=mime_type)

    def create_data_part(self, data: Dict[str, Any]) -> SamDataPart:
        return SamDataPart(data=data)

    def process_sac_template(
        self,
        template: str,
        payload: Any = None,
        headers: Optional[Dict[str, str]] = None,
        query_params: Optional[Dict[str, str]] = None,
        user_data: Optional[Dict[str, Any]] = None,
    ) -> str:
        raise NotImplementedError
