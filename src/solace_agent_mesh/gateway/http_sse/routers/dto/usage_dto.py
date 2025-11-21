"""
Data Transfer Objects for token usage API responses.
Uses camelCase for frontend compatibility.
"""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class UsageByModelDTO(BaseModel):
    """Usage breakdown by model."""
    model_config = {"populate_by_name": True}
    
    # Dynamic dict, no fixed fields


class CurrentUsageDTO(BaseModel):
    """Current month usage response."""
    model_config = {
        "populate_by_name": True,
        "by_alias": True,
    }
    
    userId: str = Field(alias="user_id", serialization_alias="userId")
    month: str
    totalUsage: int = Field(alias="total_usage", serialization_alias="totalUsage")
    promptUsage: int = Field(alias="prompt_usage", serialization_alias="promptUsage")
    completionUsage: int = Field(alias="completion_usage", serialization_alias="completionUsage")
    cachedUsage: int = Field(alias="cached_usage", serialization_alias="cachedUsage")
    usageByModel: Dict[str, int] = Field(alias="usage_by_model", serialization_alias="usageByModel")
    usageBySource: Dict[str, int] = Field(alias="usage_by_source", serialization_alias="usageBySource")
    costUsd: str = Field(alias="cost_usd", serialization_alias="costUsd")
    updatedAt: Optional[int] = Field(None, alias="updated_at", serialization_alias="updatedAt")
    # Raw token counts
    totalTokens: int = Field(alias="total_tokens", serialization_alias="totalTokens")
    promptTokens: int = Field(alias="prompt_tokens", serialization_alias="promptTokens")
    completionTokens: int = Field(alias="completion_tokens", serialization_alias="completionTokens")
    cachedTokens: int = Field(alias="cached_tokens", serialization_alias="cachedTokens")


class MonthlyUsageHistoryDTO(BaseModel):
    """Monthly usage history item."""
    model_config = {
        "populate_by_name": True,
        "by_alias": True,
    }
    
    month: str
    totalUsage: int = Field(alias="total_usage", serialization_alias="totalUsage")
    promptUsage: int = Field(alias="prompt_usage", serialization_alias="promptUsage")
    completionUsage: int = Field(alias="completion_usage", serialization_alias="completionUsage")
    cachedUsage: int = Field(alias="cached_usage", serialization_alias="cachedUsage")
    usageByModel: Dict[str, int] = Field(alias="usage_by_model", serialization_alias="usageByModel")
    usageBySource: Dict[str, int] = Field(alias="usage_by_source", serialization_alias="usageBySource")
    costUsd: str = Field(alias="cost_usd", serialization_alias="costUsd")


class QuotaStatusDTO(BaseModel):
    """Quota status response."""
    model_config = {
        "populate_by_name": True,
        "by_alias": True,
    }
    
    userId: str = Field(alias="user_id", serialization_alias="userId")
    month: str
    quota: int
    currentUsage: int = Field(alias="current_usage", serialization_alias="currentUsage")
    remaining: int
    usagePercentage: float = Field(alias="usage_percentage", serialization_alias="usagePercentage")
    accountType: str = Field(alias="account_type", serialization_alias="accountType")
    isActive: bool = Field(alias="is_active", serialization_alias="isActive")
    isCustomQuota: bool = Field(alias="is_custom_quota", serialization_alias="isCustomQuota")
    enforcementEnabled: bool = Field(alias="enforcement_enabled", serialization_alias="enforcementEnabled")
    quotaResetDay: int = Field(alias="quota_reset_day", serialization_alias="quotaResetDay")


class TokenTransactionDTO(BaseModel):
    """Token transaction response."""
    model_config = {
        "populate_by_name": True,
        "by_alias": True,  # This makes model_dump use aliases by default
    }
    
    id: int
    taskId: Optional[str] = Field(None, alias="task_id", serialization_alias="taskId")
    transactionType: str = Field(alias="transaction_type", serialization_alias="transactionType")
    model: str
    rawTokens: int = Field(alias="raw_tokens", serialization_alias="rawTokens")
    tokenCost: int = Field(alias="token_cost", serialization_alias="tokenCost")
    costUsd: str = Field(alias="cost_usd", serialization_alias="costUsd")
    rate: float
    source: Optional[str] = None
    toolName: Optional[str] = Field(None, alias="tool_name", serialization_alias="toolName")
    context: Optional[str] = None
    createdAt: int = Field(alias="created_at", serialization_alias="createdAt")


class TransactionsResponseDTO(BaseModel):
    """Transactions list response."""
    model_config = {"populate_by_name": True}
    
    transactions: List[TokenTransactionDTO]
    total: int
    limit: int
    offset: int
    hasMore: bool = Field(alias="has_more")


class UserQuotaConfigDTO(BaseModel):
    """User quota configuration response."""
    model_config = {"populate_by_name": True}
    
    userId: str = Field(alias="user_id")
    monthlyQuota: Optional[int] = Field(None, alias="monthly_quota")
    accountType: str = Field(alias="account_type")
    isActive: bool = Field(alias="is_active")
    updatedAt: int = Field(alias="updated_at")


class UserUsageStatusDTO(BaseModel):
    """User usage status for admin view."""
    model_config = {"populate_by_name": True}
    
    userId: str = Field(alias="user_id")
    quota: int
    currentUsage: int = Field(alias="current_usage")
    remaining: int
    usagePercentage: float = Field(alias="usage_percentage")
    accountType: str = Field(alias="account_type")
    isActive: bool = Field(alias="is_active")
    isCustomQuota: bool = Field(alias="is_custom_quota")


class AllUsersResponseDTO(BaseModel):
    """All users usage response."""
    model_config = {"populate_by_name": True}
    
    users: List[UserUsageStatusDTO]
    total: int
    limit: int
    offset: int
    hasMore: bool = Field(alias="has_more")


class SetQuotaRequestDTO(BaseModel):
    """Set quota request."""
    model_config = {"populate_by_name": True}
    
    userId: str = Field(alias="user_id")
    monthlyQuota: Optional[int] = Field(None, alias="monthly_quota")
    accountType: Optional[str] = Field(None, alias="account_type")


class ResetUsageResponseDTO(BaseModel):
    """Reset usage response."""
    model_config = {"populate_by_name": True}
    
    userId: str = Field(alias="user_id")
    month: str
    previousUsage: int = Field(alias="previous_usage")
    newUsage: int = Field(alias="new_usage")
    resetAt: int = Field(alias="reset_at")
    message: Optional[str] = None