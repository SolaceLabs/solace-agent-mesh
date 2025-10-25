"""
Slack Gateway Adapter for the Generic Gateway Framework.
"""

import asyncio
import base64
import json
import logging
import re
from typing import Any, Dict, List, Optional

import requests
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp
from slack_sdk.errors import SlackApiError

from pydantic import BaseModel, Field

from ..adapter.base import GatewayAdapter
from ..adapter.types import (
    AuthClaims,
    GatewayContext,
    ResponseContext,
    SamDataPart,
    SamError,
    SamFeedback,
    SamFilePart,
    SamTask,
    SamTextPart,
    SamUpdate,
)
from . import handlers, utils

log = logging.getLogger(__name__)

_NO_EMAIL_MARKER = "_NO_EMAIL_"


class SlackAdapterConfig(BaseModel):
    """Configuration model for the SlackAdapter."""

    slack_bot_token: str = Field(..., description="Slack Bot Token (xoxb-...).")
    slack_app_token: str = Field(
        ..., description="Slack App Token (xapp-...) for Socket Mode."
    )
    slack_initial_status_message: str = Field(
        "Got it, thinking...",
        description="Message posted to Slack upon receiving a user request.",
    )
    correct_markdown_formatting: bool = Field(
        True, description="Attempt to convert common Markdown to Slack's format."
    )
    feedback_enabled: bool = Field(
        False, description="Enable thumbs up/down feedback buttons on final messages."
    )
    slack_email_cache_ttl_seconds: int = Field(
        3600, description="TTL for caching Slack user email addresses."
    )


class SlackAdapter(GatewayAdapter):
    """A feature-complete Slack Gateway implementation using the adapter pattern."""

    ConfigModel = SlackAdapterConfig

    def __init__(self):
        self.context: Optional[GatewayContext] = None
        self.slack_app: Optional[AsyncApp] = None
        self.slack_handler: Optional[AsyncSocketModeHandler] = None

    async def init(self, context: GatewayContext) -> None:
        """Initialize the Slack app, handlers, and start the listener."""
        self.context = context
        log.info("Initializing Slack Adapter...")

        # Config is now a validated Pydantic model
        adapter_config: SlackAdapterConfig = self.context.adapter_config

        self.slack_app = AsyncApp(token=adapter_config.slack_bot_token)

        # --- Register Event and Action Handlers ---
        self._register_handlers()

        # --- Start Socket Mode Handler ---
        self.slack_handler = AsyncSocketModeHandler(
            self.slack_app, adapter_config.slack_app_token
        )
        asyncio.create_task(self.slack_handler.start_async())
        log.info("Slack Adapter initialized and listener started.")

    async def cleanup(self) -> None:
        """Stop the Slack listener."""
        if self.slack_handler:
            log.info("Stopping Slack listener...")
            self.slack_handler.close()

    def _register_handlers(self):
        """Registers all Slack event and action handlers."""

        # Event handlers for messages and mentions
        @self.slack_app.event("message")
        async def handle_message_wrapper(event, say):
            await handlers.handle_slack_message(self, event, say)

        @self.slack_app.event("app_mention")
        async def handle_mention_wrapper(event, say):
            await handlers.handle_slack_mention(self, event, say)

        # Action handler for the cancel button
        @self.slack_app.action(utils.CANCEL_BUTTON_ACTION_ID)
        async def handle_cancel_action(ack, body, logger):
            await ack()
            task_id = body["actions"][0]["value"]
            logger.info(f"Cancel button clicked for task: {task_id}")
            await self.context.cancel_task(task_id)

        # Action handlers for multi-step feedback
        @self.slack_app.action(utils.THUMBS_UP_ACTION_ID)
        async def handle_thumbs_up(ack, body, client, logger):
            await ack()
            payload = json.loads(body["actions"][0]["value"])
            logger.info(
                "Feedback process started (up) for task: %s", payload["task_id"]
            )
            input_blocks = utils.create_feedback_input_blocks("up", payload)
            await client.chat_update(
                channel=body["container"]["channel_id"],
                ts=body["container"]["message_ts"],
                blocks=input_blocks,
                text="Please provide your feedback.",
            )

        @self.slack_app.action(utils.THUMBS_DOWN_ACTION_ID)
        async def handle_thumbs_down(ack, body, client, logger):
            await ack()
            payload = json.loads(body["actions"][0]["value"])
            logger.info(
                "Feedback process started (down) for task: %s", payload["task_id"]
            )
            input_blocks = utils.create_feedback_input_blocks("down", payload)
            await client.chat_update(
                channel=body["container"]["channel_id"],
                ts=body["container"]["message_ts"],
                blocks=input_blocks,
                text="Please provide your feedback.",
            )

        @self.slack_app.action(utils.CANCEL_FEEDBACK_ACTION_ID)
        async def handle_cancel_feedback(ack, body, client, logger):
            await ack()
            payload = json.loads(body["actions"][0]["value"])
            logger.info("Feedback cancelled for task: %s", payload["task_id"])
            original_feedback_elements = utils.create_feedback_blocks(
                payload["task_id"], payload["user_id"], payload["session_id"]
            )
            original_blocks = [
                {
                    "type": "actions",
                    "block_id": utils.FEEDBACK_BLOCK_ID,
                    "elements": original_feedback_elements,
                }
            ]
            await client.chat_update(
                channel=body["container"]["channel_id"],
                ts=body["container"]["message_ts"],
                blocks=original_blocks,
                text="How was this response?",
            )

        @self.slack_app.action(utils.SUBMIT_FEEDBACK_ACTION_ID)
        async def handle_submit_feedback(ack, body, client, logger):
            await ack()
            payload = json.loads(body["actions"][0]["value"])
            task_id = payload["task_id"]
            rating = payload["rating"]
            session_id = payload["session_id"]

            comment = ""
            try:
                state_values = body.get("state", {}).get("values", {})
                comment_block = state_values.get(utils.FEEDBACK_COMMENT_BLOCK_ID, {})
                comment = comment_block.get(
                    utils.FEEDBACK_COMMENT_INPUT_ACTION_ID, {}
                ).get("value", "")
            except Exception as e:
                logger.error(
                    "Error extracting feedback comment for task %s: %s", task_id, e
                )

            logger.info(
                "Feedback submitted for task %s: rating=%s, comment='%s...'",
                task_id,
                rating,
                comment[:50],
            )

            feedback = SamFeedback(
                task_id=task_id,
                session_id=session_id,
                rating=rating,
                comment=comment,
                user_id=payload["user_id"],
            )
            await self.context.submit_feedback(feedback)

            thank_you_blocks = [
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": "✅ Thank you for your feedback!",
                        }
                    ],
                }
            ]
            await client.chat_update(
                channel=body["container"]["channel_id"],
                ts=body["container"]["message_ts"],
                blocks=thank_you_blocks,
                text="Thank you for your feedback!",
            )

    async def extract_auth_claims(
        self, external_input: Dict, endpoint_context: Optional[Dict[str, Any]] = None
    ) -> Optional[AuthClaims]:
        """Extract user identity from a Slack event."""
        slack_user_id = external_input.get("user")
        slack_team_id = external_input.get("team") or external_input.get("team_id")

        if not slack_user_id or not slack_team_id:
            log.warning("Could not determine Slack user_id or team_id from event.")
            return None

        adapter_config: SlackAdapterConfig = self.context.adapter_config
        cache_key = f"slack_email_cache:{slack_user_id}"
        ttl = adapter_config.slack_email_cache_ttl_seconds

        if self.context.cache_service and ttl > 0:
            cached_claim = self.context.cache_service.get_data(cache_key)
            if cached_claim:
                if cached_claim == _NO_EMAIL_MARKER:
                    return AuthClaims(
                        id=f"slack:{slack_team_id}:{slack_user_id}",
                        source="slack_fallback",
                        raw_context={
                            "slack_user_id": slack_user_id,
                            "slack_team_id": slack_team_id,
                        },
                    )
                else:
                    return AuthClaims(
                        id=cached_claim,
                        email=cached_claim,
                        source="slack_api",
                        raw_context={
                            "slack_user_id": slack_user_id,
                            "slack_team_id": slack_team_id,
                        },
                    )

        try:
            profile_response = await self.slack_app.client.users_profile_get(
                user=slack_user_id
            )
            user_email = profile_response.get("profile", {}).get("email")

            if user_email:
                if self.context.cache_service and ttl > 0:
                    self.context.cache_service.add_data(
                        cache_key, user_email, expiry=ttl
                    )
                return AuthClaims(
                    id=user_email,
                    email=user_email,
                    source="slack_api",
                    raw_context={
                        "slack_user_id": slack_user_id,
                        "slack_team_id": slack_team_id,
                    },
                )
            else:
                raise ValueError("Email not found in profile")
        except Exception as e:
            log.warning(
                "Could not fetch email for Slack user %s: %s. Using fallback ID.",
                slack_user_id,
                e,
            )
            if self.context.cache_service and ttl > 0:
                self.context.cache_service.add_data(
                    cache_key, _NO_EMAIL_MARKER, expiry=ttl
                )
            return AuthClaims(
                id=f"slack:{slack_team_id}:{slack_user_id}",
                source="slack_fallback",
                raw_context={
                    "slack_user_id": slack_user_id,
                    "slack_team_id": slack_team_id,
                },
            )

    async def prepare_task(
        self, external_input: Dict, endpoint_context: Optional[Dict[str, Any]] = None
    ) -> SamTask:
        """Convert a Slack event into a SamTask."""
        if external_input.get("bot_id") or external_input.get("subtype") == "bot_message":
            raise ValueError("Ignoring bot message")

        channel_id = external_input.get("channel")
        thread_ts = external_input.get("thread_ts") or external_input.get("ts")
        text = external_input.get("text", "")
        files_info = external_input.get("files", [])

        # Resolve @mentions in the text
        resolved_text = await self._resolve_mentions_in_text(text)

        parts = [self.context.create_text_part(resolved_text)]

        # Handle file uploads
        if files_info:
            for file_info in files_info:
                try:
                    file_bytes = await self._download_file(file_info)
                    parts.append(
                        self.context.create_file_part_from_bytes(
                            name=file_info["name"],
                            content_bytes=file_bytes,
                            mime_type=file_info.get(
                                "mimetype", "application/octet-stream"
                            ),
                        )
                    )
                except Exception as e:
                    log.error(
                        "Failed to download and attach file %s: %s",
                        file_info.get("name"),
                        e,
                    )

        if not any(
            p.text.strip() for p in parts if isinstance(p, SamTextPart)
        ) and not any(isinstance(p, SamFilePart) for p in parts):
            raise ValueError("No content to send to agent")

        return SamTask(
            parts=parts,
            conversation_id=f"slack:{channel_id}:{thread_ts}",
            target_agent=self.context.get_config("default_agent_name", "default"),
            platform_context={
                "channel_id": channel_id,
                "thread_ts": thread_ts,
            },
        )

    async def handle_update(self, update: SamUpdate, context: ResponseContext) -> None:
        """Handle a streaming update from the agent."""
        task_id = context.task_id
        channel_id = context.platform_context["channel_id"]
        thread_ts = context.platform_context["thread_ts"]

        # Get or create message timestamps
        status_ts = self.context.get_task_state(task_id, "status_ts")

        adapter_config: SlackAdapterConfig = self.context.adapter_config
        # If this is the first update, post the initial status message
        if not status_ts:
            initial_status_msg = adapter_config.slack_initial_status_message
            if initial_status_msg:
                status_blocks = utils.build_slack_blocks(status_text=initial_status_msg)
                new_status_ts = await utils.send_slack_message(
                    self, channel_id, thread_ts, initial_status_msg, status_blocks
                )
                if new_status_ts:
                    self.context.set_task_state(task_id, "status_ts", new_status_ts)
                    self.context.set_task_state(
                        task_id, "current_status", initial_status_msg
                    )
                    status_ts = new_status_ts

        # Process parts sequentially to maintain conversational order
        for part in update.parts:
            if isinstance(part, SamTextPart):
                # Buffer text and update the content message
                content_ts = self.context.get_task_state(task_id, "content_ts")
                buffer = self.context.get_task_state(task_id, "content_buffer", "")
                buffer += part.text
                self.context.set_task_state(task_id, "content_buffer", buffer)

                formatted_text = self._format_text(buffer)
                content_blocks = utils.build_slack_blocks(content_text=formatted_text)

                if content_ts:
                    await utils.update_slack_message(
                        self, channel_id, content_ts, formatted_text, content_blocks
                    )
                else:
                    new_content_ts = await utils.send_slack_message(
                        self, channel_id, thread_ts, formatted_text, content_blocks
                    )
                    if new_content_ts:
                        self.context.set_task_state(task_id, "content_ts", new_content_ts)

            elif isinstance(part, SamFilePart):
                await self._handle_file_part(part, channel_id, thread_ts)
            elif isinstance(part, SamDataPart):
                await self._handle_data_part(part, channel_id, thread_ts, context)

    async def handle_task_complete(self, context: ResponseContext) -> None:
        """Update UI to show task is complete and add feedback buttons."""
        task_id = context.task_id
        channel_id = context.platform_context["channel_id"]
        thread_ts = context.platform_context["thread_ts"]
        status_ts = self.context.get_task_state(task_id, "status_ts")

        adapter_config: SlackAdapterConfig = self.context.adapter_config

        # First, update the status message to show completion.
        final_status_text = "✅ Task complete."
        status_blocks = utils.build_slack_blocks(status_text=final_status_text)
        if status_ts:
            await utils.update_slack_message(
                self, channel_id, status_ts, final_status_text, status_blocks
            )
        else:
            # If no status message was ever posted, post a new one.
            await utils.send_slack_message(
                self, channel_id, thread_ts, final_status_text, status_blocks
            )

        # Then, if feedback is enabled, post it as a new message in the thread.
        if adapter_config.feedback_enabled:
            feedback_elements = utils.create_feedback_blocks(
                task_id, context.user_id, context.conversation_id
            )
            if feedback_elements:
                feedback_blocks = [
                    {
                        "type": "actions",
                        "block_id": utils.FEEDBACK_BLOCK_ID,
                        "elements": feedback_elements,
                    }
                ]
                await utils.send_slack_message(
                    self,
                    channel=channel_id,
                    thread_ts=thread_ts,
                    text="How was this response?",  # Fallback text for notifications
                    blocks=feedback_blocks,
                )

    async def handle_error(self, error: SamError, context: ResponseContext) -> None:
        """Display an error message in Slack."""
        task_id = context.task_id
        channel_id = context.platform_context["channel_id"]
        status_ts = self.context.get_task_state(task_id, "status_ts")

        if status_ts:
            error_text = f"❌ Error: {error.message}"
            if error.category == "CANCELED":
                error_text = "🛑 Task canceled."

            error_blocks = utils.build_slack_blocks(status_text=error_text)
            await utils.update_slack_message(
                self, channel_id, status_ts, error_text, error_blocks
            )

    # --- Private Helper Methods ---

    def _get_icon_for_mime_type(self, mime_type: Optional[str]) -> str:
        """Returns a Slack emoji for a given MIME type."""
        if not mime_type:
            return ":page_facing_up:"
        if "image" in mime_type:
            return ":art:"
        if "audio" in mime_type:
            return ":sound:"
        if "video" in mime_type:
            return ":film_frames:"
        if "pdf" in mime_type:
            return ":page_facing_up:"
        if "zip" in mime_type or "archive" in mime_type:
            return ":compression:"
        if "text" in mime_type or "json" in mime_type or "csv" in mime_type:
            return ":page_with_curl:"
        return ":page_facing_up:"

    def _format_text(self, text: str) -> str:
        """Applies markdown correction if enabled."""
        adapter_config: SlackAdapterConfig = self.context.adapter_config
        if adapter_config.correct_markdown_formatting:
            return utils.correct_slack_markdown(text)
        return text

    async def _handle_file_part(
        self, part: SamFilePart, channel_id: str, thread_ts: str
    ):
        """Handles sending a file to Slack."""
        if part.content_bytes:
            await utils.upload_slack_file(
                self, channel_id, thread_ts, part.name, part.content_bytes
            )
        elif part.uri:
            uri_text = f":link: Artifact available: {part.name} - {part.uri}"
            await utils.send_slack_message(self, channel_id, thread_ts, uri_text)

    async def _handle_data_part(
        self, part: SamDataPart, channel_id: str, thread_ts: str, context: ResponseContext
    ):
        """Handles structured data, checking for special types like progress updates."""
        data_type = part.data.get("type")
        task_id = context.task_id

        if data_type == "agent_progress_update":
            status_text = part.data.get("status_text")
            if status_text:
                await self.handle_status_update(status_text, context)

        elif data_type == "artifact_creation_progress":
            status = part.data.get("status")
            filename = part.data.get("filename", "unknown file")
            artifact_msg_ts_key = f"artifact_msg_ts:{filename}"
            artifact_msg_ts = self.context.get_task_state(
                task_id, artifact_msg_ts_key
            )

            if status == "in-progress":
                bytes_transferred = part.data.get("bytes_transferred", 0)
                icon = self._get_icon_for_mime_type(None)
                progress_text = f"{icon} Creating `{filename}`..."
                if bytes_transferred > 0:
                    progress_text += f" ({bytes_transferred} bytes)"
                progress_blocks = utils.build_slack_blocks(content_text=progress_text)

                if artifact_msg_ts:
                    # We have a message for this artifact, so update it
                    await utils.update_slack_message(
                        self,
                        channel_id,
                        artifact_msg_ts,
                        progress_text,
                        progress_blocks,
                    )
                else:
                    # This is the first progress update for this artifact.
                    # Finalize any previous text message.
                    content_ts = self.context.get_task_state(task_id, "content_ts")
                    buffer = self.context.get_task_state(task_id, "content_buffer", "")
                    if content_ts and buffer:
                        formatted_text = self._format_text(buffer)
                        content_blocks = utils.build_slack_blocks(
                            content_text=formatted_text
                        )
                        await utils.update_slack_message(
                            self,
                            channel_id,
                            content_ts,
                            formatted_text,
                            content_blocks,
                        )

                    # Force subsequent text to a new message
                    self.context.set_task_state(task_id, "content_buffer", "")
                    self.context.set_task_state(task_id, "content_ts", None)

                    # Post the new artifact progress message
                    new_artifact_msg_ts = await utils.send_slack_message(
                        self, channel_id, thread_ts, progress_text, progress_blocks
                    )
                    if new_artifact_msg_ts:
                        self.context.set_task_state(
                            task_id, artifact_msg_ts_key, new_artifact_msg_ts
                        )

            elif status == "completed":
                if artifact_msg_ts:
                    description = part.data.get("description", "N/A")
                    mime_type = part.data.get("mime_type")
                    icon = self._get_icon_for_mime_type(mime_type)
                    completed_text = (
                        f"{icon} Artifact Created: `{filename}`\n"
                        f"*Description*: {description}"
                    )
                    completed_blocks = utils.build_slack_blocks(
                        content_text=completed_text
                    )
                    await utils.update_slack_message(
                        self,
                        channel_id,
                        artifact_msg_ts,
                        completed_text,
                        completed_blocks,
                    )

                    # Now, load the artifact and upload it to Slack
                    try:
                        log.info(
                            "Artifact '%s' creation complete. Fetching content for upload.",
                            filename,
                        )
                        version = part.data.get("version")
                        content_bytes = await self.context.load_artifact_content(
                            context=context, filename=filename, version=version
                        )

                        if content_bytes:
                            await utils.upload_slack_file(
                                self,
                                channel_id,
                                thread_ts,
                                filename,
                                content_bytes,
                            )
                        else:
                            log.error(
                                "Failed to load content for artifact '%s' (version: %s). Cannot upload to Slack.",
                                filename,
                                version or "latest",
                            )
                            error_text = f":warning: Could not retrieve content for artifact `{filename}`."
                            await utils.send_slack_message(
                                self, channel_id, thread_ts, error_text
                            )

                    except Exception as e:
                        log.exception(
                            "Error fetching or uploading artifact '%s': %s", filename, e
                        )
                        error_text = f":warning: An error occurred while uploading artifact `{filename}`."
                        await utils.send_slack_message(
                            self, channel_id, thread_ts, error_text
                        )
                else:
                    log.warning(
                        f"Could not find message TS for completing artifact '{filename}'"
                    )

            elif status == "failed":
                if artifact_msg_ts:
                    failed_text = f"❌ Failed to create artifact: `{filename}`"
                    failed_blocks = utils.build_slack_blocks(content_text=failed_text)
                    await utils.update_slack_message(
                        self, channel_id, artifact_msg_ts, failed_text, failed_blocks
                    )
                else:
                    # If we never even started a message, post a new one.
                    failed_text = f"❌ Failed to create artifact: `{filename}`"
                    await utils.send_slack_message(
                        self, channel_id, thread_ts, failed_text
                    )

    async def handle_status_update(
        self, status_text: str, context: ResponseContext
    ) -> None:
        """Update the status message in Slack."""
        task_id = context.task_id
        channel_id = context.platform_context["channel_id"]
        status_ts = self.context.get_task_state(task_id, "status_ts")
        if status_ts:
            current_status = self.context.get_task_state(task_id, "current_status", "")
            new_status = f"⏳ {status_text}"
            if new_status != current_status:
                status_blocks = utils.build_slack_blocks(status_text=new_status)
                await utils.update_slack_message(
                    self, channel_id, status_ts, new_status, status_blocks
                )
                self.context.set_task_state(task_id, "current_status", new_status)

    async def _resolve_mentions_in_text(self, text: str) -> str:
        """Finds all Slack user mentions (<@U...>) and replaces them with email/name."""
        mention_pattern = re.compile(r"<@([UW][A-Z0-9]+)>")
        user_ids_found = set(mention_pattern.findall(text))
        if not user_ids_found:
            return text

        modified_text = text
        for user_id in user_ids_found:
            try:
                user_info_response = await self.slack_app.client.users_info(
                    user=user_id
                )
                profile = user_info_response.get("user", {}).get("profile", {})
                replacement = profile.get("email") or profile.get(
                    "real_name_normalized"
                )
                if replacement:
                    modified_text = modified_text.replace(f"<@{user_id}>", replacement)
            except SlackApiError as e:
                log.warning(
                    "Slack API error resolving mention for user ID %s: %s", user_id, e
                )
        return modified_text

    async def _download_file(self, file_info: Dict) -> bytes:
        """Downloads a file from Slack given its private URL."""
        file_url = file_info.get("url_private_download") or file_info.get("url_private")
        if not file_url:
            raise ValueError("File info is missing a download URL.")

        adapter_config: SlackAdapterConfig = self.context.adapter_config
        headers = {"Authorization": f"Bearer {adapter_config.slack_bot_token}"}

        # Use to_thread to avoid blocking the event loop
        response = await asyncio.to_thread(
            requests.get, file_url, headers=headers, timeout=30
        )
        response.raise_for_status()
        return response.content
