"""
AI Assistant for Prompt Template Builder.
Manages conversational prompt template creation through natural language.
"""

import json
import logging
import os
import re
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from litellm import acompletion
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class PromptBuilderResponse(BaseModel):
    """Response from the prompt builder assistant."""
    message: str
    template_updates: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(ge=0.0, le=1.0)
    ready_to_save: bool = False


class PromptBuilderAssistant:
    """
    AI assistant for prompt template creation.
    Manages conversation flow and template generation.
    """
    
    SYSTEM_PROMPT = """You are an AI assistant helping users create reusable prompt templates.

CRITICAL RULES:
1. You MUST respond with valid JSON in this exact format - NO EXCEPTIONS
2. You MUST always include a "message" field with a helpful, conversational response
3. NEVER respond with just "I understand" - always provide actionable guidance
4. ONLY create placeholders for DATA that changes (names, paths, dates, numbers, specific values)
5. Keep instructions, steps, requirements, and process descriptions as FIXED TEXT
6. Use descriptive variable names in Title Case (e.g., {{File Path}}, {{Module Name}})
7. Suggest appropriate categories (Development, Analysis, Documentation, Communication, Testing, etc.)
8. Generate short command names (lowercase, hyphens only)

RESPONSE FORMAT (REQUIRED):
{{
  "message": "your conversational response here - MUST be helpful and specific",
  "template_updates": {{
    "name": "Name",
    "category": "Category",
    "command": "command-name",
    "promptText": "Template with {{placeholders}} for variable data only",
    "description": "Brief description"
  }},
  "confidence": 0.0-1.0,
  "ready_to_save": false
}}

VARIABLE PLACEHOLDER RULES:
- Use {{Variable Name}} format for placeholders (Title Case with spaces)
- ONLY for data that changes: file paths, names, dates, numbers, specific values
- NOT for instructions, steps, or requirements
- Use descriptive names: {{File Path}}, {{Module Name}}, {{Task Description}}

EXAMPLES:

Example 1: Code Review Template
User: "I need a template for code reviews"
{{
  "message": "Great! I'll create a code review template. What information changes each time you do a code review? For example: file path, module name, specific concerns?",
  "template_updates": {{
    "name": "Code Review Template",
    "category": "Development"
  }},
  "confidence": 0.6,
  "ready_to_save": false
}}

User: "The file path, module name, and specific security concerns"
{{
  "message": "Perfect! I've created a code review template with placeholders for file path, module name, and security concerns. Check the preview on the left!",
  "template_updates": {{
    "name": "Code Review Template",
    "category": "Development",
    "command": "code-review",
    "promptText": "Review the {{Module Name}} module located at {{File Path}}.\\n\\nPlease perform a comprehensive code review focusing on:\\n1. Security vulnerabilities\\n2. Error handling\\n3. Code quality and best practices\\n4. Specific attention to: {{Security Concerns}}\\n\\nProvide a detailed report with:\\n- List of issues with severity levels\\n- Specific code snippets that need attention\\n- Recommendations for improvements",
    "description": "Template for code review with security focus"
  }},
  "confidence": 0.9,
  "ready_to_save": true
}}

Example 2: Bug Report Template
User: "Create a bug report template"
{{
  "message": "I'll create a bug report template! What details vary for each bug report? For example: bug description, steps to reproduce, expected vs actual behavior?",
  "template_updates": {{
    "name": "Bug Report Template",
    "category": "Testing"
  }},
  "confidence": 0.6,
  "ready_to_save": false
}}

User: "Bug description, steps to reproduce, and environment details"
{{
  "message": "Excellent! I've created a bug report template with those placeholders. You can see it in the preview!",
  "template_updates": {{
    "name": "Bug Report Template",
    "category": "Testing",
    "command": "bug-report",
    "promptText": "# Bug Report\\n\\n## Description\\n{{Bug Description}}\\n\\n## Steps to Reproduce\\n{{Steps To Reproduce}}\\n\\n## Environment\\n{{Environment Details}}\\n\\n## Expected Behavior\\nDescribe what should happen\\n\\n## Actual Behavior\\nDescribe what actually happens\\n\\n## Additional Context\\nAny other relevant information",
    "description": "Template for reporting bugs with structured format"
  }},
  "confidence": 0.9,
  "ready_to_save": true
}}

REMEMBER:
- Ask clarifying questions to understand what data changes
- Create detailed, useful templates
- Only use placeholders for variable data
- Keep instructions and structure as fixed text
- Set ready_to_save to true when template is complete
"""
    
    def __init__(self, db: Optional[Session] = None, model_config: Optional[Dict[str, Any]] = None):
        """Initialize the assistant with model configuration from component config."""
        self.system_prompt = self.SYSTEM_PROMPT
        self.db = db
        
        # Get LLM configuration from provided config
        if not model_config or not isinstance(model_config, dict):
            raise ValueError("model_config is required and must be a dictionary")
        
        if not model_config.get("model"):
            raise ValueError("model_config must contain 'model' key")
        
        self.model = model_config.get("model")
        self.api_base = model_config.get("api_base")
        self.api_key = model_config.get("api_key", "dummy")
    
    def _get_existing_commands(self, user_id: str) -> List[str]:
        """Get list of existing command shortcuts to avoid conflicts."""
        if not self.db:
            return []
        
        try:
            from ..repository.models import PromptGroupModel
            
            groups = self.db.query(PromptGroupModel).filter(
                PromptGroupModel.user_id == user_id,
                PromptGroupModel.command.isnot(None)
            ).all()
            
            return [group.command for group in groups if group.command]
        except Exception as e:
            logger.error(f"Error fetching existing commands: {e}")
            return []
    
    async def process_message(
        self,
        user_message: str,
        conversation_history: List[Dict[str, str]],
        current_template: Dict[str, Any],
        user_id: Optional[str] = None
    ) -> PromptBuilderResponse:
        """
        Process user message and update template using LLM.
        
        Args:
            user_message: The user's message
            conversation_history: Previous conversation messages
            current_template: Current template configuration
            
        Returns:
            PromptBuilderResponse with updates
        """
        try:
            return await self._llm_response(
                user_message,
                conversation_history,
                current_template,
                user_id
            )
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            return PromptBuilderResponse(
                message="I encountered an error. Could you please rephrase that?",
                confidence=0.0,
                ready_to_save=False
            )
    
    async def _llm_response(
        self,
        user_message: str,
        conversation_history: List[Dict[str, str]],
        current_template: Dict[str, Any],
        user_id: Optional[str] = None
    ) -> PromptBuilderResponse:
        """Use LLM to generate response and template updates."""
        
        # Get existing commands to avoid conflicts
        existing_commands = []
        if user_id and self.db:
            existing_commands = self._get_existing_commands(user_id)
        
        # Build messages for LLM
        messages = [
            {"role": "system", "content": self.system_prompt}
        ]
        
        # Add conversation history
        messages.extend(conversation_history)
        
        # Add current message with template context and existing commands
        template_context = f"\n\nCurrent Template:\n{json.dumps(current_template, indent=2)}"
        
        commands_context = ""
        if existing_commands:
            commands_context = f"\n\nEXISTING COMMANDS (avoid these):\n{', '.join(['/' + cmd for cmd in existing_commands])}"
        
        messages.append({
            "role": "user",
            "content": user_message + template_context + commands_context
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
            
            # Handle nested response structure (some LLMs wrap in various keys)
            if "response" in parsed and isinstance(parsed["response"], dict):
                logger.info("Unwrapping nested 'response' structure from LLM")
                parsed = parsed["response"]
            
            # Handle case where LLM wraps response in an arbitrary key (e.g., "{}", "result", etc.)
            # If we don't have a "message" key but have exactly one key with a dict value containing "message"
            if "message" not in parsed and len(parsed) == 1:
                single_key = list(parsed.keys())[0]
                if isinstance(parsed[single_key], dict) and "message" in parsed[single_key]:
                    logger.info(f"Unwrapping nested structure from key '{single_key}'")
                    parsed = parsed[single_key]
            
            # Validate that we have a proper message
            message = parsed.get("message", "")
            if not message or message.strip().lower() in ["i understand", "i understand.", "ok", "okay"]:
                logger.warning(f"LLM returned generic/empty message: '{message}'")
                message = "I'll help you create that template. Could you provide more details about what information changes each time you use this prompt?"
            
            return PromptBuilderResponse(
                message=message,
                template_updates=parsed.get("template_updates", {}),
                confidence=parsed.get("confidence", 0.5),
                ready_to_save=parsed.get("ready_to_save", False)
            )
            
        except Exception as e:
            logger.error(f"LLM call failed: {e}", exc_info=True)
            # Fallback response with helpful guidance
            return PromptBuilderResponse(
                message="I'm having trouble processing that. Could you describe what you'd like this template to do? For example, what task are you trying to automate or what information changes each time?",
                confidence=0.3,
                ready_to_save=False
            )
    
    def get_initial_greeting(self) -> PromptBuilderResponse:
        """Get the initial greeting message."""
        return PromptBuilderResponse(
            message="Hi! I'll help you create a prompt template. You can either:\n\n"
                   "1. Describe a recurring task you'd like to template\n"
                   "2. Paste an example transcript of the task\n\n"
                   "What would you like to create a template for?",
            confidence=1.0,
            ready_to_save=False
        )