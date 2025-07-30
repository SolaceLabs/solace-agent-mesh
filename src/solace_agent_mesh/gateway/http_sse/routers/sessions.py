"""
API Router for managing chat sessions.
"""

from fastapi import APIRouter, Body, Depends, HTTPException, status
from solace_ai_connector.common.log import log

from ....common.a2a_protocol import get_a2a_base_topic
from ..database.persistence_service import PersistenceService
from ....gateway.http_sse.dependencies import (
    get_persistence_service,
    get_publish_a2a_func,
    get_namespace,
    PublishFunc,
)
from ....gateway.http_sse.routers.users import get_current_user

router = APIRouter()


@router.get("/sessions", response_model=list)
async def get_all_sessions(
    user: dict = Depends(get_current_user),
    persistence_service: PersistenceService = Depends(get_persistence_service),
):
    """
    Retrieves all chat sessions for the current user.
    """
    user_id = user.get("id")
    log.info("Fetching sessions for user_id: %s", user_id)
    sessions = persistence_service.get_sessions(user_id)
    return sessions


@router.get("/sessions/{session_id}", response_model=dict)
async def get_session(
    session_id: str,
    user: dict = Depends(get_current_user),
    persistence_service: PersistenceService = Depends(get_persistence_service),
):
    """
    Retrieves a specific chat session,
    ensuring the user has permission to access it.
    """
    user_id = user.get("id")
    log.info("User %s attempting to fetch session_id: %s", user_id, session_id)

    session = persistence_service.get_session(session_id)
    if not session or session.get("user_id") != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found.",
        )

    log.info("User %s authorized. Fetching session_id: %s", user_id, session_id)
    return session


@router.get("/sessions/{session_id}/history", response_model=list)
async def get_session_history(
    session_id: str,
    user: dict = Depends(get_current_user),
    persistence_service: PersistenceService = Depends(get_persistence_service),
):
    """
    Retrieves the message history for a specific chat session,
    ensuring the user has permission to access it.
    """
    user_id = user.get("id")
    log.info(
        "User %s attempting to fetch history for session_id: %s", user_id, session_id
    )

    # First, verify that the session belongs to the current user.
    session = persistence_service.get_session(session_id)
    if not session or session.get("user_id") != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this session.",
        )

    log.info(
        "User %s authorized. Fetching history for session_id: %s", user_id, session_id
    )
    history = persistence_service.get_chat_history(session_id)
    return history


@router.patch("/sessions/{session_id}", response_model=dict)
async def update_session_name(
    session_id: str,
    name: str = Body(..., embed=True),
    user: dict = Depends(get_current_user),
    persistence_service: PersistenceService = Depends(get_persistence_service),
):
    """
    Updates the name of a specific chat session.
    """
    user_id = user.get("id")
    log.info("User %s attempting to update session %s", user_id, session_id)

    # Verify that the session belongs to the current user.
    session = persistence_service.get_session(session_id)
    if not session or session.get("user_id") != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to modify this session.",
        )

    updated_session = persistence_service.update_session(session_id, name)
    log.info("Session %s updated successfully", session_id)
    return updated_session


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: str,
    user: dict = Depends(get_current_user),
    persistence_service: PersistenceService = Depends(get_persistence_service),
    publish_a2a_func: PublishFunc = Depends(get_publish_a2a_func),
    namespace: str = Depends(get_namespace),
):
    """
    Deletes a specific chat session, notifying the agent if one is associated.
    """
    user_id = user.get("id")
    log.info("User %s attempting to delete session %s", user_id, session_id)

    session = persistence_service.get_session(session_id)
    if not session or session.get("user_id") != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this session.",
        )

    agent_id = session.get("agent_id")
    if agent_id:
        log.info("Notifying agent %s to delete session %s", agent_id, session_id)
        # Debug logging to validate namespace format
        log.debug(
            "Session deletion - namespace: '%s' (ends with slash: %s)",
            namespace,
            namespace.endswith("/"),
        )
        base_topic = get_a2a_base_topic(namespace)
        topic = f"{base_topic}/{agent_id}/mop/session/delete/request"
        log.debug("Session deletion - generated topic: '%s'", topic)
        payload = {
            "session_id": session_id,
            "user_id": user_id,
            "app_name": agent_id,
        }
        try:
            publish_a2a_func(topic, payload)
            log.info("Successfully published delete event to topic: %s", topic)
        except Exception as e:
            log.error(
                "Failed to publish delete event for session %s to agent %s: %s",
                session_id,
                agent_id,
                e,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to notify agent of session deletion.",
            ) from e

    persistence_service.delete_session(session_id)
    log.info("Session %s deleted successfully from orchestrator", session_id)
