"""
Token transaction SQLAlchemy model for detailed usage logging.
"""

from sqlalchemy import Column, String, BigInteger, Integer, Float, Index, JSON

from .base import Base


class TokenTransactionModel(Base):
    """
    Detailed token transaction log for auditing and analytics.
    
    Records individual token usage events with full context for analysis.
    """

    __tablename__ = "token_transactions"

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # References
    user_id = Column(String, nullable=False, index=True)
    task_id = Column(String, nullable=True, index=True)  # Link to tasks table
    
    # Transaction details
    transaction_type = Column(String, nullable=False)  # prompt, completion, cached
    model = Column(String, nullable=False, index=True)
    
    # Token counts (raw tokens)
    raw_tokens = Column(Integer, nullable=False)
    
    # Cost calculation
    token_cost = Column(BigInteger, nullable=False)  # In credits (1M credits = $1)
    rate = Column(Float, nullable=False)  # Multiplier used (USD per 1M tokens)
    
    # Context
    source = Column(String, nullable=True)  # agent, tool, etc.
    tool_name = Column(String, nullable=True)
    context = Column(String, nullable=True)  # message, title, summary, etc.
    
    # Metadata
    created_at = Column(BigInteger, nullable=False, index=True)
    transaction_metadata = Column(JSON, nullable=True)
    
    __table_args__ = (
        Index('idx_token_tx_user_created', 'user_id', 'created_at'),
        Index('idx_token_tx_task', 'task_id'),
        Index('idx_token_tx_model', 'model'),
        Index('idx_token_tx_created', 'created_at'),
    )