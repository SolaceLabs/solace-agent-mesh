from fastapi import APIRouter, Body, Depends, HTTPException, status
from fastapi import Request as FastAPIRequest
from solace_ai_connector.common.log import log

from a2a.types import JSONRPCSuccessResponse
from ..dependencies import get_session_business_service, get_session_manager
from ..services.session_service import SessionService
from ..session_manager import SessionManager
from ..shared.auth_utils import get_current_user
from .dto.requests.session_requests import (
    GetSessionHistoryRequest,
    GetSessionRequest,
    GetSessionsRequest,
    UpdateSessionRequest,
)
from .dto.responses.session_responses import (
    MessageResponse,
    SessionListResponse,
    SessionResponse,
)
from ....common.a2a import create_generic_success_response

router = APIRouter()


@router.post("/sessions/new", response_model=JSONRPCSuccessResponse)
async def create_new_session(
    request: FastAPIRequest,
    user: dict = Depends(get_current_user),
    session_manager: SessionManager = Depends(get_session_manager),
    session_service: SessionService = Depends(get_session_business_service),
):
    """Creates a new session on-demand and returns its ID."""
    user_id = user.get("id")
    log.info("User %s requesting new session", user_id)
    try:
        new_session_id = session_manager.create_new_session_id(request)
        log.info("Created new session ID: %s for user %s", new_session_id, user_id)

        # Attempt to create the session record in the DB.
        # The service will handle the check for whether persistence is enabled.
        session_service.create_session(
            user_id=user_id,
            agent_id=None,  # Agent is not known at this point
            name=None,
            session_id=new_session_id,
        )

        return create_generic_success_response(
            result={"id": new_session_id}, request_id=None
        )
    except Exception as e:
        log.error("Error creating new session for user %s: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create a new session",
        )


@router.get("/sessions", response_model=SessionListResponse)
async def get_all_sessions(
    user: dict = Depends(get_current_user),
    session_service: SessionService = Depends(get_session_business_service),
):
    user_id = user.get("id")
    log.info("Fetching sessions for user_id: %s", user_id)

    try:
        request_dto = GetSessionsRequest(user_id=user_id)

        session_domains = session_service.get_user_sessions(
            user_id=request_dto.user_id, pagination=request_dto.pagination
        )

        session_responses = []
        for domain in session_domains:
            session_response = SessionResponse(
                id=domain.id,
                user_id=domain.user_id,
                name=domain.name,
                agent_id=domain.agent_id,
                created_time=domain.created_time,
                updated_time=domain.updated_time,
            )
            session_responses.append(session_response)

        return SessionListResponse(
            sessions=session_responses,
            total_count=len(session_responses),
            pagination=request_dto.pagination,
        )

    except Exception as e:
        log.error("Error fetching sessions for user %s: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve sessions",
        )


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    user: dict = Depends(get_current_user),
    session_service: SessionService = Depends(get_session_business_service),
):
    user_id = user.get("id")
    log.info("User %s attempting to fetch session_id: %s", user_id, session_id)

    try:
        if (
            not session_id
            or session_id.strip() == ""
            or session_id in ["null", "undefined"]
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Session not found."
            )

        request_dto = GetSessionRequest(session_id=session_id, user_id=user_id)

        session_domain = session_service.get_session_details(
            session_id=request_dto.session_id, user_id=request_dto.user_id
        )

        if not session_domain:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Session not found."
            )

        log.info("User %s authorized. Fetching session_id: %s", user_id, session_id)

        return SessionResponse(
            id=session_domain.id,
            user_id=session_domain.user_id,
            name=session_domain.name,
            agent_id=session_domain.agent_id,
            created_time=session_domain.created_time,
            updated_time=session_domain.updated_time,
        )

    except HTTPException:
        raise
    except Exception as e:
        log.error(
            "Error fetching session %s for user %s: %s",
            session_id,
            user_id,
            e,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve session",
        )


@router.get("/sessions/{session_id}/messages")
async def get_session_history(
    session_id: str,
    user: dict = Depends(get_current_user),
    session_service: SessionService = Depends(get_session_business_service),
):
    user_id = user.get("id")
    log.info(
        "User %s attempting to fetch history for session_id: %s", user_id, session_id
    )

    try:
        if (
            not session_id
            or session_id.strip() == ""
            or session_id in ["null", "undefined"]
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Session not found."
            )

        request_dto = GetSessionHistoryRequest(session_id=session_id, user_id=user_id)

        history_domain = session_service.get_session_history(
            session_id=request_dto.session_id,
            user_id=request_dto.user_id,
            pagination=request_dto.pagination,
        )

        if not history_domain:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Session not found."
            )

        log.info(
            "User %s authorized. Fetching history for session_id: %s",
            user_id,
            session_id,
        )

        message_responses = []
        for message_domain in history_domain.messages:
            message_response = MessageResponse(
                id=message_domain.id,
                session_id=message_domain.session_id,
                message=message_domain.message,
                sender_type=message_domain.sender_type,
                sender_name=message_domain.sender_name,
                message_type=message_domain.message_type,
                created_time=message_domain.created_time,
            )
            message_responses.append(message_response)

        return message_responses

    except HTTPException:
        raise
    except Exception as e:
        log.error(
            "Error fetching history for session %s for user %s: %s",
            session_id,
            user_id,
            e,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve session history",
        )


@router.patch("/sessions/{session_id}", response_model=SessionResponse)
async def update_session_name(
    session_id: str,
    name: str = Body(..., embed=True),
    user: dict = Depends(get_current_user),
    session_service: SessionService = Depends(get_session_business_service),
):
    user_id = user.get("id")
    log.info("User %s attempting to update session %s", user_id, session_id)

    try:
        if (
            not session_id
            or session_id.strip() == ""
            or session_id in ["null", "undefined"]
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Session not found."
            )

        request_dto = UpdateSessionRequest(
            session_id=session_id, user_id=user_id, name=name
        )

        updated_domain = session_service.update_session_name(
            session_id=request_dto.session_id,
            user_id=request_dto.user_id,
            name=request_dto.name,
        )

        if not updated_domain:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Session not found."
            )

        log.info("Session %s updated successfully", session_id)

        return SessionResponse(
            id=updated_domain.id,
            user_id=updated_domain.user_id,
            name=updated_domain.name,
            agent_id=updated_domain.agent_id,
            created_time=updated_domain.created_time,
            updated_time=updated_domain.updated_time,
        )

    except HTTPException:
        raise
    except ValueError as e:
        log.warning("Validation error updating session %s: %s", session_id, e)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        )
    except Exception as e:
        log.error(
            "Error updating session %s for user %s: %s",
            session_id,
            user_id,
            e,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update session",
        )


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: str,
    user: dict = Depends(get_current_user),
    session_service: SessionService = Depends(get_session_business_service),
):
    user_id = user.get("id")
    log.info("User %s attempting to delete session %s", user_id, session_id)

    try:
        deleted = session_service.delete_session_with_notifications(
            session_id=session_id, user_id=user_id
        )

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Session not found."
            )

        log.info("Session %s deleted successfully", session_id)

    except ValueError as e:
        log.warning("Validation error deleting session %s: %s", session_id, e)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        log.error(
            "Error deleting session %s for user %s: %s",
            session_id,
            user_id,
            e,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete session",
        )
