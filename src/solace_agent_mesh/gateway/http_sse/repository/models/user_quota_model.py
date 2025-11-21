"""
User quota SQLAlchemy model for token usage tracking.
"""

from sqlalchemy import Column, String, BigInteger, Integer, Boolean, Index, JSON

from .base import Base


class UserQuotaModel(Base):
    """
    User quota and account configuration for token usage tracking.
    
    Stores per-user quota settings, account types, and custom configurations.
    """

    __tablename__ = "user_quotas"

    # Primary key
    user_id = Column(String, primary_key=True, index=True)
    
    # Quota configuration
    monthly_quota = Column(BigInteger, nullable=True)  # null = use system default
    account_type = Column(String, default="free")  # free, pro, enterprise, etc.
    
    # Status
    is_active = Column(Boolean, default=True)
    quota_reset_day = Column(Integer, default=1)  # Day of month to reset (1-28)
    
    # Metadata
    created_at = Column(BigInteger, nullable=False)
    updated_at = Column(BigInteger, nullable=False)
    last_reset_at = Column(BigInteger, nullable=True)
    
    # Custom settings (JSON for flexibility)
    # Example: {"model_overrides": {"gpt-4": 1000000}, "alerts_enabled": true}
    custom_settings = Column(JSON, nullable=True)
    
    __table_args__ = (
        Index('idx_user_quotas_account_type', 'account_type'),
        Index('idx_user_quotas_is_active', 'is_active'),
    )