"""
DEPRECATED: This module has been removed.

All utilities have been moved to solace_agent_mesh.shared/

Migration guide:
  from solace_agent_mesh.gateway.http_sse.shared.pagination import PaginationParams
  → from solace_agent_mesh.shared.api.pagination import PaginationParams

  from solace_agent_mesh.gateway.http_sse.shared.exceptions import ValidationError
  → from solace_agent_mesh.shared.exceptions.exceptions import ValidationError

  from solace_agent_mesh.gateway.http_sse.shared.auth_utils import get_current_user
  → from solace_agent_mesh.shared.auth.dependencies import get_current_user

  from solace_agent_mesh.gateway.http_sse.dependencies import ValidatedUserConfig
  → from solace_agent_mesh.shared.auth.dependencies import ValidatedUserConfig

Architecture:
  - GATEWAYS (http_sse, slack, webhook) → import from shared/
  - SERVICES (platform) → import from shared/
  - No cross-dependencies between gateways and services

This file will be removed in v2.0.0.
"""

raise ImportError(
    "solace_agent_mesh.gateway.http_sse.shared has been removed. "
    "Import from solace_agent_mesh.shared instead. "
    "See module docstring for migration guide."
)
