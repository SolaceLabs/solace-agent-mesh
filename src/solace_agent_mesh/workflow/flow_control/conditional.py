"""
Conditional expression evaluation for workflow flow control.

Supports Argo Workflows-compatible template syntax with aliases:
- {{item}} -> {{_map_item}} (Argo loop variable)
- {{workflow.parameters.x}} -> {{workflow.input.x}} (Argo input syntax)
"""

import logging
import re
from typing import Any, Dict
from simpleeval import simple_eval

from ..workflow_execution_context import WorkflowExecutionState

log = logging.getLogger(__name__)


class ConditionalEvaluationError(Exception):
    """Raised when conditional expression evaluation fails."""

    pass


# Argo-compatible template aliases
TEMPLATE_ALIASES = {
    # Argo uses 'item' for loop variable, SAM uses '_map_item'
    "{{item}}": "{{_map_item}}",
    "{{item.": "{{_map_item.",
    # Argo uses 'workflow.parameters', SAM uses 'workflow.input'
    "workflow.parameters.": "workflow.input.",
}


def _apply_template_aliases(expression: str) -> str:
    """
    Apply Argo-compatible aliases to template expression.

    Transforms:
    - {{item}} -> {{_map_item}}
    - {{item.field}} -> {{_map_item.field}}
    - {{workflow.parameters.x}} -> {{workflow.input.x}}
    """
    result = expression
    for alias, target in TEMPLATE_ALIASES.items():
        result = result.replace(alias, target)
    return result


def evaluate_condition(
    condition_expr: str, workflow_state: WorkflowExecutionState
) -> bool:
    """
    Safely evaluate conditional expression.
    Returns boolean result.

    Supports Argo-style aliases:
    - {{item}} for map loop variable
    - {{workflow.parameters.x}} for workflow input
    """
    # Apply template aliases for Argo compatibility
    condition_expr = _apply_template_aliases(condition_expr)

    # Build context from completed nodes
    context = {}
    for node_id, output_data in workflow_state.node_outputs.items():
        context[node_id] = {"output": output_data.get("output")}

    # Add safe functions
    functions = {"true": True, "false": False, "null": None}

    try:
        # Helper to resolve a single match
        def replace_match(match):
            path = match.group(1).strip()
            parts = path.split(".")

            # Navigate path in workflow state (similar to DAGExecutor._resolve_template)
            if parts[0] == "workflow" and parts[1] == "input":
                if "workflow_input" not in workflow_state.node_outputs:
                    raise ValueError("Workflow input has not been initialized")
                data = workflow_state.node_outputs["workflow_input"]["output"]
                parts = parts[2:]
            # Handle workflow.status and workflow.error for exit handlers
            elif parts[0] == "workflow" and len(parts) >= 2:
                if "workflow" not in workflow_state.node_outputs:
                    raise ValueError("Workflow status has not been initialized")
                data = workflow_state.node_outputs["workflow"]
                parts = parts[1:]
            else:
                node_id = parts[0]
                if node_id not in workflow_state.node_outputs:
                    raise ValueError(f"Referenced node '{node_id}' has not completed")
                data = workflow_state.node_outputs[node_id]
                parts = parts[1:]

            # Traverse remaining parts
            for part in parts:
                if isinstance(data, dict) and part in data:
                    data = data[part]
                elif data is None:
                    # Allow graceful handling of None values in path
                    return "None"
                else:
                    raise ValueError(f"Field '{part}' not found in path: {path}")

            return str(data)

        # Replace all {{...}} patterns with their resolved string values
        clean_expr = re.sub(r"\{\{(.+?)\}\}", replace_match, condition_expr)

        log.debug(f"Evaluated condition: '{condition_expr}' -> '{clean_expr}'")

        result = simple_eval(clean_expr, names=context, functions=functions)
        return bool(result)
    except Exception as e:
        raise ConditionalEvaluationError(
            f"Failed to evaluate condition '{condition_expr}': {e}"
        ) from e
