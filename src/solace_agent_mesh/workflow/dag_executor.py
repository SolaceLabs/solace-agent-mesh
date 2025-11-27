"""
DAG Executor for Prescriptive Workflows.
Manages the execution order of workflow nodes based on their dependencies.
"""

import logging
import re
import asyncio
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, TYPE_CHECKING

from google.genai import types as adk_types

from .app import (
    WorkflowDefinition,
    WorkflowNode,
    AgentNode,
    ConditionalNode,
    ForkNode,
    MapNode,
)
from .workflow_execution_context import WorkflowExecutionContext, WorkflowExecutionState
from ..common.data_parts import WorkflowNodeResultData

if TYPE_CHECKING:
    from .component import WorkflowExecutorComponent

log = logging.getLogger(__name__)


class WorkflowExecutionError(Exception):
    """Raised when workflow execution fails."""

    pass


class WorkflowNodeFailureError(Exception):
    """Raised when a workflow node fails."""

    def __init__(self, node_id: str, error_message: str):
        self.node_id = node_id
        self.error_message = error_message
        super().__init__(f"Node '{node_id}' failed: {error_message}")


class DAGExecutor:
    """Executes workflow DAG by coordinating node execution."""

    def __init__(
        self,
        workflow_definition: WorkflowDefinition,
        host_component: "WorkflowExecutorComponent",
    ):
        self.workflow_def = workflow_definition
        self.host = host_component

        # Build dependency graph
        self.nodes: Dict[str, WorkflowNode] = {
            node.id: node for node in workflow_definition.nodes
        }
        self.dependencies = self._build_dependency_graph()
        self.reverse_dependencies = self._build_reverse_dependencies()

    def _build_dependency_graph(self) -> Dict[str, List[str]]:
        """Build mapping of node_id -> list of node IDs it depends on."""
        dependencies = {}

        for node in self.workflow_def.nodes:
            deps = node.depends_on or []
            dependencies[node.id] = deps

        return dependencies

    def _build_reverse_dependencies(self) -> Dict[str, List[str]]:
        """Build mapping of node_id -> list of nodes that depend on it."""
        reverse_deps = {node_id: [] for node_id in self.nodes}

        for node_id, deps in self.dependencies.items():
            for dep in deps:
                if dep in reverse_deps:
                    reverse_deps[dep].append(node_id)

        return reverse_deps

    def get_initial_nodes(self) -> List[str]:
        """Get nodes with no dependencies (entry points)."""
        return [
            node_id for node_id, deps in self.dependencies.items() if not deps
        ]

    def get_next_nodes(
        self, workflow_state: WorkflowExecutionState
    ) -> List[str]:
        """
        Determine which nodes can execute next.
        Returns nodes whose dependencies are all complete.
        """
        completed = set(workflow_state.completed_nodes.keys())
        next_nodes = []

        for node_id, deps in self.dependencies.items():
            # Skip if already completed
            if node_id in completed:
                continue

            # Skip if already pending
            if node_id in workflow_state.pending_nodes:
                continue

            # Check if all dependencies are satisfied
            if all(dep in completed for dep in deps):
                next_nodes.append(node_id)

        return next_nodes

    def validate_dag(self) -> List[str]:
        """
        Validate DAG structure.
        Returns list of validation errors or empty list if valid.
        """
        errors = []

        # Check for cycles
        if self._has_cycles():
            errors.append("Workflow DAG contains cycles")

        # Check for invalid dependencies
        for node_id, deps in self.dependencies.items():
            for dep in deps:
                if dep not in self.nodes:
                    errors.append(
                        f"Node '{node_id}' depends on non-existent node '{dep}'"
                    )

        # Check for unreachable nodes
        reachable = self._get_reachable_nodes()
        for node_id in self.nodes:
            if node_id not in reachable:
                errors.append(f"Node '{node_id}' is unreachable")

        return errors

    def _has_cycles(self) -> bool:
        """Detect cycles using depth-first search."""
        visited = set()
        rec_stack = set()

        def dfs(node_id: str) -> bool:
            visited.add(node_id)
            rec_stack.add(node_id)

            for dependent in self.reverse_dependencies.get(node_id, []):
                if dependent not in visited:
                    if dfs(dependent):
                        return True
                elif dependent in rec_stack:
                    return True

            rec_stack.remove(node_id)
            return False

        for node_id in self.nodes:
            if node_id not in visited:
                if dfs(node_id):
                    return True

        return False

    def _get_reachable_nodes(self) -> Set[str]:
        """Get set of all reachable nodes from initial nodes."""
        reachable = set()
        queue = self.get_initial_nodes()

        while queue:
            node_id = queue.pop(0)
            if node_id in reachable:
                continue
            reachable.add(node_id)
            queue.extend(self.reverse_dependencies.get(node_id, []))

        return reachable

    async def execute_workflow(
        self,
        workflow_state: WorkflowExecutionState,
        workflow_context: WorkflowExecutionContext,
    ):
        """
        Execute workflow DAG until completion or failure.
        Main execution loop.
        """
        log_id = f"{self.host.log_identifier}[Workflow:{workflow_state.execution_id}]"

        while True:
            # Get next nodes to execute
            next_nodes = self.get_next_nodes(workflow_state)

            if not next_nodes:
                # Check if workflow is complete
                if len(workflow_state.completed_nodes) == len(self.nodes):
                    log.info(f"{log_id} Workflow completed successfully")
                    await self.host.finalize_workflow_success(workflow_context)
                    return

                # Check if workflow is stuck
                if (
                    not workflow_state.pending_nodes
                    and not workflow_state.active_branches
                ):
                    # If we have conditional nodes, it's possible some nodes are skipped.
                    # We need to check if we are truly stuck or just finished a path.
                    # For MVP, we assume if pending is empty and not all nodes are done,
                    # but no next nodes are available, we might be done if the remaining
                    # nodes are unreachable due to conditional branches.
                    # However, a simpler check is: are there any nodes running?
                    # If pending_nodes is empty, nothing is running.
                    # If we are not "complete" (all nodes visited), but nothing is running,
                    # and no next nodes, then we are done with this execution path.
                    log.info(
                        f"{log_id} Workflow execution path completed (some nodes may have been skipped)."
                    )
                    await self.host.finalize_workflow_success(workflow_context)
                    return

                # Wait for pending nodes to complete
                log.debug(
                    f"{log_id} Waiting for {len(workflow_state.pending_nodes)} pending nodes"
                )
                return  # Execution will resume on node completion

            # Execute next nodes
            for node_id in next_nodes:
                await self.execute_node(node_id, workflow_state, workflow_context)

                # Update pending nodes
                # Only add if NOT completed (i.e. it was an async node that started)
                if node_id not in workflow_state.completed_nodes:
                    workflow_state.pending_nodes.append(node_id)

            # Persist state
            await self.host._update_workflow_state(workflow_context, workflow_state)

    async def execute_node(
        self,
        node_id: str,
        workflow_state: WorkflowExecutionState,
        workflow_context: WorkflowExecutionContext,
    ):
        """Execute a single workflow node."""
        log_id = f"{self.host.log_identifier}[Node:{node_id}]"

        try:
            node = self.nodes[node_id]

            # Handle different node types
            if node.type == "agent":
                await self._execute_agent_node(node, workflow_state, workflow_context)
            elif node.type == "conditional":
                await self._execute_conditional_node(
                    node, workflow_state, workflow_context
                )
            elif node.type == "fork":
                await self._execute_fork_node(node, workflow_state, workflow_context)
            elif node.type == "map":
                await self._execute_map_node(node, workflow_state, workflow_context)
            else:
                raise ValueError(f"Unknown node type: {node.type}")

        except Exception as e:
            log.error(f"{log_id} Node execution failed: {e}")

            # Set error state
            workflow_state.error_state = {
                "failed_node_id": node_id,
                "failure_reason": "execution_error",
                "error_message": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            # Propagate error
            raise WorkflowNodeFailureError(node_id, str(e)) from e

    async def _execute_agent_node(
        self,
        node: AgentNode,
        workflow_state: WorkflowExecutionState,
        workflow_context: WorkflowExecutionContext,
    ):
        """Execute an agent node by calling the persona."""
        await self.host.persona_caller.call_persona(
            node, workflow_state, workflow_context
        )

    async def _execute_conditional_node(
        self,
        node: ConditionalNode,
        workflow_state: WorkflowExecutionState,
        workflow_context: WorkflowExecutionContext,
    ):
        """Execute conditional node."""
        log_id = f"{self.host.log_identifier}[Conditional:{node.id}]"

        # Evaluate condition
        from .flow_control.conditional import evaluate_condition

        result = evaluate_condition(node.condition, workflow_state)

        log.info(f"{log_id} Condition '{node.condition}' evaluated to: {result}")

        # Select branch
        next_node_id = node.true_branch if result else node.false_branch

        # Mark conditional as complete immediately since it's internal logic
        workflow_state.completed_nodes[node.id] = "conditional_evaluated"

        if next_node_id:
            # Add selected branch to dependencies dynamically?
            # No, the graph is static. But we need to ensure the next node
            # becomes runnable.
            # The next node already depends on this conditional node.
            # So by marking this node complete, the next node will be picked up
            # by get_next_nodes in the next iteration.
            # However, we need to handle the UN-taken branch.
            # Nodes on the un-taken branch will effectively be skipped because
            # their dependencies (this conditional node) are met, BUT
            # we need to ensure we don't execute BOTH if the graph structure
            # implies it.
            # Actually, in a DAG, if A -> B and A -> C, and A is conditional,
            # we need to know which edge to follow.
            # The current DAG structure has `depends_on` in the child.
            # So B depends on A, and C depends on A.
            # If A evaluates to True, we want B to run.
            # If A evaluates to False, we want C to run.
            # But `get_next_nodes` will see A is complete and try to run BOTH B and C.
            # This implies we need to modify the graph or state to "block" the un-taken path.
            #
            # Strategy: We can mark the un-taken node as "skipped" or "completed"
            # so that its children can proceed (if they don't strictly need its output)
            # OR we assume the un-taken branch is dead.
            #
            # Let's implement a "skip" mechanism.
            pass

        # For MVP, we will assume the graph is structured such that
        # the conditional node is the ONLY dependency for the branch start nodes.
        # We need to explicitly "disable" the un-taken branch.
        # But wait, `get_next_nodes` checks `dependencies`.
        # If we want to prevent a node from running, we can mark it as "skipped" in completed_nodes?
        # Or we can modify the dependencies in memory?
        #
        # Better approach for MVP:
        # The `ConditionalNode` has `true_branch` and `false_branch` IDs.
        # We can check these in `get_next_nodes`? No, that's coupling.
        #
        # Let's use a `skipped_nodes` set in WorkflowExecutionState?
        # If a node is skipped, we treat it as completed for dependency purposes,
        # but we don't execute it. And we recursively skip its children?
        # That seems complex.
        #
        # Alternative:
        # `get_next_nodes` logic:
        # If a node depends on a ConditionalNode, we check if that ConditionalNode
        # selected THIS node as its branch.
        # This requires looking up the parent node type.

        # Let's refine `get_next_nodes` to handle this.
        # But `get_next_nodes` is generic.
        #
        # Let's stick to the design doc:
        # "Nodes on the un-taken branch will be skipped automatically by the
        # DAGExecutor, as their dependencies will never be met."
        # This implies we DON'T mark the conditional node as complete in the standard way?
        # Or we mark it complete, but `get_next_nodes` has extra logic?
        #
        # Actually, if we mark the conditional node as complete, both branches become runnable.
        # We must prevent the un-taken branch from running.
        #
        # Let's add `skipped_nodes` to `WorkflowExecutionState`.
        # When a conditional evaluates, we add the un-taken branch root to `skipped_nodes`.
        # And `get_next_nodes` filters out skipped nodes.
        # AND we need to propagate skipping. If a node depends on a skipped node, it is also skipped.

        untaken_node_id = node.false_branch if result else node.true_branch
        if untaken_node_id:
            await self._skip_branch(untaken_node_id, workflow_state)

        # Continue execution
        await self.execute_workflow(workflow_state, workflow_context)

    async def _skip_branch(
        self, node_id: str, workflow_state: WorkflowExecutionState
    ):
        """Recursively mark a branch as skipped."""
        if node_id in workflow_state.completed_nodes:
            return

        # Mark as skipped (using a special value in completed_nodes)
        workflow_state.completed_nodes[node_id] = "SKIPPED"

        # Find children
        children = self.reverse_dependencies.get(node_id, [])
        for child_id in children:
            # If child depends ONLY on skipped nodes (or completed nodes), skip it too?
            # If child has other dependencies that are NOT skipped, should it run?
            # Usually in workflow engines, if a parent is skipped, the child is skipped
            # unless there's a specific "join" logic (like "all_done" vs "all_success").
            # For MVP, we'll assume strict dependency: if any parent is skipped, child is skipped.
            await self._skip_branch(child_id, workflow_state)

    async def _execute_fork_node(
        self,
        node: ForkNode,
        workflow_state: WorkflowExecutionState,
        workflow_context: WorkflowExecutionContext,
    ):
        """Execute fork node with parallel branches."""
        log_id = f"{self.host.log_identifier}[Fork:{node.id}]"

        # Track active branches
        branch_sub_tasks = []

        # Launch all branches concurrently
        for branch in node.branches:
            log.debug(f"{log_id} Starting branch '{branch.id}'")

            # Create temporary node for branch
            branch_node = AgentNode(
                id=branch.id,
                type="agent",
                agent_persona=branch.agent_persona,
                input=branch.input,
                depends_on=[node.id],  # Depends on fork node
            )

            # Execute branch (returns immediately with sub-task ID)
            sub_task_id = await self.host.persona_caller.call_persona(
                branch_node, workflow_state, workflow_context
            )

            branch_sub_tasks.append(
                {
                    "branch_id": branch.id,
                    "output_key": branch.output_key,
                    "sub_task_id": sub_task_id,
                }
            )

        # Store branch tracking in workflow state
        workflow_state.active_branches[node.id] = branch_sub_tasks

        # Mark fork as pending (not complete until all branches finish)
        # Note: It was already added to pending_nodes by execute_workflow loop
        # but we need to ensure it stays there until branches are done.

    async def _execute_map_node(
        self,
        node: MapNode,
        workflow_state: WorkflowExecutionState,
        workflow_context: WorkflowExecutionContext,
    ):
        """Execute map node with concurrency control."""
        log_id = f"{self.host.log_identifier}[Map:{node.id}]"

        # Resolve items array
        items = self.resolve_value(node.items, workflow_state)

        if items is None:
            log.warning(f"{log_id} Map target resolved to None. Treating as empty list.")
            items = []

        if not isinstance(items, list):
            raise ValueError(f"Map target must be array, got: {type(items)}")

        # Check item limit
        max_items = (
            node.max_items or self.host.get_config("default_max_map_items", 100)
        )

        if len(items) > max_items:
            raise WorkflowExecutionError(
                f"Map '{node.id}' exceeds max items: " f"{len(items)} > {max_items}"
            )

        log.info(f"{log_id} Starting map with {len(items)} items")

        # Initialize tracking state
        # We store the full list of items and their status
        map_state = {
            "items": items,
            "results": [None] * len(items),  # Placeholders for results
            "pending_indices": list(range(len(items))),  # Indices waiting to run
            "active_indices": set(),  # Indices currently running
            "completed_count": 0,
            "concurrency_limit": node.concurrency_limit,
            "target_node_id": node.node,
        }

        # Store in active_branches (using a dict instead of list for map state)
        # Note: active_branches type hint is Dict[str, List[Dict]], but we are storing a Dict.
        # We should probably update the type hint or wrap this in a list.
        # For compatibility with existing structure, let's wrap it or adapt.
        # The existing structure expects a list of branches.
        # Let's adapt: active_branches[node.id] will hold the list of *active* sub-tasks.
        # But we need to store the *pending* state somewhere.
        # We can store the map_state in a special metadata field or abuse active_branches.
        # Let's use a list of dicts where the first element is the metadata/state.
        # This is a bit hacky but avoids schema changes.
        # Better: Use `metadata` field in WorkflowExecutionState for map state.
        workflow_state.metadata[f"map_state_{node.id}"] = map_state
        workflow_state.active_branches[node.id] = []  # Will hold active sub-tasks

        # Launch initial batch
        await self._launch_map_iterations(node.id, workflow_state, workflow_context)

    async def _launch_map_iterations(
        self,
        map_node_id: str,
        workflow_state: WorkflowExecutionState,
        workflow_context: WorkflowExecutionContext,
    ):
        """Launch pending map iterations up to concurrency limit."""
        map_state = workflow_state.metadata.get(f"map_state_{map_node_id}")
        if not map_state:
            return

        concurrency_limit = map_state["concurrency_limit"]
        active_indices = map_state["active_indices"]
        pending_indices = map_state["pending_indices"]
        items = map_state["items"]
        target_node_id = map_state["target_node_id"]

        # Determine how many to launch
        while pending_indices:
            if concurrency_limit and len(active_indices) >= concurrency_limit:
                break

            index = pending_indices.pop(0)
            item = items[index]
            active_indices.add(index)

            # Create iteration state
            iteration_state = workflow_state.model_copy(deep=False)
            iteration_state.node_outputs = {
                **workflow_state.node_outputs,
                "_map_item": {"output": item},
                "_map_index": {"output": index},
            }

            target_node = self.nodes[target_node_id]
            iter_node = target_node.model_copy()

            # Execute
            sub_task_id = await self.host.persona_caller.call_persona(
                iter_node, iteration_state, workflow_context
            )

            # Track active sub-task
            workflow_state.active_branches[map_node_id].append(
                {
                    "index": index,
                    "sub_task_id": sub_task_id,
                }
            )

    def resolve_value(
        self, value_def: Any, workflow_state: WorkflowExecutionState
    ) -> Any:
        """
        Resolve a value definition, handling templates and operators.
        Supports:
        - Literal values
        - Template strings: "{{...}}"
        - Operators: coalesce, concat
        """
        # Handle template string
        if isinstance(value_def, str) and value_def.startswith("{{"):
            return self._resolve_template(value_def, workflow_state)

        # Handle intrinsic functions (operators)
        if isinstance(value_def, dict) and len(value_def) == 1:
            op = next(iter(value_def))
            args = value_def[op]

            if op == "coalesce":
                if not isinstance(args, list):
                    raise ValueError("'coalesce' operator requires a list of values")

                for arg in args:
                    resolved = self.resolve_value(arg, workflow_state)
                    if resolved is not None:
                        return resolved
                return None

            if op == "concat":
                if not isinstance(args, list):
                    raise ValueError("'concat' operator requires a list of values")

                parts = []
                for arg in args:
                    resolved = self.resolve_value(arg, workflow_state)
                    if resolved is not None:
                        parts.append(str(resolved))
                return "".join(parts)

        # Return literal
        return value_def

    def _resolve_template(
        self, template: str, workflow_state: WorkflowExecutionState
    ) -> Any:
        """
        Resolve template variable.
        Format: {{node_id.output.field_path}} or {{workflow.input.field_path}}
        """
        # Extract variable path
        # Use fullmatch to ensure the template takes up the entire string
        # and handle optional whitespace inside braces: {{  value  }}
        match = re.fullmatch(r"\{\{\s*(.+?)\s*\}\}", template)
        if not match:
            return template

        path = match.group(1)
        parts = path.split(".")

        # Navigate path in workflow state
        if parts[0] == "workflow" and parts[1] == "input":
            # Reference to workflow input
            # Workflow input is stored in node_outputs["workflow_input"]
            if "workflow_input" not in workflow_state.node_outputs:
                raise ValueError("Workflow input has not been initialized")

            # Navigate from workflow_input.output.field_path
            data = workflow_state.node_outputs["workflow_input"]["output"]
            for part in parts[2:]:  # Skip "workflow" and "input"
                if isinstance(data, dict) and part in data:
                    data = data[part]
                else:
                    # Return None if input field is missing (allows coalesce to work)
                    return None
            return data
        else:
            # Reference to node output
            node_id = parts[0]
            if node_id not in workflow_state.node_outputs:
                # Check if it's a map variable
                if node_id in ["_map_item", "_map_index"]:
                    pass  # Allow it
                else:
                    # Return None for skipped/incomplete nodes to allow for safe navigation/coalescing
                    return None

            # Navigate remaining path
            data = workflow_state.node_outputs[node_id]
            for part in parts[1:]:
                if isinstance(data, dict) and part in data:
                    data = data[part]
                else:
                    raise ValueError(
                        f"Output field '{part}' not found in node '{node_id}' for path: {path}"
                    )

            return data

    async def handle_node_completion(
        self,
        workflow_context: WorkflowExecutionContext,
        sub_task_id: str,
        result: WorkflowNodeResultData,
    ):
        """Handle completion of a workflow node."""
        log_id = f"{self.host.log_identifier}[Workflow:{workflow_context.workflow_task_id}]"

        # Find which node this sub-task corresponds to
        node_id = workflow_context.get_node_id_for_sub_task(sub_task_id)

        if not node_id:
            log.error(f"{log_id} Received result for unknown sub-task: {sub_task_id}")
            return

        workflow_state = workflow_context.workflow_state

        # Check result status
        if result.status == "failure":
            log.error(f"{log_id} Node '{node_id}' failed: {result.error_message}")

            # Set error state
            workflow_state.error_state = {
                "failed_node_id": node_id,
                "failure_reason": "node_execution_failed",
                "error_message": result.error_message,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            # Fail entire workflow
            await self.host.finalize_workflow_failure(
                workflow_context,
                WorkflowNodeFailureError(node_id, result.error_message),
            )
            return

        # Node succeeded
        log.debug(f"{log_id} Node '{node_id}' completed successfully")

        # Check if this was part of a Fork or Map
        # We need to find if this node_id is being tracked in active_branches
        # But wait, node_id is the ID of the node definition.
        # For Fork, the node_id IS the branch ID.
        # For Map, the node_id IS the map body node ID.

        # Check if this node is part of an active fork/map
        parent_control_node_id = None
        for control_node_id, branches in workflow_state.active_branches.items():
            for branch in branches:
                if branch.get("sub_task_id") == sub_task_id:
                    parent_control_node_id = control_node_id
                    break
            if parent_control_node_id:
                break

        if parent_control_node_id:
            await self._handle_control_node_child_completion(
                parent_control_node_id,
                sub_task_id,
                result,
                workflow_state,
                workflow_context,
            )
        else:
            # Standard node completion
            workflow_state.completed_nodes[node_id] = result.artifact_name
            if node_id in workflow_state.pending_nodes:
                workflow_state.pending_nodes.remove(node_id)

            # Cache node output for value references
            if result.artifact_name:
                artifact_data = await self.host._load_node_output(
                    node_id,
                    result.artifact_name,
                    result.artifact_version,
                    workflow_context,
                )
                workflow_state.node_outputs[node_id] = {"output": artifact_data}

            # Continue workflow execution
            await self.execute_workflow(workflow_state, workflow_context)

    async def _handle_control_node_child_completion(
        self,
        control_node_id: str,
        sub_task_id: str,
        result: WorkflowNodeResultData,
        workflow_state: WorkflowExecutionState,
        workflow_context: WorkflowExecutionContext,
    ):
        """Handle completion of a child task within a Fork or Map."""
        log_id = f"{self.host.log_identifier}[ControlNode:{control_node_id}]"
        branches = workflow_state.active_branches.get(control_node_id, [])

        # Find the specific branch/iteration
        completed_branch = None
        for branch in branches:
            if branch["sub_task_id"] == sub_task_id:
                completed_branch = branch
                break

        if not completed_branch:
            log.error(f"{log_id} Could not find branch for sub-task {sub_task_id}")
            return

        # Update result
        completed_branch["result"] = {
            "artifact_name": result.artifact_name,
            "artifact_version": result.artifact_version,
        }

        control_node = self.nodes[control_node_id]

        if control_node.type == "map":
            # Handle Map logic (concurrency, state update)
            map_state = workflow_state.metadata.get(f"map_state_{control_node_id}")
            if map_state:
                index = completed_branch["index"]
                map_state["active_indices"].remove(index)
                map_state["completed_count"] += 1
                # Store result in map_state for final aggregation
                map_state["results"][index] = completed_branch

                # Launch next pending items
                await self._launch_map_iterations(
                    control_node_id, workflow_state, workflow_context
                )

                # Check if ALL items are complete
                if map_state["completed_count"] == len(map_state["items"]):
                    log.info(f"{log_id} All map items completed")
                    await self._finalize_map_node(
                        control_node_id, map_state, workflow_state, workflow_context
                    )
        else:
            # Fork logic (wait for all)
            all_complete = all("result" in b for b in branches)
            if all_complete:
                log.info(f"{log_id} All fork branches completed")
                await self._finalize_fork_node(
                    control_node_id, branches, workflow_state, workflow_context
                )

    async def _finalize_fork_node(
        self,
        fork_node_id: str,
        branches: List[Dict],
        workflow_state: WorkflowExecutionState,
        workflow_context: WorkflowExecutionContext,
    ):
        """Merge fork branch results."""
        log_id = f"{self.host.log_identifier}[Fork:{fork_node_id}]"

        # Load all branch artifacts
        merged_output = {}

        for branch in branches:
            output_key = branch["output_key"]
            artifact_name = branch["result"]["artifact_name"]
            artifact_version = branch["result"]["artifact_version"]

            # Load artifact
            artifact_data = await self.host._load_node_output(
                node_id=fork_node_id,
                artifact_name=artifact_name,
                artifact_version=artifact_version,
                workflow_context=workflow_context,
                sub_task_id=branch["sub_task_id"],
            )

            # Add to merged output
            merged_output[output_key] = artifact_data

        # Create merged artifact
        merged_artifact_name = f"fork_{fork_node_id}_merged.json"
        await self.host.artifact_service.save_artifact(
            app_name=self.host.agent_name,
            user_id=workflow_context.a2a_context["user_id"],
            session_id=workflow_context.a2a_context["session_id"],
            filename=merged_artifact_name,
            artifact=adk_types.Part.from_text(json.dumps(merged_output)), # Simplified for MVP
        )
        # Note: The above save_artifact call is simplified. 
        # Real implementation needs to construct a proper Part or use a helper.
        # We will rely on the host component to provide a helper or use the service directly correctly.
        # For now, let's assume we can pass data directly if we use a helper, 
        # or we need to construct a Part.
        
        # Mark fork complete
        workflow_state.completed_nodes[fork_node_id] = merged_artifact_name
        if fork_node_id in workflow_state.pending_nodes:
            workflow_state.pending_nodes.remove(fork_node_id)
        workflow_state.node_outputs[fork_node_id] = {"output": merged_output}

        # Clear branch tracking
        del workflow_state.active_branches[fork_node_id]

        # Continue workflow
        await self.execute_workflow(workflow_state, workflow_context)

    async def _finalize_map_node(
        self,
        map_node_id: str,
        map_state: Dict,
        workflow_state: WorkflowExecutionState,
        workflow_context: WorkflowExecutionContext,
    ):
        """Aggregate map results."""
        log_id = f"{self.host.log_identifier}[Map:{map_node_id}]"

        results_list = []
        # map_state["results"] is already ordered by index
        for iter_info in map_state["results"]:
            if not iter_info or "result" not in iter_info:
                # Should not happen if completed_count check is correct
                log.error(f"{log_id} Missing result for item")
                results_list.append(None)
                continue

            artifact_name = iter_info["result"]["artifact_name"]
            artifact_version = iter_info["result"]["artifact_version"]

            artifact_data = await self.host._load_node_output(
                node_id=map_node_id,
                artifact_name=artifact_name,
                artifact_version=artifact_version,
                workflow_context=workflow_context,
                sub_task_id=iter_info["sub_task_id"],
            )
            results_list.append(artifact_data)

        # Create aggregated artifact
        merged_artifact_name = f"map_{map_node_id}_results.json"
        await self.host.artifact_service.save_artifact(
            app_name=self.host.agent_name,
            user_id=workflow_context.a2a_context["user_id"],
            session_id=workflow_context.a2a_context["session_id"],
            filename=merged_artifact_name,
            artifact=adk_types.Part.from_text(json.dumps({"results": results_list})),
        )

        workflow_state.completed_nodes[map_node_id] = merged_artifact_name
        if map_node_id in workflow_state.pending_nodes:
            workflow_state.pending_nodes.remove(map_node_id)
        workflow_state.node_outputs[map_node_id] = {"output": {"results": results_list}}

        # Cleanup state
        del workflow_state.active_branches[map_node_id]
        del workflow_state.metadata[f"map_state_{map_node_id}"]

        await self.execute_workflow(workflow_state, workflow_context)
