"""
API Router for managing user sessions.
"""

from fastapi import APIRouter, Depends, HTTPException, Request as FastAPIRequest, status
from typing import TYPE_CHECKING

from solace_ai_connector.common.log import log
from ....gateway.http_sse.session_manager import SessionManager
from ....gateway.http_sse.dependencies import get_session_manager
from ....common.types import JSONRPCResponse, InternalError

if TYPE_CHECKING:
    from ....gateway.http_sse.component import WebUIBackendComponent

router = APIRouter()


@router.post("/new", response_model=JSONRPCResponse)
async def create_new_session(
    request: FastAPIRequest,
    session_manager: SessionManager = Depends(get_session_manager),
):
    """
    Forces creation of a new A2A session, replacing any existing one.
    Returns the new session ID.
    """
    log_prefix = "[POST /api/v1/sessions/new] "
    log.info("%sReceived new session creation request", log_prefix)

    try:
        new_session_id = session_manager.start_new_a2a_session(request)

        log.info("%sCreated new A2A session: %s", log_prefix, new_session_id)

        return JSONRPCResponse(
            result={
                "sessionId": new_session_id,
                "message": "New A2A session created successfully",
            }
        )

    except Exception as e:
        log.exception("%sError creating new session: %s", log_prefix, e)
        error_resp = InternalError(message=f"Failed to create new session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_resp.model_dump(exclude_none=True),
        )


@router.get("/current", response_model=JSONRPCResponse)
async def get_current_session(
    request: FastAPIRequest,
    session_manager: SessionManager = Depends(get_session_manager),
):
    """
    Returns information about the current session.
    """
    log_prefix = "[GET /api/v1/sessions/current] "

    try:
        client_id = session_manager.get_a2a_client_id(request)
        session_id = session_manager.get_a2a_session_id(request)

        return JSONRPCResponse(
            result={
                "clientId": client_id,
                "sessionId": session_id,
                "hasActiveSession": session_id is not None,
            }
        )

    except Exception as e:
        log.exception("%sError getting current session info: %s", log_prefix, e)
        error_resp = InternalError(message=f"Failed to get session info: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_resp.model_dump(exclude_none=True),
        )
