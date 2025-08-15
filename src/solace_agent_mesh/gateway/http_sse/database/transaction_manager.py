"""
Transaction management utilities for database operations.

Provides context managers and decorators for handling database transactions,
rollbacks, retries, and error handling in a consistent way.
"""

import time
import logging
from contextlib import contextmanager
from typing import Optional, Type, Tuple, Callable, Any, Generator
from functools import wraps
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.exc import (
    IntegrityError,
    OperationalError,
    DatabaseError,
    DisconnectionError,
    TimeoutError as SQLTimeoutError,
    DataError,
    SQLAlchemyError
)

logger = logging.getLogger(__name__)


class TransactionError(Exception):
    """Base class for transaction-related errors."""
    
    def __init__(self, message: str, original_error: Optional[Exception] = None):
        super().__init__(message)
        self.original_error = original_error


class RetriableTransactionError(TransactionError):
    """Error that indicates the transaction can be retried."""
    pass


class NonRetriableTransactionError(TransactionError):
    """Error that indicates the transaction should not be retried."""
    pass


class TransactionManager:
    """
    Manages database transactions with automatic rollback, retry logic,
    and comprehensive error handling.
    """
    
    def __init__(self, session_factory: sessionmaker, default_timeout: float = 30.0):
        """
        Initialize the transaction manager.
        
        Args:
            session_factory: SQLAlchemy sessionmaker instance
            default_timeout: Default timeout for transactions in seconds
        """
        self.session_factory = session_factory
        self.default_timeout = default_timeout
        
    @contextmanager
    def transaction(
        self, 
        timeout: Optional[float] = None,
        read_only: bool = False,
        isolation_level: Optional[str] = None
    ) -> Generator[Session, None, None]:
        """
        Context manager for database transactions with automatic rollback.
        
        Args:
            timeout: Transaction timeout in seconds
            read_only: Whether this is a read-only transaction
            isolation_level: Transaction isolation level
            
        Yields:
            SQLAlchemy session object
            
        Raises:
            TransactionError: On transaction failures
        """
        session = self.session_factory()
        timeout = timeout or self.default_timeout
        start_time = time.time()
        
        try:
            # Set isolation level if specified
            if isolation_level:
                session.execute(f"SET TRANSACTION ISOLATION LEVEL {isolation_level}")
            
            # For read-only transactions, we can skip begin/commit
            if not read_only:
                session.begin()
            
            logger.debug("Transaction started (read_only=%s, timeout=%s)", read_only, timeout)
            
            yield session
            
            # Check for timeout
            elapsed = time.time() - start_time
            if elapsed > timeout:
                raise TransactionError(f"Transaction timeout after {elapsed:.2f} seconds")
            
            # Commit if not read-only
            if not read_only:
                session.commit()
                logger.debug("Transaction committed successfully (elapsed=%.2fs)", elapsed)
            else:
                logger.debug("Read-only transaction completed (elapsed=%.2fs)", elapsed)
                
        except Exception as e:
            # Rollback on any exception
            if not read_only:
                try:
                    session.rollback()
                    logger.debug("Transaction rolled back due to error: %s", str(e))
                except Exception as rollback_error:
                    logger.error("Failed to rollback transaction: %s", str(rollback_error))
            
            # Re-raise as appropriate transaction error
            raise self._classify_error(e)
            
        finally:
            session.close()
    
    def _classify_error(self, error: Exception) -> TransactionError:
        """
        Classify database errors into retriable or non-retriable categories.
        
        Args:
            error: The original database error
            
        Returns:
            Appropriate TransactionError subclass
        """
        error_msg = str(error)
        
        # Retriable errors (connection issues, deadlocks, timeouts)
        if isinstance(error, (OperationalError, DisconnectionError, SQLTimeoutError)):
            return RetriableTransactionError(
                f"Retriable database error: {error_msg}", 
                original_error=error
            )
        
        # Check for specific retriable error patterns
        retriable_patterns = [
            "deadlock detected",
            "lock wait timeout exceeded",
            "connection lost",
            "server has gone away",
            "too many connections"
        ]
        
        if any(pattern in error_msg.lower() for pattern in retriable_patterns):
            return RetriableTransactionError(
                f"Retriable database error: {error_msg}",
                original_error=error
            )
        
        # Non-retriable errors (data integrity, constraint violations)
        if isinstance(error, (IntegrityError, DataError)):
            return NonRetriableTransactionError(
                f"Data integrity error: {error_msg}",
                original_error=error
            )
        
        # Default to non-retriable for unknown errors
        return NonRetriableTransactionError(
            f"Unknown database error: {error_msg}",
            original_error=error
        )
    
    @contextmanager
    def savepoint(self, session: Session, name: Optional[str] = None) -> Generator[str, None, None]:
        """
        Context manager for database savepoints (nested transactions).
        
        Args:
            session: Active database session
            name: Optional savepoint name
            
        Yields:
            Savepoint name
        """
        import uuid
        savepoint_name = name or f"sp_{uuid.uuid4().hex[:8]}"
        
        try:
            session.begin_nested()  # Create savepoint
            logger.debug("Savepoint '%s' created", savepoint_name)
            yield savepoint_name
            
        except Exception as e:
            logger.debug("Rolling back to savepoint '%s' due to error: %s", savepoint_name, str(e))
            session.rollback()  # Rollback to savepoint
            raise
            
        else:
            logger.debug("Savepoint '%s' completed successfully", savepoint_name)


class RetryManager:
    """
    Manages retry logic for database operations with exponential backoff.
    """
    
    def __init__(
        self,
        max_retries: int = 3,
        initial_delay: float = 0.1,
        max_delay: float = 5.0,
        backoff_factor: float = 2.0
    ):
        """
        Initialize the retry manager.
        
        Args:
            max_retries: Maximum number of retry attempts
            initial_delay: Initial delay between retries in seconds
            max_delay: Maximum delay between retries in seconds
            backoff_factor: Exponential backoff multiplier
        """
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
    
    def retry_operation(self, operation: Callable, *args, **kwargs) -> Any:
        """
        Execute an operation with retry logic.
        
        Args:
            operation: Function to execute
            *args: Positional arguments for the operation
            **kwargs: Keyword arguments for the operation
            
        Returns:
            Result of the operation
            
        Raises:
            TransactionError: After all retry attempts fail
        """
        last_error = None
        delay = self.initial_delay
        
        for attempt in range(self.max_retries + 1):
            try:
                if attempt > 0:
                    logger.info("Retrying operation (attempt %d/%d)", attempt + 1, self.max_retries + 1)
                    time.sleep(delay)
                    delay = min(delay * self.backoff_factor, self.max_delay)
                
                return operation(*args, **kwargs)
                
            except RetriableTransactionError as e:
                last_error = e
                logger.warning(
                    "Retriable error on attempt %d/%d: %s", 
                    attempt + 1, self.max_retries + 1, str(e)
                )
                continue
                
            except NonRetriableTransactionError as e:
                logger.error("Non-retriable error, stopping retries: %s", str(e))
                raise e
        
        # All retries exhausted
        logger.error("All retry attempts exhausted. Last error: %s", str(last_error))
        raise TransactionError(
            f"Operation failed after {self.max_retries + 1} attempts",
            original_error=last_error
        )


def atomic_operation(
    max_retries: int = 3,
    timeout: float = 30.0,
    read_only: bool = False,
    isolation_level: Optional[str] = None
):
    """
    Decorator for atomic database operations with retry logic.
    
    Args:
        max_retries: Maximum number of retry attempts
        timeout: Transaction timeout in seconds
        read_only: Whether this is a read-only operation
        isolation_level: Transaction isolation level
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            # Assume the first argument is a service instance with transaction_manager
            if not hasattr(self, 'transaction_manager'):
                raise AttributeError(
                    f"{self.__class__.__name__} must have a 'transaction_manager' attribute "
                    "to use @atomic_operation decorator"
                )
            
            transaction_manager: TransactionManager = self.transaction_manager
            retry_manager = RetryManager(max_retries=max_retries)
            
            def operation():
                with transaction_manager.transaction(
                    timeout=timeout,
                    read_only=read_only,
                    isolation_level=isolation_level
                ) as session:
                    # Inject session as first argument
                    return func(self, session, *args, **kwargs)
            
            return retry_manager.retry_operation(operation)
        
        return wrapper
    return decorator


def handle_database_errors(
    retriable_errors: Tuple[Type[Exception], ...] = (OperationalError, DisconnectionError),
    non_retriable_errors: Tuple[Type[Exception], ...] = (IntegrityError, DataError)
):
    """
    Decorator for handling specific database errors.
    
    Args:
        retriable_errors: Tuple of exception types that can be retried
        non_retriable_errors: Tuple of exception types that should not be retried
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except retriable_errors as e:
                raise RetriableTransactionError(str(e), original_error=e)
            except non_retriable_errors as e:
                raise NonRetriableTransactionError(str(e), original_error=e)
            except SQLAlchemyError as e:
                # Default SQLAlchemy errors to non-retriable
                raise NonRetriableTransactionError(str(e), original_error=e)
        
        return wrapper
    return decorator