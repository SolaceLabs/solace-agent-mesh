"""
Conditional expression evaluation for workflow flow control.

Supports Argo Workflows-compatible template syntax with aliases:
- {{item}} -> {{_map_item}} (Argo loop variable)
- {{workflow.parameters.x}} -> {{workflow.input.x}} (Argo input syntax)
"""

import ast
import logging
import operator
import re
from typing import Any

from ..workflow_execution_context import WorkflowExecutionState

log = logging.getLogger(__name__)


# Comparison operators supported in conditions
_COMPARE_OPS = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.In: lambda a, b: a in b,
    ast.NotIn: lambda a, b: a not in b,
}


def _safe_eval_expression(expr: str) -> Any:
    """
    Safely evaluate a simple expression using Python's AST.

    Supports:
    - Comparisons: ==, !=, <, <=, >, >=, in, not in
    - Boolean operators: and, or, not
    - Literals: strings, numbers, booleans (true/false), null
    - Parentheses for grouping

    Args:
        expr: The expression string to evaluate

    Returns:
        The result of evaluating the expression

    Raises:
        ValueError: If the expression contains unsupported syntax
    """
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        raise ValueError(f"Invalid expression syntax: {e}") from e

    return _eval_node(tree.body)


def _eval_node(node: ast.AST) -> Any:
    """
    Recursively evaluate an AST node.

    Args:
        node: The AST node to evaluate

    Returns:
        The result of evaluating the node
    """
    if isinstance(node, ast.Compare):
        # Handle comparisons: x == y, x > y, x in y, etc.
        left = _eval_node(node.left)
        for op, comparator in zip(node.ops, node.comparators):
            right = _eval_node(comparator)
            op_func = _COMPARE_OPS.get(type(op))
            if op_func is None:
                raise ValueError(f"Unsupported comparison operator: {type(op).__name__}")
            if not op_func(left, right):
                return False
            left = right
        return True

    elif isinstance(node, ast.BoolOp):
        # Handle boolean operations: x and y, x or y
        if isinstance(node.op, ast.And):
            return all(_eval_node(v) for v in node.values)
        elif isinstance(node.op, ast.Or):
            return any(_eval_node(v) for v in node.values)
        else:
            raise ValueError(f"Unsupported boolean operator: {type(node.op).__name__}")

    elif isinstance(node, ast.UnaryOp):
        # Handle unary operations: not x, -x
        operand = _eval_node(node.operand)
        if isinstance(node.op, ast.Not):
            return not operand
        elif isinstance(node.op, ast.USub):
            return -operand
        elif isinstance(node.op, ast.UAdd):
            return +operand
        else:
            raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")

    elif isinstance(node, ast.Constant):
        # Handle literals: strings, numbers, booleans, None
        return node.value

    elif isinstance(node, ast.Name):
        # Handle identifiers: true, false, null (and Python's True, False, None)
        name = node.id.lower()
        if name == "true":
            return True
        elif name == "false":
            return False
        elif name == "null" or name == "none":
            return None
        else:
            raise ValueError(f"Unknown identifier: {node.id}")

    elif isinstance(node, ast.Expr):
        # Handle expression wrapper
        return _eval_node(node.value)

    else:
        raise ValueError(f"Unsupported expression type: {type(node).__name__}")


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

        result = _safe_eval_expression(clean_expr)
        return bool(result)
    except Exception as e:
        raise ConditionalEvaluationError(
            f"Failed to evaluate condition '{condition_expr}': {e}"
        ) from e
