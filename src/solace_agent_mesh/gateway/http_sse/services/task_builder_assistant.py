"""
AI Assistant for Scheduled Task Builder.
Manages conversational scheduled task creation through natural language.
"""

import json
import logging
import re
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from litellm import acompletion
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class TaskBuilderResponse(BaseModel):
    """Response from the task builder assistant."""
    message: str
    task_updates: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(ge=0.0, le=1.0)
    ready_to_save: bool = False


class TaskBuilderAssistant:
    """
    AI assistant for scheduled task creation.
    Manages conversation flow and task configuration generation.
    """
    
    SYSTEM_PROMPT = """You are an AI assistant helping users create scheduled tasks with natural language.

CRITICAL RULES:
1. You MUST respond with valid JSON in this exact format - NO EXCEPTIONS
2. You MUST always include a "message" field with a helpful, conversational response
3. NEVER respond with just "I understand" - always provide actionable guidance
4. Help users define: task name, description, schedule (cron/interval), target agent, and task message
5. For schedules, suggest common patterns or help convert natural language to cron expressions
6. ONLY suggest agents from the available_agents list provided in the context
7. If user requests an agent not in the list, suggest the closest match or ask for clarification

RESPONSE FORMAT (REQUIRED):
{{
  "message": "your conversational response here - MUST be helpful and specific",
  "task_updates": {{
    "name": "Task Name",
    "description": "Task description",
    "schedule_type": "cron|interval|one_time",
    "schedule_expression": "cron expression or interval",
    "target_agent_name": "AgentName",
    "task_message": "Message to send to agent",
    "timezone": "UTC"
  }},
  "confidence": 0.0-1.0,
  "ready_to_save": false
}}

SCHEDULE PATTERNS:
- Daily at specific time: "0 9 * * *" (9 AM daily)
- Weekly on specific days: "0 9 * * 1,3,5" (Mon, Wed, Fri at 9 AM)
- Monthly: "0 9 1 * *" (1st of month at 9 AM)
- Hourly: "0 * * * *" (every hour)
- Every X hours: "0 */6 * * *" (every 6 hours)
- Interval: "30m", "1h", "2h" (for interval type)

EXAMPLES:

Example 1: Daily Report
User: "I need a task to generate a daily report"
{{
  "message": "Great! I'll help you create a daily report task. What time would you like the report generated? And what should the report include?",
  "task_updates": {{
    "name": "Daily Report Generation",
    "schedule_type": "cron",
    "target_agent_name": "OrchestratorAgent"
  }},
  "confidence": 0.6,
  "ready_to_save": false
}}

User: "Every morning at 9 AM, summarize yesterday's activities"
{{
  "message": "Perfect! I've configured a daily task that runs at 9 AM to summarize yesterday's activities. Check the preview!",
  "task_updates": {{
    "name": "Daily Activity Report",
    "description": "Generate summary of previous day's activities",
    "schedule_type": "cron",
    "schedule_expression": "0 9 * * *",
    "target_agent_name": "OrchestratorAgent",
    "task_message": "Generate a comprehensive summary of yesterday's activities and key metrics",
    "timezone": "UTC"
  }},
  "confidence": 0.9,
  "ready_to_save": true
}}

Example 2: Monitoring Task
User: "Create a monitoring task that checks system health every 30 minutes"
{{
  "message": "I'll create a monitoring task that runs every 30 minutes. What specific health checks should it perform?",
  "task_updates": {{
    "name": "System Health Monitor",
    "schedule_type": "interval",
    "schedule_expression": "30m",
    "target_agent_name": "OrchestratorAgent"
  }},
  "confidence": 0.7,
  "ready_to_save": false
}}

User: "Check API endpoints, database connections, and disk space"
{{
  "message": "Excellent! I've configured a monitoring task that checks API endpoints, database connections, and disk space every 30 minutes.",
  "task_updates": {{
    "name": "System Health Monitor",
    "description": "Monitor system health metrics every 30 minutes",
    "schedule_type": "interval",
    "schedule_expression": "30m",
    "target_agent_name": "OrchestratorAgent",
    "task_message": "Perform health check: verify API endpoints are responding, check database connections are active, and monitor disk space usage. Alert if any issues detected.",
    "timezone": "UTC"
  }},
  "confidence": 0.9,
  "ready_to_save": true
}}

Example 3: Weekly Cleanup
User: "I want to clean up old data every Sunday"
{{
  "message": "I'll set up a weekly cleanup task for Sundays. What time should it run, and what data needs to be cleaned up?",
  "task_updates": {{
    "name": "Weekly Data Cleanup",
    "schedule_type": "cron",
    "schedule_expression": "0 2 * * 0",
    "target_agent_name": "OrchestratorAgent"
  }},
  "confidence": 0.7,
  "ready_to_save": false
}}

User: "At 2 AM, delete logs older than 30 days and archive completed tasks"
{{
  "message": "Perfect! Your weekly cleanup task is configured to run every Sunday at 2 AM.",
  "task_updates": {{
    "name": "Weekly Data Cleanup",
    "description": "Clean up old logs and archive completed tasks",
    "schedule_type": "cron",
    "schedule_expression": "0 2 * * 0",
    "target_agent_name": "OrchestratorAgent",
    "task_message": "Perform weekly cleanup: delete log files older than 30 days and archive all completed tasks to long-term storage",
    "timezone": "UTC"
  }},
  "confidence": 0.9,
  "ready_to_save": true
}}

REMEMBER:
- Ask clarifying questions to understand the task requirements
- Help convert natural language schedules to cron expressions
- Suggest appropriate schedule types (cron for recurring, interval for fixed intervals)
- Set ready_to_save to true when all required fields are complete
- Be conversational and helpful
"""
    
    def __init__(self, db: Optional[Session] = None, model_config: Optional[Dict[str, Any]] = None):
        """Initialize the assistant with model configuration."""
        self.system_prompt = self.SYSTEM_PROMPT
        self.db = db
        
        # Get LLM configuration
        if not model_config or not isinstance(model_config, dict):
            raise ValueError("model_config is required and must be a dictionary")
        
        if not model_config.get("model"):
            raise ValueError("model_config must contain 'model' key")
        
        self.model = model_config.get("model")
        self.api_base = model_config.get("api_base")
        self.api_key = model_config.get("api_key", "dummy")
    
    async def process_message(
        self,
        user_message: str,
        conversation_history: List[Dict[str, str]],
        current_task: Dict[str, Any],
        user_id: Optional[str] = None,
        available_agents: Optional[List[str]] = None
    ) -> TaskBuilderResponse:
        """
        Process user message and update task configuration using LLM.
        
        Args:
            user_message: The user's message
            conversation_history: Previous conversation messages
            current_task: Current task configuration
            user_id: Optional user ID for context
            available_agents: List of available agent names
            
        Returns:
            TaskBuilderResponse with updates
        """
        try:
            return await self._llm_response(
                user_message,
                conversation_history,
                current_task,
                user_id,
                available_agents
            )
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            return TaskBuilderResponse(
                message="I encountered an error. Could you please rephrase that?",
                confidence=0.0,
                ready_to_save=False
            )
    
    async def _llm_response(
        self,
        user_message: str,
        conversation_history: List[Dict[str, str]],
        current_task: Dict[str, Any],
        user_id: Optional[str] = None,
        available_agents: Optional[List[str]] = None
    ) -> TaskBuilderResponse:
        """Use LLM to generate response and task updates."""
        
        # Build messages for LLM
        messages = [
            {"role": "system", "content": self.system_prompt}
        ]
        
        # Add conversation history
        messages.extend(conversation_history)
        
        # Add current message with task context and available agents
        task_context = f"\n\nCurrent Task Configuration:\n{json.dumps(current_task, indent=2)}"
        
        if available_agents:
            agents_context = f"\n\nAvailable Agents (ONLY use these):\n{json.dumps(available_agents, indent=2)}"
            task_context += agents_context
        
        messages.append({
            "role": "user",
            "content": user_message + task_context
        })
        
        # Call LLM with JSON mode
        try:
            completion_args = {
                "model": self.model,
                "messages": messages,
                "response_format": {"type": "json_object"},
                "temperature": 0.1,  # Low temperature for consistency
            }
            
            if self.api_base:
                completion_args["api_base"] = self.api_base
            if self.api_key:
                completion_args["api_key"] = self.api_key
            
            response = await acompletion(**completion_args)
            
            # Parse response
            content = response.choices[0].message.content
            logger.info(f"LLM Response: {content}")
            
            try:
                parsed = json.loads(content)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM response as JSON: {e}")
                logger.error(f"Response content: {content}")
                # Try to extract JSON from response
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    parsed = json.loads(json_match.group())
                else:
                    raise
            
            # Handle nested response structure
            if "response" in parsed and isinstance(parsed["response"], dict):
                logger.info("Unwrapping nested 'response' structure from LLM")
                parsed = parsed["response"]
            
            # Validate message
            message = parsed.get("message", "")
            if not message or message.strip().lower() in ["i understand", "i understand.", "ok", "okay"]:
                logger.warning(f"LLM returned generic/empty message: '{message}'")
                message = "I'll help you create that scheduled task. Could you provide more details about when it should run and what it should do?"
            
            return TaskBuilderResponse(
                message=message,
                task_updates=parsed.get("task_updates", {}),
                confidence=parsed.get("confidence", 0.5),
                ready_to_save=parsed.get("ready_to_save", False)
            )
            
        except Exception as e:
            logger.error(f"LLM call failed: {e}", exc_info=True)
            # Fallback response
            return TaskBuilderResponse(
                message="I'm having trouble processing that. Could you describe what you'd like this scheduled task to do? For example, what should it do and when should it run?",
                confidence=0.3,
                ready_to_save=False
            )
    
    def get_initial_greeting(self) -> TaskBuilderResponse:
        """Get the initial greeting message."""
        return TaskBuilderResponse(
            message="Hi! I'll help you create a scheduled task. You can either:\n\n"
                   "1. Describe what you want to automate (e.g., 'Generate a daily report at 9 AM')\n"
                   "2. Tell me about a recurring task you need to schedule\n\n"
                   "What would you like to create?",
            confidence=1.0,
            ready_to_save=False
        )