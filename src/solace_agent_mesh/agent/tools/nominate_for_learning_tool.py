"""
Nominate for Learning Tool.

This tool allows agents to explicitly nominate the current task for skill learning
when they determine it represents a reusable pattern worth learning.
"""

import logging
import time
from typing import TYPE_CHECKING, Any, Dict, Optional

from google.adk.tools import FunctionTool
from google.adk.tools.base_tool import BaseTool

if TYPE_CHECKING:
    from ..sac.component import SamAgentComponent

log = logging.getLogger(__name__)

# Topic pattern for nominating tasks for learning
LEARNING_NOMINATION_TOPIC_TEMPLATE = "sam/{agent_name}/task/nominate-for-learning"


def create_nominate_for_learning_tool(host_component: "SamAgentComponent") -> BaseTool:
    """
    Create a tool that allows the agent to nominate the current task for skill learning.
    
    Args:
        host_component: The host component instance
        
    Returns:
        A FunctionTool for nominating tasks for learning
    """
    
    def nominate_for_learning(
        skill_name: str,
        skill_description: str,
        reason: str,
    ) -> Dict[str, Any]:
        """
        Nominate the current task for skill learning.
        
        Use this tool when you've successfully completed a task that represents a 
        reusable pattern that could help with similar future requests. Good candidates
        for learning are tasks that:
        - Involve multiple steps or tool calls
        - Follow a clear, repeatable procedure
        - Could be useful for other users with similar needs
        - Demonstrate a workflow that isn't already captured in existing skills
        
        Do NOT nominate tasks that are:
        - Simple, single-step operations
        - Highly specific to one user's unique situation
        - Already covered by existing skills
        - Failed or incomplete
        
        Args:
            skill_name: A short, descriptive name for the skill (e.g., "Create Sales Report", 
                       "Deploy to Production", "Analyze Customer Feedback")
            skill_description: A brief description of what this skill does and when to use it
            reason: Why this task is worth learning - what makes it reusable?
            
        Returns:
            Confirmation that the task has been nominated for learning
        """
        try:
            # Get context from the component
            agent_name = host_component.get_config("agent_name")
            
            # We need to get the current task context
            # This is tricky because we're in a tool call, not in the finalization
            # We'll use the active_tasks to find the current task
            current_task_id = None
            current_a2a_context = None
            
            with host_component.active_tasks_lock:
                # Find the most recent active task (there should typically be one)
                for task_id, task_context in host_component.active_tasks.items():
                    current_task_id = task_id
                    current_a2a_context = task_context.a2a_context if hasattr(task_context, 'a2a_context') else {}
                    break
            
            if not current_task_id:
                log.warning(
                    "[NominateForLearning] No active task found, cannot nominate"
                )
                return {
                    "status": "error",
                    "message": "No active task found to nominate for learning"
                }
            
            # Build the nomination topic
            topic = LEARNING_NOMINATION_TOPIC_TEMPLATE.format(agent_name=agent_name)
            
            # Build the nomination payload with the agent's reasoning
            nomination_payload = {
                "task_id": current_task_id,
                "agent_name": agent_name,
                "user_id": current_a2a_context.get("user_id") if current_a2a_context else None,
                "session_id": current_a2a_context.get("session_id") if current_a2a_context else None,
                "timestamp": time.time(),
                "nomination_reason": "agent_tool_call",  # Distinguishes from automatic nomination
                "skill_suggestion": {
                    "name": skill_name,
                    "description": skill_description,
                    "reason": reason,
                },
                "metadata": {
                    "context_id": current_a2a_context.get("contextId") if current_a2a_context else None,
                    "client_id": current_a2a_context.get("client_id") if current_a2a_context else None,
                    "gateway_id": current_a2a_context.get("gateway_id") if current_a2a_context else None,
                },
            }
            
            # Publish to broker
            host_component.publish_a2a_message(
                payload=nomination_payload,
                topic=topic,
            )
            
            log.info(
                "[NominateForLearning] Published learning nomination to %s for task %s (skill: %s)",
                topic,
                current_task_id,
                skill_name,
            )
            
            return {
                "status": "success",
                "message": f"Task nominated for learning as skill '{skill_name}'",
                "task_id": current_task_id,
                "skill_name": skill_name,
            }
            
        except Exception as e:
            log.error(
                "[NominateForLearning] Failed to nominate task for learning: %s",
                e,
            )
            return {
                "status": "error",
                "message": f"Failed to nominate task for learning: {str(e)}"
            }
    
    # Create the FunctionTool
    tool = FunctionTool(func=nominate_for_learning)
    tool.origin = "builtin"
    
    return tool


def get_nominate_for_learning_instruction() -> str:
    """
    Get the system prompt instruction for the nominate_for_learning tool.
    
    Returns:
        Instruction text to add to the system prompt
    """
    return """\
## Skill Learning

You have access to a `nominate_for_learning` tool that allows you to nominate successful tasks 
for the skill learning system. When you complete a task that represents a reusable pattern, 
you can nominate it so the system can learn from it and help with similar future requests.

### When to Nominate a Task for Learning

**Good candidates for learning:**
- Tasks involving multiple steps or tool calls that follow a clear procedure
- Workflows that could benefit other users with similar needs
- Complex operations that you successfully completed
- Tasks that demonstrate best practices or efficient approaches

**Do NOT nominate:**
- Simple, single-step operations (e.g., "what time is it?")
- Tasks that failed or were incomplete
- Highly specific requests that won't generalize to other users
- Tasks already covered by existing skills
- Trivial queries or basic information lookups

### How to Use

After successfully completing a task that meets the criteria above, call:

```
nominate_for_learning(
    skill_name="Short descriptive name",
    skill_description="What this skill does and when to use it",
    reason="Why this task is worth learning"
)
```

### Examples

**Good nomination:**
```
nominate_for_learning(
    skill_name="Generate Monthly Sales Report",
    skill_description="Creates a comprehensive monthly sales report by querying the database, aggregating data by region, and generating visualizations",
    reason="This is a common request that involves multiple data sources and a repeatable workflow"
)
```

**Bad nomination (don't do this):**
```
nominate_for_learning(
    skill_name="Answer Question",
    skill_description="Answered a simple question",
    reason="User asked a question"
)
```

Use your judgment to identify truly valuable patterns worth learning.
"""