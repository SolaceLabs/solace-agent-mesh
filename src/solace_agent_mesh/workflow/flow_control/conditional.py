"""
Conditional expression evaluation for workflow flow control.
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


def evaluate_condition(
    condition_expr: str, workflow_state: WorkflowExecutionState
) -> bool:
    """
    Safely evaluate conditional expression.
    Returns boolean result.
    """
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
