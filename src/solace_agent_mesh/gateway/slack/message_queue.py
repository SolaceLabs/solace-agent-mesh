"""
Sequential message queue for Slack to ensure proper ordering of text and file posts.

This module provides a per-task queue that manages all Slack API operations,
ensuring that files are fully visible in the channel before subsequent messages
are posted, preventing race conditions and out-of-order message appearance.
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from slack_sdk.web.async_client import AsyncWebClient

if TYPE_CHECKING:
    from .adapter import SlackAdapter

log = logging.getLogger(__name__)


# --- Queue Operation Types ---


@dataclass
class QueueOperation:
    """Base class for all queue operations."""

    pass


@dataclass
class TextUpdateOp(QueueOperation):
    """Append text to the current buffered message."""

    text: str


@dataclass
class FileUploadOp(QueueOperation):
    """Upload a file with polling to ensure visibility."""

    filename: str
    content_bytes: bytes
    initial_comment: Optional[str] = None


@dataclass
class MessagePostOp(QueueOperation):
    """Post a new message to the channel."""

    text: str
    blocks: Optional[List[Dict]] = None


@dataclass
class MessageUpdateOp(QueueOperation):
    """Update an existing message."""

    ts: str
    text: str
    blocks: Optional[List[Dict]] = None


@dataclass
class MessageDeleteOp(QueueOperation):
    """Delete an existing message."""

    ts: str


@dataclass
class StopSignal(QueueOperation):
    """Sentinel to stop the queue processor."""

    pass


# --- Main Queue Class ---


class SlackMessageQueue:
    """
    Sequential message queue for a single Slack task.

    Ensures proper ordering of text messages and file uploads by:
    1. Buffering text updates into a single message
    2. Polling files.info after uploads until file is visible
    3. Resetting text state after file uploads (forcing new message)
    4. Processing all operations sequentially in a background task
    """

    def __init__(
        self,
        task_id: str,
        slack_client: AsyncWebClient,
        channel_id: str,
        thread_ts: str,
        adapter: "SlackAdapter",
    ):
        """
        Initialize a message queue for a specific task.

        Args:
            task_id: Unique identifier for this task
            slack_client: Async Slack API client
            channel_id: Target Slack channel ID
            thread_ts: Thread timestamp for replies
            adapter: Reference to SlackAdapter for task state access
        """
        self.task_id = task_id
        self.client = slack_client
        self.channel_id = channel_id
        self.thread_ts = thread_ts
        self.adapter = adapter

        # Queue and processor
        self.queue: asyncio.Queue[QueueOperation] = asyncio.Queue()
        self.processor_task: Optional[asyncio.Task] = None

        # State for text message buffering
        self.current_text_message_ts: Optional[str] = None
        self.text_buffer: str = ""

        log.debug(f"[Queue:{task_id}] Initialized for channel {channel_id}")

    async def start(self):
        """Start the background queue processor."""
        if self.processor_task is None or self.processor_task.done():
            self.processor_task = asyncio.create_task(
                self._process_queue(), name=f"slack-queue-{self.task_id}"
            )
            log.info(f"[Queue:{self.task_id}] Started queue processor")

    async def stop(self):
        """Stop the queue processor and wait for completion."""
        if self.processor_task and not self.processor_task.done():
            log.info(f"[Queue:{self.task_id}] Stopping queue processor")
            await self.queue.put(StopSignal())
            try:
                await asyncio.wait_for(self.processor_task, timeout=60.0)
            except asyncio.TimeoutError:
                log.error(
                    f"[Queue:{self.task_id}] Timeout waiting for queue to stop, cancelling"
                )
                self.processor_task.cancel()
            log.info(f"[Queue:{self.task_id}] Queue processor stopped")

    async def wait_until_complete(self):
        """Wait for all queued operations to be processed."""
        await self.queue.join()
        log.debug(f"[Queue:{self.task_id}] All operations complete")

    # --- Queue Operation Methods ---

    async def queue_text_update(self, text: str):
        """Queue a text update to be appended to the current message."""
        await self.queue.put(TextUpdateOp(text=text))
        log.debug(f"[Queue:{self.task_id}] Queued text update: {text[:50]}...")

    async def queue_file_upload(
        self, filename: str, content_bytes: bytes, initial_comment: Optional[str] = None
    ):
        """Queue a file upload with automatic polling for visibility."""
        await self.queue.put(
            FileUploadOp(
                filename=filename,
                content_bytes=content_bytes,
                initial_comment=initial_comment,
            )
        )
        log.debug(
            f"[Queue:{self.task_id}] Queued file upload: {filename} ({len(content_bytes)} bytes)"
        )

    async def queue_message_post(self, text: str, blocks: Optional[List[Dict]] = None):
        """Queue posting a new message."""
        await self.queue.put(MessagePostOp(text=text, blocks=blocks))
        log.debug(f"[Queue:{self.task_id}] Queued message post: {text[:50]}...")

    async def queue_message_update(
        self, ts: str, text: str, blocks: Optional[List[Dict]] = None
    ):
        """Queue updating an existing message."""
        await self.queue.put(MessageUpdateOp(ts=ts, text=text, blocks=blocks))
        log.debug(f"[Queue:{self.task_id}] Queued message update for ts={ts}")

    async def queue_message_delete(self, ts: str):
        """Queue deleting a message."""
        await self.queue.put(MessageDeleteOp(ts=ts))
        log.debug(f"[Queue:{self.task_id}] Queued message delete for ts={ts}")

    # --- Queue Processor ---

    async def _process_queue(self):
        """Background task that processes queue operations sequentially."""
        log.info(f"[Queue:{self.task_id}] Queue processor started")
        try:
            while True:
                operation = await self.queue.get()

                if isinstance(operation, StopSignal):
                    log.debug(f"[Queue:{self.task_id}] Received stop signal")
                    self.queue.task_done()
                    break

                try:
                    if isinstance(operation, TextUpdateOp):
                        await self._handle_text_update(operation)
                    elif isinstance(operation, FileUploadOp):
                        await self._handle_file_upload(operation)
                    elif isinstance(operation, MessagePostOp):
                        await self._handle_message_post(operation)
                    elif isinstance(operation, MessageUpdateOp):
                        await self._handle_message_update(operation)
                    elif isinstance(operation, MessageDeleteOp):
                        await self._handle_message_delete(operation)
                    else:
                        log.warning(
                            f"[Queue:{self.task_id}] Unknown operation type: {type(operation)}"
                        )

                except Exception as e:
                    log.error(
                        f"[Queue:{self.task_id}] Error processing operation {operation}: {e}",
                        exc_info=True,
                    )
                    # Continue processing despite error

                finally:
                    self.queue.task_done()

        except Exception as e:
            log.error(
                f"[Queue:{self.task_id}] Fatal error in queue processor: {e}",
                exc_info=True,
            )
        finally:
            log.info(f"[Queue:{self.task_id}] Queue processor stopped")

    # --- Operation Handlers ---

    async def _handle_text_update(self, op: TextUpdateOp):
        """Handle appending text to the current message buffer."""
        log.debug(f"[Queue:{self.task_id}] Processing text update: {op.text[:50]}...")

        # Append RAW text to buffer
        self.text_buffer += op.text

        # Format the FULL buffer (not individual chunks!)
        formatted_text = self.adapter._format_text(self.text_buffer)

        if not self.current_text_message_ts:
            # Post a new message with formatted text
            log.info(f"[Queue:{self.task_id}] Posting new text message")
            response = await self.client.chat_postMessage(
                channel=self.channel_id,
                thread_ts=self.thread_ts,
                text=formatted_text,
            )
            self.current_text_message_ts = response.get("ts")
            log.info(
                f"[Queue:{self.task_id}] Posted new message with ts={self.current_text_message_ts}"
            )
        else:
            # Update existing message with formatted text
            log.debug(
                f"[Queue:{self.task_id}] Updating text message ts={self.current_text_message_ts}"
            )
            await self.client.chat_update(
                channel=self.channel_id,
                ts=self.current_text_message_ts,
                text=formatted_text,
            )
            log.debug(f"[Queue:{self.task_id}] Updated message")

    async def _handle_file_upload(self, op: FileUploadOp):
        """
        Handle file upload with polling to ensure visibility.

        This is the critical operation that prevents race conditions.
        """
        log.info(f"[Queue:{self.task_id}] Processing file upload: {op.filename}")

        # Step 1: Finalize any pending text message
        if self.text_buffer and self.current_text_message_ts:
            log.info(
                f"[Queue:{self.task_id}] Finalizing text message before file upload"
            )
            await self.client.chat_update(
                channel=self.channel_id,
                ts=self.current_text_message_ts,
                text=self.text_buffer,
            )

        # Step 2: Reset text state (forces next text to a new message)
        self.text_buffer = ""
        self.current_text_message_ts = None

        # Step 3: Upload file using 3-step process
        try:
            # Step 3a: Get upload URL
            log.debug(
                f"[Queue:{self.task_id}] Step 1: Getting upload URL for {op.filename}"
            )
            upload_url_response = await self.client.files_getUploadURLExternal(
                filename=op.filename, length=len(op.content_bytes)
            )
            upload_url = upload_url_response.get("upload_url")
            file_id = upload_url_response.get("file_id")

            if not upload_url or not file_id:
                raise ValueError("Failed to get upload URL from Slack")

            # Step 3b: Upload content to temporary URL
            log.debug(
                f"[Queue:{self.task_id}] Step 2: Uploading {len(op.content_bytes)} bytes"
            )
            import requests

            upload_response = await asyncio.to_thread(
                requests.post, upload_url, data=op.content_bytes
            )
            upload_response.raise_for_status()

            # Step 3c: Complete the upload
            log.debug(f"[Queue:{self.task_id}] Step 3: Completing external upload")
            comment = op.initial_comment or f"Attached file: {op.filename}"
            await self.client.files_completeUploadExternal(
                files=[{"id": file_id, "title": op.filename}],
                channel_id=self.channel_id,
                thread_ts=self.thread_ts,
                initial_comment=comment,
            )
            log.info(f"[Queue:{self.task_id}] Upload request completed for {op.filename}")

            # Step 4: CRITICAL - Poll files.info until file is visible
            log.info(f"[Queue:{self.task_id}] Step 4: Polling for file visibility...")
            await self._wait_for_file_visible(file_id, timeout_seconds=30)
            log.info(
                f"[Queue:{self.task_id}] ✅ File {op.filename} is now visible in channel"
            )

        except Exception as e:
            log.error(
                f"[Queue:{self.task_id}] Failed to upload file {op.filename}: {e}",
                exc_info=True,
            )
            # Post error message
            await self.client.chat_postMessage(
                channel=self.channel_id,
                thread_ts=self.thread_ts,
                text=f"❌ Failed to upload file: {op.filename}",
            )

    async def _handle_message_post(self, op: MessagePostOp):
        """Handle posting a new message."""
        log.debug(f"[Queue:{self.task_id}] Posting new message: {op.text[:50]}...")
        await self.client.chat_postMessage(
            channel=self.channel_id,
            thread_ts=self.thread_ts,
            text=op.text,
            blocks=op.blocks,
        )

    async def _handle_message_update(self, op: MessageUpdateOp):
        """Handle updating an existing message."""
        log.debug(f"[Queue:{self.task_id}] Updating message ts={op.ts}")
        await self.client.chat_update(
            channel=self.channel_id, ts=op.ts, text=op.text, blocks=op.blocks
        )

    async def _handle_message_delete(self, op: MessageDeleteOp):
        """Handle deleting a message."""
        log.debug(f"[Queue:{self.task_id}] Deleting message ts={op.ts}")
        await self.client.chat_delete(channel=self.channel_id, ts=op.ts)

    # --- Polling Helper ---

    async def _wait_for_file_visible(self, file_id: str, timeout_seconds: int = 30):
        """
        Poll files.info until the 'shares' object appears, indicating the file
        is fully processed and visible in the channel.

        This is the KEY to ensuring proper ordering - we don't proceed until
        Slack confirms the file is actually posted.

        Args:
            file_id: The Slack file ID to monitor
            timeout_seconds: Maximum time to wait for file visibility

        Raises:
            TimeoutError: If file doesn't become visible within timeout
        """
        start_time = asyncio.get_event_loop().time()
        backoff_delay = 0.5  # Start with 500ms
        max_backoff = 5.0  # Cap at 5 seconds

        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed >= timeout_seconds:
                raise TimeoutError(
                    f"File {file_id} was not shared within {timeout_seconds} seconds"
                )

            try:
                # Query the file info
                info_response = await self.client.files_info(file=file_id)
                file_info = info_response.get("file", {})

                # Check if the 'shares' object exists and is populated
                shares = file_info.get("shares")
                if shares:
                    # Check both public channels and private/DM shares
                    public_shares = shares.get("public", {})
                    private_shares = shares.get("private", {})

                    # Check if file is in our channel (could be in either public or private)
                    if self.channel_id in public_shares:
                        log.debug(
                            f"[Queue:{self.task_id}] File {file_id} confirmed in public channel"
                        )
                        return
                    elif self.channel_id in private_shares:
                        log.debug(
                            f"[Queue:{self.task_id}] File {file_id} confirmed in private/DM channel"
                        )
                        return
                    else:
                        log.debug(
                            f"[Queue:{self.task_id}] File {file_id} has shares but not in target channel. "
                            f"Public: {list(public_shares.keys())}, Private: {list(private_shares.keys())}"
                        )

                # Not ready yet, wait with exponential backoff
                log.debug(
                    f"[Queue:{self.task_id}] File {file_id} not yet shared. Waiting {backoff_delay:.2f}s..."
                )
                await asyncio.sleep(backoff_delay)
                backoff_delay = min(backoff_delay * 1.5, max_backoff)

            except Exception as e:
                log.warning(
                    f"[Queue:{self.task_id}] Error checking file info: {e}"
                )
                await asyncio.sleep(backoff_delay)
                backoff_delay = min(backoff_delay * 1.5, max_backoff)
