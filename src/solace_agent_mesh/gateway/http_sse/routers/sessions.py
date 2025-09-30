from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from solace_ai_connector.common.log import log
from sqlalchemy.orm import Session

from ..dependencies import get_session_business_service, get_db
from ..services.session_service import SessionService
from ..shared.auth_utils import get_current_user
from ..shared.pagination import DataResponse, PaginatedResponse, PaginationParams
from ..shared.response_utils import create_data_response
from .dto.requests.session_requests import (
    GetSessionHistoryRequest,
    GetSessionRequest,
    UpdateSessionRequest,
)
from .dto.responses.session_responses import MessageResponse, SessionResponse

router = APIRouter()



@router.get("/sessions", response_model=PaginatedResponse[SessionResponse])
async def get_all_sessions(
    page_number: int = Query(default=1, ge=1, alias="pageNumber"),
    page_size: int = Query(default=20, ge=1, le=100, alias="pageSize"),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    session_service: SessionService = Depends(get_session_business_service),
):
    user_id = user.get("id")
    log.info(f"User '{user_id}' is listing sessions with pagination (page={page_number}, size={page_size})")

    try:
        pagination = PaginationParams(page_number=page_number, page_size=page_size)
        paginated_response = session_service.get_user_sessions(db, user_id, pagination)

        session_responses = []
        for session_domain in paginated_response.data:
            session_response = SessionResponse(
                id=session_domain.id,
                user_id=session_domain.user_id,
                name=session_domain.name,
                agent_id=session_domain.agent_id,
                created_time=session_domain.created_time,
                updated_time=session_domain.updated_time,
            )
            session_responses.append(session_response)

        return PaginatedResponse(data=session_responses, meta=paginated_response.meta)

    except Exception as e:
        log.error("Error fetching sessions for user %s: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve sessions",
        )


@router.get("/sessions/{session_id}", response_model=DataResponse[SessionResponse])
async def get_session(
    session_id: str,
    db: Session = Depends(get_db),
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
            db=db, session_id=request_dto.session_id, user_id=request_dto.user_id
        )

        if not session_domain:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Session not found."
            )

        log.info("User %s authorized. Fetching session_id: %s", user_id, session_id)

        session_response = SessionResponse(
            id=session_domain.id,
            user_id=session_domain.user_id,
            name=session_domain.name,
            agent_id=session_domain.agent_id,
            created_time=session_domain.created_time,
            updated_time=session_domain.updated_time,
        )

        return create_data_response(session_response)

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
    db: Session = Depends(get_db),
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
            db=db,
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
    db: Session = Depends(get_db),
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
            db=db,
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
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    session_service: SessionService = Depends(get_session_business_service),
):
    user_id = user.get("id")
    log.info("User %s attempting to delete session %s", user_id, session_id)

    try:
        deleted = session_service.delete_session_with_notifications(
            db=db, session_id=session_id, user_id=user_id
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
