"""
API Router for Server-Sent Events (SSE) subscriptions.
"""

import logging
import asyncio
import json
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, Request as FastAPIRequest, HTTPException, status, Query

from sse_starlette.sse import EventSourceResponse

from ....gateway.http_sse.sse_manager import SSEManager
from ....gateway.http_sse.dependencies import get_sse_manager, SessionLocal
from ....gateway.http_sse.repository.task_repository import TaskRepository

log = logging.getLogger(__name__)
trace_logger = logging.getLogger("sam_trace")


router = APIRouter()


def _prepare_replay_events(
    task_id: str,
    is_background_task: bool,
    last_event_timestamp: int,
    log_prefix: str
) -> List[Dict[str, Any]]:
    """
    Prepare events to replay for SSE reconnection using a short-lived database session.
    
    This function uses its own database session that is closed before returning,
    preventing the long-lived SSE connection from holding a database connection.
    
    Returns:
        List of event dictionaries with 'event' type and 'data' payload ready for SSE.
    """
    replay_events = []
    
    if SessionLocal is None:
        log.warning("%sDatabase not configured, cannot replay events", log_prefix)
        return replay_events
    
    replay_from_timestamp = last_event_timestamp if last_event_timestamp > 0 else 0
    
    # For background tasks, always replay from the beginning
    if is_background_task:
        replay_from_timestamp = 0
        log.info("%sBackground task reconnection - replaying ALL events from beginning", log_prefix)
    else:
        log.info("%sReplaying events since timestamp %d", log_prefix, replay_from_timestamp)
    
    # Use a short-lived database session
    db = SessionLocal()
    try:
        repo = TaskRepository()
        task_with_events = repo.find_by_id_with_events(db, task_id)
        
        if task_with_events:
            _, events = task_with_events
            # Use >= for timestamp 0 to include all events
            missed_events = [e for e in events if e.created_time > replay_from_timestamp]
            log.info("%sReplaying %d missed events", log_prefix, len(missed_events))
            
            # For background tasks, filter out intermediate artifact update events
            if is_background_task:
                has_final_response = any(
                    e.direction == "response" and
                    "result" in e.payload and
                    e.payload.get("result", {}).get("kind") == "task"
                    for e in missed_events
                )
                
                if has_final_response:
                    filtered_events = []
                    for e in missed_events:
                        if e.direction == "response" and "result" in e.payload:
                            result = e.payload.get("result", {})
                            if result.get("kind") == "artifact-update":
                                log.debug(
                                    "%sFiltering out intermediate artifact-update event during replay",
                                    log_prefix
                                )
                                continue
                        filtered_events.append(e)
                    missed_events = filtered_events
                    log.info(
                        "%sFiltered to %d events (removed intermediate artifact updates)",
                        log_prefix,
                        len(missed_events)
                    )
            
            # Convert events to SSE format
            for event in missed_events:
                event_type = "status_update"  # Default
                
                if event.direction == "response":
                    if "result" in event.payload:
                        result = event.payload.get("result", {})
                        if result.get("kind") == "task":
                            event_type = "final_response"
                        elif result.get("kind") == "status-update":
                            event_type = "status_update"
                        elif result.get("kind") == "artifact-update":
                            event_type = "artifact_update"
                
                replay_events.append({
                    "event": event_type,
                    "data": json.dumps(event.payload)
                })
        
        db.commit()
    except Exception as e:
        log.error("%sError preparing replay events: %s", log_prefix, e, exc_info=True)
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        try:
            db.close()
        except Exception:
            pass
    
    return replay_events


def _get_task_info(task_id: str, log_prefix: str) -> Optional[bool]:
    """
    Get task information using a short-lived database session.
    
    Returns:
        True if task is a background task, False if not, None if task not found or db not configured.
    """
    if SessionLocal is None:
        log.debug("%sDatabase not configured", log_prefix)
        return None
    
    db = SessionLocal()
    try:
        repo = TaskRepository()
        task = repo.find_by_id(db, task_id)
        is_background_task = task and task.background_execution_enabled if task else False
        db.commit()
        return is_background_task
    except Exception as e:
        log.error("%sError getting task info: %s", log_prefix, e, exc_info=True)
        try:
            db.rollback()
        except Exception:
            pass
        return None
    finally:
        try:
            db.close()
        except Exception:
            pass


@router.get("/subscribe/{task_id}")
async def subscribe_to_task_events(
    task_id: str,
    request: FastAPIRequest,
    reconnect: bool = Query(False, description="Whether this is a reconnection attempt"),
    last_event_timestamp: int = Query(0, description="Timestamp of last received event for replay"),
    sse_manager: SSEManager = Depends(get_sse_manager),
):
    """
    Establishes an SSE connection to receive real-time updates for a specific task.
    
    Note: This endpoint uses short-lived database sessions to avoid holding connections
    during the long-lived SSE stream, which could cause SSL connection timeouts.
    
    Args:
        task_id: The task to monitor
        reconnect: If true, replay missed events before streaming live
        last_event_timestamp: Timestamp of last received event (for replay)
    """
    log_prefix = "[GET /api/v1/sse/subscribe/%s] " % task_id
    log.debug("%sClient requesting SSE subscription (reconnect=%s).", log_prefix, reconnect)

    connection_queue: asyncio.Queue = None
    try:
        # Get task info using a short-lived database session
        # This closes the DB connection BEFORE the long-lived SSE stream starts
        is_background_task = _get_task_info(task_id, log_prefix)
        if is_background_task is None:
            is_background_task = False  # Default if task not found
        
        if is_background_task:
            log.info("%sTask %s is a background task.", log_prefix, task_id)
        
        # Prepare replay events using a short-lived database session
        # This also closes its DB connection before the SSE stream starts
        replay_events: List[Dict[str, Any]] = []
        if reconnect:
            replay_events = _prepare_replay_events(
                task_id, is_background_task, last_event_timestamp, log_prefix
            )
        
        connection_queue = await sse_manager.create_sse_connection(task_id)
        log.debug("%sSSE connection queue created.", log_prefix)

        async def event_generator():
            nonlocal connection_queue
            log.debug("%sSSE event generator started.", log_prefix)
            try:
                yield {"comment": "SSE connection established"}
                log.debug("%sSent initial SSE comment.", log_prefix)
                
                # Replay pre-fetched events (database session already closed)
                if replay_events:
                    for event in replay_events:
                        yield event
                    log.info("%sFinished replaying %d missed events", log_prefix, len(replay_events))

                loop_count = 0
                while True:
                    loop_count += 1
                    log.debug(
                        "%sEvent generator loop iteration: %d", log_prefix, loop_count
                    )

                    disconnected = await request.is_disconnected()
                    log.debug(
                        "%sRequest disconnected status: %s", log_prefix, disconnected
                    )
                    if disconnected:
                        if is_background_task:
                            log.info(
                                "%sClient disconnected from background task %s. Draining buffers and exiting SSE stream.",
                                log_prefix,
                                task_id
                            )
                            # For background tasks, we need to drain the buffers to prevent overflow
                            # The task will continue running, but we stop consuming events
                        else:
                            log.info("%sClient disconnected. Breaking loop.", log_prefix)
                        break

                    try:
                        log.debug("%sWaiting for event from queue...", log_prefix)
                        event_payload = await asyncio.wait_for(
                            connection_queue.get(), timeout=120
                        )
                        log.debug(
                            "%sReceived from queue: %s",
                            log_prefix,
                            event_payload is not None,
                        )

                        if event_payload is None:
                            log.info(
                                "%sReceived None sentinel. Closing connection. Breaking loop.",
                                log_prefix,
                            )
                            break
                        if trace_logger.isEnabledFor(logging.DEBUG):
                            trace_logger.debug(
                                "%sYielding event_payload: %s",
                                log_prefix, event_payload
                            )
                        else:
                            log.debug(
                                "%sYielding event: %s",
                                log_prefix,
                                event_payload.get("event") if event_payload else "unknown"
                            )
                        yield event_payload
                        connection_queue.task_done()
                        log.debug(
                            "%sSent event: %s", log_prefix, event_payload.get("event")
                        )

                    except asyncio.TimeoutError:
                        log.debug(
                            "%sSSE queue wait timed out (iteration %d), checking disconnect status.",
                            log_prefix,
                            loop_count,
                        )
                        continue
                    except asyncio.CancelledError:
                        log.info(
                            "%sSSE event generator cancelled. Breaking loop.",
                            log_prefix,
                        )
                        break
                    except Exception as q_err:
                        log.error(
                            "%sError getting event from queue: %s. Breaking loop.",
                            log_prefix,
                            q_err,
                            exc_info=True,
                        )
                        yield {
                            "event": "error",
                            "data": json.dumps({"error": "Internal queue error"}),
                        }
                        break

            except asyncio.CancelledError:
                log.info(
                    "%sSSE event generator explicitly cancelled. Breaking loop.",
                    log_prefix,
                )
            except Exception as gen_err:
                log.error(
                    "%sError in SSE event generator: %s",
                    log_prefix,
                    gen_err,
                    exc_info=True,
                )
            finally:
                log.info("%sSSE event generator finished.", log_prefix)
                if connection_queue:
                    await sse_manager.remove_sse_connection(task_id, connection_queue)
                    log.info("%sRemoved SSE connection queue from manager.", log_prefix)
                    
                    # If this was a background task, drain the buffer to prevent overflow
                    if is_background_task:
                        await sse_manager.drain_buffer_for_background_task(task_id)
                        log.info("%sDrained buffer for background task %s", log_prefix, task_id)

        return EventSourceResponse(event_generator())

    except Exception as e:
        log.exception("%sError establishing SSE connection: %s", log_prefix, e)

        if connection_queue:
            await sse_manager.remove_sse_connection(task_id, connection_queue)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to establish SSE connection: %s" % e,
        )
