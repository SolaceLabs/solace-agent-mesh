"""
RBAC utility functions for agent access control.

Provides common validation logic for enforcing agent access permissions
across gateways and agent components.
"""

import logging
from typing import Dict, Any

from ..middleware.registry import MiddlewareRegistry

log = logging.getLogger(__name__)


def validate_agent_access(
    user_config: Dict[str, Any],
    target_agent_name: str,
    validation_context: Dict[str, Any],
    log_identifier: str = "[RBAC]",
) -> None:
    """
    Validates that a user has permission to access a target agent.

    Uses the middleware ConfigResolver to check if the user has the required
    agent:{target_agent}:delegate scope. Raises PermissionError if access is denied.

    Args:
        user_config: User configuration dict containing scopes (from ConfigResolver.resolve_user_config)
        target_agent_name: Name of the agent being accessed
        validation_context: Additional context for validation (e.g., gateway_id, delegating_agent)
        log_identifier: Logging prefix for error messages

    Raises:
        PermissionError: If the user does not have the required agent:*:delegate scope
    """
    config_resolver = MiddlewareRegistry.get_config_resolver()
    operation_spec = {
        "operation_type": "agent_access",
        "target_agent": target_agent_name,
    }

    validation_result = config_resolver.validate_operation_config(
        user_config, operation_spec, validation_context
    )

    if not validation_result.get("valid", False):
        reason = validation_result.get(
            "reason", f"Access denied to agent '{target_agent_name}'"
        )
        required_scopes = validation_result.get("required_scopes", [])

        log.warning(
            "%s Access to agent '%s' denied. Required scopes: %s. Reason: %s",
            log_identifier,
            target_agent_name,
            required_scopes,
            reason,
        )

        raise PermissionError(
            f"Access denied to agent '{target_agent_name}'. Required scopes: {required_scopes}"
        )

    log.debug(
        "%s Access to agent '%s' granted.",
        log_identifier,
        target_agent_name,
    )
