"""
Service for generating starter card suggestions using LLM.

Generates contextual starter suggestions based on available agent cards,
with in-memory caching to avoid repeated LLM calls.
"""

import json
import logging
import time
from typing import Any

from google.adk.models import BaseLlm

from ....agent.adk.models.lite_llm import LiteLlm
from ....common.agent_registry import AgentRegistry

log = logging.getLogger(__name__)

# URI for the SAM tools extension in agent capabilities
TOOLS_EXTENSION_URI = "https://solace.com/a2a/extensions/sam/tools"


def extract_agent_data(agent_registry: AgentRegistry) -> list[dict[str, Any]]:
    """
    Extract simplified agent data from the registry for the suggestions service.

    Returns a list of dicts with keys: name, description, tools.
    """
    agent_names = agent_registry.get_agent_names()
    agents_data = []

    for name in agent_names:
        agent = agent_registry.get_agent(name)
        if not agent:
            continue

        tools = []
        if agent.capabilities and agent.capabilities.extensions:
            for ext in agent.capabilities.extensions:
                if ext.uri == TOOLS_EXTENSION_URI and ext.params:
                    for tool in ext.params.get("tools", []):
                        if isinstance(tool, dict):
                            tools.append(
                                {
                                    "name": tool.get("name", ""),
                                    "description": tool.get("description", ""),
                                }
                            )

        agents_data.append(
            {
                "name": agent.name,
                "description": agent.description or "",
                "tools": tools,
            }
        )

    return agents_data

# Cache TTL in seconds (10 minutes)
CACHE_TTL_SECONDS = 600

# LLM parameters
DEFAULT_TEMPERATURE = 0.7

# Max retries for JSON parse failures (with error feedback to LLM)
MAX_JSON_RETRIES = 1

# Default fallback suggestions when LLM is unavailable
DEFAULT_STARTER_SUGGESTIONS: list[dict[str, Any]] = [
    {
        "icon": "BarChart3",
        "label": "Research & Analysis",
        "description": "Investigate topics and analyze data",
        "options": [
            {
                "label": "Help me research a topic",
                "prompt": "Help me research a topic in depth. Ask me what I'd like to investigate and I'll provide the details.",
            },
            {
                "label": "Analyze data for insights",
                "prompt": "Help me analyze some data to find patterns and insights. Ask me about the data I'm working with so we can get started.",
            },
            {
                "label": "Compare options or alternatives",
                "prompt": "Help me compare different options or alternatives to make a decision. Ask me what I'm evaluating.",
            },
        ],
    },
    {
        "icon": "FileText",
        "label": "Writing & Editing",
        "description": "Draft, rewrite, and improve content",
        "options": [
            {
                "label": "Make my message more persuasive",
                "prompt": "Rewrite my message so it feels more persuasive for its audience and goal. If needed, ask me to share the message and what I want it to achieve.",
            },
            {
                "label": "Draft a professional email",
                "prompt": "Help me draft a professional email. Ask me about the recipient, purpose, and key points I want to cover.",
            },
            {
                "label": "Summarize a long document",
                "prompt": "Help me create a concise summary of a document. Ask me to share the content or tell you what it's about.",
            },
        ],
    },
    {
        "icon": "Lightbulb",
        "label": "Planning & Strategy",
        "description": "Organize ideas and plan next steps",
        "options": [
            {
                "label": "Help me plan a project",
                "prompt": "Help me create a project plan with milestones and tasks. Ask me about the project scope and timeline so we can get started.",
            },
            {
                "label": "Brainstorm solutions",
                "prompt": "Help me brainstorm solutions to a challenge I'm facing. Ask me to describe the problem and any constraints.",
            },
            {
                "label": "Prepare for a meeting",
                "prompt": "Help me prepare for an upcoming meeting. Ask me about the meeting topic, attendees, and what I want to accomplish.",
            },
        ],
    },
    {
        "icon": "TrendingUp",
        "label": "Problem Solving",
        "description": "Work through complex challenges",
        "options": [
            {
                "label": "Break down a complex problem",
                "prompt": "Help me break down a complex problem into manageable parts. Ask me to describe what I'm dealing with.",
            },
            {
                "label": "Evaluate a decision",
                "prompt": "Help me think through a decision by weighing pros and cons. Ask me about the options I'm considering.",
            },
            {
                "label": "Troubleshoot an issue",
                "prompt": "Help me troubleshoot an issue I'm experiencing. Ask me to describe the problem and what I've already tried.",
            },
        ],
    },
]


class StarterSuggestionsService:
    """
    Generates contextual starter card suggestions using LiteLLM based on
    available agent capabilities. Results are cached in-memory with TTL.
    """

    def __init__(self, model_config: dict, llm: BaseLlm):
        # Use a dedicated model if configured, otherwise fall back to the general LLM
        starter_model = model_config.get("llm_service_starter_model_name")
        if starter_model:
            litellm_config = {
                k: v
                for k, v in model_config.items()
                if k not in ("model", "llm_service_starter_model_name")
            }
            self.llm = LiteLlm(model=starter_model, **litellm_config)
        else:
            self.llm = llm

        # In-memory cache: { cache_key: (timestamp, suggestions) }
        self._cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}

        log.info("StarterSuggestionsService initialized with LiteLLM instance")

    def _build_cache_key(self, agent_names: list[str]) -> str:
        """Build a cache key based on the sorted set of available agent names."""
        sorted_names = sorted(set(agent_names))
        return "|".join(sorted_names)

    def _get_cached(self, cache_key: str) -> list[dict[str, Any]] | None:
        """Return cached suggestions if still valid, otherwise None."""
        if cache_key in self._cache:
            timestamp, suggestions = self._cache[cache_key]
            if time.time() - timestamp < CACHE_TTL_SECONDS:
                log.debug("Cache hit for starter suggestions (key=%s)", cache_key)
                return suggestions
            else:
                log.debug("Cache expired for starter suggestions (key=%s)", cache_key)
                del self._cache[cache_key]
        return None

    def _set_cached(
        self, cache_key: str, suggestions: list[dict[str, Any]]
    ) -> None:
        """Store suggestions in cache."""
        self._cache[cache_key] = (time.time(), suggestions)
        log.debug("Cached starter suggestions (key=%s)", cache_key)

    async def warm_cache(self, agents: list[dict[str, Any]]) -> None:
        """
        Pre-generate and cache suggestions at startup.
        Called during system initialization so first user request is instant.
        """
        try:
            log.info("Warming starter suggestions cache with %d agents", len(agents))
            await self.generate_suggestions(agents)
            log.info("Starter suggestions cache warmed successfully")
        except Exception as e:
            log.warning("Failed to warm starter suggestions cache: %s", e)

    async def generate_suggestions(
        self, agents: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Generate starter card suggestions based on available agents.

        Args:
            agents: List of agent card data dicts with keys like
                     'name', 'description', 'tools'.

        Returns:
            List of category dicts with icon, label, description, and options.
        """
        agent_names = [a.get("name", "") for a in agents if a.get("name")]
        cache_key = self._build_cache_key(agent_names)

        # Check cache first
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        # Build agent description for the prompt
        agent_descriptions = self._build_agent_descriptions(agents)

        if not agent_descriptions.strip():
            log.info("No agent descriptions available, returning defaults")
            return DEFAULT_STARTER_SUGGESTIONS

        try:
            suggestions = await self._call_litellm(agent_descriptions)
            if suggestions:
                self._set_cached(cache_key, suggestions)
                return suggestions
        except Exception as e:
            log.error(
                "Error generating starter suggestions via LLM: %s",
                e,
                exc_info=True,
            )

        log.info("Falling back to default starter suggestions")
        return DEFAULT_STARTER_SUGGESTIONS

    def _build_agent_descriptions(self, agents: list[dict[str, Any]]) -> str:
        """Build a text description of available agents for the LLM prompt."""
        lines = []
        for agent in agents:
            name = agent.get("name", "Unknown")
            description = agent.get("description", "No description")
            tools = agent.get("tools", [])

            tool_names = []
            for tool in tools:
                if isinstance(tool, str):
                    tool_names.append(tool)
                elif isinstance(tool, dict):
                    tool_names.append(tool.get("name", ""))

            tool_str = ", ".join(t for t in tool_names if t)
            line = f"- **{name}**: {description}"
            if tool_str:
                line += f" (tools/skills: {tool_str})"
            lines.append(line)

        return "\n".join(lines)

    def _build_initial_prompt(self, agent_descriptions: str) -> str:
        """Build the initial LLM prompt for generating starter suggestions."""
        return f"""You are generating starter task suggestions for an enterprise AI chat interface called Agent Mesh.

The system has these AI agents available:

{agent_descriptions}

Generate exactly 4 starter card categories that showcase what these agents can do. Each category should represent a type of task the agents can help with.

For each category, provide:
- "icon": A Lucide icon name from this list ONLY: BarChart3, Users, ShieldCheck, TrendingUp, FileSearch, Lightbulb, Search, FileText, Database, Globe, Bot, Briefcase, Code, Mail, Calendar, Settings, Zap, Target, PieChart, LineChart
- "label": A short category label (2-3 words)
- "description": A brief description (5-8 words)
- "options": An array of 3-4 task options, each with:
  - "label": A short action label (3-7 words)
  - "prompt": A ready-to-send prompt (1-2 sentences)

CRITICAL RULES for prompts:
- Prompts are written FROM THE USER'S PERSPECTIVE — they will be sent as the user's message to the AI assistant
- Use first person: "I", "my", "me" — NOT second person "you", "your"
- Prompts must be GENERIC and work for ANY user at ANY company
- Do NOT invent specific company names, product names, competitor names, or industry-specific details
- Do NOT reference "our company", "our competitors", "our data" — the user hasn't provided any context yet
- Prompts should describe what the user wants and invite the AI to ask clarifying questions
- Prompts should feel natural, like a real person asking for help
- Good example: "I need to rewrite my message so it feels more persuasive. I'll share the message and what I want it to achieve."
- Good example: "Help me draft a competitive analysis. I'll tell you about my industry and key competitors."
- Good example: "I need to prepare a summary report. Ask me what the report is about so we can get started."
- Bad example: "Share what you'd like summarized" (wrong — uses "you" instead of "I")
- Bad example: "Analyze Apple vs Samsung market share" (wrong — invents specific subjects)
- Bad example: "Summarize the Q3 2024 financial report for Acme Corp" (wrong — invents specific details)

Focus on enterprise use cases that match the available agent capabilities.
Use different icons for each category.

Respond with ONLY valid JSON (no markdown, no code fences, no explanation):
{{"categories": [
  {{
    "icon": "IconName",
    "label": "Category Label",
    "description": "Brief description",
    "options": [
      {{"label": "Action label", "prompt": "Generic task prompt..."}}
    ]
  }}
]}}"""

    def _build_correction_prompt(
        self, previous_response: str, error_reason: str
    ) -> str:
        """Build a correction prompt that includes the previous invalid response and error."""
        return f"""Your previous response was not valid JSON or failed validation.

Here is what you returned:
---
{previous_response[:2000]}
---

Error: {error_reason}

Please try again. Return ONLY valid JSON with no markdown, no code fences, and no explanation.
The response must be a JSON object with a "categories" array containing exactly 4 category objects.
Each category must have: "icon" (string), "label" (string), "description" (string), "options" (array).
Each option must have: "label" (string), "prompt" (string).

Valid icon names: BarChart3, Users, ShieldCheck, TrendingUp, FileSearch, Lightbulb, Search, FileText, Database, Globe, Bot, Briefcase, Code, Mail, Calendar, Settings, Zap, Target, PieChart, LineChart

Example of valid JSON:
{{"categories": [{{"icon": "Lightbulb", "label": "Planning", "description": "Organize and plan tasks", "options": [{{"label": "Help me plan a project", "prompt": "Help me create a project plan. Ask me about the scope and timeline."}}]}}]}}"""

    async def _send_llm_request(self, prompt: str) -> str | None:
        """Send a prompt to the LLM and return the raw text response."""
        try:
            from google.genai import types
            from google.adk.models.llm_request import LlmRequest

            llm_request = LlmRequest(
                contents=[
                    types.Content(
                        role="user",
                        parts=[types.Part.from_text(text=prompt)],
                    )
                ],
                config=types.GenerateContentConfig(
                    temperature=DEFAULT_TEMPERATURE,
                ),
            )

            parts = []
            async for llm_response in self.llm.generate_content_async(
                llm_request
            ):
                if llm_response.content and llm_response.content.parts:
                    for part in llm_response.content.parts:
                        if part.text:
                            parts.append(part.text)

            return "".join(parts) if parts else None

        except Exception as e:
            log.error(
                "Error calling LiteLLM for starter suggestions: %s",
                e,
                exc_info=True,
            )
            return None

    async def _call_litellm(
        self, agent_descriptions: str
    ) -> list[dict[str, Any]] | None:
        """
        Call LiteLLM to generate starter suggestions with retry on JSON parse failure.

        If the first response fails JSON validation, sends the error back to the LLM
        with a correction prompt for one retry attempt.
        """
        log.info("Calling LiteLLM for starter suggestions generation")

        # First attempt
        prompt = self._build_initial_prompt(agent_descriptions)
        content = await self._send_llm_request(prompt)

        if content is None:
            log.warning("LiteLLM returned None content for starter suggestions")
            return None

        # Try to parse the response
        result, error_reason = self._parse_llm_response(content)
        if result is not None:
            return result

        # First attempt failed - retry with error feedback
        log.info(
            "First LLM attempt failed validation (%s), retrying with correction prompt",
            error_reason,
        )

        for retry in range(MAX_JSON_RETRIES):
            correction_prompt = self._build_correction_prompt(content, error_reason)
            content = await self._send_llm_request(correction_prompt)

            if content is None:
                log.warning("LiteLLM returned None on retry %d", retry + 1)
                return None

            result, error_reason = self._parse_llm_response(content)
            if result is not None:
                log.info("Retry %d succeeded - valid JSON produced", retry + 1)
                return result

            log.warning(
                "Retry %d still failed validation: %s", retry + 1, error_reason
            )

        log.warning(
            "All %d retries exhausted, LLM could not produce valid JSON",
            MAX_JSON_RETRIES,
        )
        return None

    def _parse_llm_response(
        self, content: str
    ) -> tuple[list[dict[str, Any]] | None, str]:
        """
        Parse and validate the LLM JSON response.

        Returns:
            A tuple of (parsed_categories, error_reason).
            If parsing succeeds, error_reason is empty.
            If parsing fails, parsed_categories is None and error_reason describes the issue.
        """
        try:
            # Strip any markdown code fences if present
            text = content.strip()
            if text.startswith("```"):
                # Remove opening fence (with optional language tag)
                first_newline = text.find("\n")
                if first_newline == -1:
                    return None, "Code fence has no newline delimiter"
                text = text[first_newline + 1 :]
            if text.endswith("```"):
                text = text[: -len("```")]
            text = text.strip()

            data = json.loads(text)

            categories = data.get("categories", [])
            if not isinstance(categories, list) or len(categories) == 0:
                reason = "Response JSON has no 'categories' array or it is empty"
                log.warning("LLM response has no categories")
                return None, reason

            # Validate and normalize each category
            valid_icons = {
                "BarChart3",
                "Users",
                "ShieldCheck",
                "TrendingUp",
                "FileSearch",
                "Lightbulb",
                "Search",
                "FileText",
                "Database",
                "Globe",
                "Bot",
                "Briefcase",
                "Code",
                "Mail",
                "Calendar",
                "Settings",
                "Zap",
                "Target",
                "PieChart",
                "LineChart",
                "ChevronRight",
            }

            validated: list[dict[str, Any]] = []
            skipped_reasons: list[str] = []
            for i, cat in enumerate(categories):
                if not isinstance(cat, dict):
                    skipped_reasons.append(f"Category {i}: not a JSON object")
                    continue

                icon = cat.get("icon", "Lightbulb")
                if icon not in valid_icons:
                    icon = "Lightbulb"

                label = cat.get("label", "")
                description = cat.get("description", "")
                options = cat.get("options", [])

                if not label:
                    skipped_reasons.append(f"Category {i}: missing 'label'")
                    continue
                if not isinstance(options, list) or len(options) == 0:
                    skipped_reasons.append(
                        f"Category '{label}': missing or empty 'options' array"
                    )
                    continue

                valid_options = []
                for opt in options:
                    if not isinstance(opt, dict):
                        continue
                    opt_label = opt.get("label", "")
                    opt_prompt = opt.get("prompt", "")
                    if opt_label and opt_prompt:
                        valid_options.append(
                            {"label": opt_label, "prompt": opt_prompt}
                        )

                if valid_options:
                    validated.append(
                        {
                            "icon": icon,
                            "label": label,
                            "description": description,
                            "options": valid_options,
                        }
                    )
                else:
                    skipped_reasons.append(
                        f"Category '{label}': all options missing 'label' or 'prompt'"
                    )

            if not validated:
                reason = "No valid categories after validation. Issues: " + "; ".join(
                    skipped_reasons
                )
                log.warning("No valid categories after validation")
                return None, reason

            log.info(
                "Successfully parsed %d starter suggestion categories",
                len(validated),
            )
            return validated, ""

        except json.JSONDecodeError as e:
            reason = f"Invalid JSON syntax: {e}"
            log.warning("Failed to parse LLM response as JSON: %s", e)
            return None, reason
        except ValueError as e:
            reason = f"Value error during parsing: {e}"
            log.warning("Failed to parse LLM response: %s", e)
            return None, reason
