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
DEFAULT_TEMPERATURE = 0.8

# Default fallback suggestions when LLM is unavailable
DEFAULT_STARTER_SUGGESTIONS: list[dict[str, Any]] = [
    {
        "icon": "BarChart3",
        "label": "Competitive Research",
        "description": "Analyze market position and competitors",
        "options": [
            {
                "label": "Compare against top 3 competitors",
                "prompt": "Conduct a competitive analysis comparing our company's market position against our top 3 competitors. Include market share, product differentiation, pricing strategies, and recent strategic moves.",
            },
            {
                "label": "Identify market trends",
                "prompt": "Research and summarize the latest market trends in our industry. Identify emerging opportunities, potential disruptions, and how competitors are positioning themselves.",
            },
            {
                "label": "SWOT analysis of our position",
                "prompt": "Perform a SWOT analysis of our company's current market position. Identify our key strengths, weaknesses, opportunities, and threats relative to our competitive landscape.",
            },
        ],
    },
    {
        "icon": "Users",
        "label": "Customer Insights",
        "description": "Discover trends from customer data",
        "options": [
            {
                "label": "Analyze customer pain points",
                "prompt": "Analyze our customer feedback data to identify the top pain points and friction areas. Provide actionable recommendations for improving customer experience.",
            },
            {
                "label": "Customer satisfaction drivers",
                "prompt": "Identify the key drivers of customer satisfaction from our feedback data. What are customers most happy about and what keeps them loyal?",
            },
            {
                "label": "Churn risk analysis",
                "prompt": "Analyze customer behavior patterns to identify early warning signs of churn. What factors most strongly predict customer attrition?",
            },
        ],
    },
    {
        "icon": "ShieldCheck",
        "label": "Compliance Report",
        "description": "Review regulatory status and risks",
        "options": [
            {
                "label": "Regulatory status overview",
                "prompt": "Generate a compliance status report covering our current regulatory obligations, recent policy changes, and any areas requiring immediate attention.",
            },
            {
                "label": "Risk assessment summary",
                "prompt": "Perform a risk assessment of our current compliance posture. Identify high-risk areas, gaps in controls, and recommended remediation steps.",
            },
            {
                "label": "Policy change impact analysis",
                "prompt": "Analyze recent regulatory and policy changes that affect our industry. Summarize the impact on our operations and required actions.",
            },
        ],
    },
    {
        "icon": "TrendingUp",
        "label": "Business Strategy",
        "description": "Plan initiatives and growth strategy",
        "options": [
            {
                "label": "Quarterly strategic plan",
                "prompt": "Help me develop a strategic plan for the next quarter. Analyze current performance metrics, identify growth opportunities, and recommend key initiatives with expected ROI.",
            },
            {
                "label": "Growth opportunity analysis",
                "prompt": "Identify and evaluate the top growth opportunities for our business. Consider market expansion, product development, partnerships, and operational improvements.",
            },
            {
                "label": "KPI dashboard review",
                "prompt": "Review our key performance indicators and provide insights on trends, areas of concern, and recommendations for improvement across all business units.",
            },
        ],
    },
    {
        "icon": "FileSearch",
        "label": "Data Analysis",
        "description": "Extract insights from your data",
        "options": [
            {
                "label": "Find patterns and trends",
                "prompt": "Help me analyze a dataset to uncover key patterns, trends, and anomalies. I need statistical summaries and actionable insights from the data.",
            },
            {
                "label": "Create data visualizations",
                "prompt": "Recommend the best data visualizations for my dataset. Suggest chart types, key metrics to highlight, and how to tell a compelling data story.",
            },
            {
                "label": "Statistical summary report",
                "prompt": "Generate a comprehensive statistical summary of my data including distributions, correlations, outliers, and key metrics with interpretations.",
            },
        ],
    },
    {
        "icon": "Lightbulb",
        "label": "Process Optimization",
        "description": "Streamline workflows and operations",
        "options": [
            {
                "label": "Identify bottlenecks",
                "prompt": "Review our current workflow processes and identify bottlenecks, inefficiencies, and automation opportunities. Provide a prioritized list of improvements.",
            },
            {
                "label": "Automation opportunities",
                "prompt": "Analyze our business processes to identify the best candidates for automation. Estimate effort, impact, and ROI for each automation opportunity.",
            },
            {
                "label": "Workflow redesign",
                "prompt": "Help me redesign a key business workflow to improve efficiency. Map the current state, identify waste, and propose an optimized future state.",
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

        prompt = f"""You are a helpful assistant that generates starter conversation suggestions for an enterprise AI chat interface.

The chat interface has access to the following AI agents and their capabilities:

{agent_descriptions}

Based on these available agents and their capabilities, generate 4-6 starter card categories. Each category should represent a common enterprise task that leverages the available agents.

For each category, provide:
- "icon": A Lucide React icon name (choose from: BarChart3, Users, ShieldCheck, TrendingUp, FileSearch, Lightbulb, Search, FileText, Database, Globe, Bot, Briefcase, Code, Mail, Calendar, Settings, Zap, Target, PieChart, LineChart)
- "label": A short category label (2-4 words)
- "description": A brief description (5-10 words)
- "options": An array of 3-4 specific prompt options, each with:
  - "label": A short action label (3-8 words)
  - "prompt": A detailed, ready-to-send prompt (1-3 sentences) that a user would send to the chat

Requirements:
- Make suggestions specific and actionable, not generic
- Tailor suggestions to the actual capabilities of the available agents
- Focus on enterprise use cases (research, analysis, reporting, planning, etc.)
- Each prompt should be self-contained and ready to submit
- Vary the icon choices across categories

Respond with ONLY valid JSON in this exact format (no markdown, no code fences):
{{"categories": [
  {{
    "icon": "IconName",
    "label": "Category Label",
    "description": "Brief description",
    "options": [
      {{"label": "Action label", "prompt": "Detailed prompt text..."}}
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
