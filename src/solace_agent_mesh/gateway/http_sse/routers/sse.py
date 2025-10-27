"""
API Router for Server-Sent Events (SSE) subscriptions.
"""

import logging
import asyncio
import json
from fastapi import APIRouter, Depends, Request as FastAPIRequest, HTTPException, status

from sse_starlette.sse import EventSourceResponse

from ....gateway.http_sse.sse_manager import SSEManager
from ....gateway.http_sse.dependencies import get_sse_manager

log = logging.getLogger(__name__)
trace_logger = logging.getLogger("sam_trace")


router = APIRouter()


@router.get("/subscribe/{task_id}")
async def subscribe_to_task_events(
    task_id: str,
    request: FastAPIRequest,
    sse_manager: SSEManager = Depends(get_sse_manager),
):
    """
    Establishes an SSE connection to receive real-time updates for a specific task.
    """
    log_prefix = "[GET /api/v1/sse/subscribe/%s] " % task_id
    log.debug("%sClient requesting SSE subscription.", log_prefix)

    connection_queue: asyncio.Queue = None
    try:
        connection_queue = await sse_manager.create_sse_connection(task_id)
        log.debug("%sSSE connection queue created.", log_prefix)

        async def event_generator():
            nonlocal connection_queue
            log.debug("%sSSE event generator started.", log_prefix)
            try:
                yield {"comment": "SSE connection established"}
                log.debug("%sSent initial SSE comment.", log_prefix)

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

        return EventSourceResponse(event_generator())

    except Exception as e:
        log.exception("%sError establishing SSE connection: %s", log_prefix, e)

        if connection_queue:
            await sse_manager.remove_sse_connection(task_id, connection_queue)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to establish SSE connection: %s" % e,
        )
