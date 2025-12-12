"""
Monthly usage SQLAlchemy model for token usage tracking.
"""

from sqlalchemy import Column, String, BigInteger, Integer, Index, UniqueConstraint, JSON

from .base import Base


class MonthlyUsageModel(Base):
    """
    Monthly aggregated token usage per user.
    
    Tracks total usage and breakdowns by model and source for efficient querying.
    """

    __tablename__ = "monthly_usage"

    # Composite key: user + month
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=False, index=True)
    month = Column(String, nullable=False)  # Format: "2025-01"
    
    # Usage totals (in token credits, not raw tokens)
    # 1,000,000 credits = $1 USD
    total_usage = Column(BigInteger, default=0)
    prompt_usage = Column(BigInteger, default=0)
    completion_usage = Column(BigInteger, default=0)
    cached_usage = Column(BigInteger, default=0)
    
    # Breakdown by model (JSON for flexibility)
    # Example: {"gpt-4": 150000, "claude-3": 80000}
    usage_by_model = Column(JSON, default={})
    
    # Breakdown by source
    # Example: {"agent": 200000, "tool:web_search": 30000}
    usage_by_source = Column(JSON, default={})
    
    # Metadata
    created_at = Column(BigInteger, nullable=False)
    updated_at = Column(BigInteger, nullable=False)
    last_reset_at = Column(BigInteger, nullable=True)
    
    __table_args__ = (
        UniqueConstraint('user_id', 'month', name='uq_user_month'),
        Index('idx_monthly_usage_user_month', 'user_id', 'month'),
        Index('idx_monthly_usage_month', 'month'),
    )