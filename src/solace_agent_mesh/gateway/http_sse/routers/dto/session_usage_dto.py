"""
DTOs for session-specific token usage tracking
"""

from typing import Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class SessionTokenUsageDTO(BaseModel):
    """Session-specific token usage for real-time context tracking"""
    
    model_config = ConfigDict(populate_by_name=True)
    
    session_id: str = Field(serialization_alias="sessionId")
    # Accumulated totals (for cost tracking)
    total_tokens: int = Field(serialization_alias="totalTokens")
    prompt_tokens: int = Field(serialization_alias="promptTokens")
    completion_tokens: int = Field(serialization_alias="completionTokens")
    cached_tokens: int = Field(serialization_alias="cachedTokens")
    cost_usd: str = Field(serialization_alias="costUsd")
    model_breakdown: Dict[str, Dict[str, Any]] = Field(
        serialization_alias="modelBreakdown",
        description="Breakdown by model with tokens and cost"
    )
    # Current context window usage (most recent prompt tokens)
    current_context_tokens: int = Field(
        serialization_alias="currentContextTokens",
        description="Current context window usage - tokens from the most recent LLM call"
    )
    last_updated: int = Field(serialization_alias="lastUpdated")