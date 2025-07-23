"""
Custom Solace AI Connector Component to host the Slack Gateway logic.
Connects to Slack, handles events, interacts with CoreA2AService, and processes A2A messages.
"""

import asyncio
import base64
import json
import re
import threading
from typing import Any, Dict, Optional, List, Tuple, Union, Set
from datetime import datetime, timezone

try:
    import slack_bolt
    from slack_bolt.async_app import AsyncApp
    from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
    from slack_sdk.errors import SlackApiError
    import requests

    SLACK_BOLT_AVAILABLE = True
except ImportError:
    SLACK_BOLT_AVAILABLE = False
    requests = None
    AsyncApp = None
    AsyncSocketModeHandler = None
    SlackApiError = None

from solace_ai_connector.common.log import log
from solace_agent_mesh.gateway.base.component import BaseGatewayComponent
from solace_agent_mesh.common.types import (
    Part as A2APart,
    TextPart,
    FilePart,
    DataPart,
    FileContent,
    Task,
    TaskStatusUpdateEvent,
    TaskArtifactUpdateEvent,
    JSONRPCError,
    TaskState,
)
from solace_agent_mesh.agent.utils.artifact_helpers import save_artifact_with_metadata
from .utils import (
    generate_a2a_session_id,
    send_slack_message,
    update_slack_message,
    upload_slack_file,
    create_feedback_blocks,
    _build_current_slack_blocks,
    correct_slack_markdown,
    CANCEL_BUTTON_ACTION_ID,
)

_NO_EMAIL_MARKER = "_NO_EMAIL_"

info = {
    "class_name": "SlackGatewayComponent",
    "description": (
        "Implements the A2A Slack Gateway, inheriting from BaseGatewayComponent. "
        "Handles communication between Slack and the A2A agent ecosystem. "
        "Connects to Slack via Socket Mode, translates messages, and processes A2A responses/updates. "
        "Configuration is defined in SlackGatewayApp's app_config."
    ),
    "config_parameters": [],
    "input_schema": {
        "type": "object",
        "description": "Not typically used; component reacts to events from its input queue or Slack.",
        "properties": {},
    },
    "output_schema": {
        "type": "object",
        "description": "Not typically used; component publishes results to Slack or A2A.",
        "properties": {},
    },
}


class SlackGatewayComponent(BaseGatewayComponent):
    """
    SAC Component implementing the A2A Slack Gateway, inheriting from BaseGatewayComponent.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        log.info(
            "%s Initializing Slack Gateway Component (Post-Base)...",
            self.log_identifier,
        )

        if not SLACK_BOLT_AVAILABLE:
            log.error(
                f"{self.log_identifier} Slack Bolt library not found. Please install 'slack_bolt' (`pip install slack_bolt`)."
            )
            raise ImportError("Slack Bolt library not found.")
        if not requests:
            log.error(
                f"{self.log_identifier} Requests library not found. Please install 'requests' (`pip install requests`)."
            )
            raise ImportError("Requests library not found.")

        try:
            self.slack_bot_token = self.get_config("slack_bot_token")
            self.slack_app_token = self.get_config("slack_app_token")
            self.default_agent_name = self.get_config("default_agent_name")
            self.slack_initial_status_message = self.get_config(
                "slack_initial_status_message", "Thinking..."
            )
            self.correct_markdown_formatting = self.get_config(
                "correct_markdown_formatting", True
            )
            self.feedback_enabled = self.get_config("feedback_enabled", False)
            self.feedback_post_url = self.get_config("feedback_post_url")
            self.feedback_post_headers = self.get_config("feedback_post_headers", {})
            self.slack_email_cache_ttl_seconds = self.get_config(
                "slack_email_cache_ttl_seconds", 3600
            )

            if not self.slack_bot_token or not self.slack_app_token:
                raise ValueError("Slack Bot Token and App Token are required.")
            log.info("%s Slack-specific configuration retrieved.", self.log_identifier)
        except Exception as e:
            log.error(
                "%s Failed to retrieve Slack-specific configuration: %s",
                self.log_identifier,
                e,
            )
            raise ValueError(
                f"Slack-specific configuration retrieval error: {e}"
            ) from e

        try:
            self.slack_app = AsyncApp(token=self.slack_bot_token)
            self.task_slack_context: Dict[str, Dict[str, str]] = {}
            self.status_message_ts: Dict[str, Optional[str]] = {}
            self.content_message_ts: Dict[str, Optional[str]] = {}
            self.content_message_buffer: Dict[str, str] = {}
            self.current_status_text: Dict[str, Optional[str]] = {}
            self.active_cancellable_tasks: Set[str] = set()
            self.context_lock = threading.Lock()
            self.slack_handler: Optional[AsyncSocketModeHandler] = None

            from . import handlers

            @self.slack_app.action(CANCEL_BUTTON_ACTION_ID)
            async def handle_cancel_request_button_wrapper(
                ack, body, client, logger_bolt
            ):
                log.info(
                    "%s Received '%s' action.",
                    self.log_identifier,
                    CANCEL_BUTTON_ACTION_ID,
                )
                await ack()
                try:
                    await self.handle_cancel_request_action(body, client)
                except Exception as e:
                    log.exception(
                        "%s Error in cancel request action handler: %s",
                        self.log_identifier,
                        e,
                    )
                    try:
                        await client.chat_postEphemeral(
                            channel=body["channel"]["id"],
                            user=body["user"]["id"],
                            text=f":warning: Sorry, I couldn't process your cancel request: {e}",
                        )
                    except Exception as e_ephemeral:
                        log.error(
                            "%s Failed to send ephemeral error for cancel action: %s",
                            self.log_identifier,
                            e_ephemeral,
                        )

            @self.slack_app.event("message")
            async def handle_message_events_async(event, say, client):
                log.debug(
                    "%s Received Slack 'message' event (async).", self.log_identifier
                )
                await handlers.handle_slack_message(self, event, say, client)

            @self.slack_app.event("app_mention")
            async def handle_mention_events_async(event, say, client):
                log.debug(
                    "%s Received Slack 'app_mention' event (async).",
                    self.log_identifier,
                )
                await handlers.handle_slack_mention(self, event, say, client)

            log.info("%s Slack event handlers registered.", self.log_identifier)
        except Exception as e:
            log.exception(
                "%s Slack-specific initialization failed: %s", self.log_identifier, e
            )
            raise
        log.info(
            "%s Slack Gateway Component initialization complete.", self.log_identifier
        )

    async def _resolve_mentions_in_text(self, text: str) -> str:
        """
        Finds all Slack user mentions (<@U...>) in a string and replaces them
        with the user's email address or real name as a fallback.
        """
        log_id = f"{self.log_identifier}[ResolveMentions]"
        # Regex to find all occurrences of <@USERID>
        mention_pattern = re.compile(r"<@([UW][A-Z0-9]+)>")
        user_ids_found = set(mention_pattern.findall(text))

        if not user_ids_found:
            return text

        log.debug(
            "%s Found %d unique user mentions to resolve.",
            log_id,
            len(user_ids_found),
        )

        modified_text = text
        for user_id in user_ids_found:
            try:
                user_info_response = await self.slack_app.client.users_info(
                    user=user_id
                )
                profile = user_info_response.get("user", {}).get("profile", {})

                replacement = profile.get("email")
                if not replacement:
                    replacement = profile.get("real_name_normalized")
                    log.debug(
                        "%s Could not find email for %s, falling back to real name: %s",
                        log_id,
                        user_id,
                        replacement,
                    )

                if replacement:
                    log.debug(
                        "%s Resolved mention for %s to '%s'",
                        log_id,
                        user_id,
                        replacement,
                    )
                    modified_text = modified_text.replace(f"<@{user_id}>", replacement)
                else:
                    log.warning(
                        "%s Could not resolve mention for user ID %s (no email or real name found).",
                        log_id,
                        user_id,
                    )

            except SlackApiError as e:
                log.warning(
                    "%s Slack API error resolving mention for user ID %s: %s. Leaving mention in place.",
                    log_id,
                    user_id,
                    e,
                )
            except Exception as e:
                log.error(
                    "%s Unexpected error resolving mention for user ID %s: %s",
                    log_id,
                    user_id,
                    e,
                )

        return modified_text

    async def handle_cancel_request_action(self, body: Dict[str, Any], client: Any):
        """
        Handles the 'a2a_cancel_request_button' action from Slack.
        Updates the UI and initiates an A2A task cancellation.
        """
        log_id_prefix = f"{self.log_identifier}[CancelAction]"
        try:
            action_details = body.get("actions", [])[0]
            button_value_str = action_details.get("value")
            if not button_value_str:
                log.error("%s Missing value in cancel button action.", log_id_prefix)
                return

            button_payload = json.loads(button_value_str)
            task_id = button_payload.get("task_id")
            target_agent_name = button_payload.get("target_agent_name")
            channel_id = button_payload.get("channel_id")
            message_ts = button_payload.get("message_ts")

            if not all([task_id, target_agent_name, channel_id, message_ts]):
                log.error(
                    "%s Incomplete payload in cancel button value: %s",
                    log_id_prefix,
                    button_payload,
                )
                return

            log.info(
                "%s Processing cancel request for Task ID: %s, Agent: %s, Channel: %s, Message TS: %s",
                log_id_prefix,
                task_id,
                target_agent_name,
                channel_id,
                message_ts,
            )

            try:
                current_content = self.get_content_buffer(task_id)
                status_text_for_update = f":hourglass_flowing_sand: Cancelling request for task `{task_id}`..."

                updated_blocks = _build_current_slack_blocks(
                    status_text=status_text_for_update,
                    content_text=(current_content.strip() if current_content else " "),
                )
                await update_slack_message(
                    self,
                    channel_id,
                    message_ts,
                    status_text_for_update,
                    blocks=updated_blocks,
                )
                log.info(
                    "%s Updated Slack message to 'Cancelling...' for task %s.",
                    log_id_prefix,
                    task_id,
                )
            except Exception as ui_update_err:
                log.error(
                    "%s Failed to provide immediate UI feedback for cancel action: %s",
                    log_id_prefix,
                    ui_update_err,
                )

            try:
                target_topic, payload, user_properties = (
                    self.core_a2a_service.cancel_task(
                        agent_name=target_agent_name,
                        task_id=task_id,
                        client_id=self.gateway_id,
                        user_id=self.gateway_id,
                    )
                )
                self.publish_a2a_message(
                    topic=target_topic, payload=payload, user_properties=user_properties
                )
                log.info(
                    "%s A2A CancelTaskRequest sent for task %s to agent %s.",
                    log_id_prefix,
                    task_id,
                    target_agent_name,
                )
            except Exception as cancel_err:
                log.exception(
                    "%s Failed to send A2A CancelTaskRequest for task %s: %s",
                    log_id_prefix,
                    task_id,
                    cancel_err,
                )
                try:
                    error_status_text = f":warning: Failed to send cancellation request for task `{task_id}`."
                    error_blocks = _build_current_slack_blocks(
                        status_text=error_status_text,
                        content_text=(
                            self.get_content_buffer(task_id).strip()
                            if self.get_content_buffer(task_id)
                            else " "
                        ),
                    )
                    await update_slack_message(
                        self,
                        channel_id,
                        message_ts,
                        error_status_text,
                        blocks=error_blocks,
                    )
                except Exception:
                    pass
                return

            with self.context_lock:
                if task_id in self.active_cancellable_tasks:
                    self.active_cancellable_tasks.remove(task_id)
                    log.debug(
                        "%s Removed task %s from active_cancellable_tasks (cancel requested).",
                        log_id_prefix,
                        task_id,
                    )

        except json.JSONDecodeError as json_err:
            log.error(
                "%s Failed to parse JSON from button value: %s. Value: '%s'",
                log_id_prefix,
                json_err,
                button_value_str if "button_value_str" in locals() else "Unknown",
            )
        except Exception as e:
            log.exception(
                "%s Unhandled error in handle_cancel_request_action: %s",
                log_id_prefix,
                e,
            )
            raise

    async def _extract_initial_claims(
        self, external_event_data: Dict
    ) -> Optional[Dict[str, Any]]:
        """
        Extracts the primary identity claims from a Slack event.
        Attempts to retrieve the user's email via Slack API and caches it.
        Falls back to "slack:{team_id}:{user_id}" if email cannot be obtained.

        Args:
            external_event_data: The Slack event dictionary.

        Returns:
            A dictionary of initial claims, which MUST include an 'id' key,
            or None if authentication fails.
        """
        log_id_prefix = f"{self.log_identifier}[ExtractClaims]"
        if not isinstance(external_event_data, dict):
            log.error(
                "%s Expected Slack event dictionary, got %s",
                log_id_prefix,
                type(external_event_data),
            )
            return None

        slack_user_id = external_event_data.get("user")
        slack_team_id = external_event_data.get("team") or external_event_data.get(
            "team_id"
        )

        if not slack_user_id or not slack_team_id:
            log.warning(
                "%s Could not determine Slack user_id or team_id from event.",
                log_id_prefix,
            )
            return None

        cache_key = f"slack_email_cache:{slack_user_id}"
        if self.cache_service and self.slack_email_cache_ttl_seconds > 0:
            cached_claim = self.cache_service.get_data(cache_key)
            if cached_claim:
                if cached_claim == _NO_EMAIL_MARKER:
                    log.debug(
                        "%s Using fallback ID from cache for user %s.",
                        log_id_prefix,
                        slack_user_id,
                    )
                    return {
                        "id": f"slack:{slack_team_id}:{slack_user_id}",
                        "source": "slack_fallback",
                    }
                else:
                    log.debug(
                        "%s Using cached email for user %s.",
                        log_id_prefix,
                        slack_user_id,
                    )
                    return {
                        "id": cached_claim,
                        "email": cached_claim,
                        "source": "slack_api",
                    }

        try:
            if not hasattr(self.slack_app, "client") or self.slack_app.client is None:
                raise RuntimeError("Slack app client not initialized.")

            profile_response = await self.slack_app.client.users_profile_get(
                user=slack_user_id
            )
            user_email = profile_response.get("profile", {}).get("email")

            if user_email:
                log.info(
                    "%s Successfully fetched email for user %s: %s",
                    log_id_prefix,
                    slack_user_id,
                    user_email,
                )
                if self.cache_service:
                    self.cache_service.add_data(
                        cache_key, user_email, expiry=self.slack_email_cache_ttl_seconds
                    )
                return {"id": user_email, "email": user_email, "source": "slack_api"}
            else:
                raise ValueError("Email not found in profile")

        except Exception as e:
            log.warning(
                "%s Could not fetch email for Slack user %s: %s. Using fallback ID.",
                log_id_prefix,
                slack_user_id,
                e,
            )
            if self.cache_service:
                self.cache_service.add_data(
                    cache_key,
                    _NO_EMAIL_MARKER,
                    expiry=self.slack_email_cache_ttl_seconds,
                )
            return {
                "id": f"slack:{slack_team_id}:{slack_user_id}",
                "source": "slack_fallback",
            }

    def _start_listener(self) -> None:
        log.info(
            "%s [_start_listener] Scheduling Slack listener startup...",
            self.log_identifier,
        )
        if self.async_loop and self.async_loop.is_running():
            self.async_loop.create_task(self._start_slack_listener())
            log.info(
                "%s Slack listener startup task created on async_loop.",
                self.log_identifier,
            )
        elif self.async_loop:
            log.warning(
                "%s async_loop exists but is not running. Attempting to run _start_slack_listener via call_soon_threadsafe.",
                self.log_identifier,
            )
            self.async_loop.call_soon_threadsafe(
                self.async_loop.create_task, self._start_slack_listener()
            )
        else:
            log.error(
                "%s Cannot start Slack listener: self.async_loop is not available.",
                self.log_identifier,
            )
            self.stop_signal.set()

    def _stop_listener(self) -> None:
        log.info(
            "%s [_stop_listener] Attempting to stop Slack listener (AsyncSocketModeHandler)...",
            self.log_identifier,
        )
        if (
            self.slack_handler
            and hasattr(self.slack_handler, "stop")
            and callable(self.slack_handler.stop)
        ):
            try:
                log.info(
                    "%s Calling AsyncSocketModeHandler.stop()...", self.log_identifier
                )
                self.slack_handler.stop()
                log.info(
                    "%s AsyncSocketModeHandler.stop() called successfully.",
                    self.log_identifier,
                )
            except Exception as e:
                log.error(
                    "%s Error calling AsyncSocketModeHandler.stop(): %s",
                    self.log_identifier,
                    e,
                    exc_info=True,
                )
        elif self.slack_handler:
            log.warning(
                "%s Slack handler instance present but does not have a callable 'stop' method. Type: %s",
                self.log_identifier,
                type(self.slack_handler).__name__,
            )
        else:
            log.debug(
                "%s No Slack handler (self.slack_handler) instance to stop.",
                self.log_identifier,
            )

    async def _download_slack_file_content(self, file_info: Dict) -> Dict[str, Any]:
        file_url = file_info.get("url_private")
        file_name = file_info.get("name", "unknown_file")
        mime_type = file_info.get("mimetype", "application/octet-stream")
        log_id = f"{self.log_identifier}[FileDownload:{file_name}]"
        if not file_url:
            log.warning("%s File URL is missing in file info.", log_id)
            return {"error": "Missing file URL"}
        try:
            headers = {"Authorization": f"Bearer {self.slack_bot_token}"}
            response = await asyncio.to_thread(
                requests.get, file_url, headers=headers, timeout=20
            )
            response.raise_for_status()
            content_bytes = response.content
            log.info("%s Successfully downloaded %d bytes.", log_id, len(content_bytes))
            return {"name": file_name, "content": content_bytes, "mime_type": mime_type}
        except requests.exceptions.RequestException as e:
            log.error("%s Failed to download file: %s", log_id, e)
            return {"error": f"Failed to download file: {e}"}
        except Exception as e:
            log.exception("%s Unexpected error downloading file: %s", log_id, e)
            return {"error": f"Unexpected error downloading file: {e}"}

    async def _translate_external_input(
        self, external_event: Any, authenticated_user_identity: Dict[str, Any]
    ) -> Tuple[str, List[A2APart], Dict[str, Any]]:
        log_id = f"{self.log_identifier}[TranslateInput]"
        event: Dict = external_event
        if event.get("bot_id") or event.get("subtype") == "bot_message":
            log.debug("%s Ignoring message from bot.", log_id)
            raise ValueError("Ignoring bot message")
        try:
            auth_test_result = await self.slack_app.client.auth_test()
            bot_user_id = auth_test_result.get("user_id")
            if not bot_user_id:
                log.error(
                    "%s Could not determine bot user ID. Cannot filter mentions.",
                    log_id,
                )
                raise ValueError("Cannot determine bot user ID")
        except Exception as auth_err:
            log.error("%s Failed to call auth.test: %s", log_id, auth_err)
            raise ValueError(f"Failed to get bot user ID: {auth_err}")
        if event.get("subtype") == "thread_broadcast" and not event.get(
            "text", ""
        ).startswith(f"<@{bot_user_id}>"):
            log.debug("%s Ignoring thread broadcast (not a mention).", log_id)
            raise ValueError("Ignoring non-mention thread broadcast")
        channel_id = event.get("channel")
        thread_ts = event.get("thread_ts") or event.get("ts")
        message_ts = event.get("ts")
        slack_user_id = event.get("user")
        slack_team_id = event.get("team") or event.get("team_id")
        text = event.get("text", "")
        files_info = event.get("files", [])

        resolved_text = await self._resolve_mentions_in_text(text)

        if not channel_id or not message_ts or not slack_user_id or not slack_team_id:
            log.warning("%s Missing critical context in event: %s", log_id, event)
            raise ValueError("Missing critical Slack context (channel, ts, user, team)")
        log.info(
            "%s Translating event from User: %s, Team: %s, Channel: %s, MsgTS: %s (ThreadTS: %s)",
            log_id,
            slack_user_id,
            slack_team_id,
            channel_id,
            message_ts,
            thread_ts or "N/A",
        )
        target_agent_name = self.default_agent_name
        if not target_agent_name:
            log.error("%s No target agent determined.", log_id)
            raise ValueError("Cannot determine target agent")
        a2a_session_id = generate_a2a_session_id(
            channel_id, thread_ts, target_agent_name
        )
        a2a_parts: List[A2APart] = []
        file_metadata_summary_parts: List[str] = []
        processed_text_for_a2a = resolved_text
        if files_info and self.shared_artifact_service:
            log.info("%s Found %d file(s). Processing...", log_id, len(files_info))
            user_id_for_artifacts = authenticated_user_identity.get("id")
            for file_info_slack in files_info:
                download_result = await self._download_slack_file_content(
                    file_info_slack
                )
                if "error" in download_result:
                    log.error(
                        "%s File download failed: %s", log_id, download_result["error"]
                    )
                    continue
                content_bytes = download_result["content"]
                original_filename = download_result["name"]
                mime_type = download_result["mime_type"]
                try:
                    save_result = await save_artifact_with_metadata(
                        artifact_service=self.shared_artifact_service,
                        app_name=self.gateway_id,
                        user_id=user_id_for_artifacts,
                        session_id=a2a_session_id,
                        filename=original_filename,
                        content_bytes=content_bytes,
                        mime_type=mime_type,
                        metadata_dict={
                            "source": "slack_gateway_upload",
                            "original_filename": original_filename,
                            "slack_user_id": slack_user_id,
                            "slack_team_id": slack_team_id,
                            "slack_channel_id": channel_id,
                            "slack_message_ts": message_ts,
                            "slack_thread_ts": thread_ts,
                            "upload_timestamp_utc": datetime.now(
                                timezone.utc
                            ).isoformat(),
                            "gateway_id": self.gateway_id,
                            "a2a_session_id": a2a_session_id,
                        },
                        timestamp=datetime.now(timezone.utc),
                    )
                    if save_result["status"] in ["success", "partial_success"]:
                        data_version = save_result.get("data_version", 0)
                        artifact_uri = f"artifact://{self.gateway_id}/{user_id_for_artifacts}/{a2a_session_id}/{original_filename}?version={data_version}"
                        file_content_a2a = FileContent(
                            name=original_filename, mimeType=mime_type, uri=artifact_uri
                        )
                        a2a_parts.append(FilePart(file=file_content_a2a))
                        file_metadata_summary_parts.append(
                            f"- {original_filename} ({mime_type}, {len(content_bytes)} bytes, URI: {artifact_uri})"
                        )
                        log.info(
                            "%s Created URI for uploaded file: %s", log_id, artifact_uri
                        )
                    else:
                        log.error(
                            "%s Failed to save artifact %s: %s",
                            log_id,
                            original_filename,
                            save_result.get("message"),
                        )
                except Exception as e:
                    log.exception(
                        "%s Error saving artifact %s: %s", log_id, original_filename, e
                    )
        if file_metadata_summary_parts:
            summary_text = "The user uploaded the following file(s):\n" + "\n".join(
                file_metadata_summary_parts
            )
            processed_text_for_a2a = f"{summary_text}\n\nUser message: {resolved_text}"
        if processed_text_for_a2a:
            a2a_parts.append(TextPart(text=processed_text_for_a2a))
        if not a2a_parts:
            log.warning(
                "%s No text or successfully processed files. Cannot create A2A message.",
                log_id,
            )
            raise ValueError("No content to send to agent")
        external_request_context = {
            "slack_channel_id": channel_id,
            "slack_thread_ts": thread_ts,
            "slack_message_ts": message_ts,
            "slack_user_id": slack_user_id,
            "slack_team_id": slack_team_id,
            "a2a_session_id": a2a_session_id,
            "app_name_for_artifacts": self.gateway_id,
            "user_id_for_artifacts": authenticated_user_identity.get("id"),
            "user_id_for_a2a": authenticated_user_identity.get("id"),
            "target_agent_name": target_agent_name,
        }
        log.debug(
            "%s Translation complete. Target: %s, Parts: %d",
            log_id,
            target_agent_name,
            len(a2a_parts),
        )
        return target_agent_name, a2a_parts, external_request_context

    async def _update_slack_ui_state(
        self,
        task_id: str,
        external_request_context: Dict[str, Any],
        text_to_display: Optional[str],
        data_parts_for_slack: List[str],
        file_infos_for_slack: List[Dict],
        status_signal_text: Optional[str],
        is_final_event: bool,
    ):
        log_id = f"{self.log_identifier}[UpdateSlackUI:{task_id}]"
        channel_id = external_request_context.get("slack_channel_id")
        thread_ts = external_request_context.get("slack_thread_ts")

        if not channel_id or not thread_ts:
            log.error(
                "%s Missing 'slack_channel_id' or 'slack_thread_ts' in external_request_context. Cannot update Slack UI.",
                log_id,
            )
            return

        if data_parts_for_slack or file_infos_for_slack:
            buffered_text_before_data_artifact = self.get_content_buffer(task_id)
            content_ts_before_data_artifact = self.get_content_ts(task_id)
            if buffered_text_before_data_artifact and content_ts_before_data_artifact:
                log.debug(
                    "%s Finalizing buffered content message (TS: %s) before sending DataPart/Artifact.",
                    log_id,
                    content_ts_before_data_artifact,
                )

                resolved_final_buffer, _, _ = await self.resolve_and_format_for_slack(
                    buffered_text_before_data_artifact, task_id
                )

                content_blocks = _build_current_slack_blocks(
                    content_text=resolved_final_buffer
                )
                await update_slack_message(
                    self,
                    channel_id,
                    content_ts_before_data_artifact,
                    resolved_final_buffer or " ",
                    blocks=content_blocks,
                )

            self.clear_content_buffer(task_id)
            self.clear_content_ts(task_id)
            log.debug(
                "%s Cleared content buffer and TS due to DataPart/Artifact.", log_id
            )

            for data_content in data_parts_for_slack:
                log.info("%s Sending DataPart content as separate message.", log_id)
                await send_slack_message(self, channel_id, thread_ts, data_content)

            for file_info in file_infos_for_slack:
                if file_info.get("bytes"):
                    await upload_slack_file(
                        self,
                        channel_id,
                        thread_ts,
                        file_info["name"],
                        file_info["bytes"],
                        file_info["mime_type"],
                    )
                elif file_info.get("uri"):
                    uri_text = f":link: Artifact available: {file_info['name']} - {file_info['uri']}"
                    await send_slack_message(self, channel_id, thread_ts, uri_text)

        effective_status_text = status_signal_text
        if is_final_event:
            effective_status_text = (
                ":x: Error"
                if status_signal_text and "Error" in status_signal_text
                else ":checkered_flag: Task complete."
            )
            log.info(
                "%s Setting final status text: '%s'", log_id, effective_status_text
            )

        cancel_button_elements = None
        if not is_final_event and task_id in self.active_cancellable_tasks:
            status_ts_for_button_val = self.get_status_ts(task_id)
            button_value_payload = {
                "task_id": task_id,
                "target_agent_name": external_request_context.get(
                    "target_agent_name", self.default_agent_name
                ),
                "channel_id": channel_id,
                "message_ts": status_ts_for_button_val,
            }
            button_value_payload_filtered = {
                k: v for k, v in button_value_payload.items() if v is not None
            }

            cancel_button_elements = [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Cancel Request",
                        "emoji": True,
                    },
                    "style": "danger",
                    "action_id": CANCEL_BUTTON_ACTION_ID,
                    "value": json.dumps(button_value_payload_filtered),
                }
            ]
            log.debug(
                "%s Constructed cancel button elements for task %s.", log_id, task_id
            )

        if effective_status_text:
            current_status_on_slack = self.get_current_status(task_id)
            if (
                effective_status_text != current_status_on_slack
                or cancel_button_elements
            ):
                status_ts = self.get_status_ts(task_id)
                status_blocks_for_update = _build_current_slack_blocks(
                    status_text=effective_status_text,
                    cancel_button_action_elements=cancel_button_elements,
                )
                if status_ts:
                    log.debug(
                        "%s Updating status message (TS: %s) to: '%s'. Cancel button included: %s",
                        log_id,
                        status_ts,
                        effective_status_text,
                        cancel_button_elements is not None,
                    )
                    await update_slack_message(
                        self,
                        channel_id,
                        status_ts,
                        effective_status_text,
                        blocks=status_blocks_for_update,
                    )
                else:
                    log.warning(
                        "%s Status TS not found for task %s. Posting new status message: '%s'",
                        log_id,
                        task_id,
                        effective_status_text,
                    )
                    new_status_ts = await send_slack_message(
                        self,
                        channel_id,
                        thread_ts,
                        effective_status_text,
                        blocks=status_blocks_for_update,
                    )
                    if new_status_ts:
                        self.set_status_ts(task_id, new_status_ts)

                self.set_current_status(task_id, effective_status_text)
            else:
                log.debug(
                    "%s Skipping status update: Status text unchanged ('%s') and cancel button state also unchanged.",
                    log_id,
                    effective_status_text,
                )

        if not is_final_event and text_to_display is not None:
            current_buffer = self.get_content_buffer(task_id)
            new_buffer_content = current_buffer + text_to_display
            self.set_content_buffer(task_id, new_buffer_content)
            log.debug(
                "%s Appended to Slack content buffer. New total length: %d",
                log_id,
                len(new_buffer_content),
            )

            display_content = new_buffer_content.strip() if new_buffer_content else " "
            content_blocks = _build_current_slack_blocks(content_text=display_content)
            content_ts = self.get_content_ts(task_id)

            if content_ts:
                log.debug(
                    "%s Updating content message (TS: %s) with %d chars (total buffer).",
                    log_id,
                    content_ts,
                    len(display_content),
                )
                await update_slack_message(
                    self, channel_id, content_ts, display_content, blocks=content_blocks
                )
            else:
                log.debug(
                    "%s Posting new content message with %d chars (total buffer).",
                    log_id,
                    len(display_content),
                )
                new_content_ts = await send_slack_message(
                    self, channel_id, thread_ts, display_content, blocks=content_blocks
                )
                if new_content_ts:
                    self.set_content_ts(task_id, new_content_ts)
        if is_final_event:
            log.info("%s Performing final state handling for task %s.", log_id, task_id)

            final_buffered_content = self.get_content_buffer(task_id)
            final_content_ts = self.get_content_ts(task_id)
            if final_buffered_content:
                log.info(
                    "%s Flushing final content buffer (%d chars) to content message (TS: %s).",
                    log_id,
                    len(final_buffered_content),
                    final_content_ts or "New Message",
                )
                final_display_content = (
                    final_buffered_content.strip() if final_buffered_content else " "
                )
                final_content_blocks = _build_current_slack_blocks(
                    content_text=final_display_content
                )
                if final_content_ts:
                    await update_slack_message(
                        self,
                        channel_id,
                        final_content_ts,
                        final_display_content,
                        blocks=final_content_blocks,
                    )
                else:
                    new_final_content_ts = await send_slack_message(
                        self,
                        channel_id,
                        thread_ts,
                        final_display_content,
                        blocks=final_content_blocks,
                    )
                    if new_final_content_ts:
                        self.set_content_ts(task_id, new_final_content_ts)
            self.clear_content_buffer(task_id)

            status_ts_for_feedback = self.get_status_ts(task_id)
            final_status_text_for_slack = (
                self.get_current_status(task_id) or effective_status_text
            )

            feedback_elements = None
            if self.feedback_enabled:
                feedback_data = {
                    "task_id": task_id,
                    "session_id": external_request_context.get(
                        "a2a_session_id", "unknown"
                    ),
                    "user_id": external_request_context.get("slack_user_id", "unknown"),
                }
                feedback_block_list = create_feedback_blocks(
                    feedback_data, channel_id, thread_ts
                )
                if feedback_block_list:
                    feedback_elements = feedback_block_list[0].get("elements")

            final_status_blocks_with_feedback = _build_current_slack_blocks(
                status_text=final_status_text_for_slack,
                feedback_elements=feedback_elements,
            )
            if status_ts_for_feedback:
                await update_slack_message(
                    self,
                    channel_id,
                    status_ts_for_feedback,
                    final_status_text_for_slack,
                    blocks=final_status_blocks_with_feedback,
                )
            else:
                log.warning(
                    "%s Cannot update final status with feedback for task %s: Status message TS not found. Posting new.",
                    log_id,
                    task_id,
                )
                await send_slack_message(
                    self,
                    channel_id,
                    thread_ts,
                    final_status_text_for_slack,
                    blocks=final_status_blocks_with_feedback,
                )

            with self.context_lock:
                if task_id in self.active_cancellable_tasks:
                    self.active_cancellable_tasks.remove(task_id)
                    log.debug(
                        "%s Removed task %s from active_cancellable_tasks (final event).",
                        log_id,
                        task_id,
                    )
            self.remove_slack_context(task_id)

    async def _send_update_to_external(
        self,
        external_request_context: Dict[str, Any],
        event_data: Union[TaskStatusUpdateEvent, TaskArtifactUpdateEvent],
        is_final_chunk_of_update: bool,
    ) -> None:
        task_id = event_data.id
        log_id = f"{self.log_identifier}[SendUpdateExt:{task_id}]"
        log.debug(
            "%s Received event type: %s. GDK final_chunk_of_update: %s",
            log_id,
            type(event_data).__name__,
            is_final_chunk_of_update,
        )

        text_to_display: Optional[str] = None
        data_parts_for_slack: List[str] = []
        file_infos_for_slack: List[Dict] = []
        status_signal_text: Optional[str] = None

        if isinstance(event_data, TaskStatusUpdateEvent):
            temp_text_parts = []
            if (
                event_data.status
                and event_data.status.message
                and event_data.status.message.parts
            ):
                for part in event_data.status.message.parts:
                    if isinstance(part, TextPart):
                        if not is_final_chunk_of_update:
                            corrected_text = (
                                correct_slack_markdown(part.text)
                                if self.correct_markdown_formatting
                                else part.text
                            )
                            temp_text_parts.append(corrected_text)
                    elif isinstance(part, DataPart):
                        if part.data.get("a2a_signal_type") == "agent_status_message":
                            signal_text = part.data.get("text", "[Agent status update]")
                            status_signal_text = f":thinking_face: {signal_text}"
                            log.debug(
                                "%s Processed DataPart as agent_status_message signal: '%s'",
                                log_id,
                                status_signal_text,
                            )

            if temp_text_parts:
                text_to_display = "".join(temp_text_parts)
                if status_signal_text and (
                    not text_to_display or text_to_display.isspace()
                ):
                    log.debug(
                        "%s Status signal ('%s') present and text_to_display ('%s') is empty/whitespace. Setting text_to_display to None.",
                        log_id,
                        status_signal_text,
                        text_to_display,
                    )
                    text_to_display = None

        elif isinstance(event_data, TaskArtifactUpdateEvent):
            if event_data.artifact and event_data.artifact.parts:
                for part in event_data.artifact.parts:
                    if isinstance(part, FilePart) and part.file:
                        file_info = {
                            "name": part.file.name or f"artifact_{task_id}",
                            "mime_type": part.file.mimeType,
                            "bytes": None,
                            "uri": None,
                        }
                        if part.file.bytes:
                            try:
                                file_info["bytes"] = base64.b64decode(part.file.bytes)
                            except Exception as e:
                                log.error(
                                    "%s Failed to decode base64 bytes for artifact '%s': %s",
                                    log_id,
                                    file_info["name"],
                                    e,
                                )
                        elif part.file.uri:
                            file_info["uri"] = part.file.uri
                        if file_info["bytes"] or file_info["uri"]:
                            file_infos_for_slack.append(file_info)

        await self._update_slack_ui_state(
            task_id,
            external_request_context,
            text_to_display,
            data_parts_for_slack,
            file_infos_for_slack,
            status_signal_text,
            is_final_event=False,
        )

    async def _send_final_response_to_external(
        self, external_request_context: Dict[str, Any], task_data: Task
    ) -> None:
        task_id = task_data.id
        log_id = f"{self.log_identifier}[SendFinalResponseExt:{task_id}]"
        log.debug("%s Processing final task data.", log_id)

        text_to_display: Optional[str] = None
        data_parts_for_slack: List[str] = []

        final_status_text_for_slack = ":checkered_flag: Task complete."
        if task_data.status:
            if task_data.status.state == TaskState.FAILED:
                error_message_text = ""
                if task_data.status.message and task_data.status.message.parts:
                    for part in task_data.status.message.parts:
                        if isinstance(part, TextPart):
                            error_message_text = part.text
                            break
                final_status_text_for_slack = (
                    f":x: Error: Task failed. {error_message_text}".strip()
                )
            elif task_data.status.state == TaskState.CANCELED:
                final_status_text_for_slack = ":octagonal_sign: Task canceled."

        await self._update_slack_ui_state(
            task_id,
            external_request_context,
            text_to_display,
            data_parts_for_slack,
            [],
            final_status_text_for_slack,
            is_final_event=True,
        )

    async def _send_error_to_external(
        self, external_request_context: Dict[str, Any], error_data: JSONRPCError
    ) -> None:
        task_id = external_request_context.get(
            "a2a_task_id_for_event", "unknown_task_error"
        )
        log_id = f"{self.log_identifier}[SendErrorExt:{task_id}]"
        log.debug("%s Processing error: %s", log_id, error_data.message)

        error_text_for_slack = (
            f":boom: An error occurred: {error_data.message} (Code: {error_data.code})"
        )
        if error_data.data:
            try:
                error_details = json.dumps(error_data.data, indent=2)
                error_text_for_slack += f"\nDetails:\n```\n{error_details}\n```"
            except Exception:
                error_text_for_slack += f"\nDetails: {str(error_data.data)}"

        await self._update_slack_ui_state(
            task_id,
            external_request_context,
            None,
            [],
            [],
            error_text_for_slack,
            is_final_event=True,
        )
        with self.context_lock:
            if task_id in self.active_cancellable_tasks:
                self.active_cancellable_tasks.remove(task_id)
                log.debug(
                    "%s Removed task %s from active_cancellable_tasks (error event).",
                    log_id,
                    task_id,
                )

    def run(self):
        log.info("%s SlackGatewayComponent.run() called.", self.log_identifier)
        super().run()
        log.info("%s SlackGatewayComponent.run() finished.", self.log_identifier)

    async def _start_slack_listener(self):
        if not self.slack_app_token:
            log.error(
                f"{self.log_identifier} Slack App Token is required for Socket Mode."
            )
            self.stop_signal.set()
            raise ValueError("Slack App Token is required for Socket Mode.")

        log.info("%s Starting Slack AsyncSocketModeHandler...", self.log_identifier)
        try:
            self.slack_handler = AsyncSocketModeHandler(
                self.slack_app, self.slack_app_token
            )
            await self.slack_handler.start_async()
            log.info("%s Slack AsyncSocketModeHandler finished.", self.log_identifier)
        except Exception as e:
            log.exception(
                "%s Error in AsyncSocketModeHandler: %s", self.log_identifier, e
            )
            self.stop_signal.set()

    def cleanup(self):
        log.info(
            "%s Cleaning up Slack Gateway Component (Pre-Base)...", self.log_identifier
        )
        super().cleanup()
        with self.context_lock:
            self.task_slack_context.clear()
            self.status_message_ts.clear()
            self.content_message_ts.clear()
            self.content_message_buffer.clear()
            self.current_status_text.clear()
        log.info(
            "%s Cleared Slack-specific internal state maps and buffers.",
            self.log_identifier,
        )
        log.info("%s Slack Gateway Component cleanup finished.", self.log_identifier)

    def get_slack_context(self, task_id: str) -> Optional[Dict[str, str]]:
        with self.context_lock:
            return self.task_slack_context.get(task_id)

    def remove_slack_context(self, task_id: str):
        with self.context_lock:
            removed_context = self.task_slack_context.pop(task_id, None)
            removed_status_ts = self.status_message_ts.pop(task_id, None)
            removed_content_ts = self.content_message_ts.pop(task_id, None)
            removed_buffer = self.content_message_buffer.pop(task_id, None)
            removed_current_status = self.current_status_text.pop(task_id, None)
            if (
                removed_context
                or removed_status_ts
                or removed_content_ts
                or removed_buffer is not None
                or removed_current_status is not None
            ):
                log.debug(
                    "%s Removed context and state for task %s.",
                    self.log_identifier,
                    task_id,
                )

    def get_status_ts(self, task_id: str) -> Optional[str]:
        with self.context_lock:
            return self.status_message_ts.get(task_id)

    def set_status_ts(self, task_id: str, ts: Optional[str]):
        with self.context_lock:
            self.status_message_ts[task_id] = ts

    def get_content_ts(self, task_id: str) -> Optional[str]:
        with self.context_lock:
            return self.content_message_ts.get(task_id)

    def set_content_ts(self, task_id: str, ts: Optional[str]):
        with self.context_lock:
            self.content_message_ts[task_id] = ts

    def clear_content_ts(self, task_id: str):
        with self.context_lock:
            self.content_message_ts[task_id] = None

    def get_content_buffer(self, task_id: str) -> str:
        with self.context_lock:
            return self.content_message_buffer.get(task_id, "")

    def set_content_buffer(self, task_id: str, content: str):
        with self.context_lock:
            self.content_message_buffer[task_id] = content

    def clear_content_buffer(self, task_id: str):
        with self.context_lock:
            self.content_message_buffer[task_id] = ""

    def get_current_status(self, task_id: str) -> Optional[str]:
        with self.context_lock:
            return self.current_status_text.get(task_id)

    def set_current_status(self, task_id: str, status_text: Optional[str]):
        with self.context_lock:
            self.current_status_text[task_id] = status_text

    async def resolve_and_format_for_slack(
        self, text: str, task_id: str
    ) -> Tuple[str, int, List[Tuple[int, Any]]]:
        """
        Resolves late-stage embeds in text and applies Slack markdown correction.
        Now runs synchronously and returns processed_until_index.
        """
        from solace_agent_mesh.common.utils.embeds import (
            resolve_embeds_in_string,
            evaluate_embed,
            LATE_EMBED_TYPES,
            EMBED_DELIMITER_OPEN,
        )

        log_id = f"{self.log_identifier}[ResolveSlack:{task_id}]"
        resolved_text = text
        signals_found: List[Tuple[int, Any]] = []
        processed_until_index = len(text)

        if self.enable_embed_resolution and text and EMBED_DELIMITER_OPEN in text:
            log.debug(
                "%s Performing late-stage embed resolution for Slack output...", log_id
            )
            session_context_data = None
            with self.context_lock:
                slack_context = self.task_slack_context.get(task_id)
                if slack_context:
                    session_context_data = {
                        "app_name": self.gateway_id,
                        "user_id": slack_context.get("user", "unknown_slack_user"),
                        "session_id": generate_a2a_session_id(
                            slack_context.get("channel"),
                            slack_context.get("thread_ts"),
                            self.default_agent_name or "UnknownAgent",
                        ),
                    }
                else:
                    log.warning(
                        "%s Slack context not found for Task ID: %s during embed resolution.",
                        log_id,
                        task_id,
                    )

            if not session_context_data:
                log.warning(
                    "%s Cannot resolve embeds: Session context could not be constructed for Task ID: %s",
                    log_id,
                    task_id,
                )
                return text, len(text), []
            elif not self.shared_artifact_service:
                log.warning(
                    "%s Cannot resolve artifact_content embeds: ArtifactService not available.",
                    log_id,
                )
                types_to_resolve = LATE_EMBED_TYPES.copy()
            else:
                types_to_resolve = LATE_EMBED_TYPES.copy()

            gateway_context_for_embed = {
                "artifact_service": self.shared_artifact_service,
                "session_context": session_context_data,
            }
            embed_config_for_resolve = {
                "gateway_max_artifact_resolve_size_bytes": self.gateway_max_artifact_resolve_size_bytes,
                "gateway_recursive_embed_depth": self.gateway_recursive_embed_depth,
            }

            try:
                resolved_text, processed_until_index, signals_found = (
                    await asyncio.to_thread(
                        resolve_embeds_in_string,
                        text=text,
                        context=gateway_context_for_embed,
                        resolver_func=evaluate_embed,
                        types_to_resolve=types_to_resolve,
                        log_identifier=log_id,
                        config=embed_config_for_resolve,
                    )
                )

                if resolved_text != text or signals_found:
                    log.info(
                        "%s Embed/signal resolution complete (Processed Index: %d, Signals: %d).",
                        log_id,
                        processed_until_index,
                        len(signals_found),
                    )
                else:
                    log.debug("%s No embeds/signals resolved.", log_id)

            except Exception as e:
                log.exception("%s Error during embed resolution: %s", log_id, e)
                resolved_text = (
                    text + f"\n\n[:warning: Error resolving dynamic content: {e}]"
                )
                processed_until_index = len(text)
                signals_found = []

        if self.correct_markdown_formatting:
            formatted_text = correct_slack_markdown(resolved_text)
            if formatted_text != resolved_text:
                log.debug("%s Applied Slack markdown corrections.", log_id)
            return (
                formatted_text,
                processed_until_index,
                signals_found,
            )
        else:
            return (
                resolved_text,
                processed_until_index,
                signals_found,
            )
