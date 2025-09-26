"""
Parses and validates configuration for the SamAgentComponent and its App.
"""

import logging
from typing import Any, Union, Callable
from google.adk.agents.readonly_context import ReadonlyContext

log = logging.getLogger(__name__)

InstructionProvider = Callable[[ReadonlyContext], str]


def resolve_instruction_provider(
    component, config_value: Any
) -> Union[str, InstructionProvider]:
    """
    Resolves instruction config which can be a string or an invoke block
    handled by SAC's get_config.
    Args:
        component: The component instance (for context in get_config).
        config_value: The configuration value for the instruction (e.g., the value
                      retrieved using component.get_config("instruction")).
    Returns:
        The resolved instruction string or provider function.
    Raises:
        ValueError: If the configuration is invalid or resolution fails.
    """
    if isinstance(config_value, str):
        return config_value
    elif isinstance(config_value, dict) and "invoke" in config_value:
        if callable(config_value):
            log.info(
                "%s Resolved instruction to a callable provider.",
                component.log_identifier,
            )
            return config_value
        elif isinstance(config_value, str):
            return config_value
        else:
            raise ValueError(
                f"Invoke block for instruction resolved to unexpected type: {type(config_value)}"
            )
    elif not config_value:
        return ""
    else:
        raise ValueError(
            f"Invalid instruction configuration type: {type(config_value)}"
        )
