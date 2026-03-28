"""
Service for generating starter card suggestions using LLM.

Generates contextual starter suggestions based on available agent cards,
with in-memory caching to avoid repeated LLM calls.
"""

import hashlib
import json
import logging
import time
from typing import Any, Optional

from google.adk.models import BaseLlm

from ....agent.adk.models.lite_llm import LiteLlm

log = logging.getLogger(__name__)

# Cache TTL in seconds (10 minutes)
CACHE_TTL_SECONDS = 600

# LLM parameters
DEFAULT_TEMPERATURE = 0.7

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
        key_str = "|".join(sorted_names)
        return hashlib.md5(key_str.encode()).hexdigest()

    def _get_cached(self, cache_key: str) -> Optional[list[dict[str, Any]]]:
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

    async def _call_litellm(
        self, agent_descriptions: str
    ) -> Optional[list[dict[str, Any]]]:
        """Call LiteLLM to generate starter suggestions."""
        log.info("Calling LiteLLM for starter suggestions generation")

        prompt = f"""You are generating starter task suggestions for an enterprise AI chat interface called Agent Mesh.

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
- Prompts must be GENERIC and work for ANY user at ANY company
- Do NOT invent specific company names, product names, competitor names, or industry-specific details
- Do NOT reference "our company", "our competitors", "our data" — the user hasn't provided any context yet
- Prompts should describe the TYPE of task and invite the user to provide their own context
- Prompts should feel conversational and helpful, like a smart assistant offering to help
- If the task needs user input, the prompt should ask for it naturally
- Good example: "Rewrite my message so it feels more persuasive for its audience and goal. If needed, ask me to share the message and what I want it to achieve."
- Good example: "Help me draft a competitive analysis. Ask me about my industry and key competitors to get started."
- Good example: "I need to prepare a summary report. Help me organize my thoughts — ask me what the report is about."
- Bad example: "Analyze Apple vs Samsung market share in the smartphone industry"
- Bad example: "Summarize the Q3 2024 financial report for Acme Corp"
- Bad example: "Research the latest trends in the automotive industry"

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

            content = None
            async for llm_response in self.llm.generate_content_async(
                llm_request
            ):
                if llm_response.content and llm_response.content.parts:
                    for part in llm_response.content.parts:
                        if part.text:
                            content = part.text
                            break

            if content is None:
                log.warning(
                    "LiteLLM returned None content for starter suggestions"
                )
                return None

            # Parse the JSON response
            return self._parse_llm_response(content)

        except Exception as e:
            log.error(
                "Error calling LiteLLM for starter suggestions: %s",
                e,
                exc_info=True,
            )
            return None

    def _parse_llm_response(
        self, content: str
    ) -> Optional[list[dict[str, Any]]]:
        """Parse and validate the LLM JSON response."""
        try:
            # Strip any markdown code fences if present
            text = content.strip()
            if text.startswith("```"):
                # Remove opening fence (with optional language tag)
                first_newline = text.index("\n")
                text = text[first_newline + 1 :]
            if text.endswith("```"):
                text = text[: -len("```")]
            text = text.strip()

            data = json.loads(text)

            categories = data.get("categories", [])
            if not isinstance(categories, list) or len(categories) == 0:
                log.warning("LLM response has no categories")
                return None

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
            for cat in categories:
                if not isinstance(cat, dict):
                    continue

                icon = cat.get("icon", "Lightbulb")
                if icon not in valid_icons:
                    icon = "Lightbulb"

                label = cat.get("label", "")
                description = cat.get("description", "")
                options = cat.get("options", [])

                if not label or not isinstance(options, list) or len(options) == 0:
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

            if not validated:
                log.warning("No valid categories after validation")
                return None

            log.info(
                "Successfully parsed %d starter suggestion categories",
                len(validated),
            )
            return validated

        except (json.JSONDecodeError, ValueError) as e:
            log.error(
                "Failed to parse LLM response as JSON: %s", e, exc_info=True
            )
            return None
