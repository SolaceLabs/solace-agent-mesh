"""
Sandbox Worker Package.

This package provides sandboxed execution of Python tools using bubblewrap (bwrap)
within a container environment. It enables secure execution of user-generated
code with process isolation, filesystem sandboxing, and resource limits.

Components:
- SandboxWorkerApp: App class for broker configuration and subscriptions
- SandboxWorkerComponent: Main component handling tool invocations
- SandboxRunner: Subprocess management for bubblewrap sandbox execution
- SandboxToolContextFacade: Tool interface within the sandbox (Phase 3)

Usage:
    The sandbox worker runs as a separate process (typically in a container)
    and communicates with SAM agents via Solace broker.

Example:
    # In a container entry point:
    from solace_agent_mesh.sandbox import SandboxWorkerApp

    app_info = {
        "name": "sandbox-worker",
        "app_config": {
            "namespace": "myorg/dev",
            "worker_id": "sandbox-worker-001",
            "artifact_service": {"type": "filesystem", "base_path": "/artifacts"},
        },
        "broker": {
            "host": "localhost",
            "vpn": "default",
            "username": "sandbox",
            "password": "password",
        },
    }
    app = SandboxWorkerApp(app_info)
    app.run()
"""

# Lazy imports: heavy modules (app, component, sandbox_runner) pull in the full
# SAM + Google ADK dependency chain.  When tool_runner.py runs inside bwrap
# via `python -m solace_agent_mesh.sandbox.tool_runner`, this __init__.py is
# executed first.  Eagerly importing app/component would add ~5 seconds of
# import time.  Instead we use lazy imports so the cost is only paid when those
# symbols are actually accessed.

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
    "SandboxWorkerApp",
    "SandboxWorkerComponent",
    "SandboxRunner",
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
    "SandboxWorkerApp": (".app", "SandboxWorkerApp"),
    "SandboxWorkerComponent": (".component", "SandboxWorkerComponent"),
    "SandboxRunner": (".sandbox_runner", "SandboxRunner"),
    "SandboxToolContextFacade": (".context_facade", "SandboxToolContextFacade"),
}


def __getattr__(name: str):
    if name in _LAZY_IMPORTS:
        module_path, attr = _LAZY_IMPORTS[name]
        module = _importlib.import_module(module_path, __name__)
        return getattr(module, attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
