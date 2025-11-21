"""
Service for managing user quotas and checking usage limits.
"""

import logging
from datetime import datetime
from typing import Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from ..repository.models import UserQuotaModel, MonthlyUsageModel

log = logging.getLogger(__name__)


class QuotaManagementService:
    """Service for managing user quotas and limits."""
    
    # Default system quota (20M credits = $20)
    DEFAULT_SYSTEM_QUOTA = 20_000_000
    
    def __init__(
        self,
        db_session: Session,
        system_quota: Optional[int] = None,
        enforcement_enabled: bool = False,
    ):
        """
        Initialize quota management service.
        
        Args:
            db_session: SQLAlchemy database session
            system_quota: System-wide default quota (uses DEFAULT_SYSTEM_QUOTA if None)
            enforcement_enabled: Whether to enforce quota limits
        """
        self.db = db_session
        self.system_quota = system_quota or self.DEFAULT_SYSTEM_QUOTA
        self.enforcement_enabled = enforcement_enabled
    
    def check_quota(
        self,
        user_id: str,
        estimated_cost: int,
    ) -> Dict[str, any]:
        """Check if user has sufficient quota for an operation."""
        try:
            quota_config = self._get_or_create_quota_config(user_id)
            effective_quota = quota_config.monthly_quota or self.system_quota
            
            current_month = datetime.utcnow().strftime("%Y-%m")
            stmt = select(MonthlyUsageModel).where(
                MonthlyUsageModel.user_id == user_id,
                MonthlyUsageModel.month == current_month,
            )
            result = self.db.execute(stmt)
            usage_record = result.scalar_one_or_none()
            
            current_usage = usage_record.total_usage if usage_record else 0
            remaining = max(0, effective_quota - current_usage)
            would_exceed = (current_usage + estimated_cost) > effective_quota
            
            can_proceed = True
            if self.enforcement_enabled and would_exceed:
                can_proceed = False
            
            return {
                "can_proceed": can_proceed,
                "current_usage": current_usage,
                "quota": effective_quota,
                "remaining": remaining,
                "estimated_cost": estimated_cost,
                "would_exceed": would_exceed,
                "enforcement_enabled": self.enforcement_enabled,
                "is_active": quota_config.is_active,
            }
        except Exception as e:
            log.error(f"Error checking quota for user {user_id}: {e}", exc_info=True)
            return {
                "can_proceed": True,
                "current_usage": 0,
                "quota": self.system_quota,
                "remaining": self.system_quota,
                "estimated_cost": estimated_cost,
                "would_exceed": False,
                "enforcement_enabled": False,
                "error": str(e),
            }
    
    def _get_or_create_quota_config(self, user_id: str) -> UserQuotaModel:
        """Get or create user quota configuration."""
        stmt = select(UserQuotaModel).where(UserQuotaModel.user_id == user_id)
        result = self.db.execute(stmt)
        quota_config = result.scalar_one_or_none()
        
        if not quota_config:
            current_time = int(datetime.utcnow().timestamp() * 1000)
            quota_config = UserQuotaModel(
                user_id=user_id,
                monthly_quota=None,
                account_type="free",
                is_active=True,
                quota_reset_day=1,
                created_at=current_time,
                updated_at=current_time,
            )
            self.db.add(quota_config)
            self.db.commit()
            self.db.refresh(quota_config)
            log.info(f"Created default quota config for user {user_id}")
        
        return quota_config
    
    def set_user_quota(
        self,
        user_id: str,
        monthly_quota: Optional[int],
        account_type: Optional[str] = None,
    ) -> Dict[str, any]:
        """Set custom quota for a user."""
        try:
            quota_config = self._get_or_create_quota_config(user_id)
            
            quota_config.monthly_quota = monthly_quota
            if account_type:
                quota_config.account_type = account_type
            quota_config.updated_at = int(datetime.utcnow().timestamp() * 1000)
            
            self.db.commit()
            self.db.refresh(quota_config)
            
            log.info(f"Updated quota for user {user_id}: quota={monthly_quota}, type={account_type}")
            
            return {
                "user_id": quota_config.user_id,
                "monthly_quota": quota_config.monthly_quota,
                "account_type": quota_config.account_type,
                "is_active": quota_config.is_active,
                "updated_at": quota_config.updated_at,
            }
        except Exception as e:
            self.db.rollback()
            log.error(f"Error setting quota for user {user_id}: {e}", exc_info=True)
            raise
    
    def reset_user_usage(self, user_id: str) -> Dict[str, any]:
        """Reset monthly usage for a user."""
        try:
            current_month = datetime.utcnow().strftime("%Y-%m")
            current_time = int(datetime.utcnow().timestamp() * 1000)
            
            stmt = select(MonthlyUsageModel).where(
                MonthlyUsageModel.user_id == user_id,
                MonthlyUsageModel.month == current_month,
            )
            result = self.db.execute(stmt)
            usage_record = result.scalar_one_or_none()
            
            if usage_record:
                old_usage = usage_record.total_usage
                usage_record.total_usage = 0
                usage_record.prompt_usage = 0
                usage_record.completion_usage = 0
                usage_record.cached_usage = 0
                usage_record.usage_by_model = {}
                usage_record.usage_by_source = {}
                usage_record.last_reset_at = current_time
                usage_record.updated_at = current_time
                
                self.db.commit()
                log.info(f"Reset usage for user {user_id}: {old_usage} -> 0")
                
                return {
                    "user_id": user_id,
                    "month": current_month,
                    "previous_usage": old_usage,
                    "new_usage": 0,
                    "reset_at": current_time,
                }
            else:
                return {
                    "user_id": user_id,
                    "month": current_month,
                    "previous_usage": 0,
                    "new_usage": 0,
                    "message": "No usage record found for current month",
                }
        except Exception as e:
            self.db.rollback()
            log.error(f"Error resetting usage for user {user_id}: {e}", exc_info=True)
            raise
    
    def get_quota_status(self, user_id: str) -> Dict[str, any]:
        """Get comprehensive quota status for a user."""
        try:
            quota_config = self._get_or_create_quota_config(user_id)
            effective_quota = quota_config.monthly_quota or self.system_quota
            
            current_month = datetime.utcnow().strftime("%Y-%m")
            stmt = select(MonthlyUsageModel).where(
                MonthlyUsageModel.user_id == user_id,
                MonthlyUsageModel.month == current_month,
            )
            result = self.db.execute(stmt)
            usage_record = result.scalar_one_or_none()
            
            current_usage = usage_record.total_usage if usage_record else 0
            remaining = max(0, effective_quota - current_usage)
            usage_percentage = (current_usage / effective_quota * 100) if effective_quota > 0 else 0
            
            return {
                "user_id": user_id,
                "month": current_month,
                "quota": effective_quota,
                "current_usage": current_usage,
                "remaining": remaining,
                "usage_percentage": round(usage_percentage, 2),
                "account_type": quota_config.account_type,
                "is_active": quota_config.is_active,
                "is_custom_quota": quota_config.monthly_quota is not None,
                "enforcement_enabled": self.enforcement_enabled,
                "quota_reset_day": quota_config.quota_reset_day,
            }
        except Exception as e:
            log.error(f"Error getting quota status for user {user_id}: {e}", exc_info=True)
            raise
    
    def deactivate_user(self, user_id: str) -> Dict[str, any]:
        """Deactivate a user's quota."""
        try:
            quota_config = self._get_or_create_quota_config(user_id)
            quota_config.is_active = False
            quota_config.updated_at = int(datetime.utcnow().timestamp() * 1000)
            
            self.db.commit()
            self.db.refresh(quota_config)
            log.info(f"Deactivated user {user_id}")
            
            return {
                "user_id": quota_config.user_id,
                "is_active": quota_config.is_active,
                "updated_at": quota_config.updated_at,
            }
        except Exception as e:
            self.db.rollback()
            log.error(f"Error deactivating user {user_id}: {e}", exc_info=True)
            raise
    
    def activate_user(self, user_id: str) -> Dict[str, any]:
        """Activate a user's quota."""
        try:
            quota_config = self._get_or_create_quota_config(user_id)
            quota_config.is_active = True
            quota_config.updated_at = int(datetime.utcnow().timestamp() * 1000)
            
            self.db.commit()
            self.db.refresh(quota_config)
            log.info(f"Activated user {user_id}")
            
            return {
                "user_id": quota_config.user_id,
                "is_active": quota_config.is_active,
                "updated_at": quota_config.updated_at,
            }
        except Exception as e:
            self.db.rollback()
            log.error(f"Error activating user {user_id}: {e}", exc_info=True)
            raise
    
    def get_all_users_quota_status(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, any]:
        """Get quota status for all users."""
        try:
            from sqlalchemy import func
            
            count_stmt = select(func.count()).select_from(UserQuotaModel)
            count_result = self.db.execute(count_stmt)
            total = count_result.scalar()
            
            stmt = select(UserQuotaModel).limit(limit).offset(offset)
            result = self.db.execute(stmt)
            quota_configs = result.scalars().all()
            
            current_month = datetime.utcnow().strftime("%Y-%m")
            user_ids = [config.user_id for config in quota_configs]
            
            usage_stmt = select(MonthlyUsageModel).where(
                MonthlyUsageModel.user_id.in_(user_ids),
                MonthlyUsageModel.month == current_month,
            )
            usage_result = self.db.execute(usage_stmt)
            usage_records = usage_result.scalars().all()
            usage_dict = {record.user_id: record.total_usage for record in usage_records}
            
            users = []
            for config in quota_configs:
                effective_quota = config.monthly_quota or self.system_quota
                current_usage = usage_dict.get(config.user_id, 0)
                remaining = max(0, effective_quota - current_usage)
                usage_percentage = (current_usage / effective_quota * 100) if effective_quota > 0 else 0
                
                users.append({
                    "user_id": config.user_id,
                    "quota": effective_quota,
                    "current_usage": current_usage,
                    "remaining": remaining,
                    "usage_percentage": round(usage_percentage, 2),
                    "account_type": config.account_type,
                    "is_active": config.is_active,
                    "is_custom_quota": config.monthly_quota is not None,
                })
            
            return {
                "users": users,
                "total": total,
                "limit": limit,
                "offset": offset,
                "has_more": (offset + len(users)) < total,
            }
        except Exception as e:
            log.error(f"Error getting all users quota status: {e}", exc_info=True)
            raise