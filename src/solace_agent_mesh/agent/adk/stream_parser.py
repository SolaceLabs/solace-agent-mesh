"""
A stateful stream parser for identifying and extracting fenced artifact blocks
from an LLM's text stream.
"""

import logging
import re
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import List, Dict, Any

from ...common.utils.embeds.constants import (
    EMBED_DELIMITER_OPEN,
    EMBED_DELIMITER_CLOSE,
)

log = logging.getLogger(__name__)

# --- Constants ---
# These are duplicated from callbacks for now to keep the parser self-contained.
# They should eventually live in a shared constants module.
ARTIFACT_BLOCK_DELIMITER_OPEN = "«««"
ARTIFACT_BLOCK_DELIMITER_CLOSE = "»»»"
# The full sequences that must be matched to start a block.
SAVE_ARTIFACT_START_SEQUENCE = f"{ARTIFACT_BLOCK_DELIMITER_OPEN}save_artifact:"
TEMPLATE_START_SEQUENCE = f"{ARTIFACT_BLOCK_DELIMITER_OPEN}template:"
TEMPLATE_LIQUID_START_SEQUENCE = f"{ARTIFACT_BLOCK_DELIMITER_OPEN}template_liquid:"
# For backward compatibility
BLOCK_START_SEQUENCE = SAVE_ARTIFACT_START_SEQUENCE
# Regex to parse parameters from a confirmed start line.
PARAMS_REGEX = re.compile(r'(\w+)\s*=\s*"(.*?)"')


# --- Parser State and Events (as per design doc) ---
class ParserState(Enum):
    """Represents the current state of the stream parser."""

    IDLE = auto()
    POTENTIAL_BLOCK = auto()
    IN_BLOCK = auto()


@dataclass
class ParserEvent:
    """Base class for events emitted by the parser."""

    pass


@dataclass
class BlockStartedEvent(ParserEvent):
    """Emitted when a fenced block's start is confirmed."""

    params: Dict[str, Any]


@dataclass
class BlockProgressedEvent(ParserEvent):
    """Emitted periodically while content is being buffered for a block."""

    params: Dict[str, Any]
    buffered_size: int
    chunk: str


@dataclass
class BlockCompletedEvent(ParserEvent):
    """Emitted when a fenced block is successfully closed."""

    params: Dict[str, Any]
    content: str


@dataclass
class BlockInvalidatedEvent(ParserEvent):
    """Emitted when a potential block start is found to be invalid."""

    rolled_back_text: str


@dataclass
class TemplateBlockStartedEvent(ParserEvent):
    """Emitted when a template block's start is confirmed."""

    params: Dict[str, Any]


@dataclass
class TemplateBlockCompletedEvent(ParserEvent):
    """Emitted when a template block is successfully closed."""

    params: Dict[str, Any]
    template_content: str


@dataclass
class ParserResult:
    """The result of processing a single text chunk."""

    user_facing_text: str = ""
    events: List[ParserEvent] = field(default_factory=list)


# --- The Parser Class ---
class FencedBlockStreamParser:
    """
    Processes a stream of text chunks to identify and extract fenced artifact blocks.

    This class implements a state machine to robustly handle partial delimiters
    and block content that may be split across multiple chunks from an LLM stream.
    It is designed to be side-effect-free; it emits events that an orchestrator
    (like an ADK callback) can use to perform actions.
    """

    def __init__(self, progress_update_interval_bytes: int = 4096):
        """Initializes the parser and its state machine."""
        self._state = ParserState.IDLE
        self._speculative_buffer = ""
        self._artifact_buffer = ""
        self._block_params: Dict[str, Any] = {}
        self._progress_update_interval = progress_update_interval_bytes
        self._last_progress_update_size = 0
        self._last_progress_chunk_end = 0  # Character position in buffer where last chunk ended
        # Track block type and nesting for template handling
        self._current_block_type: str = None  # "save_artifact" or "template"
        self._nesting_depth = 0  # Track if we're inside a block
        self._previous_state: ParserState = None  # Track state before POTENTIAL_BLOCK
        # Safety limit: force emission after this many pending bytes (to handle unclosed embeds)
        # Use minimum of 8KB to handle long templates/embeds
        self._max_pending_bytes = max(progress_update_interval_bytes * 4, 8192)  # Min 8KB
        # Store the original opening line for rollback if block is unterminated
        self._block_opening_line: str = ""

    def _reset_state(self):
        """Resets the parser to its initial IDLE state."""
        self._state = ParserState.IDLE
        self._speculative_buffer = ""
        self._artifact_buffer = ""
        self._block_params = {}
        self._last_progress_update_size = 0
        self._last_progress_chunk_end = 0
        self._current_block_type = None
        self._nesting_depth = 0
        self._previous_state = None
        self._block_opening_line = ""

    def _is_safe_to_emit_chunk(self) -> bool:
        """
        Check if current buffer position is safe for chunking (not inside an embed).

        Looks at the content since the last chunk emission to see if there's an
        unclosed embed delimiter. If so, waits until the embed is closed before emitting.

        Returns:
            True if safe to emit chunk (no partial embeds), False otherwise.
        """
        # Check the portion of buffer we're about to emit
        buffer_to_check = self._artifact_buffer[self._last_progress_chunk_end:]

        # Find last occurrence of opening delimiter
        last_open = buffer_to_check.rfind(EMBED_DELIMITER_OPEN)

        if last_open == -1:
            # No embed delimiter found in this portion
            return True

        # Found an opening delimiter - check if it's closed
        last_close = buffer_to_check.rfind(EMBED_DELIMITER_CLOSE, last_open)

        # Safe only if there's a closing delimiter after the opening one
        return last_close > last_open

    def process_chunk(self, text_chunk: str) -> ParserResult:
        """
        Processes the next chunk of text from the stream.

        Args:
            text_chunk: The string content from the LLM stream.

        Returns:
            A ParserResult object containing the text to show to the user and
            a list of any events that occurred during processing.
        """
        user_text_parts: List[str] = []
        events: List[ParserEvent] = []

        for char in text_chunk:
            if self._state == ParserState.IDLE:
                self._process_idle(char, user_text_parts)
            elif self._state == ParserState.POTENTIAL_BLOCK:
                self._process_potential(char, user_text_parts, events)
            elif self._state == ParserState.IN_BLOCK:
                self._process_in_block(char, events)

        return ParserResult("".join(user_text_parts), events)

    def finalize(self) -> ParserResult:
        """
        Call this at the end of an LLM turn to handle any unterminated blocks.
        This will perform a rollback on any partial block and return the
        buffered text.
        """
        user_text_parts: List[str] = []
        events: List[ParserEvent] = []

        if self._state == ParserState.POTENTIAL_BLOCK:
            # The turn ended mid-potential-block. This is a rollback.
            rolled_back_text = self._speculative_buffer
            user_text_parts.append(rolled_back_text)
            events.append(BlockInvalidatedEvent(rolled_back_text=rolled_back_text))
        elif self._state == ParserState.IN_BLOCK:
            # The turn ended while inside a block. This is an error/failure.
            log.warning(
                "[StreamParser] finalize() found unterminated block! Type: %s, buffer length: %d, nesting_depth: %d.",
                self._current_block_type,
                len(self._artifact_buffer),
                self._nesting_depth,
            )
            
            # Handle differently based on block type:
            # - Template blocks: Still emit TemplateBlockCompletedEvent (templates are processed server-side)
            # - Save_artifact blocks: Emit BlockInvalidatedEvent with rolled-back text (need to show original text to user)
            if self._current_block_type == "template":
                # Template blocks should still be processed even if unterminated
                events.append(
                    TemplateBlockCompletedEvent(
                        params=self._block_params,
                        template_content=self._artifact_buffer,
                    )
                )
            else:
                # For save_artifact blocks, this happens when the LLM outputs partial artifact markers in text
                # (e.g., explaining how to use artifacts) without actually completing the block.
                # We need to return the original text to the user so they can see it.
                log.warning(
                    "[StreamParser] Unterminated save_artifact block. Returning original text to user."
                )
                
                # Reconstruct the original text: opening line + buffered content
                # This is what the LLM actually output, which should be shown to the user
                rolled_back_text = self._block_opening_line + self._artifact_buffer
                user_text_parts.append(rolled_back_text)
                
                # Emit a BlockInvalidatedEvent to signal that this was not a valid artifact block
                # The callback can use this to clean up any in-progress UI
                events.append(BlockInvalidatedEvent(rolled_back_text=rolled_back_text))

        self._reset_state()
        return ParserResult("".join(user_text_parts), events)

    def _process_idle(self, char: str, user_text_parts: List[str]):
        """State handler for when the parser is outside any block."""
        if char == BLOCK_START_SEQUENCE[0]:
            self._previous_state = ParserState.IDLE
            self._state = ParserState.POTENTIAL_BLOCK
            self._speculative_buffer += char
        else:
            user_text_parts.append(char)

    def _process_potential(
        self, char: str, user_text_parts: List[str], events: List[ParserEvent]
    ):
        """State handler for when a block might be starting."""
        self._speculative_buffer += char

        # Check if we match save_artifact or template start sequences
        matched_sequence = None
        matched_type = None

        if self._speculative_buffer.startswith(SAVE_ARTIFACT_START_SEQUENCE):
            matched_sequence = SAVE_ARTIFACT_START_SEQUENCE
            matched_type = "save_artifact"
        elif self._speculative_buffer.startswith(TEMPLATE_LIQUID_START_SEQUENCE):
            matched_sequence = TEMPLATE_LIQUID_START_SEQUENCE
            matched_type = "template"
        elif self._speculative_buffer.startswith(TEMPLATE_START_SEQUENCE):
            matched_sequence = TEMPLATE_START_SEQUENCE
            matched_type = "template"

        if matched_sequence:
            if char == "\n":
                # We found the newline, the block is officially started.

                # If we're already inside a save_artifact block and this is a template,
                # we need to pass it through as literal text (preserve nesting)
                if self._nesting_depth > 0 and matched_type == "template":
                    # Preserve template literally inside artifact
                    self._artifact_buffer += self._speculative_buffer
                    # Increment nesting depth so we know to skip the next »»»
                    # (it will close the nested template, not the outer artifact)
                    self._nesting_depth += 1
                    # Don't reset state! We're still inside the save_artifact block.
                    # Just clear the speculative buffer and stay IN_BLOCK to continue
                    # buffering the rest of the artifact content.
                    self._speculative_buffer = ""
                    self._state = ParserState.IN_BLOCK
                    return

                self._state = ParserState.IN_BLOCK
                self._current_block_type = matched_type
                self._nesting_depth += 1

                # Store the original opening line for rollback if block is unterminated
                # This includes the full line: «««save_artifact: filename="test.md"\n
                self._block_opening_line = self._speculative_buffer

                # Extract the parameters string between the start sequence and the newline
                params_str = self._speculative_buffer[len(matched_sequence) : -1]
                self._block_params = dict(PARAMS_REGEX.findall(params_str))

                if matched_type == "save_artifact":
                    events.append(BlockStartedEvent(params=self._block_params))
                elif matched_type == "template":
                    events.append(TemplateBlockStartedEvent(params=self._block_params))

                self._speculative_buffer = ""  # Clear buffer, we are done with it.
            # else, we are still buffering the parameters line.
            return

        # If we are still building up a start sequence (could be either)
        if (SAVE_ARTIFACT_START_SEQUENCE.startswith(self._speculative_buffer) or
            TEMPLATE_LIQUID_START_SEQUENCE.startswith(self._speculative_buffer) or
            TEMPLATE_START_SEQUENCE.startswith(self._speculative_buffer)):
            # It's still a potential match. Continue buffering.
            return

        # If we've reached here, the sequence is invalid.
        # Rollback: The sequence was invalid.
        rolled_back_text = self._speculative_buffer

        # Check if we were IN_BLOCK before transitioning to POTENTIAL_BLOCK
        # If so, add the rolled-back text to the artifact buffer, not user-visible text
        if self._previous_state == ParserState.IN_BLOCK:
            log.debug(
                "[StreamParser] Invalid sequence '%s' detected while IN_BLOCK. Adding to artifact buffer.",
                repr(rolled_back_text),
            )
            self._artifact_buffer += rolled_back_text
            self._speculative_buffer = ""
            self._state = ParserState.IN_BLOCK
            # Don't emit BlockInvalidatedEvent - this is just normal artifact content
        else:
            # We were IDLE, so this is user-facing text
            user_text_parts.append(rolled_back_text)
            events.append(BlockInvalidatedEvent(rolled_back_text=rolled_back_text))
            self._speculative_buffer = ""
            self._state = ParserState.IDLE

        self._previous_state = None

    def _process_in_block(self, char: str, events: List[ParserEvent]):
        """State handler for when the parser is inside a block, buffering content."""
        # Check if this might be the start of a nested block
        if char == BLOCK_START_SEQUENCE[0]:
            # This might be the start of a nested template block
            # Transition to POTENTIAL_BLOCK to check
            self._previous_state = ParserState.IN_BLOCK
            self._state = ParserState.POTENTIAL_BLOCK
            self._speculative_buffer += char
            return

        self._artifact_buffer += char

        # Check for the closing delimiter
        if self._artifact_buffer.endswith(ARTIFACT_BLOCK_DELIMITER_CLOSE):
            # Check if this is closing a nested block or the current block
            if self._nesting_depth > 1:
                # This »»» is closing a nested template block, not the outer save_artifact
                # Keep it in the buffer and just decrement nesting
                self._nesting_depth -= 1
                # Don't emit events, don't strip the delimiter, just continue buffering
            else:
                # This is closing the outermost block (nesting_depth == 1)
                # Block is complete.
                final_content = self._artifact_buffer[
                    : -len(ARTIFACT_BLOCK_DELIMITER_CLOSE)
                ]

                # Emit the appropriate completion event based on block type
                if self._current_block_type == "template":
                    events.append(
                        TemplateBlockCompletedEvent(
                            params=self._block_params, template_content=final_content
                        )
                    )
                else:
                    # Default to save_artifact behavior
                    events.append(
                        BlockCompletedEvent(
                            params=self._block_params, content=final_content
                        )
                    )

                # Decrement nesting depth
                self._nesting_depth = max(0, self._nesting_depth - 1)
                self._reset_state()
        else:
            # Check if we should emit a progress update (only for save_artifact blocks)
            if self._current_block_type == "save_artifact":
                # Calculate current total size in bytes (for threshold check)
                current_size_bytes = len(self._artifact_buffer.encode("utf-8"))

                # Check if we've accumulated enough new bytes since last update
                bytes_since_last = current_size_bytes - self._last_progress_update_size
                if bytes_since_last >= self._progress_update_interval:
                    # Check if it's safe to emit (not inside an embed)
                    # OR force emit if we've exceeded safety limit (very long unclosed embed)
                    force_emit = bytes_since_last >= self._max_pending_bytes

                    if force_emit:
                        log.warning(
                            "[StreamParser] Forcing chunk emission due to safety limit (%d bytes pending). "
                            "Possible unclosed embed or very long embed.",
                            bytes_since_last
                        )

                    if self._is_safe_to_emit_chunk() or force_emit:
                        # Extract all new content since last progress update
                        # Slice by character position (not bytes) to avoid UTF-8 issues
                        current_char_position = len(self._artifact_buffer)
                        new_chunk = self._artifact_buffer[self._last_progress_chunk_end:]

                        events.append(
                            BlockProgressedEvent(
                                params=self._block_params,
                                buffered_size=current_size_bytes,  # Total bytes accumulated so far
                                chunk=new_chunk,  # All new content since last update
                            )
                        )

                        # Update tracking: character position for slicing, bytes for threshold
                        self._last_progress_chunk_end = current_char_position
                        self._last_progress_update_size = current_size_bytes
                    # else: wait for embed to close before emitting
