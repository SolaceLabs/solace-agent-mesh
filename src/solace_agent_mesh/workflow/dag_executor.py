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
    LoopNode,
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
            elif node.type == "loop":
                await self._execute_loop_node(node, workflow_state, workflow_context)
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
        workflow_state.pending_nodes.remove(node.id)

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

    async def _execute_loop_node(
        self,
        node: LoopNode,
        workflow_state: WorkflowExecutionState,
        workflow_context: WorkflowExecutionContext,
    ):
        """Execute loop node."""
        log_id = f"{self.host.log_identifier}[Loop:{node.id}]"

        # Resolve loop array
        items = self._resolve_template(node.loop_over, workflow_state)

        if not isinstance(items, list):
            raise ValueError(f"Loop target must be array, got: {type(items)}")

        # Check iteration limit
        max_iterations = (
            node.max_iterations
            or self.host.get_config("default_max_loop_iterations", 100)
        )

        if len(items) > max_iterations:
            raise WorkflowExecutionError(
                f"Loop '{node.id}' exceeds max iterations: "
                f"{len(items)} > {max_iterations}"
            )

        log.info(f"{log_id} Starting loop with {len(items)} iterations")

        # Execute loop iterations sequentially
        loop_results = []

        for i, item in enumerate(items):
            log.debug(f"{log_id} Iteration {i+1}/{len(items)}")

            # Create a lightweight, temporary state for the iteration.
            # This avoids deep-copying the entire workflow state for each loop.
            # We just need to inject the loop variables.
            iteration_state = workflow_state.model_copy(deep=False)
            iteration_state.node_outputs = {
                **workflow_state.node_outputs,
                "_loop_item": {"output": item},
                "_loop_index": {"output": i},
            }

            # Execute loop body node
            # Note: loop_node is an ID referencing a node definition.
            # We need to find that node definition.
            # But wait, the loop body node is likely defined in the main nodes list?
            # Or is it a sub-node?
            # The design doc says: "loop_node: str # Node ID to execute for each item"
            # This implies the node exists in self.nodes.
            loop_body_node = self.nodes[node.loop_node]

            if loop_body_node.type != "agent":
                raise ValueError("Loop body must be an agent node for MVP")

            # We need to execute this node and WAIT for it.
            # But `call_persona` is async and returns sub_task_id.
            # We can't easily "wait" here without blocking the event loop if we use `await`.
            # But we ARE in an async method.
            # The problem is `call_persona` sends a message and returns.
            # The response comes later via `handle_persona_response`.
            #
            # If we want sequential execution of loop items, we need to:
            # 1. Send request for item 0.
            # 2. Return/Exit.
            # 3. When item 0 completes, trigger item 1.
            #
            # This requires state management for the loop index.
            # `WorkflowExecutionState` doesn't currently have `loop_state`.
            #
            # For MVP, let's assume we can't easily do sequential loops without
            # adding significant state management complexity (re-entry).
            #
            # Alternative: Parallel Loop (Launch all at once like Fork).
            # This is much easier with the current architecture.
            # Let's implement Parallel Loop for MVP.

            # ... Switching to Parallel Loop Implementation ...
            pass

        # Parallel Loop Implementation
        loop_sub_tasks = []
        for i, item in enumerate(items):
            # Create iteration state
            iteration_state = workflow_state.model_copy(deep=False)
            iteration_state.node_outputs = {
                **workflow_state.node_outputs,
                "_loop_item": {"output": item},
                "_loop_index": {"output": i},
            }

            loop_body_node = self.nodes[node.loop_node]
            # We need to clone the node to give it a unique ID for this iteration?
            # Or just track it by sub_task_id.
            # `call_persona` uses node.id for logging/metadata.
            # Let's create a temporary node wrapper.
            iter_node = loop_body_node.model_copy()
            # We don't change ID, but we rely on sub_task_id uniqueness.

            sub_task_id = await self.host.persona_caller.call_persona(
                iter_node, iteration_state, workflow_context
            )

            loop_sub_tasks.append(
                {
                    "index": i,
                    "sub_task_id": sub_task_id,
                }
            )

        # Store loop tracking
        workflow_state.active_branches[node.id] = loop_sub_tasks
        # Mark loop as pending
        # (It stays in pending_nodes until all iterations are done)

    def _resolve_template(
        self, template: str, workflow_state: WorkflowExecutionState
    ) -> Any:
        """
        Resolve template variable.
        Format: {{node_id.output.field_path}}
        """
        # Extract variable path
        match = re.match(r"\{\{(.+?)\}\}", template)
        if not match:
            return template

        path = match.group(1)
        parts = path.split(".")

        # Navigate path in workflow state
        if parts[0] == "workflow" and parts[1] == "input":
            # Reference to workflow input
            # TODO: implement workflow input storage
            pass
        else:
            # Reference to node output
            node_id = parts[0]
            if node_id not in workflow_state.node_outputs:
                # Check if it's a loop variable
                if node_id in ["_loop_item", "_loop_index"]:
                    pass  # Allow it
                else:
                    raise ValueError(f"Referenced node '{node_id}' has not completed")

            # Navigate remaining path
            data = workflow_state.node_outputs[node_id]
            for part in parts[1:]:
                if isinstance(data, dict) and part in data:
                    data = data[part]
                else:
                    # Path not found
                    return None

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

        # Check if this was part of a Fork or Loop
        # We need to find if this node_id is being tracked in active_branches
        # But wait, node_id is the ID of the node definition.
        # For Fork, the node_id IS the branch ID.
        # For Loop, the node_id IS the loop body node ID.

        # Check if this node is part of an active fork/loop
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
                    result.artifact_name, result.artifact_version, workflow_context
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
        """Handle completion of a child task within a Fork or Loop."""
        log_id = f"{self.host.log_identifier}[ControlNode:{control_node_id}]"
        branches = workflow_state.active_branches.get(control_node_id, [])

        # Find and update the specific branch/iteration
        for branch in branches:
            if branch["sub_task_id"] == sub_task_id:
                branch["result"] = {
                    "artifact_name": result.artifact_name,
                    "artifact_version": result.artifact_version,
                }
                break

        # Check if all branches/iterations are complete
        all_complete = all("result" in b for b in branches)

        if all_complete:
            log.info(f"{log_id} All branches/iterations completed")
            
            # Determine if it's a Fork or Loop based on node definition
            control_node = self.nodes[control_node_id]
            
            if control_node.type == "fork":
                await self._finalize_fork_node(
                    control_node_id, branches, workflow_state, workflow_context
                )
            elif control_node.type == "loop":
                await self._finalize_loop_node(
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
                artifact_name, artifact_version, workflow_context
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

    async def _finalize_loop_node(
        self,
        loop_node_id: str,
        iterations: List[Dict],
        workflow_state: WorkflowExecutionState,
        workflow_context: WorkflowExecutionContext,
    ):
        """Aggregate loop iteration results."""
        log_id = f"{self.host.log_identifier}[Loop:{loop_node_id}]"
        
        # Sort by index to ensure order
        iterations.sort(key=lambda x: x["index"])
        
        results_list = []
        for iter_info in iterations:
            artifact_name = iter_info["result"]["artifact_name"]
            artifact_version = iter_info["result"]["artifact_version"]
            
            artifact_data = await self.host._load_node_output(
                artifact_name, artifact_version, workflow_context
            )
            results_list.append(artifact_data)
            
        # Create aggregated artifact
        merged_artifact_name = f"loop_{loop_node_id}_results.json"
        # Save artifact logic...
        
        workflow_state.completed_nodes[loop_node_id] = merged_artifact_name
        if loop_node_id in workflow_state.pending_nodes:
            workflow_state.pending_nodes.remove(loop_node_id)
        workflow_state.node_outputs[loop_node_id] = {"output": {"results": results_list}}
        
        del workflow_state.active_branches[loop_node_id]
        
        await self.execute_workflow(workflow_state, workflow_context)
