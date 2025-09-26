"""
Service layer for handling user feedback on chat messages.
"""

import csv
import os
import threading
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Dict

from solace_ai_connector.common.log import log

# The FeedbackPayload is defined in the router, this creates a forward reference
# which is resolved at runtime.
if TYPE_CHECKING:
    from ..routers.feedback import FeedbackPayload


class FeedbackService:
    """Handles the business logic for processing user feedback."""

    def __init__(self, config: Dict = None):
        """Initializes the FeedbackService based on configuration."""
        if config is None:
            config = {}
        self._type = config.get("type", "log")
        self._filename = config.get("filename", "feedback.csv")
        self._lock = threading.Lock()
        log.info("FeedbackService initialized with type '%s'.", self._type)

    async def process_feedback(self, payload: "FeedbackPayload", user_id: str):
        """
        Processes and stores the feedback based on the configured service type.
        """
        if self._type == "csv":
            self._write_to_csv(payload, user_id)
        else:  # Default to logging
            self._log_feedback(payload, user_id)

    def _log_feedback(self, payload: "FeedbackPayload", user_id: str):
        """Logs the feedback in a structured format."""
        log.info(
            "Feedback received from user '%s' for message '%s': %s",
            user_id,
            payload.message_id,
            payload.model_dump_json(by_alias=True),
        )

    def _write_to_csv(self, payload: "FeedbackPayload", user_id: str):
        """Appends feedback to a CSV file in a thread-safe manner."""
        log.info("Writing feedback to CSV file: %s", self._filename)
        file_exists = os.path.exists(self._filename)
        headers = [
            "timestamp_utc",
            "user_id",
            "session_id",
            "message_id",
            "feedback_type",
            "feedback_text",
        ]

        row_data = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "user_id": user_id,
            "session_id": payload.session_id,
            "message_id": payload.message_id,
            "feedback_type": payload.feedback_type,
            "feedback_text": payload.feedback_text,
        }

        with self._lock:
            try:
                with open(self._filename, "a", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=headers)
                    if not file_exists:
                        writer.writeheader()
                    writer.writerow(row_data)
            except IOError as e:
                log.error(
                    "Failed to write feedback to CSV file '%s': %s", self._filename, e
                )
