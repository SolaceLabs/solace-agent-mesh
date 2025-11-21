"""
Token pricing configuration and cost calculation service.

Rates are in USD per 1M tokens, stored as integer credits (1M credits = $1 USD).
"""

import logging
from typing import Dict, Optional
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass
class ModelPricing:
    """Pricing for a specific model."""
    prompt: float  # USD per 1M tokens
    completion: float  # USD per 1M tokens
    cached_read: Optional[float] = None  # For models with prompt caching
    cached_write: Optional[float] = None


# Default pricing (can be overridden via config)
# All rates are in USD per 1M tokens
DEFAULT_MODEL_PRICING: Dict[str, ModelPricing] = {
    # OpenAI GPT-5 Series
    "gpt-5.1": ModelPricing(prompt=1.25, completion=10.0, cached_read=0.125),
    "gpt-5": ModelPricing(prompt=1.25, completion=10.0, cached_read=0.125),
    "gpt-5-mini": ModelPricing(prompt=0.25, completion=2.0, cached_read=0.025),
    "gpt-5-nano": ModelPricing(prompt=0.05, completion=0.4, cached_read=0.005),
    "gpt-5.1-chat-latest": ModelPricing(prompt=1.25, completion=10.0, cached_read=0.125),
    "gpt-5-chat-latest": ModelPricing(prompt=1.25, completion=10.0, cached_read=0.125),
    "gpt-5.1-codex": ModelPricing(prompt=1.25, completion=10.0, cached_read=0.125),
    "gpt-5-codex": ModelPricing(prompt=1.25, completion=10.0, cached_read=0.125),
    "gpt-5-pro": ModelPricing(prompt=15.0, completion=120.0),
    "gpt-5.1-codex-mini": ModelPricing(prompt=0.25, completion=2.0, cached_read=0.025),
    "codex-mini-latest": ModelPricing(prompt=1.5, completion=6.0, cached_read=0.375),
    "gpt-5-search-api": ModelPricing(prompt=1.25, completion=10.0, cached_read=0.125),
    
    # OpenAI GPT-4.1 Series
    "gpt-4.1": ModelPricing(prompt=2.0, completion=8.0, cached_read=0.5),
    "gpt-4.1-mini": ModelPricing(prompt=0.4, completion=1.6, cached_read=0.1),
    "gpt-4.1-nano": ModelPricing(prompt=0.1, completion=0.4, cached_read=0.025),
    
    # OpenAI GPT-4o Series
    "gpt-4o": ModelPricing(prompt=2.5, completion=10.0, cached_read=1.25),
    "gpt-4o-2024-05-13": ModelPricing(prompt=5.0, completion=15.0),
    "gpt-4o-mini": ModelPricing(prompt=0.15, completion=0.6, cached_read=0.075),
    
    # OpenAI Realtime Models
    "gpt-realtime": ModelPricing(prompt=4.0, completion=16.0, cached_read=0.4),
    "gpt-realtime-mini": ModelPricing(prompt=0.6, completion=2.4, cached_read=0.06),
    "gpt-4o-realtime-preview": ModelPricing(prompt=5.0, completion=20.0, cached_read=2.5),
    "gpt-4o-mini-realtime-preview": ModelPricing(prompt=0.6, completion=2.4, cached_read=0.3),
    
    # OpenAI Audio Models
    "gpt-audio": ModelPricing(prompt=2.5, completion=10.0),
    "gpt-audio-mini": ModelPricing(prompt=0.6, completion=2.4),
    "gpt-4o-audio-preview": ModelPricing(prompt=2.5, completion=10.0),
    "gpt-4o-mini-audio-preview": ModelPricing(prompt=0.15, completion=0.6),
    
    # OpenAI o-Series (Reasoning Models)
    "o1": ModelPricing(prompt=15.0, completion=60.0, cached_read=7.5),
    "o1-pro": ModelPricing(prompt=150.0, completion=600.0),
    "o1-mini": ModelPricing(prompt=1.1, completion=4.4, cached_read=0.55),
    "o3-pro": ModelPricing(prompt=20.0, completion=80.0),
    "o3": ModelPricing(prompt=2.0, completion=8.0, cached_read=0.5),
    "o3-deep-research": ModelPricing(prompt=10.0, completion=40.0, cached_read=2.5),
    "o3-mini": ModelPricing(prompt=1.1, completion=4.4, cached_read=0.55),
    "o4-mini": ModelPricing(prompt=1.1, completion=4.4, cached_read=0.275),
    "o4-mini-deep-research": ModelPricing(prompt=2.0, completion=8.0, cached_read=0.5),
    
    # Legacy OpenAI Models
    "gpt-4-turbo": ModelPricing(prompt=10.0, completion=30.0),
    "gpt-4": ModelPricing(prompt=30.0, completion=60.0),
       
    # Anthropic Models
    "claude-3-opus": ModelPricing(
        prompt=15.0,
        completion=75.0,
        cached_write=18.75,
        cached_read=1.5
    ),
    "claude-3-sonnet": ModelPricing(
        prompt=3.0,
        completion=15.0,
        cached_write=3.75,
        cached_read=0.3
    ),
    "claude-3-haiku": ModelPricing(prompt=0.25, completion=1.25),
    "claude-3-5-sonnet": ModelPricing(
        prompt=3.0,
        completion=15.0,
        cached_write=3.75,
        cached_read=0.3
    ),
    "claude-3-5-haiku": ModelPricing(
        prompt=0.8,
        completion=4.0,
        cached_write=1.0,
        cached_read=0.08
    ),
    "claude-sonnet-4": ModelPricing(
        prompt=3.0,
        completion=15.0,
        cached_write=3.75,
        cached_read=0.3
    ),
    "claude-haiku-4": ModelPricing(
        prompt=1.0,
        completion=5.0,
        cached_write=1.25,
        cached_read=0.1
    ),
    
    # Google Models
    "gemini-1.5-pro": ModelPricing(prompt=2.5, completion=10.0),
    "gemini-1.5-flash": ModelPricing(prompt=0.15, completion=0.6),
    "gemini-1.5-flash-8b": ModelPricing(prompt=0.075, completion=0.3),
    "gemini-2.0-flash": ModelPricing(prompt=0.1, completion=0.4),
    "gemini-2.0-flash-lite": ModelPricing(prompt=0.075, completion=0.3),
    "gemini-2.5-flash": ModelPricing(prompt=0.30, completion=2.5),
    "gemini-2.5-pro": ModelPricing(prompt=1.25, completion=10.0),
    
    # DeepSeek Models
    "deepseek-chat": ModelPricing(prompt=0.14, completion=0.28),
    "deepseek-reasoner": ModelPricing(prompt=0.55, completion=2.19),
    
    # Cohere Models
    "command-r-plus": ModelPricing(prompt=3.0, completion=15.0),
    "command-r": ModelPricing(prompt=0.5, completion=1.5),
    
    # Default fallback
    "default": ModelPricing(prompt=1.0, completion=2.0),
}


class TokenCostCalculator:
    """Calculate token costs based on model pricing."""
    
    def __init__(self, pricing_config: Optional[Dict[str, ModelPricing]] = None):
        """
        Initialize calculator with pricing configuration.
        
        Args:
            pricing_config: Optional custom pricing. Uses DEFAULT_MODEL_PRICING if None.
        """
        self.pricing = pricing_config or DEFAULT_MODEL_PRICING
        log.debug(f"TokenCostCalculator initialized with {len(self.pricing)} model pricings")
    
    def get_model_pricing(self, model: str) -> ModelPricing:
        """
        Get pricing for a model, with fuzzy matching and fallback.
        
        Args:
            model: Model identifier (e.g., "gpt-4o-2024-05-13")
            
        Returns:
            ModelPricing for the model
        """
        if not model:
            return self.pricing["default"]
        
        model_lower = model.lower()
        
        # Exact match
        if model_lower in self.pricing:
            return self.pricing[model_lower]
        
        # Fuzzy match - check if any pricing key is a substring of the model
        # Sort by length descending to match most specific first
        sorted_keys = sorted(self.pricing.keys(), key=len, reverse=True)
        for key in sorted_keys:
            if key in model_lower or model_lower.startswith(key):
                log.debug(f"Fuzzy matched model '{model}' to pricing key '{key}'")
                return self.pricing[key]
        
        # Fallback to default
        log.warning(f"No pricing found for model '{model}', using default")
        return self.pricing["default"]
    
    def calculate_cost(
        self,
        model: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        cached_input_tokens: int = 0,
    ) -> Dict[str, any]:
        """
        Calculate the cost for token usage.
        
        Args:
            model: Model identifier
            prompt_tokens: Number of prompt/input tokens
            completion_tokens: Number of completion/output tokens
            cached_input_tokens: Number of cached input tokens (if applicable)
            
        Returns:
            Dictionary with cost breakdown:
            {
                "prompt_cost": int,  # In credits (1M = $1)
                "completion_cost": int,
                "cached_cost": int,
                "total_cost": int,
                "prompt_rate": float,
                "completion_rate": float,
                "cached_rate": float,
                "model": str,
            }
        """
        pricing = self.get_model_pricing(model)
        
        # Calculate costs (convert to credits: rate * tokens)
        prompt_cost = int(pricing.prompt * prompt_tokens)
        completion_cost = int(pricing.completion * completion_tokens)
        
        # Handle cached tokens if model supports it
        cached_cost = 0
        cached_rate = 0.0
        if cached_input_tokens > 0 and pricing.cached_read:
            cached_cost = int(pricing.cached_read * cached_input_tokens)
            cached_rate = pricing.cached_read
        
        total_cost = prompt_cost + completion_cost + cached_cost
        
        return {
            "prompt_cost": prompt_cost,
            "completion_cost": completion_cost,
            "cached_cost": cached_cost,
            "total_cost": total_cost,
            "prompt_rate": pricing.prompt,
            "completion_rate": pricing.completion,
            "cached_rate": cached_rate,
            "model": model,
        }
    
    def format_cost_usd(self, credits: int) -> str:
        """
        Format credits as USD string.
        
        Args:
            credits: Cost in credits (1M credits = $1)
            
        Returns:
            Formatted string like "$0.0025"
        """
        usd = credits / 1_000_000
        return f"${usd:.4f}"
    
    def add_custom_pricing(self, model: str, pricing: ModelPricing) -> None:
        """
        Add or update pricing for a specific model.
        
        Args:
            model: Model identifier
            pricing: ModelPricing configuration
        """
        self.pricing[model.lower()] = pricing
        log.info(f"Added custom pricing for model '{model}'")
    
    def get_all_models(self) -> list[str]:
        """
        Get list of all models with configured pricing.
        
        Returns:
            List of model identifiers
        """
        return list(self.pricing.keys())