"""
Slow dependency injection framework for stress testing.

Allows injecting artificial latency into database and network operations
to test how the system behaves when dependencies are slow.

This is critical for detecting synchronous blocking issues like the
504 timeout caused by synchronous database writes.
"""

import time
import threading
import functools
import logging
from typing import Callable, Optional, Dict, Any, List
from contextlib import contextmanager
from dataclasses import dataclass, field
from unittest.mock import patch, MagicMock

logger = logging.getLogger(__name__)


@dataclass
class InjectionConfig:
    """Configuration for a single latency injection."""
    
    target: str  # Module/function path to inject
    latency_ms: float  # Latency to inject in milliseconds
    probability: float = 1.0  # Probability of injection (0-1)
    max_injections: Optional[int] = None  # Max number of injections (None = unlimited)
    injection_count: int = field(default=0, init=False)


class SlowDependencyInjector:
    """
    Inject artificial latency into dependencies to test
    how the system behaves when things are slow.
    
    Usage:
        injector = SlowDependencyInjector(metrics_collector)
        
        # Inject 500ms latency into DB commits
        with injector.inject_db_latency(500):
            await run_test()
        
        # Inject into specific SQLAlchemy operations
        with injector.inject_sqlalchemy_latency(latency_ms=200, operations=['commit', 'flush']):
            await run_test()
    """
    
    def __init__(self, metrics_collector: Optional[Any] = None):
        self.metrics = metrics_collector
        self._active_patches: List[Any] = []
        self._lock = threading.Lock()
        self._injection_stats: Dict[str, int] = {}
    
    @contextmanager
    def inject_db_latency(
        self,
        latency_ms: float,
        probability: float = 1.0,
    ):
        """
        Inject latency into database commit operations.
        
        This simulates slow database writes which was the root cause
        of the 504 timeout issue.
        
        Args:
            latency_ms: Latency to add in milliseconds
            probability: Probability of injection per call (0-1)
        """
        import random
        
        original_commit = None
        
        def slow_commit(session_self, *args, **kwargs):
            """Wrapper that adds latency before commit."""
            if random.random() < probability:
                delay_sec = latency_ms / 1000
                logger.debug(f"Injecting {latency_ms}ms DB commit latency")
                time.sleep(delay_sec)
                
                with self._lock:
                    self._injection_stats["db_commit"] = self._injection_stats.get("db_commit", 0) + 1
                
                if self.metrics:
                    try:
                        # Use sync version since we're in a non-async context
                        self.metrics.increment_counter_sync("injected_db_latency")
                    except Exception:
                        pass
            
            return original_commit(session_self, *args, **kwargs)
        
        try:
            # Patch SQLAlchemy Session.commit
            from sqlalchemy.orm import Session
            original_commit = Session.commit
            Session.commit = slow_commit
            
            logger.info(f"Injecting {latency_ms}ms DB commit latency")
            yield self
            
        finally:
            # Restore original
            if original_commit:
                from sqlalchemy.orm import Session
                Session.commit = original_commit
            logger.info("Removed DB commit latency injection")
    
    @contextmanager
    def inject_sqlalchemy_latency(
        self,
        latency_ms: float,
        operations: List[str] = None,
        probability: float = 1.0,
    ):
        """
        Inject latency into specific SQLAlchemy operations.
        
        Args:
            latency_ms: Latency to add in milliseconds
            operations: List of operations to slow (commit, flush, execute, etc.)
            probability: Probability of injection per call (0-1)
        """
        import random
        
        operations = operations or ["commit", "flush"]
        original_methods = {}
        
        def make_slow_method(op_name: str, original: Callable):
            """Create a slow wrapper for a method."""
            @functools.wraps(original)
            def slow_method(self, *args, **kwargs):
                if random.random() < probability:
                    delay_sec = latency_ms / 1000
                    logger.debug(f"Injecting {latency_ms}ms latency into {op_name}")
                    time.sleep(delay_sec)
                    
                    with self._lock:
                        stat_key = f"sqlalchemy_{op_name}"
                        self._injection_stats[stat_key] = self._injection_stats.get(stat_key, 0) + 1
                
                return original(self, *args, **kwargs)
            return slow_method
        
        try:
            from sqlalchemy.orm import Session
            
            for op in operations:
                if hasattr(Session, op):
                    original = getattr(Session, op)
                    original_methods[op] = original
                    setattr(Session, op, make_slow_method(op, original))
            
            logger.info(f"Injecting {latency_ms}ms latency into SQLAlchemy: {operations}")
            yield self
            
        finally:
            # Restore originals
            from sqlalchemy.orm import Session
            for op, original in original_methods.items():
                setattr(Session, op, original)
            logger.info(f"Removed SQLAlchemy latency injection from: {list(original_methods.keys())}")
    
    @contextmanager
    def inject_network_latency(
        self,
        latency_ms: float,
        targets: List[str] = None,
    ):
        """
        Inject latency into HTTP/network calls.
        
        Args:
            latency_ms: Latency to add in milliseconds
            targets: URL patterns to match (None = all)
        """
        import httpx
        
        original_request = None
        
        async def slow_request(self, method, url, *args, **kwargs):
            """Async wrapper that adds latency."""
            import asyncio
            
            should_inject = targets is None or any(t in str(url) for t in targets)
            
            if should_inject:
                logger.debug(f"Injecting {latency_ms}ms network latency for {url}")
                await asyncio.sleep(latency_ms / 1000)
                
                with self._lock:
                    self._injection_stats["network"] = self._injection_stats.get("network", 0) + 1
            
            return await original_request(self, method, url, *args, **kwargs)
        
        try:
            original_request = httpx.AsyncClient.request
            httpx.AsyncClient.request = slow_request
            
            logger.info(f"Injecting {latency_ms}ms network latency")
            yield self
            
        finally:
            if original_request:
                httpx.AsyncClient.request = original_request
            logger.info("Removed network latency injection")
    
    @contextmanager
    def inject_thread_sleep(
        self,
        target_function: str,
        latency_ms: float,
    ):
        """
        Inject a sleep into a specific function.
        
        This is a more targeted injection for specific code paths.
        
        Args:
            target_function: Full path to function (e.g., 'module.submodule.function')
            latency_ms: Sleep duration in milliseconds
        """
        module_path, func_name = target_function.rsplit('.', 1)
        
        original_func = None
        
        def slow_wrapper(*args, **kwargs):
            """Wrapper that adds sleep."""
            time.sleep(latency_ms / 1000)
            with self._lock:
                self._injection_stats[target_function] = self._injection_stats.get(target_function, 0) + 1
            return original_func(*args, **kwargs)
        
        try:
            import importlib
            module = importlib.import_module(module_path)
            original_func = getattr(module, func_name)
            setattr(module, func_name, slow_wrapper)
            
            logger.info(f"Injecting {latency_ms}ms sleep into {target_function}")
            yield self
            
        finally:
            if original_func:
                import importlib
                module = importlib.import_module(module_path)
                setattr(module, func_name, original_func)
            logger.info(f"Removed sleep injection from {target_function}")
    
    def get_injection_stats(self) -> Dict[str, int]:
        """Get statistics about injections that occurred."""
        with self._lock:
            return dict(self._injection_stats)
    
    def reset_stats(self):
        """Reset injection statistics."""
        with self._lock:
            self._injection_stats.clear()


class BufferWriteLatencyInjector:
    """
    Specialized injector for the PersistentSSEEventBuffer.
    
    Simulates the slow database write scenario that caused the 504 timeout.
    """
    
    def __init__(self, metrics_collector: Optional[Any] = None):
        self.metrics = metrics_collector
        self._write_count = 0
        self._lock = threading.Lock()
    
    @contextmanager
    def inject_buffer_write_latency(self, latency_ms: float):
        """
        Inject latency into SSE event buffer database writes.
        
        This directly targets the code path that caused the 504:
        - PersistentSSEEventBuffer.buffer_event() calling repository.buffer_event()
        
        Args:
            latency_ms: Latency to add to each buffer write
        """
        from unittest.mock import patch
        
        original_buffer_event = None
        
        def slow_buffer_event(repo_self, db, task_id, session_id, user_id, event_type, event_payload, consumed):
            """Wrapper that adds latency to buffer writes."""
            time.sleep(latency_ms / 1000)
            
            with self._lock:
                self._write_count += 1
            
            logger.debug(f"Injected {latency_ms}ms latency on buffer write #{self._write_count}")
            
            return original_buffer_event(repo_self, db, task_id, session_id, user_id, event_type, event_payload, consumed)
        
        try:
            from solace_agent_mesh.gateway.http_sse.repository.sse_event_buffer_repository import SSEEventBufferRepository
            original_buffer_event = SSEEventBufferRepository.buffer_event
            SSEEventBufferRepository.buffer_event = slow_buffer_event
            
            logger.info(f"Injecting {latency_ms}ms latency into SSE buffer writes")
            yield self
            
        finally:
            if original_buffer_event:
                from solace_agent_mesh.gateway.http_sse.repository.sse_event_buffer_repository import SSEEventBufferRepository
                SSEEventBufferRepository.buffer_event = original_buffer_event
            logger.info(f"Removed buffer write latency injection (total writes: {self._write_count})")
    
    def get_write_count(self) -> int:
        """Get the number of writes that were slowed."""
        with self._lock:
            return self._write_count
    
    def reset(self):
        """Reset write count."""
        with self._lock:
            self._write_count = 0
