"""
Service for tracking and recording token usage.
"""

import logging
from datetime import datetime
from typing import Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from ..repository.models import (
    MonthlyUsageModel,
    TokenTransactionModel,
)
from .token_pricing import TokenCostCalculator

log = logging.getLogger(__name__)


class UsageTrackingService:
    """Service for recording and tracking token usage."""
    
    def __init__(
        self,
        db_session: Session,
        cost_calculator: Optional[TokenCostCalculator] = None
    ):
        """
        Initialize the usage tracking service.
        
        Args:
            db_session: SQLAlchemy database session
            cost_calculator: Token cost calculator (creates default if None)
        """
        self.db = db_session
        self.calculator = cost_calculator or TokenCostCalculator()
    
    def record_token_usage(
        self,
        user_id: str,
        task_id: Optional[str],
        model: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        cached_input_tokens: int = 0,
        source: str = "agent",
        tool_name: Optional[str] = None,
        context: Optional[str] = None,
    ) -> Dict[str, any]:
        """
        Record token usage for a user.
        
        Creates transaction records and updates monthly usage aggregates.
        
        Args:
            user_id: User identifier
            task_id: Associated task ID (optional)
            model: Model identifier
            prompt_tokens: Number of prompt tokens
            completion_tokens: Number of completion tokens
            cached_input_tokens: Number of cached tokens
            source: Source of usage (agent, tool, etc.)
            tool_name: Tool name if source is tool
            context: Additional context (message, title, etc.)
            
        Returns:
            Dictionary with transaction details and updated usage
        """
        try:
            # Calculate costs
            cost_breakdown = self.calculator.calculate_cost(
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cached_input_tokens=cached_input_tokens,
            )
            
            current_time = int(datetime.utcnow().timestamp() * 1000)
            current_month = datetime.utcnow().strftime("%Y-%m")
            
            # Create transaction records
            transactions = []
            
            if prompt_tokens > 0:
                tx = TokenTransactionModel(
                    user_id=user_id,
                    task_id=task_id,
                    transaction_type="prompt",
                    model=model,
                    raw_tokens=prompt_tokens,
                    token_cost=cost_breakdown["prompt_cost"],
                    rate=cost_breakdown["prompt_rate"],
                    source=source,
                    tool_name=tool_name,
                    context=context,
                    created_at=current_time,
                )
                self.db.add(tx)
                transactions.append(tx)
                log.info(
                    f"Created prompt transaction: user={user_id}, task={task_id}, "
                    f"tokens={prompt_tokens}, cost={cost_breakdown['prompt_cost']}, "
                    f"created_at={current_time}"
                )
            
            if completion_tokens > 0:
                tx = TokenTransactionModel(
                    user_id=user_id,
                    task_id=task_id,
                    transaction_type="completion",
                    model=model,
                    raw_tokens=completion_tokens,
                    token_cost=cost_breakdown["completion_cost"],
                    rate=cost_breakdown["completion_rate"],
                    source=source,
                    tool_name=tool_name,
                    context=context,
                    created_at=current_time,
                )
                self.db.add(tx)
                transactions.append(tx)
                log.info(
                    f"Created completion transaction: user={user_id}, task={task_id}, "
                    f"tokens={completion_tokens}, cost={cost_breakdown['completion_cost']}, "
                    f"created_at={current_time}"
                )
            
            if cached_input_tokens > 0:
                tx = TokenTransactionModel(
                    user_id=user_id,
                    task_id=task_id,
                    transaction_type="cached",
                    model=model,
                    raw_tokens=cached_input_tokens,
                    token_cost=cost_breakdown["cached_cost"],
                    rate=cost_breakdown["cached_rate"],
                    source=source,
                    tool_name=tool_name,
                    context=context,
                    created_at=current_time,
                )
                self.db.add(tx)
                transactions.append(tx)
                log.info(
                    f"Created cached transaction: user={user_id}, task={task_id}, "
                    f"tokens={cached_input_tokens}, cost={cost_breakdown['cached_cost']}, "
                    f"created_at={current_time}"
                )
            
            # Update monthly usage
            self._update_monthly_usage(
                user_id=user_id,
                month=current_month,
                cost_breakdown=cost_breakdown,
                model=model,
                source=source,
                tool_name=tool_name,
            )
            
            self.db.commit()
            
            log.debug(
                f"Recorded token usage for user {user_id}: "
                f"model={model}, prompt={prompt_tokens}, "
                f"completion={completion_tokens}, cost={cost_breakdown['total_cost']}"
            )
            
            return {
                "success": True,
                "transactions": len(transactions),
                "total_cost": cost_breakdown["total_cost"],
                "cost_breakdown": cost_breakdown,
            }
            
        except Exception as e:
            self.db.rollback()
            log.error(f"Error recording token usage: {e}", exc_info=True)
            raise
    
    def _update_monthly_usage(
        self,
        user_id: str,
        month: str,
        cost_breakdown: Dict,
        model: str,
        source: str,
        tool_name: Optional[str],
    ) -> None:
        """Update monthly usage aggregates."""
        current_time = int(datetime.utcnow().timestamp() * 1000)
        
        # Get or create monthly usage record
        stmt = select(MonthlyUsageModel).where(
            MonthlyUsageModel.user_id == user_id,
            MonthlyUsageModel.month == month,
        )
        result = self.db.execute(stmt)
        usage_record = result.scalar_one_or_none()
        
        if not usage_record:
            usage_record = MonthlyUsageModel(
                user_id=user_id,
                month=month,
                total_usage=0,
                prompt_usage=0,
                completion_usage=0,
                cached_usage=0,
                usage_by_model={},
                usage_by_source={},
                created_at=current_time,
                updated_at=current_time,
            )
            self.db.add(usage_record)
            self.db.flush()
        
        # Update totals
        usage_record.total_usage += cost_breakdown["total_cost"]
        usage_record.prompt_usage += cost_breakdown["prompt_cost"]
        usage_record.completion_usage += cost_breakdown["completion_cost"]
        usage_record.cached_usage += cost_breakdown["cached_cost"]
        usage_record.updated_at = current_time
        
        # Update by_model breakdown
        if not usage_record.usage_by_model:
            usage_record.usage_by_model = {}
        usage_record.usage_by_model[model] = (
            usage_record.usage_by_model.get(model, 0) + cost_breakdown["total_cost"]
        )
        
        # Update by_source breakdown
        if not usage_record.usage_by_source:
            usage_record.usage_by_source = {}
        source_key = f"{source}:{tool_name}" if tool_name else source
        usage_record.usage_by_source[source_key] = (
            usage_record.usage_by_source.get(source_key, 0) + cost_breakdown["total_cost"]
        )
        
        # Mark as modified for JSONB columns
        flag_modified(usage_record, "usage_by_model")
        flag_modified(usage_record, "usage_by_source")
    
    def get_user_usage(
        self,
        user_id: str,
        month: Optional[str] = None,
    ) -> Dict:
        """
        Get usage summary for a user including raw token counts.
        
        Args:
            user_id: User identifier
            month: Month string (YYYY-MM), defaults to current month
            
        Returns:
            Usage summary dictionary with costs and token counts
        """
        if not month:
            month = datetime.utcnow().strftime("%Y-%m")
        
        # Get cost data from monthly_usage
        stmt = select(MonthlyUsageModel).where(
            MonthlyUsageModel.user_id == user_id,
            MonthlyUsageModel.month == month,
        )
        result = self.db.execute(stmt)
        usage_record = result.scalar_one_or_none()
        
        # Calculate raw token counts from transactions
        token_counts = self._get_token_counts_for_month(user_id, month)
        
        if not usage_record:
            return {
                "user_id": user_id,
                "month": month,
                "total_usage": 0,
                "prompt_usage": 0,
                "completion_usage": 0,
                "cached_usage": 0,
                "usage_by_model": {},
                "usage_by_source": {},
                "cost_usd": "$0.0000",
                "total_tokens": token_counts["total_tokens"],
                "prompt_tokens": token_counts["prompt_tokens"],
                "completion_tokens": token_counts["completion_tokens"],
                "cached_tokens": token_counts["cached_tokens"],
            }
        
        return {
            "user_id": usage_record.user_id,
            "month": usage_record.month,
            "total_usage": usage_record.total_usage,
            "prompt_usage": usage_record.prompt_usage,
            "completion_usage": usage_record.completion_usage,
            "cached_usage": usage_record.cached_usage,
            "usage_by_model": usage_record.usage_by_model or {},
            "usage_by_source": usage_record.usage_by_source or {},
            "cost_usd": self.calculator.format_cost_usd(usage_record.total_usage),
            "updated_at": usage_record.updated_at,
            "total_tokens": token_counts["total_tokens"],
            "prompt_tokens": token_counts["prompt_tokens"],
            "completion_tokens": token_counts["completion_tokens"],
            "cached_tokens": token_counts["cached_tokens"],
        }
    
    def _get_token_counts_for_month(
        self,
        user_id: str,
        month: str,
    ) -> Dict[str, int]:
        """
        Calculate raw token counts from transactions for a given month.
        
        Args:
            user_id: User identifier
            month: Month string (YYYY-MM)
            
        Returns:
            Dictionary with token counts by type
        """
        from sqlalchemy import func
        from datetime import datetime
        
        # Calculate month boundaries in epoch milliseconds
        year, month_num = map(int, month.split('-'))
        start_date = datetime(year, month_num, 1)
        if month_num == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month_num + 1, 1)
        
        start_ms = int(start_date.timestamp() * 1000)
        end_ms = int(end_date.timestamp() * 1000)
        
        # Query transactions for the month
        stmt = select(
            TokenTransactionModel.transaction_type,
            func.sum(TokenTransactionModel.raw_tokens).label('total')
        ).where(
            TokenTransactionModel.user_id == user_id,
            TokenTransactionModel.created_at >= start_ms,
            TokenTransactionModel.created_at < end_ms
        ).group_by(TokenTransactionModel.transaction_type)
        
        result = self.db.execute(stmt)
        rows = result.all()
        
        # Build token counts
        counts = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "cached_tokens": 0,
            "total_tokens": 0,
        }
        
        for row in rows:
            tx_type, total = row
            if tx_type == "prompt":
                counts["prompt_tokens"] = total or 0
            elif tx_type == "completion":
                counts["completion_tokens"] = total or 0
            elif tx_type == "cached":
                counts["cached_tokens"] = total or 0
        
        counts["total_tokens"] = (
            counts["prompt_tokens"] +
            counts["completion_tokens"] +
            counts["cached_tokens"]
        )
        
        return counts
    
    def get_usage_history(
        self,
        user_id: str,
        months: int = 6,
    ) -> list[Dict]:
        """
        Get historical usage for a user.
        
        Args:
            user_id: User identifier
            months: Number of months to retrieve
            
        Returns:
            List of monthly usage summaries
        """
        # Generate list of month strings
        current_date = datetime.utcnow()
        month_strings = []
        for i in range(months):
            # Calculate month offset
            year = current_date.year
            month = current_date.month - i
            while month <= 0:
                month += 12
                year -= 1
            month_strings.append(f"{year:04d}-{month:02d}")
        
        # Query all months
        stmt = select(MonthlyUsageModel).where(
            MonthlyUsageModel.user_id == user_id,
            MonthlyUsageModel.month.in_(month_strings),
        ).order_by(MonthlyUsageModel.month.desc())
        
        result = self.db.execute(stmt)
        records = result.scalars().all()
        
        # Convert to dict for easy lookup
        records_dict = {r.month: r for r in records}
        
        # Build response with all months (including zeros)
        history = []
        for month_str in month_strings:
            record = records_dict.get(month_str)
            if record:
                history.append({
                    "month": record.month,
                    "total_usage": record.total_usage,
                    "prompt_usage": record.prompt_usage,
                    "completion_usage": record.completion_usage,
                    "cached_usage": record.cached_usage,
                    "usage_by_model": record.usage_by_model or {},
                    "usage_by_source": record.usage_by_source or {},
                    "cost_usd": self.calculator.format_cost_usd(record.total_usage),
                })
            else:
                history.append({
                    "month": month_str,
                    "total_usage": 0,
                    "prompt_usage": 0,
                    "completion_usage": 0,
                    "cached_usage": 0,
                    "usage_by_model": {},
                    "usage_by_source": {},
                    "cost_usd": "$0.0000",
                })
        
        return history
    
    def get_transactions(
        self,
        user_id: str,
        task_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict:
        """
        Get transaction history for a user.
        
        Args:
            user_id: User identifier
            task_id: Optional task ID filter
            limit: Maximum number of transactions to return
            offset: Offset for pagination
            
        Returns:
            Dictionary with transactions and pagination info
        """
        # Build query
        stmt = select(TokenTransactionModel).where(
            TokenTransactionModel.user_id == user_id
        )
        
        if task_id:
            stmt = stmt.where(TokenTransactionModel.task_id == task_id)
        
        # Get total count
        from sqlalchemy import func
        count_stmt = select(func.count()).select_from(stmt.subquery())
        count_result = self.db.execute(count_stmt)
        total = count_result.scalar()
        
        log.info(
            f"get_transactions: user_id={user_id}, task_id={task_id}, "
            f"total_count={total}, limit={limit}, offset={offset}"
        )
        
        # Get paginated results
        stmt = stmt.order_by(TokenTransactionModel.created_at.desc())
        stmt = stmt.limit(limit).offset(offset)
        
        result = self.db.execute(stmt)
        transactions = result.scalars().all()
        
        log.info(f"get_transactions: Retrieved {len(transactions)} transaction records")
        if transactions:
            log.info(f"get_transactions: First transaction sample: id={transactions[0].id}, "
                    f"model={transactions[0].model}, tokens={transactions[0].raw_tokens}, "
                    f"created_at={transactions[0].created_at}")
        
        return {
            "transactions": [
                {
                    "id": tx.id,
                    "task_id": tx.task_id,
                    "transaction_type": tx.transaction_type,
                    "model": tx.model,
                    "raw_tokens": tx.raw_tokens,
                    "token_cost": tx.token_cost,
                    "cost_usd": self.calculator.format_cost_usd(tx.token_cost),
                    "rate": tx.rate,
                    "source": tx.source,
                    "tool_name": tx.tool_name,
                    "context": tx.context,
                    "created_at": tx.created_at,
                }
                for tx in transactions
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": (offset + len(transactions)) < total,
        }