"""SAM common observability package.

Re-exports the type-safe monitor classes (preserves existing imports such
as `from solace_agent_mesh.common.observability import AgentMonitor`) and
adds the request-correlation primitives.
"""

from .monitors import (
    AgentMonitor,
    ArtifactMonitor,
    RemoteAgentProxyMonitor,
    ToolMonitor,
)
from .request_context import (
    HEADER_NAME,
    LOG_FIELD,
    MISSING_VALUE,
    RequestContext,
    WIRE_KEY,
    append_x_request_id,
)
from .request_context_logging import install_log_record_factory

__all__ = [
    # monitors
    "AgentMonitor",
    "ArtifactMonitor",
    "RemoteAgentProxyMonitor",
    "ToolMonitor",
    # request context
    "RequestContext",
    "HEADER_NAME",
    "WIRE_KEY",
    "LOG_FIELD",
    "MISSING_VALUE",
    "append_x_request_id",
    "install_log_record_factory",
]