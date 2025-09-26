"""
Service layer for handling user feedback on chat messages.
"""

from typing import TYPE_CHECKING
from solace_ai_connector.common.log import log

# The FeedbackPayload is defined in the router, this creates a forward reference
# which is resolved at runtime.
if TYPE_CHECKING:
    from ..routers.feedback import FeedbackPayload


class FeedbackService:
    """Handles the business logic for processing user feedback."""

    def __init__(self):
        """Initializes the FeedbackService."""
        log.info("FeedbackService initialized.")

    async def process_feedback(self, payload: "FeedbackPayload", user_id: str):
        """
        Processes and stores the feedback.

        For now, this implementation logs the feedback in a structured format.
        In a production system, this could be extended to publish to a Solace topic
        or store in a database.
        """
        log.info(
            "Feedback received from user '%s' for message '%s': %s",
            user_id,
            payload.message_id,
            payload.model_dump_json(by_alias=True),
        )
