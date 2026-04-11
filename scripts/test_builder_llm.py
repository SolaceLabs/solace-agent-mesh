#!/usr/bin/env python3
"""
Test script to verify LLM responses for the task builder assistant.
Tests both claude-sonnet-4-6 and vertex-claude-sonnet-4-5 models via litellm proxy.

Usage:
    .venv/bin/python scripts/test_builder_llm.py

Requires:
    - LITELLM_API_BASE env var (e.g., http://localhost:4000)
    - LITELLM_API_KEY env var (or "dummy" for local proxy)
"""

import asyncio
import json
import os
import sys

from litellm import acompletion


# Minimal version of the task builder system prompt
SYSTEM_PROMPT = """You are an AI assistant helping users create scheduled tasks with natural language.

CRITICAL RULES:
1. You MUST respond with valid JSON in this exact format - NO EXCEPTIONS
2. You MUST always include a "message" field with a helpful, conversational response

RESPONSE FORMAT (REQUIRED):
{{
  "message": "your conversational response here - MUST be helpful and specific",
  "task_updates": {{
    "name": "Task Name",
    "schedule_type": "cron|interval|one_time",
    "schedule_expression": "cron expression or interval",
    "target_agent_name": "AgentName",
    "task_message": "Message to send to agent"
  }},
  "confidence": 0.0-1.0,
  "ready_to_save": false
}}

Example:
User: "I need a task to generate a daily report"
{{
  "message": "I'll help you create a daily report task. What time would you like the report generated?",
  "task_updates": {{
    "name": "Daily Report Generation",
    "schedule_type": "cron"
  }},
  "confidence": 0.6,
  "ready_to_save": false
}}
"""

# Same prompt but with single braces (the fix)
SYSTEM_PROMPT_FIXED = """You are an AI assistant helping users create scheduled tasks with natural language.

CRITICAL RULES:
1. You MUST respond with valid JSON in this exact format - NO EXCEPTIONS
2. You MUST always include a "message" field with a helpful, conversational response

RESPONSE FORMAT (REQUIRED):
{
  "message": "your conversational response here - MUST be helpful and specific",
  "task_updates": {
    "name": "Task Name",
    "schedule_type": "cron|interval|one_time",
    "schedule_expression": "cron expression or interval",
    "target_agent_name": "AgentName",
    "task_message": "Message to send to agent"
  },
  "confidence": 0.0-1.0,
  "ready_to_save": false
}

Example:
User: "I need a task to generate a daily report"
{
  "message": "I'll help you create a daily report task. What time would you like the report generated?",
  "task_updates": {
    "name": "Daily Report Generation",
    "schedule_type": "cron"
  },
  "confidence": 0.6,
  "ready_to_save": false
}
"""

USER_MESSAGE = "Create a task that checks system health every 30 minutes"

API_BASE = os.environ.get("LLM_SERVICE_ENDPOINT", os.environ.get("LITELLM_API_BASE", "http://localhost:4000"))
API_KEY = os.environ.get("LLM_SERVICE_API_KEY", os.environ.get("LITELLM_API_KEY", "dummy"))
DEFAULT_MODEL = os.environ.get("LLM_SERVICE_GENERAL_MODEL_NAME", "openai/claude-sonnet-4-6")

MODELS = [
    DEFAULT_MODEL,
]
# Add a second model for comparison if the default isn't vertex-claude-sonnet-4-5
if "vertex-claude-sonnet-4-5" not in DEFAULT_MODEL:
    MODELS.append("openai/vertex-claude-sonnet-4-5")


async def test_model(model: str, system_prompt: str, prompt_label: str) -> dict:
    """Test a single model with a given system prompt."""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": USER_MESSAGE},
    ]

    try:
        response = await acompletion(
            model=model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.1,
            api_base=API_BASE,
            api_key=API_KEY,
        )
        content = response.choices[0].message.content
        parsed = json.loads(content)
        has_message = bool(parsed.get("message", "").strip())
        return {
            "model": model,
            "prompt": prompt_label,
            "status": "OK" if has_message else "EMPTY_MESSAGE",
            "content": content[:300],
            "has_message": has_message,
        }
    except Exception as e:
        return {
            "model": model,
            "prompt": prompt_label,
            "status": "ERROR",
            "content": str(e)[:300],
            "has_message": False,
        }


async def main():
    print("=" * 70)
    print("Task Builder LLM Test")
    print(f"API Base: {API_BASE}")
    print(f"User Message: {USER_MESSAGE}")
    print("=" * 70)

    results = []
    for model in MODELS:
        for prompt, label in [
            (SYSTEM_PROMPT, "DOUBLE_BRACES (current)"),
            (SYSTEM_PROMPT_FIXED, "SINGLE_BRACES (fixed)"),
        ]:
            print(f"\nTesting: {model} with {label}...")
            result = await test_model(model, prompt, label)
            results.append(result)
            print(f"  Status: {result['status']}")
            print(f"  Has message: {result['has_message']}")
            print(f"  Content: {result['content'][:150]}...")

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    for r in results:
        icon = "✅" if r["has_message"] else "❌"
        print(f"  {icon} {r['model']:40s} | {r['prompt']:25s} | {r['status']}")


if __name__ == "__main__":
    asyncio.run(main())
