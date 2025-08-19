"""
Session API controller using 3-tiered architecture.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Body
from solace_ai_connector.common.log import log

from ..dto.requests.session_requests import (
    GetSessionsRequest,
    GetSessionRequest,
    GetSessionHistoryRequest,
    UpdateSessionRequest,
    DeleteSessionRequest,
    CreateSessionRequest,
)
from ..dto.responses.session_responses import (
    SessionResponse,
    SessionListResponse,
    SessionHistoryResponse,
    SessionUpdatedResponse,
    MessageResponse,
)
from ...business.services.session_service import SessionService
from ...infrastructure.dependency_injection import get_session_service
from ...shared.types import SessionId, UserId

# Import the current user dependency from shared utilities
from ...shared.auth_utils import get_current_user

router = APIRouter()


@router.get("/sessions", response_model=SessionListResponse)
async def get_all_sessions(
    user: dict = Depends(get_current_user),
    session_service: SessionService = Depends(get_session_service),
):
    user_id = user.get("id")
    log.info("Fetching sessions for user_id: %s", user_id)
    
    try:
        request_dto = GetSessionsRequest(user_id=user_id)
        
        # Get sessions from business service
        session_domains = session_service.get_user_sessions(
            user_id=request_dto.user_id,
            pagination=request_dto.pagination
        )
        
        # Convert to response DTOs
        session_responses = []
        for domain in session_domains:
            session_response = SessionResponse(
                id=domain.id,
                user_id=domain.user_id,
                name=domain.name,
                agent_id=domain.agent_id,
                status=domain.status,
                created_at=domain.created_at,
                updated_at=domain.updated_at,
                last_activity=domain.last_activity
            )
            session_responses.append(session_response)
        
        # Return proper SessionListResponse structure
        return SessionListResponse(
            sessions=session_responses,
            total_count=len(session_responses),
            pagination=request_dto.pagination
        )
        
    except Exception as e:
        log.error("Error fetching sessions for user %s: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve sessions"
        )


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    user: dict = Depends(get_current_user),
    session_service: SessionService = Depends(get_session_service),
):
    user_id = user.get("id")
    log.info("User %s attempting to fetch session_id: %s", user_id, session_id)

    try:
        # Validate session_id input
        if not session_id or session_id.strip() == "" or session_id in ["null", "undefined"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found."
            )
        
        request_dto = GetSessionRequest(session_id=session_id, user_id=user_id)
        
        # Get session from business service
        session_domain = session_service.get_session(
            session_id=request_dto.session_id,
            user_id=request_dto.user_id
        )
        
        if not session_domain:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found."
            )

        log.info("User %s authorized. Fetching session_id: %s", user_id, session_id)
        
        # Convert to response DTO
        return SessionResponse(
            id=session_domain.id,
            user_id=session_domain.user_id,
            name=session_domain.name,
            agent_id=session_domain.agent_id,
            status=session_domain.status,
            created_at=session_domain.created_at,
            updated_at=session_domain.updated_at,
            last_activity=session_domain.last_activity
        )
        
    except HTTPException:
        raise
    except Exception as e:
        log.error("Error fetching session %s for user %s: %s", session_id, user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve session"
        )


@router.get("/sessions/{session_id}/messages")
async def get_session_history(
    session_id: str,
    user: dict = Depends(get_current_user),
    session_service: SessionService = Depends(get_session_service),
):
    user_id = user.get("id")
    log.info(
        "User %s attempting to fetch history for session_id: %s", user_id, session_id
    )

    try:
        # Validate session_id input
        if not session_id or session_id.strip() == "" or session_id in ["null", "undefined"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found."
            )
        
        request_dto = GetSessionHistoryRequest(session_id=session_id, user_id=user_id)
        
        # Get session history from business service
        history_domain = session_service.get_session_history(
            session_id=request_dto.session_id,
            user_id=request_dto.user_id,
            pagination=request_dto.pagination
        )
        
        if not history_domain:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found."
            )

        log.info(
            "User %s authorized. Fetching history for session_id: %s", user_id, session_id
        )
        
        # Convert messages to response DTOs
        message_responses = []
        for message_domain in history_domain.messages:
            message_response = MessageResponse(
                id=message_domain.id,
                session_id=message_domain.session_id,
                message=message_domain.message,
                sender_type=message_domain.sender_type,
                sender_name=message_domain.sender_name,
                message_type=message_domain.message_type,
                timestamp=message_domain.created_at,
                created_at=message_domain.created_at
            )
            message_responses.append(message_response)
        
        # Return direct array of messages for backward compatibility
        return message_responses
        
    except HTTPException:
        raise
    except Exception as e:
        log.error("Error fetching history for session %s for user %s: %s", session_id, user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve session history"
        )


@router.patch("/sessions/{session_id}", response_model=SessionResponse)
async def update_session_name(
    session_id: str,
    name: str = Body(..., embed=True),
    user: dict = Depends(get_current_user),
    session_service: SessionService = Depends(get_session_service),
):
    user_id = user.get("id")
    log.info("User %s attempting to update session %s", user_id, session_id)

    try:
        # Validate session_id input
        if not session_id or session_id.strip() == "" or session_id in ["null", "undefined"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found."
            )
        
        request_dto = UpdateSessionRequest(
            session_id=session_id,
            user_id=user_id,
            name=name
        )
        
        updated_domain = session_service.update_session_name(
            session_id=request_dto.session_id,
            user_id=request_dto.user_id,
            name=request_dto.name
        )
        
        if not updated_domain:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found."
            )

        log.info("Session %s updated successfully", session_id)
        
        # Convert to response DTO and return directly
        return SessionResponse(
            id=updated_domain.id,
            user_id=updated_domain.user_id,
            name=updated_domain.name,
            agent_id=updated_domain.agent_id,
            status=updated_domain.status,
            created_at=updated_domain.created_at,
            updated_at=updated_domain.updated_at,
            last_activity=updated_domain.last_activity
        )
        
    except HTTPException:
        raise
    except ValueError as e:
        log.warning("Validation error updating session %s: %s", session_id, e)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        log.error("Error updating session %s for user %s: %s", session_id, user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update session"
        )


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: str,
    user: dict = Depends(get_current_user),
    session_service: SessionService = Depends(get_session_service),
):
    user_id = user.get("id")
    log.info("User %s attempting to delete session %s", user_id, session_id)

    try:
        # Validate session_id input
        if not session_id or session_id.strip() == "" or session_id in ["null", "undefined"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found."
            )
        
        request_dto = DeleteSessionRequest(session_id=session_id, user_id=user_id)
        
        deleted = session_service.delete_session(
            session_id=request_dto.session_id,
            user_id=request_dto.user_id
        )
        
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found."
            )

        log.info("Session %s deleted successfully", session_id)
        
        # TODO: Add agent notification logic to a separate service/manager
        # This would handle the A2A messaging part
        
    except HTTPException:
        raise
    except Exception as e:
        log.error("Error deleting session %s for user %s: %s", session_id, user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete session"
        )