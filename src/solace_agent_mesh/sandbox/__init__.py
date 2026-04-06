"""
Sandbox Protocol Package.

Protocol types and context facade for the Secure Tool Runtime (STR).
The STR worker itself is implemented in Go (solace-agent-mesh-go/internal/str/).
This package provides the Python-side protocol types used by agents to invoke
remote tools, and the context facade used by Python tools running inside the
Go STR sandbox.
"""

import importlib as _importlib

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
    "SandboxToolContextFacade",
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

_LAZY_IMPORTS = {
    "SandboxToolContextFacade": (".context_facade", "SandboxToolContextFacade"),
}


def __getattr__(name: str):
    if name in _LAZY_IMPORTS:
        module_path, attr = _LAZY_IMPORTS[name]
        module = _importlib.import_module(module_path, __name__)
        return getattr(module, attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
