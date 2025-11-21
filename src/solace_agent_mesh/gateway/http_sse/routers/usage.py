"""
API router for token usage tracking and quota management.
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..dependencies import get_db, get_user_id
from ..services.usage_tracking_service import UsageTrackingService
from ..services.quota_management_service import QuotaManagementService
from ..services.token_pricing import TokenCostCalculator
from .dto.usage_dto import (
    CurrentUsageDTO,
    MonthlyUsageHistoryDTO,
    QuotaStatusDTO,
    TokenTransactionDTO,
    TransactionsResponseDTO,
    UserQuotaConfigDTO,
    AllUsersResponseDTO,
    SetQuotaRequestDTO,
    ResetUsageResponseDTO,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/usage", tags=["usage"])
admin_router = APIRouter(prefix="/api/v1/admin/usage", tags=["admin-usage"])


# Dependency to get services
def get_usage_service(
    db: Session = Depends(get_db)
) -> UsageTrackingService:
    """Get usage tracking service instance."""
    calculator = TokenCostCalculator()
    return UsageTrackingService(db, calculator)


def get_quota_service(
    db: Session = Depends(get_db)
) -> QuotaManagementService:
    """Get quota management service instance."""
    # TODO: Get these from app config
    system_quota = 20_000_000  # $20 default
    enforcement_enabled = False
    return QuotaManagementService(db, system_quota, enforcement_enabled)


# ============================================================================
# USER ENDPOINTS
# ============================================================================

@router.get("/current")
async def get_current_usage(
    user_id: str = Depends(get_user_id),
    usage_service: UsageTrackingService = Depends(get_usage_service),
):
    """
    Get current month usage for the authenticated user.
    
    Returns:
        Usage summary including total usage, breakdown by model/source, and cost
    """
    try:
        usage = usage_service.get_user_usage(user_id)
        log.info(f"get_current_usage: Retrieved usage for user {user_id}: {usage}")
        # Convert to DTO for camelCase
        usage_dto = CurrentUsageDTO(
            user_id=usage["user_id"],
            month=usage["month"],
            total_usage=usage["total_usage"],
            prompt_usage=usage["prompt_usage"],
            completion_usage=usage["completion_usage"],
            cached_usage=usage["cached_usage"],
            usage_by_model=usage["usage_by_model"],
            usage_by_source=usage["usage_by_source"],
            cost_usd=usage["cost_usd"],
            updated_at=usage.get("updated_at"),
            total_tokens=usage["total_tokens"],
            prompt_tokens=usage["prompt_tokens"],
            completion_tokens=usage["completion_tokens"],
            cached_tokens=usage["cached_tokens"],
        )
        serialized = usage_dto.model_dump(by_alias=True)
        log.info(f"get_current_usage: Serialized DTO keys: {list(serialized.keys())}")
        log.info(f"get_current_usage: Serialized values - totalTokens={serialized.get('totalTokens')}, totalUsage={serialized.get('totalUsage')}")
        return {
            "success": True,
            "data": serialized,
        }
    except Exception as e:
        log.error(f"Error getting current usage for user {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
async def get_usage_history(
    months: int = Query(default=6, ge=1, le=24),
    user_id: str = Depends(get_user_id),
    usage_service: UsageTrackingService = Depends(get_usage_service),
):
    """
    Get historical usage for the authenticated user.
    
    Args:
        months: Number of months to retrieve (1-24)
        
    Returns:
        List of monthly usage summaries
    """
    try:
        history = usage_service.get_usage_history(user_id, months)
        # Convert to DTOs for camelCase
        history_dtos = [
            MonthlyUsageHistoryDTO(
                month=h["month"],
                total_usage=h["total_usage"],
                prompt_usage=h["prompt_usage"],
                completion_usage=h["completion_usage"],
                cached_usage=h["cached_usage"],
                usage_by_model=h["usage_by_model"],
                usage_by_source=h["usage_by_source"],
                cost_usd=h["cost_usd"],
            ).model_dump(by_alias=True)
            for h in history
        ]
        return {
            "success": True,
            "data": history_dtos,
        }
    except Exception as e:
        log.error(f"Error getting usage history for user {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/quota")
async def get_quota_status(
    user_id: str = Depends(get_user_id),
    quota_service: QuotaManagementService = Depends(get_quota_service),
):
    """
    Get quota status for the authenticated user.
    
    Returns:
        Quota configuration, current usage, and remaining quota
    """
    try:
        status = quota_service.get_quota_status(user_id)
        # Convert to DTO for camelCase
        status_dto = QuotaStatusDTO(
            user_id=status["user_id"],
            month=status["month"],
            quota=status["quota"],
            current_usage=status["current_usage"],
            remaining=status["remaining"],
            usage_percentage=status["usage_percentage"],
            account_type=status["account_type"],
            is_active=status["is_active"],
            is_custom_quota=status["is_custom_quota"],
            enforcement_enabled=status["enforcement_enabled"],
            quota_reset_day=status["quota_reset_day"],
        )
        return {
            "success": True,
            "data": status_dto.model_dump(by_alias=True),
        }
    except Exception as e:
        log.error(f"Error getting quota status for user {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/transactions")
async def get_transactions(
    task_id: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    user_id: str = Depends(get_user_id),
    usage_service: UsageTrackingService = Depends(get_usage_service),
):
    """
    Get transaction history for the authenticated user.
    
    Args:
        task_id: Optional task ID filter
        limit: Maximum number of transactions to return
        offset: Offset for pagination
        
    Returns:
        Paginated list of transactions
    """
    try:
        transactions = usage_service.get_transactions(
            user_id=user_id,
            task_id=task_id,
            limit=limit,
            offset=offset,
        )
        log.info(
            f"Retrieved {len(transactions['transactions'])} transactions for user {user_id}, "
            f"total={transactions['total']}"
        )
        # Convert to DTOs for camelCase - serialize each transaction individually
        tx_dtos = []
        for tx in transactions["transactions"]:
            tx_dto = TokenTransactionDTO(
                id=tx["id"],
                task_id=tx["task_id"],
                transaction_type=tx["transaction_type"],
                model=tx["model"],
                raw_tokens=tx["raw_tokens"],
                token_cost=tx["token_cost"],
                cost_usd=tx["cost_usd"],
                rate=tx["rate"],
                source=tx["source"],
                tool_name=tx["tool_name"],
                context=tx["context"],
                created_at=tx["created_at"],
            )
            # Serialize with aliases to get camelCase
            serialized = tx_dto.model_dump(by_alias=True)
            log.info(f"Serialized transaction: {serialized}")
            tx_dtos.append(serialized)
        
        response_data = {
            "transactions": tx_dtos,
            "total": transactions["total"],
            "limit": transactions["limit"],
            "offset": transactions["offset"],
            "hasMore": transactions["has_more"],
        }
        log.info(f"Final response data keys: {list(response_data.keys())}, first tx keys: {list(tx_dtos[0].keys()) if tx_dtos else 'none'}")
        
        return {
            "success": True,
            "data": response_data,
        }
    except Exception as e:
        log.error(f"Error getting transactions for user {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ADMIN ENDPOINTS
# ============================================================================

@admin_router.get("/users")
async def get_all_users_usage(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    # TODO: Add admin role check
    # user_id: str = Depends(get_user_id),
    quota_service: QuotaManagementService = Depends(get_quota_service),
):
    """
    Get usage status for all users (admin only).
    
    Args:
        limit: Maximum number of users to return
        offset: Offset for pagination
        
    Returns:
        Paginated list of user usage statuses
    """
    try:
        users = quota_service.get_all_users_quota_status(limit, offset)
        return {
            "success": True,
            "data": users,
        }
    except Exception as e:
        log.error(f"Error getting all users usage: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@admin_router.post("/quota/set")
async def set_user_quota(
    user_id: str,
    monthly_quota: Optional[int] = None,
    account_type: Optional[str] = None,
    # TODO: Add admin role check
    # admin_id: str = Depends(get_user_id),
    quota_service: QuotaManagementService = Depends(get_quota_service),
):
    """
    Set custom quota for a user (admin only).
    
    Args:
        user_id: Target user ID
        monthly_quota: Custom monthly quota in credits (None = use system default)
        account_type: Account type (free, pro, enterprise, etc.)
        
    Returns:
        Updated quota configuration
    """
    try:
        result = quota_service.set_user_quota(
            user_id=user_id,
            monthly_quota=monthly_quota,
            account_type=account_type,
        )
        return {
            "success": True,
            "data": result,
        }
    except Exception as e:
        log.error(f"Error setting quota for user {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@admin_router.post("/quota/reset")
async def reset_user_usage(
    user_id: str,
    # TODO: Add admin role check
    # admin_id: str = Depends(get_user_id),
    quota_service: QuotaManagementService = Depends(get_quota_service),
):
    """
    Reset monthly usage for a user (admin only).
    
    Args:
        user_id: Target user ID
        
    Returns:
        Reset confirmation with previous and new usage
    """
    try:
        result = quota_service.reset_user_usage(user_id)
        return {
            "success": True,
            "data": result,
        }
    except Exception as e:
        log.error(f"Error resetting usage for user {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@admin_router.post("/users/{user_id}/activate")
async def activate_user(
    user_id: str,
    # TODO: Add admin role check
    # admin_id: str = Depends(get_user_id),
    quota_service: QuotaManagementService = Depends(get_quota_service),
):
    """
    Activate a user's quota (admin only).
    
    Args:
        user_id: Target user ID
        
    Returns:
        Updated quota configuration
    """
    try:
        result = quota_service.activate_user(user_id)
        return {
            "success": True,
            "data": result,
        }
    except Exception as e:
        log.error(f"Error activating user {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@admin_router.post("/users/{user_id}/deactivate")
async def deactivate_user(
    user_id: str,
    # TODO: Add admin role check
    # admin_id: str = Depends(get_user_id),
    quota_service: QuotaManagementService = Depends(get_quota_service),
):
    """
    Deactivate a user's quota (admin only).
    
    Args:
        user_id: Target user ID
        
    Returns:
        Updated quota configuration
    """
    try:
        result = quota_service.deactivate_user(user_id)
        return {
            "success": True,
            "data": result,
        }
    except Exception as e:
        log.error(f"Error deactivating user {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@admin_router.get("/analytics/models")
async def get_usage_by_model(
    days: int = Query(default=30, ge=1, le=365),
    # TODO: Add admin role check
    # admin_id: str = Depends(get_user_id),
    db: Session = Depends(get_db),
):
    """
    Get usage distribution by model (admin only).
    
    Args:
        days: Number of days to analyze
        
    Returns:
        Usage breakdown by model
    """
    try:
        # TODO: Implement analytics aggregation
        # This would query token_transactions and aggregate by model
        return {
            "success": True,
            "data": {
                "message": "Analytics endpoint - to be implemented",
                "days": days,
            },
        }
    except Exception as e:
        log.error(f"Error getting usage by model: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@admin_router.get("/analytics/trends")
async def get_usage_trends(
    days: int = Query(default=30, ge=1, le=365),
    # TODO: Add admin role check
    # admin_id: str = Depends(get_user_id),
    db: Session = Depends(get_db),
):
    """
    Get usage trends over time (admin only).
    
    Args:
        days: Number of days to analyze
        
    Returns:
        Time-series usage data
    """
    try:
        # TODO: Implement time-series analytics
        # This would query token_transactions and group by date
        return {
            "success": True,
            "data": {
                "message": "Analytics endpoint - to be implemented",
                "days": days,
            },
        }
    except Exception as e:
        log.error(f"Error getting usage trends: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# Export routers
__all__ = ["router", "admin_router"]