"""
Sandbox Protocol Package.

Protocol types for the Secure Tool Runtime (STR).
The STR worker is implemented in Go (solace-agent-mesh-go/internal/str/).
This package provides the Python-side protocol types used by agents to invoke
remote tools hosted by the Go STR.
"""

from .protocol import (
    ArtifactReference,
    CreatedArtifact,
    PreloadedArtifact,
    SandboxError,
    SandboxErrorCodes,
    SandboxInvokeParams,
    SandboxInvokeResult,
    SandboxStatusUpdate,
    SandboxStatusUpdateParams,
    SandboxToolInvocationRequest,
    SandboxToolInvocationResponse,
)

__all__ = [
    "ArtifactReference",
    "CreatedArtifact",
    "PreloadedArtifact",
    "SandboxError",
    "SandboxErrorCodes",
    "SandboxInvokeParams",
    "SandboxInvokeResult",
    "SandboxStatusUpdate",
    "SandboxStatusUpdateParams",
    "SandboxToolInvocationRequest",
    "SandboxToolInvocationResponse",
]
