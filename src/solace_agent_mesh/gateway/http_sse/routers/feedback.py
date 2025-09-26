"""
API Router for receiving and processing user feedback on chat messages.
"""

from typing import Literal, Optional

from fastapi import APIRouter, Depends
from fastapi import Request as FastAPIRequest
from pydantic import BaseModel, Field

from ..dependencies import get_feedback_service, get_user_id
from ..services.feedback_service import FeedbackService

router = APIRouter()


class FeedbackPayload(BaseModel):
    """Data model for the feedback submission payload."""

    message_id: str = Field(..., alias="messageId")
    session_id: str = Field(..., alias="sessionId")
    feedback_type: Literal["up", "down"] = Field(..., alias="feedbackType")
    feedback_text: Optional[str] = Field(None, alias="feedbackText")


@router.post("/feedback", status_code=202, tags=["Feedback"])
async def submit_feedback(
    payload: FeedbackPayload,
    request: FastAPIRequest,
    user_id: str = Depends(get_user_id),
    feedback_service: FeedbackService = Depends(get_feedback_service),
):
    """
    Receives and processes user feedback for a specific chat message.
    """
    await feedback_service.process_feedback(payload, user_id)
    return {"status": "feedback received"}
