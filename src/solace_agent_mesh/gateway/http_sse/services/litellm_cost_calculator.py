"""
Token cost calculator using LiteLLM's completion_cost() function.

This delegates cost calculation to LiteLLM, ensuring pricing is always up-to-date
and matches the actual costs from providers.
"""

import logging
from typing import Dict
from litellm import completion_cost as litellm_completion_cost

log = logging.getLogger(__name__)


class LiteLLMCostCalculator:
    """Calculate token costs using LiteLLM's completion_cost() function."""
    
    def calculate_cost(
        self,
        model: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        cached_input_tokens: int = 0,
    ) -> Dict[str, any]:
        """
        Calculate the cost for token usage using LiteLLM.
        
        Args:
            model: Model identifier
            prompt_tokens: Number of prompt/input tokens (includes cached)
            completion_tokens: Number of completion/output tokens
            cached_input_tokens: Number of cached input tokens
            
        Returns:
            Dictionary with cost breakdown:
            {
                "prompt_cost": int,  # In credits (1M = $1)
                "completion_cost": int,
                "cached_cost": int,
                "total_cost": int,
                "prompt_rate": float,  # Estimated
                "completion_rate": float,  # Estimated
                "cached_rate": float,  # Estimated
                "model": str,
            }
        """
        try:
            # Create a mock response for LiteLLM's completion_cost()
            mock_response = {
                "model": model,
                "usage": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": prompt_tokens + completion_tokens,
                },
                "choices": [{"message": {"role": "assistant", "content": ""}}]
            }
            
            # Add cached tokens if present
            if cached_input_tokens > 0:
                mock_response["usage"]["prompt_tokens_details"] = {
                    "cached_tokens": cached_input_tokens
                }
            
            # Get total cost from LiteLLM
            total_cost_usd = litellm_completion_cost(completion_response=mock_response)
            total_cost_credits = int(total_cost_usd * 1_000_000)
            
            # Calculate individual costs by testing each component
            # This gives us the breakdown for display purposes
            non_cached_prompt_tokens = prompt_tokens - cached_input_tokens
            
            # Get prompt cost (non-cached)
            if non_cached_prompt_tokens > 0:
                prompt_only_response = {
                    "model": model,
                    "usage": {
                        "prompt_tokens": non_cached_prompt_tokens,
                        "completion_tokens": 0,
                        "total_tokens": non_cached_prompt_tokens,
                    },
                    "choices": [{"message": {"role": "assistant", "content": ""}}]
                }
                prompt_cost_usd = litellm_completion_cost(completion_response=prompt_only_response)
                prompt_cost_credits = int(prompt_cost_usd * 1_000_000)
                prompt_rate = (prompt_cost_usd / non_cached_prompt_tokens * 1_000_000) if non_cached_prompt_tokens > 0 else 0
            else:
                prompt_cost_credits = 0
                prompt_rate = 0
            
            # Get completion cost
            if completion_tokens > 0:
                completion_only_response = {
                    "model": model,
                    "usage": {
                        "prompt_tokens": 0,
                        "completion_tokens": completion_tokens,
                        "total_tokens": completion_tokens,
                    },
                    "choices": [{"message": {"role": "assistant", "content": ""}}]
                }
                completion_cost_usd = litellm_completion_cost(completion_response=completion_only_response)
                completion_cost_credits = int(completion_cost_usd * 1_000_000)
                completion_rate = (completion_cost_usd / completion_tokens * 1_000_000) if completion_tokens > 0 else 0
            else:
                completion_cost_credits = 0
                completion_rate = 0
            
            # Get cached cost
            if cached_input_tokens > 0:
                cached_only_response = {
                    "model": model,
                    "usage": {
                        "prompt_tokens": cached_input_tokens,
                        "completion_tokens": 0,
                        "total_tokens": cached_input_tokens,
                        "prompt_tokens_details": {
                            "cached_tokens": cached_input_tokens
                        }
                    },
                    "choices": [{"message": {"role": "assistant", "content": ""}}]
                }
                cached_cost_usd = litellm_completion_cost(completion_response=cached_only_response)
                cached_cost_credits = int(cached_cost_usd * 1_000_000)
                cached_rate = (cached_cost_usd / cached_input_tokens * 1_000_000) if cached_input_tokens > 0 else 0
            else:
                cached_cost_credits = 0
                cached_rate = 0
            
            log.debug(
                f"Calculated cost for {model}: prompt={prompt_cost_credits}, "
                f"completion={completion_cost_credits}, cached={cached_cost_credits}, total={total_cost_credits}"
            )
            
            return {
                "prompt_cost": prompt_cost_credits,
                "completion_cost": completion_cost_credits,
                "cached_cost": cached_cost_credits,
                "total_cost": total_cost_credits,
                "prompt_rate": prompt_rate,
                "completion_rate": completion_rate,
                "cached_rate": cached_rate,
                "model": model,
            }
            
        except Exception as e:
            log.error(f"Error calculating cost with LiteLLM for model '{model}': {e}")
            # Fallback to simple estimation
            # Use conservative rates if LiteLLM fails
            fallback_prompt_rate = 1.0
            fallback_completion_rate = 2.0
            fallback_cached_rate = 0.5
            
            non_cached_prompt_tokens = max(0, prompt_tokens - cached_input_tokens)
            prompt_cost = int(fallback_prompt_rate * non_cached_prompt_tokens)
            completion_cost = int(fallback_completion_rate * completion_tokens)
            cached_cost = int(fallback_cached_rate * cached_input_tokens)
            total_cost = prompt_cost + completion_cost + cached_cost
            
            log.warning(
                f"Using fallback pricing for model '{model}': "
                f"prompt=${fallback_prompt_rate}/1M, completion=${fallback_completion_rate}/1M, "
                f"cached=${fallback_cached_rate}/1M"
            )
            
            return {
                "prompt_cost": prompt_cost,
                "completion_cost": completion_cost,
                "cached_cost": cached_cost,
                "total_cost": total_cost,
                "prompt_rate": fallback_prompt_rate,
                "completion_rate": fallback_completion_rate,
                "cached_rate": fallback_cached_rate,
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