"""
Conditional expression evaluation for workflow flow control.
"""

import logging
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
        # Pre-process the expression to handle {{...}} syntax if present
        # (Though simpleeval works on variable names directly)
        # If the user writes "{{node.output.val}} == 1", we need to strip {{}}
        # But our design says: "{{validate.output.is_valid}} == true"
        # simpleeval expects: "validate.output.is_valid == true"
        # So we should strip {{ and }}
        clean_expr = condition_expr.replace("{{", "").replace("}}", "")

        result = simple_eval(clean_expr, names=context, functions=functions)
        return bool(result)
    except Exception as e:
        raise ConditionalEvaluationError(
            f"Failed to evaluate condition '{condition_expr}': {e}"
        ) from e
