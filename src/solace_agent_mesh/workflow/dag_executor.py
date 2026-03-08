"""
DAG Executor for Prescriptive Workflows.
Manages the execution order of workflow nodes based on their dependencies.
"""

import logging
import re
import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, TYPE_CHECKING

from google.genai import types as adk_types

from .app import (
    WorkflowDefinition,
    WorkflowNode,
    AgentNode,
    SwitchNode,
    LoopNode,
    MapNode,
    WorkflowInvokeNode,
)
from .workflow_execution_context import WorkflowExecutionContext, WorkflowExecutionState
from ..common.data_parts import (
    StructuredInvocationResult,
    WorkflowNodeExecutionStartData,
    WorkflowNodeExecutionResultData,
    WorkflowMapProgressData,
    ArtifactRef,
)
from ..agent.utils.artifact_helpers import save_artifact_with_metadata

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

        # Identify inner nodes (targets of MapNodes/LoopNodes) that should not be executed directly
        self.inner_nodes = set()
        for node in workflow_definition.nodes:
            if node.type == "map":
                self.inner_nodes.add(node.node)
            elif node.type == "loop":
                self.inner_nodes.add(node.node)

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
            node_id
            for node_id, deps in self.dependencies.items()
            if not deps and node_id not in self.inner_nodes
        ]

    def get_node_by_id(self, node_id: str) -> Optional[WorkflowNode]:
        """Get a node by its ID."""
        return self.nodes.get(node_id)

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
            # Skip inner nodes (executed by MapNodes)
            if node_id in self.inner_nodes:
                continue

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

        # Check for unreachable nodes (excluding inner nodes which are reached via map execution)
        reachable = self._get_reachable_nodes()
        for node_id in self.nodes:
            # Inner nodes (map targets) are reachable via their parent map node
            if node_id not in reachable and node_id not in self.inner_nodes:
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
            # Check for cancellation before proceeding
            if workflow_context.is_cancelled():
                log.info(f"{log_id} Workflow cancelled, stopping execution")
                return

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

            # Execute next nodes with implicit parallelism detection and branch inheritance
            # Determine parallel group and branch assignments for each node
            node_parallel_info = {}  # node_id -> (parallel_group_id, branch_index)

            if len(next_nodes) > 1:
                # Multiple nodes ready = implicit parallel execution (like implicit fork)
                # Check if all nodes share the same single dependency in the same branch
                # If so, this is a new fork point
                parallel_group_id = f"implicit_parallel_{workflow_state.execution_id}_{uuid.uuid4().hex[:8]}"
                log.info(f"{log_id} Implicit parallel execution: {len(next_nodes)} nodes, group={parallel_group_id}")

                # Assign each node to a separate branch
                for branch_idx, nid in enumerate(next_nodes):
                    node_parallel_info[nid] = (parallel_group_id, branch_idx)
                    # Track in workflow state
                    if parallel_group_id not in workflow_state.parallel_branch_assignments:
                        workflow_state.parallel_branch_assignments[parallel_group_id] = {}
                    workflow_state.parallel_branch_assignments[parallel_group_id][nid] = branch_idx
            else:
                # Single node - check if it should inherit a branch from its dependencies
                for nid in next_nodes:
                    inherited_info = self._get_inherited_branch(nid, workflow_state)
                    if inherited_info:
                        parallel_group_id, branch_idx = inherited_info
                        node_parallel_info[nid] = inherited_info
                        # Track in workflow state
                        workflow_state.parallel_branch_assignments[parallel_group_id][nid] = branch_idx
                        log.debug(f"{log_id} Node {nid} inherits branch {branch_idx} from group {parallel_group_id}")

            for node_id in next_nodes:
                parallel_info = node_parallel_info.get(node_id)
                pg_id = parallel_info[0] if parallel_info else None
                branch_idx = parallel_info[1] if parallel_info else None
                await self.execute_node(node_id, workflow_state, workflow_context, pg_id, branch_idx)

                # Update pending nodes
                # Only add if NOT completed (i.e. it was an async node that started)
                if node_id not in workflow_state.completed_nodes:
                    workflow_state.pending_nodes.append(node_id)

            # Persist state
            await self.host._update_workflow_state(workflow_context, workflow_state)

    def _get_inherited_branch(
        self,
        node_id: str,
        workflow_state: WorkflowExecutionState,
    ) -> Optional[tuple]:
        """
        Check if a node should inherit a branch assignment from its dependencies.

        A node inherits a branch if ALL its dependencies are in the same branch
        of the same parallel group. If dependencies span multiple branches or
        parallel groups, this is an implicit join point and no inheritance occurs.

        Returns: (parallel_group_id, branch_index) or None
        """
        node = self.nodes[node_id]
        if not node.depends_on:
            return None

        # Find which parallel group/branch each dependency is in
        dep_branches = []  # List of (parallel_group_id, branch_index) for each dep
        for dep_id in node.depends_on:
            # Skip dependencies that were skipped (conditional branches)
            if dep_id in workflow_state.skipped_nodes:
                continue

            # Find if this dependency is in any parallel group
            found = False
            for pg_id, assignments in workflow_state.parallel_branch_assignments.items():
                if dep_id in assignments:
                    dep_branches.append((pg_id, assignments[dep_id]))
                    found = True
                    break

            if not found:
                # Dependency is not in any parallel group
                dep_branches.append(None)

        # Filter out None entries (deps not in parallel groups)
        parallel_deps = [b for b in dep_branches if b is not None]

        if not parallel_deps:
            # No dependencies are in parallel groups
            return None

        # Check if all parallel dependencies are in the same group and branch
        first_group, first_branch = parallel_deps[0]
        for pg_id, branch_idx in parallel_deps[1:]:
            if pg_id != first_group or branch_idx != first_branch:
                # Dependencies span multiple branches - this is an implicit join
                return None

        # All parallel dependencies are in the same branch - inherit it
        return (first_group, first_branch)

    async def execute_node(
        self,
        node_id: str,
        workflow_state: WorkflowExecutionState,
        workflow_context: WorkflowExecutionContext,
        implicit_parallel_group_id: Optional[str] = None,
        implicit_branch_index: Optional[int] = None,
    ):
        """Execute a single workflow node."""
        log_id = f"{self.host.log_identifier}[Node:{node_id}]"

        # Check for cancellation before executing node
        if workflow_context.is_cancelled():
            log.info(f"{log_id} Workflow cancelled, not executing node")
            return

        try:
            node = self.nodes[node_id]

            # Generate sub-task ID for agent and workflow nodes to link events
            sub_task_id = None
            if node.type in ("agent", "workflow"):
                sub_task_id = f"wf_{workflow_state.execution_id}_{node.id}_{uuid.uuid4().hex[:8]}"

            # Publish start event
            start_data_args = {
                "type": "workflow_node_execution_start",
                "node_id": node_id,
                "node_type": node.type,
                "agent_name": getattr(node, "agent_name", None) or getattr(node, "workflow_name", None),
                "sub_task_id": sub_task_id,
            }

            # Include implicit parallel group ID and branch index for agent and workflow nodes (used for visualization)
            if implicit_parallel_group_id and node.type in ("agent", "workflow"):
                start_data_args["parallel_group_id"] = implicit_parallel_group_id
                if implicit_branch_index is not None:
                    start_data_args["iteration_index"] = implicit_branch_index

            if node.type == "switch":
                # Include switch case info for visualization
                from ..common.data_parts import SwitchCaseInfo
                start_data_args["cases"] = [
                    SwitchCaseInfo(condition=case.condition, node=case.node)
                    for case in node.cases
                ]
                start_data_args["default_branch"] = node.default

            elif node.type == "loop":
                # Include loop configuration for visualization
                start_data_args["condition"] = node.condition
                start_data_args["max_iterations"] = node.max_iterations
                start_data_args["loop_delay"] = node.delay

            # Generate parallel_group_id for map nodes so the frontend can group children
            parallel_group_id = None
            if node.type == "map":
                parallel_group_id = f"map_{node.id}_{workflow_state.execution_id}"
                start_data_args["parallel_group_id"] = parallel_group_id

            start_data = WorkflowNodeExecutionStartData(**start_data_args)
            await self.host.publish_workflow_event(workflow_context, start_data)

            # Handle different node types
            if node.type == "agent":
                await self._execute_agent_node(node, workflow_state, workflow_context, sub_task_id)
            elif node.type == "workflow":
                await self._execute_workflow_node(node, workflow_state, workflow_context, sub_task_id)
            elif node.type == "switch":
                await self._execute_switch_node(node, workflow_state, workflow_context)
            elif node.type == "loop":
                await self._execute_loop_node(node, workflow_state, workflow_context)
            elif node.type == "map":
                await self._execute_map_node(node, workflow_state, workflow_context, parallel_group_id)
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
        sub_task_id: Optional[str] = None,
    ):
        """Execute an agent node by calling the agent."""
        log_id = f"{self.host.log_identifier}[Agent:{node.id}]"

        # Check 'when' clause if present (Argo-style conditional)
        if node.when:
            from .flow_control.conditional import evaluate_condition

            try:
                should_execute = evaluate_condition(node.when, workflow_state)
            except Exception as e:
                log.warning(f"{log_id} 'when' clause evaluation failed: {e}")
                should_execute = False

            if not should_execute:
                log.info(
                    f"{log_id} Skipping node due to 'when' clause: {node.when}"
                )
                # Mark as skipped
                workflow_state.skipped_nodes[node.id] = f"when_clause_false: {node.when}"
                workflow_state.completed_nodes[node.id] = "SKIPPED_BY_WHEN"
                workflow_state.node_outputs[node.id] = {
                    "output": None,
                    "skipped": True,
                    "skip_reason": "when_clause_false",
                }

                # Publish skipped event
                result_data = WorkflowNodeExecutionResultData(
                    type="workflow_node_execution_result",
                    node_id=node.id,
                    status="skipped",
                    metadata={"skip_reason": "when_clause_false", "when": node.when},
                )
                await self.host.publish_workflow_event(workflow_context, result_data)

                # Continue workflow
                await self.execute_workflow(workflow_state, workflow_context)
                return

        await self.host.agent_caller.call_agent(
            node, workflow_state, workflow_context, sub_task_id
        )

    async def _execute_workflow_node(
        self,
        node: WorkflowInvokeNode,
        workflow_state: WorkflowExecutionState,
        workflow_context: WorkflowExecutionContext,
        sub_task_id: Optional[str] = None,
    ):
        """Execute a workflow node by calling the sub-workflow."""
        log_id = f"{self.host.log_identifier}[Workflow:{node.id}]"

        # Check for direct recursion (workflow invoking itself)
        if node.workflow_name == self.host.workflow_name:
            error_msg = (
                f"Direct recursion detected: workflow '{self.host.workflow_name}' "
                f"cannot invoke itself via node '{node.id}'"
            )
            log.error(f"{log_id} {error_msg}")
            raise WorkflowExecutionError(error_msg)

        # Check 'when' clause if present (Argo-style conditional)
        if node.when:
            from .flow_control.conditional import evaluate_condition

            try:
                should_execute = evaluate_condition(node.when, workflow_state)
            except Exception as e:
                log.warning(f"{log_id} 'when' clause evaluation failed: {e}")
                should_execute = False

            if not should_execute:
                log.info(
                    f"{log_id} Skipping workflow node due to 'when' clause: {node.when}"
                )
                # Mark as skipped
                workflow_state.skipped_nodes[node.id] = f"when_clause_false: {node.when}"
                workflow_state.completed_nodes[node.id] = "SKIPPED_BY_WHEN"
                workflow_state.node_outputs[node.id] = {
                    "output": None,
                    "skipped": True,
                    "skip_reason": "when_clause_false",
                }

                # Publish skipped event
                result_data = WorkflowNodeExecutionResultData(
                    type="workflow_node_execution_result",
                    node_id=node.id,
                    status="skipped",
                    metadata={"skip_reason": "when_clause_false", "when": node.when},
                )
                await self.host.publish_workflow_event(workflow_context, result_data)

                # Continue workflow
                await self.execute_workflow(workflow_state, workflow_context)
                return

        # Call the sub-workflow using the agent caller
        # Workflows register as agents, so we use call_workflow which adapts the invocation
        await self.host.agent_caller.call_workflow(
            node, workflow_state, workflow_context, sub_task_id
        )

    async def _execute_switch_node(
        self,
        node: SwitchNode,
        workflow_state: WorkflowExecutionState,
        workflow_context: WorkflowExecutionContext,
    ):
        """Execute switch node for multi-way branching."""
        log_id = f"{self.host.log_identifier}[Switch:{node.id}]"

        from .flow_control.conditional import evaluate_condition

        selected_branch = None
        selected_case_index = None

        # Evaluate cases in order, first match wins
        for i, case in enumerate(node.cases):
            try:
                result = evaluate_condition(case.condition, workflow_state)
                if result:
                    selected_branch = case.node
                    selected_case_index = i
                    log.info(
                        f"{log_id} Case {i} condition '{case.condition}' matched, "
                        f"selecting branch '{case.node}'"
                    )
                    break
            except Exception as e:
                log.warning(f"{log_id} Case {i} evaluation failed: {e}")
                continue

        # Use default if no case matched
        if selected_branch is None and node.default:
            selected_branch = node.default
            log.info(f"{log_id} No case matched, using default branch '{node.default}'")

        # Mark switch as complete
        workflow_state.completed_nodes[node.id] = "switch_evaluated"
        workflow_state.node_outputs[node.id] = {
            "output": {
                "selected_branch": selected_branch,
                "selected_case_index": selected_case_index,
            }
        }

        # Publish result event
        result_data = WorkflowNodeExecutionResultData(
            type="workflow_node_execution_result",
            node_id=node.id,
            status="success",
            metadata={
                "selected_branch": selected_branch,
                "selected_case_index": selected_case_index,
            },
        )
        await self.host.publish_workflow_event(workflow_context, result_data)

        # Skip all non-selected branches
        all_branches = [case.node for case in node.cases]
        if node.default:
            all_branches.append(node.default)

        for branch_id in all_branches:
            if branch_id != selected_branch:
                await self._skip_branch(branch_id, workflow_state)

        # Continue execution
        await self.execute_workflow(workflow_state, workflow_context)

    async def _execute_loop_node(
        self,
        node: LoopNode,
        workflow_state: WorkflowExecutionState,
        workflow_context: WorkflowExecutionContext,
    ):
        """Execute loop node for while-loop iteration."""
        log_id = f"{self.host.log_identifier}[Loop:{node.id}]"

        # Check for cancellation before starting loop iteration
        if workflow_context.is_cancelled():
            log.info(f"{log_id} Workflow cancelled, not starting loop iteration")
            return

        from .flow_control.conditional import evaluate_condition
        from .utils import parse_duration

        # Initialize or get iteration count
        if node.id not in workflow_state.loop_iterations:
            workflow_state.loop_iterations[node.id] = 0

        iteration = workflow_state.loop_iterations[node.id]

        # Check max iterations
        if iteration >= node.max_iterations:
            log.warning(
                f"{log_id} Max iterations ({node.max_iterations}) reached, stopping loop"
            )
            workflow_state.completed_nodes[node.id] = "loop_max_iterations"
            workflow_state.node_outputs[node.id] = {
                "output": {
                    "iterations_completed": iteration,
                    "stopped_reason": "max_iterations",
                }
            }
            # Continue workflow
            await self.execute_workflow(workflow_state, workflow_context)
            return

        # Evaluate loop condition
        # On the first iteration (iteration=0), skip condition check and always run
        # This makes the loop behave like a "do-while" - condition is checked after first run
        if iteration == 0:
            should_continue = True
        else:
            try:
                should_continue = evaluate_condition(node.condition, workflow_state)
            except Exception as e:
                log.error(f"{log_id} Loop condition evaluation failed: {e}")
                should_continue = False

        if not should_continue:
            workflow_state.completed_nodes[node.id] = "loop_condition_false"
            if node.id in workflow_state.pending_nodes:
                workflow_state.pending_nodes.remove(node.id)
            workflow_state.node_outputs[node.id] = {
                "output": {
                    "iterations_completed": iteration,
                    "stopped_reason": "condition_false",
                }
            }

            # Publish result event for the loop node completion
            result_data = WorkflowNodeExecutionResultData(
                type="workflow_node_execution_result",
                node_id=node.id,
                status="success",
                metadata={
                    "iterations_completed": iteration,
                    "stopped_reason": "condition_false",
                },
            )
            await self.host.publish_workflow_event(workflow_context, result_data)

            # Continue workflow
            await self.execute_workflow(workflow_state, workflow_context)
            return

        # Apply delay if configured
        if node.delay and iteration > 0:  # No delay on first iteration
            delay_seconds = parse_duration(node.delay)
            log.debug(f"{log_id} Applying delay of {delay_seconds}s before iteration {iteration}")
            await asyncio.sleep(delay_seconds)

        # Increment iteration count
        workflow_state.loop_iterations[node.id] = iteration + 1

        log.info(f"{log_id} Starting iteration {iteration + 1}")

        # Execute inner node
        target_node = self.nodes[node.node]
        iter_node = target_node.model_copy()
        # Assign unique ID for this iteration
        iter_node.id = f"{node.id}_iter_{iteration}"

        # Store iteration context
        workflow_state.node_outputs["_loop_iteration"] = {"output": iteration}

        # Generate sub-task ID
        sub_task_id = f"wf_{workflow_state.execution_id}_{iter_node.id}_{uuid.uuid4().hex[:8]}"

        # Handle both AgentInvokeNode (has agent_name) and WorkflowInvokeNode (has workflow_name)
        target_name = getattr(iter_node, "agent_name", getattr(iter_node, "workflow_name", None))

        # Emit start event for loop iteration child
        start_data = WorkflowNodeExecutionStartData(
            type="workflow_node_execution_start",
            node_id=iter_node.id,
            node_type="agent",
            agent_name=target_name,
            iteration_index=iteration,
            sub_task_id=sub_task_id,
            parent_node_id=node.id,
        )
        await self.host.publish_workflow_event(workflow_context, start_data)

        # Track in active branches for completion handling
        workflow_state.active_branches[node.id] = [
            {
                "iteration": iteration,
                "sub_task_id": sub_task_id,
                "type": "loop",
            }
        ]

        # Execute the inner node
        if iter_node.type == "workflow":
            await self.host.agent_caller.call_workflow(
                iter_node, workflow_state, workflow_context, sub_task_id=sub_task_id
            )
        else:
            await self.host.agent_caller.call_agent(
                iter_node, workflow_state, workflow_context, sub_task_id=sub_task_id
            )

    async def _skip_branch(
        self, node_id: str, workflow_state: WorkflowExecutionState
    ):
        """Recursively mark a branch as skipped."""
        if node_id in workflow_state.completed_nodes:
            return

        # Mark as skipped (using a special value in completed_nodes)
        workflow_state.completed_nodes[node_id] = "SKIPPED"

        # Publish skipped event (optional, but good for visualization)
        # We need context to publish, but _skip_branch doesn't have it passed down.
        # For now, we skip publishing "skipped" events to avoid signature changes,
        # or we can rely on the UI inferring it from the conditional result.
        # Actually, let's leave it implicit for now.

        # Find children
        children = self.reverse_dependencies.get(node_id, [])
        for child_id in children:
            # Only skip child if ALL its dependencies are skipped
            child_deps = self.dependencies.get(child_id, [])

            all_deps_skipped = True
            for dep in child_deps:
                # If dependency is not completed, or completed but not skipped, then child might still run
                if dep not in workflow_state.completed_nodes:
                    all_deps_skipped = False
                    break
                if workflow_state.completed_nodes[dep] != "SKIPPED":
                    all_deps_skipped = False
                    break

            if all_deps_skipped:
                await self._skip_branch(child_id, workflow_state)

    async def _execute_map_node(
        self,
        node: MapNode,
        workflow_state: WorkflowExecutionState,
        workflow_context: WorkflowExecutionContext,
        parallel_group_id: str,
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
            "parallel_group_id": parallel_group_id,
        }

        # Store in active_branches (using a dict instead of list for map state)
        # Store map state in metadata field (designed for node-specific extensible state).
        # active_branches tracks the currently executing sub-tasks for this map node.
        workflow_state.metadata[f"map_state_{node.id}"] = map_state
        workflow_state.active_branches[node.id] = []

        # Launch initial batch
        await self._launch_map_iterations(node.id, workflow_state, workflow_context)

    async def _launch_map_iterations(
        self,
        map_node_id: str,
        workflow_state: WorkflowExecutionState,
        workflow_context: WorkflowExecutionContext,
    ):
        """Launch pending map iterations up to concurrency limit."""
        # Check for cancellation before launching new iterations
        if workflow_context.is_cancelled():
            log.info(f"{self.host.log_identifier}[Map:{map_node_id}] Workflow cancelled, not launching new iterations")
            return

        map_state = workflow_state.metadata.get(f"map_state_{map_node_id}")
        if not map_state:
            return

        concurrency_limit = map_state["concurrency_limit"]
        active_indices = map_state["active_indices"]
        pending_indices = map_state["pending_indices"]
        items = map_state["items"]
        target_node_id = map_state["target_node_id"]
        parallel_group_id = map_state.get("parallel_group_id")

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
            # Assign unique ID for this iteration to ensure distinct events and tracking
            iter_node.id = f"{map_node_id}_{index}"

            # Generate sub-task ID
            sub_task_id = f"wf_{workflow_state.execution_id}_{iter_node.id}_{uuid.uuid4().hex[:8]}"

            # Emit start event for iteration BEFORE execution
            target_name = getattr(iter_node, "agent_name", getattr(iter_node, "workflow_name", None))            
            start_data = WorkflowNodeExecutionStartData(
                type="workflow_node_execution_start",
                node_id=iter_node.id,
                node_type="agent",
                agent_name=target_name,
                iteration_index=index,
                sub_task_id=sub_task_id,
                parent_node_id=map_node_id,
                parallel_group_id=parallel_group_id,
            )
            await self.host.publish_workflow_event(workflow_context, start_data)

            # Execute
            if iter_node.type == "workflow":
                await self.host.agent_caller.call_workflow(
                    iter_node, iteration_state, workflow_context, sub_task_id=sub_task_id
                )
            else:
                await self.host.agent_caller.call_agent(
                    iter_node, iteration_state, workflow_context, sub_task_id=sub_task_id
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
        - Nested dicts and lists (recursively resolved)
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

        # Handle nested dicts - recursively resolve all values
        if isinstance(value_def, dict):
            resolved_dict = {}
            for key, value in value_def.items():
                resolved_dict[key] = self.resolve_value(value, workflow_state)
            return resolved_dict

        # Handle nested lists - recursively resolve all items
        if isinstance(value_def, list):
            return [self.resolve_value(item, workflow_state) for item in value_def]

        # Return literal
        return value_def

    def _resolve_template(
        self, template: str, workflow_state: WorkflowExecutionState
    ) -> Any:
        """
        Resolve template variable.
        Format: {{node_id.output.field_path}} or {{workflow.input.field_path}}

        Supports Argo-style aliases:
        - {{item}} -> {{_map_item}}
        - {{workflow.parameters.x}} -> {{workflow.input.x}}
        """
        # Apply Argo-compatible aliases
        from .flow_control.conditional import _apply_template_aliases

        template = _apply_template_aliases(template)

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
                # Check if it's a map/loop variable
                if node_id in ["_map_item", "_map_index", "_loop_iteration"]:
                    pass  # Allow it
                else:
                    # Return None for skipped/incomplete nodes to allow for safe navigation/coalescing
                    return None

            # Navigate remaining path
            # Special handling for map/loop variables: unwrap 'output' immediately
            if node_id in ["_map_item", "_map_index", "_loop_iteration"]:
                data = workflow_state.node_outputs[node_id].get("output")
            else:
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
        result: StructuredInvocationResult,
    ):
        """Handle completion of a workflow node."""
        log_id = f"{self.host.log_identifier}[Workflow:{workflow_context.workflow_task_id}]"

        # Check for cancellation - don't process results if workflow is cancelled
        if workflow_context.is_cancelled():
            log.info(f"{log_id} Workflow cancelled, ignoring node completion for sub-task {sub_task_id}")
            return

        # Find which node this sub-task corresponds to
        node_id = workflow_context.get_node_id_for_sub_task(sub_task_id)

        if not node_id:
            log.error(f"{log_id} Received result for unknown sub-task: {sub_task_id}")
            return

        workflow_state = workflow_context.workflow_state

        # Check result status
        if result.status == "error":
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

        # Publish success event
        result_data = WorkflowNodeExecutionResultData(
            type="workflow_node_execution_result",
            node_id=node_id,
            status="success",
            output_artifact_ref=result.output_artifact_ref,
        )
        await self.host.publish_workflow_event(workflow_context, result_data)

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
            artifact_name = result.output_artifact_ref.name if result.output_artifact_ref else None
            workflow_state.completed_nodes[node_id] = artifact_name
            if node_id in workflow_state.pending_nodes:
                workflow_state.pending_nodes.remove(node_id)

            # Cache node output for value references
            if result.output_artifact_ref and result.output_artifact_ref.name:
                artifact_data = await self.host._load_node_output(
                    node_id,
                    result.output_artifact_ref.name,
                    result.output_artifact_ref.version,
                    workflow_context,
                )
                workflow_state.node_outputs[node_id] = {"output": artifact_data}

            # Continue workflow execution
            await self.execute_workflow(workflow_state, workflow_context)

    async def _handle_control_node_child_completion(
        self,
        control_node_id: str,
        sub_task_id: str,
        result: StructuredInvocationResult,
        workflow_state: WorkflowExecutionState,
        workflow_context: WorkflowExecutionContext,
    ):
        """Handle completion of a child task within a Fork or Map."""
        log_id = f"{self.host.log_identifier}[ControlNode:{control_node_id}]"

        # Check for cancellation - don't continue processing if workflow is cancelled
        if workflow_context.is_cancelled():
            log.info(f"{log_id} Workflow cancelled, not processing child completion for sub-task {sub_task_id}")
            return

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

        # Check for duplicate completion
        if "result" in completed_branch:
            log.warning(
                f"{log_id} Sub-task {sub_task_id} already completed. Ignoring duplicate response."
            )
            return

        # Update result
        completed_branch["result"] = {
            "artifact_name": result.output_artifact_ref.name if result.output_artifact_ref else None,
            "artifact_version": result.output_artifact_ref.version if result.output_artifact_ref else None,
        }

        control_node = self.nodes[control_node_id]

        if control_node.type == "loop":
            # Handle Loop iteration completion
            iteration = completed_branch.get("iteration")
            log.info(f"{log_id} Loop iteration {iteration} completed")

            # Load result and store in node_outputs for condition evaluation
            if result.output_artifact_ref and result.output_artifact_ref.name:
                artifact_data = await self.host._load_node_output(
                    node_id=control_node_id,
                    artifact_name=result.output_artifact_ref.name,
                    artifact_version=result.output_artifact_ref.version,
                    workflow_context=workflow_context,
                    sub_task_id=sub_task_id,
                )
                # Store result under the inner node's original ID so conditions can reference it
                # e.g., {{check_task_status.output.ready}} will find the result
                inner_node_id = control_node.node  # The original inner node ID from workflow definition
                workflow_state.node_outputs[inner_node_id] = {
                    "output": artifact_data
                }
                log.debug(f"{log_id} Stored loop iteration result under '{inner_node_id}'")

            # Clear active branches for this loop
            del workflow_state.active_branches[control_node_id]

            # Re-execute loop node to check condition for next iteration
            await self._execute_loop_node(
                control_node, workflow_state, workflow_context
            )
        elif control_node.type == "map":
            # Handle Map logic (concurrency, state update)
            map_state = workflow_state.metadata.get(f"map_state_{control_node_id}")
            if map_state:
                index = completed_branch["index"]
                # Safely remove index (idempotency check above should prevent this, but being safe)
                if index in map_state["active_indices"]:
                    map_state["active_indices"].remove(index)
                else:
                    log.warning(f"{log_id} Index {index} not found in active_indices during completion.")

                map_state["completed_count"] += 1
                # Store result in map_state for final aggregation
                map_state["results"][index] = completed_branch

                # Publish map progress
                progress_data = WorkflowMapProgressData(
                    type="workflow_map_progress",
                    node_id=control_node_id,
                    total_items=len(map_state["items"]),
                    completed_items=map_state["completed_count"],
                    status="in-progress",
                )
                await self.host.publish_workflow_event(workflow_context, progress_data)

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
        merged_bytes = json.dumps({"results": results_list}).encode("utf-8")

        await save_artifact_with_metadata(
            artifact_service=self.host.artifact_service,
            app_name=self.host.workflow_name,
            user_id=workflow_context.a2a_context["user_id"],
            session_id=workflow_context.a2a_context["session_id"],
            filename=merged_artifact_name,
            content_bytes=merged_bytes,
            mime_type="application/json",
            metadata_dict={
                "description": f"Aggregated results from map node '{map_node_id}'",
                "source": "workflow_map_aggregate",
                "node_id": map_node_id,
            },
            timestamp=datetime.now(timezone.utc),
        )

        # Publish result event
        result_data = WorkflowNodeExecutionResultData(
            type="workflow_node_execution_result",
            node_id=map_node_id,
            status="success",
            output_artifact_ref=ArtifactRef(name=merged_artifact_name),
        )
        await self.host.publish_workflow_event(workflow_context, result_data)

        workflow_state.completed_nodes[map_node_id] = merged_artifact_name
        if map_node_id in workflow_state.pending_nodes:
            workflow_state.pending_nodes.remove(map_node_id)
        workflow_state.node_outputs[map_node_id] = {"output": {"results": results_list}}

        # Cleanup state
        del workflow_state.active_branches[map_node_id]
        del workflow_state.metadata[f"map_state_{map_node_id}"]

        await self.execute_workflow(workflow_state, workflow_context)
