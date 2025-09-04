"""
A stateful stream parser for identifying and extracting fenced artifact blocks
from an LLM's text stream.
"""

import re
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import List, Dict, Any

# --- Constants ---
# These are duplicated from callbacks for now to keep the parser self-contained.
# They should eventually live in a shared constants module.
ARTIFACT_BLOCK_DELIMITER_OPEN = "«««"
ARTIFACT_BLOCK_DELIMITER_CLOSE = "»»»"
# The full sequence that must be matched to start a block.
BLOCK_START_SEQUENCE = f"{ARTIFACT_BLOCK_DELIMITER_OPEN}save_artifact:"
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

    def _reset_state(self):
        """Resets the parser to its initial IDLE state."""
        self._state = ParserState.IDLE
        self._speculative_buffer = ""
        self._artifact_buffer = ""
        self._block_params = {}
        self._last_progress_update_size = 0

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
            # The orchestrator (callback) will see this and know to fail the artifact.
            # We emit a BlockCompletedEvent so the orchestrator knows what was buffered.
            # The orchestrator is responsible for interpreting this as a failure.
            events.append(
                BlockCompletedEvent(
                    params=self._block_params, content=self._artifact_buffer
                )
            )

        self._reset_state()
        return ParserResult("".join(user_text_parts), events)

    def _process_idle(self, char: str, user_text_parts: List[str]):
        """State handler for when the parser is outside any block."""
        if char == BLOCK_START_SEQUENCE[0]:
            self._state = ParserState.POTENTIAL_BLOCK
            self._speculative_buffer += char
        else:
            user_text_parts.append(char)

    def _process_potential(
        self, char: str, user_text_parts: List[str], events: List[ParserEvent]
    ):
        """State handler for when a block might be starting."""
        self._speculative_buffer += char

        # If we have the full start sequence, we are now looking for the newline.
        if self._speculative_buffer.startswith(BLOCK_START_SEQUENCE):
            if char == "\n":
                # We found the newline, the block is officially started.
                self._state = ParserState.IN_BLOCK
                # Extract the parameters string between the start sequence and the newline
                params_str = self._speculative_buffer[len(BLOCK_START_SEQUENCE) : -1]
                self._block_params = dict(PARAMS_REGEX.findall(params_str))
                events.append(BlockStartedEvent(params=self._block_params))
                self._speculative_buffer = ""  # Clear buffer, we are done with it.
            # else, we are still buffering the parameters line.
            return

        # If we are still building up the start sequence itself
        if BLOCK_START_SEQUENCE.startswith(self._speculative_buffer):
            # It's still a potential match. Continue buffering.
            return

        # If we've reached here, the sequence is invalid.
        # Rollback: The sequence was invalid.
        rolled_back_text = self._speculative_buffer
        user_text_parts.append(rolled_back_text)
        events.append(BlockInvalidatedEvent(rolled_back_text=rolled_back_text))
        self._reset_state()

    def _process_in_block(self, char: str, events: List[ParserEvent]):
        """State handler for when the parser is inside a block, buffering content."""
        self._artifact_buffer += char

        # Check for the closing delimiter
        if self._artifact_buffer.endswith(ARTIFACT_BLOCK_DELIMITER_CLOSE):
            # Block is complete.
            final_content = self._artifact_buffer[
                : -len(ARTIFACT_BLOCK_DELIMITER_CLOSE)
            ]
            events.append(
                BlockCompletedEvent(params=self._block_params, content=final_content)
            )
            self._reset_state()
        else:
            # Check if we should emit a progress update
            current_size = len(self._artifact_buffer.encode("utf-8"))
            if (
                current_size - self._last_progress_update_size
            ) >= self._progress_update_interval:
                new_chunk = self._artifact_buffer[
                    self._last_progress_update_size : current_size
                ]
                events.append(
                    BlockProgressedEvent(buffered_size=current_size, chunk=new_chunk)
                )
                self._last_progress_update_size = current_size
