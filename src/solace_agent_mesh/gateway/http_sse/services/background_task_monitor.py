"""
Background Task Monitor Service.
Monitors background tasks and enforces timeouts.
Also handles recovery of orphaned tasks on startup.
"""

import logging
from typing import Callable
from sqlalchemy.orm import Session as DBSession

from ....gateway.http_sse.repository.task_repository import TaskRepository
from ....gateway.http_sse.services.task_service import TaskService
from ....gateway.http_sse.shared import now_epoch_ms

log = logging.getLogger(__name__)


class BackgroundTaskMonitor:
    """
    Monitors background tasks and enforces timeouts.
    Runs as a periodic background job in the gateway.
    Also handles recovery of orphaned tasks on startup.
    """

    def __init__(
        self,
        session_factory: Callable[[], DBSession],
        task_service: TaskService,
        default_timeout_ms: int = 3600000,  # 1 hour default
    ):
        """
        Initialize the background task monitor.
        
        Args:
            session_factory: Factory function to create database sessions
            task_service: TaskService instance for cancelling tasks
            default_timeout_ms: Default timeout in milliseconds if task doesn't specify one
        """
        self.session_factory = session_factory
        self.task_service = task_service
        self.default_timeout_ms = default_timeout_ms
        self.log_identifier = "[BackgroundTaskMonitor]"
        self._startup_recovery_done = False
        log.info(f"{self.log_identifier} Initialized with default timeout {default_timeout_ms}ms")

    def recover_orphaned_tasks(self) -> dict:
        """
        Mark all running background tasks as interrupted on startup.
        
        This should be called once during backend startup to handle tasks
        that were running when the backend crashed or was restarted.
        Tasks that were in "running" or "pending" state with no end_time
        are marked as "interrupted" since we can't know their actual state.
        
        Returns:
            Dictionary with statistics about the recovery
        """
        if self._startup_recovery_done:
            log.debug(f"{self.log_identifier} Startup recovery already done, skipping")
            return {"recovered": 0, "already_done": True}
        
        log.info(f"{self.log_identifier} Starting orphaned task recovery on startup")
        
        if not self.session_factory:
            log.warning(f"{self.log_identifier} No database session factory, skipping recovery")
            return {"recovered": 0, "error": "No database configured"}
        
        db = self.session_factory()
        try:
            repo = TaskRepository()
            current_time = now_epoch_ms()
            
            # Get all running background tasks (these are orphaned since we just started)
            running_tasks = repo.find_background_tasks_by_status(db, status=None)
            orphaned_tasks = [
                task for task in running_tasks
                if task.status in [None, "running", "pending"] and task.end_time is None
            ]
            
            log.info(
                f"{self.log_identifier} Found {len(orphaned_tasks)} orphaned background tasks to recover"
            )
            
            recovered_count = 0
            for task in orphaned_tasks:
                try:
                    # Mark task as interrupted
                    task.status = "interrupted"
                    task.end_time = current_time
                    repo.save_task(db, task)
                    recovered_count += 1
                    log.info(
                        f"{self.log_identifier} Marked orphaned task {task.id} as interrupted "
                        f"(was {task.status or 'running'}, started at {task.start_time})"
                    )
                except Exception as e:
                    log.error(
                        f"{self.log_identifier} Failed to recover task {task.id}: {e}",
                        exc_info=True
                    )
            
            db.commit()
            self._startup_recovery_done = True
            
            stats = {
                "found": len(orphaned_tasks),
                "recovered": recovered_count,
                "timestamp": current_time
            }
            
            if orphaned_tasks:
                log.info(
                    f"{self.log_identifier} Orphaned task recovery complete: "
                    f"found={stats['found']}, recovered={stats['recovered']}"
                )
            else:
                log.info(f"{self.log_identifier} No orphaned tasks found during startup recovery")
            
            return stats
            
        except Exception as e:
            log.error(
                f"{self.log_identifier} Error during orphaned task recovery: {e}",
                exc_info=True
            )
            db.rollback()
            return {"recovered": 0, "error": str(e)}
        finally:
            db.close()

    async def check_timeouts(self) -> dict:
        """
        Check for timed-out background tasks and cancel them.
        
        Returns:
            Dictionary with statistics about the check
        """
        log.debug(f"{self.log_identifier} Starting timeout check")
        
        if not self.session_factory:
            log.warning(f"{self.log_identifier} No database session factory, skipping timeout check")
            return {"checked": 0, "timed_out": 0, "cancelled": 0}
        
        db = self.session_factory()
        try:
            repo = TaskRepository()
            current_time = now_epoch_ms()
            
            # Get all running background tasks
            running_tasks = repo.find_background_tasks_by_status(db, status=None)
            running_tasks = [
                task for task in running_tasks
                if task.status in [None, "running", "pending"] and task.end_time is None
            ]
            
            log.debug(f"{self.log_identifier} Found {len(running_tasks)} running background tasks")
            
            timed_out_tasks = []
            
            for task in running_tasks:
                # Determine timeout for this task
                task_timeout = task.max_execution_time_ms or self.default_timeout_ms
                
                # Check if task has exceeded timeout based on last activity
                if task.last_activity_time:
                    time_since_activity = current_time - task.last_activity_time
                    if time_since_activity > task_timeout:
                        timed_out_tasks.append({
                            "task": task,
                            "timeout_ms": task_timeout,
                            "time_since_activity": time_since_activity
                        })
                        log.warning(
                            f"{self.log_identifier} Task {task.id} exceeded timeout: "
                            f"{time_since_activity}ms since last activity (timeout: {task_timeout}ms)"
                        )
            
            # Cancel timed-out tasks
            cancelled_count = 0
            for item in timed_out_tasks:
                task = item["task"]
                try:
                    # Extract agent name from task metadata or use a default
                    # In a real implementation, we'd need to store this in the task record
                    log.info(f"{self.log_identifier} Cancelling timed-out task {task.id}")
                    
                    # Update task status in database
                    task.status = "timeout"
                    task.end_time = current_time
                    repo.save_task(db, task)
                    
                    # Note: We can't easily cancel the actual agent task from here
                    # without knowing the agent name. This would require storing
                    # the agent name in the task record or having a different
                    # cancellation mechanism.
                    
                    cancelled_count += 1
                    log.info(f"{self.log_identifier} Marked task {task.id} as timed out")
                    
                except Exception as e:
                    log.error(
                        f"{self.log_identifier} Failed to cancel task {task.id}: {e}",
                        exc_info=True
                    )
            
            db.commit()
            
            stats = {
                "checked": len(running_tasks),
                "timed_out": len(timed_out_tasks),
                "cancelled": cancelled_count,
                "timestamp": current_time
            }
            
            if timed_out_tasks:
                log.info(
                    f"{self.log_identifier} Timeout check complete: "
                    f"checked={stats['checked']}, timed_out={stats['timed_out']}, "
                    f"cancelled={stats['cancelled']}"
                )
            else:
                log.debug(f"{self.log_identifier} Timeout check complete: no timeouts detected")
            
            return stats
            
        except Exception as e:
            log.error(
                f"{self.log_identifier} Error during timeout check: {e}",
                exc_info=True
            )
            db.rollback()
            return {"checked": 0, "timed_out": 0, "cancelled": 0, "error": str(e)}
        finally:
            db.close()

    async def get_background_task_stats(self) -> dict:
        """
        Get statistics about background tasks.
        
        Returns:
            Dictionary with task statistics
        """
        if not self.session_factory:
            return {"error": "No database configured"}
        
        db = self.session_factory()
        try:
            repo = TaskRepository()
            
            # Get all background tasks
            all_background = repo.find_background_tasks_by_status(db, status=None)
            
            # Count by status
            running = len([t for t in all_background if t.status in [None, "running", "pending"] and t.end_time is None])
            completed = len([t for t in all_background if t.status == "completed"])
            failed = len([t for t in all_background if t.status in ["failed", "error"]])
            cancelled = len([t for t in all_background if t.status == "cancelled"])
            timeout = len([t for t in all_background if t.status == "timeout"])
            interrupted = len([t for t in all_background if t.status == "interrupted"])
            
            return {
                "total": len(all_background),
                "running": running,
                "completed": completed,
                "failed": failed,
                "cancelled": cancelled,
                "timeout": timeout,
                "interrupted": interrupted,
                "timestamp": now_epoch_ms()
            }
            
        except Exception as e:
            log.error(f"{self.log_identifier} Error getting stats: {e}", exc_info=True)
            return {"error": str(e)}
        finally:
            db.close()