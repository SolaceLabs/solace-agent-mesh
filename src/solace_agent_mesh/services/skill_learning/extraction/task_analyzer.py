"""
Task analyzer for extracting skill-relevant information from task executions.

This module analyzes completed task data to extract:
- Agent chains and delegation patterns
- Tool invocations and their parameters
- Success/failure patterns
- Complexity metrics
"""

import logging
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ToolInvocation:
    """Represents a single tool invocation."""
    agent_name: str
    tool_name: str
    parameters: Dict[str, Any]
    result: Optional[Any]
    success: bool
    timestamp: int
    sequence_number: int


@dataclass
class AgentExecution:
    """Represents an agent's execution in a task."""
    agent_name: str
    task_id: str
    parent_task_id: Optional[str]
    role: str  # orchestrator, specialist, leaf
    tools_used: List[str]
    delegated_to: List[str]
    tool_invocations: List[ToolInvocation]


@dataclass
class TaskAnalysis:
    """Result of analyzing a task execution."""
    task_id: str
    user_request: str
    success: bool
    agent_executions: List[AgentExecution]
    total_tool_calls: int
    total_agents: int
    complexity_score: int
    is_learnable: bool
    skip_reason: Optional[str]
    
    @property
    def tools_used(self) -> List[str]:
        """Get all unique tools used across all agent executions."""
        tools = set()
        for ae in self.agent_executions:
            tools.update(ae.tools_used)
        return list(tools)


class TaskAnalyzer:
    """
    Analyzes task execution data to extract skill-relevant information.
    
    This analyzer processes task events and tool invocations to build
    a structured representation suitable for skill extraction.
    """
    
    # Minimum requirements for a task to be learnable
    MIN_TOOL_CALLS = 1
    MAX_TOOL_CALLS = 50  # Too complex tasks are hard to generalize
    
    def __init__(
        self,
        min_tool_calls: int = 1,
        max_tool_calls: int = 50,
        exclude_agents: Optional[List[str]] = None,
        exclude_tools: Optional[List[str]] = None,
    ):
        """
        Initialize the task analyzer.
        
        Args:
            min_tool_calls: Minimum tool calls for learnable task
            max_tool_calls: Maximum tool calls for learnable task
            exclude_agents: Agents to exclude from analysis
            exclude_tools: Tools to exclude from analysis
        """
        self.min_tool_calls = min_tool_calls
        self.max_tool_calls = max_tool_calls
        self.exclude_agents = set(exclude_agents or [])
        self.exclude_tools = set(exclude_tools or [])
    
    def analyze_task(
        self,
        task_id: str,
        task_events: List[Dict[str, Any]],
        task_metadata: Optional[Dict[str, Any]] = None,
    ) -> TaskAnalysis:
        """
        Analyze a completed task to extract skill-relevant information.
        
        Args:
            task_id: The task ID
            task_events: List of task events
            task_metadata: Optional task metadata
            
        Returns:
            TaskAnalysis with extracted information
        """
        # Extract user request
        user_request = self._extract_user_request(task_events, task_metadata)
        
        # Determine task success
        success = self._determine_success(task_events, task_metadata)
        
        # Extract agent executions
        agent_executions = self._extract_agent_executions(task_events)
        
        # Calculate metrics
        total_tool_calls = sum(
            len(ae.tool_invocations) for ae in agent_executions
        )
        total_agents = len(agent_executions)
        complexity_score = self._calculate_complexity(
            agent_executions, total_tool_calls
        )
        
        # Determine if learnable
        is_learnable, skip_reason = self._check_learnability(
            success=success,
            total_tool_calls=total_tool_calls,
            agent_executions=agent_executions,
        )
        
        return TaskAnalysis(
            task_id=task_id,
            user_request=user_request,
            success=success,
            agent_executions=agent_executions,
            total_tool_calls=total_tool_calls,
            total_agents=total_agents,
            complexity_score=complexity_score,
            is_learnable=is_learnable,
            skip_reason=skip_reason,
        )
    
    def _extract_user_request(
        self,
        task_events: List[Dict[str, Any]],
        task_metadata: Optional[Dict[str, Any]],
    ) -> str:
        """Extract the original user request."""
        # Try metadata first
        if task_metadata and "user_request" in task_metadata:
            return task_metadata["user_request"]
        
        # Look for initial message event
        for event in task_events:
            event_type = event.get("event_type", event.get("type", ""))
            if event_type in ("user_message", "task_start", "message"):
                content = event.get("content", event.get("data", {}).get("content", ""))
                if content:
                    return content
        
        return ""
    
    def _determine_success(
        self,
        task_events: List[Dict[str, Any]],
        task_metadata: Optional[Dict[str, Any]],
    ) -> bool:
        """Determine if the task was successful."""
        # Check metadata
        if task_metadata:
            if "success" in task_metadata:
                return task_metadata["success"]
            if "status" in task_metadata:
                return task_metadata["status"] in ("completed", "success")
        
        # Look for completion event
        for event in reversed(task_events):
            event_type = event.get("event_type", event.get("type", ""))
            if event_type in ("task_complete", "task_completed", "completion"):
                return event.get("success", True)
            if event_type in ("task_failed", "error"):
                return False
        
        # Default to success if no explicit failure
        return True
    
    def _extract_agent_executions(
        self,
        task_events: List[Dict[str, Any]],
    ) -> List[AgentExecution]:
        """Extract agent execution information from events."""
        # Group events by agent
        agent_events: Dict[str, List[Dict[str, Any]]] = {}
        agent_task_ids: Dict[str, str] = {}
        agent_parent_ids: Dict[str, Optional[str]] = {}
        
        for event in task_events:
            agent_name = event.get("agent_name", event.get("agent"))
            
            # Skip events without an agent name (e.g., user_message, task_complete)
            if not agent_name:
                continue
            
            if agent_name in self.exclude_agents:
                continue
            
            if agent_name not in agent_events:
                agent_events[agent_name] = []
                agent_task_ids[agent_name] = event.get("task_id", "")
                agent_parent_ids[agent_name] = event.get("parent_task_id")
            
            agent_events[agent_name].append(event)
        
        # Build agent executions
        executions = []
        for agent_name, events in agent_events.items():
            tool_invocations = self._extract_tool_invocations(agent_name, events)
            tools_used = list(set(ti.tool_name for ti in tool_invocations))
            delegated_to = self._extract_delegations(events)
            
            # Determine role
            if delegated_to:
                role = "orchestrator"
            elif agent_parent_ids.get(agent_name):
                role = "specialist"
            else:
                role = "leaf"
            
            executions.append(AgentExecution(
                agent_name=agent_name,
                task_id=agent_task_ids.get(agent_name, ""),
                parent_task_id=agent_parent_ids.get(agent_name),
                role=role,
                tools_used=tools_used,
                delegated_to=delegated_to,
                tool_invocations=tool_invocations,
            ))
        
        return executions
    
    def _extract_tool_invocations(
        self,
        agent_name: str,
        events: List[Dict[str, Any]],
    ) -> List[ToolInvocation]:
        """Extract tool invocations from agent events."""
        invocations = []
        sequence = 0
        
        for event in events:
            event_type = event.get("event_type", event.get("type", ""))
            
            if event_type in ("tool_call", "tool_invocation", "tool_start"):
                tool_name = event.get("tool_name", event.get("name", ""))
                
                if tool_name in self.exclude_tools:
                    continue
                
                invocations.append(ToolInvocation(
                    agent_name=agent_name,
                    tool_name=tool_name,
                    parameters=event.get("parameters", event.get("args", {})),
                    result=event.get("result"),
                    success=event.get("success", True),
                    timestamp=event.get("timestamp", 0),
                    sequence_number=sequence,
                ))
                sequence += 1
        
        return invocations
    
    def _extract_delegations(
        self,
        events: List[Dict[str, Any]],
    ) -> List[str]:
        """Extract agent delegations from events."""
        delegations = []
        
        for event in events:
            event_type = event.get("event_type", event.get("type", ""))
            
            if event_type in ("delegation", "peer_delegation", "agent_call"):
                target = event.get("target_agent", event.get("delegated_to", ""))
                if target and target not in delegations:
                    delegations.append(target)
        
        return delegations
    
    def _calculate_complexity(
        self,
        agent_executions: List[AgentExecution],
        total_tool_calls: int,
    ) -> int:
        """
        Calculate a complexity score for the task.
        
        Score is based on:
        - Number of agents involved
        - Number of tool calls
        - Depth of delegation chain
        """
        num_agents = len(agent_executions)
        
        # Calculate delegation depth
        max_depth = 0
        for ae in agent_executions:
            depth = 0
            current = ae
            while current.parent_task_id:
                depth += 1
                # Find parent agent
                parent = next(
                    (a for a in agent_executions if a.task_id == current.parent_task_id),
                    None
                )
                if parent:
                    current = parent
                else:
                    break
            max_depth = max(max_depth, depth)
        
        # Complexity formula
        complexity = (
            num_agents * 10 +
            total_tool_calls * 2 +
            max_depth * 5
        )
        
        return min(100, complexity)  # Cap at 100
    
    def _check_learnability(
        self,
        success: bool,
        total_tool_calls: int,
        agent_executions: List[AgentExecution],
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if a task is suitable for learning.
        
        Returns:
            Tuple of (is_learnable, skip_reason)
        """
        if not success:
            return False, "Task was not successful"
        
        if total_tool_calls < self.min_tool_calls:
            return False, f"Too few tool calls ({total_tool_calls} < {self.min_tool_calls})"
        
        if total_tool_calls > self.max_tool_calls:
            return False, f"Too many tool calls ({total_tool_calls} > {self.max_tool_calls})"
        
        if not agent_executions:
            return False, "No agent executions found"
        
        # Check for excluded agents
        all_excluded = all(
            ae.agent_name in self.exclude_agents
            for ae in agent_executions
        )
        if all_excluded:
            return False, "All agents are excluded"
        
        return True, None
    
    def get_primary_agent(
        self,
        analysis: TaskAnalysis,
    ) -> Optional[str]:
        """
        Get the primary agent for a task.
        
        The primary agent is typically the orchestrator or the
        first agent in the execution chain.
        """
        if not analysis.agent_executions:
            return None
        
        # Look for orchestrator
        for ae in analysis.agent_executions:
            if ae.role == "orchestrator":
                return ae.agent_name
        
        # Return first agent without parent
        for ae in analysis.agent_executions:
            if not ae.parent_task_id:
                return ae.agent_name
        
        # Fallback to first agent
        return analysis.agent_executions[0].agent_name