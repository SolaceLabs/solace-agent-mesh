"""
Handles A2A topic construction and translation between A2A and ADK message formats.
Consolidated from src/a2a_adk_host/a2a_protocol.py and src/tools/common/a2a_protocol.py.
"""

from typing import Any, Dict, List, Optional, Tuple
import json
import base64
import re
import uuid
from datetime import datetime, timezone
from solace_ai_connector.common.log import log
from google.genai import types as adk_types
from google.adk.events import Event as ADKEvent

from a2a.types import (
    Message as A2AMessage,
    TextPart,
    FilePart,
    DataPart,
    Part as A2APart,
    JSONRPCResponse,
    InternalError,
    TaskStatus,
    TaskState,
    TaskStatusUpdateEvent,
)

from .a2a.protocol import get_gateway_response_topic, get_gateway_status_topic

A2A_LLM_STREAM_CHUNKS_PROCESSED_KEY = "temp:llm_stream_chunks_processed"
A2A_STATUS_SIGNAL_STORAGE_KEY = "temp:a2a_status_signals_collected"


