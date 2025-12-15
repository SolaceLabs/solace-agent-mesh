"""
AI-powered app icon generator.
Generates emoji and background color combinations for app icons.
"""

import json
import logging
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from litellm import acompletion

logger = logging.getLogger(__name__)

# Default fallback icon when AI generation fails or is not configured
DEFAULT_ICON = {
    "emoji": "🚀",
    "background": "linear-gradient(135deg, #667eea 0%, #764ba2 100%)"
}

# Curated list of gradients that work well with emojis
GRADIENT_OPTIONS = [
    "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",  # Purple blue
    "linear-gradient(135deg, #f093fb 0%, #f5576c 100%)",  # Pink red
    "linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)",  # Blue cyan
    "linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)",  # Green teal
    "linear-gradient(135deg, #fa709a 0%, #fee140 100%)",  # Pink yellow
    "linear-gradient(135deg, #a8edea 0%, #fed6e3 100%)",  # Teal pink light
    "linear-gradient(135deg, #ff9a9e 0%, #fecfef 100%)",  # Salmon pink
    "linear-gradient(135deg, #ffecd2 0%, #fcb69f 100%)",  # Peach
    "linear-gradient(135deg, #a1c4fd 0%, #c2e9fb 100%)",  # Light blue
    "linear-gradient(135deg, #d299c2 0%, #fef9d7 100%)",  # Mauve cream
    "linear-gradient(135deg, #89f7fe 0%, #66a6ff 100%)",  # Cyan blue
    "linear-gradient(135deg, #fddb92 0%, #d1fdff 100%)",  # Yellow light blue
    "linear-gradient(135deg, #9890e3 0%, #b1f4cf 100%)",  # Purple green
    "linear-gradient(135deg, #ebc0fd 0%, #d9ded8 100%)",  # Lavender gray
    "linear-gradient(135deg, #f6d365 0%, #fda085 100%)",  # Yellow orange
]


class AppIconResult(BaseModel):
    """Result from the app icon generator."""
    emoji: str = Field(description="Emoji representing the app")
    background: str = Field(description="CSS gradient or color for the background")


class AppIconGenerator:
    """
    AI-powered app icon generator.
    Uses LLM to select appropriate emoji and background for an app.
    """

    SYSTEM_PROMPT = """You are an AI assistant that generates app icons.
Given an app name and description, select an appropriate emoji and background gradient.

RESPONSE FORMAT (REQUIRED - respond with valid JSON only):
{
  "emoji": "single emoji character",
  "background_index": 0-14
}

EMOJI SELECTION RULES:
- Choose a single emoji that best represents the app's purpose
- Consider the app name and description
- Prefer commonly recognized emojis
- If a current emoji is provided and you're asked to regenerate, try to pick something DIFFERENT but still appropriate
- For generic apps, use: 🚀 (launch/new), 💡 (ideas), ⚡ (fast/efficient), 🎯 (focused)

BACKGROUND INDEX:
Choose a number 0-14 representing these gradient styles:
0: Purple-blue (professional, tech)
1: Pink-red (creative, bold)
2: Blue-cyan (fresh, modern)
3: Green-teal (growth, nature)
4: Pink-yellow (fun, energetic)
5: Teal-pink light (soft, friendly)
6: Salmon-pink (warm, approachable)
7: Peach (warm, inviting)
8: Light blue (calm, trustworthy)
9: Mauve-cream (elegant, subtle)
10: Cyan-blue (tech, clean)
11: Yellow-light blue (cheerful, open)
12: Purple-green (creative, unique)
13: Lavender-gray (professional, minimal)
14: Yellow-orange (energetic, warm)

If a current background index is provided, try to pick a DIFFERENT gradient that still matches the app's mood.

Match the gradient mood to the app's purpose."""

    def __init__(self, model_config: Optional[Dict[str, Any]] = None):
        """Initialize the generator with model configuration."""
        self.model_config = model_config
        self.enabled = False

        logger.debug(f"AppIconGenerator received model_config: {model_config}")

        if model_config and isinstance(model_config, dict):
            model = model_config.get("model")
            # Check for non-empty string (env vars may resolve to empty string)
            if model and str(model).strip():
                self.enabled = True
                self.model = model
                self.api_base = model_config.get("api_base")
                self.api_key = model_config.get("api_key", "dummy")
                logger.info(f"AppIconGenerator initialized with model: {model}")
            else:
                logger.info(f"AppIconGenerator disabled: 'model' value is empty or not set (value: '{model}')")
        else:
            logger.info(f"AppIconGenerator disabled: model_config is {type(model_config).__name__} (value: {model_config})")

    async def generate(
        self,
        app_name: str,
        description: Optional[str] = None,
        current_emoji: Optional[str] = None,
        current_background: Optional[str] = None,
    ) -> AppIconResult:
        """
        Generate an emoji and background for an app.

        Args:
            app_name: The name of the app
            description: Optional description of the app
            current_emoji: Optional current emoji (to avoid picking the same one)
            current_background: Optional current background gradient (to avoid picking the same one)

        Returns:
            AppIconResult with emoji and background
        """
        if not self.enabled:
            logger.debug("Icon generation disabled, using default")
            return AppIconResult(**DEFAULT_ICON)

        try:
            return await self._generate_with_llm(app_name, description, current_emoji, current_background)
        except Exception as e:
            logger.warning(f"Icon generation failed, using default: {e}")
            return AppIconResult(**DEFAULT_ICON)

    def _get_background_index(self, gradient: str) -> Optional[int]:
        """Get the index of a gradient in GRADIENT_OPTIONS, or None if not found."""
        try:
            return GRADIENT_OPTIONS.index(gradient)
        except ValueError:
            return None

    async def _generate_with_llm(
        self,
        app_name: str,
        description: Optional[str],
        current_emoji: Optional[str],
        current_background: Optional[str],
    ) -> AppIconResult:
        """Use LLM to generate icon."""
        # Build the prompt
        user_message = f"App name: {app_name}"
        if description:
            user_message += f"\nDescription: {description}"

        # Include current values so LLM can pick something different
        if current_emoji:
            user_message += f"\nCurrent emoji: {current_emoji} (please pick a DIFFERENT one)"
        if current_background:
            bg_index = self._get_background_index(current_background)
            if bg_index is not None:
                user_message += f"\nCurrent background index: {bg_index} (please pick a DIFFERENT one)"

        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": user_message}
        ]

        # Call LLM
        completion_args = {
            "model": self.model,
            "messages": messages,
            "response_format": {"type": "json_object"},
            "temperature": 0.7,  # Some creativity for varied results
            "max_tokens": 100,  # Small response expected
        }

        if self.api_base:
            completion_args["api_base"] = self.api_base
        if self.api_key:
            completion_args["api_key"] = self.api_key

        response = await acompletion(**completion_args)
        content = response.choices[0].message.content

        logger.debug(f"LLM icon response: {content}")

        # Parse response
        parsed = json.loads(content)

        emoji = parsed.get("emoji", DEFAULT_ICON["emoji"])
        background_index = parsed.get("background_index", 0)

        # Validate emoji (should be a single character or emoji sequence)
        if not emoji or len(emoji) > 10:
            emoji = DEFAULT_ICON["emoji"]

        # Get gradient from index
        if isinstance(background_index, int) and 0 <= background_index < len(GRADIENT_OPTIONS):
            background = GRADIENT_OPTIONS[background_index]
        else:
            background = DEFAULT_ICON["background"]

        return AppIconResult(emoji=emoji, background=background)


def get_default_icon() -> AppIconResult:
    """Get the default icon for when generation is not available."""
    return AppIconResult(**DEFAULT_ICON)
