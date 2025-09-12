"""
Enumerations used throughout the application.
"""

from enum import Enum


class SenderType(str, Enum):
    """Types of message senders."""
    USER = "user"
    AGENT = "agent"
    SYSTEM = "system"


class TaskStatus(str, Enum):
    """Task execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"




class MessageType(str, Enum):
    """Types of messages."""
    TEXT = "text"
    FILE = "file"
    IMAGE = "image"
    DOCUMENT = "document"


class ValidationErrorType(str, Enum):
    """Types of validation errors."""
    REQUIRED_FIELD = "required_field"
    INVALID_FORMAT = "invalid_format"
    OUT_OF_RANGE = "out_of_range"
    DUPLICATE_VALUE = "duplicate_value"
    BUSINESS_RULE = "business_rule"