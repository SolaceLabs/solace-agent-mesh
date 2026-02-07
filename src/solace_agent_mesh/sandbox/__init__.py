"""
Sandbox Worker Package.

This package provides sandboxed execution of Python tools using nsjail
within a container environment. It enables secure execution of user-generated
code with process isolation, filesystem sandboxing, and resource limits.

Components:
- SandboxWorkerApp: App class for broker configuration and subscriptions
- SandboxWorkerComponent: Main component handling tool invocations
- NsjailRunner: Subprocess management for nsjail execution (Phase 2)
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

from .protocol import (
    ArtifactReference,
    CreatedArtifact,
    PreloadedArtifact,
    SandboxError,
    SandboxErrorCodes,
    SandboxInvokeParams,
    SandboxInvokeResult,
    SandboxStatusUpdate,
    SandboxToolInvocationRequest,
    SandboxToolInvocationResponse,
)

# Import app and component - these may fail if SAM dependencies aren't available
# (e.g., when just importing protocol types)
try:
    from .app import SandboxWorkerApp
    from .component import SandboxWorkerComponent
    from .nsjail_runner import NsjailRunner
    from .context_facade import SandboxToolContextFacade

    __all__ = [
        # App and Component
        "SandboxWorkerApp",
        "SandboxWorkerComponent",
        # nsjail execution
        "NsjailRunner",
        "SandboxToolContextFacade",
        # Protocol types
        "ArtifactReference",
        "CreatedArtifact",
        "PreloadedArtifact",
        "SandboxError",
        "SandboxErrorCodes",
        "SandboxInvokeParams",
        "SandboxInvokeResult",
        "SandboxStatusUpdate",
        "SandboxToolInvocationRequest",
        "SandboxToolInvocationResponse",
    ]
except ImportError:
    # Allow importing protocol types even without full SAM installation
    __all__ = [
        "ArtifactReference",
        "CreatedArtifact",
        "PreloadedArtifact",
        "SandboxError",
        "SandboxErrorCodes",
        "SandboxInvokeParams",
        "SandboxInvokeResult",
        "SandboxStatusUpdate",
        "SandboxToolInvocationRequest",
        "SandboxToolInvocationResponse",
    ]
